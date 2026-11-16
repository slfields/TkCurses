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
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Literal

__all__ = [
    "MOD_ALT",
    "MOD_BUTTON1",
    "MOD_BUTTON2",
    "MOD_BUTTON3",
    "MOD_BUTTON4",
    "MOD_BUTTON5",
    "MOD_BUTTONS",
    "MOD_CTRL",
    "MOD_META",
    "MOD_SHIFT",
    "PUNCTUATION_KEYSYMS",
    "Event",
    "KeyEvent",
    "MouseEvent",
    "MouseState",
    "PasteEvent",
    "ResizeEvent",
    "canonical_keysym",
    "char_for_keysym",
    "keysym_for",
    "keysym_for_char",
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

#: A mouse button being *held*, which Tk spells B1 to B5 and treats as a
#: modifier like any other. <B1-Motion> - drag with the left button down - is
#: how every Tk program implements dragging, so these are not a corner: they
#: are the second most used mouse binding there is.
MOD_BUTTON1 = 0x10
MOD_BUTTON2 = 0x20
MOD_BUTTON3 = 0x40
MOD_BUTTON4 = 0x80
MOD_BUTTON5 = 0x100

#: The held-button bit for each button number.
MOD_BUTTONS: dict[int, int] = {
    1: MOD_BUTTON1,
    2: MOD_BUTTON2,
    3: MOD_BUTTON3,
    4: MOD_BUTTON4,
    5: MOD_BUTTON5,
}

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
        keycode: The raw value returned by ``getch()``, or the code point
            of a character beyond ASCII, which arrives as several.
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


@dataclass
class PasteEvent(Event):
    """Text pasted into the terminal, which the terminal marked as a paste.

    A terminal in bracketed-paste mode (DEC 2004) wraps what is pasted in
    ``ESC [ 200 ~`` and ``ESC [ 201 ~``, so that it arrives as one piece of
    text rather than as keys - a pasted line break is not Return.

    Attributes:
        text: What was pasted, as the terminal sent it: line breaks are
            usually carriage returns.
        complete: False when the paste was cut short - longer than the
            handler keeps, or its end never arrived.
    """

    type: str = "paste"
    text: str = ""
    complete: bool = True


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
    # The four control codes past Control-Z, which are not letters and so
    # fall outside the 1..26 arithmetic. Tk names them by the character on
    # the key - checked against Tk 9.0.2, which reports Control-backslash as
    # keysym "\\" and not as "backslash".
    28: "\\",
    29: "]",
    30: "^",
    31: "_",
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
    stays ``space``, as it does in Tk. The same goes for the keys beyond
    ASCII: ``eacute``, ``U00E9`` and ``é`` are one key, stored as ``é``.
    """
    if name == "space":
        return "space"
    if name in PUNCTUATION_KEYSYMS:
        return PUNCTUATION_KEYSYMS[name]
    char = _named_char(name)
    return keysym_for_char(char) if char else name


#: The character the named control keys carry, as Tk 9.0.2 reports for a
#: generated event: ``event_generate("<KeyPress>", keysym="Return")`` has
#: ``event.char`` ``"\r"``.
_CONTROL_CHARS: dict[str, str] = {
    "BackSpace": "\b",
    "Delete": "\x7f",
    "Escape": "\x1b",
    "Return": "\r",
    "Tab": "\t",
}


def char_for_keysym(keysym: str) -> str:
    """The character a key with this keysym types, or ``""`` for one that
    types none - an arrow, a function key."""
    if len(keysym) == 1:
        return keysym
    return (
        PUNCTUATION_KEYSYMS.get(keysym)
        or _CONTROL_CHARS.get(keysym)
        or _named_char(keysym)
    )


#: X11's names for the Latin-1 keys, U+00A0 to U+00FF in order. Tk accepts
#: each in a binding and stores it as the character itself - ``<Key-eacute>``
#: reads back from ``bind`` as ``<Key-é>`` - so they are resolved to it here
#: too. Checked one by one against Tk 9.0.2.
_LATIN1_NAMES = [
    "nobreakspace",
    "exclamdown",
    "cent",
    "sterling",
    "currency",
    "yen",
    "brokenbar",
    "section",
    "diaeresis",
    "copyright",
    "ordfeminine",
    "guillemotleft",
    "notsign",
    "hyphen",
    "registered",
    "macron",
    "degree",
    "plusminus",
    "twosuperior",
    "threesuperior",
    "acute",
    "mu",
    "paragraph",
    "periodcentered",
    "cedilla",
    "onesuperior",
    "masculine",
    "guillemotright",
    "onequarter",
    "onehalf",
    "threequarters",
    "questiondown",
    "Agrave",
    "Aacute",
    "Acircumflex",
    "Atilde",
    "Adiaeresis",
    "Aring",
    "AE",
    "Ccedilla",
    "Egrave",
    "Eacute",
    "Ecircumflex",
    "Ediaeresis",
    "Igrave",
    "Iacute",
    "Icircumflex",
    "Idiaeresis",
    "ETH",
    "Ntilde",
    "Ograve",
    "Oacute",
    "Ocircumflex",
    "Otilde",
    "Odiaeresis",
    "multiply",
    "Oslash",
    "Ugrave",
    "Uacute",
    "Ucircumflex",
    "Udiaeresis",
    "Yacute",
    "THORN",
    "ssharp",
    "agrave",
    "aacute",
    "acircumflex",
    "atilde",
    "adiaeresis",
    "aring",
    "ae",
    "ccedilla",
    "egrave",
    "eacute",
    "ecircumflex",
    "ediaeresis",
    "igrave",
    "iacute",
    "icircumflex",
    "idiaeresis",
    "eth",
    "ntilde",
    "ograve",
    "oacute",
    "ocircumflex",
    "otilde",
    "odiaeresis",
    "division",
    "oslash",
    "ugrave",
    "uacute",
    "ucircumflex",
    "udiaeresis",
    "yacute",
    "thorn",
    "ydiaeresis",
]

#: Every name above, the later spellings X11 gives some of them, and the
#: euro sign, which is the one key outside Latin-1 a keyboard commonly has.
_NAMED_CHARS: dict[str, str] = {
    **{name: chr(0xA0 + offset) for offset, name in enumerate(_LATIN1_NAMES)},
    "guillemetleft": "\u00ab",
    "guillemetright": "\u00bb",
    "ordmasculine": "\u00ba",
    "Ooblique": "\u00d8",
    "ooblique": "\u00f8",
    "Eth": "\u00d0",
    "Thorn": "\u00de",
    "EuroSign": "\u20ac",
}

#: X11's form for any other character: ``U`` and its code point in hex.
_UNICODE_KEYSYM = re.compile(r"U([0-9A-Fa-f]{4,6})")


def _named_char(name: str) -> str:
    """The character an X11 keysym name stands for, or ``""``."""
    if name in _NAMED_CHARS:
        return _NAMED_CHARS[name]
    match = _UNICODE_KEYSYM.fullmatch(name)
    if match is None:
        return ""
    code = int(match.group(1), 16)
    return chr(code) if code <= sys.maxunicode else ""


def keysym_for_char(char: str) -> str:
    """The keysym of a key that types ``char``, as Tk 9.0.2 names it.

    A character that prints is its own keysym, as ASCII's are: Tk reads
    ``<Key-U754C>`` back as ``<Key-界>``. Space and no-break space keep
    their names, ``space`` and ``nobreakspace``, and anything else that does
    not print - a soft hyphen, a control character - is named by its code
    point, ``U00AD``, as Tk names it.
    """
    if char == " ":
        return "space"
    if char == "\u00a0":
        return "nobreakspace"
    if char.isprintable():
        return char
    return f"U{ord(char):04X}"


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
