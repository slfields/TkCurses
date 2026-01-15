"""TkCurses constants and symbolic names.

Provides constants compatible with tkinter and curses including:
- Anchor positions (N, S, E, W, CENTER, etc.)
- Relief styles (FLAT, RAISED, SUNKEN, etc.)
- State values (NORMAL, DISABLED, ACTIVE)
- Selection modes and other widget options
- Curses attribute constants (A_BOLD, A_UNDERLINE, etc.)
- Curses key constants (KEY_UP, KEY_DOWN, etc.)
- Curses ACS (Alternate Character Set) constants

This module re-exports curses constants for convenience, allowing
applications to use `from tkcurses.constants import *` to get all
constants without importing curses directly.
"""

import curses

# =============================================================================
# Tkinter-compatible Widget Constants
# =============================================================================

# Anchor positions (compass directions)
N = 'n'
S = 's'
E = 'e'
W = 'w'
NE = 'ne'
NW = 'nw'
SE = 'se'
SW = 'sw'
CENTER = 'center'
NSEW = 'nsew'

# Relief styles
FLAT = 'flat'
RAISED = 'raised'
SUNKEN = 'sunken'
GROOVE = 'groove'
RIDGE = 'ridge'
SOLID = 'solid'

# Widget states
NORMAL = 'normal'
DISABLED = 'disabled'
ACTIVE = 'active'
HIDDEN = 'hidden'

# Boolean-like constants
YES = True
NO = False
ON = True
OFF = False
TRUE = True
FALSE = False

# Selection modes (Listbox)
SINGLE = 'single'
BROWSE = 'browse'
MULTIPLE = 'multiple'
EXTENDED = 'extended'

# Scrollbar/Scale orientation
HORIZONTAL = 'horizontal'
VERTICAL = 'vertical'
BOTH = 'both'

# Pack side options
TOP = 'top'
BOTTOM = 'bottom'
LEFT = 'left'
RIGHT = 'right'

# Pack fill options
NONE = 'none'
X = 'x'
Y = 'y'
# BOTH already defined above

# Text widget insert marks
INSERT = 'insert'
CURRENT = 'current'
END = 'end'
SEL = 'sel'
SEL_FIRST = 'sel.first'
SEL_LAST = 'sel.last'

# Text wrap modes
CHAR = 'char'
WORD = 'word'
# NONE already defined above

# Menu types
CASCADE = 'cascade'
CHECKBUTTON = 'checkbutton'
COMMAND = 'command'
RADIOBUTTON = 'radiobutton'
SEPARATOR = 'separator'

# Cursor movement
UNITS = 'units'
PAGES = 'pages'

# Event types (subset of tkinter event types)
BUTTON_PRESS = '4'
BUTTON_RELEASE = '5'
MOTION = '6'
KEY_PRESS = '2'
KEY_RELEASE = '3'
ENTER = '7'
LEAVE = '8'
FOCUS_IN = '9'
FOCUS_OUT = '10'
CONFIGURE = '22'

# =============================================================================
# Curses Attribute Constants (re-exported)
# =============================================================================

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

# A_ITALIC may not be available on all platforms
try:
    A_ITALIC = curses.A_ITALIC
except AttributeError:
    A_ITALIC = 0

# =============================================================================
# Curses Key Constants (re-exported)
# =============================================================================

KEY_UP = curses.KEY_UP
KEY_DOWN = curses.KEY_DOWN
KEY_LEFT = curses.KEY_LEFT
KEY_RIGHT = curses.KEY_RIGHT
KEY_HOME = curses.KEY_HOME
KEY_END = curses.KEY_END
KEY_NPAGE = curses.KEY_NPAGE  # Page Down
KEY_PPAGE = curses.KEY_PPAGE  # Page Up
KEY_IC = curses.KEY_IC        # Insert
KEY_DC = curses.KEY_DC        # Delete
KEY_BACKSPACE = curses.KEY_BACKSPACE
KEY_ENTER = curses.KEY_ENTER
KEY_BTAB = curses.KEY_BTAB    # Back Tab (Shift-Tab)

# Function keys
KEY_F1 = curses.KEY_F1
KEY_F2 = curses.KEY_F2
KEY_F3 = curses.KEY_F3
KEY_F4 = curses.KEY_F4
KEY_F5 = curses.KEY_F5
KEY_F6 = curses.KEY_F6
KEY_F7 = curses.KEY_F7
KEY_F8 = curses.KEY_F8
KEY_F9 = curses.KEY_F9
KEY_F10 = curses.KEY_F10
KEY_F11 = curses.KEY_F11
KEY_F12 = curses.KEY_F12

