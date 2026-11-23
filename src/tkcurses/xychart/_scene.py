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

"""What an XY chart draws, as canvas items. Pure.

:func:`chart` turns the series, the references and the options into a
list of :class:`Item` values, each with a key that stays the same from
one drawing to the next while it describes the same part: the widget
keeps the canvas item it made for a key, and changes it in place rather
than making another. Items come in drawing order: gridlines, reference
bands and the current time's marker under everything; then every area's
fill, every line, the reference lines and the points, so no fill hides a
line; then the axes, outside the plot. :func:`scene` is the series alone,
on a plot given in pixels.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tkcurses._charts.color import hex_color, mix
from tkcurses._charts.geometry import Rect
from tkcurses._charts.numformat import NumberFormat
from tkcurses._charts.scale import ScaleType, ValueRange, fitted_ticks, label_start
from tkcurses._charts.text import fit as fit_text
from tkcurses._charts.timeticks import time_ticks
from tkcurses._core.cells import cells
from tkcurses.xychart._axes import value_range
from tkcurses.xychart._fit import fit
from tkcurses.xychart._layout import Layout, layout
from tkcurses.xychart._path import (
    area,
    clip_line,
    clip_polygon,
    dashes,
    pixels,
    points_shown,
    project,
    trace,
)
from tkcurses.xychart._stack import Band, Layer, stack

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from tkcurses._charts.color import RGB
    from tkcurses.xychart._model import Model

__all__ = [
    "DIM",
    "LIGHT",
    "REFERENCE_COLOR",
    "TAG",
    "Config",
    "Item",
    "Reference",
    "chart",
    "scene",
]

#: The tag every item the chart makes carries, and the start of the tag
#: naming its part.
TAG = "xychart"
#: How far an area's fill is mixed from its line's colour toward the
#: background, at 256 colours and above.
DIM = 0.6
#: How far a point is mixed from its line's colour toward white.
LIGHT = 0.5
#: The colours below which a mixed colour would round back to its own.
MIXES_FROM = 256
#: A reference line's colour when it is given none.
REFERENCE_COLOR = "white"
#: Cells between two tick labels, at least, along the x axis and up the
#: value axis.
XGAP = 2
YGAP = 1


@dataclass(frozen=True, slots=True)
class Config:
    """The options a scene depends on, checked."""

    colors: tuple[str, ...]
    stackmode: str = "stacked"
    interpolation: str = "straight"
    points: str = "auto"
    missing: str = "hide"
    endvalues: str = "hide"
    dottedgaps: bool = False
    scaletype: ScaleType = "linear"
    logbase: float = 10.0
    bounds: str = "full"
    minimum: float | None = None
    maximum: float | None = None
    nicebounds: bool = True
    xlabel: str = ""
    ylabel: str = ""
    ticklabels: bool = True
    gridlines: bool = False
    nowmarker: bool = False
    numbers: NumberFormat = field(default_factory=NumberFormat)


@dataclass(frozen=True, slots=True)
class Reference:
    """A reference line across the plot at ``value``, on the value axis
    (``axis="y"``) or down it at an x (``axis="x"``), with a shaded
    ``band`` from one value to another under the series."""

    ident: str
    value: float
    text: str = ""
    color: str = ""
    band: tuple[float, float] | None = None
    axis: str = "y"


@dataclass(frozen=True, slots=True)
class Item:
    """One canvas item: what kind, where, how it looks, and its tags."""

    key: str
    kind: str
    coords: tuple[int, ...]
    options: tuple[tuple[str, Any], ...] = ()
    tags: tuple[str, ...] = field(default=(TAG,))


@dataclass(frozen=True, slots=True)
class _Frame:
    """What the series and the axes share: the bands to draw, each
    series' colour, and the two axes' ranges."""

    bands: list[Band]
    colors: dict[str, str]
    yspan: ValueRange
    #: ``None`` when the chart has one x.
    xspan: ValueRange | None
    xlow: float
    xhigh: float
    percentage: bool


def _frame(
    model: Model, config: Config, references: Sequence[Reference]
) -> _Frame | None:
    names = model.names()
    colors = {
        name: model.get(name).color or config.colors[i % len(config.colors)]
        for i, name in enumerate(names)
    }
    layers = []
    for series in model.shown():
        fitted = fit(series.xs, series.ys, config.missing, config.endvalues)
        layers.append(
            Layer(series.name, series.kind, tuple(series.xs), fitted.ys, fitted.filled)
        )
    bands = stack(layers, config.stackmode)
    has_area = any(band.kind == "area" for band in bands)
    percentage = config.stackmode == "percentage" and has_area
    values = _values(bands)
    for reference in references:
        if reference.axis == "y":
            values.append(reference.value)
            values.extend(reference.band or ())
    yspan = value_range(
        values,
        bounds=config.bounds,
        minimum=config.minimum,
        maximum=config.maximum,
        nice=config.nicebounds,
        scaletype=config.scaletype,
        base=config.logbase,
        areas=has_area,
        percentage=percentage,
    )
    xs = [x for band in bands for x in band.xs]
    if not xs:
        return None
    low, high = min(xs), max(xs)
    xspan = ValueRange(high, low) if high > low else None
    return _Frame(bands, colors, yspan, xspan, low, high, percentage)


def scene(
    model: Model,
    config: Config,
    plot: Rect,
    *,
    depth: int,
    rgb: Callable[[str], RGB | None],
    background: RGB,
) -> list[Item]:
    """The series alone, drawn in ``plot``, a rectangle of pixels.

    ``depth`` is the terminal's colours, 0 for none; ``rgb`` says what a
    colour spec is in red, green and blue, and ``background`` is the
    canvas's.
    """
    if plot.width < 1 or plot.height < 1:
        return []
    frame = _frame(model, config, ())
    if frame is None:
        return []
    fills, lines, dots = _series(frame, config, plot, depth, rgb, background)
    return fills + lines + dots


def chart(
    model: Model,
    config: Config,
    width: int,
    height: int,
    *,
    depth: int,
    rgb: Callable[[str], RGB | None],
    background: RGB,
    references: Sequence[Reference] = (),
    now: float | None = None,
    xkind: str = "number",
) -> list[Item]:
    """Everything the chart draws on a canvas ``width`` by ``height``
    cells: the series, their axes, gridlines and references.

    ``now`` is the time for ``nowmarker``, in epoch seconds; ``xkind`` is
    ``"time"`` when x is a time.
    """
    if width < 1 or height < 1:
        return []
    frame = _frame(model, config, references)
    if frame is None:
        return []
    numbers = config.numbers
    if frame.percentage:
        numbers = dataclasses.replace(numbers, units="%", unitscale="none")
    time = xkind == "time"

    def yticks(rows: int) -> list[float]:
        return fitted_ticks(frame.yspan, rows, lambda _: 1, YGAP, numbers.steps)

    def label_width(rows: int) -> int:
        if not config.ticklabels:
            return 0
        return max((cells(numbers.format(t)) for t in yticks(rows)), default=0)

    lay = layout(
        width,
        height,
        ylabel=bool(config.ylabel),
        ticklabels=config.ticklabels,
        title=bool(config.xlabel) or (time and config.ticklabels),
        label_width=label_width,
    )
    cell_plot = lay.plot
    plot = Rect(cell_plot.x, cell_plot.y * 2, cell_plot.width, cell_plot.height * 2)
    ink = ""
    grid = _dimmed("white", depth, rgb, background) if depth >= MIXES_FROM else ink

    yrows: list[tuple[int, str]] = []
    xcols: list[tuple[int, int, str]] = []
    context = ""
    if lay.axes:
        yrows = _yrows(yticks(cell_plot.height), frame.yspan, plot, numbers)
        xcols, context = _xcols(frame, cell_plot, time)

    under: list[Item] = []
    if config.gridlines and lay.axes:
        under.extend(_gridlines(yrows, xcols, cell_plot, grid))
    over: list[Item] = []
    for reference in references:
        span = frame.yspan if reference.axis == "y" else frame.xspan
        color = reference.color or REFERENCE_COLOR
        under.extend(
            _band(reference, span, plot, _dimmed(color, depth, rgb, background))
        )
        over.extend(_reference(reference, span, plot, color))
    if config.nowmarker and time and now is not None and frame.xspan is not None:
        under.extend(_now(now, frame.xspan, plot, ink))
    fills, lines, dots = _series(frame, config, plot, depth, rgb, background)
    axes = _axes(lay, config, yrows, xcols, context, ink) if lay.axes else []
    return under + fills + lines + over + dots + axes


def _series(
    frame: _Frame,
    config: Config,
    plot: Rect,
    depth: int,
    rgb: Callable[[str], RGB | None],
    background: RGB,
) -> tuple[list[Item], list[Item], list[Item]]:
    """The series' fills, lines and points, in ``plot`` (pixels)."""
    fills: list[Item] = []
    lines: list[Item] = []
    dots: list[Item] = []
    if plot.width < 1 or plot.height < 1:
        return fills, lines, dots
    yspan, xspan = frame.yspan, frame.xspan
    baseline = _baseline(yspan, plot)
    for band in frame.bands:
        color = frame.colors[band.name]
        tags = (TAG, f"{TAG}.series.{band.name}")
        highs = project(band.xs, band.highs, xspan, yspan, plot)
        if band.kind == "area":
            lows = (
                None
                if band.lows is None
                else project(band.xs, band.lows, xspan, yspan, plot)
            )
            fill = _dimmed(color, depth, rgb, background)
            for n, outline in enumerate(
                area(highs, lows, baseline, config.interpolation)
            ):
                shape = pixels(clip_polygon(outline, plot))
                if len(shape) >= 3:
                    fills.append(
                        Item(
                            f"area.{band.name}.{n}",
                            "polygon",
                            _flat(shape),
                            (("fill", fill), ("outline", "")),
                            (TAG, f"{TAG}.area.{band.name}"),
                        )
                    )
        filled = band.filled if config.dottedgaps else (False,) * len(band.filled)
        n = 0
        for piece in trace(highs, filled, config.interpolation):
            for part in clip_line(piece.points, plot):
                drawn = pixels(part)
                for run in dashes(drawn) if piece.dotted else [drawn]:
                    lines.append(_line(f"line.{band.name}.{n}", run, color, tags))
                    n += 1
        _points(band, highs, config.points, color, depth, rgb, plot, dots)
    return fills, lines, dots


