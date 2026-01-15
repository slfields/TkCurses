"""Input handling for TkCurses internals.

Provides efficient, non-blocking input handling using select-based
waiting. Handles keyboard input, mouse events (including drag),
and terminal resize events.

The InputHandler class is the primary interface for all input
operations in TkCurses. It translates raw curses input into
higher-level event objects compatible with tkinter-style event
handling.
"""

from __future__ import annotations

import curses
import select
import sys
from typing import TYPE_CHECKING

from .events import (
    Event,
    KeyEvent,
    MouseEvent,
    ResizeEvent,
    MOD_SHIFT,
    MOD_CTRL,
    MOD_ALT,
)

if TYPE_CHECKING:
    from .config import TkCursesConfig


# Tkinter-style keysym mapping for curses key codes
KEY_MAP: dict[int, str] = {
    curses.KEY_UP: 'Up',
    curses.KEY_DOWN: 'Down',
    curses.KEY_LEFT: 'Left',
    curses.KEY_RIGHT: 'Right',
    curses.KEY_HOME: 'Home',
    curses.KEY_END: 'End',
    curses.KEY_PPAGE: 'Prior',      # Page Up
    curses.KEY_NPAGE: 'Next',       # Page Down
    curses.KEY_IC: 'Insert',
    curses.KEY_DC: 'Delete',
    curses.KEY_BACKSPACE: 'BackSpace',
    curses.KEY_ENTER: 'Return',
    10: 'Return',                    # Enter key (LF)
    13: 'Return',                    # Carriage return
    27: 'Escape',
    9: 'Tab',
    curses.KEY_BTAB: 'Shift-Tab',
    curses.KEY_F1: 'F1',
    curses.KEY_F2: 'F2',
    curses.KEY_F3: 'F3',
    curses.KEY_F4: 'F4',
    curses.KEY_F5: 'F5',
    curses.KEY_F6: 'F6',
    curses.KEY_F7: 'F7',
    curses.KEY_F8: 'F8',
    curses.KEY_F9: 'F9',
    curses.KEY_F10: 'F10',
    curses.KEY_F11: 'F11',
    curses.KEY_F12: 'F12',
    127: 'BackSpace',                # DEL character (alternate backspace)
    curses.KEY_SHOME: 'Shift-Home',
    curses.KEY_SEND: 'Shift-End',
    curses.KEY_SLEFT: 'Shift-Left',
    curses.KEY_SRIGHT: 'Shift-Right',
}


def _build_button_masks() -> dict[int, dict[str, int]]:
    """Build button event masks for all mouse buttons.

    Returns a dictionary mapping button numbers (1-5) to their
    curses event masks for each state (pressed, released, clicked,
    double, triple).

    Returns:
        Dictionary mapping button number to state-to-mask mapping.
    """
    return {
        1: {
            'pressed': curses.BUTTON1_PRESSED,
            'released': curses.BUTTON1_RELEASED,
            'clicked': curses.BUTTON1_CLICKED,
            'double': curses.BUTTON1_DOUBLE_CLICKED,
            'triple': curses.BUTTON1_TRIPLE_CLICKED,
        },
        2: {
            'pressed': curses.BUTTON2_PRESSED,
            'released': curses.BUTTON2_RELEASED,
            'clicked': curses.BUTTON2_CLICKED,
            'double': curses.BUTTON2_DOUBLE_CLICKED,
            'triple': curses.BUTTON2_TRIPLE_CLICKED,
        },
        3: {
            'pressed': curses.BUTTON3_PRESSED,
            'released': curses.BUTTON3_RELEASED,
            'clicked': curses.BUTTON3_CLICKED,
            'double': curses.BUTTON3_DOUBLE_CLICKED,
            'triple': curses.BUTTON3_TRIPLE_CLICKED,
        },
        4: {
            'pressed': curses.BUTTON4_PRESSED,
            'released': curses.BUTTON4_RELEASED,
            'clicked': curses.BUTTON4_CLICKED,
            'double': curses.BUTTON4_DOUBLE_CLICKED,
            'triple': curses.BUTTON4_TRIPLE_CLICKED,
        },
        # Button 5 may not be available on all platforms
        5: {
            'pressed': getattr(curses, 'BUTTON5_PRESSED', 0),
            'released': getattr(curses, 'BUTTON5_RELEASED', 0),
            'clicked': getattr(curses, 'BUTTON5_CLICKED', 0),
            'double': getattr(curses, 'BUTTON5_DOUBLE_CLICKED', 0),
            'triple': getattr(curses, 'BUTTON5_TRIPLE_CLICKED', 0),
        },
    }


