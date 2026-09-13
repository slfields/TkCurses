"""Drawing on a grid of half-cells, and the items that describe what to draw.

A Canvas is the one widget that wants pixels rather than characters, and a
terminal has none. What it does have is ``▀`` and ``▄``, which divide a cell
across the middle - and because a character cell is about twice as tall as it
is wide, each of those halves is very nearly **square**. That is the whole
idea behind this module: the canvas is a plane of half-cells, so a circle
comes out round rather than as the tall ellipse a one-cell-per-unit canvas
would give.

Two coordinate systems meet here, and confusing them is the only real hazard:

**Pixels** are the canvas's own units. One pixel is one cell wide and half a
cell tall. Item coordinates are in these.

**Cells** are what the terminal has. Column ``x`` holds pixel column ``x``;
row ``y`` holds pixel rows ``2y`` and ``2y + 1``.

Rasterising and compositing are kept apart. The rasterisers turn geometry into
a set of pixels; :func:`compose` folds each pair of pixel rows into one cell,
a glyph and up to two colours. Neither touches curses, so the awkward cases -
an oval one pixel tall, a line steeper than it is wide, two colours meeting
inside a single cell - can be exercised directly.
"""

from __future__ import annotations

import math
from itertools import pairwise
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping, Sequence

__all__ = [
    "FULL",
    "LOWER",
    "UPPER",
    "bbox_of",
    "compose",
    "filled_oval_pixels",
    "filled_polygon_pixels",
    "filled_rectangle_pixels",
    "line_pixels",
    "oval_pixels",
    "polygon_pixels",
    "rectangle_pixels",
]

#: The three glyphs a composed cell can use. A cell with ink in one half only
#: uses the matching half block; a cell with ink in both uses the full block
#: when the two agree on colour, and the upper half otherwise - the lower
#: pixel then showing through as the background.
UPPER = "▀"
LOWER = "▄"
FULL = "█"

#: A pixel with no colour of its own takes the canvas's foreground. Kept as a
#: distinct value rather than an empty string so that "no colour named" and
#: "the colour named is empty" stay different questions.
DEFAULT = ""


