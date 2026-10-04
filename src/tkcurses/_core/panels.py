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

"""Window stacking: which window is in front, and what is visible where.

Toplevels, menus and dialogs all overlap, so something has to own the order
they are drawn in and answer which of them a given cell belongs to.
:class:`PanelStack` does both, wrapping ``curses.panel``.

The ordering model is kept separate from the curses objects it drives: the
stack maintains its own bottom-to-top list and applies it, rather than reading
order back out of curses. That makes the interesting logic - stacking, hit
testing, visibility - testable without a terminal, and leaves one obvious place
where order is decided.
"""

from __future__ import annotations

import contextlib
import curses
import curses.panel
from typing import TYPE_CHECKING, Any

from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses._core.geometry import Point, Rect

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

__all__ = ["Panel", "PanelStack"]


class Panel:
    """One stacked window.

    Created through :meth:`PanelStack.new_panel`; not instantiated directly,
    because a panel only means anything as part of a stack.
    """

    def __init__(self, stack: PanelStack, window: Any, panel: Any, rect: Rect) -> None:
        self._stack = stack
        self._window = window
        self._panel = panel
        self._rect = rect
        self._hidden = False
        self._userptr: Any = None
        self._destroyed = False

    @property
    def window(self) -> Any:
        """The curses window this panel carries."""
        return self._window

    @property
    def rect(self) -> Rect:
        """Position and size on screen, in cells."""
        return self._rect

    @property
    def hidden(self) -> bool:
        """True while this panel is hidden."""
        return self._hidden

    @property
    def destroyed(self) -> bool:
        """True once the panel has been removed from its stack."""
        return self._destroyed

    def userptr(self) -> Any:
        """Application data attached to this panel."""
        return self._userptr

    def set_userptr(self, value: Any) -> None:
        """Attach application data, usually the owning widget."""
        self._userptr = value

    def __repr__(self) -> str:
        state = (
            "destroyed" if self._destroyed else ("hidden" if self._hidden else "shown")
        )
        return f"<Panel {self._rect.width}x{self._rect.height} at ({self._rect.x},{self._rect.y}) {state}>"


def _default_window_factory(rect: Rect) -> Any:
    """Create a real curses window for ``rect``."""
    return curses.newwin(rect.height, rect.width, rect.y, rect.x)


def _default_panel_factory(window: Any) -> Any:
    """Wrap a curses window in a panel."""
    return curses.panel.new_panel(window)


