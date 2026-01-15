"""Color management for TkCurses internals.

Handles curses color pair initialization, color name mapping,
and palette management. Translates tkinter color specifications
to terminal color pairs.
"""

from __future__ import annotations

import curses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# Base 8-color mapping: X11 name -> curses constant
BASE_COLORS: dict[str, int] = {
    "black": curses.COLOR_BLACK,
    "red": curses.COLOR_RED,
    "green": curses.COLOR_GREEN,
    "yellow": curses.COLOR_YELLOW,
    "blue": curses.COLOR_BLUE,
    "magenta": curses.COLOR_MAGENTA,
    "cyan": curses.COLOR_CYAN,
    "white": curses.COLOR_WHITE,
}

# Extended X11 color approximations: X11 name -> (curses_color, attribute)
# Uses curses attributes A_DIM, A_BOLD, A_NORMAL for color variations
EXTENDED_COLORS: dict[str, tuple[int, int]] = {
    # Gray variants
    "gray": (curses.COLOR_WHITE, curses.A_DIM),
    "grey": (curses.COLOR_WHITE, curses.A_DIM),
    "lightgray": (curses.COLOR_WHITE, curses.A_NORMAL),
    "lightgrey": (curses.COLOR_WHITE, curses.A_NORMAL),
    "darkgray": (curses.COLOR_BLACK, curses.A_BOLD),
    "darkgrey": (curses.COLOR_BLACK, curses.A_BOLD),
    # Warm colors
    "orange": (curses.COLOR_YELLOW, curses.A_NORMAL),
    "pink": (curses.COLOR_MAGENTA, curses.A_NORMAL),
    "brown": (curses.COLOR_YELLOW, curses.A_DIM),
    # Purple/violet variants
    "purple": (curses.COLOR_MAGENTA, curses.A_NORMAL),
    "violet": (curses.COLOR_MAGENTA, curses.A_NORMAL),
    # Blue variants
    "navy": (curses.COLOR_BLUE, curses.A_DIM),
    # Green variants
    "lime": (curses.COLOR_GREEN, curses.A_BOLD),
    # Cyan variants
    "aqua": (curses.COLOR_CYAN, curses.A_NORMAL),
    "turquoise": (curses.COLOR_CYAN, curses.A_NORMAL),
    "teal": (curses.COLOR_CYAN, curses.A_DIM),
    # Red variants
    "maroon": (curses.COLOR_RED, curses.A_DIM),
    # Yellow variants
    "olive": (curses.COLOR_YELLOW, curses.A_DIM),
    # White/silver variants
    "silver": (curses.COLOR_WHITE, curses.A_NORMAL),
    # Magenta variants
    "fuchsia": (curses.COLOR_MAGENTA, curses.A_BOLD),
}


def hex_to_curses(hex_color: str) -> tuple[int, int]:
    """Convert #RRGGBB hex color to (curses_color, attribute).

    Analyzes the hex color's RGB components and brightness to
    determine the closest curses 8-color match and appropriate
    attribute (A_BOLD, A_DIM, or A_NORMAL).

    Args:
        hex_color: A hex color string in #RRGGBB format.

    Returns:
        A tuple of (curses_color_constant, curses_attribute).

    Examples:
        >>> hex_to_curses("#FF0000")  # Pure red
        (1, curses.A_BOLD)
        >>> hex_to_curses("#000000")  # Black
        (0, curses.A_DIM)
        >>> hex_to_curses("#808080")  # Gray
        (7, curses.A_DIM)
    """
    # Parse RGB components from hex string
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)

    # Determine brightness (average of RGB)
    brightness = (r + g + b) / 3

    # Select attribute based on brightness
    if brightness > 170:
        attr = curses.A_BOLD
    elif brightness < 85:
        attr = curses.A_DIM
    else:
        attr = curses.A_NORMAL

    # Find dominant color channel(s)
    # Red dominant
    if r > 200 and g < 100 and b < 100:
        return curses.COLOR_RED, attr

    # Green dominant
    if r < 100 and g > 200 and b < 100:
        return curses.COLOR_GREEN, attr

    # Blue dominant
    if r < 100 and g < 100 and b > 200:
        return curses.COLOR_BLUE, attr

    # Yellow (red + green)
    if r > 200 and g > 200 and b < 100:
        return curses.COLOR_YELLOW, attr

    # Magenta (red + blue)
    if r > 200 and g < 100 and b > 200:
        return curses.COLOR_MAGENTA, attr

    # Cyan (green + blue)
    if r < 100 and g > 200 and b > 200:
        return curses.COLOR_CYAN, attr

    # Very bright -> white
    if brightness > 200:
        return curses.COLOR_WHITE, attr

    # Very dark -> black
    if brightness < 50:
        return curses.COLOR_BLACK, attr

    # Gray fallback for mid-range colors
    return curses.COLOR_WHITE, curses.A_DIM


