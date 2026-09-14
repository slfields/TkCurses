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

"""Character-cell geometry: rectangles, insets, and content areas.

Every coordinate in TkCurses is a character cell, so all arithmetic here is
integral. The module is deliberately free of curses imports: geometry is pure
computation, which keeps it cheap to test exhaustively and lets layout bugs be
found without a terminal.

The central rule it encodes comes from ARCHITECTURE.md, "Window Content
Areas": a bordered window's outermost cells belong to the border, so a
``width x height`` window offers ``(width - 2) x (height - 2)`` usable cells
starting at ``(1, 1)``. Widgets that ignore this overwrite their own frame.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "BORDER_WIDTH",
    "Insets",
    "Point",
    "Rect",
    "Size",
    "clamp",
    "clip_text",
    "content_rect",
    "content_size",
]

#: Cells consumed by a border on one side. Curses borders are one cell wide.
BORDER_WIDTH = 1


def clamp(value: int, low: int, high: int) -> int:
    """Constrain ``value`` to the inclusive range ``[low, high]``.

    Raises:
        ValueError: If ``low`` exceeds ``high``.
    """
    if low > high:
        raise ValueError(f"empty range: [{low}, {high}]")
    return max(low, min(value, high))


@dataclass(frozen=True, slots=True)
class Point:
    """A cell coordinate, with ``x`` across and ``y`` down."""

    x: int = 0
    y: int = 0

    def translated(self, dx: int, dy: int) -> Point:
        """Return this point moved by ``(dx, dy)``."""
        return Point(self.x + dx, self.y + dy)


@dataclass(frozen=True, slots=True)
class Size:
    """A width and height in cells.

    Dimensions are never negative: a widget cannot be smaller than nothing, and
    allowing negatives lets a subtraction error propagate silently into layout.
    """

    width: int = 0
    height: int = 0

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError(f"negative size: {self.width}x{self.height}")

    @property
    def is_empty(self) -> bool:
        """True if the size encloses no cells."""
        return self.width == 0 or self.height == 0

    @property
    def area(self) -> int:
        """Number of cells enclosed."""
        return self.width * self.height

    def grown(self, dw: int, dh: int) -> Size:
        """Return this size enlarged by ``(dw, dh)``, clamped at zero."""
        return Size(max(0, self.width + dw), max(0, self.height + dh))


@dataclass(frozen=True, slots=True)
class Insets:
    """Per-edge spacing in cells, used for borders and padding."""

    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0

    def __post_init__(self) -> None:
        if min(self.left, self.top, self.right, self.bottom) < 0:
            raise ValueError(f"negative inset: {self}")

    @classmethod
    def uniform(cls, amount: int) -> Insets:
        """Insets with the same value on all four edges."""
        return cls(amount, amount, amount, amount)

    @classmethod
    def symmetric(cls, horizontal: int = 0, vertical: int = 0) -> Insets:
        """Insets with matching left/right and top/bottom values."""
        return cls(horizontal, vertical, horizontal, vertical)

    @property
    def width(self) -> int:
        """Total cells consumed horizontally."""
        return self.left + self.right

    @property
    def height(self) -> int:
        """Total cells consumed vertically."""
        return self.top + self.bottom

    def __add__(self, other: Insets) -> Insets:
        """Combine two sets of insets edge by edge."""
        return Insets(
            self.left + other.left,
            self.top + other.top,
            self.right + other.right,
            self.bottom + other.bottom,
        )


@dataclass(frozen=True, slots=True)
class Rect:
    """A rectangle of cells at ``(x, y)`` extending ``width`` by ``height``.

    ``x`` and ``y`` may be negative so that a partly off-screen widget can still
    be described and then clipped; the dimensions may not.
    """

    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError(f"negative size: {self.width}x{self.height}")

    @classmethod
    def from_size(cls, size: Size, origin: Point | None = None) -> Rect:
        """Build a rectangle from a :class:`Size` at an optional origin."""
        start = origin or Point(0, 0)
        return cls(start.x, start.y, size.width, size.height)

    # ------------------------------------------------------------- edges

    @property
    def left(self) -> int:
        """Leftmost column."""
        return self.x

    @property
    def top(self) -> int:
        """Topmost row."""
        return self.y

    @property
    def right(self) -> int:
        """Rightmost column that is inside the rectangle.

        Inclusive, matching how curses addresses cells. An empty rectangle has
        no such column, so this is only meaningful when ``width`` is positive.
        """
        return self.x + self.width - 1

    @property
    def bottom(self) -> int:
        """Bottommost row that is inside the rectangle. Inclusive."""
        return self.y + self.height - 1

    @property
    def origin(self) -> Point:
        """Top-left corner."""
        return Point(self.x, self.y)

    @property
    def size(self) -> Size:
        """Dimensions, without position."""
        return Size(self.width, self.height)

    @property
    def area(self) -> int:
        """Number of cells enclosed."""
        return self.width * self.height

    @property
    def is_empty(self) -> bool:
        """True if the rectangle encloses no cells."""
        return self.width == 0 or self.height == 0

    # --------------------------------------------------------- relations

    def contains_point(self, point: Point) -> bool:
        """True if ``point`` lies inside this rectangle."""
        return (
            self.x <= point.x <= self.right and self.y <= point.y <= self.bottom
            if not self.is_empty
            else False
        )

    def contains(self, other: Rect) -> bool:
        """True if ``other`` lies entirely inside this rectangle.

        An empty rectangle is contained by anything, since it covers no cells
        that could fall outside.
        """
        if other.is_empty:
            return True
        if self.is_empty:
            return False
        return (
            other.x >= self.x
            and other.y >= self.y
            and other.right <= self.right
            and other.bottom <= self.bottom
        )

    def intersects(self, other: Rect) -> bool:
        """True if the two rectangles share at least one cell."""
        return not self.intersection(other).is_empty

    def intersection(self, other: Rect) -> Rect:
        """Return the overlapping region, empty if they do not overlap."""
        if self.is_empty or other.is_empty:
            return Rect(self.x, self.y, 0, 0)
        left = max(self.x, other.x)
        top = max(self.y, other.y)
        right = min(self.right, other.right)
        bottom = min(self.bottom, other.bottom)
        if left > right or top > bottom:
            return Rect(left, top, 0, 0)
        return Rect(left, top, right - left + 1, bottom - top + 1)

    # ------------------------------------------------------ derivations

    def translated(self, dx: int, dy: int) -> Rect:
        """Return this rectangle moved by ``(dx, dy)``."""
        return Rect(self.x + dx, self.y + dy, self.width, self.height)

    def inset(self, insets: Insets) -> Rect:
        """Return the region left after removing ``insets`` from each edge.

        Collapses to an empty rectangle rather than going negative when the
        insets exceed the available space, which is the common case for a
        widget too small to hold its own border.
        """
        width = max(0, self.width - insets.width)
        height = max(0, self.height - insets.height)
        if width == 0 or height == 0:
            return Rect(self.x + insets.left, self.y + insets.top, 0, 0)
        return Rect(self.x + insets.left, self.y + insets.top, width, height)


def content_size(size: Size, *, bordered: bool = True) -> Size:
    """Usable interior of a window of ``size``.

    A bordered window loses one cell on each edge, so a 30x8 window offers
    28x6 cells. A window too small to hold both border edges has no interior
    at all rather than a negative one.
    """
    if not bordered:
        return size
    return Size(
        max(0, size.width - 2 * BORDER_WIDTH),
        max(0, size.height - 2 * BORDER_WIDTH),
    )


def content_rect(
    rect: Rect, *, bordered: bool = True, padding: Insets | None = None
) -> Rect:
    """Region a widget may draw into, excluding border and padding.

    Content in a bordered window starts at ``(1, 1)`` relative to the window,
    per ARCHITECTURE.md "Content Coordinate Rules".
    """
    insets = Insets.uniform(BORDER_WIDTH) if bordered else Insets()
    if padding is not None:
        insets = insets + padding
    return rect.inset(insets)


def clip_text(text: str, width: int) -> str:
    """Truncate ``text`` to at most ``width`` cells.

    Widgets must not write past their content area; truncating at the source
    keeps a long label from spilling over a neighbour or a border.
    """
    if width <= 0:
        return ""
    return text[:width]
