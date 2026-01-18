"""Color management for TkCurses internals.

Handles curses color pair initialization, color name mapping,
and palette management. Translates tkinter color specifications
to terminal color pairs.
"""

from __future__ import annotations

import curses
import re
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


# Compiled regex for hex color validation (module level for performance)
_HEX_COLOR_PATTERN = re.compile(r'^#[0-9A-Fa-f]{6}$')


def hex_to_curses(hex_color: str) -> tuple[int, int]:
    """Convert #RRGGBB hex color to (curses_color, attribute).

    Analyzes the hex color's RGB components and brightness to
    determine the closest curses 8-color match and appropriate
    attribute (A_BOLD, A_DIM, or A_NORMAL).

    Args:
        hex_color: A hex color string in #RRGGBB format.

    Returns:
        A tuple of (curses_color_constant, curses_attribute).

    Raises:
        ValueError: If hex_color is not a valid #RRGGBB format string.

    Examples:
        >>> hex_to_curses("#FF0000")  # Pure red
        (1, curses.A_BOLD)
        >>> hex_to_curses("#000000")  # Black
        (0, curses.A_DIM)
        >>> hex_to_curses("#808080")  # Gray
        (7, curses.A_DIM)
    """
    # Validate input format
    if not isinstance(hex_color, str):
        raise ValueError(
            f"hex_color must be a string, got {type(hex_color).__name__}"
        )

    if not _HEX_COLOR_PATTERN.match(hex_color):
        raise ValueError(
            f"Invalid hex color format: {hex_color!r}. "
            "Expected #RRGGBB format (e.g., '#FF0000')."
        )

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


class ColorPairLimitError(Exception):
    """Raised when the color pair limit is reached and cannot be recovered."""

    pass


class ColorManager:
    """Manages curses color pairs and X11 color name translation.

    Curses requires pre-initialized color pairs for foreground/background
    combinations. This class maintains a dynamic registry of color pairs
    and handles translation from X11 color names to curses constants.

    The manager tracks color pair usage and implements LRU eviction when
    the terminal's color pair limit is reached.

    Attributes:
        _pairs: Dictionary mapping (fg, bg) tuples to pair numbers.
        _next_pair: Next available pair number (pair 0 is reserved).
        _pair_usage: List tracking pair usage order for LRU eviction.
        _max_pairs: Maximum number of color pairs allowed.

    Example:
        >>> manager = ColorManager()
        >>> pair = manager.get_pair(curses.COLOR_RED, curses.COLOR_BLACK)
        >>> color, attr = manager.name_to_curses("lime")
        >>> manager.reset()  # Clear for testing
    """

    # Default max pairs if curses.COLOR_PAIRS is not available
    DEFAULT_MAX_PAIRS = 256

    def __init__(self, max_pairs: int | None = None) -> None:
        """Initialize the ColorManager with empty pair registry.

        Args:
            max_pairs: Maximum number of color pairs to use. If None,
                uses curses.COLOR_PAIRS - 1 (pair 0 is reserved).
        """
        self._pairs: dict[tuple[int, int], int] = {}
        self._reverse_pairs: dict[int, tuple[int, int]] = {}  # pair_num -> (fg, bg)
        self._next_pair: int = 1  # Pair 0 is reserved by curses
        self._pair_usage: list[int] = []  # Track usage order for LRU

        # Determine max pairs from curses or use provided/default
        if max_pairs is not None:
            self._max_pairs = max_pairs
        else:
            try:
                # curses.COLOR_PAIRS includes pair 0, so subtract 1
                self._max_pairs = getattr(curses, 'COLOR_PAIRS', self.DEFAULT_MAX_PAIRS) - 1
            except Exception:
                self._max_pairs = self.DEFAULT_MAX_PAIRS - 1

        # Ensure at least some pairs are available
        self._max_pairs = max(1, self._max_pairs)

    def get_pair(self, fg: int, bg: int) -> int:
        """Get or create a curses color pair for the given fg/bg combination.

        If the combination has not been used before, initializes a new
        curses color pair. When the color pair limit is reached, evicts
        the least recently used pair.

        Args:
            fg: Foreground curses color constant (0-7).
            bg: Background curses color constant (0-7).

        Returns:
            A curses color_pair() value that can be OR'd with attributes.

        Raises:
            ColorPairLimitError: If pair limit is reached and eviction fails.

        Example:
            >>> manager = ColorManager()
            >>> attr = manager.get_pair(curses.COLOR_WHITE, curses.COLOR_BLUE)
            >>> window.addstr(0, 0, "Hello", attr | curses.A_BOLD)
        """
        key = (fg, bg)

        if key in self._pairs:
            # Update usage tracking (move to end = most recently used)
            pair_num = self._pairs[key]
            if pair_num in self._pair_usage:
                self._pair_usage.remove(pair_num)
            self._pair_usage.append(pair_num)
            return curses.color_pair(pair_num)

        # Need to create new pair - check limit
        if len(self._pairs) >= self._max_pairs:
            # Evict least recently used pair
            self._evict_lru_pair()

        # Create new pair
        pair_num = self._next_pair
        try:
            curses.init_pair(pair_num, fg, bg)
        except curses.error as e:
            raise ColorPairLimitError(
                f"Failed to initialize color pair {pair_num}: {e}"
            ) from e

        self._pairs[key] = pair_num
        self._reverse_pairs[pair_num] = key
        self._pair_usage.append(pair_num)
        self._next_pair += 1

        return curses.color_pair(pair_num)

    def _evict_lru_pair(self) -> None:
        """Evict the least recently used color pair.

        Removes the oldest pair from tracking and allows its pair number
        to be reused.
        """
        if not self._pair_usage:
            return

        # Get least recently used pair number
        lru_pair = self._pair_usage.pop(0)

        # Find and remove from pairs dict
        if lru_pair in self._reverse_pairs:
            key = self._reverse_pairs.pop(lru_pair)
            self._pairs.pop(key, None)

    @property
    def pair_count(self) -> int:
        """Return the number of active color pairs."""
        return len(self._pairs)

    @property
    def max_pairs(self) -> int:
        """Return the maximum number of color pairs."""
        return self._max_pairs

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
        self._reverse_pairs.clear()
        self._pair_usage.clear()
        self._next_pair = 1