class ColorManager:
    """Manages curses color pairs and X11 color name translation.

    Curses requires pre-initialized color pairs for foreground/background
    combinations. This class maintains a dynamic registry of color pairs
    and handles translation from X11 color names to curses constants.

    Attributes:
        _pairs: Dictionary mapping (fg, bg) tuples to pair numbers.
        _next_pair: Next available pair number (pair 0 is reserved).

    Example:
        >>> manager = ColorManager()
        >>> pair = manager.get_pair(curses.COLOR_RED, curses.COLOR_BLACK)
        >>> color, attr = manager.name_to_curses("lime")
        >>> manager.reset()  # Clear for testing
    """

    def __init__(self) -> None:
        """Initialize the ColorManager with empty pair registry."""
        self._pairs: dict[tuple[int, int], int] = {}
        self._next_pair: int = 1  # Pair 0 is reserved by curses

    def get_pair(self, fg: int, bg: int) -> int:
        """Get or create a curses color pair for the given fg/bg combination.

        If the combination has not been used before, initializes a new
        curses color pair. Returns the curses color_pair() value ready
        for use with addstr() or similar functions.

        Args:
            fg: Foreground curses color constant (0-7).
            bg: Background curses color constant (0-7).

        Returns:
            A curses color_pair() value that can be OR'd with attributes.

        Example:
            >>> manager = ColorManager()
            >>> attr = manager.get_pair(curses.COLOR_WHITE, curses.COLOR_BLUE)
            >>> window.addstr(0, 0, "Hello", attr | curses.A_BOLD)
        """
        key = (fg, bg)
        if key not in self._pairs:
            curses.init_pair(self._next_pair, fg, bg)
            self._pairs[key] = self._next_pair
            self._next_pair += 1
        return curses.color_pair(self._pairs[key])

    def name_to_curses(self, name: str) -> tuple[int, int]:
        """Convert an X11 color name to curses color and attribute.

        Handles both base 8-color names and extended X11 color names.
        Color names are case-insensitive.

        Args:
            name: An X11 color name (e.g., "red", "lightgray", "navy").

        Returns:
            A tuple of (curses_color_constant, curses_attribute).
            Returns (COLOR_WHITE, A_NORMAL) for unrecognized names.

        Example:
            >>> manager = ColorManager()
            >>> color, attr = manager.name_to_curses("Navy")
            >>> color == curses.COLOR_BLUE
            True
            >>> attr == curses.A_DIM
            True
        """
        # Normalize to lowercase for case-insensitive lookup
        name_lower = name.lower()

        # Check base colors first (most common)
        if name_lower in BASE_COLORS:
            return BASE_COLORS[name_lower], curses.A_NORMAL

        # Check extended color mappings
        if name_lower in EXTENDED_COLORS:
            return EXTENDED_COLORS[name_lower]

        # Default to white for unrecognized colors
        return curses.COLOR_WHITE, curses.A_NORMAL

    def reset(self) -> None:
        """Clear all registered color pairs.

        Resets the internal pair registry and next pair counter.
        Useful for testing or reinitializing the color system.

        Note:
            This does not call curses to reset pairs; it only clears
            the internal tracking. Curses pairs persist until the
            screen is reinitialized.
        """
        self._pairs.clear()
        self._next_pair = 1
