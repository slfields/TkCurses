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

"""Block Elements glyphs (U+2580-U+259F) for drawing bars at 1/8-cell steps.

Pure: no curses, no TkCurses.
"""

from __future__ import annotations

from typing import Final, Literal

Orient = Literal["vertical", "horizontal"]

#: Points (eighths) in one cell along the bar.
POINTS_PER_CELL: Final = 8

FULL: Final = "█"  # █
EMPTY: Final = " "

#: Lower blocks, 1/8 to 8/8: grows bottom -> top.
VERTICAL_RAMP: Final = (
    "▁",  # ▁
    "▂",  # ▂
    "▃",  # ▃
    "▄",  # ▄
    "▅",  # ▅
    "▆",  # ▆
    "▇",  # ▇
    FULL,
)

#: Left blocks, 1/8 to 8/8: grows left -> right.
HORIZONTAL_RAMP: Final = (
    "▏",  # ▏
    "▎",  # ▎
    "▍",  # ▍
    "▌",  # ▌
    "▋",  # ▋
    "▊",  # ▊
    "▉",  # ▉
    FULL,
)

#: Fill patterns that tell series (or threshold zones) apart without color.
MONO_PATTERNS: Final = (
    FULL,
    "▓",  # ▓
    "▒",  # ▒
    "░",  # ░
)


def ramp(orient: Orient) -> tuple[str, ...]:
    """The 8-step ramp for bars growing along ``orient``."""
    return VERTICAL_RAMP if orient == "vertical" else HORIZONTAL_RAMP


def partial(points: int, orient: Orient) -> str:
    """The glyph for a cell filled ``points`` eighths from its near edge.

    0 is an empty cell and 8 a full one. The filled part takes the cell's
    foreground color and the rest its background.
    """
    if not 0 <= points <= POINTS_PER_CELL:
        raise ValueError(f"points must be 0-{POINTS_PER_CELL}, not {points}")
    if points == 0:
        return EMPTY
    return ramp(orient)[points - 1]


def partial_from_far_edge(points: int, orient: Orient) -> tuple[str, bool]:
    """The glyph for a cell filled ``points`` eighths from its *far* edge.

    The Block Elements block has no 8-step upper or right blocks, so the
    complementary near-edge glyph is drawn with foreground and background
    swapped. Returns ``(glyph, swapped)``; when ``swapped`` is true the
    caller must exchange the cell's colors.
    """
    if not 0 <= points <= POINTS_PER_CELL:
        raise ValueError(f"points must be 0-{POINTS_PER_CELL}, not {points}")
    if points in (0, POINTS_PER_CELL):
        return partial(points, orient), False
    return partial(POINTS_PER_CELL - points, orient), True


def mono_pattern(index: int) -> str:
    """The fill pattern for series or zone ``index`` on a monochrome terminal."""
    return MONO_PATTERNS[index % len(MONO_PATTERNS)]