def compose(
    pixels: Mapping[tuple[int, int], str],
) -> dict[tuple[int, int], tuple[str, str, str | None]]:
    """Fold a plane of pixels into cells.

    Args:
        pixels: Colour of each lit pixel, by ``(x, y)``. Pixels not present
            are unlit and let the canvas background through.

    Returns:
        For each cell that has any ink, ``(column, row)`` mapped to the glyph
        to draw and the two colours it needs: the foreground, and a background
        which is None when the cell's unlit half should show the canvas
        background rather than a colour of its own.
    """
    cells: dict[tuple[int, int], tuple[str, str, str | None]] = {}
    rows = {(x, y // 2) for x, y in pixels}
    for x, row in rows:
        top = pixels.get((x, row * 2))
        bottom = pixels.get((x, row * 2 + 1))
        if top is not None and bottom is not None:
            if top == bottom:
                cells[(x, row)] = (FULL, top, None)
            else:
                cells[(x, row)] = (UPPER, top, bottom)
        elif top is not None:
            cells[(x, row)] = (UPPER, top, None)
        elif bottom is not None:
            cells[(x, row)] = (LOWER, bottom, None)
    return cells


def bbox_of(pixels: Iterable[tuple[int, int]]) -> tuple[int, int, int, int] | None:
    """The rectangle a set of pixels occupies, or None if there are none."""
    points = list(pixels)
    if not points:
        return None
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return (min(xs), min(ys), max(xs), max(ys))


# --------------------------------------------------------------------- lines


def line_pixels(points: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    """Every pixel on a run of connected straight segments.

    Ordered, and without the duplicate that would otherwise appear where one
    segment ends and the next begins.
    """
    if not points:
        return []
    if len(points) == 1:
        return [points[0]]
    drawn: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for (x0, y0), (x1, y1) in pairwise(points):
        for pixel in _segment(x0, y0, x1, y1):
            if pixel not in seen:
                seen.add(pixel)
                drawn.append(pixel)
    return drawn


def _segment(x0: int, y0: int, x1: int, y1: int) -> Iterator[tuple[int, int]]:
    """Bresenham's line, one pixel at a time.

    The integer form, so a line is the same set of pixels whichever end it is
    drawn from - which is what stops a redrawn shape shifting by a pixel.
    """
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    step_x = 1 if x0 < x1 else -1
    step_y = 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        yield (x0, y0)
        if x0 == x1 and y0 == y1:
            return
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x0 += step_x
        if doubled <= dx:
            error += dx
            y0 += step_y


# ---------------------------------------------------------------- rectangles


def rectangle_pixels(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """The outline of a rectangle, corners included.

    The two corners may be given in any order, because a rectangle dragged
    out with a mouse arrives in whichever order the drag went.
    """
    left, right = sorted((x0, x1))
    top, bottom = sorted((y0, y1))
    return line_pixels(
        [(left, top), (right, top), (right, bottom), (left, bottom), (left, top)]
    )


def filled_rectangle_pixels(
    x0: int, y0: int, x1: int, y1: int
) -> list[tuple[int, int]]:
    """Every pixel inside a rectangle, outline included."""
    left, right = sorted((x0, x1))
    top, bottom = sorted((y0, y1))
    return [(x, y) for y in range(top, bottom + 1) for x in range(left, right + 1)]


# --------------------------------------------------------------------- ovals


def oval_pixels(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """The outline of the ellipse inscribed in a rectangle.

    Walked round the perimeter rather than stepped along one axis: stepping
    by x leaves gaps wherever the curve is steeper than one pixel per column,
    which on a small oval is most of it. The number of steps is set from the
    perimeter so consecutive samples are always less than a pixel apart, and
    the result is deduplicated.
    """
    left, right = sorted((x0, x1))
    top, bottom = sorted((y0, y1))
    radius_x, radius_y = (right - left) / 2, (bottom - top) / 2
    if radius_x < 0.5 or radius_y < 0.5:
        # Too thin to be a curve at all; Tk draws the degenerate case as the
        # rectangle it was given, and so does this.
        return rectangle_pixels(left, top, right, bottom)
    centre_x, centre_y = left + radius_x, top + radius_y
    steps = max(16, int(8 * (radius_x + radius_y)))
    drawn: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for step in range(steps):
        angle = 2 * math.pi * step / steps
        pixel = (
            round(centre_x + radius_x * math.cos(angle)),
            round(centre_y + radius_y * math.sin(angle)),
        )
        if pixel not in seen:
            seen.add(pixel)
            drawn.append(pixel)
    return drawn


def filled_oval_pixels(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Every pixel inside an ellipse, outline included."""
    left, right = sorted((x0, x1))
    top, bottom = sorted((y0, y1))
    radius_x, radius_y = (right - left) / 2, (bottom - top) / 2
    if radius_x < 0.5 or radius_y < 0.5:
        return filled_rectangle_pixels(left, top, right, bottom)
    centre_x, centre_y = left + radius_x, top + radius_y
    drawn: list[tuple[int, int]] = []
    for y in range(top, bottom + 1):
        offset = (y - centre_y) / radius_y
        if abs(offset) > 1:
            continue
        half = radius_x * math.sqrt(max(0.0, 1 - offset * offset))
        drawn.extend(
            (x, y) for x in range(math.ceil(centre_x - half), int(centre_x + half) + 1)
        )
    # The scanlines can fall short of the drawn outline by a pixel where the
    # curve is steep, which leaves a filled shape with a ragged edge.
    return _dedupe(drawn + oval_pixels(x0, y0, x1, y1))


# ------------------------------------------------------------------ polygons


def polygon_pixels(points: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    """The outline of a polygon, closed back to its first point."""
    if len(points) < 2:
        return list(points)
    return line_pixels([*points, points[0]])


def filled_polygon_pixels(
    points: Sequence[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Every pixel inside a polygon, outline included.

    Scanline with the even-odd rule, which is what Tk uses and what makes a
    self-intersecting polygon come out with a hole in it rather than solid.
    """
    if len(points) < 3:
        return polygon_pixels(points)
    ys = [y for _, y in points]
    drawn: list[tuple[int, int]] = []
    for y in range(min(ys), max(ys) + 1):
        crossings: list[float] = []
        for (x0, y0), (x1, y1) in zip(points, [*points[1:], points[0]], strict=True):
            if y0 == y1:
                continue
            low, high = sorted((y0, y1))
            # Half-open in y, so a vertex shared by two edges is counted once
            # and the parity stays right.
            if low <= y < high:
                crossings.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
        crossings.sort()
        for start, stop in zip(crossings[::2], crossings[1::2], strict=False):
            drawn.extend((x, y) for x in range(math.ceil(start), int(stop) + 1))
    return _dedupe(drawn + polygon_pixels(points))


def _dedupe(pixels: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Drop repeats, keeping the order the pixels were produced in."""
    seen: set[tuple[int, int]] = set()
    kept: list[tuple[int, int]] = []
    for pixel in pixels:
        if pixel not in seen:
            seen.add(pixel)
            kept.append(pixel)
    return kept
