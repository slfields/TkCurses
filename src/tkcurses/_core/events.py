"""Input events: keyboard, mouse, and terminal resize.

These are the internal representation produced by
:mod:`tkcurses._core.input` and consumed by the widget layer, which converts
them into tkinter-style ``Event`` objects for binding callbacks.

Translation from curses key codes to tkinter keysyms lives here rather than in
the input handler, because it is pure data: it needs no terminal, so it can be
tested directly and reused by anything that has a key code in hand.
"""

from __future__ import annotations

import curses
import time
from dataclasses import dataclass, field
from typing import Literal

__all__ = [
    "MOD_ALT",
    "MOD_CTRL",
    "MOD_META",
    "MOD_SHIFT",
    "Event",
    "KeyEvent",
    "MouseEvent",
    "MouseState",
    "ResizeEvent",
    "keysym_for",
    "modifier_names",
    "shift_held",
]

# --------------------------------------------------------------------------
# Modifier flags, combinable with bitwise OR
# --------------------------------------------------------------------------
MOD_SHIFT = 0x01
MOD_CTRL = 0x02
MOD_ALT = 0x04
MOD_META = 0x08  # Command on macOS

_MODIFIER_NAMES: tuple[tuple[int, str], ...] = (
    (MOD_SHIFT, "Shift"),
    (MOD_CTRL, "Control"),
    (MOD_ALT, "Alt"),
    (MOD_META, "Meta"),
)

#: The states a mouse event can carry.
MouseState = Literal[
    "pressed", "released", "clicked", "double", "triple", "drag", "motion"
]


def modifier_names(modifiers: int) -> tuple[str, ...]:
    """Names of the modifiers set in ``modifiers``, in binding order.

    The order matters: tkinter binding strings are written ``<Control-Alt-x>``,
    so the names are emitted in a fixed sequence rather than set order.
    """
    return tuple(name for flag, name in _MODIFIER_NAMES if modifiers & flag)


@dataclass
class Event:
    """Base class for input events."""

    type: str = "event"
    time: float = field(default_factory=time.time)


@dataclass
class KeyEvent(Event):
    """A key press.

    Attributes:
        keycode: The raw value returned by ``getch()``.
        keysym: tkinter-style name, such as ``Up``, ``Return``, or ``a``.
        char: The printable character, empty for keys that produce none.
        modifiers: Bitwise OR of the ``MOD_*`` flags.
    """

    type: str = "key"
    keycode: int = 0
    keysym: str = ""
    char: str = ""
    modifiers: int = 0

    @property
    def is_printable(self) -> bool:
        """True if this key produced a character that can be inserted."""
        return bool(self.char)


@dataclass
class MouseEvent(Event):
    """A mouse action, including drag tracking.

    Attributes:
        x: Column, in cells.
        y: Row, in cells.
        button: 1 left, 2 middle, 3 right, 4 scroll up, 5 scroll down.
        state: What the button did; see :data:`MouseState`.
        modifiers: Bitwise OR of the ``MOD_*`` flags.
        drag_start: Where a drag began, once one is in progress.
        drag_end: Where a drag finished, set on release.
    """

    type: str = "mouse"
    x: int = 0
    y: int = 0
    button: int = 0
    state: MouseState = "pressed"
    modifiers: int = 0
    drag_start: tuple[int, int] | None = None
    drag_end: tuple[int, int] | None = None

    @property
    def position(self) -> tuple[int, int]:
        """Current position as ``(x, y)``."""
        return self.x, self.y

    @property
    def is_scroll(self) -> bool:
        """True for wheel events, which curses reports as buttons 4 and 5."""
        return self.button in (4, 5)


@dataclass
class ResizeEvent(Event):
    """The terminal changed size.

    Attributes:
        width: New column count.
        height: New row count.
    """

    type: str = "resize"
    width: int = 0
    height: int = 0

    @property
    def size(self) -> tuple[int, int]:
        """New size as ``(width, height)``."""
        return self.width, self.height


