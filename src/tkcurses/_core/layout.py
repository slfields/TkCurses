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

"""Geometry negotiation: who asks for what size, and who decides.

Layout in Tk is a conversation. A widget says how big it would like to be; its
geometry manager adds that up across siblings and asks the container for that
much; the container asks its own manager, and so on to the toplevel. Then the
sizes agreed on are handed back down and windows are moved.

Two things make that harder than it sounds, and both are what this module is
for.

The conversation can fail to end. A parent that resizes to fit its children
changes its own requested size, which asks its parent to recompute, which can
come back around. The previous attempt at this library looped here and
exhausted memory. :class:`LayoutEngine` is written so that cannot happen: the
walk upward stops as soon as a requested size does not change, a widget is
never visited twice in one pass, and the whole run is bounded - exceeding the
bound raises :class:`LayoutLoop` rather than continuing, because a diagnosable
error beats a machine that has to be power-cycled.

Recomputing eagerly is also wrong. Packing ten children one at a time would
lay the container out ten times. Work is queued and coalesced instead, and the
main loop runs it once before drawing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from tkcurses._core.geometry import Container, Managed, Rect, Size

__all__ = ["Layout", "LayoutEngine", "LayoutLoop"]

#: How many containers one run may lay out before it is treated as a loop.
#: Large enough that no real widget tree reaches it - a deep tree is a few
#: hundred containers - and small enough that hitting it costs milliseconds
#: rather than the machine.
DEFAULT_PASS_LIMIT = 10_000


class LayoutLoop(RuntimeError):
    """Layout did not settle.

    Raised instead of continuing, because the alternative is the failure that
    killed the previous implementation: a propagation cycle allocating until
    the process is killed. The message names the container being laid out when
    the limit was reached, which is where the cycle runs through.
    """


class Layout(Protocol):
    """What a geometry manager has to do to take part in negotiation.

    Pack, Grid, Place and Paned each implement this. The engine knows nothing
    else about them, which is what lets a container use one manager while its
    parent uses another.

    Three of the four methods say what they mean. ``remove`` still takes
    ``Any``, for a measured reason given below.

    **Why the first attempt at this failed, and what it was really about.**
    Narrowing the three ``container`` parameters to :class:`Container` cost
    **17 mypy errors**, ten of them "Statement is unreachable", and the count
    oscillated rather than converging (TkCurses-sup, reverted). The diagnosis in
    the issue was that something about protocol matching was subtly wrong. It
    was simpler and more embarrassing than that: ``pack``, ``grid`` and
    ``paned`` declared types for a parameter **they never read**. Seven of the
    eight implementation signatures carry ``# noqa: ARG002``. Those annotations
    were decorative, and because a parameter is contravariant, a decorative
    annotation on one is a hard constraint on the protocol.

    Widen the unused parameters to ``object`` - losing nothing, since no body
    touches them - and the same narrowing costs **nothing**:

    =========================================  ======
    narrowing                                  errors
    =========================================  ======
    ``apply``/``requested`` to ``Container``    17
    ... with the unused parameters widened     **0**
    ``slaves -> Sequence[Managed]``            **0**
    ``slaves -> list[Managed]``                 1
    ``remove(widget: Managed)``                 2
    ``requested(container: object)``            8
    =========================================  ======

    Two of those rows are worth keeping. ``list[Managed]`` fails where
    ``Sequence[Managed]`` succeeds because ``list`` is invariant and
    ``Sequence`` is covariant: :class:`~tkcurses._core.paned.PanedLayout`
    returns ``list[Pane]``, which is a ``Sequence[Managed]`` and is not a
    ``list[Managed]``. And **widening does not help**: ``object`` is the widest
    type there is and costs eight errors, because an implementation declaring
    ``Pane | None`` does not accept an arbitrary object. Contravariance bites in
    the direction nobody expects.

    ``remove`` keeps ``Any`` because narrowing it is a real change rather than a
    cosmetic one: ``PanedLayout`` keeps ``list[Pane]`` as its order, so
    ``remove(widget: Managed)`` makes ``self._order.remove(widget)`` an error.
    Fixing that means deciding whether a paned window's order should be typed
    in ``Pane`` at all, which is a design question and not an annotation.
    TkCurses-sup.
    """

    #: Whether this manager's children decide their container's size. True
    #: for pack and grid, which arrange a container's contents and therefore
    #: know how much room those contents need. False for place, whose
    #: children state where they go and make no claim on the container - a
    #: frame full of placed children keeps the size it was configured with.
    propagates: bool

    def requested(self, container: Container) -> Size:
        """The size this manager needs to lay out the container's children."""
        ...

    def apply(self, container: Container, area: Rect) -> None:
        """Place the children within ``area``, in screen cells."""
        ...

    def slaves(self, container: Container) -> Sequence[Managed]:
        """The widgets this manager is laying out in ``container``.

        ``Sequence`` and not ``list``: see the note on invariance above.
        """
        ...

    def remove(self, widget: Any) -> None:
        """Stop laying ``widget`` out. Not an error if it was never here.

        Part of the protocol because a widget can be moved from one
        container to another, and the one it is leaving has to be told -
        whichever manager that one happens to be using.
        """
        ...


