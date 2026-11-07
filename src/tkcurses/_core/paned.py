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

__all__ = [
    "SASH_WIDTH",
    "STRETCH_VALUES",
    "PaneOptions",
    "PanedLayout",
    "distribute",
    "place_sash",
]

#: Cells a sash occupies between two panes. One, because a terminal has no
#: half cells to spare on furniture and a single line reads as a divider.
SASH_WIDTH = 1

#: What a classic pane's ``stretch`` may be, in the order Tk lists them.
STRETCH_VALUES = ("always", "first", "last", "middle", "never")


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
    #: How this pane shares surplus and shortfall: ttk's ``-weight``, which
    #: :func:`distribute` follows. The classic widget has no such option and
    #: leaves it None, and its panes are laid out by ``stretch`` instead.
    weight: int | None = None
    #: Which room a classic pane takes beyond its size: Tk's ``-stretch``.
    stretch: str = "last"


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

    The themed panedwindow's arithmetic: surplus and shortfall follow the
    panes' weights (see :func:`_shares`). A classic PanedWindow's panes are
    laid out by :func:`arrange` instead, which follows Tk's.
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

    Without weights the cells go round-robin from the first pane.
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
    sizes: Sequence[int],
    sash: int,
    position: int,
    minimums: Sequence[int],
    gap: int = SASH_WIDTH,
) -> list[int]:
    """Move one sash, taking the cells from one side and giving them to the other.

    Args:
        sizes: Current pane sizes.
        sash: Which sash, counting from 0 between panes 0 and 1.
        position: Where the sash should now start, measured from the first
            pane's edge.
        minimums: The floor for each pane.
        gap: Cells each sash takes, its padding included.

    Returns:
        New sizes. The total never changes: a sash moves the boundary between
        two panes and takes nothing from the rest, which is what stops a drag
        rippling through the whole window.
    """
    sizes = list(sizes)
    if not 0 <= sash < len(sizes) - 1:
        return sizes
    before = sum(sizes[:sash]) + sash * gap
    pair = sizes[sash] + sizes[sash + 1]
    wanted = position - before
    low = max(1, minimums[sash])
    high = pair - max(1, minimums[sash + 1])
    sizes[sash] = min(max(wanted, low), max(low, high))
    sizes[sash + 1] = pair - sizes[sash]
    return sizes


def _stretchable(stretch: str, index: int, first: int, last: int) -> bool:
    """Whether a pane takes a share of spare room: Tk's ``IsStretchable``."""
    return (
        stretch == "always"
        or (stretch == "first" and index == first)
        or (stretch == "last" and index == last)
        or (stretch == "middle" and index not in (first, last))
    )


def arrange(
    bases: Sequence[int],
    minimums: Sequence[int],
    stretches: Sequence[str],
    length: int,
    gap: int = SASH_WIDTH,
) -> list[int]:
    """Each classic pane's size in ``length`` cells: Tk's ``ArrangePanes``.

    Step for step from ``generic/tkPanedWindow.c``, as are
    :func:`move_sash` (``MoveSash``) and the layout's requested size
    (``ComputeGeometry``).

    Args:
        bases: Each pane's own size - its ``width`` (or ``height``) if it
            was given one, otherwise the size it had when it was added.
        minimums: Each pane's ``minsize``.
        stretches: Each pane's ``stretch``.
        length: The cells the paned window has along its direction.
        gap: Cells each sash takes, its padding included.

    The spare room - or the shortfall - goes to the panes ``stretch``
    allows, in proportion to their sizes, any left over to the last of
    them; with none stretchable, a shortfall comes out of the others as
    late as it can. Measured on Tk 9.0.2 with ``-stretch`` at its
    default, ``last``: two panes of 50 and 50 with minsizes 120 and 200 in
    600 pixels are 120 and 475, and growing the window gives the whole
    growth to the last. A pane cut off by the edge has a size of zero or
    less, and is not shown. Recomputed every time from ``bases``: what a
    person did with a sash is kept by setting the pane's ``width``, as
    :func:`move_sash` does, not by remembering sizes.
    """
    count = len(bases)
    if count == 0:
        return []
    first, last = 0, count - 1
    reserve = length - sum(bases) - gap * (count - 1)
    dynamic = dynamic_minimum = 0
    for index in range(count):
        if _stretchable(stretches[index], index, first, last):
            dynamic += bases[index]
            dynamic_minimum += minimums[index]
    sizes = []
    position = 0
    sashes = count - 1
    for index in range(count):
        size, floor = bases[index], minimums[index]
        if _stretchable(stretches[index], index, first, last):
            share = size / dynamic if dynamic > 0 else size / length if length else 0
            dynamic -= size
            dynamic_minimum -= floor
            amount = int(share * reserve)
            if size + amount >= floor:
                reserve -= amount
                size += amount
            else:
                reserve += size - floor
                size = floor
            if index == last and reserve > 0:
                size += reserve
                reserve = 0
        elif dynamic - dynamic_minimum + reserve < 0:
            if size + dynamic - dynamic_minimum + reserve <= floor:
                reserve += size - floor
                size = floor
            else:
                size += dynamic - dynamic_minimum + reserve
                reserve = dynamic_minimum - dynamic
        # Cut off where the window ends, room for the sashes still to come
        # kept back.
        size = min(size, length - gap * sashes - position)
        sizes.append(size)
        position = max(0, position + size) + gap
        sashes -= 1
    return sizes


