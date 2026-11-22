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

"""Split the widget's area into regions for bars, labels, axis and readout.

Pure. Space is taken in this order, and what is left holds the bars, whose
length the ``%`` scale then divides:

1. the box, ``borderwidth`` cells on each side;
2. the graph label: in the box's top or bottom edge when there is a box,
   otherwise a row of its own;
3. the axis (vertical graphs: tick-label columns plus a ruler column, left);
4. segment labels (vertical: a row below; horizontal: a column to the left);
5. the baseline (one row below, or one column left of, the bars);
6. the readout (horizontal only: a column to the right);
7. the axis (horizontal graphs: a ruler row and a tick-label row, below).

See ARCHITECTURE.md, BarGraph: layout.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from tkcurses._charts.text import fit
from tkcurses._core.cells import cells
from tkcurses.bargraph._glyphs import POINTS_PER_CELL, Orient

#: The anchors the graph label accepts, as ``ttk.LabelFrame``'s.
LABEL_ANCHORS = ("n", "nw", "ne", "s", "sw", "se")

#: Rows a horizontal graph's axis takes: the ruler and the tick labels.
HORIZONTAL_AXIS_ROWS = 2

#: Cells of edge left visible either side of a graph label set in the box
#: (the corner and one line cell: ``┌─ Title ─┐``).
TITLE_INSET = 2


@dataclass(frozen=True, slots=True)
class Rect:
    """A rectangle in cells, relative to the widget's window."""

    x: int
    y: int
    width: int
    height: int

    @property
    def empty(self) -> bool:
        return self.width <= 0 or self.height <= 0

    def inset(self, cells: int) -> Rect:
        """This rect with ``cells`` taken off every side."""
        return Rect(
            self.x + cells,
            self.y + cells,
            max(0, self.width - 2 * cells),
            max(0, self.height - 2 * cells),
        )

    def take_top(self, rows: int) -> tuple[Rect, Rect]:
        """``(taken, rest)`` with up to ``rows`` taken from the top."""
        rows = min(max(0, rows), self.height)
        return (
            Rect(self.x, self.y, self.width, rows),
            Rect(self.x, self.y + rows, self.width, self.height - rows),
        )

    def take_bottom(self, rows: int) -> tuple[Rect, Rect]:
        """``(taken, rest)`` with up to ``rows`` taken from the bottom."""
        rows = min(max(0, rows), self.height)
        return (
            Rect(self.x, self.y + self.height - rows, self.width, rows),
            Rect(self.x, self.y, self.width, self.height - rows),
        )

    def take_left(self, columns: int) -> tuple[Rect, Rect]:
        """``(taken, rest)`` with up to ``columns`` taken from the left."""
        columns = min(max(0, columns), self.width)
        return (
            Rect(self.x, self.y, columns, self.height),
            Rect(self.x + columns, self.y, self.width - columns, self.height),
        )

    def take_right(self, columns: int) -> tuple[Rect, Rect]:
        """``(taken, rest)`` with up to ``columns`` taken from the right."""
        columns = min(max(0, columns), self.width)
        return (
            Rect(self.x + self.width - columns, self.y, columns, self.height),
            Rect(self.x, self.y, self.width - columns, self.height),
        )


