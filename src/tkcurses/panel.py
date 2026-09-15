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

"""Stacked windows, the way ``curses.panel`` does them.

A curses window has no idea what is in front of it. Refresh two overlapping
windows in the wrong order and the wrong one is on top, and there is nothing
in curses proper to stop you - which is what ``curses.panel`` is for. It adds
one thing: an order, bottom to top, and an :func:`update_panels` that
refreshes every panel in it.

This is that, over the windows :mod:`tkcurses.curses` makes.

It does not reuse :class:`~tkcurses._core.panels.PanelStack`, which the
widgets stack themselves with, and the reason is a difference in what each
owns. That one creates its own windows from a rectangle and hands the
ordering to real curses panels; this one is handed a window that is already
a cell buffer and has to do the ordering itself. Sharing the code would mean
one class doing both, badly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tkcurses.curses import Window

__all__ = ["Panel", "bottom_panel", "new_panel", "top_panel", "update_panels"]

#: Every panel, bottom first. The last one is the one in front.
_stack: list[Panel] = []


class Panel:
    """One window's place in the stack.

    Made by :func:`new_panel` rather than directly, which is also how
    ``curses.panel`` has it.
    """

    def __init__(self, window: Window) -> None:
        self._window = window
        self._hidden = False
        self._userptr: Any = None

    # ------------------------------------------------------------- the window

    def window(self) -> Window:
        """The window this panel stacks."""
        return self._window

    def replace(self, window: Window) -> None:
        """Put a different window in this panel's place in the stack."""
        self._window = window

    # -------------------------------------------------------------- the order

    def above(self) -> Panel | None:
        """The panel directly in front of this one, if any."""
        return self._neighbour(1)

    def below(self) -> Panel | None:
        """The panel directly behind this one, if any."""
        return self._neighbour(-1)

    def _neighbour(self, step: int) -> Panel | None:
        """The panel one place along, or None at the end of the stack."""
        if self not in _stack:
            return None
        index = _stack.index(self) + step
        if not 0 <= index < len(_stack):
            return None
        return _stack[index]

    def top(self) -> None:
        """Bring this panel to the front."""
        self._restack(len(_stack))

    def bottom(self) -> None:
        """Send this panel to the back."""
        self._restack(0)

    def _restack(self, position: int) -> None:
        """Move this panel to a place in the order, if it is in one."""
        if self in _stack:
            _stack.remove(self)
            _stack.insert(min(position, len(_stack)), self)

    # ------------------------------------------------------------ visibility

    def hidden(self) -> bool:
        """Whether this panel is out of the stack for now."""
        return self._hidden

    def hide(self) -> None:
        """Take this panel out of the stack, keeping its place for later."""
        self._hidden = True

    def show(self) -> None:
        """Put a hidden panel back, at the front."""
        self._hidden = False
        if self not in _stack:
            _stack.append(self)

    # ------------------------------------------------------------- the rest

    def move(self, y: int, x: int) -> None:
        """Move this panel's window to ``(y, x)`` on the screen."""
        self._window.mvwin(y, x)

    def set_userptr(self, obj: Any) -> None:
        """Attach anything to this panel. curses' own escape hatch."""
        self._userptr = obj

    def userptr(self) -> Any:
        """Whatever was attached with :meth:`set_userptr`."""
        return self._userptr

    def __repr__(self) -> str:
        where = _stack.index(self) if self in _stack else -1
        return f"<tkcurses.panel.Panel at {where} hidden={self._hidden}>"


def new_panel(win: Window) -> Panel:
    """Put ``win`` in a panel at the front of the stack."""
    panel = Panel(win)
    _stack.append(panel)
    return panel


def top_panel() -> Panel | None:
    """The panel in front, ignoring hidden ones."""
    for panel in reversed(_stack):
        if not panel.hidden():
            return panel
    return None


def bottom_panel() -> Panel | None:
    """The panel at the back, ignoring hidden ones."""
    for panel in _stack:
        if not panel.hidden():
            return panel
    return None


def update_panels() -> None:
    """Copy every visible panel onto the screen, back to front.

    The whole of each window, not only what has changed in it. That is what
    makes the stack mean anything: a panel moving away has to leave whatever
    was behind it looking right, and the only thing that knows what was
    behind it is the panel behind it.

    As in curses, this stops short of painting - :func:`tkcurses.curses.doupdate`
    does that.
    """
    for panel in _stack:
        if panel.hidden():
            continue
        window = panel.window()
        window.touchwin()
        window.noutrefresh()


def _reset() -> None:
    """Empty the stack. For tests, and for a second screen in one process."""
    _stack.clear()
