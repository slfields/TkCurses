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

"""The grid geometry manager.

Grid lays children out in rows and columns. Unlike pack, where each child
carves a slice off what is left, every child names the cell it wants and the
manager works out how wide each column and how tall each row has to be.

The sizing happens in three steps, per axis. Each line takes the size its
own children need. A child spanning several lines then has any shortfall
spread across them, since a widget two columns wide constrains the pair
rather than either one. Finally, space the container has left over is shared
among the lines by *weight* - and a line with no weight does not grow at all,
which is the rule most often missed: ``sticky`` decides how a child sits in
its cell, and only ``weight`` makes the cell itself bigger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tkcurses._core.geometry import Rect, Size

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
        padx: Cells of space either side of the child, inside its cell.
        pady: Cells above and below.
        ipadx: Cells added to the child's own width.
        ipady: Cells added to the child's own height.
    """

    row: int = 0
    column: int = 0
    rowspan: int = 1
    columnspan: int = 1
    sticky: str = ""
    padx: int = 0
    pady: int = 0
    ipadx: int = 0
    ipady: int = 0

    def demand(self, requested: Size) -> Size:
        """Room this child needs in its cell, padding included."""
        return Size(
            requested.width + 2 * self.ipadx + 2 * self.padx,
            requested.height + 2 * self.ipady + 2 * self.pady,
        )


@dataclass
class LineConfig:
    """How one row or column behaves.

    Attributes:
        weight: Share of leftover space this line claims. Zero - the default -
            means the line never grows beyond what its children need.
        minsize: Smallest the line may be, in cells.
        pad: Cells added to the line beyond its children's needs.
        uniform: Lines sharing a name are kept in proportion to their weights.
    """

    weight: int = 0
    minsize: int = 0
    pad: int = 0
    uniform: str = ""


@dataclass
class _Axis:
    """One direction's worth of line sizes, being worked out."""

    sizes: list[int] = field(default_factory=list)
    configs: dict[int, LineConfig] = field(default_factory=dict)

    def config(self, index: int) -> LineConfig:
        """The configuration for one line, defaulted if never set."""
        return self.configs.get(index, LineConfig())

    def total(self) -> int:
        """Cells the lines take altogether."""
        return sum(self.sizes)

    def offset(self, index: int) -> int:
        """Where a line starts, relative to the grid's origin."""
        return sum(self.sizes[:index])

    def extent(self, start: int, span: int) -> int:
        """Cells covered by ``span`` lines from ``start``."""
        return sum(self.sizes[start : start + span])