# Shifted keys
KEY_SHOME = curses.KEY_SHOME
KEY_SEND = curses.KEY_SEND
KEY_SLEFT = curses.KEY_SLEFT
KEY_SRIGHT = curses.KEY_SRIGHT

# Special keys
KEY_MOUSE = curses.KEY_MOUSE
KEY_RESIZE = curses.KEY_RESIZE

# =============================================================================
# Curses Mouse Button Constants (re-exported)
# =============================================================================

BUTTON1_PRESSED = curses.BUTTON1_PRESSED
BUTTON1_RELEASED = curses.BUTTON1_RELEASED
BUTTON1_CLICKED = curses.BUTTON1_CLICKED
BUTTON1_DOUBLE_CLICKED = curses.BUTTON1_DOUBLE_CLICKED
BUTTON1_TRIPLE_CLICKED = curses.BUTTON1_TRIPLE_CLICKED

BUTTON2_PRESSED = curses.BUTTON2_PRESSED
BUTTON2_RELEASED = curses.BUTTON2_RELEASED
BUTTON2_CLICKED = curses.BUTTON2_CLICKED
BUTTON2_DOUBLE_CLICKED = curses.BUTTON2_DOUBLE_CLICKED
BUTTON2_TRIPLE_CLICKED = curses.BUTTON2_TRIPLE_CLICKED

BUTTON3_PRESSED = curses.BUTTON3_PRESSED
BUTTON3_RELEASED = curses.BUTTON3_RELEASED
BUTTON3_CLICKED = curses.BUTTON3_CLICKED
BUTTON3_DOUBLE_CLICKED = curses.BUTTON3_DOUBLE_CLICKED
BUTTON3_TRIPLE_CLICKED = curses.BUTTON3_TRIPLE_CLICKED

BUTTON4_PRESSED = curses.BUTTON4_PRESSED
BUTTON4_RELEASED = curses.BUTTON4_RELEASED
BUTTON4_CLICKED = curses.BUTTON4_CLICKED
BUTTON4_DOUBLE_CLICKED = curses.BUTTON4_DOUBLE_CLICKED
BUTTON4_TRIPLE_CLICKED = curses.BUTTON4_TRIPLE_CLICKED

# Button 5 may not be available on all platforms
BUTTON5_PRESSED = getattr(curses, 'BUTTON5_PRESSED', 0)
BUTTON5_RELEASED = getattr(curses, 'BUTTON5_RELEASED', 0)
BUTTON5_CLICKED = getattr(curses, 'BUTTON5_CLICKED', 0)
BUTTON5_DOUBLE_CLICKED = getattr(curses, 'BUTTON5_DOUBLE_CLICKED', 0)
BUTTON5_TRIPLE_CLICKED = getattr(curses, 'BUTTON5_TRIPLE_CLICKED', 0)

# Mouse modifier keys
BUTTON_SHIFT = curses.BUTTON_SHIFT
BUTTON_CTRL = curses.BUTTON_CTRL
BUTTON_ALT = curses.BUTTON_ALT

# Mouse event masks
ALL_MOUSE_EVENTS = curses.ALL_MOUSE_EVENTS
REPORT_MOUSE_POSITION = curses.REPORT_MOUSE_POSITION

# =============================================================================
# Curses ACS (Alternate Character Set) Constants
# These are used for drawing box characters and other special graphics
# =============================================================================

# Note: ACS constants require curses to be initialized before use.
# These are placeholders that will be populated after initscr().
# Use get_acs_chars() after initialization to get actual values.


