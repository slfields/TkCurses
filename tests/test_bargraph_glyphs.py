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

"""The Block Elements ramps and the far-edge (swapped-color) trick."""

from __future__ import annotations

import pytest

from tkcurses.bargraph import _glyphs as glyphs


def test_ramps_are_the_block_elements_eighths():
    assert "".join(glyphs.VERTICAL_RAMP) == "▁▂▃▄▅▆▇█"
    assert "".join(glyphs.HORIZONTAL_RAMP) == "▏▎▍▌▋▊▉█"
    for glyph in glyphs.VERTICAL_RAMP + glyphs.HORIZONTAL_RAMP + glyphs.MONO_PATTERNS:
        assert 0x2580 <= ord(glyph) <= 0x259F


@pytest.mark.parametrize("orient", ["vertical", "horizontal"])
def test_partial_covers_empty_to_full(orient):
    assert glyphs.partial(0, orient) == " "
    assert glyphs.partial(8, orient) == "█"
    assert [glyphs.partial(n, orient) for n in range(1, 9)] == list(glyphs.ramp(orient))


@pytest.mark.parametrize("points", [-1, 9])
def test_partial_rejects_out_of_range(points):
    with pytest.raises(ValueError):
        glyphs.partial(points, "vertical")


def test_far_edge_uses_the_complement_with_colors_swapped():
    assert glyphs.partial_from_far_edge(3, "vertical") == ("▅", True)
    assert glyphs.partial_from_far_edge(0, "vertical") == (" ", False)
    assert glyphs.partial_from_far_edge(8, "vertical") == ("█", False)


def test_mono_patterns_cycle():
    assert [glyphs.mono_pattern(i) for i in range(5)] == ["█", "▓", "▒", "░", "█"]
