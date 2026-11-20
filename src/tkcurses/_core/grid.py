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
#
# Portions follow logic in Tk's C sources, each named beside the code that
# follows it. Tcl and Tk are copyright the Regents of the University of
# California, Sun Microsystems, Inc., Scriptics Corporation, ActiveState
# Corporation, Apple Inc. and other parties, and are used under
# the Tcl/Tk licence; see THIRD_PARTY_NOTICES.md.

"""The grid geometry manager.

Grid lays children out in rows and columns. Unlike pack, where each child
carves a slice off what is left, every child names the cell it wants and the
manager works out how wide each column and how tall each row has to be.

The sizing is Tk's, from ``generic/tkGrid.c``, per axis. Each line takes
the size its own children need; lines in a ``uniform`` group are evened up;
a child spanning several lines then has any shortfall spread across them,
since a widget two columns wide constrains the pair rather than either one.
That is the size the grid asks for. Finally the space the container actually
has is shared among the lines by *weight* - and a line with no weight does
not grow at all, which is the rule most often missed: ``sticky`` decides how
a child sits in its cell, and only ``weight`` makes the cell itself bigger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tkcurses._core.geometry import Managed, Pad, Rect, Size

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["GridLayout", "GridOptions", "LineConfig", "parse_sticky"]

#: The sides a child may be stuck to, in the order Tk writes them.
STICKY_SIDES = ("n", "s", "e", "w")


def parse_sticky(sticky: str) -> frozenset[str]:
    """The set of sides in a sticky string.

    Raises:
        ValueError: If it names anything but n, s, e, w. Separators Tk
            tolerates - spaces and commas - are ignored.
    """
    sides = set()
    for character in sticky.lower():
        if character in " ,":
            continue
        if character not in STICKY_SIDES:
            raise ValueError(f"bad sticky value {sticky!r}")
        sides.add(character)
    return frozenset(sides)


@dataclass
class GridOptions:
    """Where one child sits in the grid.

    Attributes:
        row: Row index, counting from zero.
        column: Column index.
        rowspan: How many rows the child covers.
        columnspan: How many columns.
        sticky: Sides of the cell the child is stuck to; stretching between
            two opposite sides, aligning against a single one.
        padx: Cells of space left and right of the child, inside its cell.
            The two sides are separate - ``padx=(0, 1)`` pads only the right -
            which is why this is a :class:`Pad` and not a number.
        pady: Cells above and below, likewise per side.
        ipadx: Cells added to the child's own width.
        ipady: Cells added to the child's own height.
    """

    row: int = 0
    column: int = 0
    rowspan: int = 1
    columnspan: int = 1
    sticky: str = ""
    # default_factory, not Pad(), only to satisfy RUF009: a frozen Pad is
    # safe to share, but the rule cannot tell one from a mutable default.
    padx: Pad = field(default_factory=Pad)
    pady: Pad = field(default_factory=Pad)
    ipadx: int = 0
    ipady: int = 0

    def demand(self, requested: Size) -> Size:
        """Room this child needs in its cell, padding included."""
        return Size(
            requested.width + 2 * self.ipadx + self.padx.total,
            requested.height + 2 * self.ipady + self.pady.total,
        )


@dataclass
class LineConfig:
    """How one row or column behaves.

    Attributes:
        weight: Share of leftover space this line claims. Zero - the default -
            means the line never grows beyond what its children need.
        minsize: Smallest the line may be, in cells.
        pad: Cells added to the largest child wholly in the line, as Tk adds
            it; a line with no such child gets none.
        uniform: Lines sharing a name are kept in proportion to their weights,
            a weight of zero counting as one.
    """

    weight: int = 0
    minsize: int = 0
    pad: int = 0
    uniform: str = ""


@dataclass
class _Axis:
    """One direction's line sizes, once they have been worked out."""

    sizes: list[int] = field(default_factory=list)

    def total(self) -> int:
        """Cells the lines take altogether."""
        return sum(self.sizes)

    def offset(self, index: int) -> int:
        """Where a line starts, relative to the grid's origin."""
        return sum(self.sizes[:index])

    def extent(self, start: int, span: int) -> int:
        """Cells covered by ``span`` lines from ``start``."""
        return sum(self.sizes[start : start + span])


