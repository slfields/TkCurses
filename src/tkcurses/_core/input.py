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
import termios
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
    modified_key,
    shift_held,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

__all__ = [
    "DEFAULT_CLICK_INTERVAL",
    "SIGNAL_KEYS",
    "InputHandler",
    "MouseDecoder",
    "button_masks",
]

#: The keys a tty turns into a signal before the application can read them,
#: and the control character each one occupies. Keysyms, so that they can be
#: compared against a binding's detail directly: Control-C reports keysym
#: ``c``, and Control-backslash reports ``\\``, as they do in Tk.
SIGNAL_KEYS: dict[str, int] = {
    "c": termios.VINTR,  # interrupt
    "\\": termios.VQUIT,  # quit
    "z": termios.VSUSP,  # suspend
}

#: What a control character is set to when it is to do nothing. POSIX names
#: it _POSIX_VDISABLE; Python exposes it, but only on some platforms, and
#: fpathconf can also answer per file descriptor. Zero is the value on every
#: platform this library runs on, and is the documented fallback.
_VDISABLE: int = getattr(termios, "_POSIX_VDISABLE", 0)

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
        position = bool(bstate & getattr(curses, "REPORT_MOUSE_POSITION", 0))
        # Motion while a button is held is a drag, and curses has no name for
        # one. It has to be decided before the button masks are looked at:
        # some ncurses builds report a drag as REPORT_MOUSE_POSITION *and*
        # the button's own pressed bit, and reading that as another press
        # would re-anchor the selection at every step of the drag - so a drag
        # would select nothing at all, while press and release looked fine.
        if position and self._button:
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
        events: list[MouseEvent] = []
        for button, states in _MASKS.items():
            event = self._decode_button(button, bstate, x, y, modifiers, states)
            if event is not None:
                events.append(event)
        if events:
            return events
        if self._button:
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
        if position:
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
        report_motion: bool = True,
        report_hover: bool = False,
    ) -> None:
        self._stdscr = stdscr
        self._dispatcher = dispatcher or CursesDispatcher.get()
        self._stream = stream if stream is not None else sys.stdin
        self._decoder = MouseDecoder(click_interval)
        self._mouse_available = False
        self._click_interval = click_interval
        self._report_motion = report_motion
        self._report_hover = report_hover
        self._motion_mode = b""
        self._saved_termios: tuple[int, list[Any]] | None = None
        #: Keysyms taken back from the tty's signal handling, by request.
        self._signal_keys: set[str] = set()
        self._configure()

    def _configure(self) -> None:
        """Put curses into the mode this handler expects."""
        self._dispatcher.call(self._stdscr.keypad, True)
        self._dispatcher.call(curses.noecho)
        self._dispatcher.call(curses.cbreak)
        # select() does the waiting, so getch() must never block.
        self._dispatcher.call(self._stdscr.nodelay, True)
        self._disable_flow_control()
        self._enable_mouse()

    def _disable_flow_control(self) -> None:
        """Take the tty's own keys back, as far as the application needs.

        Control-S and Control-Q are XOFF and XON: the line discipline uses
        them to pause and resume output and never passes either on, so an
        application that binds Control-Q - as a menu with a Ctrl+Q
        accelerator invites - never sees the key at all. Those two are taken
        back for everyone, because nothing is lost by it.

        Control-C, Control-backslash and Control-Z are a different matter:
        they are interrupt, quit and suspend, and giving one up costs a way
        of stopping a wedged application. Those are taken back one at a time,
        only while something is bound to them - see :meth:`claim_signal_keys`.
        curses' raw() would clear all five at once, which is why it is not
        used here.
        """
        stream = sys.__stdin__
        if stream is None:
            return
        try:
            fd = stream.fileno()
            saved = termios.tcgetattr(fd)
        except (termios.error, ValueError, OSError, AttributeError):
            return
        self._saved_termios = (fd, saved)
        self._apply_termios()

    def claim_signal_keys(self, keysyms: Iterable[str]) -> set[str]:
        """Stop the tty turning these keys into signals, and pass them on.

        Args:
            keysyms: The keysyms wanted, from :data:`SIGNAL_KEYS`. Anything
                else is ignored, and the set replaces whatever was claimed
                before - so a key no longer wanted gets its signal back.

        Returns:
            The keysyms now claimed.

        Only the keys asked for are given up. An application that binds
        Control-C keeps Control-backslash, which still kills it from the
        keyboard if it stops responding - and that mattered enough to do
        this per key rather than by clearing ISIG, which would take all
        three at once.
        """
        wanted = {key for key in keysyms if key in SIGNAL_KEYS}
        if wanted == self._signal_keys:
            return set(wanted)
        self._signal_keys = wanted
        self._apply_termios()
        return set(wanted)

    @property
    def signal_keys(self) -> set[str]:
        """The keysyms currently taken back from the tty's signal handling."""
        return set(self._signal_keys)

    def _apply_termios(self) -> None:
        """Write the tty settings this handler wants, over the saved ones.

        Always built from the state found at start-up rather than from what
        is there now, so claiming a key and letting it go again puts back
        exactly what the terminal had - including a control character the
        person had rebound for themselves.
        """
        if self._saved_termios is None:
            return
        fd, saved = self._saved_termios
        attributes = list(saved)
        attributes[0] &= ~(termios.IXON | termios.IXOFF | termios.IXANY)
        control = list(attributes[6])
        for keysym in self._signal_keys:
            control[SIGNAL_KEYS[keysym]] = _VDISABLE
        attributes[6] = control
        with contextlib.suppress(termios.error, OSError):
            termios.tcsetattr(fd, termios.TCSANOW, attributes)

    def _restore_flow_control(self) -> None:
        """Put the tty's own keys back the way they were found."""
        if self._saved_termios is None:
            return
        fd, saved = self._saved_termios
        self._saved_termios = None
        self._signal_keys = set()
        with contextlib.suppress(termios.error, OSError, ValueError):
            termios.tcsetattr(fd, termios.TCSANOW, saved)

    def restore(self) -> None:
        """Undo everything this handler did to the terminal."""
        self.disable_mouse()
        self._restore_flow_control()

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
            self._enable_motion()

    def _enable_motion(self) -> None:
        """Ask the terminal itself to report the mouse moving.

        ncurses will not. ``mousemask`` accepts REPORT_MOUSE_POSITION and
        reports it granted, but the only thing it sends the terminal is
        ``ESC [ ? 1006 ; 1000 h`` - SGR encoding and *normal* tracking, which
        is press and release and nothing else. Its built-in xterm string
        hard-codes 1000, and only a terminfo entry with an ``XM`` capability
        of its own would change that.

        So the mode is set here. 1002 reports motion while a button is held,
        which is what a drag is; 1003 reports every movement, which is what
        hovering needs and what floods an application that does not. Written
        through ncurses' own output so it cannot overtake what curses has
        buffered.
        """
        if self._report_hover:
            self._motion_mode = b"\x1b[?1003h"
        elif self._report_motion:
            self._motion_mode = b"\x1b[?1002h"
        else:
            return
        self.enable_motion()

    def enable_motion(self) -> bool:
        """Write the motion mode to the terminal. True if it was written.

        Straight to the terminal's file descriptor, not through putp. ncurses
        sends its own ``1006;1000h`` through its output buffer, and a mode
        written into that buffer is at the mercy of when it is flushed and of
        anything ncurses decides to write afterwards - so the screen is
        flushed first and ours goes out last, where nothing can overtake it.

        Safe to call more than once, and worth doing: a single mode string
        lost during startup is the difference between drags working and a
        terminal that never reports them.
        """
        if not self._motion_mode:
            return False
        with contextlib.suppress(curses.error):
            self._dispatcher.call(curses.doupdate)
        return self._write_to_terminal(self._motion_mode)

    @staticmethod
    def _write_to_terminal(data: bytes) -> bool:
        """Put bytes on the terminal itself, past any buffering."""
        stream = sys.__stdout__
        if stream is None:
            return False
        try:
            os.write(stream.fileno(), data)
        except (OSError, ValueError):
            return False
        return True

    def disable_mouse(self) -> None:
        """Stop the terminal reporting the mouse, on the way out.

        A terminal left in 1002 or 1003 goes on sending mouse reports to
        whatever runs next, which sees them as garbage input.
        """
        if not self._motion_mode:
            return
        self._motion_mode = b""
        self._write_to_terminal(b"\x1b[?1003l\x1b[?1002l")

    # ------------------------------------------------------------- state

    @property
    def motion_mode(self) -> bytes:
        """The motion mode this handler asked the terminal for, if any."""
        return self._motion_mode

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
        if code == 0 or 28 <= code <= 31:
            # NUL is Control-Space, and 28 to 31 are Control with the four
            # keys past Z: backslash, bracketright, asciicircum, underscore.
            modifiers |= MOD_CTRL
        elif 1 <= code <= 26:
            # Control-A through Control-Z arrive as 1..26. Tab, Return and
            # Escape fall in that range too but are keys in their own right.
            if code not in (9, 10, 13):
                modifiers |= MOD_CTRL
        elif 32 <= code <= 126:
            char = chr(code)
        if shift_held(code):
            modifiers |= MOD_SHIFT
        modified = modified_key(code)
        if modified is not None:
            modifiers |= modified[1]
        return KeyEvent(
            keycode=code,
            keysym=keysym_for(code),
            char=char,
            modifiers=modifiers,
        )
