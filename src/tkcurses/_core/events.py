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
    "PUNCTUATION_KEYSYMS",
    "Event",
    "KeyEvent",
    "MouseEvent",
    "MouseState",
    "ResizeEvent",
    "canonical_keysym",
    "keysym_for",
    "modified_key",
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

#: X11's names for the punctuation keys, and the characters they produce.
#: Tk resolves these when it parses a binding, so ``<Key-period>`` is how a
#: full stop is bound and ``<Key-.>`` is not - the name is the spelling every
#: piece of tkinter documentation uses. Everything here keeps the character
#: as the canonical form, because that is what Tk 9.0.2 reports back in
#: ``event.keysym`` for the same key; the names are resolved to it rather
#: than the other way round, so a binding written either way finds the same
#: event. Space is the exception Tk itself makes: it is named, not literal,
#: because a bare space in a sequence cannot be told from a separator.
PUNCTUATION_KEYSYMS: dict[str, str] = {
    "space": " ",
    "exclam": "!",
    "quotedbl": '"',
    "numbersign": "#",
    "dollar": "$",
    "percent": "%",
    "ampersand": "&",
    "apostrophe": "'",
    "quoteright": "'",
    "parenleft": "(",
    "parenright": ")",
    "asterisk": "*",
    "plus": "+",
    "comma": ",",
    "minus": "-",
    "period": ".",
    "slash": "/",
    "colon": ":",
    "semicolon": ";",
    "less": "<",
    "equal": "=",
    "greater": ">",
    "question": "?",
    "at": "@",
    "bracketleft": "[",
    "backslash": "\\",
    "bracketright": "]",
    "asciicircum": "^",
    "underscore": "_",
    "grave": "`",
    "quoteleft": "`",
    "braceleft": "{",
    "bar": "|",
    "braceright": "}",
    "asciitilde": "~",
}


def canonical_keysym(name: str) -> str:
    """The form a keysym is stored in, resolving X11's punctuation names.

    ``period`` and ``.`` are the same key, and a binding may be written
    either way; both end up as ``.`` so they match the same event. Space
    stays ``space``, as it does in Tk.
    """
    if name == "space":
        return "space"
    return PUNCTUATION_KEYSYMS.get(name, name)


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


#: ncurses' names for the modified forms of the keys that have them, without
#: the modifier digit. A terminal that reports Control-Down at all reports it
#: through an *extended* capability, which ncurses numbers at run time from
#: whatever the terminal description offers - so there is no constant to
#: compare against and the code has to be asked what it is called.
_EXTENDED_KEYSYMS: dict[str, str] = {
    "kDN": "Down",
    "kUP": "Up",
    "kLFT": "Left",
    "kRIT": "Right",
    "kHOM": "Home",
    "kEND": "End",
    "kPRV": "Prior",
    "kNXT": "Next",
    "kDC": "Delete",
    "kIC": "Insert",
}

#: The modifiers each of xterm's modifier parameters stands for. The
#: parameter is one more than a three-bit set, so 6 is 5 - Shift and Control
#: - and 8 is all three.
_XTERM_MODIFIER_BITS: tuple[tuple[int, int], ...] = (
    (0x1, MOD_SHIFT),
    (0x2, MOD_ALT),
    (0x4, MOD_CTRL),
)

_MISSING = object()

_modified_keys: dict[int, tuple[str, int] | None] = {}


def modified_key(keycode: int) -> tuple[str, int] | None:
    """The key and modifiers behind one of ncurses' extended key codes.

    Args:
        keycode: A code from ``getch``.

    Returns:
        ``(keysym, modifiers)`` for a code ncurses names as a modified key -
        ``kDN5`` is Down with Control - or None for anything else, which is
        every ordinary key.

    ncurses decodes the terminal's modified-key sequences for us but has
    nowhere to put the modifier: it allocates a fresh code for each
    combination and names it. The name is the only place the modifier
    survives, so this reads it back out. Answers are cached because a key
    press is on the hot path and a name does not change under a running
    terminal - but a refusal is not cached, because before ``initscr`` there
    is no terminal to ask and the answer afterwards is a different one.
    """
    cached = _modified_keys.get(keycode, _MISSING)
    if cached is not _MISSING:
        return cached  # type: ignore[return-value]
    try:
        name = curses.keyname(keycode).decode("ascii", "replace")
    except (curses.error, ValueError):
        return None
    result = _parse_extended(name)
    _modified_keys[keycode] = result
    return result


def _parse_extended(name: str) -> tuple[str, int] | None:
    """Split one of ncurses' extended key names into a key and modifiers."""
    prefix, digit = name[:-1], name[-1:]
    if not digit.isdigit() or prefix not in _EXTENDED_KEYSYMS:
        return None
    parameter = int(digit)
    if parameter < 2:
        return None
    modifiers = 0
    for bit, flag in _XTERM_MODIFIER_BITS:
        if (parameter - 1) & bit:
            modifiers |= flag
    return _EXTENDED_KEYSYMS[prefix], modifiers


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
    modified = modified_key(keycode)
    if modified is not None:
        return modified[0]
    return f"keycode-{keycode}"
