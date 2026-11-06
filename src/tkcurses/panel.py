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

"""Windows stacked in front of one another, as ``curses.panel``.

Sample output:
    from tkcurses import curses, panel
    stdscr = curses.initscr()
    panels = []
    for n, (y, x) in enumerate(((1, 2), (3, 10), (5, 18))):
        win = curses.newwin(4, 18, y, x)
        win.box()
        win.addstr(1, 2, f"Panel {n + 1}")
        panels.append(panel.new_panel(win))
    panels[0].top()
    panel.update_panels()
    curses.doupdate()

Put each window in a panel with :func:`new_panel`; the newest is in
front. :meth:`Panel.top`, :meth:`Panel.bottom`, :meth:`Panel.hide` and
:meth:`Panel.show` change the order, and :func:`update_panels` followed
by :func:`tkcurses.curses.doupdate` puts the screen right, whatever
order the windows were written in.

TkCurses extension:
    tkinter has no such module. This is the standard library's
    ``curses.panel``, for the windows :mod:`tkcurses.curses` makes.
"""
# A curses window has no idea what is in front of it; this adds an order,
# bottom to top. It does not reuse the PanelStack the widgets stack themselves
# with, because of what each owns: that one creates its own windows from a
# rectangle and hands the ordering to real curses panels, while this one is
# handed a window that is already a cell buffer and has to do the ordering
# itself.

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
        #: Where this panel was last copied to, so that moving or hiding it
        #: can have the background put back over the place it left.
        self._painted: tuple[int, int, int, int] | None = None

    def _area(self) -> tuple[int, int, int, int]:
        """Where this panel is now, as ``(y, x, height, width)``."""
        top, left = self._window.getbegyx()
        height, width = self._window.getmaxyx()
        return (top, left, height, width)

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

    Where a panel has been hidden or moved away from is first put back from
    ``stdscr``, the window behind everything, so a hidden panel leaves the
    screen. Then every visible panel is copied whole, since one not written
    to still has to be copied if something in front of it moved. As in
    curses this stops short of painting: :func:`tkcurses.curses.doupdate`
    does that.

    Differences from curses:
        When a tkinter application owns the screen, the widgets are the
        background rather than ``stdscr``, and the first step is left to
        the application.
    """
    # Measured: the standard library puts back what a hidden panel covered,
    # and without the first step a hidden panel stays on the screen. Skipped
    # when tkcurses.curses attached to an application's screen, where stdscr
    # is a blank window: restoring from it wiped the widget half of the demo
    # off the screen on a resize.
    from tkcurses import curses as _tkcurses

    # stdscr is the background only when this process started the screen.
    # Attached to a running application it is a blank window and the widgets
    # are what is behind the panels, so restoring from it paints blanks over
    # them.
    background = _tkcurses._stdscr if _tkcurses._owns_screen else None
    for panel in _stack:
        where = panel._painted
        if where is None:
            continue
        if panel.hidden() or where != panel._area():
            if background is not None:
                background.touch_region(*where)
            panel._painted = None
    if background is not None and background.is_wintouched():
        background.noutrefresh()
    for panel in _stack:
        if panel.hidden():
            panel._painted = None
            continue
        window = panel.window()
        window.touchwin()
        window.noutrefresh()
        panel._painted = panel._area()


def _reset() -> None:
    """Empty the stack. For tests, and for a second screen in one process."""
    _stack.clear()
