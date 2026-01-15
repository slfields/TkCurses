"""Internal implementation components for TkCurses.

This module contains the core implementation details that power the TkCurses
library. These components handle low-level curses operations, screen management,
event dispatching, and other internal functionality.

Warning:
    This module is NOT part of the public API. The contents may change between
    versions without notice. Users should only interact with TkCurses through
    the public top-level API.

Internal Components:
    - config: Configuration management and defaults
    - dispatcher: Event loop and callback dispatching
    - screen: Low-level curses screen management
    - colors: Color pair and palette management
    - attributes: Text attribute handling (bold, underline, etc.)
    - events: Event object definitions and processing
    - input: Keyboard and mouse input handling
    - geometry: Coordinate system and layout calculations
    - panels: Curses panel management for overlapping windows
"""

from .attributes import (
    A_ALTCHARSET,
    A_BLINK,
    A_BOLD,
    A_DIM,
    A_INVIS,
    A_ITALIC,
    A_NORMAL,
    A_PROTECT,
    A_REVERSE,
    A_STANDOUT,
    A_UNDERLINE,
    add_attr,
    attrs_to_str,
    combine_attrs,
    has_attr,
    remove_attr,
    style_to_attr,
)
from .colors import (
    BASE_COLORS,
    EXTENDED_COLORS,
    ColorManager,
    hex_to_curses,
)
from .config import (
    AccessibilityConfig,
    DebugConfig,
    DisplayConfig,
    InputConfig,
    MouseConfig,
    TkCursesConfig,
)
from .dispatcher import CursesDispatcher
from .events import (
    MOD_ALT,
    MOD_CTRL,
    MOD_META,
    MOD_SHIFT,
    Event,
    KeyEvent,
    MouseEvent,
    ResizeEvent,
    has_modifier,
)
from .geometry import (
    Padding,
    Point,
    Rect,
    Size,
    SizeConstraints,
    align_in_rect,
    center_in_rect,
    distribute_space,
)
from .input import InputHandler
from .screen import CursesScreen

__all__ = [
    # attributes
    'A_ALTCHARSET',
    'A_BLINK',
    'A_BOLD',
    'A_DIM',
    'A_INVIS',
    'A_ITALIC',
    'A_NORMAL',
    'A_PROTECT',
    'A_REVERSE',
    'A_STANDOUT',
    'A_UNDERLINE',
    'add_attr',
    'attrs_to_str',
    'combine_attrs',
    'has_attr',
    'remove_attr',
    'style_to_attr',
    # colors
    'BASE_COLORS',
    'EXTENDED_COLORS',
    'ColorManager',
    'hex_to_curses',
    # config
    'AccessibilityConfig',
    'DebugConfig',
    'DisplayConfig',
    'InputConfig',
    'MouseConfig',
    'TkCursesConfig',
    # dispatcher
    'CursesDispatcher',
    # events
    'MOD_ALT',
    'MOD_CTRL',
    'MOD_META',
    'MOD_SHIFT',
    'Event',
    'KeyEvent',
    'MouseEvent',
    'ResizeEvent',
    'has_modifier',
    # geometry
    'Padding',
    'Point',
    'Rect',
    'Size',
    'SizeConstraints',
    'align_in_rect',
    'center_in_rect',
    'distribute_space',
    # input
    'InputHandler',
    # screen
    'CursesScreen',
]