def get_acs_chars() -> dict[str, int]:
    """Get ACS character mappings after curses initialization.

    This function must be called after curses.initscr() has been
    invoked, as ACS characters are not available until then.

    Returns:
        Dictionary mapping character names to their curses values.

    Example:
        >>> import curses
        >>> curses.initscr()
        >>> acs = get_acs_chars()
        >>> curses.endwin()
        >>> 'ULCORNER' in acs
        True
    """
    return {
        # Box drawing corners
        'ULCORNER': curses.ACS_ULCORNER,    # Upper left corner
        'URCORNER': curses.ACS_URCORNER,    # Upper right corner
        'LLCORNER': curses.ACS_LLCORNER,    # Lower left corner
        'LRCORNER': curses.ACS_LRCORNER,    # Lower right corner
        # Box drawing lines
        'HLINE': curses.ACS_HLINE,          # Horizontal line
        'VLINE': curses.ACS_VLINE,          # Vertical line
        # Box drawing T-pieces
        'LTEE': curses.ACS_LTEE,            # Left T
        'RTEE': curses.ACS_RTEE,            # Right T
        'TTEE': curses.ACS_TTEE,            # Top T
        'BTEE': curses.ACS_BTEE,            # Bottom T
        'PLUS': curses.ACS_PLUS,            # Plus/crossover
        # Other graphics
        'DIAMOND': curses.ACS_DIAMOND,      # Diamond
        'CKBOARD': curses.ACS_CKBOARD,      # Checkerboard (stipple)
        'DEGREE': curses.ACS_DEGREE,        # Degree symbol
        'PLMINUS': curses.ACS_PLMINUS,      # Plus/minus
        'BULLET': curses.ACS_BULLET,        # Bullet
        # Arrows
        'LARROW': curses.ACS_LARROW,        # Left arrow
        'RARROW': curses.ACS_RARROW,        # Right arrow
        'UARROW': curses.ACS_UARROW,        # Up arrow
        'DARROW': curses.ACS_DARROW,        # Down arrow
        # Misc
        'BOARD': curses.ACS_BOARD,          # Board of squares
        'LANTERN': curses.ACS_LANTERN,      # Lantern symbol
        'BLOCK': curses.ACS_BLOCK,          # Solid block
        # Scan lines
        'S1': curses.ACS_S1,                # Scan line 1
        'S3': curses.ACS_S3,                # Scan line 3
        'S7': curses.ACS_S7,                # Scan line 7
        'S9': curses.ACS_S9,                # Scan line 9
        # Inequalities
        'LEQUAL': curses.ACS_LEQUAL,        # Less than or equal
        'GEQUAL': curses.ACS_GEQUAL,        # Greater than or equal
        'NEQUAL': curses.ACS_NEQUAL,        # Not equal
        'PI': curses.ACS_PI,                # Pi
        'STERLING': curses.ACS_STERLING,    # UK pound sign
    }


# Unicode fallbacks for box drawing (used when ACS not available)
BOX_CHARS_UNICODE = {
    'ULCORNER': '\u250c',  # ┌
    'URCORNER': '\u2510',  # ┐
    'LLCORNER': '\u2514',  # └
    'LRCORNER': '\u2518',  # ┘
    'HLINE': '\u2500',     # ─
    'VLINE': '\u2502',     # │
    'LTEE': '\u251c',      # ├
    'RTEE': '\u2524',      # ┤
    'TTEE': '\u252c',      # ┬
    'BTEE': '\u2534',      # ┴
    'PLUS': '\u253c',      # ┼
}

# ASCII fallbacks for box drawing (maximum compatibility)
BOX_CHARS_ASCII = {
    'ULCORNER': '+',
    'URCORNER': '+',
    'LLCORNER': '+',
    'LRCORNER': '+',
    'HLINE': '-',
    'VLINE': '|',
    'LTEE': '+',
    'RTEE': '+',
    'TTEE': '+',
    'BTEE': '+',
    'PLUS': '+',
}

# Double-line box drawing (Unicode only)
BOX_CHARS_DOUBLE = {
    'ULCORNER': '\u2554',  # ╔
    'URCORNER': '\u2557',  # ╗
    'LLCORNER': '\u255a',  # ╚
    'LRCORNER': '\u255d',  # ╝
    'HLINE': '\u2550',     # ═
    'VLINE': '\u2551',     # ║
    'LTEE': '\u2560',      # ╠
    'RTEE': '\u2563',      # ╣
    'TTEE': '\u2566',      # ╦
    'BTEE': '\u2569',      # ╩
    'PLUS': '\u256c',      # ╬
}

# =============================================================================
# Color Constants
# =============================================================================

# Base curses colors
COLOR_BLACK = curses.COLOR_BLACK
COLOR_RED = curses.COLOR_RED
COLOR_GREEN = curses.COLOR_GREEN
COLOR_YELLOW = curses.COLOR_YELLOW
COLOR_BLUE = curses.COLOR_BLUE
COLOR_MAGENTA = curses.COLOR_MAGENTA
COLOR_CYAN = curses.COLOR_CYAN
COLOR_WHITE = curses.COLOR_WHITE

# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Anchor positions
    'N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW', 'CENTER', 'NSEW',
    # Relief styles
    'FLAT', 'RAISED', 'SUNKEN', 'GROOVE', 'RIDGE', 'SOLID',
    # Widget states
    'NORMAL', 'DISABLED', 'ACTIVE', 'HIDDEN',
    # Boolean constants
    'YES', 'NO', 'ON', 'OFF', 'TRUE', 'FALSE',
    # Selection modes
    'SINGLE', 'BROWSE', 'MULTIPLE', 'EXTENDED',
    # Orientations
    'HORIZONTAL', 'VERTICAL', 'BOTH',
    # Pack options
    'TOP', 'BOTTOM', 'LEFT', 'RIGHT', 'NONE', 'X', 'Y',
    # Text marks
    'INSERT', 'CURRENT', 'END', 'SEL', 'SEL_FIRST', 'SEL_LAST',
    # Wrap modes
    'CHAR', 'WORD',
    # Menu types
    'CASCADE', 'CHECKBUTTON', 'COMMAND', 'RADIOBUTTON', 'SEPARATOR',
    # Cursor movement
    'UNITS', 'PAGES',
    # Event types
    'BUTTON_PRESS', 'BUTTON_RELEASE', 'MOTION', 'KEY_PRESS', 'KEY_RELEASE',
    'ENTER', 'LEAVE', 'FOCUS_IN', 'FOCUS_OUT', 'CONFIGURE',
    # Curses attributes
    'A_NORMAL', 'A_STANDOUT', 'A_UNDERLINE', 'A_REVERSE', 'A_BLINK',
    'A_DIM', 'A_BOLD', 'A_PROTECT', 'A_INVIS', 'A_ALTCHARSET', 'A_ITALIC',
    # Curses keys
    'KEY_UP', 'KEY_DOWN', 'KEY_LEFT', 'KEY_RIGHT', 'KEY_HOME', 'KEY_END',
    'KEY_NPAGE', 'KEY_PPAGE', 'KEY_IC', 'KEY_DC', 'KEY_BACKSPACE', 'KEY_ENTER',
    'KEY_BTAB', 'KEY_F1', 'KEY_F2', 'KEY_F3', 'KEY_F4', 'KEY_F5', 'KEY_F6',
    'KEY_F7', 'KEY_F8', 'KEY_F9', 'KEY_F10', 'KEY_F11', 'KEY_F12',
    'KEY_SHOME', 'KEY_SEND', 'KEY_SLEFT', 'KEY_SRIGHT',
    'KEY_MOUSE', 'KEY_RESIZE',
    # Mouse buttons
    'BUTTON1_PRESSED', 'BUTTON1_RELEASED', 'BUTTON1_CLICKED',
    'BUTTON1_DOUBLE_CLICKED', 'BUTTON1_TRIPLE_CLICKED',
    'BUTTON2_PRESSED', 'BUTTON2_RELEASED', 'BUTTON2_CLICKED',
    'BUTTON2_DOUBLE_CLICKED', 'BUTTON2_TRIPLE_CLICKED',
    'BUTTON3_PRESSED', 'BUTTON3_RELEASED', 'BUTTON3_CLICKED',
    'BUTTON3_DOUBLE_CLICKED', 'BUTTON3_TRIPLE_CLICKED',
    'BUTTON4_PRESSED', 'BUTTON4_RELEASED', 'BUTTON4_CLICKED',
    'BUTTON4_DOUBLE_CLICKED', 'BUTTON4_TRIPLE_CLICKED',
    'BUTTON5_PRESSED', 'BUTTON5_RELEASED', 'BUTTON5_CLICKED',
    'BUTTON5_DOUBLE_CLICKED', 'BUTTON5_TRIPLE_CLICKED',
    'BUTTON_SHIFT', 'BUTTON_CTRL', 'BUTTON_ALT',
    'ALL_MOUSE_EVENTS', 'REPORT_MOUSE_POSITION',
    # ACS functions and fallbacks
    'get_acs_chars', 'BOX_CHARS_UNICODE', 'BOX_CHARS_ASCII', 'BOX_CHARS_DOUBLE',
    # Colors
    'COLOR_BLACK', 'COLOR_RED', 'COLOR_GREEN', 'COLOR_YELLOW',
    'COLOR_BLUE', 'COLOR_MAGENTA', 'COLOR_CYAN', 'COLOR_WHITE',
]