# --------------------------------------------------------------------------
# Key code translation
# --------------------------------------------------------------------------

#: Control characters that have their own tkinter keysym.
_CONTROL_KEYSYMS: dict[int, str] = {
    0: "space",  # Control-Space arrives as NUL
    9: "Tab",
    10: "Return",  # line feed, what the tty delivers for Enter
    13: "Return",  # carriage return
    27: "Escape",
    127: "BackSpace",
}

#: Curses key codes that map to a named tkinter keysym.
_SPECIAL_KEYSYMS: dict[int, str] = {
    curses.KEY_UP: "Up",
    curses.KEY_DOWN: "Down",
    curses.KEY_LEFT: "Left",
    curses.KEY_RIGHT: "Right",
    curses.KEY_HOME: "Home",
    curses.KEY_END: "End",
    curses.KEY_PPAGE: "Prior",  # Page Up
    curses.KEY_NPAGE: "Next",  # Page Down
    curses.KEY_IC: "Insert",
    curses.KEY_DC: "Delete",
    curses.KEY_BACKSPACE: "BackSpace",
    curses.KEY_ENTER: "Return",
    curses.KEY_BTAB: "ISO_Left_Tab",  # what X11 and tkinter call Shift-Tab
    curses.KEY_MOUSE: "Mouse",
    curses.KEY_RESIZE: "Configure",
}

#: Curses key codes that are a named key *with Shift held*. ncurses decodes
#: the terminal's modified-arrow sequences into these - Shift-Down arrives as
#: KEY_SF, Shift-Up as KEY_SR, from terminfo's kind and kri - so a shifted
#: arrow is one code here rather than a modifier alongside the plain one.
#: Without this table, selecting with the keyboard could not work at all:
#: Shift-Right was indistinguishable from Right.
_SHIFTED_KEYSYMS: dict[int, str] = {
    curses.KEY_SLEFT: "Left",
    curses.KEY_SRIGHT: "Right",
    # Scroll-forward and scroll-reverse, which is what terminfo calls the
    # shifted vertical arrows.
    curses.KEY_SF: "Down",
    curses.KEY_SR: "Up",
    curses.KEY_SHOME: "Home",
    curses.KEY_SEND: "End",
    curses.KEY_SPREVIOUS: "Prior",
    curses.KEY_SNEXT: "Next",
    curses.KEY_SDC: "Delete",
    curses.KEY_SIC: "Insert",
}


def shift_held(keycode: int) -> bool:
    """True if a key code is the shifted form of a named key."""
    return keycode in _SHIFTED_KEYSYMS


def keysym_for(keycode: int) -> str:
    """Return the tkinter-style keysym for a curses key code.

    Printable ASCII maps to itself, control characters and curses' named keys
    map to their tkinter names, and function keys are derived from ``KEY_F0``
    so that all 64 of them work rather than only the twelve worth listing.
    Anything unrecognised is reported as ``keycode-N``, which keeps an
    unknown terminal's key visible in bindings instead of silently dropped.
    """
    if keycode in _SPECIAL_KEYSYMS:
        return _SPECIAL_KEYSYMS[keycode]
    if keycode in _SHIFTED_KEYSYMS:
        return _SHIFTED_KEYSYMS[keycode]
    if 0 <= keycode - curses.KEY_F0 <= 63:
        return f"F{keycode - curses.KEY_F0}"
    if keycode in _CONTROL_KEYSYMS:
        return _CONTROL_KEYSYMS[keycode]
    if 1 <= keycode <= 26:
        # Control-A through Control-Z arrive as 1..26.
        return chr(keycode + 96)
    if keycode == 32:
        return "space"  # tkinter names the space bar, it does not use " "
    if 33 <= keycode <= 126:
        return chr(keycode)
    return f"keycode-{keycode}"
