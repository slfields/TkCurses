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

"""Bars at 1/8 cell: runs, the two-colors-per-cell rule, and the grid."""

from __future__ import annotations

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses.bargraph._glyphs import EMPTY, FULL, HORIZONTAL_RAMP, VERTICAL_RAMP
from tkcurses.bargraph._layout import LayoutSpec, compute_layout
from tkcurses.bargraph._render import (
    BACKGROUND,
    Cell,
    Run,
    cells_along,
    render_bars,
    segment_runs,
    series,
    threshold_runs,
    zone,
    zoned_runs,
)

S0, S1, S2 = series(0), series(1), series(2)
BG = BACKGROUND

# With maximum == peak, one data unit is one point (an eighth of a cell).
UNIT = {"maximum": 64, "peak_points": 64}


# ------------------------------------------------------------------ runs ----


def test_stacked_lays_values_end_to_end():
    assert segment_runs([3, 2, 4], "stacked", **UNIT) == [
        Run(S0, 0, 3),
        Run(S1, 3, 5),
        Run(S2, 5, 9),
    ]


def test_stacked_skips_zero_and_negative_values():
    assert segment_runs([3, 0, -4, 2], "stacked", **UNIT) == [
        Run(S0, 0, 3),
        Run(series(3), 3, 5),
    ]


def test_stacked_clamps_the_total_to_maximum():
    assert segment_runs([40, 40], "stacked", **UNIT) == [
        Run(S0, 0, 40),
        Run(S1, 40, 64),
    ]


def test_stacked_rounds_the_running_total():
    # 1/3 + 1/3 + 1/3 of 8 points: each alone rounds to 3, which would make 9.
    third = 8 / 3
    runs = segment_runs([third] * 3, "stacked", maximum=8, peak_points=8)
    assert runs[-1].end == 8


def test_overlay_shows_the_shortest_value_on_top():
    assert segment_runs([9, 4, 6], "overlay", **UNIT) == [
        Run(S1, 0, 4),
        Run(S2, 4, 6),
        Run(S0, 6, 9),
    ]


def test_overlay_tie_goes_to_the_lower_series():
    assert segment_runs([5, 5], "overlay", **UNIT) == [Run(S0, 0, 5)]


def test_bad_mode():
    with pytest.raises(ValueError):
        segment_runs([1], "pie", **UNIT)  # type: ignore[arg-type]


# ----------------------------------------------------------------- cells ----


def test_one_series():
    assert cells_along([Run(S0, 0, 12)], 3) == [
        Cell(FULL, S0, BG),
        Cell("▄", S0, BG),
        Cell(EMPTY, BG, BG),
    ]


def test_boundary_inside_a_cell_uses_both_colors():
    assert cells_along([Run(S0, 0, 3), Run(S1, 3, 16)], 2) == [
        Cell("▃", S0, S1),
        Cell(FULL, S1, BG),
    ]


def test_three_colors_merge_the_smallest_into_its_larger_neighbour():
    # s0 3, s1 2, s2 3 in one cell: s1 is smallest; its neighbours tie at 3,
    # so it goes to the lower one, s0.
    runs = [Run(S0, 0, 3), Run(S1, 3, 5), Run(S2, 5, 8)]
    assert cells_along(runs, 1) == [Cell("▅", S0, S2)]


def test_a_crowded_tip_cell_keeps_the_tip():
    # s0 2, s1 3, then background: s0 merges into s1 and the tip stays at 5.
    runs = [Run(S0, 0, 2), Run(S1, 2, 5)]
    assert cells_along(runs, 1) == [Cell("▅", S1, BG)]


def test_horizontal_uses_the_left_blocks():
    assert cells_along([Run(S0, 0, 3)], 1, "horizontal") == [Cell("▍", S0, BG)]


def test_runs_past_the_length_are_clipped():
    assert cells_along([Run(S0, 0, 40)], 2) == [Cell(FULL, S0, BG)] * 2


def _filled(cells: list[Cell]) -> int:
    """Points covered by color: what the eye reads as the bar's length."""
    total = 0
    for cell in cells:
        if cell.char == FULL or (cell.char != EMPTY and cell.bg != BG):
            # Full, or a partial glyph whose background is another color.
            total += 8
        elif cell.char != EMPTY:
            ramp = VERTICAL_RAMP if cell.char in VERTICAL_RAMP else HORIZONTAL_RAMP
            total += ramp.index(cell.char) + 1
    return total


VALUES = st.lists(st.floats(-10, 80, allow_nan=False), min_size=1, max_size=5)


