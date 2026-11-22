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

"""Optional decorations, and the whole window put together. Pure.

Baseline, axis ticks, gridlines, markers, peak hold and the horizontal-only
readout are all off by default. :func:`compose` draws the window in this
order, last on top: gridlines -> bars -> baseline -> markers -> peak hold ->
axis -> readout -> labels -> graph label.

Gridlines go only in empty cells, so they always sit under the bars. A marker
or peak-hold line crossing a bar replaces only that cell's *graph
background*, never another color, so it never changes what the data shows.

Levels (ticks, markers, peaks) fall at cell resolution: each is drawn in the
cell its value's tip would end in. The one exception is a tick at the bottom
of the scale when there is a baseline: a bar of that value ends on the
baseline, not in the first cell, so its tick goes on the corner. Put in the
first cell, it would sit a cell closer to the next tick than every other pair.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tkcurses._charts.numformat import NumberFormat, for_readout
from tkcurses._charts.text import clusters
from tkcurses._core.cells import cells
from tkcurses.bargraph._glyphs import FULL, POINTS_PER_CELL
from tkcurses.bargraph._layout import Rect, place_text
from tkcurses.bargraph._render import (
    BACKGROUND,
    EMPTY_CELL,
    GRID,
    TEXT,
    Cell,
    Mode,
    Role,
    marker,
)
from tkcurses.bargraph._scale import (
    Steps,
    ValueRange,
    as_range,
    round_steps,
    tidy,
    to_points,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tkcurses.bargraph._layout import Layout
    from tkcurses.bargraph._render import Grid

#: A whole-window grid. ``None`` is a cell the graph leaves alone, such as
#: the box border TkCurses draws.
Window = list[list[Cell | None]]

# Line glyphs, by the direction they run.
H_LINE = "─"  # ─
V_LINE = "│"  # │
H_DASH = "┈"  # ┈ gridline across a vertical graph
V_DASH = "┊"  # ┊ gridline across a horizontal graph
TICK_LEFT = "┤"  # ┤ vertical axis ruler, tick pointing at the bars
TICK_DOWN = "┬"  # ┬ horizontal axis ruler, tick pointing at the labels
CORNER = "└"  # └ where the axis or baseline meet
CORNER_TICK_LEFT = "┴"  # ┴ that corner with a vertical axis's tick on it
CORNER_TICK_DOWN = "├"  # ├ that corner with a horizontal axis's tick on it

#: The second cell of a wide character: drawn by the character before it,
#: so nothing is written there.
CONTINUATION = Cell("", TEXT, BACKGROUND)

#: Fewest cells between ticks: rows on a vertical axis. A horizontal axis
#: needs the widest tick label plus one.
MIN_TICK_ROWS = 2


# ---------------------------------------------------------------- peaks ----


@dataclass(slots=True)
class PeakHold:
    """The highest value seen per segment within the last ``hold_ms``."""

    hold_ms: int
    #: (value, time it was reached in ms) per segment.
    peaks: list[tuple[float, float]] = field(default_factory=list)

    def update(self, values: Sequence[float], now_ms: float) -> list[float]:
        """Record ``values`` at ``now_ms`` and return the peaks to draw.

        Only a value at or above the held peak starts a hold. Once a hold
        has run out the peak follows the value down; it does not catch the
        value on its way down and hold that too.
        """
        if len(self.peaks) != len(values):
            self.peaks = [(value, now_ms) for value in values]
        held: list[float] = []
        for index, value in enumerate(values):
            peak, when = self.peaks[index]
            if value >= peak:
                self.peaks[index] = (value, now_ms)
                peak = value
            elif now_ms - when > self.hold_ms:
                # Expired: keep the old time, so the next lower value is
                # followed as well, until a rise starts a new hold.
                self.peaks[index] = (value, when)
                peak = value
            held.append(peak)
        return held


# ---------------------------------------------------------------- ticks ----


def auto_ticks(
    maximum: float | ValueRange,
    length_cells: int,
    min_spacing: int,
    steps: Steps = "decimal",
) -> list[float]:
    """Round tick values across the range that fit ``length_cells``.

    Linear: the step is the smallest of :func:`~scale.round_steps` that
    keeps ticks at least ``min_spacing`` cells apart on average - 1, 2 or 5
    times a power of ten; for ``"binary"`` steps, times a power of 1024;
    for a time unit, steps a clock reads well, 15 s, 1 min, 1 h - from the
    first multiple of it at or above the minimum. Log: see
    :func:`log_ticks`. Rounding to cells can still bring two together, so
    :func:`spaced` then drops any that land too close.
    """
    if not isinstance(maximum, ValueRange) and maximum <= 0:
        return [0.0]
    span = as_range(maximum)
    if length_cells <= 0:
        return [span.minimum]
    fits = max(1, length_cells // max(1, min_spacing))
    if span.log:
        return log_ticks(span, fits)
    for step in round_steps(steps):
        first = math.ceil(span.minimum / step - 1e-9)
        last = math.floor(span.maximum / step + 1e-9)
        if last - first <= fits:
            return [tidy(i * step) for i in range(first, last + 1)]
    raise AssertionError("unreachable")  # pragma: no cover


def log_ticks(span: ValueRange, fits: int) -> list[float]:
    """Ticks for a log range, at most about ``fits`` of them: each power of
    the base, and 2 and 5 times each when there is room for those too and
    the base is above 5. With too many powers, every second, third...
    """
    low = math.ceil(math.log(span.minimum, span.base) - 1e-9)
    high = math.floor(math.log(span.maximum, span.base) + 1e-9)
    powers = [tidy(span.base**k) for k in range(low, high + 1)]
    if not powers:
        return [span.minimum]
    between = [m for m in (2, 5) if m < span.base]
    if between and len(powers) * (1 + len(between)) <= fits:
        ticks = [
            tidy(power * m)
            for power in [tidy(span.base ** (low - 1)), *powers]
            for m in (1, *between)
        ]
        return sorted(t for t in set(ticks) if span.minimum <= t <= span.maximum)
    every = max(1, math.ceil(len(powers) / max(1, fits)))
    return powers[::every]


def even_ticks(maximum: float | ValueRange, count: int) -> list[float]:
    """``count`` ticks spread evenly along the bar (``ticks=N``): evenly
    spaced values on a linear range, a geometric series on a log one."""
    span = as_range(maximum)
    if count < 2:
        return [span.minimum]
    if span.log:
        ratio = span.maximum / span.minimum
        return [tidy(span.minimum * ratio ** (i / (count - 1))) for i in range(count)]
    width = span.maximum - span.minimum
    return [tidy(span.minimum + width * i / (count - 1)) for i in range(count)]


def level_cell(value: float, maximum: float | ValueRange, peak_points: int) -> int:
    """The cell, along the bar, where a bar of ``value`` would end."""
    points = to_points(value, maximum, peak_points)
    return max(0, points - 1) // POINTS_PER_CELL


def spaced(
    ticks: Sequence[float],
    maximum: float | ValueRange,
    peak_points: int,
    min_spacing: int,
) -> list[float]:
    """``ticks`` without any that land closer than ``min_spacing`` cells to
    the one kept before it."""
    kept: list[float] = []
    last: int | None = None
    for tick in ticks:
        cell = level_cell(tick, maximum, peak_points)
        if last is None or cell - last >= min_spacing:
            kept.append(tick)
            last = cell
    return kept


# ------------------------------------------------------------- readout ----


def readout_value(values: Sequence[float], mode: Mode) -> float:
    """What a segment's readout shows: the total when stacked, the largest
    value when overlaid."""
    if mode == "stacked":
        return sum(max(0.0, value) for value in values)
    return max((max(0.0, value) for value in values), default=0.0)


# --------------------------------------------------------------- compose ----


@dataclass(frozen=True, slots=True)
class Decor:
    """What to draw besides the bars. Levels are in data units."""

    maximum: float
    peak_points: int
    mode: Mode = "stacked"
    title: str = ""
    labelanchor: str = "n"
    #: The box's width; nothing but the graph label is drawn inside it.
    borderwidth: int = 0
    labels: tuple[str, ...] = ()
    baseline: bool = False
    #: Tick values, already chosen; empty for no axis ticks.
    ticks: tuple[float, ...] = ()
    axis: bool = False
    gridlines: bool = False
    markers: tuple[float, ...] = ()
    #: Per segment: the held peak and the role to draw it in, or None.
    peaks: tuple[tuple[float, Role] | None, ...] = ()
    #: Draw each segment's readout, in ``readoutformat`` if given, else in
    #: ``numbers`` (whole numbers unless digits or decimals are set).
    readout: bool = False
    readoutformat: str = ""
    #: How tick labels and the readout write values.
    numbers: NumberFormat = field(default_factory=NumberFormat)
    #: Where values fall along the bars; None for linear from 0 to maximum.
    values: ValueRange | None = None
    #: The axis title, drawn where the layout puts it. A name only: the
    #: tick labels keep their units, since each writes its own magnifier.
    axis_title: str = ""


def compose(
    width: int,
    height: int,
    layout: Layout,
    bars: Grid,
    rows: Sequence[Sequence[float]],
    decor: Decor,
) -> Window:
    """The whole ``width`` x ``height`` window: bars and decorations."""
    window: Window = [[None] * width for _ in range(height)]
    painter = _Painter(window, layout, decor)
    painter.bars(bars)
    if decor.gridlines:
        painter.gridlines()
    if decor.baseline:
        painter.baseline()
    for index, level in enumerate(decor.markers):
        painter.marker(level, marker(index))
    painter.peaks()
    if decor.axis:
        painter.axis()
    if (decor.readout or decor.readoutformat) and layout.readout is not None:
        painter.readout(rows)
    painter.labels()
    if decor.axis:
        painter.axis_title()
    painter.title()
    return window


class _Painter:
    def __init__(self, window: Window, layout: Layout, decor: Decor) -> None:
        self.window = window
        self.layout = layout
        self.decor = decor
        self.vertical = layout.orient == "vertical"
        height = len(window)
        width = len(window[0]) if window else 0
        self.inside = Rect(0, 0, width, height).inset(decor.borderwidth)

    # ------------------------------------------------------------ helpers

    def within(self, x: int, y: int, *, on_border: bool = False) -> bool:
        """Whether a cell is inside the box (or anywhere, ``on_border``)."""
        area = (
            Rect(0, 0, len(self.window[0]), len(self.window))
            if on_border
            else self.inside
        )
        return area.x <= x < area.x + area.width and area.y <= y < area.y + area.height

    def put(self, x: int, y: int, cell: Cell, *, on_border: bool = False) -> None:
        """Set a cell, if it is inside the box (or anywhere, ``on_border``)."""
        if self.within(x, y, on_border=on_border):
            self.window[y][x] = cell

    def text(self, x: int, y: int, text: str, *, on_border: bool = False) -> None:
        """``text`` from cell ``x``, a cell for each cell it takes.

        A wide character takes its cell and a :data:`CONTINUATION` after
        it, or is a space where only one cell is left; a combining mark
        goes into the cell of the character it follows.
        """
        column = x
        for glyph, width in clusters(text):
            if width == 2:
                if self.within(column + 1, y, on_border=on_border):
                    self.put(
                        column, y, Cell(glyph, TEXT, BACKGROUND), on_border=on_border
                    )
                    self.put(column + 1, y, CONTINUATION, on_border=on_border)
                else:
                    self.put(
                        column, y, Cell(" ", TEXT, BACKGROUND), on_border=on_border
                    )
                column += 2
            elif width:
                self.put(column, y, Cell(glyph, TEXT, BACKGROUND), on_border=on_border)
                column += 1

    def cell_of(self, value: float) -> int | None:
        """The cell along the bars for ``value``, or None past their end."""
        span = self.decor.values or self.decor.maximum
        cell = level_cell(value, span, self.decor.peak_points)
        return cell if cell < self.layout.length_cells else None

    def line_cells(self, along: int, across: Rect) -> list[tuple[int, int]]:
        """The ``(x, y)`` cells of a line across ``across`` at step ``along``."""
        bars = self.layout.bars
        if self.vertical:
            y = bars.y + bars.height - 1 - along
            return [(x, y) for x in range(across.x, across.x + across.width)]
        x = bars.x + along
        return [(x, y) for y in range(across.y, across.y + across.height)]

    def overlay(self, x: int, y: int, char: str, role: Role) -> None:
        """A line through a cell: drawn in empty cells, and in place of the
        graph background behind a partial glyph; never over a color."""
        current = self.window[y][x]
        # A line drawn earlier (gridline, marker) is replaced by a later
        # one on top; only the bars' own cells are protected.
        if (
            current is None
            or current == EMPTY_CELL
            or current.fg[0] in ("grid", "marker")
        ):
            self.put(x, y, Cell(char, role, BACKGROUND))
        elif current.bg == BACKGROUND and current.char != FULL:
            self.put(x, y, Cell(current.char, current.fg, role))

    # ---------------------------------------------------------- painters

    def bars(self, grid: Grid) -> None:
        bars = self.layout.bars
        for row, line in enumerate(grid):
            for col, cell in enumerate(line):
                self.put(bars.x + col, bars.y + row, cell)

    def gridlines(self) -> None:
        char = H_DASH if self.vertical else V_DASH
        for tick in self.decor.ticks:
            along = self.cell_of(tick)
            if along is None or tick <= 0:
                continue
            for x, y in self.line_cells(along, self.layout.bars):
                if self.window[y][x] in (None, EMPTY_CELL):
                    self.put(x, y, Cell(char, GRID, BACKGROUND))

    def baseline(self) -> None:
        line = self.layout.baseline
        if line is None:
            return
        char = H_LINE if self.vertical else V_LINE
        for y in range(line.y, line.y + line.height):
            for x in range(line.x, line.x + line.width):
                self.put(x, y, Cell(char, TEXT, BACKGROUND))

    def marker(self, level: float, role: Role) -> None:
        along = self.cell_of(level)
        if along is None:
            return
        char = H_LINE if self.vertical else V_LINE
        for x, y in self.line_cells(along, self.layout.bars):
            self.overlay(x, y, char, role)

    def peaks(self) -> None:
        char = H_LINE if self.vertical else V_LINE
        for track, peak in zip(self.layout.tracks, self.decor.peaks, strict=False):
            if peak is None or track.empty:
                continue
            value, role = peak
            along = self.cell_of(value)
            if along is None or value <= 0:
                continue
            for x, y in self.line_cells(along, track):
                self.overlay(x, y, char, role)

    def axis(self) -> None:
        axis = self.layout.axis
        if axis is None or axis.empty:
            return
        baseline = self.layout.baseline
        corner = baseline is not None and not baseline.empty
        ticks = {}
        span = as_range(self.decor.values or self.decor.maximum)
        for tick in self.decor.ticks:
            # Cell -1 is the corner: the baseline is where an empty bar ends.
            along = -1 if corner and tick <= span.minimum else self.cell_of(tick)
            if along is not None:
                ticks[along] = self.decor.numbers.format(tick, self.decor.maximum)
        floor = ticks.get(-1)
        if self.vertical:
            ruler = axis.x + axis.width - 1
            for along in range(self.layout.length_cells):
                y = axis.y + axis.height - 1 - along
                label = ticks.get(along)
                self.put(
                    ruler, y, Cell(TICK_LEFT if label else V_LINE, TEXT, BACKGROUND)
                )
                if label:
                    x, text = place_text(Rect(axis.x, y, axis.width - 1, 1), label, "e")
                    self.text(x, y, text)
            if corner:
                assert baseline is not None
                glyph = CORNER_TICK_LEFT if floor else CORNER
                self.put(ruler, baseline.y, Cell(glyph, TEXT, BACKGROUND))
                if floor:
                    row = Rect(axis.x, baseline.y, axis.width - 1, 1)
                    x, text = place_text(row, floor, "e")
                    self.text(x, baseline.y, text)
        else:
            ruler = axis.y
            # The label row only if the axis got both of its rows.
            labels_row = axis.y + 1 if axis.height > 1 else None
            free = axis.x
            if corner and floor:
                assert baseline is not None
                if labels_row is not None:
                    self.text(baseline.x, labels_row, floor)
                    free = baseline.x + cells(floor) + 1
            for along in range(self.layout.length_cells):
                x = axis.x + along
                label = ticks.get(along)
                self.put(
                    x, ruler, Cell(TICK_DOWN if label else H_LINE, TEXT, BACKGROUND)
                )
                # A label starts at its tick, or ends at the axis's right
                # edge if it would run past it; it is skipped if that
                # would run into the label before.
                start = min(x, axis.x + axis.width - cells(label or ""))
                if label and labels_row is not None and start >= free:
                    self.text(start, labels_row, label)
                    free = start + cells(label) + 1
            if corner:
                assert baseline is not None
                glyph = CORNER_TICK_DOWN if floor else CORNER
                self.put(baseline.x, ruler, Cell(glyph, TEXT, BACKGROUND))

    def readout(self, rows: Sequence[Sequence[float]]) -> None:
        readout = self.layout.readout
        if readout is None or readout.empty:
            return
        for track, values in zip(self.layout.tracks, rows, strict=False):
            if track.empty:
                continue
            value = readout_value(values, self.decor.mode)
            if self.decor.readoutformat:
                text = self.decor.readoutformat.format(value)
            else:
                text = for_readout(self.decor.numbers).format(value, self.decor.maximum)
            y = track.y + (track.height - 1) // 2
            x, text = place_text(Rect(readout.x, y, readout.width, 1), text, "e")
            self.text(x, y, text)

    def labels(self) -> None:
        for rect, label in zip(self.layout.labels, self.decor.labels, strict=False):
            if not label or rect.empty:
                continue
            if self.vertical:
                x, text = place_text(rect, label, "n")
                self.text(x, rect.y, text)
            else:
                y = rect.y + (rect.height - 1) // 2
                x, text = place_text(Rect(rect.x, y, rect.width, 1), label, "w")
                self.text(x, y, text)

    def axis_title(self) -> None:
        rect = self.layout.axis_title
        if rect is None or not self.decor.axis_title:
            return
        self.text(rect.x, rect.y, f" {self.decor.axis_title} ", on_border=True)

    def title(self) -> None:
        rect = self.layout.title
        if rect is None or not self.decor.title:
            return
        # In a box's edge the label gets a space either side, as Tk's does.
        boxed = self.decor.borderwidth > 0
        title = f" {self.decor.title} " if boxed else self.decor.title
        x, text = place_text(rect, title, self.decor.labelanchor)
        self.text(x, rect.y, text, on_border=boxed)
