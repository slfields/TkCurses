"""Constants for TkCurses: tkinter's widget constants plus curses constants.

This module mirrors ``tkinter.constants`` name for name and value for value, so
that ``from tkcurses.constants import *`` gives application code exactly the
names ``from tkinter.constants import *`` would. The values are defined here
rather than re-exported, because importing ``tkinter.constants`` would pull in
the ``tkinter`` package and with it ``_tkinter``, which TkCurses does not
require at runtime.

Curses constants are also exposed: attribute masks (``A_BOLD``), colours
(``COLOR_RED``), and keys (``KEY_UP``) come straight from the ``curses``
module. The alternate character set names (``ACS_ULCORNER`` and friends) are
resolved lazily, because curses only defines them once a screen exists.
"""

from __future__ import annotations

import curses
from typing import Any

# --------------------------------------------------------------------------
# Booleans
# --------------------------------------------------------------------------
NO: bool = False
FALSE: bool = False
OFF: bool = False
YES: bool = True
TRUE: bool = True
ON: bool = True

# --------------------------------------------------------------------------
# Anchors and sticky directions
# --------------------------------------------------------------------------
N = "n"
S = "s"
W = "w"
E = "e"
NW = "nw"
SW = "sw"
NE = "ne"
SE = "se"
NS = "ns"
EW = "ew"
NSEW = "nsew"
CENTER = "center"

# --------------------------------------------------------------------------
# Fill and side, for the pack geometry manager
# --------------------------------------------------------------------------
NONE = "none"
X = "x"
Y = "y"
BOTH = "both"
LEFT = "left"
TOP = "top"
RIGHT = "right"
BOTTOM = "bottom"

# --------------------------------------------------------------------------
# Borders and relief
# --------------------------------------------------------------------------
RAISED = "raised"
SUNKEN = "sunken"
FLAT = "flat"
RIDGE = "ridge"
GROOVE = "groove"
SOLID = "solid"

# --------------------------------------------------------------------------
# Orientation
# --------------------------------------------------------------------------
HORIZONTAL = "horizontal"
VERTICAL = "vertical"

# --------------------------------------------------------------------------
# Tab and entry behaviour
# --------------------------------------------------------------------------
NUMERIC = "numeric"

# --------------------------------------------------------------------------
# Wrapping
# --------------------------------------------------------------------------
CHAR = "char"
WORD = "word"

# --------------------------------------------------------------------------
# Text and canvas alignment
# --------------------------------------------------------------------------
BASELINE = "baseline"
INSIDE = "inside"
OUTSIDE = "outside"

# --------------------------------------------------------------------------
# Special text and canvas indices
# --------------------------------------------------------------------------
SEL = "sel"
SEL_FIRST = "sel.first"
SEL_LAST = "sel.last"
END = "end"
INSERT = "insert"
CURRENT = "current"
ANCHOR = "anchor"
ALL = "all"

# --------------------------------------------------------------------------
# Widget states
# --------------------------------------------------------------------------
NORMAL = "normal"
DISABLED = "disabled"
ACTIVE = "active"
HIDDEN = "hidden"

# --------------------------------------------------------------------------
# Menu item types
# --------------------------------------------------------------------------
CASCADE = "cascade"
CHECKBUTTON = "checkbutton"
COMMAND = "command"
RADIOBUTTON = "radiobutton"
SEPARATOR = "separator"

# --------------------------------------------------------------------------
# Selection modes, for the listbox
# --------------------------------------------------------------------------
SINGLE = "single"
BROWSE = "browse"
MULTIPLE = "multiple"
EXTENDED = "extended"

# --------------------------------------------------------------------------
# Activestyle, for the listbox
# --------------------------------------------------------------------------
DOTBOX = "dotbox"
UNDERLINE = "underline"

# --------------------------------------------------------------------------
# Canvas arc styles
# --------------------------------------------------------------------------
PIESLICE = "pieslice"
CHORD = "chord"
ARC = "arc"

# --------------------------------------------------------------------------
# Canvas arrow and line styles
# --------------------------------------------------------------------------
FIRST = "first"
LAST = "last"
BUTT = "butt"
PROJECTING = "projecting"
ROUND = "round"
BEVEL = "bevel"
MITER = "miter"

