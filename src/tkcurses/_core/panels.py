"""Panel management for TkCurses internals.

Wraps curses.panel functionality for managing overlapping
windows. Handles z-order, visibility, and panel updates
for the widget hierarchy.
"""

from __future__ import annotations

import curses.panel
from typing import TYPE_CHECKING, Any, Optional

from .dispatcher import CursesDispatcher

if TYPE_CHECKING:
    from curses import _CursesWindow


class PanelError(Exception):
    """Exception raised for panel-related errors."""

    pass


class Panel:
    """Wrapper around curses.panel.Panel for window z-ordering.

    Provides a higher-level interface to curses panels with thread-safe
    operations through CursesDispatcher. Each panel wraps a curses window
    and provides methods for managing visibility and z-order position.

    All curses.panel operations are serialized through CursesDispatcher
    to ensure thread safety, as curses is not thread-safe.

    Attributes:
        window: The underlying curses window object.

    Example:
        >>> from tkcurses._core.screen import CursesScreen
        >>> from tkcurses._core.panels import Panel, PanelStack
        >>> screen = CursesScreen()
        >>> screen.initialize()
        >>> win = screen.stdscr.subwin(10, 20, 0, 0)
        >>> panel = Panel(win)
        >>> panel.show()
        >>> panel.top()
    """

    def __init__(self, window: _CursesWindow) -> None:
        """Initialize a Panel wrapper around a curses window.

        Args:
            window: The curses window to wrap in a panel.

        Raises:
            PanelError: If panel creation fails.
        """
        self._window = window
        self._dispatcher = CursesDispatcher.get()
        self._userptr: Any = None

        # Create the panel through the dispatcher for thread safety
        try:
            self._panel = self._dispatcher.call(curses.panel.new_panel, window)
            self._visible = True
        except Exception as e:
            raise PanelError(f"Failed to create panel: {e}") from e

    @property
    def window(self) -> _CursesWindow:
        """The underlying curses window object.

        Returns:
            The curses window wrapped by this panel.
        """
        return self._window

    def show(self) -> None:
        """Make the panel visible.

        If the panel is already visible, this is a no-op.
        Call PanelStack.update() to reflect changes on screen.

        Raises:
            PanelError: If the show operation fails.
        """
        if self._visible:
            return

        try:
            self._dispatcher.call(self._panel.show)
            self._visible = True
        except Exception as e:
            raise PanelError(f"Failed to show panel: {e}") from e

    def hide(self) -> None:
        """Hide the panel from display.

        If the panel is already hidden, this is a no-op.
        Call PanelStack.update() to reflect changes on screen.

        Raises:
            PanelError: If the hide operation fails.
        """
        if not self._visible:
            return

        try:
            self._dispatcher.call(self._panel.hide)
            self._visible = False
        except Exception as e:
            raise PanelError(f"Failed to hide panel: {e}") from e

    def top(self) -> None:
        """Move panel to the top of the stack.

        Makes this panel render above all other panels.
        Call PanelStack.update() to reflect changes on screen.

        Raises:
            PanelError: If the move operation fails.
        """
        try:
            self._dispatcher.call(self._panel.top)
        except Exception as e:
            raise PanelError(f"Failed to move panel to top: {e}") from e

    def bottom(self) -> None:
        """Move panel to the bottom of the stack.

        Makes this panel render below all other panels.
        Call PanelStack.update() to reflect changes on screen.

        Raises:
            PanelError: If the move operation fails.
        """
        try:
            self._dispatcher.call(self._panel.bottom)
        except Exception as e:
            raise PanelError(f"Failed to move panel to bottom: {e}") from e

    def above(self) -> Optional[Panel]:
        """Get the panel above this one in the stack.

        Returns:
            The Panel above this one, or None if this is the top panel.

        Raises:
            PanelError: If the operation fails.
        """
        try:
            above_panel = self._dispatcher.call(self._panel.above)
            if above_panel is None:
                return None
            # Get the PanelStack to look up our wrapper
            stack = PanelStack.get()
            return stack._get_panel_wrapper(above_panel)
        except Exception as e:
            raise PanelError(f"Failed to get panel above: {e}") from e

    def below(self) -> Optional[Panel]:
        """Get the panel below this one in the stack.

        Returns:
            The Panel below this one, or None if this is the bottom panel.

        Raises:
            PanelError: If the operation fails.
        """
        try:
            below_panel = self._dispatcher.call(self._panel.below)
            if below_panel is None:
                return None
            # Get the PanelStack to look up our wrapper
            stack = PanelStack.get()
            return stack._get_panel_wrapper(below_panel)
        except Exception as e:
            raise PanelError(f"Failed to get panel below: {e}") from e

    def hidden(self) -> bool:
        """Check if the panel is hidden.

        Returns:
            True if the panel is hidden, False if visible.

        Raises:
            PanelError: If the operation fails.
        """
        try:
            return self._dispatcher.call(self._panel.hidden)
        except Exception as e:
            raise PanelError(f"Failed to check panel visibility: {e}") from e

    def move(self, y: int, x: int) -> None:
        """Move the panel's window to a new position.

        Args:
            y: New row position (0-based).
            x: New column position (0-based).

        Raises:
            PanelError: If the move operation fails.
        """
        try:
            self._dispatcher.call(self._panel.move, y, x)
        except Exception as e:
            raise PanelError(f"Failed to move panel to ({y}, {x}): {e}") from e

    def replace(self, window: _CursesWindow) -> None:
        """Replace the panel's window with a new window.

        Args:
            window: The new curses window for this panel.

        Raises:
            PanelError: If the replace operation fails.
        """
        try:
            self._dispatcher.call(self._panel.replace, window)
            self._window = window
        except Exception as e:
            raise PanelError(f"Failed to replace panel window: {e}") from e

    def set_userptr(self, obj: Any) -> None:
        """Set arbitrary user data associated with this panel.

        Args:
            obj: Any Python object to associate with this panel.
        """
        self._userptr = obj

    def userptr(self) -> Any:
        """Get the user data associated with this panel.

        Returns:
            The user object previously set with set_userptr(), or None.
        """
        return self._userptr


