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

"""From values to pixels: points placed by their axes, joined straight,
in steps or smoothly without overshooting, thinned when dense, clipped
to the plot, and dotted where filled in."""

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses._charts.geometry import Rect
from tkcurses._charts.scale import ValueRange
from tkcurses.xychart._path import (
    area,
    clip_line,
    clip_polygon,
    dashes,
    m4,
    pixels,
    points_shown,
    project,
    trace,
)

PLOT = Rect(10, 4, 41, 21)  # pixels: x 10..50, y 4..24


def test_points_are_placed_by_their_axes():
    placed = project(
        [0, 10, 5], [0, 100, None], ValueRange(10, 0), ValueRange(100, 0), PLOT
    )
    assert placed == [(10, 24), (50, 4), None]


def test_one_x_goes_in_the_middle():
    assert project([3], [0], None, ValueRange(1, 0), PLOT) == [(30, 24)]


def test_a_log_axis_cannot_place_zero():
    assert project([0], [0], None, ValueRange(10, 1, "log"), PLOT) == [None]


def test_straight_joins_the_points():
    (piece,) = trace([(0, 0), (10, 5), (20, 0)], [False] * 3)
    assert piece.points == ((0, 0), (10, 5), (20, 0))
    assert not piece.dotted


def test_a_step_holds_each_value_until_the_next_x():
    (piece,) = trace([(0, 0), (10, 5), (20, 2)], [False] * 3, "step")
    assert piece.points == ((0, 0), (10, 0), (10, 5), (20, 5), (20, 2))


def test_smooth_passes_through_every_point_and_samples_each_column():
    run = [(0, 0), (4, 8), (10, 2)]
    (piece,) = trace(run, [False] * 3, "smooth")
    assert [x for x, _ in piece.points] == list(range(11))
    for point in run:
        assert point in piece.points


def test_a_gap_breaks_the_line():
    pieces = trace([(0, 0), (1, 1), None, (3, 3), (4, 4)], [False] * 5)
    assert [p.points for p in pieces] == [((0, 0), (1, 1)), ((3, 3), (4, 4))]


def test_segments_through_a_filled_value_are_dotted():
    pieces = trace(
        [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)], [False, False, True, False, False]
    )
    assert [(p.points, p.dotted) for p in pieces] == [
        (((0, 0), (1, 1)), False),
        (((1, 1), (2, 2), (3, 3)), True),
        (((3, 3), (4, 4)), False),
    ]


def test_a_dense_run_is_reduced_and_drawn_straight():
    run = [(0.0, 5), (0.2, 9), (0.3, 1), (0.4, 4), (1.0, 3)]
    kept, _ = m4(run, [False] * 5)
    assert kept == [(0.0, 5), (0.2, 9), (0.3, 1), (0.4, 4), (1.0, 3)]
    (piece,) = trace(run, [False] * 5, "smooth")
    assert piece.points == tuple(kept)


def test_m4_keeps_first_lowest_highest_and_last_of_a_column():
    run = [(0, 5), (0.1, 6), (0.2, 1), (0.3, 7), (0.35, 9), (0.4, 4)]
    kept, _ = m4(run, [False] * 6)
    assert kept == [(0, 5), (0.2, 1), (0.35, 9), (0.4, 4)]


def test_a_line_leaving_the_plot_is_cut_where_it_leaves():
    pieces = clip_line([(10, 24), (30, -16), (50, 24)], PLOT)
    assert pieces == [[(10, 24), (20, 4)], [(40, 4), (50, 24)]]


def test_a_line_outside_the_plot_is_gone():
    assert clip_line([(0, 0), (5, 0)], PLOT) == []


def test_a_polygon_is_cut_to_the_plot():
    shape = clip_polygon([(10, 24), (30, -16), (50, 24)], PLOT)
    assert all(10 <= x <= 50 and 4 <= y <= 24 for x, y in shape)
    assert (20, 4) in shape and (40, 4) in shape


def test_an_area_closes_on_its_baseline_or_on_the_one_below():
    (shape,) = area([(0, 5), (10, 2)], None, 9)
    assert shape == [(0, 5), (10, 2), (10, 9), (0, 9)]
    (shape,) = area([(0, 5), (10, 2)], [(0, 7), (10, 6)], 9)
    assert shape == [(0, 5), (10, 2), (10, 6), (0, 7)]


def test_an_area_has_a_gap_where_its_top_does():
    shapes = area([(0, 5), (1, 5), None, (3, 5), (4, 5)], None, 9)
    assert len(shapes) == 2


def test_pixels_round_once_and_drop_repeats():
    assert pixels([(0.4, 0.4), (0.6, 0.4), (1.2, 0.6), (1.4, 1.4)]) == [
        (0, 0),
        (1, 0),
        (1, 1),
    ]


def test_dashes_are_two_on_two_off():
    assert dashes([(0, 0), (9, 0)]) == [
        [(0, 0), (1, 0)],
        [(4, 0), (5, 0)],
        [(8, 0), (9, 0)],
    ]


def test_points_show_when_sparse():
    assert points_shown("auto", [0, 4, 8])
    assert not points_shown("auto", [0, 4, 7])
    assert points_shown("show", [0, 1])
    assert not points_shown("hide", [0, 40])
    with pytest.raises(ValueError, match="must be auto, show or hide"):
        points_shown("some", [])


def test_bad_interpolation():
    with pytest.raises(ValueError, match="must be straight, smooth or step"):
        trace([], [], "curvy")


# ------------------------------------------------------------- properties

runs = st.lists(st.floats(-100, 100, allow_nan=False), min_size=2, max_size=12).map(
    lambda ys: [(i * 5.0, y) for i, y in enumerate(ys)]
)


@given(runs)
def test_smooth_never_overshoots_the_points_it_joins(run):
    (piece,) = trace(run, [False] * len(run), "smooth")
    for (x0, y0), (x1, y1) in itertools.pairwise(run):
        low, high = min(y0, y1), max(y0, y1)
        for x, y in piece.points:
            if x0 <= x <= x1:
                assert low - 1e-6 <= y <= high + 1e-6


coords = st.floats(-60, 120, allow_nan=False)


@given(st.lists(st.tuples(coords, coords), min_size=1, max_size=10))
def test_whatever_is_clipped_is_inside_the_plot(points):
    def inside(x, y):
        return 10 - 1e-6 <= x <= 50 + 1e-6 and 4 - 1e-6 <= y <= 24 + 1e-6

    for piece in clip_line(points, PLOT):
        assert all(inside(x, y) for x, y in piece)
    assert all(inside(x, y) for x, y in clip_polygon(points, PLOT))


@given(
    st.lists(
        st.tuples(st.floats(0, 5, allow_nan=False), coords), min_size=1, max_size=40
    )
)
def test_m4_keeps_each_columns_extremes_and_ends(points):
    run = sorted(points)
    kept, _ = m4(run, [False] * len(run))
    for column in {round(x) for x, _ in run}:
        mine = [p for p in run if round(p[0]) == column]
        theirs = [p for p in kept if round(p[0]) == column]
        assert theirs[0] == mine[0] and theirs[-1] == mine[-1]
        assert min(y for _, y in theirs) == min(y for _, y in mine)
        assert max(y for _, y in theirs) == max(y for _, y in mine)
        assert len(theirs) <= 4
