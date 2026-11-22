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

"""Gradient color mode: each series shaded by its position along the scale.

At zero a series is its start color, at the scale's maximum its own color,
in at most :data:`MAX_STEPS` shades. :func:`shade_window` is a pass over a
composed window that gives every series cell inside the bars its shade; the
widget turns shades into color specs with
:func:`tkcurses._charts.color.shade_rgb`. Pure: errors
are ``ValueError``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tkcurses._charts.color import RGB
    from tkcurses.bargraph._decor import Window
    from tkcurses.bargraph._layout import Layout
    from tkcurses.bargraph._render import Role


#: The most shades one series has. Each shade pairs with every background it
#: meets, and curses can name only about 255 color pairs.
MAX_STEPS = 16
#: Without a start color, a series starts at this fraction of its brightness.
START_BRIGHTNESS = 0.25


def shade(series: int, step: int) -> Role:
    """The role for shade ``step`` of series ``series``."""
    if not 0 <= step < MAX_STEPS:
        raise ValueError(f"shade step {step} outside 0-{MAX_STEPS - 1}")
    return ("shade", series * MAX_STEPS + step)


def shade_parts(index: int) -> tuple[int, int]:
    """``(series, step)`` from a shade role's index."""
    return divmod(index, MAX_STEPS)


def step_count(length_cells: int) -> int:
    """How many shades a bar ``length_cells`` long has: one per cell, at
    most :data:`MAX_STEPS`."""
    return max(1, min(MAX_STEPS, length_cells))


def step_at(cell: int, length_cells: int) -> int:
    """The shade of the ``cell``-th cell from zero: 0 at the zero edge, the
    last shade at the far one, spread evenly between."""
    if not 0 <= cell < max(1, length_cells):
        raise ValueError(f"cell {cell} outside a bar {length_cells} long")
    steps = step_count(length_cells)
    if length_cells <= 1:
        return steps - 1
    return round(cell * (steps - 1) / (length_cells - 1))


def default_start(color: RGB) -> RGB:
    """A series' start color when none is given: 25 % of its brightness."""
    red, green, blue = (round(channel * START_BRIGHTNESS) for channel in color)
    return red, green, blue


def shade_window(window: Window, layout: Layout) -> Window:
    """``window`` with every series color inside the bars shaded by position.

    Both colors of a cell are shaded alike - a partial cell's lower and upper
    series sit at the same position. Zones, markers, gridlines, text and
    anything outside the bars are left as they are, so thresholds still win
    and a held peak drawn in a series color takes the shade at its level.
    """
    bars = layout.bars
    length = layout.length_cells
    if bars.empty or length <= 0:
        return window
    vertical = layout.orient == "vertical"
    shaded = [list(row) for row in window]
    for y in range(bars.y, bars.y + bars.height):
        for x in range(bars.x, bars.x + bars.width):
            cell = shaded[y][x]
            if cell is None:
                continue
            along = bars.y + bars.height - 1 - y if vertical else x - bars.x
            if not 0 <= along < length:
                continue
            step = step_at(along, length)
            fg, bg = _shaded(cell.fg, step), _shaded(cell.bg, step)
            if fg != cell.fg or bg != cell.bg:
                shaded[y][x] = replace(cell, fg=fg, bg=bg)
    return shaded


def _shaded(role: Role, step: int) -> Role:
    """A series role's shade. Zone 0 - a single-value bar below its first
    threshold - is the base color, series 0's, so it is shaded as series 0;
    the zones above a threshold keep their colors."""
    kind, index = role
    if kind == "series":
        return shade(index, step)
    if role == ("zone", 0):
        return shade(0, step)
    return role
