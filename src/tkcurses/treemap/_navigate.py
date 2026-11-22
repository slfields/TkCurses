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

"""Which tile an arrow key moves to. Pure.

A treemap has no rows or columns to step along, so a key moves by
geometry: Right goes to a tile wholly to the right of the focused one,
preferring

1. one that overlaps it top to bottom, as a neighbour across a shared
   edge does;
2. then the nearest, by the gap between them;
3. then the one whose centre is nearest across the move, so Right from
   a tall tile goes to the neighbour level with its middle.

The other three keys are the same, turned. With nothing that way the
focus stays, and the key is left for the program's own bindings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tkcurses._charts.geometry import Rect

__all__ = ["DIRECTIONS", "OPPOSITE", "Direction", "neighbour"]

Direction = Literal["Left", "Right", "Up", "Down"]
DIRECTIONS: tuple[Direction, ...] = ("Left", "Right", "Up", "Down")
OPPOSITE: dict[Direction, Direction] = {
    "Left": "Right",
    "Right": "Left",
    "Up": "Down",
    "Down": "Up",
}


def _span(low: int, size: int) -> tuple[int, int]:
    return low, low + size


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> int:
    return min(a[1], b[1]) - max(a[0], b[0])


def neighbour(
    current: Rect, candidates: Sequence[tuple[str, Rect]], direction: Direction
) -> str | None:
    """The candidate an arrow key in ``direction`` moves to from
    ``current``, or ``None``. Ties go to the earlier candidate."""
    horizontal = direction in ("Left", "Right")
    forward = direction in ("Right", "Down")
    best: tuple[tuple[int, int, float], int, str] | None = None
    for order, (iid, rect) in enumerate(candidates):
        if horizontal:
            near, far = _span(current.x, current.width)
            low, high = _span(rect.x, rect.width)
            across = _overlap(
                _span(current.y, current.height), _span(rect.y, rect.height)
            )
            centre = abs((rect.y + rect.height / 2) - (current.y + current.height / 2))
        else:
            near, far = _span(current.y, current.height)
            low, high = _span(rect.y, rect.height)
            across = _overlap(
                _span(current.x, current.width), _span(rect.x, rect.width)
            )
            centre = abs((rect.x + rect.width / 2) - (current.x + current.width / 2))
        if forward:
            if low < far:
                continue
            gap = low - far
        else:
            if high > near:
                continue
            gap = near - high
        rank = (0 if across > 0 else 1, gap, centre)
        if best is None or (rank, order) < (best[0], best[1]):
            best = (rank, order, iid)
    return None if best is None else best[2]
