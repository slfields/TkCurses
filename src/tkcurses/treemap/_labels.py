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

"""What text fits in a treemap tile, and how a value is written. Pure.

As Kibana does, a label that does not fit is left out rather than
overflowing its tile. A name is cut with ``…`` to fit, but never to fewer
than :data:`MIN_LABEL` cells, which would say nothing; a value is never
cut, since a number cut short reads as a different number.
"""

from __future__ import annotations

from tkcurses._charts.text import fit
from tkcurses._core.cells import cells

__all__ = ["MIN_LABEL", "header_text", "percent", "tile_text"]

#: The fewest cells a cut name keeps; less and it is not drawn.
MIN_LABEL = 3


def _name(name: str, width: int) -> str | None:
    """``name`` whole if it fits, cut if it keeps :data:`MIN_LABEL`
    cells, else ``None``."""
    if not name or width <= 0:
        return None
    if cells(name) <= width:
        return name
    if width >= MIN_LABEL:
        return fit(name, width)
    return None


def tile_text(
    name: str | None, value: str | None, width: int, height: int
) -> list[str]:
    """The lines a tile ``width`` by ``height`` shows, from its top.

    The name takes the first row and the value the second. In a one-row
    tile the value follows the name when both fit whole, and is dropped
    otherwise: the name matters more. With no name, the value takes the
    first row.
    """
    if width <= 0 or height <= 0:
        return []
    named = _name(name, width) if name else None
    fits = value if value and cells(value) <= width else None
    if height == 1:
        if named and fits and named == name and cells(name) + 1 + cells(fits) <= width:
            return [f"{name} {fits}"]
        if named:
            return [named]
        return [fits] if fits else []
    return [line for line in (named, fits) if line]


def header_text(name: str, value: str | None, width: int) -> str:
    """A group's header: its name and value if both fit whole, else the
    name as a tile's would be, else nothing."""
    if value and name and cells(name) + 1 + cells(value) <= width:
        return f"{name} {value}"
    return _name(name, width) or ""


def percent(part: float, whole: float, decimals: int) -> str:
    """``part`` as a percentage of ``whole``, with ``decimals`` places."""
    share = 100 * part / whole if whole > 0 else 0.0
    return f"{share:.{decimals}f}%"