@dataclass(frozen=True, slots=True)
class LayoutSpec:
    """The options that decide where things go.

    ``axis_label_width`` is the widest tick label in cells, used by a
    vertical graph's axis. ``readout_width`` is the widest readout in cells;
    0 means no readout. Both are measured by the caller, which knows the
    tick values and the readout format.
    """

    orient: Orient = "vertical"
    segments: int = 1
    thickness: int = 1
    gap: int = 1
    relative: bool = True
    borderwidth: int = 0
    title: str = ""
    labelanchor: str = "n"
    labels: tuple[str, ...] = field(default=())
    labelwidth: int = 12
    axis: bool = False
    axis_label_width: int = 0
    readout_width: int = 0
    baseline: bool = False
    #: The axis title; drawn only in a box's edge.
    axis_title: str = ""

    def __post_init__(self) -> None:
        if self.orient not in ("vertical", "horizontal"):
            raise ValueError(f"bad orient {self.orient!r}")
        for name in ("segments", "thickness"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be >= 1")
        for name in (
            "gap",
            "borderwidth",
            "labelwidth",
            "axis_label_width",
            "readout_width",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0")
        if self.labelanchor not in LABEL_ANCHORS:
            raise ValueError(f"bad labelanchor {self.labelanchor!r}")
        if self.readout_width and self.orient != "horizontal":
            raise ValueError("readout needs orient=horizontal")

    @property
    def has_labels(self) -> bool:
        return any(self.labels)

    @property
    def label_column_width(self) -> int:
        """A horizontal graph's segment-label column, without its spacer."""
        if not self.has_labels:
            return 0
        return min(max(cells(label) for label in self.labels), self.labelwidth)


@dataclass(frozen=True, slots=True)
class Layout:
    """Where each part of the graph goes.

    ``tracks`` and ``labels`` have one rect per segment, in segment order.
    A segment that doesn't fit is clipped: its track is cut short, or is
    empty (zero width or height) when none of it fits.
    """

    orient: Orient
    bars: Rect
    tracks: tuple[Rect, ...]
    title: Rect | None = None
    labels: tuple[Rect, ...] = ()
    axis: Rect | None = None
    readout: Rect | None = None
    baseline: Rect | None = None
    #: Where the axis title goes in the box's edge, its spaces included;
    #: None when it isn't drawn.
    axis_title: Rect | None = None

    @property
    def length_cells(self) -> int:
        """Cells available along the bars, which the ``%`` scale divides."""
        return self.bars.height if self.orient == "vertical" else self.bars.width


def track_sizes(cross_cells: int, spec: LayoutSpec) -> list[int]:
    """Each segment's thickness, before clipping.

    Absolute scale: ``thickness`` each. ``%`` scale: the cross axis, minus
    gaps, shared evenly; leading segments take the leftover cells one each.
    If that would make bars thinner than ``thickness``, they fall back to
    ``thickness`` and the trailing ones are clipped.
    """
    count = spec.segments
    if spec.relative:
        available = cross_cells - spec.gap * (count - 1)
        base, extra = divmod(max(0, available), count)
        if base >= spec.thickness:
            return [base + (1 if index < extra else 0) for index in range(count)]
    return [spec.thickness] * count


def compute_layout(width: int, height: int, spec: LayoutSpec) -> Layout:
    """Lay the graph out in a ``width`` x ``height`` window."""
    outer = Rect(0, 0, max(0, width), max(0, height))
    area = outer.inset(spec.borderwidth)
    title = None
    if spec.title:
        top = spec.labelanchor.startswith("n")
        if spec.borderwidth > 0:
            # In the box's edge, clear of the corners.
            row = outer.y if top else outer.y + outer.height - 1
            span = outer.width - 2 * TITLE_INSET
            if span > 0 and outer.height > 0:
                title = Rect(outer.x + TITLE_INSET, row, span, 1)
        else:
            title, area = area.take_top(1) if top else area.take_bottom(1)
            if title.empty:
                title = None

    if spec.orient == "vertical":
        layout = _vertical(area, spec, title)
    else:
        layout = _horizontal(area, spec, title)
    spot = axis_title_spot(outer, spec)
    return replace(layout, axis_title=spot) if spot is not None else layout


def axis_title_spot(outer: Rect, spec: LayoutSpec) -> Rect | None:
    """Where the axis title goes, or None if it isn't drawn.

    In the box's edge at the axis's end - the top above a vertical graph's
    axis, the bottom below a horizontal one's - at the left. If the graph's
    own label is there, the label keeps its place and the axis title goes
    to the right; if it fits at neither end, it isn't drawn.
    """
    if not (spec.axis and spec.axis_title and spec.borderwidth > 0):
        return None
    if outer.width < 2 or outer.height < 2:
        return None
    vertical = spec.orient == "vertical"
    row = outer.y if vertical else outer.y + outer.height - 1
    span = Rect(outer.x + TITLE_INSET, row, outer.width - 2 * TITLE_INSET, 1)
    width = cells(spec.axis_title) + 2
    if width > span.width:
        return None
    taken: tuple[int, int] | None = None
    if spec.title:
        bottom = outer.y + outer.height - 1
        label_row = outer.y if spec.labelanchor.startswith("n") else bottom
        if label_row == row:
            x, text = place_text(span, f" {spec.title} ", spec.labelanchor)
            taken = (x, x + cells(text))
    for x in (span.x, span.x + span.width - width):
        # A cell of border between the two, so they read as two.
        if taken is None or x + width < taken[0] or x > taken[1]:
            return Rect(x, row, width, 1)
    return None


def _vertical(area: Rect, spec: LayoutSpec, title: Rect | None) -> Layout:
    axis = None
    if spec.axis:
        axis, area = area.take_left(spec.axis_label_width + 1)
    labels_row = baseline = None
    if spec.has_labels:
        labels_row, area = area.take_bottom(1)
    if spec.baseline:
        baseline, area = area.take_bottom(1)
    bars = area
    tracks = []
    offset = 0
    for size in track_sizes(bars.width, spec):
        visible = max(0, min(size, bars.width - offset))
        tracks.append(
            Rect(bars.x + min(offset, bars.width), bars.y, visible, bars.height)
        )
        offset += size + spec.gap
    labels: tuple[Rect, ...] = ()
    if labels_row is not None:
        labels = tuple(
            Rect(track.x, labels_row.y, track.width, labels_row.height)
            for track in tracks
        )
    if axis is not None:
        axis = Rect(axis.x, bars.y, axis.width, bars.height)
    if baseline is not None:
        baseline = Rect(bars.x, baseline.y, bars.width, baseline.height)
    return Layout("vertical", bars, tuple(tracks), title, labels, axis, None, baseline)


def _horizontal(area: Rect, spec: LayoutSpec, title: Rect | None) -> Layout:
    label_column = baseline = readout = axis = None
    if spec.has_labels:
        # The label column, then a space before the bars.
        label_column, area = area.take_left(spec.label_column_width + 1)
    if spec.baseline:
        baseline, area = area.take_left(1)
    if spec.readout_width:
        # A space, then the readout column.
        readout, area = area.take_right(spec.readout_width + 1)
        readout = Rect(
            readout.x + 1, readout.y, max(0, readout.width - 1), readout.height
        )
    if spec.axis:
        axis, area = area.take_bottom(HORIZONTAL_AXIS_ROWS)
    bars = area
    tracks = []
    offset = 0
    for size in track_sizes(bars.height, spec):
        visible = max(0, min(size, bars.height - offset))
        tracks.append(
            Rect(bars.x, bars.y + min(offset, bars.height), bars.width, visible)
        )
        offset += size + spec.gap
    labels: tuple[Rect, ...] = ()
    if label_column is not None:
        width = max(0, label_column.width - 1)
        labels = tuple(
            Rect(label_column.x, track.y, width, track.height) for track in tracks
        )
    if baseline is not None:
        baseline = Rect(baseline.x, bars.y, baseline.width, bars.height)
    if readout is not None:
        readout = Rect(readout.x, bars.y, readout.width, bars.height)
    if axis is not None:
        axis = Rect(bars.x, axis.y, bars.width, axis.height)
    return Layout(
        "horizontal", bars, tuple(tracks), title, labels, axis, readout, baseline
    )


def natural_size(spec: LayoutSpec, length_cells: int) -> tuple[int, int]:
    """The ``(width, height)`` a graph with bars ``length_cells`` long needs.

    For an absolute scale, ``length_cells`` is ``ceil(scale / 8)`` and this
    is the size the widget requests. For a ``%`` scale it is the smallest
    useful size; the geometry manager usually gives more.
    """
    count = spec.segments
    cross = count * spec.thickness + spec.gap * (count - 1)
    if spec.orient == "vertical":
        width = cross + (spec.axis_label_width + 1 if spec.axis else 0)
        height = length_cells + int(spec.has_labels) + int(spec.baseline)
    else:
        width = (
            (spec.label_column_width + 1 if spec.has_labels else 0)
            + int(spec.baseline)
            + length_cells
            + (spec.readout_width + 1 if spec.readout_width else 0)
        )
        height = cross + (HORIZONTAL_AXIS_ROWS if spec.axis else 0)
    if spec.title and spec.borderwidth == 0:
        height += 1
    edge = 2 * spec.borderwidth
    width += edge
    height += edge
    if spec.title:
        # The whole label: in a box's edge with a space either side and
        # clear of the corners, otherwise in a row of its own.
        if spec.borderwidth > 0:
            width = max(width, cells(spec.title) + 2 + 2 * TITLE_INSET)
        else:
            width = max(width, cells(spec.title))
    if spec.axis and spec.axis_title and spec.borderwidth > 0:
        # Room for the axis title too, beside the label if they share an
        # edge, so a graph of fixed size shows both.
        needed = cells(spec.axis_title) + 2 + 2 * TITLE_INSET
        shares = spec.title and spec.labelanchor.startswith("n") == (
            spec.orient == "vertical"
        )
        if shares:
            needed += cells(spec.title) + 2 + 1
        width = max(width, needed)
    return width, height


def length_cells_for(points: int) -> int:
    """Cells an absolute scale of ``points`` needs along the bars."""
    return math.ceil(points / POINTS_PER_CELL)


def place_text(rect: Rect, text: str, anchor: str) -> tuple[int, str]:
    """Where a one-row ``text`` goes in ``rect``: ``(x, text)``.

    Measured in cells, so a wide character counts two and a combining mark
    none. Cut with ``…`` when it doesn't fit. The anchor's ``w`` puts it at the
    left, ``e`` at the right, and neither centres it.
    """
    if rect.width <= 0:
        return rect.x, ""
    text = fit(text, rect.width)
    spare = rect.width - cells(text)
    if anchor.endswith("w"):
        return rect.x, text
    if anchor.endswith("e"):
        return rect.x + spare, text
    return rect.x + spare // 2, text