class LayoutEngine:
    """Keeps a widget tree's geometry up to date.

    One per application. Containers are marked as needing work and the whole
    set is recomputed in one run, so a burst of changes costs one layout
    rather than one each.
    """

    def __init__(self, pass_limit: int = DEFAULT_PASS_LIMIT) -> None:
        """
        Args:
            pass_limit: Containers laid out in a single run before
                :class:`LayoutLoop` is raised.
        """
        self._pass_limit = pass_limit
        #: Containers needing recomputation. A dict rather than a set: it
        #: keeps insertion order, so a run is deterministic and a failure
        #: reproduces.
        self._dirty: dict[int, Any] = {}
        self._running = False

    # ------------------------------------------------------------ queueing

    def invalidate(self, container: Any) -> None:
        """Mark ``container`` as needing its children laid out again.

        Safe to call repeatedly and from inside a layout: the work is
        coalesced, and anything queued while a run is in progress is picked up
        by that same run.
        """
        if container is None:
            return
        self._dirty[id(container)] = container

    @property
    def pending(self) -> int:
        """How many containers are waiting to be laid out."""
        return len(self._dirty)

    @property
    def running(self) -> bool:
        """True while :meth:`run` is working."""
        return self._running

    def clear(self) -> None:
        """Discard queued work, as when the application is shutting down."""
        self._dirty.clear()

    # ------------------------------------------------------------- running

    def run(self) -> int:
        """Lay out everything queued. Returns how many containers were done.

        Reentrancy is refused rather than allowed: a manager that invalidates
        something while being applied has its request queued for the run in
        progress, and nesting runs would lay the same container out twice with
        half-applied geometry in between.

        Raises:
            LayoutLoop: If the work does not run out, which means a cycle.
        """
        if self._running:
            return 0
        self._running = True
        done = 0
        try:
            while self._dirty:
                if done >= self._pass_limit:
                    raise LayoutLoop(
                        f"layout did not settle after {done} passes; "
                        f"{len(self._dirty)} containers still queued, "
                        f"starting with {next(iter(self._dirty.values()))!r}"
                    )
                _, container = self._dirty.popitem()
                self._lay_out(container)
                done += 1
        finally:
            self._running = False
        return done

    def _lay_out(self, container: Any) -> None:
        """Recompute one container: what it needs, then where its children go.

        The order matters. The requested size is settled first, because a
        container that resizes to fit its children has to know its own size
        before it can place them in it.
        """
        manager = container._layout_manager
        # A paned window's panes, and pack or grid beside them (TkCurses-ect9).
        # Tk sizes the window by whichever manager asked last; here pack or
        # grid while it has children, and the panes otherwise.
        paned = getattr(container, "_paned_manager", None)
        sizer = manager
        if paned is not None and (manager is None or not manager.slaves(container)):
            sizer = paned
        if sizer is not None and getattr(sizer, "propagates", True):
            self._propagate(
                container, container._outer_size(sizer.requested(container))
            )
        if paned is not None:
            paned.apply(container, container._content_rect())
        if manager is not None:
            manager.apply(container, container._content_rect())
        # Placed children last, over what pack or grid arranged: place has a
        # layout of its own beside theirs, as in Tk. TkCurses-huq9.
        placed = getattr(container, "_place_manager", None)
        if placed is not None:
            placed.apply(container, container._content_rect())

    def _propagate(self, container: Any, requested: Size) -> None:
        """Record what a container needs and tell its parent, if it should.

        The walk stops at the first ancestor whose own requested size is
        unchanged, which is what makes this terminate: a change can only
        travel as far as it actually changes something, and sizes are
        integers, so it cannot oscillate by ever-smaller amounts.

        A container with propagation switched off absorbs the change instead:
        it keeps the size it was given and its parent is never told, which is
        exactly what ``pack_propagate(False)`` is for. A manager that does not
        size its container at all - place - never gets here.
        """
        if not container._layout_propagate:
            return
        if container._requested == requested:
            return
        container._requested = requested
        parent = container.master
        if parent is not None and (
            parent._layout_manager is not None
            or getattr(parent, "_place_manager", None) is not None
            or getattr(parent, "_paned_manager", None) is not None
        ):
            self.invalidate(parent)

    # ----------------------------------------------------------- diagnostics

    def ancestry(self, widget: Any) -> Iterator[Any]:
        """Walk from ``widget`` to the root, refusing to go round twice.

        The tree should be a tree. If something has made it a graph - a widget
        reparented under its own descendant - this stops rather than looping,
        and the caller sees a short walk instead of a hung process.

        Raises:
            LayoutLoop: If a widget is reached twice.
        """
        seen: set[int] = set()
        current = widget
        while current is not None:
            if id(current) in seen:
                raise LayoutLoop(f"widget tree contains a cycle at {current!r}")
            seen.add(id(current))
            yield current
            current = current.master
