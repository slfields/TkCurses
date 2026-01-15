"""Text attribute handling for TkCurses internals.

Manages curses text attributes including bold, underline,
reverse, dim, and blink. Translates font specifications
to terminal attribute combinations.
"""

from __future__ import annotations

import curses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# Re-export curses attribute constants for convenience
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

# A_CHARTEXT is available in most curses implementations
if hasattr(curses, "A_CHARTEXT"):
    A_CHARTEXT = curses.A_CHARTEXT
else:
    A_CHARTEXT = None

# A_ITALIC is not available in all curses implementations
if hasattr(curses, "A_ITALIC"):
    A_ITALIC = curses.A_ITALIC
else:
    # Fallback: A_ITALIC not supported, use A_NORMAL as a no-op
    A_ITALIC = 0


# Attribute name mapping for debugging and introspection
ATTR_NAMES: dict[int, str] = {}

# Build the attribute names mapping
_attr_constants = {
    curses.A_NORMAL: "A_NORMAL",
    curses.A_STANDOUT: "A_STANDOUT",
    curses.A_UNDERLINE: "A_UNDERLINE",
    curses.A_REVERSE: "A_REVERSE",
    curses.A_BLINK: "A_BLINK",
    curses.A_DIM: "A_DIM",
    curses.A_BOLD: "A_BOLD",
    curses.A_PROTECT: "A_PROTECT",
    curses.A_INVIS: "A_INVIS",
    curses.A_ALTCHARSET: "A_ALTCHARSET",
}

if hasattr(curses, "A_CHARTEXT"):
    _attr_constants[curses.A_CHARTEXT] = "A_CHARTEXT"

if hasattr(curses, "A_ITALIC"):
    _attr_constants[curses.A_ITALIC] = "A_ITALIC"

ATTR_NAMES = _attr_constants


def combine_attrs(*attrs: int) -> int:
    """Combine multiple attributes with bitwise OR.

    Takes any number of curses attribute constants and combines them
    using bitwise OR, allowing multiple attributes to be applied simultaneously.

    Args:
        *attrs: Variable number of curses attribute constants (e.g., A_BOLD, A_UNDERLINE).

    Returns:
        The combined attribute value.

    Examples:
        >>> combined = combine_attrs(curses.A_BOLD, curses.A_UNDERLINE)
        >>> combined == (curses.A_BOLD | curses.A_UNDERLINE)
        True
        >>> single = combine_attrs(curses.A_BOLD)
        >>> single == curses.A_BOLD
        True
        >>> empty = combine_attrs()
        >>> empty == 0
        True
    """
    result = 0
    for attr in attrs:
        result |= attr
    return result


def has_attr(attrs: int, attr: int) -> bool:
    """Check if an attribute is set in the given attribute value.

    Uses bitwise AND to determine if a specific attribute is present
    in the combined attribute value.

    Args:
        attrs: The combined attribute value to check.
        attr: The specific attribute to look for.

    Returns:
        True if the attribute is set, False otherwise.

    Examples:
        >>> combined = curses.A_BOLD | curses.A_UNDERLINE
        >>> has_attr(combined, curses.A_BOLD)
        True
        >>> has_attr(combined, curses.A_REVERSE)
        False
        >>> has_attr(curses.A_BOLD, curses.A_BOLD)
        True
    """
    return (attrs & attr) != 0


def add_attr(attrs: int, attr: int) -> int:
    """Add an attribute to the given attribute value.

    Uses bitwise OR to add a new attribute without affecting
    existing attributes.

    Args:
        attrs: The current attribute value.
        attr: The attribute to add.

    Returns:
        The updated attribute value with the new attribute set.

    Examples:
        >>> result = add_attr(curses.A_BOLD, curses.A_UNDERLINE)
        >>> result == (curses.A_BOLD | curses.A_UNDERLINE)
        True
        >>> result = add_attr(0, curses.A_BOLD)
        >>> result == curses.A_BOLD
        True
    """
    return attrs | attr


def remove_attr(attrs: int, attr: int) -> int:
    """Remove an attribute from the given attribute value.

    Uses bitwise AND with bitwise NOT to remove a specific attribute
    while preserving all other attributes.

    Args:
        attrs: The current attribute value.
        attr: The attribute to remove.

    Returns:
        The updated attribute value with the attribute removed.

    Examples:
        >>> combined = curses.A_BOLD | curses.A_UNDERLINE
        >>> result = remove_attr(combined, curses.A_BOLD)
        >>> result == curses.A_UNDERLINE
        True
        >>> result = remove_attr(curses.A_BOLD, curses.A_BOLD)
        >>> result == 0
        True
        >>> result = remove_attr(curses.A_BOLD, curses.A_REVERSE)
        >>> result == curses.A_BOLD
        True
    """
    return attrs & ~attr


def attrs_to_str(attrs: int) -> str:
    """Convert attributes to a human-readable string.

    Creates a comma-separated string representation of the attributes
    set in the given attribute value. Useful for debugging and logging.

    Args:
        attrs: The attribute value to convert.

    Returns:
        A human-readable string representation, e.g., "A_BOLD, A_UNDERLINE".
        Returns "A_NORMAL" for zero or unrecognized values.

    Examples:
        >>> attrs_to_str(curses.A_BOLD)
        'A_BOLD'
        >>> attrs_to_str(curses.A_BOLD | curses.A_UNDERLINE)
        'A_BOLD, A_UNDERLINE'
        >>> attrs_to_str(0)
        'A_NORMAL'
    """
    if attrs == 0:
        return "A_NORMAL"

    # Check which attributes are set and build a list of names
    names = []
    for attr_val, attr_name in ATTR_NAMES.items():
        if attr_val != 0 and has_attr(attrs, attr_val):
            names.append(attr_name)

    if names:
        return ", ".join(names)
    else:
        return "A_NORMAL"


def style_to_attr(style: str) -> int:
    """Convert tkinter-style font attribute name to curses attribute.

    Maps human-readable tkinter-style font attribute names to their
    corresponding curses attribute constants. Names are case-insensitive.

    Args:
        style: A font attribute name string. Supported values:
            - "bold" → A_BOLD
            - "underline" → A_UNDERLINE
            - "reverse" → A_REVERSE
            - "dim" → A_DIM
            - "blink" → A_BLINK
            - "standout" → A_STANDOUT
            - "normal" → A_NORMAL

    Returns:
        The corresponding curses attribute constant.
        Returns A_NORMAL for unrecognized styles.

    Examples:
        >>> style_to_attr("bold")
        <curses.A_BOLD>
        >>> style_to_attr("UNDERLINE")
        <curses.A_UNDERLINE>
        >>> style_to_attr("unknown")
        <curses.A_NORMAL>
    """
    # Normalize to lowercase for case-insensitive matching
    style_lower = style.lower()

    # Map tkinter-style names to curses attributes
    style_map: dict[str, int] = {
        "bold": curses.A_BOLD,
        "underline": curses.A_UNDERLINE,
        "reverse": curses.A_REVERSE,
        "dim": curses.A_DIM,
        "blink": curses.A_BLINK,
        "standout": curses.A_STANDOUT,
        "normal": curses.A_NORMAL,
        "italic": A_ITALIC,
    }

    return style_map.get(style_lower, curses.A_NORMAL)