def _c_div(numerator: int, denominator: int) -> int:
    """Integer division as C does it, truncating towards zero.

    Tk's arithmetic below is C's; Python's ``//`` floors instead, which
    differs as soon as a quantity goes negative.
    """
    quotient = abs(numerator) // abs(denominator)
    return quotient if (numerator < 0) == (denominator < 0) else -quotient


def _resolve(
    count: int,
    configs: dict[int, LineConfig],
    children: list[tuple[int, int, int]],
) -> tuple[list[int], int]:
    """Where each line ends at the grid's natural size, and that size.

    ``children`` are ``(first line, span, cells needed)``. This is Tk's
    ``ResolveConstraints`` from ``generic/tkGrid.c``, step for step, called
    as ``ArrangeGrid`` calls it - with no size imposed - and the step
    numbers are its. Measured on Tk 9.0.2 before porting: four uniform
    columns needing 6 under a spanning child needing 25 end at 6, 12, 18
    and 25 - the extra cell goes to the last column, where the rounding
    puts it - and a share ``ArrangeGrid`` then adds to.
    """
    if count == 0:
        return [], 0
    # Step 1: the lines' own constraints.
    lines = [configs.get(index, LineConfig()) for index in range(count)]
    min_size = [line.minsize for line in lines]
    weight = [line.weight for line in lines]
    # Step 2: a child in one line sizes it, its line's pad included; a
    # spanning child is binned by the line it ends in, for steps 3 and 4.
    spanning: list[list[tuple[int, int]]] = [[] for _ in range(count)]
    for first, span, size in children:
        last = first + span - 1
        if span > 1:
            spanning[last].append((span, size))
        elif last >= 0:
            min_size[last] = max(min_size[last], size + lines[last].pad)
    # Step 2b: a uniform group's lines are as big, per weight, as its
    # biggest; a weight of zero counts as one.
    unit: dict[str, int] = {}
    for index, line in enumerate(lines):
        if line.uniform:
            each = max(1, weight[index])
            needed = (min_size[index] + each - 1) // each
            unit[line.uniform] = max(unit.get(line.uniform, 0), needed)
    for index, line in enumerate(lines):
        if line.uniform:
            min_size[index] = unit[line.uniform] * max(1, weight[index])

    def min_before(index: int) -> int:
        # Tk keeps a line before the first, at offset zero.
        return min_offset[index] if index >= 0 else 0

    # Step 3: the least each line can end at, left to right.
    min_offset = [0] * count
    offset = 0
    for index in range(count):
        min_offset[index] = min_size[index] + offset
        for span, size in spanning[index]:
            min_offset[index] = max(min_offset[index], size + min_before(index - span))
        offset = min_offset[index]
    required = offset
    # Step 4: the most each line can end at, right to left.
    max_offset = [offset] * count
    index = count - 1
    while index > 0:
        for span, size in spanning[index]:
            first = index - span
            if first >= 0 and offset - size < max_offset[first]:
                max_offset[first] = offset - size
        offset -= min_size[index]
        index -= 1
        if max_offset[index] < offset:
            offset = max_offset[index]
        else:
            max_offset[index] = offset
    # Step 5: where a run of line ends is not yet fixed, share the room it
    # has by weight - evenly with no weights - cumulatively, so the
    # rounding lands at the end of the run.
    start = 0
    passes = 0
    while start < count:
        if min_offset[start] == max_offset[start]:
            start += 1
            continue
        passes += 1
        if passes > 4 * count + 4:
            # Each pass fixes at least one line end in Tk's reasoning; a
            # bound costs nothing and turns a mistake into a wrong layout
            # rather than a hung program.
            break
        end = start + 1
        while end < count - 1 and min_offset[end] != max_offset[end]:
            end += 1
        total_weight = sum(weight[start : end + 1])
        need = sum(min_size[start : end + 1])
        have = max_offset[end] - min_before(start - 1)
        no_weights = total_weight == 0
        if no_weights:
            total_weight = end - start + 1
        fits = False
        while not fits:
            fits = True
            previous = min_before(start - 1)
            given = so_far = 0
            for index in range(start, end + 1):
                each = 1 if no_weights else weight[index]
                so_far += each
                grow = _c_div((have - need) * so_far, total_weight) - given
                given += grow
                if each > 0 and previous + min_size[index] + grow > max_offset[index]:
                    # Not that much room: work out how much "have" this
                    # line can take, and try again with that.
                    grow = max_offset[index] - min_size[index] - previous
                    new_have = _c_div(grow * total_weight, each)
                    if new_have > total_weight:
                        new_have = new_have // total_weight * total_weight
                    if new_have <= 0:
                        new_have = have - need - 1
                        if new_have > 3 * total_weight:
                            new_have = new_have * 3 // 4
                        if new_have > total_weight:
                            new_have = new_have // total_weight * total_weight
                        new_have = max(new_have, 1)
                    have = new_have + need
                    fits = False
                    break
                previous = max(previous + min_size[index] + grow, min_offset[index])
        given = so_far = 0
        for index in range(start, end + 1):
            so_far += 1 if no_weights else weight[index]
            grow = _c_div((have - need) * so_far, total_weight) - given
            given += grow
            min_size[index] += grow
            min_offset[index] = max(
                min_offset[index], min_before(index - 1) + min_size[index]
            )
        for index in range(end, start, -1):
            max_offset[index - 1] = min(
                max_offset[index - 1], max_offset[index] - min_size[index]
            )
    # Step 6.
    return min_offset, required


