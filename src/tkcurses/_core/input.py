"""Keyboard, mouse and resize input.

Curses input has two failure modes worth designing around: ``getch()`` blocks
by default and freezes the event loop, while ``nodelay(True)`` returns at once
and spins the CPU. Neither is acceptable in a main loop that also has timers to
service, so this module waits on the input descriptor with ``select`` and only
calls ``getch()`` once there is something to read.

Mouse decoding is separated into :class:`MouseDecoder`, which turns a curses
button mask into events without touching a terminal. Drag tracking is the
stateful part and lives there, so it can be exercised directly.
"""

from __future__ import annotations

import contextlib
import curses
import os
import select
import sys
import time
from typing import TYPE_CHECKING, Any

from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses._core.events import (
    MOD_ALT,
    MOD_CTRL,
    MOD_SHIFT,
    Event,
    KeyEvent,
    MouseEvent,
    MouseState,
    ResizeEvent,
    keysym_for,
    shift_held,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["DEFAULT_CLICK_INTERVAL", "InputHandler", "MouseDecoder", "button_masks"]

#: Milliseconds within which clicks count as a double or triple click.
#: Curses does not inherit the system's double-click timing, so a value has to
#: be chosen: 200ms balances responsiveness against missed double clicks.
DEFAULT_CLICK_INTERVAL = 200

#: Button states, most specific first. A single mask can carry several bits,
#: and a triple click also reports a click, so order decides what is reported.
_BUTTON_STATES: tuple[tuple[str, MouseState], ...] = (
    ("TRIPLE_CLICKED", "triple"),
    ("DOUBLE_CLICKED", "double"),
    ("PRESSED", "pressed"),
    ("RELEASED", "released"),
    ("CLICKED", "clicked"),
)


def button_masks(source: Any = curses) -> dict[int, dict[MouseState, int]]:
    """Collect the button masks ``source`` actually defines.

    Button 5 and some wheel masks are absent on certain platforms, so each
    name is looked up rather than assumed, and a button with no usable masks
    is left out entirely. ``source`` is a parameter so this can be checked
    against a build other than the one running the tests.
    """
    masks: dict[int, dict[MouseState, int]] = {}
    for button in range(1, 6):
        states: dict[MouseState, int] = {}
        for suffix, state in _BUTTON_STATES:
            mask = getattr(source, f"BUTTON{button}_{suffix}", 0)
            if mask:
                states[state] = mask
        if states:
            masks[button] = states
    return masks


_MASKS = button_masks()

#: Modifier bits carried alongside a mouse report.
_MODIFIER_MASKS: tuple[tuple[str, int], ...] = (
    ("BUTTON_SHIFT", MOD_SHIFT),
    ("BUTTON_CTRL", MOD_CTRL),
    ("BUTTON_ALT", MOD_ALT),
)


def decode_modifiers(bstate: int) -> int:
    """Extract modifier flags from a curses button mask."""
    modifiers = 0
    for name, flag in _MODIFIER_MASKS:
        mask = getattr(curses, name, 0)
        if mask and bstate & mask:
            modifiers |= flag
    return modifiers


class MouseDecoder:
    """Turns curses button masks into mouse events, tracking drags and clicks.

    A drag is not something curses reports: it has to be inferred from motion
    arriving while a button is known to be down, which means remembering where
    and with which button the press happened.

    Repeat clicks are counted here rather than left to ncurses. Its own click
    detection withholds a press for ``mouseinterval`` milliseconds to see what
    follows, and what it reports then depends on what that was: a press and
    release in the same cell arrive as one CLICKED, a press and a release a
    cell apart lose the release entirely, and a press followed by motion can
    lose the press. Each of those has cost this library a bug - the last of
    them twice. So ncurses is asked for raw transitions, and the counting
    happens here where the timestamps and positions are already known.
    """

    def __init__(self, click_interval: int = DEFAULT_CLICK_INTERVAL) -> None:
        """
        Args:
            click_interval: Milliseconds within which a second press in the
                same cell counts as a double click.
        """
        self._button = 0
        self._start: tuple[int, int] = (0, 0)
        self.click_interval = click_interval
        self._last_press = 0.0
        self._last_cell: tuple[int, int] = (-1, -1)
        self._repeat = 0

    @property
    def dragging(self) -> bool:
        """True while a button is held down."""
        return self._button != 0

    @property
    def drag_button(self) -> int:
        """The button being held, or 0."""
        return self._button

    def _count_click(self, x: int, y: int) -> MouseState:
        """Decide whether this press is a first, second or third click.

        A repeat has to be both soon enough and in the same cell: two presses
        far apart are two clicks however quickly they arrive.
        """
        now = time.monotonic()
        soon = (now - self._last_press) * 1000 <= self.click_interval
        self._repeat = (
            min(self._repeat + 1, 3) if soon and (x, y) == self._last_cell else 1
        )
        self._last_press = now
        self._last_cell = (x, y)
        return ("pressed", "double", "triple")[self._repeat - 1]

    def reset(self) -> None:
        """Forget any drag in progress."""
        self._button = 0
        self._start = (0, 0)

    def decode(self, x: int, y: int, bstate: int) -> list[MouseEvent]:
        """Decode one curses mouse report into events.

        Returns a list because a single report can describe more than one
        button. It is empty when the report says nothing actionable.
        """
        modifiers = decode_modifiers(bstate)
        events: list[MouseEvent] = []
        for button, states in _MASKS.items():
            event = self._decode_button(button, bstate, x, y, modifiers, states)
            if event is not None:
                events.append(event)
        if events:
            return events
        if self._button:
            # Motion with a button held is a drag, which curses does not name.
            return [
                MouseEvent(
                    x=x,
                    y=y,
                    button=self._button,
                    state="drag",
                    modifiers=modifiers,
                    drag_start=self._start,
                )
            ]
        if bstate & getattr(curses, "REPORT_MOUSE_POSITION", 0):
            return [MouseEvent(x=x, y=y, button=0, state="motion", modifiers=modifiers)]
        return []

    def _decode_button(
        self,
        button: int,
        bstate: int,
        x: int,
        y: int,
        modifiers: int,
        states: dict[MouseState, int],
    ) -> MouseEvent | None:
        """Decode the first matching state for one button."""
        for state, mask in states.items():
            if not bstate & mask:
                continue
            event = MouseEvent(
                x=x, y=y, button=button, state=state, modifiers=modifiers
            )
            if state == "pressed":
                self._button = button
                self._start = (x, y)
                event.drag_start = self._start
                event.state = self._count_click(x, y)
            elif state == "released" and self._button == button:
                event.drag_start = self._start
                event.drag_end = (x, y)
                self._button = 0
            return event
        return None


class InputHandler:
    """Reads keyboard, mouse and resize input without blocking or spinning.

    Args:
        stdscr: The curses window to read from.
        dispatcher: Serialises curses calls. Defaults to the shared one.
        click_interval: Multi-click window in milliseconds.
        stream: Descriptor to wait on. Defaults to standard input.
    """

    def __init__(
        self,
        stdscr: Any,
        *,
        dispatcher: CursesDispatcher | None = None,
        click_interval: int = DEFAULT_CLICK_INTERVAL,
        stream: Any = None,
    ) -> None:
        self._stdscr = stdscr
        self._dispatcher = dispatcher or CursesDispatcher.get()
        self._stream = stream if stream is not None else sys.stdin
        self._decoder = MouseDecoder(click_interval)
        self._mouse_available = False
        self._click_interval = click_interval
        self._configure()

    def _configure(self) -> None:
        """Put curses into the mode this handler expects."""
        self._dispatcher.call(self._stdscr.keypad, True)
        self._dispatcher.call(curses.noecho)
        self._dispatcher.call(curses.cbreak)
        # select() does the waiting, so getch() must never block.
        self._dispatcher.call(self._stdscr.nodelay, True)
        self._enable_mouse()

    def _enable_mouse(self) -> None:
        """Ask for mouse reporting, tolerating terminals that refuse."""
        try:
            available, _ = self._dispatcher.call(
                curses.mousemask,
                curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION,
            )
        except curses.error:
            self._mouse_available = False
            return
        self._mouse_available = bool(available)
        if self._mouse_available:
            # Zero, so ncurses reports raw button transitions and never
            # withholds one while it works out what kind of click it was.
            # MouseDecoder does the counting; its docstring says what
            # ncurses' own version cost.
            self._dispatcher.call(curses.mouseinterval, 0)

    # ------------------------------------------------------------- state

    @property
    def mouse_available(self) -> bool:
        """True if the terminal reported mouse support."""
        return self._mouse_available

    @property
    def decoder(self) -> MouseDecoder:
        """The mouse decoder, exposed for drag state."""
        return self._decoder

    @property
    def click_interval(self) -> int:
        """Multi-click window in milliseconds.

        Ours, not curses'. ncurses is held at ``mouseinterval(0)`` so that it
        reports raw transitions; this is the window MouseDecoder measures a
        repeat click against. It could not be read back from curses in any
        case: Python's ``mouseinterval()`` returns None rather than the
        previous value the C API gives.
        """
        return self._click_interval

    @click_interval.setter
    def click_interval(self, milliseconds: int) -> None:
        if milliseconds < 0:
            raise ValueError(f"click interval must not be negative: {milliseconds}")
        self._click_interval = milliseconds
        # The decoder's window, never curses': handing this to ncurses would
        # put its click detection back, and with it the swallowed presses and
        # releases the decoder exists to avoid.
        self._decoder.click_interval = milliseconds

    # -------------------------------------------------------------- input

    def wait_for_input(self, timeout_ms: int = 50) -> bool:
        """Wait up to ``timeout_ms`` for input. True if any arrived.

        This is what keeps the loop off the CPU while idle, and what bounds
        how long timers wait to be serviced.
        """
        if timeout_ms < 0:
            raise ValueError(f"timeout must not be negative: {timeout_ms}")
        try:
            readable, _, _ = select.select([self._stream], [], [], timeout_ms / 1000)
        except (OSError, ValueError):
            # The descriptor was closed underneath us, during shutdown.
            return False
        return bool(readable)

    def poll(self) -> list[Event]:
        """Read every event currently available, without blocking.

        Always a list: one curses report can describe several buttons, and a
        caller that has to handle both a single event and a list of them gets
        the distinction wrong eventually.
        """
        events: list[Event] = []
        while True:
            code = self._dispatcher.call(self._stdscr.getch)
            if code == curses.ERR:
                return events
            events.extend(self._translate(code))

    def next_event(self, timeout_ms: int = 50) -> Event | None:
        """Wait for and return one event, or None if nothing arrived."""
        if not self.wait_for_input(timeout_ms):
            return None
        events = self.poll()
        return events[0] if events else None

    def _translate(self, code: int) -> Sequence[Event]:
        """Turn one key code into the events it represents."""
        if code == curses.KEY_MOUSE:
            return self._read_mouse()
        if code == curses.KEY_RESIZE:
            return [self._read_resize()]
        return [self._key_event(code)]

    def _read_mouse(self) -> Sequence[Event]:
        """Pull the pending mouse report and decode it."""
        try:
            _, x, y, _, bstate = self._dispatcher.call(curses.getmouse)
        except curses.error:
            # The report was consumed or malformed; nothing to deliver.
            return []
        return self._decoder.decode(x, y, bstate)

    def _read_resize(self) -> ResizeEvent:
        """Apply a terminal resize and describe it.

        ``update_lines_cols()`` leaves the dimensions stale, so the size is
        taken from the terminal itself and applied with ``resize_term()``.
        """
        size = os.get_terminal_size()
        with contextlib.suppress(curses.error):
            self._dispatcher.call(curses.resize_term, size.lines, size.columns)
        return ResizeEvent(width=size.columns, height=size.lines)

    def _key_event(self, code: int) -> KeyEvent:
        """Build a key event, including any modifier the code implies."""
        modifiers = 0
        char = ""
        if 1 <= code <= 26:
            # Control-A through Control-Z arrive as 1..26. Tab, Return and
            # Escape fall in that range too but are keys in their own right.
            if code not in (9, 10, 13):
                modifiers |= MOD_CTRL
        elif 32 <= code <= 126:
            char = chr(code)
        if shift_held(code):
            modifiers |= MOD_SHIFT
        return KeyEvent(
            keycode=code,
            keysym=keysym_for(code),
            char=char,
            modifiers=modifiers,
        )