class PanelStack:
    """Owns the z-order of every stacked window.

    Args:
        dispatcher: Serialises the curses calls. Defaults to the shared one.
        window_factory: Creates the backing window. Replaceable so the
            ordering logic can be exercised without a terminal.
        panel_factory: Wraps a window in a curses panel. ``None`` skips the
            curses side entirely, leaving a pure ordering model.
    """

    def __init__(
        self,
        *,
        dispatcher: CursesDispatcher | None = None,
        window_factory: Callable[[Rect], Any] = _default_window_factory,
        panel_factory: Callable[[Any], Any] | None = _default_panel_factory,
    ) -> None:
        self._dispatcher = dispatcher or CursesDispatcher.get()
        self._window_factory = window_factory
        self._panel_factory = panel_factory
        #: Bottom to top. The last element is the frontmost panel.
        self._order: list[Panel] = []
        #: Placed before every flush when set; see screen.TerminalCursor.
        self.cursor: Any = None

    # ------------------------------------------------------------ creation

    def new_panel(self, rect: Rect, *, userptr: Any = None) -> Panel:
        """Create a panel at ``rect`` and place it on top of the stack."""
        if rect.is_empty:
            raise ValueError(f"panel must have a non-zero size, got {rect}")
        window = self._dispatcher.call(self._window_factory, rect)
        backing = (
            self._dispatcher.call(self._panel_factory, window)
            if self._panel_factory is not None
            else None
        )
        panel = Panel(self, window, backing, rect)
        panel.set_userptr(userptr)
        self._order.append(panel)
        self._apply_order()
        return panel

    def destroy(self, panel: Panel) -> None:
        """Remove ``panel`` from the stack. Safe to call more than once."""
        if panel._destroyed:
            return
        panel._destroyed = True
        # destroy() is the only thing that removes a panel, so a panel that is
        # not yet destroyed is necessarily still in the order.
        self._order.remove(panel)
        if panel._panel is not None:
            # curses reclaims the panel when the last reference goes; drop
            # ours so a destroyed panel cannot be restacked by accident.
            panel._panel = None
        self._apply_order()

    def clear(self) -> None:
        """Destroy every panel, for a screen being torn down."""
        for panel in list(self._order):
            self.destroy(panel)

    # ------------------------------------------------------------ ordering

    @property
    def panels(self) -> tuple[Panel, ...]:
        """Every panel, bottom first."""
        return tuple(self._order)

    @property
    def visible(self) -> tuple[Panel, ...]:
        """Panels that are not hidden, bottom first."""
        return tuple(panel for panel in self._order if not panel.hidden)

    def __len__(self) -> int:
        return len(self._order)

    def __iter__(self) -> Iterator[Panel]:
        return iter(self._order)

    def __contains__(self, panel: object) -> bool:
        return panel in self._order

    def top(self) -> Panel | None:
        """The frontmost visible panel, if any."""
        visible = self.visible
        return visible[-1] if visible else None

    def bottom(self) -> Panel | None:
        """The rearmost visible panel, if any."""
        visible = self.visible
        return visible[0] if visible else None

    def above(self, panel: Panel) -> Panel | None:
        """The panel directly in front of ``panel``."""
        index = self._index(panel)
        return self._order[index + 1] if index + 1 < len(self._order) else None

    def below(self, panel: Panel) -> Panel | None:
        """The panel directly behind ``panel``."""
        index = self._index(panel)
        return self._order[index - 1] if index > 0 else None

    def raise_to_top(self, panel: Panel) -> None:
        """Move ``panel`` in front of everything else."""
        index = self._index(panel)
        self._order.append(self._order.pop(index))
        self._apply_order()

    def lower_to_bottom(self, panel: Panel) -> None:
        """Move ``panel`` behind everything else."""
        index = self._index(panel)
        self._order.insert(0, self._order.pop(index))
        self._apply_order()

    def raise_above(self, panel: Panel, other: Panel) -> None:
        """Place ``panel`` directly in front of ``other``."""
        if panel is other:
            raise ValueError("cannot stack a panel relative to itself")
        self._order.pop(self._index(panel))
        self._order.insert(self._index(other) + 1, panel)
        self._apply_order()

    def lower_below(self, panel: Panel, other: Panel) -> None:
        """Place ``panel`` directly behind ``other``."""
        if panel is other:
            raise ValueError("cannot stack a panel relative to itself")
        self._order.pop(self._index(panel))
        self._order.insert(self._index(other), panel)
        self._apply_order()

    # ---------------------------------------------------------- visibility

    def show(self, panel: Panel) -> None:
        """Make ``panel`` visible."""
        self._check(panel)
        if not panel._hidden:
            return
        panel._hidden = False
        if panel._panel is not None:
            self._dispatcher.call(panel._panel.show)
        self._apply_order()

    def hide(self, panel: Panel) -> None:
        """Hide ``panel`` without destroying it.

        Its place in the order is kept, so showing it again restores the
        stacking the application had set up rather than bringing it to front.
        """
        self._check(panel)
        if panel._hidden:
            return
        panel._hidden = True
        if panel._panel is not None:
            self._dispatcher.call(panel._panel.hide)

    # -------------------------------------------------------------- layout

    def move(self, panel: Panel, x: int, y: int) -> None:
        """Move ``panel`` so its top-left corner is at ``(x, y)``."""
        self._check(panel)
        panel._rect = Rect(x, y, panel._rect.width, panel._rect.height)
        if panel._panel is not None:
            self._dispatcher.call(panel._panel.move, y, x)

    def replace_window(self, panel: Panel, rect: Rect) -> None:
        """Give ``panel`` a new window of size ``rect``.

        Curses windows cannot be resized in place, so a resize means building
        a replacement and handing it to the panel.
        """
        self._check(panel)
        if rect.is_empty:
            raise ValueError(f"panel must have a non-zero size, got {rect}")
        window = self._dispatcher.call(self._window_factory, rect)
        if panel._panel is not None:
            self._dispatcher.call(panel._panel.replace, window)
        panel._window = window
        panel._rect = rect

    # --------------------------------------------------------- hit testing

    def panel_at(self, x: int, y: int) -> Panel | None:
        """The frontmost visible panel covering ``(x, y)``, if any.

        This is what decides which widget a mouse click belongs to when
        windows overlap, so it searches front to back and stops at the first
        hit.
        """
        point = Point(x, y)
        for panel in reversed(self._order):
            if not panel.hidden and panel.rect.contains_point(point):
                return panel
        return None

    def panels_at(self, x: int, y: int) -> tuple[Panel, ...]:
        """Every visible panel covering ``(x, y)``, frontmost first."""
        point = Point(x, y)
        return tuple(
            panel
            for panel in reversed(self._order)
            if not panel.hidden and panel.rect.contains_point(point)
        )

    # -------------------------------------------------------------- output

    def touch_all(self) -> None:
        """Mark every visible panel as needing to be written out again.

        A panel window keeps its own contents, but curses tracks what it
        believes is already on the terminal and sends nothing for a window
        that has not changed. When the screen has been cleared underneath the
        stack - which is what a terminal resize does - that belief is wrong
        for every panel at once, and only the ones that happened to change
        would be drawn back.
        """
        if self._panel_factory is None:
            return
        self._dispatcher.call(self._touch)

    def _touch(self) -> None:
        """Run the curses side of :meth:`touch_all` on the dispatcher's thread."""
        for panel in self._order:
            if panel.hidden or panel._window is None:
                continue
            with contextlib.suppress(curses.error):
                panel._window.touchwin()

    def update(self) -> None:
        """Push the stack to the terminal."""
        if self._panel_factory is None:
            return
        self._dispatcher.call(self._refresh)

    def _refresh(self) -> None:
        """Run the curses side of :meth:`update` on the dispatcher's thread."""
        curses.panel.update_panels()
        if self.cursor is not None:
            # After update_panels, which leaves the virtual cursor wherever
            # the last panel's window had it, and before the flush.
            self.cursor.place()
        curses.doupdate()

    # ----------------------------------------------------------- internals

    def _index(self, panel: Panel) -> int:
        """Position of ``panel`` in the order, raising if it is not stacked."""
        self._check(panel)
        return self._order.index(panel)

    def _check(self, panel: Panel) -> None:
        """Reject a panel that no longer belongs to this stack."""
        if panel._destroyed or panel not in self._order:
            raise ValueError("panel is not part of this stack")

    def _apply_order(self) -> None:
        """Impose this stack's order on curses.

        Raising each panel in turn from the bottom leaves curses' own stack
        matching ours, which is cheaper to reason about than tracking the
        difference between the two.
        """
        if self._panel_factory is None:
            return
        for panel in self._order:
            if panel._panel is not None and not panel.hidden:
                self._dispatcher.call(panel._panel.top)
