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

"""Turn the model into a grid of cells. Pure.

Cells name color *roles* (series, threshold zone, marker, background), not
colors; the widget resolves roles to curses attributes.

Rendering goes in three steps:

1. :func:`segment_runs`: one segment's values become *runs*, each one role,
   laid end to end from 0 to the bar's tip, in points (eighths of a cell).
   Stacked mode lays the values end to end. Overlay mode starts every value
   at 0 and paints the longest first, so at each point the shortest value
   still covering it is the one seen.
2. :func:`cells_along`: the runs become one cell per step along the bar,
   applying the two-colors-per-cell rule (ARCHITECTURE.md, BarGraph).
3. :func:`render_bars`: each segment's cells are drawn across its track.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from tkcurses.bargraph._glyphs import EMPTY, FULL, POINTS_PER_CELL, Orient, partial
from tkcurses.bargraph._scale import ValueRange, to_points
from tkcurses.bargraph._thresholds import zones

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tkcurses.bargraph._layout import Layout

Mode = Literal["stacked", "overlay"]

#: A color role: ("series", i), ("zone", j), ("marker", k), ("text", 0) for
#: the axis, baseline and labels, ("grid", 0) for gridlines, or
#: ("background", 0).
Role = tuple[
    Literal["series", "zone", "marker", "shade", "text", "grid", "background"], int
]

BACKGROUND: Role = ("background", 0)
TEXT: Role = ("text", 0)
GRID: Role = ("grid", 0)


def series(index: int) -> Role:
    """The role for series ``index``."""
    return ("series", index)


def marker(index: int) -> Role:
    """The role for marker ``index``, in the order the markers were given."""
    return ("marker", index)


def zone(index: int) -> Role:
    """The role for threshold zone ``index``: 0 is the base color
    (``colors[0]``), ``k`` the ``k``-th threshold in ascending order."""
    return ("zone", index)


@dataclass(frozen=True, slots=True)
class Cell:
    """One character cell: its glyph and the roles for its fg and bg."""

    char: str = EMPTY
    fg: Role = BACKGROUND
    bg: Role = BACKGROUND


EMPTY_CELL = Cell()

Grid = list[list[Cell]]


@dataclass(frozen=True, slots=True)
class Run:
    """Points ``start`` (inclusive) to ``end`` (exclusive) in one role."""

    role: Role
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


# ------------------------------------------------------------------ runs ----


def segment_runs(
    values: Sequence[float], mode: Mode, maximum: float | ValueRange, peak_points: int
) -> list[Run]:
    """One segment's values as runs from 0 to the tip.

    Negative values count as 0. Stacked mode clamps the running total to
    ``maximum``; overlay clamps each value.
    """
    if mode == "stacked":
        return _stacked(values, maximum, peak_points)
    if mode == "overlay":
        return _overlay(values, maximum, peak_points)
    raise ValueError(f"bad mode {mode!r}")


def _stacked(
    values: Sequence[float], maximum: float | ValueRange, peak: int
) -> list[Run]:
    runs: list[Run] = []
    total = 0.0
    start = 0
    for index, value in enumerate(values):
        total += max(0.0, value)
        # Rounding the running total, not each value, keeps the tip exact.
        end = to_points(total, maximum, peak)
        if end > start:
            runs.append(Run(series(index), start, end))
            start = end
    return runs


def _overlay(
    values: Sequence[float], maximum: float | ValueRange, peak: int
) -> list[Run]:
    lengths = [(to_points(max(0.0, v), maximum, peak), i) for i, v in enumerate(values)]
    # Shortest first; on a tie the lower series is painted last, so on top.
    lengths.sort()
    runs: list[Run] = []
    start = 0
    for end, index in lengths:
        if end > start:
            runs.append(Run(series(index), start, end))
            start = end
    return runs


def threshold_runs(
    value: float, levels: Sequence[float], maximum: float | ValueRange, peak_points: int
) -> list[Run]:
    """A single value's runs, colored by threshold zone.

    ``levels`` are threshold levels in data units, ascending. Only the part
    of the bar above each level takes that threshold's color.
    """
    tip = to_points(max(0.0, value), maximum, peak_points)
    return [
        Run(zone(part.role), part.start, part.end)
        for part in zones(tip, levels, maximum, peak_points)
    ]


def zoned_runs(
    runs: Sequence[Run],
    levels: Sequence[float],
    maximum: float | ValueRange,
    peak_points: int,
) -> list[Run]:
    """``runs`` with every part above a threshold level recolored.

    Below the first level each run keeps its own role (its series); above
    level ``j`` the bar is ``zone(j + 1)``, whichever series is there. So
    on a stacked bar the levels apply to the total, and on an overlay bar to
    the longest value.
    """
    boundaries = [to_points(level, maximum, peak_points) for level in levels]
    result: list[Run] = []
    for run in runs:
        start = run.start
        while start < run.end:
            above = sum(1 for boundary in boundaries if boundary <= start)
            role = run.role if above == 0 else zone(above)
            following = [b for b in boundaries if b > start]
            end = min([run.end, *following])
            if result and result[-1].role == role and result[-1].end == start:
                result[-1] = Run(role, result[-1].start, end)
            else:
                result.append(Run(role, start, end))
            start = end
    return result


# ----------------------------------------------------------------- cells ----


def cells_along(
    runs: Sequence[Run],
    length_cells: int,
    orient: Orient = "vertical",
    keep_top: bool = False,
) -> list[Cell]:
    """The cells along one bar, index 0 at the zero edge.

    Runs past ``length_cells`` are clipped. ``keep_top`` protects the last
    run's color in a crowded cell (see :func:`_merge`).
    """
    top = runs[-1].role if keep_top and runs else None
    cells: list[Cell] = []
    for index in range(length_cells):
        low = index * POINTS_PER_CELL
        high = low + POINTS_PER_CELL
        pieces = _pieces(runs, low, high)
        cells.append(_cell(_merge(pieces, top), orient))
    return cells


def _pieces(runs: Sequence[Run], low: int, high: int) -> list[tuple[Role, int]]:
    """The roles in points ``low``-``high`` as ``(role, points)``, in order.

    Any space past the tip is background. No two neighbouring pieces share
    a role, since no two neighbouring runs do: a bar's series each come
    once and in order, the threshold zones above them rise, and
    :func:`zoned_runs` joins its own pieces. So nothing here joins them.
    """
    pieces: list[tuple[Role, int]] = []
    covered = 0
    for run in runs:
        start, end = max(run.start, low), min(run.end, high)
        if end > start:
            pieces.append((run.role, end - start))
            covered += end - start
    if covered < high - low:
        pieces.append((BACKGROUND, high - low - covered))
    return pieces


def _merge(
    pieces: list[tuple[Role, int]], top: Role | None = None
) -> list[tuple[Role, int]]:
    """Apply the two-colors-per-cell rule.

    While more than two pieces remain, the smallest colored piece goes to
    its larger colored neighbour (the lower one on a tie). Background, which
    only ever comes last, is never merged, so the tip never moves.

    ``top`` is a role that is never merged away while another colored piece
    could be instead: the highest threshold zone a bar reaches, so the
    alert color still shows at the tip of a crowded cell.
    """
    pieces = list(pieces)
    while len(pieces) > 2:
        colored = [i for i, (role, _) in enumerate(pieces) if role != BACKGROUND]
        movable = [i for i in colored if pieces[i][0] != top] or colored
        smallest = min(movable, key=lambda i: (pieces[i][1], i))
        neighbours = [
            i
            for i in (smallest - 1, smallest + 1)
            if 0 <= i < len(pieces) and pieces[i][0] != BACKGROUND
        ]
        into = max(neighbours, key=lambda i: (pieces[i][1], -i))
        role, points = pieces[into]
        pieces[into] = (role, points + pieces[smallest][1])
        del pieces[smallest]
    return pieces


def _cell(pieces: list[tuple[Role, int]], orient: Orient) -> Cell:
    """A cell from at most two pieces, the lower drawn as the partial glyph."""
    if len(pieces) == 1:
        role = pieces[0][0]
        if role == BACKGROUND:
            return EMPTY_CELL
        return Cell(FULL, role, BACKGROUND)
    (lower, points), (upper, _) = pieces
    return Cell(partial(points, orient), lower, upper)


# ------------------------------------------------------------------ grid ----


def render_bars(
    rows: Sequence[Sequence[float]],
    layout: Layout,
    mode: Mode,
    maximum: float | ValueRange,
    peak_points: int,
    levels: Sequence[float] = (),
) -> Grid:
    """Draw every segment's bar into its track.

    With threshold ``levels`` (data units, ascending), the part of each bar
    above a level takes that threshold's color (see :func:`zoned_runs`); a
    single-value bar is colored entirely by zone.

    Returns a grid the size of ``layout.bars``, indexed ``grid[row][col]``
    relative to its top-left corner. Vertical bars grow up from the bottom
    row; horizontal bars grow right from the left column.
    """
    bars = layout.bars
    grid: Grid = [[EMPTY_CELL] * bars.width for _ in range(bars.height)]
    vertical = layout.orient == "vertical"
    length = layout.length_cells
    for values, track in zip(rows, layout.tracks, strict=False):
        if track.empty:
            continue
        if levels and len(values) == 1:
            runs = threshold_runs(values[0], levels, maximum, peak_points)
        else:
            runs = segment_runs(values, mode, maximum, peak_points)
            if levels:
                runs = zoned_runs(runs, levels, maximum, peak_points)
        # The alert color is protected at the tip of a crowded cell.
        keep_top = bool(runs) and runs[-1].role[0] == "zone"
        cells = cells_along(runs, length, layout.orient, keep_top=keep_top)
        for along, cell in enumerate(cells):
            if vertical:
                row = bars.height - 1 - along
                for col in range(track.x - bars.x, track.x - bars.x + track.width):
                    grid[row][col] = cell
            else:
                col = along
                for row in range(track.y - bars.y, track.y - bars.y + track.height):
                    grid[row][col] = cell
    return grid