def _adjust(size: int, ends: list[int], configs: dict[int, LineConfig]) -> int:
    """Fit the line ends to ``size`` by weight, and return the size used.

    Tk's ``AdjustOffsets`` from ``generic/tkGrid.c``: room to spare goes to
    the weighted lines cumulatively, so a remainder lands on the later ones
    - five rows of weight 1 sharing 13 cells are 2, 3, 2, 3, 3 high; too
    little room is taken from the weighted lines down to their ``minsize``,
    and past that the grid is cut off. With no weights nothing moves, and
    the anchor decides where the grid sits. ``ends`` is changed in place.
    """
    count = len(ends)
    if count == 0:
        return 0
    diff = size - ends[-1]
    if diff == 0:
        return size
    lines = [configs.get(index, LineConfig()) for index in range(count)]
    total_weight = sum(line.weight for line in lines)
    if total_weight == 0:
        return ends[-1]
    if diff > 0:
        so_far = 0
        for index, line in enumerate(lines):
            so_far += line.weight
            ends[index] += diff * so_far // total_weight
        return size

    def current(index: int) -> int:
        return ends[index] - (ends[index - 1] if index > 0 else 0)

    least = [
        line.minsize if line.weight > 0 else current(index)
        for index, line in enumerate(lines)
    ]
    if size <= sum(least):
        offset = 0
        for index in range(count):
            offset += least[index]
            ends[index] = offset
        return sum(least)
    while diff < 0:
        shares = [
            line.weight if current(index) > line.minsize else 0
            for index, line in enumerate(lines)
        ]
        total_weight = sum(shares)
        if total_weight == 0:
            break
        step = diff
        for index, line in enumerate(lines):
            if shares[index]:
                most = _c_div(
                    total_weight * (line.minsize - current(index)), shares[index]
                )
                step = max(step, most)
        so_far = 0
        for index in range(count):
            so_far += shares[index]
            ends[index] += _c_div(step * so_far, total_weight)
        diff -= step
    return size


def _sizes(ends: list[int]) -> list[int]:
    """Each line's size, from where each one ends."""
    return [end - (ends[index - 1] if index else 0) for index, end in enumerate(ends)]