def move_sash(
    sizes: Sequence[int], minimums: Sequence[int], sash: int, distance: int
) -> list[int]:
    """Move a classic sash ``distance`` cells: Tk's ``MoveSash``.

    The pane on the side it moves towards gives up room, and when that one
    is down to its ``minsize`` the next one beyond it does, and so on - a
    sash dragged far enough pushes the panes after it along, as Tk's does.
    Returns the new sizes, which the caller keeps as every pane's
    ``width``: Tk pins them all, so that the move survives the next
    layout.
    """
    sizes = list(sizes)
    if distance == 0 or not 0 <= sash < len(sizes) - 1:
        return sizes
    if distance > 0:
        grows, giving = sash, range(sash + 1, len(sizes))
    else:
        distance = -distance
        grows, giving = sash + 1, range(sash, -1, -1)
    spare = sum(sizes[index] - minimums[index] for index in giving)
    if spare <= 0:
        return sizes
    distance = min(distance, spare)
    sizes[grows] += distance
    for index in giving:
        room = sizes[index] - minimums[index]
        if distance > room:
            distance -= room
            sizes[index] = minimums[index]
        else:
            sizes[index] -= distance
            break
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
        #: Cells each sash takes between two panes: the sash, any handle
        #: wider than it, and ``sashpad`` either side. The window sets it.
        self.sash = SASH_WIDTH
        #: A classic pane's size when its ``width`` is not set: Tk's
        #: ``paneWidth``, the size it asked for when it was added. Taken
        #: again while the window has never been laid out, as Tk takes it
        #: again while the window is unmapped.
        self._natural: dict[int, int] = {}
        self._arranged = False

    @property
    def vertical(self) -> bool:
        """True if the panes are stacked rather than side by side."""
        return self.orient != "horizontal"

    # ----------------------------------------------------------- membership

    @property
    def classic(self) -> bool:
        """True for a classic PanedWindow's panes, laid out as Tk's are.

        The themed widget's panes carry a ``weight``, and share room by it.
        """
        return all(self._options[id(w)].weight is None for w in self._order)

    def add(self, widget: Pane, options: PaneOptions) -> None:
        """Add a pane, or change one already there."""
        if widget not in self._order:
            self._order.append(widget)
            self._sizes = []
            self._adopt(widget, options)
        self._options[id(widget)] = options

    def _adopt(self, widget: Pane, options: PaneOptions) -> None:
        """Start a new pane's remembered size: Tk's ``paneWidth`` on adding.

        Its ``width`` if it was added with one, otherwise left to be taken
        from what it asks for. A later ``paneconfigure`` of ``width`` does
        not touch it - measured, the window's requested size stays where it
        was - and only a sash moved changes it again.
        """
        self._natural.pop(id(widget), None)
        if options.size is not None and options.size > 0:
            self._natural[id(widget)] = options.size

    def insert(self, index: int, widget: Pane, options: PaneOptions) -> None:
        """Add a pane at a position rather than at the end."""
        if widget in self._order:
            self._order.remove(widget)
        else:
            self._adopt(widget, options)
        self._order.insert(max(0, min(index, len(self._order))), widget)
        self._options[id(widget)] = options
        self._sizes = []

    def remove(self, widget: Pane) -> None:
        """Take a pane out."""
        if widget in self._order:
            self._order.remove(widget)
        self._options.pop(id(widget), None)
        self._natural.pop(id(widget), None)
        self._sizes = []

    def options_for(self, widget: Pane) -> PaneOptions | None:
        """One pane's options, or None if it is not in this window."""
        return self._options.get(id(widget))

    def slaves(self, container: object = None) -> list[Pane]:  # noqa: ARG002
        """The panes, in order."""
        return list(self._order)

    # -------------------------------------------------------------- geometry

    def requested(self, container: object = None) -> Size:  # noqa: ARG002
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
        along += self.sash * (len(self._order) - 1)
        return Size(across, along) if self.vertical else Size(along, across)

    def _wanted(self, widget: Pane, options: PaneOptions) -> int:
        """How long one pane wants to be, along the window's direction.

        For a classic pane, Tk's ``ComputeGeometry``: its remembered size,
        raised to its ``minsize`` - and kept raised, as Tk keeps it.
        """
        if options.weight is None:
            wanted = max(self._natural_of(widget), options.minsize)
            self._natural[id(widget)] = wanted
            return wanted
        if options.size is not None:
            return max(options.size, options.minsize)
        if self.vertical:
            natural = int(widget.winfo_reqheight())
        else:
            natural = int(widget.winfo_reqwidth())
        return max(natural, options.minsize)

    def _natural_of(self, widget: Pane) -> int:
        """A classic pane's remembered size, taken now if it has none yet.

        Taken again from what the pane asks for until the window is first
        laid out, unless it was given a ``width``: Tk's
        ``PanedWindowReqProc`` does the same while the window is unmapped.
        """
        options = self._options[id(widget)]
        given = options.size is not None and options.size > 0
        if id(widget) in self._natural and (self._arranged or given):
            return self._natural[id(widget)]
        natural = int(
            widget.winfo_reqheight() if self.vertical else widget.winfo_reqwidth()
        )
        self._natural[id(widget)] = natural
        return natural

    def _base(self, widget: Pane) -> int:
        """A classic pane's size before stretching: ``ArrangePanes``' base."""
        options = self._options[id(widget)]
        if options.size is not None and options.size > 0:
            return options.size
        return max(self._natural_of(widget), options.minsize)

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
            - self.sash * (len(self._order) - 1),
        )
        if self.classic:
            self._sizes = arrange(
                [self._base(widget) for widget in self._order],
                [self._options[id(w)].minsize for w in self._order],
                [self._options[id(w)].stretch for w in self._order],
                area.height if self.vertical else area.width,
                self.sash,
            )
            self._arranged = True
            return list(self._sizes)
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
        minimums = [self._options[id(w)].minsize for w in self._order]
        if self.classic:
            # Tk's "sash place": the distance from where the sash is, then
            # MoveSash, which pins every pane's width to its new size.
            sizes = self._current()
            distance = position - self._sash_at(sizes, sash)
            if distance == 0 or not 0 <= sash < len(sizes) - 1:
                # Tk returns before pinning anything: measured, a sash
                # placed where it already is leaves every width unset.
                return
            sizes = move_sash(sizes, minimums, sash, distance)
            for widget, size in zip(self._order, sizes, strict=True):
                self._options[id(widget)].size = size
                self._natural[id(widget)] = size
            self._sizes = sizes
            return
        sizes = self.sizes(area)
        self._sizes = place_sash(sizes, sash, position, minimums, self.sash)

    def _current(self) -> list[int]:
        """The panes' sizes now: as last laid out, or as they ask before then.

        Before the first layout Tk's sashes sit where ``ComputeGeometry``
        put them, after each pane's own size - which is what lets a sash be
        placed before the window has any room.
        """
        if len(self._sizes) == len(self._order):
            return list(self._sizes)
        return [
            self._wanted(widget, self._options[id(widget)]) for widget in self._order
        ]

    def _sash_at(self, sizes: Sequence[int], sash: int) -> int:
        """Where a sash starts, given the pane sizes before it."""
        return sum(max(0, size) for size in sizes[: sash + 1]) + sash * self.sash

    def sash_position(self, sash: int) -> int:
        """Where one sash starts, in cells from the window's edge."""
        sizes = self._current() if self.classic else self._sizes
        if not 0 <= sash < len(sizes) - 1:
            return 0
        return self._sash_at(sizes, sash)

    def apply(self, container: object, area: Rect) -> None:
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
            # A pane the window's edge cut off entirely has no room at all.
            size = max(0, size)
            if self.vertical:
                rect = Rect(area.x, area.y + offset, area.width, size)
            else:
                rect = Rect(area.x + offset, area.y, size, area.height)
            self._assign(widget, rect)
            offset += size + self.sash
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
