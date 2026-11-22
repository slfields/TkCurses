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

"""The squarified treemap layout, and snapping it to character cells. Pure.

The algorithm is from Mark Bruls, Kees Huizing and Jarke J. van Wijk,
"Squarified Treemaps", in *Data Visualization 2000: Proceedings of the
Joint Eurographics and IEEE TCVG Symposium on Visualization*, Springer,
2000, pp. 33-42, implemented from the paper's description: lay the
rectangles, largest first, in a row along the shorter side of the space
left, adding each to the row while that does not make the row's worst
aspect ratio worse, then fix the row and go on in what remains.

Two things are this library's own:

- **It runs in the eye's units.** A character cell is about twice as tall
  as it is wide, so the layout is computed on a rectangle ``aspect`` times
  taller than the cells it covers and scaled back; tiles then look square
  rather than being square in cells.
- **It snaps to whole cells by rounding edges, not sizes.** Every edge two
  tiles share is the same number in both, because a row starts exactly
  where the last one ended and a tile exactly where its neighbour did.
  Rounding each edge once then keeps them shared: the tiles cover the
  area with no gap and no overlap, and each edge is within half a cell of
  its exact place.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tkcurses._charts.geometry import Rect

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["CELL_ASPECT", "Span", "snapped", "squarify", "tiles"]

#: How much taller a character cell is than it is wide.
CELL_ASPECT = 2.0


@dataclass(frozen=True, slots=True)
class Span:
    """A rectangle with exact edges: left, top, right, bottom."""

    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top


def _worst(row: Sequence[float], side: float) -> float:
    """The worst aspect ratio among ``row``'s rectangles, laid along a side
    ``side`` long (the paper's *worst*)."""
    total = math.fsum(row)
    if total <= 0 or side <= 0:
        return math.inf
    side2 = side * side
    total2 = total * total
    return max(max(side2 * area / total2, total2 / (side2 * area)) for area in row)


def squarify(weights: Sequence[float], space: Span) -> list[Span | None]:
    """Rectangles for ``weights`` in ``space``, one each, in their order.

    ``weights`` should be largest first, as the paper lays them out; each
    rectangle's area is its share of ``space``. A weight that is zero or
    less gets ``None``: it takes no room.

    Raises:
        ValueError: If a weight is not finite.
    """
    if any(not math.isfinite(weight) for weight in weights):
        raise ValueError("a weight must be finite")
    out: list[Span | None] = [None] * len(weights)
    order = [i for i, weight in enumerate(weights) if weight > 0]
    total = math.fsum(weights[i] for i in order)
    if not order or space.width <= 0 or space.height <= 0:
        return out
    scale = space.width * space.height / total
    areas = {i: weights[i] * scale for i in order}

    left, top, right, bottom = space.left, space.top, space.right, space.bottom
    start = 0
    while start < len(order):
        width, height = right - left, bottom - top
        side = min(width, height)
        end = start + 1
        row = [areas[order[start]]]
        while end < len(order):
            longer = [*row, areas[order[end]]]
            if _worst(longer, side) > _worst(row, side):
                break
            row = longer
            end += 1
        last_row = end == len(order)
        row_total = math.fsum(row)
        if width >= height:
            # A column at the left, its tiles top to bottom.
            edge = right if last_row else left + row_total / height
            cursor = top
            for k, i in enumerate(order[start:end]):
                below = (
                    bottom
                    if k == end - start - 1
                    else cursor + areas[i] / (edge - left)
                )
                out[i] = Span(left, cursor, edge, below)
                cursor = below
            left = edge
        else:
            # A row along the top, its tiles left to right.
            edge = bottom if last_row else top + row_total / width
            cursor = left
            for k, i in enumerate(order[start:end]):
                after = (
                    right if k == end - start - 1 else cursor + areas[i] / (edge - top)
                )
                out[i] = Span(cursor, top, after, edge)
                cursor = after
            top = edge
        start = end
    return out


def _round(edge: float) -> int:
    """Half up, the same way for every edge."""
    return math.floor(edge + 0.5)


def snapped(span: Span) -> Rect:
    """``span`` on whole cells, each edge rounded once; it may be empty."""
    left, top = _round(span.left), _round(span.top)
    return Rect(left, top, _round(span.right) - left, _round(span.bottom) - top)


def tiles(
    weights: Sequence[float], area: Rect, aspect: float = CELL_ASPECT
) -> list[Rect | None]:
    """``weights`` squarified into ``area``, in cells, one per weight.

    Laid out ``aspect`` times taller than ``area`` is in cells, so the tiles
    look square, then scaled back and snapped. ``None`` is a weight that
    takes no room; an empty ``Rect`` one too small to have a cell.
    """
    space = Span(
        area.x, area.y * aspect, area.x + area.width, (area.y + area.height) * aspect
    )
    out: list[Rect | None] = []
    for span in squarify(weights, space):
        if span is None:
            out.append(None)
        else:
            out.append(
                snapped(
                    Span(span.left, span.top / aspect, span.right, span.bottom / aspect)
                )
            )
    return out