class GridLayout:
    """Grids one container's children."""

    #: Gridded children decide how much room their container needs.
    propagates = True

    def __init__(self) -> None:
        self._options: dict[int, GridOptions] = {}
        self._widgets: dict[int, Any] = {}
        self._hidden: dict[int, GridOptions] = {}
        self._rows: dict[int, LineConfig] = {}
        self._columns: dict[int, LineConfig] = {}
        self.anchor = "nw"

    # ----------------------------------------------------------- membership

    def add(self, widget: Any, options: GridOptions) -> None:
        """Place ``widget`` in the grid, or move it."""
        self._options[id(widget)] = options
        self._widgets[id(widget)] = widget
        self._hidden.pop(id(widget), None)

    def remove(self, widget: Any, *, keep: bool = False) -> None:
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

    def remembered(self, widget: Any) -> GridOptions | None:
        """Options kept by a previous ``grid_remove``, if any."""
        return self._hidden.get(id(widget))

    def options_for(self, widget: Any) -> GridOptions | None:
        """Where ``widget`` sits, or None if it is not gridded."""
        return self._options.get(id(widget))

    def slaves(
        self,
        container: Any = None,  # noqa: ARG002 - Layout protocol
        *,
        row: int | None = None,
        column: int | None = None,
    ) -> list[Any]:
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

    def requested(self, container: Any = None) -> Size:  # noqa: ARG002
        """Room the grid needs at its children's natural sizes."""
        columns, rows = self._natural()
        return Size(columns.total(), rows.total())

    def _natural(self) -> tuple[_Axis, _Axis]:
        """Line sizes before any leftover space is shared out."""
        column_count, row_count = self.size()
        columns = _Axis([0] * column_count, dict(self._columns))
        rows = _Axis([0] * row_count, dict(self._rows))

        for key, options in self._options.items():
            demand = options.demand(self._requested_of(self._widgets[key]))
            if options.columnspan == 1:
                columns.sizes[options.column] = max(
                    columns.sizes[options.column], demand.width
                )
            if options.rowspan == 1:
                rows.sizes[options.row] = max(rows.sizes[options.row], demand.height)

        # A child covering several lines constrains them together rather than
        # any one of them, so only its shortfall is spread.
        for key, options in self._options.items():
            demand = options.demand(self._requested_of(self._widgets[key]))
            if options.columnspan > 1:
                self._spread(columns, options.column, options.columnspan, demand.width)
            if options.rowspan > 1:
                self._spread(rows, options.row, options.rowspan, demand.height)

        for axis in (columns, rows):
            for index, size in enumerate(axis.sizes):
                config = axis.config(index)
                axis.sizes[index] = max(size, config.minsize) + config.pad
        return columns, rows

    @staticmethod
    def _spread(axis: _Axis, start: int, span: int, needed: int) -> None:
        """Give the lines under a spanning child enough room between them."""
        have = axis.extent(start, span)
        shortfall = needed - have
        if shortfall <= 0:
            return
        each, remainder = divmod(shortfall, span)
        for offset in range(span):
            axis.sizes[start + offset] += each + (1 if offset < remainder else 0)

    def _share(self, axis: _Axis, room: int) -> None:
        """Give the lines the container's leftover space, by weight.

        A line with no weight is left alone: this is the rule that catches
        people out, because a cell that will not grow makes ``sticky`` look
        broken when it is doing exactly what it was told.
        """
        leftover = room - axis.total()
        if leftover <= 0:
            return
        self._apply_uniform(axis)
        weights = [axis.config(index).weight for index in range(len(axis.sizes))]
        total = sum(weights)
        if total <= 0:
            return
        given = 0
        claimants = [index for index, weight in enumerate(weights) if weight > 0]
        for index in claimants[:-1]:
            share = leftover * weights[index] // total
            axis.sizes[index] += share
            given += share
        axis.sizes[claimants[-1]] += leftover - given

    def _apply_uniform(self, axis: _Axis) -> None:
        """Hold the lines of each uniform group in proportion to their weights.

        Tk's rule: within a group, every line ends up at least as big as the
        largest size-per-weight in the group demands.
        """
        groups: dict[str, list[int]] = {}
        for index in range(len(axis.sizes)):
            config = axis.config(index)
            if config.uniform and config.weight > 0:
                groups.setdefault(config.uniform, []).append(index)
        for members in groups.values():
            unit = max(
                (axis.sizes[index] + axis.config(index).weight - 1)
                // axis.config(index).weight
                for index in members
            )
            for index in members:
                axis.sizes[index] = unit * axis.config(index).weight

    # ------------------------------------------------------------- placing

    def apply(self, container: Any, area: Rect) -> None:  # noqa: ARG002
        """Size the lines to ``area`` and put each child in its cell."""
        columns, rows = self._natural()
        self._share(columns, area.width)
        self._share(rows, area.height)
        origin_x, origin_y = self._origin(area, columns, rows)

        for key, options in self._options.items():
            widget = self._widgets[key]
            cell = Rect(
                origin_x + columns.offset(options.column),
                origin_y + rows.offset(options.row),
                columns.extent(options.column, options.columnspan),
                rows.extent(options.row, options.rowspan),
            )
            self._place(widget, cell, options)

    def _origin(self, area: Rect, columns: _Axis, rows: _Axis) -> tuple[int, int]:
        """Where the grid itself sits when it is smaller than the container."""
        spare_x = max(0, area.width - columns.total())
        spare_y = max(0, area.height - rows.total())
        sides = parse_sticky(self.anchor) if self.anchor != "center" else frozenset()
        if self.anchor == "center":
            return area.x + spare_x // 2, area.y + spare_y // 2
        x = (
            area.x
            if "w" in sides
            else (area.x + spare_x if "e" in sides else area.x + spare_x // 2)
        )
        y = (
            area.y
            if "n" in sides
            else (area.y + spare_y if "s" in sides else area.y + spare_y // 2)
        )
        return x, y

    def _place(self, widget: Any, cell: Rect, options: GridOptions) -> None:
        """Put one child in its cell, honouring sticky."""
        inner = Rect(
            cell.x + options.padx,
            cell.y + options.pady,
            max(0, cell.width - 2 * options.padx),
            max(0, cell.height - 2 * options.pady),
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
        columns, rows = self._natural()
        self._share(columns, area.width)
        self._share(rows, area.height)
        origin_x, origin_y = self._origin(area, columns, rows)
        return (
            origin_x + columns.offset(column),
            origin_y + rows.offset(row),
            columns.extent(column, column2 - column + 1),
            rows.extent(row, row2 - row + 1),
        )

    def location(self, area: Rect, x: int, y: int) -> tuple[int, int]:
        """The cell containing a screen position, or ``(-1, -1)`` outside it."""
        columns, rows = self._natural()
        self._share(columns, area.width)
        self._share(rows, area.height)
        origin_x, origin_y = self._origin(area, columns, rows)
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
    def _requested_of(widget: Any) -> Size:
        """The size a child asked for."""
        return Size(widget.winfo_reqwidth(), widget.winfo_reqheight())

    @staticmethod
    def _assign(widget: Any, rect: Rect) -> None:
        """Give a child its region, in coordinates relative to its master."""
        master = widget.master
        origin_x = master.winfo_rootx() if master is not None else 0
        origin_y = master.winfo_rooty() if master is not None else 0
        widget._allocate(
            Rect(rect.x - origin_x, rect.y - origin_y, rect.width, rect.height)
        )
