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

"""Colours as RGB triples: blending them, and writing them as Tk specs.

Pure. The widgets turn a blend into a colour spec with :func:`hex_color`
and leave the rest to the colour manager.
"""

from __future__ import annotations

__all__ = ["RGB", "hex_color", "shade_rgb"]

RGB = tuple[int, int, int]


def shade_rgb(start: RGB, end: RGB, step: int, steps: int) -> RGB:
    """Shade ``step`` of ``steps``, from ``start`` (0) to ``end`` (last).

    Linear in RGB, rounded to whole channel values.
    """
    if steps <= 1:
        return end
    fraction = step / (steps - 1)
    red, green, blue = (
        round(low + (high - low) * fraction)
        for low, high in zip(start, end, strict=True)
    )
    return red, green, blue


def hex_color(color: RGB) -> str:
    """``#rrggbb`` for an RGB triple."""
    return "#{:02x}{:02x}{:02x}".format(*color)
