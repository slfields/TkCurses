"""Geometry calculations for TkCurses internals.

Provides cell-based geometry primitives for widget positioning
and sizing in terminal space. All coordinates are in character
cells (columns, rows), not pixels.

This module provides the foundational geometry types used by
the Pack, Grid, and Place geometry managers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, NamedTuple


class Point(NamedTuple):
    """A point in cell coordinates.

    Attributes:
        x: Column position (0-based from left).
        y: Row position (0-based from top).

    Example:
        >>> p = Point(10, 5)
        >>> p.x, p.y
        (10, 5)
    """

    x: int
    y: int

    def offset(self, dx: int, dy: int) -> Point:
        """Return a new point offset by (dx, dy).

        Args:
            dx: Column offset.
            dy: Row offset.

        Returns:
            New Point at (x + dx, y + dy).
        """
        return Point(self.x + dx, self.y + dy)

    def __add__(self, other: Point | tuple[int, int]) -> Point:
        """Add two points (vector addition)."""
        if isinstance(other, tuple):
            return Point(self.x + other[0], self.y + other[1])
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Point | tuple[int, int]) -> Point:
        """Subtract two points (vector subtraction)."""
        if isinstance(other, tuple):
            return Point(self.x - other[0], self.y - other[1])
        return Point(self.x - other.x, self.y - other.y)


class Size(NamedTuple):
    """A size in cell dimensions.

    Attributes:
        width: Width in columns.
        height: Height in rows.

    Example:
        >>> s = Size(80, 24)
        >>> s.width, s.height
        (80, 24)
    """

    width: int
    height: int

    @property
    def area(self) -> int:
        """Return the area (width * height)."""
        return self.width * self.height

    def __add__(self, other: Size | tuple[int, int]) -> Size:
        """Add two sizes."""
        if isinstance(other, tuple):
            return Size(self.width + other[0], self.height + other[1])
        return Size(self.width + other.width, self.height + other.height)

    def __sub__(self, other: Size | tuple[int, int]) -> Size:
        """Subtract two sizes (clamped to 0)."""
        if isinstance(other, tuple):
            return Size(max(0, self.width - other[0]), max(0, self.height - other[1]))
        return Size(max(0, self.width - other.width), max(0, self.height - other.height))


@dataclass(frozen=True, slots=True)
class Padding:
    """Padding around a widget in cell units.

    Attributes:
        left: Left padding in columns.
        top: Top padding in rows.
        right: Right padding in columns.
        bottom: Bottom padding in rows.

    Example:
        >>> p = Padding(1, 1, 1, 1)  # 1 cell padding all around
        >>> p.horizontal
        2
        >>> p.vertical
        2
    """

    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0

    @classmethod
    def uniform(cls, value: int) -> Padding:
        """Create uniform padding on all sides.

        Args:
            value: Padding value for all sides.

        Returns:
            Padding with equal values on all sides.
        """
        return cls(value, value, value, value)

    @classmethod
    def symmetric(cls, horizontal: int, vertical: int) -> Padding:
        """Create symmetric padding.

        Args:
            horizontal: Padding for left and right.
            vertical: Padding for top and bottom.

        Returns:
            Padding with symmetric values.
        """
        return cls(horizontal, vertical, horizontal, vertical)

    @property
    def horizontal(self) -> int:
        """Total horizontal padding (left + right)."""
        return self.left + self.right

    @property
    def vertical(self) -> int:
        """Total vertical padding (top + bottom)."""
        return self.top + self.bottom

    @property
    def size(self) -> Size:
        """Total size consumed by padding."""
        return Size(self.horizontal, self.vertical)


@dataclass(frozen=True, slots=True)
class Rect:
    """A rectangle in cell coordinates.

    Represents a rectangular region with position and size.
    All values are in character cell units.

    Attributes:
        x: Left column position.
        y: Top row position.
        width: Width in columns.
        height: Height in rows.

    Example:
        >>> r = Rect(10, 5, 20, 10)
        >>> r.right, r.bottom
        (30, 15)
        >>> Point(15, 8) in r
        True
    """

    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_points(cls, p1: Point, p2: Point) -> Rect:
        """Create a rectangle from two corner points.

        The points can be any two opposite corners; the
        rectangle will be normalized.

        Args:
            p1: First corner point.
            p2: Second corner point.

        Returns:
            Rect spanning the two points.
        """
        x1, x2 = min(p1.x, p2.x), max(p1.x, p2.x)
        y1, y2 = min(p1.y, p2.y), max(p1.y, p2.y)
        return cls(x1, y1, x2 - x1, y2 - y1)

    @classmethod
    def from_ltrb(cls, left: int, top: int, right: int, bottom: int) -> Rect:
        """Create a rectangle from left/top/right/bottom coordinates.

        Args:
            left: Left edge column.
            top: Top edge row.
            right: Right edge column (exclusive).
            bottom: Bottom edge row (exclusive).

        Returns:
            Rect with the specified bounds.
        """
        return cls(left, top, right - left, bottom - top)

    @property
    def left(self) -> int:
        """Left edge column."""
        return self.x

    @property
    def top(self) -> int:
        """Top edge row."""
        return self.y

    @property
    def right(self) -> int:
        """Right edge column (exclusive)."""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """Bottom edge row (exclusive)."""
        return self.y + self.height

    @property
    def position(self) -> Point:
        """Top-left corner position."""
        return Point(self.x, self.y)

    @property
    def size(self) -> Size:
        """Size of the rectangle."""
        return Size(self.width, self.height)

    @property
    def center(self) -> Point:
        """Center point (integer division)."""
        return Point(self.x + self.width // 2, self.y + self.height // 2)

    @property
    def area(self) -> int:
        """Area of the rectangle."""
        return self.width * self.height

    @property
    def is_empty(self) -> bool:
        """True if rectangle has zero area."""
        return self.width <= 0 or self.height <= 0

    def contains_point(self, point: Point | tuple[int, int]) -> bool:
        """Check if a point is inside the rectangle.

        Args:
            point: Point to test.

        Returns:
            True if point is inside (inclusive of edges).
        """
        if isinstance(point, tuple):
            px, py = point
        else:
            px, py = point.x, point.y
        return self.x <= px < self.right and self.y <= py < self.bottom

    def __contains__(self, item: Point | tuple[int, int]) -> bool:
        """Support 'point in rect' syntax."""
        return self.contains_point(item)

    def contains_rect(self, other: Rect) -> bool:
        """Check if another rectangle is fully inside this one.

        Args:
            other: Rectangle to test.

        Returns:
            True if other is entirely contained within self.
        """
        return (
            self.x <= other.x
            and self.y <= other.y
            and other.right <= self.right
            and other.bottom <= self.bottom
        )

    def intersects(self, other: Rect) -> bool:
        """Check if two rectangles overlap.

        Args:
            other: Rectangle to test.

        Returns:
            True if rectangles have any overlapping area.
        """
        return not (
            self.right <= other.x
            or other.right <= self.x
            or self.bottom <= other.y
            or other.bottom <= self.y
        )

    def intersection(self, other: Rect) -> Rect | None:
        """Compute the intersection of two rectangles.

        Args:
            other: Rectangle to intersect with.

        Returns:
            Intersection rectangle, or None if no overlap.
        """
        x1 = max(self.x, other.x)
        y1 = max(self.y, other.y)
        x2 = min(self.right, other.right)
        y2 = min(self.bottom, other.bottom)

        if x1 < x2 and y1 < y2:
            return Rect(x1, y1, x2 - x1, y2 - y1)
        return None

    def union(self, other: Rect) -> Rect:
        """Compute the bounding rectangle of two rectangles.

        Args:
            other: Rectangle to union with.

        Returns:
            Smallest rectangle containing both.
        """
        x1 = min(self.x, other.x)
        y1 = min(self.y, other.y)
        x2 = max(self.right, other.right)
        y2 = max(self.bottom, other.bottom)
        return Rect(x1, y1, x2 - x1, y2 - y1)

    def offset(self, dx: int, dy: int) -> Rect:
        """Return a new rectangle offset by (dx, dy).

        Args:
            dx: Column offset.
            dy: Row offset.

        Returns:
            New Rect at offset position.
        """
        return Rect(self.x + dx, self.y + dy, self.width, self.height)

    def move_to(self, x: int, y: int) -> Rect:
        """Return a new rectangle moved to position (x, y).

        Args:
            x: New left column.
            y: New top row.

        Returns:
            New Rect at the specified position.
        """
        return Rect(x, y, self.width, self.height)

    def resize(self, width: int, height: int) -> Rect:
        """Return a new rectangle with different size.

        Args:
            width: New width.
            height: New height.

        Returns:
            New Rect with specified size at same position.
        """
        return Rect(self.x, self.y, width, height)

    def inset(self, padding: Padding | int) -> Rect:
        """Return a new rectangle inset by padding.

        Args:
            padding: Padding to remove from edges, or uniform value.

        Returns:
            Smaller Rect with padding removed.
        """
        if isinstance(padding, int):
            padding = Padding.uniform(padding)

        return Rect(
            self.x + padding.left,
            self.y + padding.top,
            max(0, self.width - padding.horizontal),
            max(0, self.height - padding.vertical),
        )

    def outset(self, padding: Padding | int) -> Rect:
        """Return a new rectangle expanded by padding.

        Args:
            padding: Padding to add to edges, or uniform value.

        Returns:
            Larger Rect with padding added.
        """
        if isinstance(padding, int):
            padding = Padding.uniform(padding)

        return Rect(
            self.x - padding.left,
            self.y - padding.top,
            self.width + padding.horizontal,
            self.height + padding.vertical,
        )

    def clamp(self, bounds: Rect) -> Rect:
        """Return a new rectangle clamped to fit within bounds.

        The rectangle is moved to fit inside bounds if possible,
        and shrunk if necessary.

        Args:
            bounds: Rectangle to clamp within.

        Returns:
            New Rect that fits within bounds.
        """
        # Clamp size first
        w = min(self.width, bounds.width)
        h = min(self.height, bounds.height)

        # Then clamp position
        x = max(bounds.x, min(self.x, bounds.right - w))
        y = max(bounds.y, min(self.y, bounds.bottom - h))

        return Rect(x, y, w, h)

    def iter_cells(self) -> Iterator[Point]:
        """Iterate over all cell positions in the rectangle.

        Yields:
            Point for each cell, row by row.
        """
        for row in range(self.y, self.bottom):
            for col in range(self.x, self.right):
                yield Point(col, row)

    def to_geometry_string(self) -> str:
        """Convert to tkinter-style geometry string.

        Returns:
            String in format "WxH+X+Y".

        Example:
            >>> Rect(10, 5, 80, 24).to_geometry_string()
            '80x24+10+5'
        """
        return f'{self.width}x{self.height}+{self.x}+{self.y}'

    @classmethod
    def from_geometry_string(cls, geometry: str) -> Rect:
        """Parse a tkinter-style geometry string.

        Args:
            geometry: String in format "WxH+X+Y" or "WxH".

        Returns:
            Rect with parsed dimensions.

        Raises:
            ValueError: If geometry string is invalid.

        Example:
            >>> Rect.from_geometry_string('80x24+10+5')
            Rect(x=10, y=5, width=80, height=24)
        """
        # Handle "WxH+X+Y" or "WxH-X-Y" or just "WxH"
        import re

        match = re.match(
            r'^(\d+)x(\d+)(?:([+-])(\d+)([+-])(\d+))?$',
            geometry.strip(),
        )
        if not match:
            raise ValueError(f'Invalid geometry string: {geometry!r}')

        width = int(match.group(1))
        height = int(match.group(2))

        if match.group(3) is not None:
            x_sign = -1 if match.group(3) == '-' else 1
            x = x_sign * int(match.group(4))
            y_sign = -1 if match.group(5) == '-' else 1
            y = y_sign * int(match.group(6))
        else:
            x, y = 0, 0

        return cls(x, y, width, height)


@dataclass(frozen=True, slots=True)
class SizeConstraints:
    """Size constraints for widget sizing.

    Specifies minimum and maximum bounds for width and height.
    Used by geometry managers to respect widget size limits.

    Attributes:
        min_width: Minimum width (0 for no minimum).
        min_height: Minimum height (0 for no minimum).
        max_width: Maximum width (None for no maximum).
        max_height: Maximum height (None for no maximum).

    Example:
        >>> c = SizeConstraints(min_width=10, max_width=100)
        >>> c.clamp_width(5)
        10
        >>> c.clamp_width(150)
        100
    """

    min_width: int = 0
    min_height: int = 0
    max_width: int | None = None
    max_height: int | None = None

    def clamp_width(self, width: int) -> int:
        """Clamp a width value to constraints.

        Args:
            width: Width to clamp.

        Returns:
            Width clamped to min/max bounds.
        """
        width = max(self.min_width, width)
        if self.max_width is not None:
            width = min(self.max_width, width)
        return width

    def clamp_height(self, height: int) -> int:
        """Clamp a height value to constraints.

        Args:
            height: Height to clamp.

        Returns:
            Height clamped to min/max bounds.
        """
        height = max(self.min_height, height)
        if self.max_height is not None:
            height = min(self.max_height, height)
        return height

    def clamp_size(self, size: Size) -> Size:
        """Clamp a size to constraints.

        Args:
            size: Size to clamp.

        Returns:
            Size with both dimensions clamped.
        """
        return Size(
            self.clamp_width(size.width),
            self.clamp_height(size.height),
        )

    @property
    def min_size(self) -> Size:
        """Minimum size as a Size object."""
        return Size(self.min_width, self.min_height)

    @property
    def max_size(self) -> Size | None:
        """Maximum size as a Size object, or None if unbounded."""
        if self.max_width is None or self.max_height is None:
            return None
        return Size(self.max_width, self.max_height)


def center_in_rect(inner: Size, outer: Rect) -> Point:
    """Calculate position to center one size within a rectangle.

    Args:
        inner: Size to center.
        outer: Rectangle to center within.

    Returns:
        Point for top-left of centered position.

    Example:
        >>> center_in_rect(Size(10, 5), Rect(0, 0, 80, 24))
        Point(x=35, y=9)
    """
    x = outer.x + (outer.width - inner.width) // 2
    y = outer.y + (outer.height - inner.height) // 2
    return Point(x, y)


def align_in_rect(
    inner: Size,
    outer: Rect,
    anchor: str = 'center',
) -> Point:
    """Calculate position to align a size within a rectangle.

    Args:
        inner: Size to position.
        outer: Rectangle to position within.
        anchor: Tkinter-style anchor ('n', 's', 'e', 'w', 'ne', 'nw',
                'se', 'sw', 'center'). Default 'center'.

    Returns:
        Point for top-left of aligned position.

    Example:
        >>> align_in_rect(Size(10, 5), Rect(0, 0, 80, 24), 'nw')
        Point(x=0, y=0)
        >>> align_in_rect(Size(10, 5), Rect(0, 0, 80, 24), 'se')
        Point(x=70, y=19)
    """
    anchor = anchor.lower()

    # Handle 'center' specially since it contains 'e'
    if anchor == 'center':
        x = outer.x + (outer.width - inner.width) // 2
        y = outer.y + (outer.height - inner.height) // 2
        return Point(x, y)

    # Horizontal alignment
    if 'w' in anchor:
        x = outer.x
    elif 'e' in anchor:
        x = outer.right - inner.width
    else:  # center horizontally
        x = outer.x + (outer.width - inner.width) // 2

    # Vertical alignment
    if 'n' in anchor:
        y = outer.y
    elif 's' in anchor:
        y = outer.bottom - inner.height
    else:  # center vertically
        y = outer.y + (outer.height - inner.height) // 2

    return Point(x, y)


def distribute_space(
    total: int,
    count: int,
    weights: list[int] | None = None,
) -> list[int]:
    """Distribute space among items based on weights.

    Args:
        total: Total space to distribute.
        count: Number of items.
        weights: Weight for each item. If None, equal weights.

    Returns:
        List of sizes for each item.

    Example:
        >>> distribute_space(100, 3)
        [34, 33, 33]
        >>> distribute_space(100, 3, [1, 2, 1])
        [25, 50, 25]
    """
    if count <= 0:
        return []

    if weights is None:
        weights = [1] * count

    if len(weights) != count:
        raise ValueError(f'weights length {len(weights)} != count {count}')

    total_weight = sum(weights)
    if total_weight <= 0:
        return [0] * count

    # Distribute proportionally
    result = []
    remaining = total
    remaining_weight = total_weight

    for weight in weights:
        if remaining_weight > 0:
            share = (remaining * weight + remaining_weight - 1) // remaining_weight
        else:
            share = 0
        result.append(share)
        remaining -= share
        remaining_weight -= weight

    return result