# --------------------------------------------------------------------------
# Scrolling
# --------------------------------------------------------------------------
MOVETO = "moveto"
SCROLL = "scroll"
UNITS = "units"
PAGES = "pages"

# --------------------------------------------------------------------------
# Curses text attributes
# --------------------------------------------------------------------------
A_NORMAL = curses.A_NORMAL
A_STANDOUT = curses.A_STANDOUT
A_UNDERLINE = curses.A_UNDERLINE
A_REVERSE = curses.A_REVERSE
A_BLINK = curses.A_BLINK
A_DIM = curses.A_DIM
A_BOLD = curses.A_BOLD
A_PROTECT = curses.A_PROTECT
A_INVIS = curses.A_INVIS
A_ALTCHARSET = curses.A_ALTCHARSET
A_ITALIC = curses.A_ITALIC

# --------------------------------------------------------------------------
# Curses colours
# --------------------------------------------------------------------------
COLOR_BLACK = curses.COLOR_BLACK
COLOR_RED = curses.COLOR_RED
COLOR_GREEN = curses.COLOR_GREEN
COLOR_YELLOW = curses.COLOR_YELLOW
COLOR_BLUE = curses.COLOR_BLUE
COLOR_MAGENTA = curses.COLOR_MAGENTA
COLOR_CYAN = curses.COLOR_CYAN
COLOR_WHITE = curses.COLOR_WHITE

# --------------------------------------------------------------------------
# Curses keys
# --------------------------------------------------------------------------
KEY_UP = curses.KEY_UP
KEY_DOWN = curses.KEY_DOWN
KEY_LEFT = curses.KEY_LEFT
KEY_RIGHT = curses.KEY_RIGHT
KEY_HOME = curses.KEY_HOME
KEY_END = curses.KEY_END
KEY_PPAGE = curses.KEY_PPAGE
KEY_NPAGE = curses.KEY_NPAGE
KEY_DC = curses.KEY_DC
KEY_IC = curses.KEY_IC
KEY_BACKSPACE = curses.KEY_BACKSPACE
KEY_ENTER = curses.KEY_ENTER
KEY_MOUSE = curses.KEY_MOUSE
KEY_RESIZE = curses.KEY_RESIZE

#: Function keys KEY_F0 through KEY_F63, as curses defines them.
KEY_F0 = curses.KEY_F0

# --------------------------------------------------------------------------
# Alternate character set
# --------------------------------------------------------------------------
#: ACS names curses defines, resolved on demand by :func:`__getattr__`.
_ACS_NAMES = frozenset(
    {
        "ACS_ULCORNER",
        "ACS_URCORNER",
        "ACS_LLCORNER",
        "ACS_LRCORNER",
        "ACS_HLINE",
        "ACS_VLINE",
        "ACS_PLUS",
        "ACS_LTEE",
        "ACS_RTEE",
        "ACS_BTEE",
        "ACS_TTEE",
        "ACS_BLOCK",
        "ACS_CKBOARD",
        "ACS_DIAMOND",
        "ACS_DEGREE",
        "ACS_BULLET",
        "ACS_BOARD",
        "ACS_LANTERN",
        "ACS_LARROW",
        "ACS_RARROW",
        "ACS_UARROW",
        "ACS_DARROW",
        "ACS_S1",
        "ACS_S9",
        "ACS_PLMINUS",
        "ACS_STERLING",
    }
)


def _function_key(number: int) -> int:
    """Return the key code for function key ``number`` (0-63)."""
    if not 0 <= number <= 63:
        raise ValueError(f"function key number out of range (0-63): {number}")
    return curses.KEY_F0 + number


def __getattr__(name: str) -> Any:
    """Resolve constants that only exist once curses has a screen.

    curses defines the alternate character set from the terminal's terminfo
    entry, so ``curses.ACS_HLINE`` does not exist until ``initscr()`` has run.
    Importing this module must not require an initialised screen, so the ACS
    names are looked up on first access instead, and ``KEY_F1``..``KEY_F63``
    are derived from ``KEY_F0``.
    """
    if name in _ACS_NAMES:
        try:
            return getattr(curses, name)
        except AttributeError:
            raise AttributeError(
                f"{name} is unavailable until the screen is initialised; "
                "curses defines the alternate character set in initscr()"
            ) from None
    if name.startswith("KEY_F") and name[5:].isdigit():
        return _function_key(int(name[5:]))
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
