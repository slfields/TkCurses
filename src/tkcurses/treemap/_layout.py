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

"""A treemap's regions and tiles, in cells. Pure.

:func:`regions` cuts the widget into the readout row, the legend and the
tiles, giving up the legend and then the readout when the tiles would be
left too small. :func:`lay_out` squarifies the items into the tiles
region: the top level first, then each group's children inside its
tile, under a header row when the group has room for one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from tkcurses._charts.geometry import Rect
from tkcurses.treemap._outline import inner, shrunk
from tkcurses.treemap._squarify import CELL_ASPECT, tiles

if TYPE_CHECKING:
    from tkcurses.treemap._model import Model

__all__ = [
    "HEADER_MIN_COLUMNS",
    "HEADER_MIN_ROWS",
    "MIN_TILE_COLUMNS",
    "MIN_TILE_ROWS",
    "Regions",
    "Tile",
    "TileLayout",
    "lay_out",
    "regions",
]

Side = Literal["left", "right", "top", "bottom"]

#: The least the tiles keep before the legend, then the readout, give way.
MIN_TILE_COLUMNS = 10
MIN_TILE_ROWS = 3
#: The least a group's tile needs for a header row above its children.
HEADER_MIN_ROWS = 3
HEADER_MIN_COLUMNS = 6


@dataclass(frozen=True, slots=True)
class Regions:
    """Where each part of the widget goes; ``None`` for a part not shown."""

    tiles: Rect
    legend: Rect | None = None
    readout: Rect | None = None


def _cut(area: Rect, readout: bool, legend: Side | None, extent: int) -> Regions:
    readout_rect = None
    if readout:
        readout_rect, area = area.take_bottom(1)
    legend_rect = None
    if legend is not None and extent > 0:
        take = {
            "left": area.take_left,
            "right": area.take_right,
            "top": area.take_top,
            "bottom": area.take_bottom,
        }[legend]
        legend_rect, area = take(extent)
    return Regions(area, legend_rect, readout_rect)


def _roomy(rect: Rect) -> bool:
    return rect.width >= MIN_TILE_COLUMNS and rect.height >= MIN_TILE_ROWS


def regions(
    area: Rect,
    *,
    readout: bool = True,
    legend: Side | None = None,
    legend_extent: int = 0,
) -> Regions:
    """``area`` cut into tiles, legend and readout.

    The readout takes the bottom row; the legend ``legend_extent`` columns
    (at the left or right) or rows (at the top or bottom) of what is left;
    the tiles the rest. When the tiles would have fewer than
    :data:`MIN_TILE_COLUMNS` columns or :data:`MIN_TILE_ROWS` rows, the
    legend is given up, and then the readout.
    """
    attempts = [(readout, legend), (readout, None), (False, None)]
    cut = Regions(area)
    for keep_readout, keep_legend in attempts:
        cut = _cut(area, keep_readout, keep_legend, legend_extent)
        if _roomy(cut.tiles):
            return cut
    return cut


@dataclass(frozen=True, slots=True)
class Tile:
    """One item's place on the screen.

    A group's ``rect`` holds its header, if it has one, and its children's
    tiles; ``header`` is its top row then, and ``None`` otherwise.
    """

    iid: str
    rect: Rect
    #: 0 for a top-level item, 1 for a child.
    level: int
    group: bool = False
    header: Rect | None = None
    #: Drawn outlined: ``rect`` is then its box's corners, and what is
    #: inside the lines is :func:`tkcurses.treemap._outline.inner`.
    boxed: bool = False


@dataclass(frozen=True, slots=True)
class TileLayout:
    """Every tile with a cell, top-level items before their children, and
    the items too small to have one."""

    tiles: tuple[Tile, ...]
    #: Items with a size but no cell, in layout order.
    hidden: tuple[str, ...]

    def at(self, x: int, y: int) -> Tile | None:
        """The innermost tile at cell ``(x, y)``, or ``None``."""
        found = None
        for tile in self.tiles:
            rect = tile.rect
            inside = (
                rect.x <= x < rect.x + rect.width and rect.y <= y < rect.y + rect.height
            )
            if inside and (found is None or tile.level >= found.level):
                found = tile
        return found

    def tile(self, iid: str) -> Tile | None:
        """``iid``'s tile, or ``None`` if it has none."""
        for tile in self.tiles:
            if tile.iid == iid:
                return tile
        return None


def lay_out(
    model: Model,
    area: Rect,
    zoom: str = "",
    aspect: float = CELL_ASPECT,
    outlined: frozenset[str] = frozenset(),
) -> TileLayout:
    """The tiles of ``model`` in ``area``.

    With ``zoom`` naming a group, its children fill ``area`` alone, as the
    top of what is shown. Items are laid largest first; a group's children
    go inside its tile, under a header row when the tile has at least
    :data:`HEADER_MIN_ROWS` rows and :data:`HEADER_MIN_COLUMNS` columns.

    ``outlined`` names the levels drawn with lines between their tiles:
    ``""`` for the top level, a group's iid for its children. An outlined
    level is laid out a column and a row short, to close its boxes; a
    group outlined itself and around its children shares its lines with
    theirs, and needs a row more for a header, the line under it.
    """
    placed: list[Tile] = []
    hidden: list[str] = []

    def lay(iids: list[str], space: Rect, level: int, boxed: bool) -> None:
        rects = tiles([model.size(iid) for iid in iids], space, aspect)
        for iid, rect in zip(iids, rects, strict=True):
            children = model.ordered(iid) if level == 0 else []
            if rect is None:
                continue
            if rect.empty:
                hidden.append(iid)
                hidden.extend(c for c in children if model.size(c) > 0)
                continue
            if not children:
                placed.append(Tile(iid, rect, level, boxed=boxed))
                continue
            inside = inner(rect) if boxed else rect
            header = None
            if (
                inside.height >= HEADER_MIN_ROWS + (1 if boxed else 0)
                and inside.width >= HEADER_MIN_COLUMNS
            ):
                header = Rect(inside.x, inside.y, inside.width, 1)
            placed.append(
                Tile(iid, rect, level, group=True, header=header, boxed=boxed)
            )
            lines_inside = iid in outlined
            if boxed and lines_inside:
                # The children's boxes close on the group's own lines.
                top = rect.y + (2 if header else 0)
                space_in = Rect(rect.x, top, rect.width, rect.y + rect.height - top)
            else:
                below = inside.take_top(1)[1] if header else inside
                space_in = shrunk(below) if lines_inside else below
            lay(children, space_in, 1, lines_inside)

    key = zoom
    top = shrunk(area) if key in outlined else area
    if zoom:
        lay(model.ordered(zoom) or [zoom], top, 1, key in outlined)
    else:
        lay(model.ordered(), top, 0, key in outlined)
    return TileLayout(tuple(placed), tuple(hidden))
