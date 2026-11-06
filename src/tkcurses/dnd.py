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
# Portions adapted from CPython's Lib/tkinter/dnd.py.
# Copyright (c) 2001 Python Software Foundation; All Rights Reserved.
# Used under the Python Software Foundation License Version 2; see
# THIRD_PARTY_NOTICES.md for the licence and a summary of the changes.

"""Dragging something from one widget to another within an application,
as ``tkinter.dnd``.

This coordinates a drag; both ends are the application's to write, as
in tkinter.

**Starting one.** Bind a button press on whatever can be dragged, and
from that callback call ``dnd_start(source, event)``. ``source`` can be
any object - it need not be a widget - and it is what the other end is
handed. A second drag while one is running is ignored.

**Receiving one.** As the pointer moves, the widget under it is asked
for a ``dnd_accept(source, event)`` method; if it has none, or that
returns None, its master is asked, and so on up to the root. Whatever
first answers becomes the target, and need not be the widget. Then:

=============================  =======================================
what happened                  what is called
=============================  =======================================
moved onto a target            ``target.dnd_enter(source, event)``
moved within the same target   ``target.dnd_motion(source, event)``
moved off a target             ``target.dnd_leave(source, event)``
released over a target         ``target.dnd_commit(source, event)``
released anywhere              ``source.dnd_end(target, event)``
=============================  =======================================

``dnd_end`` is always called, so a source can put itself back if
nothing took it. A drag needs a terminal that reports the mouse moving
while a button is held; most do.

Differences from tkinter:
    The mouse pointer does not change during a drag: the pointer belongs
    to the terminal. And tkinter's demonstration classes ``Icon`` and
    ``Tester`` are not here, because they need
    ``Canvas.create_window``, which is not available yet.
"""
# tkinter's own docstring opens "This is very preliminary". Without motion
# reports a drag looks like a press and a release far apart, the same
# limitation the Text widget's drag-selection has. A bare Misc has no cursor
# option, so imitating the hand cursor would refuse the request. create_window
# is TkCurses-aj1.16.1.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tkcurses import Event, Misc

__all__ = ["DndHandler", "dnd_start"]

#: Buttons a drag may be started with. Above this is the wheel, which curses
#: reports as buttons 4 and 5 and which cannot be held down to drag with.
LAST_DRAG_BUTTON = 3


def dnd_start(source: Any, event: Event) -> DndHandler | None:
    """Begin a drag, unless one is already running.

    Args:
        source: The object being dragged. Anything the other end will
            understand; it need not be a widget.
        event: The button press that started it.

    Returns:
        The handler, which the caller need not keep - it stays alive on its
        own for as long as the drag lasts - or None if nothing was started.
    """
    handler = DndHandler(source, event)
    return handler if handler.root is not None else None


class DndHandler:
    """One drag in progress. Made by :func:`dnd_start` rather than directly."""

    root: Misc | None = None

    def __init__(self, source: Any, event: Event) -> None:
        if event.num > LAST_DRAG_BUTTON:
            # The wheel. Nothing can be dragged with a button that cannot be
            # held, and curses reports wheel movement as buttons 4 and 5.
            return
        root = event.widget._root()
        if root.tk.dnd is not None:
            # A drag is already running. Ignored rather than refused: two
            # bindings on one press both calling dnd_start is ordinary, and
            # the second must not disturb the first.
            return
        root.tk.dnd = self
        self.root = root

        self.source = source
        self.target: Any = None
        self.initial_button = event.num
        self.initial_widget = event.widget
        self.release_pattern = f"<B{event.num}-ButtonRelease-{event.num}>"
        self.initial_widget.bind(self.release_pattern, self.on_release)
        self.initial_widget.bind("<Motion>", self.on_motion)

    def __del__(self) -> None:
        root, self.root = self.root, None
        if root is not None and root.tk.dnd is self:
            root.tk.dnd = None

    # ------------------------------------------------------------- tracking

    def on_motion(self, event: Event) -> None:
        """Find what is under the pointer, and tell it what changed."""
        widget: Misc | None = self.initial_widget.winfo_containing(
            event.x_root, event.y_root
        )
        source = self.source
        new_target = None
        while widget is not None:
            accept = getattr(widget, "dnd_accept", None)
            if accept is not None:
                new_target = accept(source, event)
                if new_target is not None:
                    break
            widget = widget.master

        old_target = self.target
        if old_target is new_target:
            if old_target is not None:
                old_target.dnd_motion(source, event)
            return
        if old_target is not None:
            self.target = None
            old_target.dnd_leave(source, event)
        if new_target is not None:
            new_target.dnd_enter(source, event)
            self.target = new_target

    def on_release(self, event: Event) -> None:
        """The drag ended over something. Commit it."""
        self.finish(event, commit=True)

    def cancel(self, event: Event | None = None) -> None:
        """The drag ended without being dropped. Put everything back."""
        self.finish(event, commit=False)

    def finish(self, event: Event | None, commit: bool = False) -> None:
        """Unwind the drag, telling both ends how it ended.

        ``dnd_end`` is called whatever else happens - including when the
        target raises - because a source that is never told the drag is over
        has no way of putting itself back.
        """
        target = self.target
        source = self.source
        widget = self.initial_widget
        root = self.root
        try:
            if root is not None:
                root.tk.dnd = None
            widget.unbind(self.release_pattern)
            widget.unbind("<Motion>")
            self.target = self.source = self.initial_widget = None
            self.root = None
            if target is not None:
                if commit:
                    target.dnd_commit(source, event)
                else:
                    target.dnd_leave(source, event)
        finally:
            source.dnd_end(target, event)
