# TkCurses - a tkinter-compatible API layer that renders to curses
# Copyright (C) 2026  Scott L. Fields
#
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""From values to pixels: where an XY chart's lines and areas go. Pure.

Values are placed on the plot by their axes, then joined as
``interpolation`` says, then clipped to the plot, in float pixels until
the last step so rounding happens once.

- ``straight`` joins each point to the next.
- ``step`` holds each value until the next x, then rises or falls: a
  step *after* the point, as Kibana's step lines are drawn.
- ``smooth`` is the monotone cubic of F. N. Fritsch and R. E. Carlson,
  "Monotone Piecewise Cubic Interpolation", *SIAM Journal on Numerical
  Analysis* 17(2), 1980, implemented from the paper: a cubic Hermite
  curve whose tangents are chosen so it never rises above or dips below
  the points it joins. It is sampled at every pixel column.

**More points than columns.** Where two points of a run fall in one
column of pixels, the run is reduced by M4, from U. Jugel, Z. Jerzak, G.
Hackenbroich and V. Markl, "M4: A Visualization-Oriented Time Series
Data Aggregation", *PVLDB* 7(10), 2014: each column keeps its first,
last, lowest and highest point, which draw the same pixels as all of
them. A run that dense is drawn straight: smoothing or steps are finer
than a pixel there.

**Clipping.** A line is clipped to the plot segment by segment, by the
algorithm of Y.-D. Liang and B. A. Barsky, "A New Concept and Method for
Line Clipping", *ACM Transactions on Graphics* 3(1), 1984. An area's
outline is clipped as a polygon, by I. E. Sutherland and G. W.
Hodgman's re-entrant clipping, "Reentrant Polygon Clipping",
*Communications of the ACM* 17(1), 1974. Both from their papers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING

from tkcurses._core.canvas import line_pixels

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tkcurses._charts.geometry import Rect
    from tkcurses._charts.scale import ValueRange

__all__ = [
    "INTERPOLATIONS",
    "POINTS",
    "Trace",
    "area",
    "clip_line",
    "clip_polygon",
    "dashes",
    "m4",
    "pixels",
    "points_shown",
    "project",
    "trace",
]

Point = tuple[float, float]

INTERPOLATIONS = ("straight", "smooth", "step")
POINTS = ("auto", "show", "hide")
#: With ``points="auto"``, points show when every two neighbours are at
#: least this many pixels apart.
POINT_SPACING = 4
#: A dotted line: this many pixels on, then this many off.
DASH = 2
#: A slope, in pixels per pixel, too small to be anything but flat.
FLAT = 1e-9


@dataclass(frozen=True, slots=True)
class Trace:
    """A piece of a series' line, in float pixels: solid, or dotted where
    it runs through a value missing values filled in."""

    points: tuple[Point, ...]
    dotted: bool = False


# ------------------------------------------------------------- placing


def project(
    xs: Sequence[float],
    ys: Sequence[float | None],
    xspan: ValueRange | None,
    yspan: ValueRange,
    plot: Rect,
) -> list[Point | None]:
    """Each ``(x, y)`` on the plot, in pixels, ``None`` where ``y`` is
    missing or the y axis cannot place it. ``xspan`` is ``None`` when the
    chart has one x, which goes in the middle."""
    right = plot.width - 1
    bottom = plot.y + plot.height - 1
    placed: list[Point | None] = []
    for x, y in zip(xs, ys, strict=True):
        across = 0.5 if xspan is None else xspan.position(x)
        up = None if y is None else yspan.position(y)
        if across is None or up is None:
            placed.append(None)
        else:
            placed.append((plot.x + across * right, bottom - up * (plot.height - 1)))
    return placed


# ------------------------------------------------------------- joining


def trace(
    points: Sequence[Point | None],
    filled: Sequence[bool],
    interpolation: str = "straight",
) -> list[Trace]:
    """A series' line: each run of placed points joined by
    ``interpolation``, split into solid and dotted pieces. A segment is
    dotted when either end was filled in.

    Raises:
        ValueError: If ``interpolation`` is not one of
            :data:`INTERPOLATIONS`.
    """
    if interpolation not in INTERPOLATIONS:
        raise ValueError(
            f'bad interpolation "{interpolation}": must be straight, smooth or step'
        )
    traces: list[Trace] = []
    for run, marks in _runs(points, filled):
        if _dense(run):
            run, marks = m4(run, marks)
            way = "straight"
        else:
            way = interpolation
        joined = _join(run, way)
        traces.extend(_split(joined, marks))
    return traces


