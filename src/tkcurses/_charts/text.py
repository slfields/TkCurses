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

"""Text laid into character cells: what each character takes, and cutting
a line to fit.

Measured with :mod:`tkcurses._core.cells`, never ``len()``: a CJK character
takes two cells and a combining mark none, so a label measured by length
runs past its space or sits off centre.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tkcurses._core.cells import cells, char_cells, clip_cells

if TYPE_CHECKING:
    from tkcurses._charts.geometry import Rect

__all__ = [
    "ELLIPSIS",
    "LABEL_ANCHORS",
    "TITLE_INSET",
    "clusters",
    "fit",
    "place_text",
]

ELLIPSIS = "\u2026"  # …

#: The anchors a chart's label accepts, as ``ttk.LabelFrame``'s.
LABEL_ANCHORS = ("n", "nw", "ne", "s", "sw", "se")

#: Cells of edge left visible either side of a chart's label set in its
#: box (the corner and one line cell: ``┌─ Title ─┐``).
TITLE_INSET = 2


def clusters(text: str) -> list[tuple[str, int]]:
    """``text`` as ``(glyph, cells)`` pairs, one per cell-taking character.

    A combining mark joins the glyph of the character before it, since it
    takes no cell of its own; one with nothing before it is dropped.
    """
    found: list[tuple[str, int]] = []
    for char in text:
        width = char_cells(char)
        if width == 0 and found:
            glyph, first = found[-1]
            found[-1] = (glyph + char, first)
        elif width:
            found.append((char, width))
    return found


def fit(text: str, width: int) -> str:
    """``text`` cut to ``width`` cells, ending in ``…`` when it was cut."""
    if width <= 0:
        return ""
    if cells(text) <= width:
        return text
    return clip_cells(text, width - 1) + ELLIPSIS if width > 1 else ELLIPSIS


def place_text(rect: Rect, text: str, anchor: str) -> tuple[int, str]:
    """Where a one-row ``text`` goes in ``rect``: ``(x, text)``.

    Measured in cells, so a wide character counts two and a combining mark
    none. Cut with ``…`` when it doesn't fit. The anchor's ``w`` puts it at the
    left, ``e`` at the right, and neither centres it.
    """
    if rect.width <= 0:
        return rect.x, ""
    text = fit(text, rect.width)
    spare = rect.width - cells(text)
    if anchor.endswith("w"):
        return rect.x, text
    if anchor.endswith("e"):
        return rect.x + spare, text
    return rect.x + spare // 2, text
