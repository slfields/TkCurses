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

"""A treemap as a grid of cells. Pure.

Every cell names its colours as specs, ``""`` for the widget's own
foreground or background; the widget turns them into curses attributes.
The order things are drawn in is the order they cover each other:

1. a group's tile in its colour, then its children's tiles over it, each
   in its colour or shade, inside its lines when outlined;
2. the lines between outlined tiles, in the colour of the group they
   divide, or the widget's own between top-level tiles;
3. headers and labels;
4. the readout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tkcurses._charts.color import BLACK, hex_color, text_on
from tkcurses._charts.text import clusters, fit
from tkcurses._core.cells import cells
from tkcurses.treemap._labels import header_text, tile_text
from tkcurses.treemap._outline import inner, lines
from tkcurses.treemap._shades import assign, shades_of

if TYPE_CHECKING:
    from collections.abc import Callable

    from tkcurses._charts.color import RGB
    from tkcurses._charts.geometry import Rect
    from tkcurses.treemap._layout import Regions, Tile, TileLayout
    from tkcurses.treemap._model import Model

__all__ = ["EMPTY_TEXT", "Cell", "Scene", "compose"]

#: What a treemap with nothing to lay out shows.
EMPTY_TEXT = "nothing to show"


@dataclass(frozen=True, slots=True)
class Cell:
    """One character cell. ``""`` colours are the widget's own; a wide
    character's second cell has ``char == ""`` and is not written."""

    char: str = " "
    fg: str = ""
    bg: str = ""
    bold: bool = False


@dataclass(frozen=True)
class Scene:
    """Everything a frame of the treemap is drawn from."""

    width: int
    height: int
    regions: Regions
    layout: TileLayout
    model: Model
    #: The colours the top-level items take in turn, each with its RGB;
    #: empty on a terminal without colour.
    colors: tuple[tuple[str, RGB], ...] = ()
    zoom: str = ""
    outlined: frozenset[str] = frozenset()
    labels: bool = True
    #: How an item's value is written, or ``None`` for no value.
    value_text: Callable[[str], str | None] = field(default=lambda _iid: None)
    readout: str = ""


Grid = list[list[Cell]]
Paint = tuple[str, "RGB"]  # a spec and its RGB


def _text_color(rgb: RGB) -> str:
    return "black" if text_on(rgb) == BLACK else "white"


class _Painter:
    def __init__(self, scene: Scene) -> None:
        self.scene = scene
        self.grid: Grid = [
            [Cell() for _ in range(scene.width)] for _ in range(scene.height)
        ]
        self.paints: dict[str, Paint] = {}
        #: Where each group's colour reaches, innermost last.
        self.group_areas: list[tuple[Rect, Paint]] = []

    def put(self, x: int, y: int, cell: Cell) -> None:
        if 0 <= y < self.scene.height and 0 <= x < self.scene.width:
            self.grid[y][x] = cell

    def fill(self, rect: Rect, paint: Paint | None) -> None:
        bg = paint[0] if paint else ""
        for y in range(rect.y, rect.y + rect.height):
            for x in range(rect.x, rect.x + rect.width):
                self.put(x, y, Cell(" ", "", bg))

    def text(
        self, x: int, y: int, text: str, paint: Paint | None, *, bold: bool = False
    ) -> None:
        """``text`` from ``(x, y)`` over ``paint``, a cell for each it takes."""
        fg = _text_color(paint[1]) if paint else ""
        bg = paint[0] if paint else ""
        column = x
        for glyph, width in clusters(text):
            self.put(column, y, Cell(glyph, fg, bg, bold))
            if width == 2:
                self.put(column + 1, y, Cell("", fg, bg, bold))
            column += width

    # ------------------------------------------------------------- colour

    def assign_colors(self) -> None:
        """A paint for every tile: top-level items in turn from ``colors``,
        children the shade :func:`assign` gives them, or their group's own
        colour when their level is outlined."""
        scene = self.scene
        if not scene.colors:
            return
        model = scene.model
        order = model.ordered()

        def top(iid: str) -> Paint:
            return scene.colors[order.index(iid) % len(scene.colors)]

        children: dict[str, list[Tile]] = {}
        for tile in scene.layout.tiles:
            if tile.level == 0:
                self.paints[tile.iid] = top(tile.iid)
            else:
                parent = scene.zoom or model.parent(tile.iid)
                children.setdefault(parent, []).append(tile)
        for parent, tiles in children.items():
            base = top(parent)
            if parent in scene.outlined:
                for tile in tiles:
                    self.paints[tile.iid] = base
                continue
            shades = shades_of(base[1])
            for tile, shade in zip(tiles, assign([t.rect for t in tiles]), strict=True):
                spec = base[0] if shade == 0 else hex_color(shades[shade])
                self.paints[tile.iid] = (spec, shades[shade])

    # -------------------------------------------------------------- tiles

    def tiles(self) -> None:
        scene = self.scene
        if scene.zoom and scene.colors:
            zoomed = scene.colors[
                scene.model.ordered().index(scene.zoom) % len(scene.colors)
            ]
            self.fill(scene.regions.tiles, zoomed)
            self.group_areas.append((scene.regions.tiles, zoomed))
        for tile in scene.layout.tiles:
            paint = self.paints.get(tile.iid)
            content = inner(tile.rect) if tile.boxed else tile.rect
            self.fill(content, paint)
            if tile.group and paint:
                self.group_areas.append((content, paint))

    def lines(self) -> None:
        boxed = [tile.rect for tile in self.scene.layout.tiles if tile.boxed]
        for (x, y), glyph in lines(boxed).items():
            paint = None
            for area, group in self.group_areas:
                if (
                    area.x <= x < area.x + area.width
                    and area.y <= y < area.y + area.height
                ):
                    paint = group
            fg = _text_color(paint[1]) if paint else ""
            self.put(x, y, Cell(glyph, fg, paint[0] if paint else ""))

    def labels(self) -> None:
        scene = self.scene
        for tile in scene.layout.tiles:
            paint = self.paints.get(tile.iid)
            name = scene.model.item(tile.iid).text if scene.labels else ""
            value = scene.value_text(tile.iid)
            if tile.group:
                if tile.header is None:
                    continue
                header = tile.header
                if scene.labels:
                    text = header_text(name, value, header.width)
                else:
                    text = value if value and cells(value) <= header.width else ""
                self.text(header.x, header.y, text, paint, bold=True)
                continue
            content = inner(tile.rect) if tile.boxed else tile.rect
            for row, line in enumerate(
                tile_text(name, value, content.width, content.height)
            ):
                self.text(content.x, content.y + row, line, paint)

    def empty(self) -> None:
        area = self.scene.regions.tiles
        if self.scene.layout.tiles or area.empty:
            return
        text = fit(EMPTY_TEXT, area.width)
        x = area.x + (area.width - cells(text)) // 2
        self.text(x, area.y + (area.height - 1) // 2, text, None)

    def readout(self) -> None:
        row = self.scene.regions.readout
        if row is None or not self.scene.readout:
            return
        self.text(row.x, row.y, fit(self.scene.readout, row.width), None)


def compose(scene: Scene) -> Grid:
    """``scene`` as rows of cells, ``scene.height`` by ``scene.width``."""
    painter = _Painter(scene)
    painter.assign_colors()
    painter.tiles()
    painter.lines()
    painter.labels()
    painter.empty()
    painter.readout()
    return painter.grid
