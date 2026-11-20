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

"""Gradient color mode: shades by position along the scale."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses.bargraph._gradient import (
    MAX_STEPS,
    default_start,
    hex_color,
    shade,
    shade_parts,
    shade_rgb,
    shade_window,
    step_at,
    step_count,
)
from tkcurses.bargraph._layout import LayoutSpec, compute_layout
from tkcurses.bargraph._render import (
    BACKGROUND,
    EMPTY_CELL,
    TEXT,
    Cell,
    marker,
    series,
    zone,
)


def test_steps_are_one_per_cell_up_to_the_cap():
    assert step_count(1) == 1
    assert step_count(8) == 8
    assert step_count(16) == MAX_STEPS
    assert step_count(40) == MAX_STEPS


@given(st.integers(1, 80))
def test_steps_run_from_zero_to_the_last_evenly(length):
    steps = [step_at(cell, length) for cell in range(length)]
    assert steps[-1] == step_count(length) - 1
    if length > 1:
        assert steps[0] == 0
    assert steps == sorted(steps)
    assert set(steps) == set(range(step_count(length)))


def test_step_outside_the_bar_is_an_error():
    with pytest.raises(ValueError):
        step_at(8, 8)


def test_default_start_is_a_quarter_of_the_brightness():
    assert default_start((205, 0, 0)) == (51, 0, 0)
    assert hex_color(default_start((205, 0, 0))) == "#330000"


def test_shades_run_from_start_to_end():
    start, end = (51, 0, 0), (205, 0, 0)
    assert shade_rgb(start, end, 0, 8) == start
    assert shade_rgb(start, end, 7, 8) == end
    assert shade_rgb(start, end, 0, 1) == end
    assert shade_rgb((0, 0, 255), (255, 0, 0), 1, 3) == (128, 0, 128)


def test_shade_roles_round_trip():
    assert shade_parts(shade(2, 5)[1]) == (2, 5)
    with pytest.raises(ValueError):
        shade(0, MAX_STEPS)


def _window(layout, fill):
    """A window the layout's size with ``fill(along)`` in every bars cell."""
    rows = layout.bars.y + layout.bars.height + 1
    cols = layout.bars.x + layout.bars.width + 1
    window = [[None] * cols for _ in range(rows)]
    bars = layout.bars
    for y in range(bars.y, bars.y + bars.height):
        for x in range(bars.x, bars.x + bars.width):
            along = bars.y + bars.height - 1 - y
            window[y][x] = fill(along)
    return window


def test_shade_window_shades_series_by_height():
    layout = compute_layout(1, 8, LayoutSpec(relative=False))
    window = _window(layout, lambda _: Cell("█", series(1), BACKGROUND))
    shaded = shade_window(window, layout)
    bottom = layout.bars.y + layout.bars.height - 1
    assert shaded[bottom][0].fg == shade(1, 0)
    assert shaded[layout.bars.y][0].fg == shade(1, 7)
    assert shaded[bottom][0].bg == BACKGROUND


def test_shade_window_shades_both_halves_of_a_partial_cell_alike():
    layout = compute_layout(1, 4, LayoutSpec(relative=False))
    window = _window(layout, lambda _: Cell("▄", series(0), series(1)))
    shaded = shade_window(window, layout)
    cell = shaded[layout.bars.y][0]
    assert cell.fg == shade(0, 3) and cell.bg == shade(1, 3)


def test_shade_window_shades_the_base_zone_as_series_0():
    # A single-value bar below its first threshold is zone 0: the base color.
    layout = compute_layout(1, 4, LayoutSpec(relative=False))
    window = _window(layout, lambda _: Cell("█", zone(0), BACKGROUND))
    assert shade_window(window, layout)[layout.bars.y][0].fg == shade(0, 3)


def test_shade_window_leaves_zones_markers_text_and_empty_cells():
    layout = compute_layout(1, 4, LayoutSpec(relative=False))
    kept = [
        Cell("█", zone(1), BACKGROUND),
        Cell("─", marker(0), BACKGROUND),
        Cell("5", TEXT, BACKGROUND),
        EMPTY_CELL,
    ]
    window = _window(layout, lambda along: kept[along])
    assert shade_window(window, layout) == window


def test_shade_window_does_not_touch_cells_outside_the_bars():
    layout = compute_layout(1, 4, LayoutSpec(relative=False))
    window = _window(layout, lambda _: EMPTY_CELL)
    outside = Cell("█", series(0), BACKGROUND)
    window[-1][-1] = outside
    assert shade_window(window, layout)[-1][-1] == outside


def test_shade_window_horizontal_runs_left_to_right():
    layout = compute_layout(8, 1, LayoutSpec(relative=False, orient="horizontal"))
    bars = layout.bars
    window = [[None] * (bars.x + bars.width) for _ in range(bars.y + bars.height)]
    for x in range(bars.x, bars.x + bars.width):
        window[bars.y][x] = Cell("█", series(0), BACKGROUND)
    shaded = shade_window(window, layout)
    assert shaded[bars.y][bars.x].fg == shade(0, 0)
    assert shaded[bars.y][bars.x + bars.width - 1].fg == shade(0, 7)