# ---------------------------------------------------------------- axes


def _ypixel(position: float, plot: Rect) -> int:
    """The pixel row of a position up the value axis, 0 to 1."""
    return round(plot.y + plot.height - 1 - position * (plot.height - 1))


def _xpixel(position: float, plot: Rect) -> int:
    return round(plot.x + position * (plot.width - 1))


def _yrows(
    ticks: list[float], span: ValueRange, plot: Rect, numbers: NumberFormat
) -> list[tuple[int, str]]:
    """Each tick's cell row and label, bottom up. :func:`fitted_ticks`
    has spaced them a blank row apart in its own rounding; the row of a
    tick's pixel can differ from it by one, and no case has been found
    where two labels then touch. The property test in
    ``test_xychart_layout.py`` holds it."""
    rows: list[tuple[int, str]] = []
    for tick in ticks:
        position = span.position(tick)
        if position is None or not -1e-9 <= position <= 1 + 1e-9:
            continue
        rows.append((_ypixel(position, plot) // 2, numbers.format(tick)))
    return rows


def _xcols(
    frame: _Frame, plot: Rect, time: bool
) -> tuple[list[tuple[int, int, str]], str]:
    """Each x tick's column, where its label starts and the label; and a
    time axis's context."""
    span = frame.xspan
    if span is None:
        return [], ""
    if time:
        found = time_ticks(frame.xlow, frame.xhigh, plot.width, XGAP)
        ticks, labels, context = list(found.values), list(found.labels), found.context
    else:
        plain = NumberFormat()
        ticks = fitted_ticks(span, plot.width, lambda t: cells(plain.format(t)), XGAP)
        labels = [plain.format(t) for t in ticks]
        context = ""
    placed = []
    for tick, label in zip(ticks, labels, strict=True):
        position = span.position(tick)
        if position is None:
            continue
        column = _xpixel(position, plot)
        start = plot.x + label_start(position, cells(label), plot.width)
        placed.append((column, start, label))
    return placed, context


def _gridlines(
    yrows: list[tuple[int, str]],
    xcols: list[tuple[int, int, str]],
    plot: Rect,
    color: str,
) -> list[Item]:
    """Dotted lines across the plot at each tick, as text: under the
    series, which take the cells they cross."""
    tags = (TAG, f"{TAG}.grid")
    options = (("anchor", "nw"), ("fill", color))
    items = [
        Item(
            f"grid.y.{n}",
            "text",
            (plot.x, row * 2),
            (("text", "\u2508" * plot.width), *options),
            tags,
        )
        for n, (row, _) in enumerate(yrows)
    ]
    column_text = "\n".join("\u250a" * 1 for _ in range(plot.height))
    items.extend(
        Item(
            f"grid.x.{n}",
            "text",
            (column, plot.y * 2),
            (("text", column_text), *options),
            tags,
        )
        for n, (column, _, _) in enumerate(xcols)
    )
    return items


def _axes(
    lay: Layout,
    config: Config,
    yrows: list[tuple[int, str]],
    xcols: list[tuple[int, int, str]],
    context: str,
    ink: str,
) -> list[Item]:
    """The two axis lines with their ticks, the tick labels and titles."""
    assert lay.axis_column is not None and lay.axis_row is not None
    plot = lay.plot
    tags = (TAG, f"{TAG}.axis")
    left = lay.axis_column

    def text(key: str, column: int, row: int, words: str, anchor: str = "nw") -> Item:
        options = (("text", words), ("anchor", anchor), ("fill", ink))
        return Item(key, "text", (column, row * 2), options, tags)

    ticked = {row for row, _ in yrows}
    up = "\n".join(
        "\u2524" if row in ticked else "\u2502"
        for row in range(plot.y, plot.y + plot.height)
    )
    across_ticks = {column for column, _, _ in xcols}
    across = "\u2514" + "".join(
        "\u252c" if column in across_ticks else "\u2500"
        for column in range(plot.x, plot.x + plot.width)
    )
    items = [
        text("axis.y", left, plot.y, up),
        text("axis.x", left, lay.axis_row, across),
    ]
    if config.ticklabels:
        items.extend(
            text(f"tick.y.{n}", left, row, label, "ne")
            for n, (row, label) in enumerate(yrows)
        )
        if lay.tick_row is not None:
            items.extend(
                text(f"tick.x.{n}", start, lay.tick_row, label)
                for n, (_, start, label) in enumerate(xcols)
            )
    right = plot.x + plot.width
    if lay.title_row is not None:
        used = 0
        if context and config.ticklabels:
            shown = fit_text(context, right)
            items.append(text("context", 0, lay.title_row, shown))
            used = cells(shown) + XGAP
        if config.xlabel and right - used > 0:
            label = fit_text(config.xlabel, right - used)
            size = cells(label)
            start = max(plot.x + (plot.width - size) // 2, used)
            start = min(start, right - size)
            items.append(text("xlabel", start, lay.title_row, label))
    if lay.ylabel_row is not None and config.ylabel:
        items.append(text("ylabel", 0, lay.ylabel_row, fit_text(config.ylabel, right)))
    return items


# ----------------------------------------------------- references, now


def _band(
    reference: Reference, span: ValueRange | None, plot: Rect, fill: str
) -> list[Item]:
    """A reference's band, a rectangle cut to the plot, under the series."""
    if reference.band is None or span is None:
        return []
    first, second = (span.position(value) for value in reference.band)
    if first is None or second is None:
        return []
    low, high = min(first, second), max(first, second)
    if high < 0 or low > 1:
        return []
    low, high = max(low, 0.0), min(high, 1.0)
    if reference.axis == "y":
        x0, x1 = plot.x, plot.x + plot.width
        y0, y1 = _ypixel(high, plot), _ypixel(low, plot) + 1
    else:
        x0, x1 = _xpixel(low, plot), _xpixel(high, plot) + 1
        y0, y1 = plot.y, plot.y + plot.height
    tags = (TAG, f"{TAG}.ref.{reference.ident}")
    options = (("fill", fill), ("outline", ""))
    return [
        Item(
            f"ref.{reference.ident}.band", "rectangle", (x0, y0, x1, y1), options, tags
        )
    ]


def _reference(
    reference: Reference, span: ValueRange | None, plot: Rect, color: str
) -> list[Item]:
    """A reference's line, and its text at the right-hand end or the top,
    over the series."""
    if span is None:
        return []
    position = span.position(reference.value)
    if position is None or not -1e-9 <= position <= 1 + 1e-9:
        return []
    tags = (TAG, f"{TAG}.ref.{reference.ident}")
    right, bottom = plot.x + plot.width - 1, plot.y + plot.height - 1
    key = f"ref.{reference.ident}"
    if reference.axis == "y":
        row = _ypixel(position, plot)
        items = [_line(f"{key}.line", [(plot.x, row), (right, row)], color, tags)]
        if reference.text:
            label = fit_text(reference.text, plot.width)
            options = (("text", label), ("anchor", "e"), ("fill", color))
            items.append(Item(f"{key}.text", "text", (right + 1, row), options, tags))
        return items
    column = _xpixel(position, plot)
    items = [_line(f"{key}.line", [(column, plot.y), (column, bottom)], color, tags)]
    if reference.text:
        room = right - column
        if room >= cells(reference.text) or room >= column - plot.x:
            label, at, anchor = fit_text(reference.text, room), column + 1, "nw"
        else:
            label, at, anchor = fit_text(reference.text, column - plot.x), column, "ne"
        if label:
            options = (("text", label), ("anchor", anchor), ("fill", color))
            items.append(Item(f"{key}.text", "text", (at, plot.y), options, tags))
    return items


def _now(now: float, span: ValueRange, plot: Rect, color: str) -> list[Item]:
    """A line down the plot at the current time, when it is on the axis."""
    position = span.position(now)
    if position is None or not 0 <= position <= 1:
        return []
    column = _xpixel(position, plot)
    bottom = plot.y + plot.height - 1
    options = (("fill", color or "white"),)
    return [
        Item(
            "now",
            "line",
            (column, plot.y, column, bottom),
            options,
            (TAG, f"{TAG}.now"),
        )
    ]


def _values(bands: list[Band]) -> list[float | None]:
    """Every value the bands reach, top and bottom."""
    values: list[float | None] = []
    for band in bands:
        values.extend(band.highs)
        if band.lows is not None:
            values.extend(band.lows)
    return values


def _baseline(yspan: ValueRange, plot: Rect) -> float:
    """The pixel row of zero, kept on the plot: an area's bottom."""
    bottom = plot.y + plot.height - 1
    position = yspan.position(0.0)
    if position is None:  # a log axis: from its bottom
        return float(bottom)
    return min(max(bottom - position * (plot.height - 1), plot.y), bottom)


def _line(
    key: str, run: list[tuple[int, int]], color: str, tags: tuple[str, ...]
) -> Item:
    if len(run) == 1:
        return _dot(key, run[0], color, tags)
    return Item(key, "line", _flat(run), (("fill", color),), tags)


def _dot(key: str, at: tuple[int, int], color: str, tags: tuple[str, ...]) -> Item:
    """One pixel: a rectangle with no outline, whose fill stops short of its
    far corner as Tk's does, so the far corner is one pixel on."""
    x, y = at
    options = (("fill", color), ("outline", ""))
    return Item(key, "rectangle", (x, y, x + 1, y + 1), options, tags)


def _points(
    band: Band,
    highs: list[tuple[float, float] | None],
    mode: str,
    color: str,
    depth: int,
    rgb: Callable[[str], RGB | None],
    plot: Rect,
    out: list[Item],
) -> None:
    """A pixel at each value the series was given, a shade lighter."""
    given = [
        point
        for point, filled in zip(highs, band.filled, strict=True)
        if point is not None and not filled
    ]
    if not points_shown(mode, [x for x, _ in given]):
        return
    light = _lightened(color, depth, rgb)
    right, bottom = plot.x + plot.width - 1, plot.y + plot.height - 1
    tags = (TAG, f"{TAG}.point.{band.name}")
    for n, (x, y) in enumerate(given):
        px, py = round(x), round(y)
        if plot.x <= px <= right and plot.y <= py <= bottom:
            out.append(_dot(f"point.{band.name}.{n}", (px, py), light, tags))


def _dimmed(
    color: str, depth: int, rgb: Callable[[str], RGB | None], background: RGB
) -> str:
    own = rgb(color)
    if depth < MIXES_FROM or own is None:
        return color
    return hex_color(mix(own, background, DIM))


def _lightened(color: str, depth: int, rgb: Callable[[str], RGB | None]) -> str:
    own = rgb(color)
    if depth < MIXES_FROM or own is None:
        return "white"
    return hex_color(mix(own, (255, 255, 255), LIGHT))


def _flat(points: list[tuple[int, int]]) -> tuple[int, ...]:
    return tuple(c for point in points for c in point)