class PanelStack:
    """Manages a stack of panels for window z-ordering.

    PanelStack provides centralized management of all curses panels
    in the application. It tracks panel creation, maintains references
    to prevent garbage collection, and provides methods for stack-wide
    operations like updating all panels.

    This class implements the singleton pattern - only one stack instance
    can exist per process.

    Example:
        >>> from tkcurses._core.screen import CursesScreen
        >>> from tkcurses._core.panels import PanelStack
        >>> screen = CursesScreen()
        >>> screen.initialize()
        >>> stack = PanelStack.get()
        >>> win = screen.stdscr.subwin(10, 20, 0, 0)
        >>> panel = stack.create_panel(win)
        >>> stack.update()
    """

    _instance: Optional[PanelStack] = None

    def __init__(self) -> None:
        """Initialize the PanelStack.

        Note:
            Do not call this directly. Use PanelStack.get() instead.
        """
        self._panels: list[Panel] = []
        self._dispatcher = CursesDispatcher.get()

    @classmethod
    def get(cls) -> PanelStack:
        """Get the singleton PanelStack instance.

        Creates the instance on first call. Subsequent calls return
        the same instance.

        Returns:
            The singleton PanelStack instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_panel(self, window: _CursesWindow) -> Panel:
        """Create a new panel for the given window.

        The panel is automatically added to the stack and tracked
        to prevent garbage collection.

        Args:
            window: The curses window to wrap in a panel.

        Returns:
            The newly created Panel object.

        Raises:
            PanelError: If panel creation fails.
        """
        panel = Panel(window)
        self._panels.append(panel)
        return panel

    def remove_panel(self, panel: Panel) -> None:
        """Remove a panel from the stack.

        The panel is hidden and removed from tracking. After removal,
        the panel object should not be used.

        Args:
            panel: The Panel to remove.

        Raises:
            PanelError: If the panel is not in the stack.
        """
        if panel not in self._panels:
            raise PanelError("Panel is not in the stack")

        panel.hide()
        self._panels.remove(panel)

    def update(self) -> None:
        """Update all panels and refresh the display.

        This method must be called after any panel operations (show, hide,
        top, bottom, move) to make the changes visible on screen.

        Calls curses.panel.update_panels() to update the virtual screen
        from all visible panels, then curses.doupdate() to update the
        physical screen. Both calls are serialized through CursesDispatcher
        for thread safety.

        Raises:
            PanelError: If the update operation fails.
        """
        try:
            self._dispatcher.call(curses.panel.update_panels)
            self._dispatcher.call(curses.doupdate)
        except Exception as e:
            raise PanelError(f"Failed to update panels: {e}") from e

    def top_panel(self) -> Optional[Panel]:
        """Get the topmost panel in the stack.

        Returns:
            The topmost Panel, or None if the stack is empty.

        Raises:
            PanelError: If the operation fails.
        """
        if not self._panels:
            return None

        try:
            top = self._dispatcher.call(curses.panel.top_panel)
            if top is None:
                return None
            return self._get_panel_wrapper(top)
        except Exception as e:
            raise PanelError(f"Failed to get top panel: {e}") from e

    def bottom_panel(self) -> Optional[Panel]:
        """Get the bottommost panel in the stack.

        Returns:
            The bottommost Panel, or None if the stack is empty.

        Raises:
            PanelError: If the operation fails.
        """
        if not self._panels:
            return None

        try:
            bottom = self._dispatcher.call(curses.panel.bottom_panel)
            if bottom is None:
                return None
            return self._get_panel_wrapper(bottom)
        except Exception as e:
            raise PanelError(f"Failed to get bottom panel: {e}") from e

    def get_panels(self) -> list[Panel]:
        """Get all panels in the stack.

        Returns:
            A list of all Panel objects in the stack.
        """
        return list(self._panels)

    def clear(self) -> None:
        """Remove all panels from the stack.

        All panels are hidden and removed from tracking.
        """
        for panel in list(self._panels):
            panel.hide()
        self._panels.clear()

    def _get_panel_wrapper(self, curses_panel: Any) -> Optional[Panel]:
        """Find the Panel wrapper for a curses.panel object.

        Args:
            curses_panel: The underlying curses.panel.Panel object.

        Returns:
            The Panel wrapper, or None if not found.
        """
        for panel in self._panels:
            if panel._panel == curses_panel:
                return panel
        return None

    @classmethod
    def reset_singleton(cls) -> None:
        """Reset the singleton instance (primarily for testing).

        Warning:
            This method is intended for testing purposes only.
            Using it in production code may lead to unexpected behavior.
        """
        if cls._instance is not None:
            cls._instance.clear()
        cls._instance = None