def area(
    highs: Sequence[Point | None],
    lows: Sequence[Point | None] | None,
    baseline: float,
    interpolation: str = "straight",
) -> list[list[Point]]:
    """The outlines of an area, one for each run of placed points: along
    its top, then back along its bottom - the ``lows`` joined the same
    way, or the horizontal line at ``baseline`` when it has none."""
    shapes: list[list[Point]] = []
    count = len(highs)
    index = 0
    while index < count:
        if highs[index] is None or (lows is not None and lows[index] is None):
            index += 1
            continue
        start = index
        while (
            index < count
            and highs[index] is not None
            and (lows is None or lows[index] is not None)
        ):
            index += 1
        top_run = [p for p in highs[start:index] if p is not None]
        way = "straight" if _dense(top_run) else interpolation
        top = [p for p, _ in _join(top_run, way)]
        if lows is None:
            bottom = [(top[-1][0], baseline), (top[0][0], baseline)]
        else:
            low_run = [p for p in lows[start:index] if p is not None]
            bottom = [p for p, _ in _join(low_run, way)][::-1]
        shapes.append(top + bottom)
    return shapes


def _runs(
    points: Sequence[Point | None], filled: Sequence[bool]
) -> list[tuple[list[Point], list[bool]]]:
    runs: list[tuple[list[Point], list[bool]]] = []
    run: list[Point] = []
    marks: list[bool] = []
    for point, mark in zip(points, filled, strict=True):
        if point is None:
            if run:
                runs.append((run, marks))
            run, marks = [], []
        else:
            run.append(point)
            marks.append(mark)
    if run:
        runs.append((run, marks))
    return runs


def _dense(run: Sequence[Point]) -> bool:
    """Whether two neighbouring points share a column of pixels."""
    return any(round(a[0]) == round(b[0]) for a, b in pairwise(run))


def _join(run: Sequence[Point], way: str) -> list[tuple[Point, int]]:
    """The run joined, each point with the segment of the run it is on:
    ``k`` for the way from point ``k`` to point ``k + 1``."""
    if len(run) < 2:
        return [(run[0], 0)] if run else []
    if way == "step":
        joined = [(run[0], 0)]
        for k, ((_, y0), (x1, y1)) in enumerate(pairwise(run)):
            joined.append(((x1, y0), k))
            joined.append(((x1, y1), k))
        return joined
    if way == "smooth":
        return _smooth(run)
    return [(point, max(0, k - 1)) for k, point in enumerate(run)]


def _smooth(run: Sequence[Point]) -> list[tuple[Point, int]]:
    """Fritsch and Carlson's monotone cubic through ``run``, sampled at
    every whole pixel column between its points."""
    xs = [p[0] for p in run]
    ys = [p[1] for p in run]
    n = len(run)
    widths = [xs[k + 1] - xs[k] for k in range(n - 1)]
    slopes = [(ys[k + 1] - ys[k]) / widths[k] for k in range(n - 1)]
    # Step 1: tangents at the points, the secants' mean inside, the
    # secant itself at either end; flat where the secants change sign.
    tangents = [slopes[0]]
    for k in range(1, n - 1):
        if slopes[k - 1] * slopes[k] <= 0:
            tangents.append(0.0)
        else:
            tangents.append((slopes[k - 1] + slopes[k]) / 2)
    tangents.append(slopes[-1])
    # Steps 3 to 5: on a flat segment both ends are flat; elsewhere keep
    # alpha and beta inside the circle of radius 3, which is sufficient
    # for the cubic to be monotone on that segment.
    for k in range(n - 1):
        # In pixels, a billionth of a pixel per column is flat; dividing by
        # it would not be.
        if abs(slopes[k]) < FLAT:
            tangents[k] = tangents[k + 1] = 0.0
            continue
        alpha = tangents[k] / slopes[k]
        beta = tangents[k + 1] / slopes[k]
        if alpha < 0:
            tangents[k] = alpha = 0.0
        if beta < 0:
            tangents[k + 1] = beta = 0.0
        size = alpha * alpha + beta * beta
        if size > 9:
            tau = 3 / math.sqrt(size)
            tangents[k] = tau * alpha * slopes[k]
            tangents[k + 1] = tau * beta * slopes[k]
    joined = [(run[0], 0)]
    for k in range(n - 1):
        x0, x1, width = xs[k], xs[k + 1], widths[k]
        column = math.floor(x0) + 1
        while column < x1:
            t = (column - x0) / width
            joined.append(
                (
                    (
                        column,
                        _hermite(
                            ys[k], ys[k + 1], tangents[k], tangents[k + 1], width, t
                        ),
                    ),
                    k,
                )
            )
            column += 1
        joined.append((run[k + 1], k))
    return joined


def _hermite(
    y0: float, y1: float, m0: float, m1: float, width: float, t: float
) -> float:
    t2, t3 = t * t, t * t * t
    return (
        (2 * t3 - 3 * t2 + 1) * y0
        + (t3 - 2 * t2 + t) * width * m0
        + (-2 * t3 + 3 * t2) * y1
        + (t3 - t2) * width * m1
    )


def _split(joined: Sequence[tuple[Point, int]], marks: Sequence[bool]) -> list[Trace]:
    """The joined run cut where its segments change from solid to dotted."""
    if len(joined) == 1:
        return [Trace((joined[0][0],), marks[0])]
    traces: list[Trace] = []
    piece: list[Point] = [joined[0][0]]
    dotted: bool | None = None
    for (_, _), (point, k) in pairwise(joined):
        this = marks[k] or (k + 1 < len(marks) and marks[k + 1])
        if dotted is not None and this != dotted:
            traces.append(Trace(tuple(piece), dotted))
            piece = [piece[-1]]
        dotted = this
        piece.append(point)
    traces.append(Trace(tuple(piece), bool(dotted)))
    return traces


