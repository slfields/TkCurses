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

"""A treemap's legend: its entries, wrapped, sized and placed. Pure.

:func:`entries` lists what the legend names, :func:`extent` says how much
of the widget it takes, and :func:`place` puts each entry in that region:
down the side at the left or right, across in columns at the top or
bottom. An entry is a swatch, a space and the item's name, wrapped at
word boundaries onto at most ``legendlines`` lines, the last cut with
``…``. What does not fit ends with a ``+N more`` line.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from tkcurses._charts.geometry import Rect
from tkcurses._charts.text import fit
from tkcurses._core.cells import cells, clip_cells

if TYPE_CHECKING:
    from tkcurses.treemap._model import Model

__all__ = [
    "LEGEND_MODES",
    "LEGEND_SIZES",
    "MAX_LINES",
    "POSITIONS",
    "SWATCH",
    "Entry",
    "LegendLayout",
    "Placed",
    "entries",
    "extent",
    "place",
    "shown",
    "wrap",
]

Side = Literal["left", "right", "top", "bottom"]

LEGEND_MODES = ("auto", "show", "hide")
POSITIONS = ("right", "left", "top", "bottom")
#: The legend's width at the left or right, in cells, edge included.
LEGEND_SIZES = {"small": 12, "medium": 20, "large": 28, "xlarge": 36}
#: The most lines an entry wraps onto, Kibana's limit.
MAX_LINES = 5
SWATCH = "██"  # ██
#: Cells before an entry's name: the swatch and a space.
LEAD = 3
#: How far a nested entry is indented under its group.
INDENT = 2
#: Cells between columns at the top or bottom.
GAP = 2
#: The least room a legend is drawn in: its edge, a swatch, a space and
#: one character; and at the top or bottom, its edge and one row.
MIN_COLUMNS = 1 + LEAD + 1
MIN_ROWS = 2


@dataclass(frozen=True, slots=True)
class Entry:
    """One item the legend names."""

    iid: str
    text: str
    #: A group's child, indented under it.
    nested: bool = False

    @property
    def indent(self) -> int:
        return INDENT if self.nested else 0

    @property
    def width(self) -> int:
        """The cells it takes on one line."""
        return self.indent + LEAD + cells(self.text)


@dataclass(frozen=True, slots=True)
class Placed:
    """An entry where it is drawn: its swatch at ``(x + indent, y)``, its
    lines from ``x + indent + 3`` down, in a column ``width`` wide."""

    iid: str
    x: int
    y: int
    width: int
    lines: tuple[str, ...]
    indent: int = 0

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.width, len(self.lines))

    @property
    def text_rect(self) -> Rect:
        """Where its name is, swatch left out."""
        start = self.x + self.indent + LEAD
        return Rect(start, self.y, self.x + self.width - start, len(self.lines))


@dataclass(frozen=True, slots=True)
class LegendLayout:
    """The entries placed in the legend's region, the line between it and
    the tiles, and how many entries had no room."""

    placed: tuple[Placed, ...]
    #: The line on the tiles' side of the region, one cell thick.
    edge: Rect
    #: ``│`` at the left or right, ``─`` at the top or bottom.
    edge_glyph: str
    more: int = 0
    #: Where ``+N more`` is written, when ``more``.
    more_at: tuple[int, int] | None = None
    more_width: int = 0

    @property
    def more_text(self) -> str:
        return fit(f"+{self.more} more", self.more_width) if self.more else ""

    def at(self, x: int, y: int) -> str | None:
        """The item whose entry is at cell ``(x, y)``, or ``None``."""
        for entry in self.placed:
            rect = entry.rect
            if rect.x <= x < rect.x + rect.width and rect.y <= y < rect.y + rect.height:
                return entry.iid
        return None


def entries(model: Model, zoom: str = "", nested: bool = False) -> list[Entry]:
    """What the legend names, largest first: the top-level items, each
    group's children under it when ``nested``; or, zoomed into a group,
    its children. An item whose size is zero takes no room and is left
    out, as its tile is."""
    found: list[Entry] = []

    def text(iid: str) -> str:
        return model.item(iid).text or iid

    for iid in model.ordered(zoom):
        if model.size(iid) <= 0:
            continue
        found.append(Entry(iid, text(iid)))
        if nested and not zoom:
            found.extend(
                Entry(child, text(child), nested=True)
                for child in model.ordered(iid)
                if model.size(child) > 0
            )
    return found


def shown(mode: str, listed: list[Entry]) -> bool:
    """Whether a legend in ``mode`` is drawn: ``"auto"`` when it names two
    or more items at the top of what is shown."""
    if mode == "show":
        return bool(listed)
    if mode == "hide":
        return False
    return sum(1 for entry in listed if not entry.nested) >= 2


def wrap(text: str, width: int, limit: int) -> list[str]:
    """``text`` on lines at most ``width`` cells, broken between words, a
    word longer than a line broken inside it. At most ``limit`` lines; the
    last holds the rest, cut with ``…`` when it does not fit."""
    if width <= 0 or limit <= 0:
        return []
    words = text.split()
    lines: list[str] = []
    current = ""
    index = 0
    while index < len(words):
        if len(lines) == limit - 1:
            rest = " ".join(([current] if current else []) + words[index:])
            lines.append(fit(rest, width))
            return lines
        word = words[index]
        candidate = f"{current} {word}" if current else word
        if cells(candidate) <= width:
            current = candidate
            index += 1
        elif current:
            lines.append(current)
            current = ""
        else:
            head = clip_cells(word, width)
            if not head:  # a wide character in a one-cell line
                lines.append(fit(word, width))
                return lines
            lines.append(head)
            words[index] = word[len(head) :]
    lines.append(current)
    return lines


def _wrapped(entry: Entry, column: int, limit: int) -> tuple[str, ...]:
    return tuple(wrap(entry.text, column - entry.indent - LEAD, limit) or [""])


def _columns(listed: list[Entry], width: int) -> tuple[int, int]:
    """The column width and the count of columns at the top or bottom."""
    column = min(max(entry.width for entry in listed), width)
    return column, max(1, (width + GAP) // (column + GAP))


def _row_heights(
    listed: list[Entry], column: int, across: int, limit: int
) -> list[int]:
    heights = []
    for start in range(0, len(listed), across):
        row = listed[start : start + across]
        heights.append(max(len(_wrapped(entry, column, limit)) for entry in row))
    return heights


def extent(listed: list[Entry], side: Side, size: str, area: Rect, limit: int) -> int:
    """How many columns (at the left or right) or rows (at the top or
    bottom) of ``area`` the legend takes, its edge included; 0 when it
    has nothing to name or no room.

    At the side it is ``size``'s width, or with ``"auto"`` the widest
    entry, at most a third of ``area``. At the top or bottom it is the
    rows the entries need flowed across in columns, at most a third of
    ``area``'s height.
    """
    if not listed:
        return 0
    if side in ("left", "right"):
        if size == "auto":
            wanted = min(1 + max(entry.width for entry in listed), area.width // 3)
        else:
            wanted = LEGEND_SIZES[size]
        return wanted if wanted >= MIN_COLUMNS else 0
    if area.width < MIN_COLUMNS - 1:
        return 0
    column, across = _columns(listed, area.width)
    wanted = 1 + sum(_row_heights(listed, column, across, limit))
    wanted = min(wanted, area.height // 3)
    return wanted if wanted >= MIN_ROWS else 0


def place(listed: list[Entry], region: Rect, side: Side, limit: int) -> LegendLayout:
    """``listed`` placed in ``region``, which :func:`extent` sized."""
    edge, inner = {
        "right": region.take_left,
        "left": region.take_right,
        "top": region.take_bottom,
        "bottom": region.take_top,
    }[side](1)
    glyph = "│" if side in ("left", "right") else "─"  # │ ─
    if side in ("left", "right"):
        column, across = inner.width, 1
    else:
        column, across = _columns(listed, inner.width)
    rows: list[list[Placed]] = []
    for start in range(0, len(listed), across):
        row = []
        for offset, entry in enumerate(listed[start : start + across]):
            row.append(
                Placed(
                    entry.iid,
                    inner.x + offset * (column + GAP),
                    0,
                    column,
                    _wrapped(entry, column, limit),
                    entry.indent,
                )
            )
        rows.append(row)
    heights = [max(len(p.lines) for p in row) for row in rows]
    bottom = inner.y + inner.height
    fits_all = sum(heights) <= inner.height
    room = bottom if fits_all else bottom - 1  # the last row says how many more
    placed: list[Placed] = []
    y = inner.y
    for row, height in zip(rows, heights, strict=True):
        if y + height > room:
            break
        placed.extend(Placed(p.iid, p.x, y, p.width, p.lines, p.indent) for p in row)
        y += height
    more = len(listed) - len(placed)
    if not more:
        return LegendLayout(tuple(placed), edge, glyph)
    return LegendLayout(
        tuple(placed), edge, glyph, more, (inner.x, bottom - 1), inner.width
    )
