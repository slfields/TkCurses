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
from typing import TYPE_CHECKING, Any

from tkcurses._core.geometry import Rect, Size

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["SASH_WIDTH", "PaneOptions", "PanedLayout", "distribute", "place_sash"]

#: Cells a sash occupies between two panes. One, because a terminal has no
#: half cells to spare on furniture and a single line reads as a divider.
SASH_WIDTH = 1


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


def distribute(
    wanted: Sequence[int], minimums: Sequence[int], available: int
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
        return _grow(sizes, difference)
    return _shrink(sizes, minimums, -difference)


def _grow(sizes: list[int], surplus: int) -> list[int]:
    """Hand out extra cells one at a time, round-robin from the first pane."""
    grown = list(sizes)
    index = 0
    while surplus > 0:
        grown[index % len(grown)] += 1
        index += 1
        surplus -= 1
    return grown


def _shrink(sizes: list[int], minimums: Sequence[int], deficit: int) -> list[int]:
    """Take cells back from whichever panes still have room to give.

    A pane at its minimum is passed over. When every pane is at its minimum
    the panes simply do not fit, and the sizes come back as they are - the
    container will clip them, which is the only honest answer.
    """
    shrunk = list(sizes)
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
        self._order: list[Any] = []
        self._options: dict[int, PaneOptions] = {}
        #: Sizes as they currently are, remembered across relayouts so that a
        #: sash a person dragged stays where they put it.
        self._sizes: list[int] = []

    @property
    def vertical(self) -> bool:
        """True if the panes are stacked rather than side by side."""
        return self.orient != "horizontal"

    # ----------------------------------------------------------- membership

    def add(self, widget: Any, options: PaneOptions) -> None:
        """Add a pane, or change one already there."""
        if widget not in self._order:
            self._order.append(widget)
            self._sizes = []
        self._options[id(widget)] = options

    def insert(self, index: int, widget: Any, options: PaneOptions) -> None:
        """Add a pane at a position rather than at the end."""
        if widget in self._order:
            self._order.remove(widget)
        self._order.insert(max(0, min(index, len(self._order))), widget)
        self._options[id(widget)] = options
        self._sizes = []

    def remove(self, widget: Any) -> None:
        """Take a pane out."""
        if widget in self._order:
            self._order.remove(widget)
        self._options.pop(id(widget), None)
        self._sizes = []

    def options_for(self, widget: Any) -> PaneOptions | None:
        """One pane's options, or None if it is not in this window."""
        return self._options.get(id(widget))

    def slaves(self, container: Any = None) -> list[Any]:  # noqa: ARG002
        """The panes, in order."""
        return list(self._order)

    # -------------------------------------------------------------- geometry

    def requested(self, container: Any = None) -> Size:  # noqa: ARG002
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

    def _wanted(self, widget: Any, options: PaneOptions) -> int:
        """How long one pane wants to be, along the window's direction."""
        if options.size is not None:
            return max(options.size, options.minsize)
        if self.vertical:
            natural = int(widget.winfo_reqheight())
        else:
            natural = int(widget.winfo_reqwidth())
        return max(natural, options.minsize)

    def _across_of(self, widget: Any) -> int:
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
        self._sizes = distribute(wanted, minimums, available)
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

    def apply(self, container: Any, area: Rect) -> None:
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
    def _assign(widget: Any, rect: Rect) -> None:
        """Give a pane its region, in coordinates relative to its master."""
        master = widget.master
        origin_x = master.winfo_rootx() if master is not None else 0
        origin_y = master.winfo_rooty() if master is not None else 0
        widget._allocate(
            Rect(rect.x - origin_x, rect.y - origin_y, rect.width, rect.height)
        )