@given(VALUES, st.integers(1, 10))
def test_stacked_tip_is_exact(values, length):
    runs = segment_runs(values, "stacked", **UNIT)
    tip = runs[-1].end if runs else 0
    assert _filled(cells_along(runs, length)) == min(tip, length * 8)


@given(VALUES, st.integers(1, 10))
def test_overlay_tip_is_the_longest_value(values, length):
    runs = segment_runs(values, "overlay", **UNIT)
    longest = max(min(max(v, 0), 64) for v in values)
    assert (runs[-1].end if runs else 0) == round(longest)
    assert _filled(cells_along(runs, length)) == min(round(longest), length * 8)


@given(VALUES, st.sampled_from(["stacked", "overlay"]))
def test_every_cell_has_at_most_two_roles_and_is_consistent(values, mode):
    for cell in cells_along(segment_runs(values, mode, **UNIT), 9):
        if cell.char == EMPTY:
            assert cell == Cell()
        elif cell.char == FULL:
            assert cell.fg != BG
        else:
            assert cell.fg != BG
            assert cell.fg != cell.bg


# ------------------------------------------------------------------ grid ----


def _text(grid: list[list[Cell]]) -> list[str]:
    return ["".join(cell.char for cell in row) for row in grid]


def test_vertical_grid_grows_up_from_the_bottom():
    layout = compute_layout(3, 2, LayoutSpec(segments=2, relative=False))
    grid = render_bars([[12], [5]], layout, "stacked", maximum=16, peak_points=16)
    assert _text(grid) == [
        "▄  ",
        "█ ▅",
    ]
    assert grid[1][0].fg == S0
    assert grid[1][1] == Cell()


def test_vertical_grid_is_as_thick_as_the_track():
    layout = compute_layout(5, 1, LayoutSpec(segments=2, thickness=2, relative=False))
    grid = render_bars([[8], [4]], layout, "stacked", maximum=8, peak_points=8)
    assert _text(grid) == ["██ ▄▄"]


def test_horizontal_grid_grows_right_from_the_left():
    spec = LayoutSpec(orient="horizontal", segments=2, relative=False)
    layout = compute_layout(2, 3, spec)
    grid = render_bars([[11], [3]], layout, "stacked", maximum=16, peak_points=16)
    assert _text(grid) == [
        "█▍",
        "  ",
        "▍ ",
    ]


def test_stacked_two_series_vertical():
    layout = compute_layout(1, 3, LayoutSpec(relative=False))
    grid = render_bars([[10, 9]], layout, "stacked", maximum=24, peak_points=24)
    # s0 0-10, s1 10-19: cell 0 full s0; cell 1 ▂ s0 over s1; cell 2 ▃ s1.
    assert [row[0] for row in grid] == [
        Cell("▃", S1, BG),
        Cell("▂", S0, S1),
        Cell(FULL, S0, BG),
    ]


def test_clipped_segments_are_skipped():
    layout = compute_layout(2, 1, LayoutSpec(segments=3, relative=False))
    grid = render_bars([[8], [8], [8]], layout, "stacked", maximum=8, peak_points=8)
    assert _text(grid) == ["█ "]


# ------------------------------------------------------- threshold zones ----

# White base, yellow from 80, red from 90; 100 units over 100 points.
LEVELS = (80.0, 90.0)
Z0, Z1, Z2 = zone(0), zone(1), zone(2)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (70, [Run(Z0, 0, 70)]),
        (85, [Run(Z0, 0, 80), Run(Z1, 80, 85)]),
        (95, [Run(Z0, 0, 80), Run(Z1, 80, 90), Run(Z2, 90, 95)]),
        (-5, []),
        (500, [Run(Z0, 0, 80), Run(Z1, 80, 90), Run(Z2, 90, 100)]),
    ],
)
def test_only_the_part_above_each_level_changes_color(value, expected):
    assert threshold_runs(value, LEVELS, maximum=100, peak_points=100) == expected


def test_zones_in_the_grid():
    # Two cells, 16 points: yellow from 10, red from 13; value 15.
    spec = LayoutSpec(orient="horizontal", relative=False)
    layout = compute_layout(2, 1, spec)
    grid = render_bars(
        [[15]], layout, "stacked", maximum=16, peak_points=16, levels=(10, 13)
    )
    # Cell 0: base, full. Cell 1: base 2, yellow 3, red 2, then background.
    # Red is the highest zone reached, so it is kept: base merges into
    # yellow, then yellow into red. The tip stays at 15 and shows red.
    assert grid[0] == [Cell(FULL, Z0, BG), Cell("▉", Z2, BG)]


