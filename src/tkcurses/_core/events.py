"""Event objects and processing for TkCurses internals.

Defines Event class compatible with tkinter events and
handles event generation, propagation, and binding
callback invocation.
"""

import time
from dataclasses import dataclass, field
from typing import Optional


# Modifier key constants
MOD_SHIFT = 0x01
MOD_CTRL = 0x02
MOD_ALT = 0x04
MOD_META = 0x08


@dataclass
class Event:
    """Base event class for all TkCurses events.

    Attributes:
        type: Event type identifier (e.g., 'key', 'mouse', 'resize').
        time: Timestamp when the event occurred (seconds since epoch).
    """

    type: str
    time: float = field(default_factory=time.time)


@dataclass
class KeyEvent(Event):
    """Keyboard event.

    Attributes:
        type: Always 'key' for keyboard events.
        keycode: Raw curses key code.
        keysym: Tkinter-style key symbol (e.g., 'Return', 'Up', 'a').
        char: Printable character representation (empty for special keys).
        modifiers: Modifier flags (MOD_SHIFT, MOD_CTRL, MOD_ALT, MOD_META).
        time: Timestamp when the event occurred.
    """

    type: str = "key"
    keycode: int = 0
    keysym: str = ""
    char: str = ""
    modifiers: int = 0


@dataclass
class MouseEvent(Event):
    """Mouse event with full drag support.

    Attributes:
        type: Always 'mouse' for mouse events.
        x: Column position of the mouse cursor.
        y: Row position of the mouse cursor.
        button: Button identifier (1=left, 2=middle, 3=right,
                4=scroll-up, 5=scroll-down).
        state: State of the mouse event. One of: 'pressed', 'released',
               'clicked', 'double', 'triple', 'drag', 'motion'.
        modifiers: Modifier flags (MOD_SHIFT, MOD_CTRL, MOD_ALT, MOD_META).
        drag_start: Starting position (x, y) if this is a drag event, None otherwise.
        drag_end: Ending position (x, y) if this is a drag event, None otherwise.
        time: Timestamp when the event occurred.
    """

    type: str = "mouse"
    x: int = 0
    y: int = 0
    button: int = 0
    state: str = "pressed"
    modifiers: int = 0
    drag_start: Optional[tuple[int, int]] = None
    drag_end: Optional[tuple[int, int]] = None


@dataclass
class ResizeEvent(Event):
    """Terminal resize event.

    Attributes:
        type: Always 'resize' for resize events.
        width: New column count (width in characters).
        height: New row count (height in characters).
        time: Timestamp when the event occurred.
    """

    type: str = "resize"
    width: int = 0
    height: int = 0


def has_modifier(modifiers: int, mod: int) -> bool:
    """Check if a specific modifier flag is set.

    Args:
        modifiers: The combined modifier flags to check.
        mod: The specific modifier to check for (MOD_SHIFT, MOD_CTRL, etc.).

    Returns:
        True if the modifier is set in the modifiers bitfield, False otherwise.
    """
    return (modifiers & mod) != 0
