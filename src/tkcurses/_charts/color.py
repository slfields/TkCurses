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

__all__ = [
    "BLACK",
    "RGB",
    "WHITE",
    "hex_color",
    "luminance",
    "mix",
    "shade_rgb",
    "text_on",
]

RGB = tuple[int, int, int]

#: A chart's colours when ``colors`` is not given, taken in turn: by
#: series in a bar graph, by top-level item in a treemap.
DEFAULT_COLORS = ("green", "red", "blue", "yellow", "magenta", "cyan")

BLACK: RGB = (0, 0, 0)
WHITE: RGB = (255, 255, 255)


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


def mix(color: RGB, toward: RGB, fraction: float) -> RGB:
    """``color`` moved ``fraction`` of the way to ``toward``, linear in RGB."""
    red, green, blue = (
        round(low + (high - low) * fraction)
        for low, high in zip(color, toward, strict=True)
    )
    return red, green, blue


def hex_color(color: RGB) -> str:
    """``#rrggbb`` for an RGB triple."""
    return "#{:02x}{:02x}{:02x}".format(*color)


def _linear(channel: int) -> float:
    """An sRGB channel, 0-255, as linear light: the sRGB transfer function
    of IEC 61966-2-1, with the 0.04045 threshold WCAG 2 gives."""
    value = channel / 255
    if value <= 0.04045:
        return value / 12.92
    return float(((value + 0.055) / 1.055) ** 2.4)


def luminance(color: RGB) -> float:
    """``color``'s relative luminance, 0 for black to 1 for white, as WCAG
    2 defines it (W3C, *Web Content Accessibility Guidelines 2.1*,
    "relative luminance")."""
    red, green, blue = (_linear(channel) for channel in color)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def text_on(color: RGB) -> RGB:
    """Black or white, whichever has the higher WCAG 2 contrast ratio,
    ``(L1 + 0.05) / (L2 + 0.05)``, against ``color``; black on a tie."""
    lit = luminance(color)
    against_black = (lit + 0.05) / 0.05
    against_white = 1.05 / (lit + 0.05)
    return BLACK if against_black >= against_white else WHITE