def test_series_do_not_protect_the_top():
    # The same crowded cell as series: the plain rule, smallest first.
    runs = [Run(S0, 8, 10), Run(S1, 10, 13), Run(S2, 13, 15)]
    assert cells_along(runs, 2, "horizontal")[1] == Cell("▉", S1, BG)


def test_a_zone_boundary_inside_a_cell():
    layout = compute_layout(1, 2, LayoutSpec(relative=False))
    grid = render_bars(
        [[16]], layout, "stacked", maximum=16, peak_points=16, levels=(11,)
    )
    assert [row[0] for row in grid] == [Cell("▃", Z0, Z1), Cell(FULL, Z0, BG)]


def test_zones_on_a_stack_apply_to_its_total():
    # User 50 + system 40 = 90: series colors up to 80, then the first
    # threshold's color whichever series is there.
    runs = segment_runs([50, 40], "stacked", maximum=100, peak_points=100)
    assert zoned_runs(runs, (80, 90), maximum=100, peak_points=100) == [
        Run(series(0), 0, 50),
        Run(series(1), 50, 80),
        Run(zone(1), 80, 90),
    ]
    runs = segment_runs([50, 45], "stacked", maximum=100, peak_points=100)
    assert zoned_runs(runs, (80, 90), maximum=100, peak_points=100)[-2:] == [
        Run(zone(1), 80, 90),
        Run(zone(2), 90, 95),
    ]


def test_zones_leave_a_bar_below_every_level_alone():
    runs = segment_runs([30, 20], "stacked", maximum=100, peak_points=100)
    assert zoned_runs(runs, (80, 90), maximum=100, peak_points=100) == runs


def test_zones_on_an_overlay_apply_to_the_longest_value():
    runs = segment_runs([85, 40], "overlay", maximum=100, peak_points=100)
    assert zoned_runs(runs, (80,), maximum=100, peak_points=100) == [
        Run(series(1), 0, 40),
        Run(series(0), 40, 80),
        Run(zone(1), 80, 85),
    ]


@given(
    st.lists(st.floats(0, 60, allow_nan=False), min_size=1, max_size=4),
    st.sampled_from(["stacked", "overlay"]),
)
def test_zones_keep_the_bar_and_only_recolor_above_a_level(values, mode):
    runs = segment_runs(values, mode, maximum=100, peak_points=100)
    zoned = zoned_runs(runs, (80, 90), maximum=100, peak_points=100)
    # Same extent, contiguous, and a zone role only at or above 80.
    assert [r.start for r in zoned][:1] == [r.start for r in runs][:1]
    assert [r.end for r in zoned][-1:] == [r.end for r in runs][-1:]
    for before, after in itertools.pairwise(zoned):
        assert before.end == after.start
    for run in zoned:
        assert (run.role[0] == "zone") == (run.start >= 80)


def test_render_bars_zones_a_stacked_bar():
    layout = compute_layout(1, 2, LayoutSpec(relative=False))
    grid = render_bars(
        [[8, 6]], layout, "stacked", maximum=16, peak_points=16, levels=(12,)
    )
    # Bottom cell: series 0. Top cell: series 1 for 4 points, zone 1 for 2,
    # then 2 empty - three pieces, so series 1 merges into the zone, which
    # as the alert color at the tip is never the one merged away.
    assert grid[1][0] == Cell(FULL, series(0), BG)
    assert grid[0][0] == Cell("▆", zone(1), BG)


@given(st.floats(-10, 120, allow_nan=False), st.integers(1, 15))
def test_zone_tip_is_exact(value, length):
    runs = threshold_runs(value, LEVELS, maximum=100, peak_points=100)
    tip = round(min(max(value, 0), 100))
    cells = cells_along(runs, length, keep_top=True)
    assert _filled(cells) == min(tip, length * 8)
    # The cell holding the tip shows the highest zone reached.
    if runs and tip <= length * 8:
        tip_cell = cells[(tip - 1) // 8]
        assert runs[-1].role in (tip_cell.fg, tip_cell.bg)


def test_a_horizontal_bar_inside_a_box_is_drawn_in_its_own_row():
    # A box moves the bars region down a row; the grid is still indexed
    # from the region's corner, so the bar is in its row 0.
    spec = LayoutSpec(relative=False, orient="horizontal", borderwidth=1)
    layout = compute_layout(12, 3, spec)
    assert layout.bars.y > 0
    grid = render_bars([[8]], layout, "stacked", maximum=8, peak_points=8)
    assert grid[0][0].char == "█"
