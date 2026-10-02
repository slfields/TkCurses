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

"""Panes divided by sashes, and where the divisions fall.

A PanedWindow is a container that is also a geometry manager: it lays its
children out in a row or a column, separated by sashes a person can drag.
That makes it the fourth manager in the library, alongside pack, grid and
place - the difference being that its arrangement is *stateful*. Pack works
out where everything goes from the options every time; a paned window
remembers where the sashes were put, because a person put them there and a
relayout must not undo it.

Everything here is arithmetic on cells, so the cases that are awkward to do
by hand can be exercised directly: a pane dragged past its neighbour, a
window too small for its own panes, a sash moved and then the whole thing
resized underneath it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from tkcurses._core.geometry import Managed, Rect, Size

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["SASH_WIDTH", "PaneOptions", "PanedLayout", "distribute", "place_sash"]

#: Cells a sash occupies between two panes. One, because a terminal has no
#: half cells to spare on furniture and a single line reads as a divider.
SASH_WIDTH = 1


class Pane(Managed, Protocol):
    """A pane: a managed widget that the paned window also operates.

    Wider than :class:`~tkcurses._core.geometry.Managed`, and the difference is
    the point. The LAYOUT needs only the four members any geometry manager
    needs; the WIDGET that owns the layout maps its panes and reports them by
    path. Measured from what PanedWindow uses on what ``slaves()`` hands back:
    ``_w`` for ``panes()``, which answers paths as Tk does, and ``_map`` when a
    pane is first shown.

    Typing ``slaves()`` as returning plain ``Managed`` made both of those an
    error, and the checker was right - the layout was promising less than its
    own caller relies on. TkCurses-d40.
    """

    _w: str

    def _map(self) -> None:
        """Show the pane, once there is somewhere to show it."""
        ...


@dataclass
class PaneOptions:
    """How one pane behaves.

    Attributes:
        minsize: Cells this pane may never be squeezed below.
        sticky: Which edges its child is held against within its pane.
        size: The size the pane was asked for, or None to take its child's.
    """

    minsize: int = 0
    sticky: str = "nsew"
    size: int | None = None
    #: How this pane shares surplus and shortfall, or None to share it evenly
    #: with every other pane. ttk's ``-weight``; the classic widget has no such
    #: option and leaves it None, which is what keeps its documented
    #: spread-across-everything behaviour. See :func:`distribute`.
    weight: int | None = None


def distribute(
    wanted: Sequence[int],
    minimums: Sequence[int],
    available: int,
    weights: Sequence[int | None] | None = None,
) -> list[int]:
    """Fit panes into the room there is, as fairly as the minimums allow.

    Args:
        wanted: What each pane would like, in cells.
        minimums: What each pane may not go below.
        available: Cells to divide, sashes already taken out.

    Returns:
        One size per pane, summing to ``available`` whenever that is possible
        without breaking a minimum.

    Surplus and shortfall are both spread across the panes rather than given
    to one of them, so growing a window widens every pane a little instead of
    stretching the last one - which is what a person expects and what Tk's
    own ``-stretch middle`` default does.
    """
    if not wanted:
        return []
    sizes = [max(size, floor) for size, floor in zip(wanted, minimums, strict=True)]
    difference = available - sum(sizes)
    if difference == 0:
        return sizes
    if difference > 0:
        return _grow(sizes, difference, weights)
    return _shrink(sizes, minimums, -difference, weights)


def _shares(weights: Sequence[int | None] | None, count: int) -> list[int] | None:
    """Which panes take a share of a change, and how big a share each takes.

    None when no pane named a weight, which means share it out evenly - the
    classic widget's documented behaviour. Otherwise one number per pane, and
    panes with nothing are passed over.

    **All weights zero is not "nobody moves".** Measured on real ttk 9.0, a
    horizontal panedwindow grown by 100 pixels:

        weights [1, 3]     each pane grew by [25, 75]
        weights [2, 1, 1]                    [50, 25, 25]
        weights [0, 1]                       [0, 100]
        weights [0, 0]                       [0, 100]
        weights [0, 0, 0]                    [0, 0, 100]

    so when every weight is zero the LAST pane absorbs the lot. That is ttk's
    default state, and the issue that asked for this predicted the panes would
    keep their sizes instead.
    """
    if weights is None or all(weight is None for weight in weights):
        return None
    shares = [0 if weight is None else max(0, weight) for weight in weights]
    if any(shares):
        return shares
    last = [0] * count
    last[-1] = 1
    return last


def _spread(change: int, shares: list[int] | None, count: int) -> list[int]:
    """How much of ``change`` each pane takes, as whole cells.

    Largest remainder, so the cells add up to the change exactly rather than
    drifting by one or two: every pane takes its floor, and what is left goes
    to the panes with the biggest fractions.
    """
    if shares is None:
        base, extra = divmod(change, count)
        return [base + (1 if index < extra else 0) for index in range(count)]
    total = sum(shares)
    exact = [change * share / total for share in shares]
    taken = [int(amount) for amount in exact]
    leftover = change - sum(taken)
    order = sorted(
        range(count), key=lambda index: exact[index] - taken[index], reverse=True
    )
    for index in order[:leftover]:
        taken[index] += 1
    return taken


def _grow(
    sizes: list[int], surplus: int, weights: Sequence[int | None] | None = None
) -> list[int]:
    """Hand out extra cells, by weight when any pane named one.

    Without weights the cells go round-robin from the first pane, which is the
    classic widget's documented behaviour: surplus spread across the panes
    rather than given to one of them.
    """
    shares = _shares(weights, len(sizes))
    return [
        size + part
        for size, part in zip(sizes, _spread(surplus, shares, len(sizes)), strict=True)
    ]


def _shrink(
    sizes: list[int],
    minimums: Sequence[int],
    deficit: int,
    weights: Sequence[int | None] | None = None,
) -> list[int]:
    """Take cells back from whichever panes still have room to give.

    A pane at its minimum is passed over. When every pane is at its minimum
    the panes simply do not fit, and the sizes come back as they are - the
    container will clip them, which is the only honest answer.
    """
    shrunk = list(sizes)
    shares = _shares(weights, len(sizes))
    if shares is not None:
        # Shortfall follows the weights too - measured, [1, 3] shrinking by 100
        # gives up [25, 75] - but never below a minimum, so whatever a pane
        # cannot give up is taken from the rest by the loop below.
        for index, part in enumerate(_spread(deficit, shares, len(sizes))):
            room = shrunk[index] - max(1, minimums[index])
            given = max(0, min(part, room))
            shrunk[index] -= given
            deficit -= given
    while deficit > 0:
        movable = [
            index for index, size in enumerate(shrunk) if size > max(1, minimums[index])
        ]
        if not movable:
            return shrunk
        for index in movable:
            if deficit == 0:
                break
            shrunk[index] -= 1
            deficit -= 1
    return shrunk


def place_sash(
    sizes: Sequence[int], sash: int, position: int, minimums: Sequence[int]
) -> list[int]:
    """Move one sash, taking the cells from one side and giving them to the other.

    Args:
        sizes: Current pane sizes.
        sash: Which sash, counting from 0 between panes 0 and 1.
        position: Where the sash should now start, measured from the first
            pane's edge.
        minimums: The floor for each pane.

    Returns:
        New sizes. The total never changes: a sash moves the boundary between
        two panes and takes nothing from the rest, which is what stops a drag
        rippling through the whole window.
    """
    sizes = list(sizes)
    if not 0 <= sash < len(sizes) - 1:
        return sizes
    before = sum(sizes[:sash]) + sash * SASH_WIDTH
    pair = sizes[sash] + sizes[sash + 1]
    wanted = position - before
    low = max(1, minimums[sash])
    high = pair - max(1, minimums[sash + 1])
    sizes[sash] = min(max(wanted, low), max(low, high))
    sizes[sash + 1] = pair - sizes[sash]
    return sizes


class PanedLayout:
    """Lays a paned window's children out in a row or a column."""

    #: The panes decide how big the window wants to be.
    propagates = True

    def __init__(self, orient: str = "horizontal") -> None:
        self.orient = orient
        self._order: list[Pane] = []
        self._options: dict[int, PaneOptions] = {}
        #: Sizes as they currently are, remembered across relayouts so that a
        #: sash a person dragged stays where they put it.
        self._sizes: list[int] = []

    @property
    def vertical(self) -> bool:
        """True if the panes are stacked rather than side by side."""
        return self.orient != "horizontal"

    # ----------------------------------------------------------- membership

    def add(self, widget: Pane, options: PaneOptions) -> None:
        """Add a pane, or change one already there."""
        if widget not in self._order:
            self._order.append(widget)
            self._sizes = []
        self._options[id(widget)] = options

    def insert(self, index: int, widget: Pane, options: PaneOptions) -> None:
        """Add a pane at a position rather than at the end."""
        if widget in self._order:
            self._order.remove(widget)
        self._order.insert(max(0, min(index, len(self._order))), widget)
        self._options[id(widget)] = options
        self._sizes = []

    def remove(self, widget: Pane) -> None:
        """Take a pane out."""
        if widget in self._order:
            self._order.remove(widget)
        self._options.pop(id(widget), None)
        self._sizes = []

    def options_for(self, widget: Pane) -> PaneOptions | None:
        """One pane's options, or None if it is not in this window."""
        return self._options.get(id(widget))

    def slaves(self, container: Pane | None = None) -> list[Pane]:  # noqa: ARG002
        """The panes, in order."""
        return list(self._order)

    # -------------------------------------------------------------- geometry

    def requested(self, container: Pane | None = None) -> Size:  # noqa: ARG002
        """What the panes together need, sashes included."""
        if not self._order:
            return Size(0, 0)
        along = 0
        across = 0
        for widget in self._order:
            options = self._options[id(widget)]
            wanted = self._wanted(widget, options)
            along += wanted
            across = max(across, self._across_of(widget))
        along += SASH_WIDTH * (len(self._order) - 1)
        return Size(across, along) if self.vertical else Size(along, across)

    def _wanted(self, widget: Pane, options: PaneOptions) -> int:
        """How long one pane wants to be, along the window's direction."""
        if options.size is not None:
            return max(options.size, options.minsize)
        if self.vertical:
            natural = int(widget.winfo_reqheight())
        else:
            natural = int(widget.winfo_reqwidth())
        return max(natural, options.minsize)

    def _across_of(self, widget: Pane) -> int:
        """How wide one pane wants to be, across the window's direction."""
        return int(
            widget.winfo_reqwidth() if self.vertical else widget.winfo_reqheight()
        )

    def sizes(self, area: Rect) -> list[int]:
        """The pane sizes for an area, keeping any a sash has already set."""
        if not self._order:
            return []
        available = max(
            0,
            (area.height if self.vertical else area.width)
            - SASH_WIDTH * (len(self._order) - 1),
        )
        minimums = [self._options[id(w)].minsize for w in self._order]
        if len(self._sizes) == len(self._order):
            wanted = self._sizes
        else:
            wanted = [
                self._wanted(widget, self._options[id(widget)])
                for widget in self._order
            ]
        weights = [self._options[id(w)].weight for w in self._order]
        self._sizes = distribute(wanted, minimums, available, weights)
        return list(self._sizes)

    def move_sash(self, sash: int, position: int, area: Rect) -> None:
        """Put one sash at a position, in cells from the window's edge."""
        sizes = self.sizes(area)
        minimums = [self._options[id(w)].minsize for w in self._order]
        self._sizes = place_sash(sizes, sash, position, minimums)

    def sash_position(self, sash: int) -> int:
        """Where one sash starts, in cells from the window's edge."""
        if not 0 <= sash < len(self._sizes) - 1:
            return 0
        return sum(self._sizes[: sash + 1]) + sash * SASH_WIDTH

    def apply(self, container: Managed, area: Rect) -> None:
        """Give each pane its strip of the window, then redraw the sashes.

        The container is repainted here rather than left to the engine
        because the sashes are drawn from these sizes, and until this runs
        there are none: the window is painted when it is allocated, which is
        before its own manager has worked anything out. Without this the
        sashes were drawn at position zero, underneath the first pane.
        """
        sizes = self.sizes(area)
        offset = 0
        for widget, size in zip(self._order, sizes, strict=True):
            if self.vertical:
                rect = Rect(area.x, area.y + offset, area.width, size)
            else:
                rect = Rect(area.x + offset, area.y, size, area.height)
            self._assign(widget, rect)
            offset += size + SASH_WIDTH
        redraw = getattr(container, "_redraw", None)
        if callable(redraw):
            redraw()

    @staticmethod
    def _assign(widget: Pane, rect: Rect) -> None:
        """Give a pane its region, in coordinates relative to its master."""
        master = widget.master
        origin_x = master.winfo_rootx() if master is not None else 0
        origin_y = master.winfo_rooty() if master is not None else 0
        widget._allocate(
            Rect(rect.x - origin_x, rect.y - origin_y, rect.width, rect.height)
        )
