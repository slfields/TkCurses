"""Low-level curses screen management for TkCurses.

Handles curses initialization, screen setup, window creation,
and teardown. Provides the foundation for all terminal
rendering operations.
"""

from __future__ import annotations

import curses
import threading
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from curses import _CursesWindow


class CursesScreenError(Exception):
    """Exception raised for curses screen-related errors."""

    pass


class CursesScreen:
    """Wrapper for curses screen management with safe initialization/cleanup.

    CursesScreen provides a high-level interface for managing the curses
    terminal screen. It handles initialization of terminal modes, color
    support detection, and ensures proper cleanup on exit.

    This class implements the singleton pattern - only one screen instance
    can exist per process. Attempting to create multiple instances will
    return the existing instance.

    Attributes:
        stdscr: The underlying curses window object (None until initialized).
        width: Terminal width in columns.
        height: Terminal height in lines.
        has_colors: Whether the terminal supports colors.
        can_change_colors: Whether terminal colors can be redefined.
        max_colors: Maximum number of colors supported.
        max_color_pairs: Maximum number of color pairs supported.

    Example:
        Using as a context manager (recommended)::

            with CursesScreen() as screen:
                screen.clear()
                screen.refresh()
                # ... use the screen ...

        Manual initialization::

            screen = CursesScreen()
            screen.initialize()
            try:
                # ... use the screen ...
            finally:
                screen.cleanup()
    """

    _instance: Optional[CursesScreen] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> CursesScreen:
        """Create or return the singleton CursesScreen instance.

        Thread-safe: All initialization is performed under the lock to prevent
        race conditions when multiple threads call CursesScreen() simultaneously.

        Returns:
            The singleton CursesScreen instance.
        """
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                # Initialize all attributes under the lock to ensure thread safety
                instance._initialized = False
                instance._stdscr = None
                instance._has_colors = False
                instance._can_change_colors = False
                instance._max_colors = 0
                instance._max_color_pairs = 0
                cls._instance = instance
            return cls._instance

    def __init__(self) -> None:
        """Initialize the CursesScreen wrapper.

        Note:
            This does NOT initialize curses. Call initialize() or use
            the context manager to actually set up the terminal.

            All attribute initialization is done in __new__ for thread safety.
            This method is intentionally empty.
        """
        # All initialization done in __new__ for thread safety
        pass

    def initialize(self) -> None:
        """Initialize the curses screen and terminal modes.

        Sets up the terminal for curses operation including:
        - Disabling echo of input characters
        - Enabling cbreak mode for immediate character availability
        - Enabling keypad mode for special key handling
        - Initializing color support if available
        - Hiding the cursor

        Raises:
            CursesScreenError: If the screen is already initialized or
                if curses initialization fails.
        """
        if self._initialized:
            raise CursesScreenError("Screen is already initialized")

        try:
            # Initialize curses and get the standard screen
            self._stdscr = curses.initscr()

            # Disable echo of input characters
            curses.noecho()

            # Enable cbreak mode (characters available immediately)
            curses.cbreak()

            # Enable keypad mode for special keys (arrows, function keys, etc.)
            self._stdscr.keypad(True)

            # Initialize color support if available
            if curses.has_colors():
                curses.start_color()
                self._has_colors = True

                # Try to use default terminal colors (-1 for transparent)
                try:
                    curses.use_default_colors()
                except curses.error:
                    pass

                # Store color capabilities
                self._max_colors = curses.COLORS
                self._max_color_pairs = curses.COLOR_PAIRS

                # Check if colors can be redefined
                self._can_change_colors = curses.can_change_color()

            # Hide the cursor (may fail on some terminals)
            try:
                curses.curs_set(0)
            except curses.error:
                pass

            self._initialized = True

        except curses.error as e:
            # Attempt cleanup on failure
            self._emergency_cleanup()
            raise CursesScreenError(f"Failed to initialize curses: {e}") from e

    def cleanup(self) -> None:
        """Restore the terminal to its original state.

        Reverses all terminal mode changes made during initialization
        and ends the curses session. Safe to call multiple times.
        """
        if not self._initialized:
            return

        try:
            # Show the cursor again
            try:
                curses.curs_set(1)
            except curses.error:
                pass

            # Disable keypad mode
            if self._stdscr is not None:
                try:
                    self._stdscr.keypad(False)
                except curses.error:
                    pass

            # Restore echo mode
            try:
                curses.echo()
            except curses.error:
                pass

            # Disable cbreak mode
            try:
                curses.nocbreak()
            except curses.error:
                pass

            # End the curses session
            try:
                curses.endwin()
            except curses.error:
                pass

        finally:
            self._initialized = False
            self._stdscr = None
            self._has_colors = False
            self._can_change_colors = False
            self._max_colors = 0
            self._max_color_pairs = 0

    def _emergency_cleanup(self) -> None:
        """Attempt cleanup after a failed initialization.

        This method attempts to restore terminal state even when
        initialization was only partially successful.
        """
        try:
            curses.echo()
        except Exception:
            pass
        try:
            curses.nocbreak()
        except Exception:
            pass
        try:
            curses.endwin()
        except Exception:
            pass

        self._initialized = False
        self._stdscr = None

    def __enter__(self) -> CursesScreen:
        """Enter the context manager and initialize the screen.

        Returns:
            The initialized CursesScreen instance.

        Raises:
            CursesScreenError: If initialization fails.
        """
        self.initialize()
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        """Exit the context manager and cleanup the screen.

        Args:
            exc_type: Exception type if an exception was raised.
            exc_val: Exception value if an exception was raised.
            exc_tb: Traceback if an exception was raised.
        """
        self.cleanup()

    @property
    def stdscr(self) -> Optional[_CursesWindow]:
        """The underlying curses window object.

        Returns:
            The curses standard screen window, or None if not initialized.
        """
        return self._stdscr

    @property
    def width(self) -> int:
        """Terminal width in columns.

        Returns:
            The number of columns in the terminal, or 0 if not initialized.
        """
        if not self._initialized:
            return 0
        return curses.COLS

    @property
    def height(self) -> int:
        """Terminal height in lines.

        Returns:
            The number of lines in the terminal, or 0 if not initialized.
        """
        if not self._initialized:
            return 0
        return curses.LINES

    @property
    def has_colors(self) -> bool:
        """Whether the terminal supports colors.

        Returns:
            True if color support is available, False otherwise.
        """
        return self._has_colors

    @property
    def can_change_colors(self) -> bool:
        """Whether terminal colors can be redefined.

        Returns:
            True if colors can be customized, False otherwise.
        """
        return self._can_change_colors

    @property
    def max_colors(self) -> int:
        """Maximum number of colors supported by the terminal.

        Returns:
            The maximum number of colors, or 0 if not initialized
            or colors are not supported.
        """
        return self._max_colors

    @property
    def max_color_pairs(self) -> int:
        """Maximum number of color pairs supported by the terminal.

        Returns:
            The maximum number of color pairs, or 0 if not initialized
            or colors are not supported.
        """
        return self._max_color_pairs

    def refresh(self) -> None:
        """Refresh the screen to display pending changes.

        Updates the physical screen to match the virtual screen buffer.

        Raises:
            CursesScreenError: If the screen is not initialized.
        """
        if not self._initialized or self._stdscr is None:
            raise CursesScreenError("Screen is not initialized")
        self._stdscr.refresh()

    def clear(self) -> None:
        """Clear the screen.

        Removes all content from the screen buffer. Call refresh()
        to update the display.

        Raises:
            CursesScreenError: If the screen is not initialized.
        """
        if not self._initialized or self._stdscr is None:
            raise CursesScreenError("Screen is not initialized")
        self._stdscr.clear()

    def resize_term(self, lines: int, cols: int) -> None:
        """Handle terminal resize.

        Resizes the curses internal structures to match the new
        terminal dimensions. This should be called when the terminal
        window is resized (typically in response to a SIGWINCH signal).

        Args:
            lines: New terminal height in lines.
            cols: New terminal width in columns.

        Raises:
            CursesScreenError: If the screen is not initialized.
        """
        if not self._initialized:
            raise CursesScreenError("Screen is not initialized")
        curses.resizeterm(lines, cols)

    def getmaxyx(self) -> Tuple[int, int]:
        """Get the terminal dimensions.

        Returns:
            A tuple of (height, width) representing the terminal size
            in lines and columns.

        Raises:
            CursesScreenError: If the screen is not initialized.
        """
        if not self._initialized or self._stdscr is None:
            raise CursesScreenError("Screen is not initialized")
        return self._stdscr.getmaxyx()

    @classmethod
    def reset_singleton(cls) -> None:
        """Reset the singleton instance (primarily for testing).

        Warning:
            This method is intended for testing purposes only.
            Using it in production code may lead to unexpected behavior.
        """
        with cls._lock:
            if cls._instance is not None and cls._instance._initialized:
                cls._instance.cleanup()
            cls._instance = None
