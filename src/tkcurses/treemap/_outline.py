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
"""The lines between outlined tiles. Pure.

An outlined tile's rectangle names the corners of its box: the line runs
along its top row and left column, and along the row and column just
past its right and bottom edges, which are the next tile's top row and
left column. So neighbours share their lines, and the region outlined
gives one column and one row to close the last box (:func:`shrunk`).
Where lines meet, the junction is drawn from the directions that do:
``┬``, ``├``, ``┼`` and the rest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tkcurses._charts.geometry import Rect

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["GLYPHS", "inner", "lines", "shrunk"]

# Directions, as bits: which way a line leaves the cell.
LEFT, RIGHT, UP, DOWN = 1, 2, 4, 8

#: The single-line box-drawing glyph for each set of directions.
GLYPHS: dict[int, str] = {
    LEFT: "╴",  # ╴
    RIGHT: "╶",  # ╶
    UP: "╵",  # ╵
    DOWN: "╷",  # ╷
    LEFT | RIGHT: "─",  # ─
    UP | DOWN: "│",  # │
    RIGHT | DOWN: "┌",  # ┌
    LEFT | DOWN: "┐",  # ┐
    RIGHT | UP: "└",  # └
    LEFT | UP: "┘",  # ┘
    UP | DOWN | RIGHT: "├",  # ├
    UP | DOWN | LEFT: "┤",  # ┤
    LEFT | RIGHT | DOWN: "┬",  # ┬
    LEFT | RIGHT | UP: "┴",  # ┴
    LEFT | RIGHT | UP | DOWN: "┼",  # ┼
}


def shrunk(region: Rect) -> Rect:
    """Where outlined tiles are laid out in ``region``: all but its last
    column and row, which close the boxes."""
    return Rect(region.x, region.y, max(0, region.width - 1), max(0, region.height - 1))


def inner(tile: Rect) -> Rect:
    """What is inside an outlined tile's lines; empty when it is too thin."""
    return Rect(tile.x + 1, tile.y + 1, max(0, tile.width - 1), max(0, tile.height - 1))


def lines(tiles: Iterable[Rect]) -> dict[tuple[int, int], str]:
    """The glyph for every cell on the lines of ``tiles``' boxes."""
    across: set[tuple[int, int]] = set()  # (x, y) to (x + 1, y)
    down: set[tuple[int, int]] = set()  # (x, y) to (x, y + 1)
    for tile in tiles:
        if tile.empty:
            continue
        right, bottom = tile.x + tile.width, tile.y + tile.height
        for x in range(tile.x, right):
            across.add((x, tile.y))
            across.add((x, bottom))
        for y in range(tile.y, bottom):
            down.add((tile.x, y))
            down.add((right, y))
    points = {p for x, y in across for p in ((x, y), (x + 1, y))}
    points |= {p for x, y in down for p in ((x, y), (x, y + 1))}
    out: dict[tuple[int, int], str] = {}
    for x, y in points:
        ways = (
            (LEFT if (x - 1, y) in across else 0)
            | (RIGHT if (x, y) in across else 0)
            | (UP if (x, y - 1) in down else 0)
            | (DOWN if (x, y) in down else 0)
        )
        out[x, y] = GLYPHS[ways]
    return out