def m4(run: Sequence[Point], marks: Sequence[bool]) -> tuple[list[Point], list[bool]]:
    """``run`` with each column of pixels down to its first, lowest,
    highest and last point, in their order; their marks with them."""
    kept: list[int] = []
    index = 0
    while index < len(run):
        column = round(run[index][0])
        end = index
        while end + 1 < len(run) and round(run[end + 1][0]) == column:
            end += 1
        group = range(index, end + 1)
        low = min(group, key=lambda i: run[i][1])
        high = max(group, key=lambda i: run[i][1])
        kept.extend(sorted({index, low, high, end}))
        index = end + 1
    return [run[i] for i in kept], [marks[i] for i in kept]


# ------------------------------------------------------------ clipping


def clip_line(points: Sequence[Point], plot: Rect) -> list[list[Point]]:
    """The parts of a polyline inside the plot, by Liang and Barsky."""
    left, top = plot.x, plot.y
    right, bottom = plot.x + plot.width - 1, plot.y + plot.height - 1
    pieces: list[list[Point]] = []
    current: list[Point] = []
    if len(points) == 1:
        x, y = points[0]
        return [[points[0]]] if left <= x <= right and top <= y <= bottom else []
    for (x0, y0), (x1, y1) in pairwise(points):
        dx, dy = x1 - x0, y1 - y0
        low, high = 0.0, 1.0
        inside = True
        for p, q in (
            (-dx, x0 - left),
            (dx, right - x0),
            (-dy, y0 - top),
            (dy, bottom - y0),
        ):
            if p == 0:
                if q < 0:
                    inside = False
                    break
                continue
            r = q / p
            if p < 0:
                low = max(low, r)
            else:
                high = min(high, r)
            if low > high:
                inside = False
                break
        if not inside:
            if current:
                pieces.append(current)
            current = []
            continue
        start = (x0 + low * dx, y0 + low * dy)
        end = (x0 + high * dx, y0 + high * dy)
        if not current or current[-1] != start or low > 0:
            if current:
                pieces.append(current)
            current = [start]
        current.append(end)
        if high < 1:
            pieces.append(current)
            current = []
    if current:
        pieces.append(current)
    return pieces


def clip_polygon(points: Sequence[Point], plot: Rect) -> list[Point]:
    """A polygon cut to the plot, by Sutherland and Hodgman: clipped
    against each edge of the plot in turn."""
    edges = (
        (0, float(plot.x), 1),
        (0, float(plot.x + plot.width - 1), -1),
        (1, float(plot.y), 1),
        (1, float(plot.y + plot.height - 1), -1),
    )
    shape = list(points)
    for axis, limit, side in edges:
        if not shape:
            break
        out: list[Point] = []
        previous = shape[-1]
        for point in shape:
            here = (point[axis] - limit) * side >= 0
            before = (previous[axis] - limit) * side >= 0
            if here != before:
                out.append(_crossing(previous, point, axis, limit))
            if here:
                out.append(point)
            previous = point
        shape = out
    return shape


def _crossing(a: Point, b: Point, axis: int, limit: float) -> Point:
    """Where the segment from ``a`` to ``b`` crosses ``axis = limit``."""
    share = (limit - a[axis]) / (b[axis] - a[axis])
    other = 1 - axis
    crossed = a[other] + share * (b[other] - a[other])
    return (limit, crossed) if axis == 0 else (crossed, limit)


# ------------------------------------------------------------ pixels


def pixels(points: Sequence[Point]) -> list[tuple[int, int]]:
    """``points`` rounded to whole pixels, without a point repeating the
    one before it."""
    out: list[tuple[int, int]] = []
    for x, y in points:
        pixel = (round(x), round(y))
        if not out or out[-1] != pixel:
            out.append(pixel)
    return out


def dashes(points: Sequence[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """A dotted line's pieces: the pixels of the polyline, :data:`DASH` on
    and :data:`DASH` off, each piece its first and last pixel."""
    drawn = line_pixels(list(points))
    pieces = []
    for start in range(0, len(drawn), 2 * DASH):
        piece = drawn[start : start + DASH]
        pieces.append([piece[0], piece[-1]] if len(piece) > 1 else [piece[0]])
    return pieces


def points_shown(mode: str, columns: Sequence[float]) -> bool:
    """Whether a series' points are marked: always, never, or with
    ``"auto"`` when neighbouring points are :data:`POINT_SPACING` pixels
    apart or more, so a sparse series shows where its data is."""
    if mode not in POINTS:
        raise ValueError(f'bad points "{mode}": must be auto, show or hide')
    if mode != "auto":
        return mode == "show"
    return all(b - a >= POINT_SPACING for a, b in pairwise(sorted(columns)))