class GridLayout:
    """Grids one container's children."""

    #: Gridded children decide how much room their container needs.
    propagates = True

    def __init__(self) -> None:
        self._options: dict[int, GridOptions] = {}
        self._widgets: dict[int, Managed] = {}
        self._hidden: dict[int, GridOptions] = {}
        self._rows: dict[int, LineConfig] = {}
        self._columns: dict[int, LineConfig] = {}
        self.anchor = "nw"

    # ----------------------------------------------------------- membership

    def add(self, widget: Managed, options: GridOptions) -> None:
        """Place ``widget`` in the grid, or move it."""
        self._options[id(widget)] = options
        self._widgets[id(widget)] = widget
        self._hidden.pop(id(widget), None)

    def remove(self, widget: Managed, *, keep: bool = False) -> None:
        """Take ``widget`` out of the grid.

        ``keep`` remembers where it was, which is what separates
        ``grid_remove`` from ``grid_forget``: the first can be undone by a
        bare ``grid()``, the second cannot.
        """
        options = self._options.pop(id(widget), None)
        self._widgets.pop(id(widget), None)
        if keep and options is not None:
            self._hidden[id(widget)] = options
        else:
            self._hidden.pop(id(widget), None)

    def remembered(self, widget: Managed) -> GridOptions | None:
        """Options kept by a previous ``grid_remove``, if any."""
        return self._hidden.get(id(widget))

    def options_for(self, widget: Managed) -> GridOptions | None:
        """Where ``widget`` sits, or None if it is not gridded."""
        return self._options.get(id(widget))

    def slaves(
        self,
        container: object = None,  # noqa: ARG002 - Layout protocol
        *,
        row: int | None = None,
        column: int | None = None,
    ) -> list[Managed]:
        """Gridded children, optionally only those in one row or column.

        Ordered by position - down the rows, then across - so the answer does
        not depend on the order they were added in.
        """
        found = []
        for key, widget in self._widgets.items():
            options = self._options[key]
            if row is not None and not (
                options.row <= row < options.row + options.rowspan
            ):
                continue
            if column is not None and not (
                options.column <= column < options.column + options.columnspan
            ):
                continue
            found.append((options.row, options.column, widget))
        return [widget for _, _, widget in sorted(found, key=lambda item: item[:2])]

    def configure_row(self, index: int, config: LineConfig) -> None:
        """Set how one row behaves."""
        self._rows[index] = config

    def configure_column(self, index: int, config: LineConfig) -> None:
        """Set how one column behaves."""
        self._columns[index] = config

    def row_config(self, index: int) -> LineConfig:
        """How one row behaves, defaulted if never configured."""
        return self._rows.get(index, LineConfig())

    def column_config(self, index: int) -> LineConfig:
        """How one column behaves."""
        return self._columns.get(index, LineConfig())

    def size(self) -> tuple[int, int]:
        """The grid's extent as ``(columns, rows)``.

        Counts what is occupied, as Tk does: a grid with a child at row 3 is
        four rows tall whether or not rows 0 to 2 hold anything.
        """
        columns = rows = 0
        for options in self._options.values():
            columns = max(columns, options.column + options.columnspan)
            rows = max(rows, options.row + options.rowspan)
        for index in self._columns:
            columns = max(columns, index + 1)
        for index in self._rows:
            rows = max(rows, index + 1)
        return columns, rows

    # -------------------------------------------------------------- sizing

    def requested(self, container: object = None) -> Size:  # noqa: ARG002
        """Room the grid needs at its children's natural sizes."""
        column_count, row_count = self.size()
        _, width = _resolve(column_count, self._columns, self._children(across=True))
        _, height = _resolve(row_count, self._rows, self._children(across=False))
        return Size(width, height)

    def _children(self, *, across: bool) -> list[tuple[int, int, int]]:
        """Each child's first line, span and the cells it needs, one way."""
        found = []
        for key, options in self._options.items():
            demand = options.demand(self._requested_of(self._widgets[key]))
            if across:
                found.append((options.column, options.columnspan, demand.width))
            else:
                found.append((options.row, options.rowspan, demand.height))
        return found

    def _lines(self, area: Rect) -> tuple[_Axis, _Axis, int, int]:
        """The columns and rows fitted to ``area``, and where the grid starts.

        Tk's ``ArrangeGrid``: resolve, adjust to the room there is, then put
        what was used where the grid's anchor says.
        """
        column_count, row_count = self.size()
        column_ends, _ = _resolve(
            column_count, self._columns, self._children(across=True)
        )
        row_ends, _ = _resolve(row_count, self._rows, self._children(across=False))
        used_x = _adjust(area.width, column_ends, self._columns)
        used_y = _adjust(area.height, row_ends, self._rows)
        x, y = self._origin(area, used_x, used_y)
        return _Axis(_sizes(column_ends)), _Axis(_sizes(row_ends)), x, y

    # ------------------------------------------------------------- placing

    def apply(self, container: object, area: Rect) -> None:  # noqa: ARG002
        """Size the lines to ``area`` and put each child in its cell."""
        columns, rows, origin_x, origin_y = self._lines(area)
        for key, options in self._options.items():
            widget = self._widgets[key]
            cell = Rect(
                origin_x + columns.offset(options.column),
                origin_y + rows.offset(options.row),
                columns.extent(options.column, options.columnspan),
                rows.extent(options.row, options.rowspan),
            )
            self._place(widget, cell, options)

    def _origin(self, area: Rect, used_x: int, used_y: int) -> tuple[int, int]:
        """Where the grid itself sits, by its anchor: Tk's ``TkComputeAnchor``.

        Centred, a grid bigger than its container is cut on both sides, as
        Tk cuts it, rather than only on the right.
        """
        sides = parse_sticky(self.anchor) if self.anchor != "center" else frozenset()
        if "w" in sides:
            x = area.x
        elif "e" in sides:
            x = area.x + area.width - used_x
        else:
            x = area.x + _c_div(area.width - used_x, 2)
        if "n" in sides:
            y = area.y
        elif "s" in sides:
            y = area.y + area.height - used_y
        else:
            y = area.y + _c_div(area.height - used_y, 2)
        return x, y

    def _place(self, widget: Managed, cell: Rect, options: GridOptions) -> None:
        """Put one child in its cell, honouring sticky."""
        inner = Rect(
            cell.x + options.padx.before,
            cell.y + options.pady.before,
            max(0, cell.width - options.padx.total),
            max(0, cell.height - options.pady.total),
        )
        sides = parse_sticky(options.sticky)
        requested = self._requested_of(widget)
        width = min(inner.width, requested.width + 2 * options.ipadx)
        height = min(inner.height, requested.height + 2 * options.ipady)
        if "e" in sides and "w" in sides:
            width = inner.width
        if "n" in sides and "s" in sides:
            height = inner.height

        if "w" in sides:
            x = inner.x
        elif "e" in sides:
            x = inner.x + inner.width - width
        else:
            x = inner.x + (inner.width - width) // 2
        if "n" in sides:
            y = inner.y
        elif "s" in sides:
            y = inner.y + inner.height - height
        else:
            y = inner.y + (inner.height - height) // 2
        self._assign(widget, Rect(x, y, width, height))

    def bbox(
        self, area: Rect, column: int, row: int, column2: int, row2: int
    ) -> tuple[int, int, int, int]:
        """The region a range of cells covers, as ``(x, y, width, height)``."""
        columns, rows, origin_x, origin_y = self._lines(area)
        return (
            origin_x + columns.offset(column),
            origin_y + rows.offset(row),
            columns.extent(column, column2 - column + 1),
            rows.extent(row, row2 - row + 1),
        )

    def location(self, area: Rect, x: int, y: int) -> tuple[int, int]:
        """The cell containing a screen position, or ``(-1, -1)`` outside it."""
        columns, rows, origin_x, origin_y = self._lines(area)
        return (
            self._line_at(columns.sizes, x - origin_x),
            self._line_at(rows.sizes, y - origin_y),
        )

    @staticmethod
    def _line_at(sizes: Sequence[int], offset: int) -> int:
        """Index of the line covering ``offset``, or -1 if it falls outside."""
        if offset < 0:
            return -1
        running = 0
        for index, size in enumerate(sizes):
            running += size
            if offset < running:
                return index
        return -1

    @staticmethod
    def _requested_of(widget: Managed) -> Size:
        """The size a child asked for."""
        return Size(widget.winfo_reqwidth(), widget.winfo_reqheight())

    @staticmethod
    def _assign(widget: Managed, rect: Rect) -> None:
        """Give a child its region, in coordinates relative to its master."""
        master = widget.master
        origin_x = master.winfo_rootx() if master is not None else 0
        origin_y = master.winfo_rooty() if master is not None else 0
        widget._allocate(
            Rect(rect.x - origin_x, rect.y - origin_y, rect.width, rect.height)
        )
