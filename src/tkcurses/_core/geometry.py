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

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

__all__ = [
    "BORDER_WIDTH",
    "Container",
    "Insets",
    "Managed",
    "Pad",
    "Point",
    "Rect",
    "Size",
    "clamp",
    "clip_text",
    "content_rect",
    "content_size",
    "parse_distance",
    "parse_pad",
    "parse_single_pad",
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


class Managed(Protocol):
    """What a geometry manager needs of a widget it places.

    Derived from what pack, grid, place and paned actually use rather than from
    what a widget happens to have - measured with ast across the four modules,
    which touch exactly these four members on a widget and nothing else. Those
    parameters were ``Any``, which meant the checker verified nothing about
    them: a typo in a method name, or a value that was never a widget at all,
    would have reached a test rather than mypy.

    Deliberately NOT the whole of Misc. A geometry manager has no business with
    a widget's options, bindings or children, and saying so in the type is how
    that stays true. TkCurses-d40.
    """

    master: Any

    def winfo_reqwidth(self) -> int:
        """How wide the widget would like to be."""
        ...

    def winfo_reqheight(self) -> int:
        """How tall the widget would like to be."""
        ...

    def _allocate(self, rect: Rect) -> None:
        """Take the region the manager decided on."""
        ...


class Container(Protocol):
    """What ``place`` needs of the widget it measures against.

    Separate from :class:`Managed` because the two are used for different
    things and only ``place`` needs this one: relative placement is computed
    against the container's screen position and current size, where the other
    three managers only ever hand out parcels of an area they were given.
    Measured, again - ``pack``, ``grid`` and ``paned`` never touch these.
    """

    def winfo_rootx(self) -> int:
        """The container's left edge in screen cells."""
        ...

    def winfo_rooty(self) -> int:
        """The container's top edge in screen cells."""
        ...

    def winfo_width(self) -> int:
        """How wide the container is now."""
        ...

    def winfo_height(self) -> int:
        """How tall the container is now."""
        ...


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
class Pad:
    """One axis of a geometry manager's ``padx`` or ``pady``.

    Tk's external padding is two distances, not one: ``padx=(0, 1)`` pads the
    right of a widget and not its left. A single number sets both. The pair is
    the only form that can express either, so it is what gets stored, and the
    read-back form is derived from it rather than remembered separately -
    which is also what Tk does, reporting ``(2, 2)`` back as plain ``2``.
    """

    before: int = 0
    after: int = 0

    def __post_init__(self) -> None:
        if self.before < 0 or self.after < 0:
            raise ValueError(f"negative pad: {self.before}, {self.after}")

    @classmethod
    def uniform(cls, amount: int) -> Pad:
        """The same distance on both sides, which is what a number means."""
        return cls(amount, amount)

    @property
    def total(self) -> int:
        """Cells consumed on this axis, both sides together."""
        return self.before + self.after

    @property
    def value(self) -> int | tuple[int, int]:
        """What ``pack_info`` and ``grid_info`` report, in Tk's own form.

        A number when both sides match, a two-tuple when they do not. Measured
        against Tcl/Tk 9.0.2: ``padx=(2, 2)`` reads back as ``2``, ``padx="2 8"`` as
        ``(2, 8)``.
        """
        return self.before if self.before == self.after else (self.before, self.after)


def parse_distance(value: object) -> int:
    """One of Tk's screen distances, in cells.

    Rounds rather than truncates, as Tk does: ``2.6`` is three cells and
    ``0.5`` is one. Tk's unit suffixes (``2c``, ``1i``) have no meaning on a
    character grid and are not accepted - TkCurses-2qo.

    Raises:
        ValueError: If the value is not a number or a string holding one.
    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if not isinstance(value, (float, str)):
        raise ValueError(f"not a screen distance: {value!r}")
    try:
        number = float(value)
    except ValueError:
        raise ValueError(f"not a screen distance: {value!r}") from None
    return math.floor(number + 0.5)


def _pad_parts(value: object) -> list[object]:
    """The parts of a pad specification, before any of them are converted.

    A number is one part; a string is split on whitespace, which is how Tk
    spells a pair in a single argument; any other sequence is its own parts.
    """
    if isinstance(value, (int, float)):
        return [value]
    if isinstance(value, str):
        return list(value.split())
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def parse_pad(value: object) -> Pad:
    """A geometry manager's ``padx`` or ``pady``, as a distance per side.

    Accepts every form Tk does: a number, a one- or two-element sequence, or a
    string holding one or two numbers. One part pads both sides equally.

    Raises:
        ValueError: With Tk's own wording, so the caller can hand the message
            straight to a ``TclError``.
    """
    parts = _pad_parts(value)
    if len(parts) not in (1, 2):
        raise ValueError("wrong number of parts to pad specification")
    distances = []
    for part in parts:
        try:
            distance = parse_distance(part)
        except ValueError:
            distance = -1  # reported the same way a negative one is
        if distance < 0:
            raise ValueError(
                f'bad pad value "{part}": must be positive screen distance'
            )
        distances.append(distance)
    if len(distances) == 1:
        return Pad.uniform(distances[0])
    return Pad(distances[0], distances[1])


def parse_single_pad(value: object, option: str) -> int:
    """A geometry manager's ``ipadx`` or ``ipady``, which takes one distance.

    Internal padding has no two-value form - measured, Tcl/Tk 9.0.2 rejects
    ``ipadx=(2, 8)`` outright where it accepts ``padx=(2, 8)``. The asymmetry
    is Tk's, so it is kept rather than tidied away.

    A sequence is joined and parsed as the one distance Tcl would have been
    handed, which is why ``ipadx=(2,)`` is accepted and ``ipadx=(2, 8)`` is
    not: tkinter stringifies both, and only the first spells a distance. The
    first version of this rejected the one-element form, which the differential
    probe against real Tk caught.

    Raises:
        ValueError: With Tk's own wording, which names the option and quotes
            the whole value rather than the offending part.
    """
    spec = _as_tcl(value) if isinstance(value, Iterable) else value
    try:
        distance = parse_distance(spec)
    except ValueError:
        distance = -1
    if distance < 0:
        raise ValueError(
            f'bad {option} value "{_as_tcl(value)}": must be positive screen distance'
        )
    return distance


def _as_tcl(value: object) -> str:
    """A value as Tcl would have seen it, for quoting in an error message."""
    if isinstance(value, str):
        return value
    if isinstance(value, Iterable):
        return " ".join(str(part) for part in value)
    return str(value)


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