BUTTON_MASKS = _build_button_masks()


class InputHandler:
    """Handles all keyboard and mouse input for TkCurses.

    Uses select-based waiting for efficient non-blocking input handling.
    Translates raw curses events into higher-level Event objects
    compatible with tkinter-style event handling.

    Attributes:
        mouse_available: Whether mouse support is available.

    Example:
        >>> import curses
        >>> def main(stdscr):
        ...     handler = InputHandler(stdscr)
        ...     while True:
        ...         if handler.wait_for_input(timeout_ms=50):
        ...             event = handler.get_event()
        ...             if event:
        ...                 print(f"Got event: {event}")
        >>> curses.wrapper(main)
    """

    def __init__(
        self,
        stdscr: curses.window,
        config: TkCursesConfig | None = None,
    ) -> None:
        """Initialize the input handler.

        Args:
            stdscr: The curses window to capture input from.
            config: Optional configuration. If None, uses default settings.
        """
        self._stdscr = stdscr
        self._config = config

        # Drag state tracking
        self._drag_button: int = 0         # Currently pressed button (0 = none)
        self._drag_start: tuple[int, int] = (0, 0)  # Drag start position

        # Mouse availability
        self.mouse_available: bool = False

        # Apply configuration and set up input
        self._setup_input()

    def _setup_input(self) -> None:
        """Configure curses for comprehensive input capture."""
        # Get configuration values or use defaults
        if self._config:
            keypad_enabled = self._config.input.keypad
            mouse_enabled = self._config.mouse.enabled
            click_interval = self._config.mouse.click_interval
            report_motion = self._config.mouse.report_motion
            escape_delay = self._config.input.escape_delay
        else:
            keypad_enabled = True
            mouse_enabled = True
            click_interval = 200
            report_motion = True
            escape_delay = 25

        # Enable keypad mode for special keys (arrows, F1-F12, etc.)
        self._stdscr.keypad(keypad_enabled)

        # Don't echo input characters
        curses.noecho()

        # React to keys immediately (no line buffering)
        curses.cbreak()

        # Make getch() non-blocking (we use select for waiting)
        self._stdscr.nodelay(True)

        # Set escape delay (affects Alt+key detection)
        try:
            curses.set_escdelay(escape_delay)
        except AttributeError:
            pass  # Not available on all platforms

        # Set up mouse input if enabled
        if mouse_enabled:
            self._setup_mouse(click_interval, report_motion)

    def _setup_mouse(self, click_interval: int, report_motion: bool) -> None:
        """Enable comprehensive mouse event capture.

        Args:
            click_interval: Milliseconds for multi-click detection.
            report_motion: Whether to report mouse motion events.
        """
        # Build mouse mask
        mouse_mask = curses.ALL_MOUSE_EVENTS
        if report_motion:
            mouse_mask |= curses.REPORT_MOUSE_POSITION

        # Enable mouse events
        available, _ = curses.mousemask(mouse_mask)

        if not available and report_motion:
            # Fallback: try without motion reporting
            available, _ = curses.mousemask(curses.ALL_MOUSE_EVENTS)

        self.mouse_available = bool(available)

        # Configure click timing for double/triple click detection
        if self.mouse_available:
            curses.mouseinterval(max(1, min(1000, click_interval)))

    def wait_for_input(self, timeout_ms: int | None = None) -> bool:
        """Wait for input efficiently without CPU spinning.

        Uses select.select() to wait for stdin to become readable,
        allowing efficient idle waiting without burning CPU cycles.

        Args:
            timeout_ms: Maximum wait time in milliseconds. If None,
                uses config.input.poll_timeout (default 50ms).

        Returns:
            True if input is available, False if timeout expired.

        Example:
            >>> if handler.wait_for_input(timeout_ms=100):
            ...     event = handler.get_event()
        """
        if timeout_ms is None:
            if self._config:
                timeout_ms = self._config.input.poll_timeout
            else:
                timeout_ms = 50

        timeout_sec = timeout_ms / 1000.0
        readable, _, _ = select.select([sys.stdin], [], [], timeout_sec)
        return bool(readable)

    def get_event(self) -> Event | list[Event] | None:
        """Get next input event (non-blocking).

        Reads from curses and translates the raw input into a
        higher-level Event object. May return a list of MouseEvents
        if multiple button states are detected simultaneously.

        Returns:
            Event object, list of Events, or None if no input available.

        Example:
            >>> event = handler.get_event()
            >>> if isinstance(event, KeyEvent):
            ...     print(f"Key pressed: {event.keysym}")
            >>> elif isinstance(event, MouseEvent):
            ...     print(f"Mouse {event.state} at ({event.x}, {event.y})")
        """
        ch = self._stdscr.getch()

        if ch == curses.ERR:
            return None  # No input available

        if ch == curses.KEY_MOUSE:
            return self._handle_mouse()

        if ch == curses.KEY_RESIZE:
            return self._handle_resize()

        return self._handle_key(ch)

    def _handle_mouse(self) -> MouseEvent | list[MouseEvent] | None:
        """Decode mouse event from curses with full state tracking.

        Handles all mouse button states including pressed, released,
        clicked, double-click, triple-click, drag, and motion.

        Returns:
            MouseEvent, list of MouseEvents, or None on error.
        """
        try:
            _, x, y, _, bstate = curses.getmouse()
        except curses.error:
            return None

        events: list[MouseEvent] = []
        modifiers = self._decode_modifiers(bstate)

        # Check each button for all possible states
        for button in range(1, 6):
            event = self._decode_button_event(button, bstate, x, y, modifiers)
            if event:
                events.append(event)

        # Handle motion during drag (button held but no new button event)
        if not events and self._drag_button != 0:
            events.append(MouseEvent(
                x=x, y=y,
                button=self._drag_button,
                state='drag',
                drag_start=self._drag_start,
                modifiers=modifiers,
            ))

        # Handle pure motion (no button pressed)
        if not events and (bstate & curses.REPORT_MOUSE_POSITION):
            events.append(MouseEvent(
                x=x, y=y,
                button=0,
                state='motion',
                modifiers=modifiers,
            ))

        if len(events) == 1:
            return events[0]
        elif events:
            return events
        return None

    def _decode_button_event(
        self,
        button: int,
        bstate: int,
        x: int,
        y: int,
        modifiers: int,
    ) -> MouseEvent | None:
        """Decode event for a specific button.

        Checks the bstate mask against all possible states for the
        given button and returns the appropriate MouseEvent.

        Args:
            button: Button number (1-5).
            bstate: Raw button state from curses.getmouse().
            x: Column position.
            y: Row position.
            modifiers: Modifier flags.

        Returns:
            MouseEvent if button has an event, None otherwise.
        """
        masks = BUTTON_MASKS.get(button, {})

        # Check each state in priority order (most specific first)
        for state in ('triple', 'double', 'clicked', 'released', 'pressed'):
            mask = masks.get(state, 0)
            if mask and (bstate & mask):
                event = MouseEvent(
                    x=x, y=y,
                    button=button,
                    state=state,
                    modifiers=modifiers,
                )

                # Track drag state
                if state == 'pressed':
                    self._drag_button = button
                    self._drag_start = (x, y)
                    event.drag_start = self._drag_start
                elif state == 'released':
                    if self._drag_button == button:
                        event.drag_start = self._drag_start
                        event.drag_end = (x, y)
                        self._drag_button = 0
                elif state in ('clicked', 'double', 'triple'):
                    # Click events also clear drag state
                    if self._drag_button == button:
                        self._drag_button = 0

                return event

        return None

    def _decode_modifiers(self, bstate: int) -> int:
        """Extract modifier keys from mouse button state.

        Args:
            bstate: Raw button state from curses.getmouse().

        Returns:
            Combined modifier flags (MOD_SHIFT, MOD_CTRL, MOD_ALT).
        """
        modifiers = 0
        if bstate & curses.BUTTON_SHIFT:
            modifiers |= MOD_SHIFT
        if bstate & curses.BUTTON_CTRL:
            modifiers |= MOD_CTRL
        if bstate & curses.BUTTON_ALT:
            modifiers |= MOD_ALT
        return modifiers

    def _handle_resize(self) -> ResizeEvent:
        """Handle terminal resize event.

        Updates curses internal dimensions and returns a ResizeEvent
        with the new terminal size.

        Returns:
            ResizeEvent with new width and height.
        """
        curses.update_lines_cols()
        return ResizeEvent(
            width=curses.COLS,
            height=curses.LINES,
        )

    def _handle_key(self, ch: int) -> KeyEvent:
        """Translate key code to KeyEvent.

        Converts raw curses key codes into tkinter-style KeyEvents
        with keysym, char, and modifier information.

        Args:
            ch: Raw character/key code from curses.getch().

        Returns:
            KeyEvent with translated key information.
        """
        return KeyEvent(
            keycode=ch,
            keysym=self._keycode_to_keysym(ch),
            char=chr(ch) if 32 <= ch <= 126 else '',
            modifiers=self._detect_key_modifiers(ch),
        )

    def _detect_key_modifiers(self, ch: int) -> int:
        """Detect modifier keys from key code.

        Curses has limited modifier detection. Ctrl+key produces
        codes 1-26 (Ctrl+A=1, Ctrl+Z=26). Alt+key typically produces
        escape sequences which are handled separately.

        Args:
            ch: Raw character/key code.

        Returns:
            Modifier flags.
        """
        modifiers = 0
        # Ctrl+key produces codes 1-26 (Ctrl+A=1, Ctrl+Z=26)
        if 1 <= ch <= 26:
            modifiers |= MOD_CTRL
        return modifiers

    def _keycode_to_keysym(self, ch: int) -> str:
        """Map curses key code to tkinter-style keysym.

        Translates raw curses key codes into human-readable key
        symbols that match tkinter's keysym naming convention.

        Args:
            ch: Raw character/key code from curses.getch().

        Returns:
            Tkinter-style key symbol string.

        Example:
            >>> handler._keycode_to_keysym(curses.KEY_UP)
            'Up'
            >>> handler._keycode_to_keysym(ord('a'))
            'a'
            >>> handler._keycode_to_keysym(1)  # Ctrl+A
            'Control-a'
        """
        # Check predefined mappings first
        if ch in KEY_MAP:
            return KEY_MAP[ch]

        # Printable ASCII characters
        if 32 <= ch <= 126:
            return chr(ch)

        # Ctrl+key combinations (1-26)
        if 1 <= ch <= 26:
            return f'Control-{chr(ch + 96)}'  # 1 -> 'a', 26 -> 'z'

        # Unknown key code
        return f'keycode-{ch}'

    def configure_mouse(self, click_interval: int | None = None) -> int:
        """Configure mouse behavior.

        Allows runtime adjustment of mouse click timing for
        double/triple click detection.

        Args:
            click_interval: Max milliseconds between clicks for
                multi-click detection (1-1000). None to query
                current value without changing it.

        Returns:
            Current click interval setting.

        Example:
            >>> handler.configure_mouse(click_interval=300)
            300
            >>> handler.configure_mouse()  # Query current
            300
        """
        if click_interval is not None:
            # Validate and clamp range
            click_interval = max(1, min(1000, click_interval))
            curses.mouseinterval(click_interval)
            if self._config:
                self._config.mouse.click_interval = click_interval
            return click_interval

        # Return current value
        if self._config:
            return self._config.mouse.click_interval
        return 200  # Default

    def cleanup(self) -> None:
        """Clean up input handler state.

        Resets drag tracking and restores terminal input mode.
        Called automatically when the application exits.
        """
        self._drag_button = 0
        self._drag_start = (0, 0)
