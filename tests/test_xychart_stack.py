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

"""Stacking areas: each sits on the ones before it, a percentage stack
reaches 100, negatives go down from zero, and lines are left alone."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses.xychart._stack import Layer, stack


def layer(name, ys, kind="area", xs=None):
    xs = tuple(xs or range(len(ys)))
    return Layer(name, kind, xs, tuple(ys), tuple(False for _ in ys))


def test_each_area_sits_on_the_ones_before_it():
    a, b = stack([layer("a", [1, 2]), layer("b", [10, 20])])
    assert a.lows == (0, 0) and a.highs == (1, 2)
    assert b.lows == (1, 2) and b.highs == (11, 22)


def test_a_percentage_stack_reaches_a_hundred():
    a, b = stack([layer("a", [1, 3]), layer("b", [3, 1])], "percentage")
    assert a.highs == (25, 75)
    assert b.highs == (100, 100)


def test_an_x_whose_total_is_zero_is_a_gap_in_a_percentage_stack():
    a, b = stack([layer("a", [0, 1]), layer("b", [0, 1])], "percentage")
    assert a.highs[0] is None and b.highs[0] is None


def test_negative_values_stack_down_from_zero():
    a, b, c = stack([layer("a", [5]), layer("b", [-3]), layer("c", [-2])])
    assert (a.lows, a.highs) == ((0,), (5,))
    assert (b.lows, b.highs) == ((0,), (-3,))
    assert (c.lows, c.highs) == ((-3,), (-5,))


def test_a_missing_value_adds_nothing_and_leaves_a_gap():
    _a, b, c = stack([layer("a", [1, 1]), layer("b", [2, None]), layer("c", [4, 4])])
    assert b.highs == (3, None)
    assert c.lows == (3, 1)


def test_areas_stack_at_every_x_any_of_them_has():
    a, b = stack([layer("a", [1], xs=[0]), layer("b", [5], xs=[1])])
    assert a.xs == b.xs == (0, 1)
    assert a.highs == (1, None)
    assert b.lows == (1, 0)  # its gap still sits on a


def test_lines_and_unstacked_areas_are_drawn_from_zero_as_given():
    line, _area = stack([layer("l", [7], kind="line"), layer("a", [3])], "stacked")
    assert line.lows is None and line.highs == (7,)
    (alone,) = stack([layer("a", [3])], "unstacked")
    assert alone.lows is None and alone.highs == (3,)


def test_a_bad_mode():
    with pytest.raises(ValueError, match="must be stacked, percentage or unstacked"):
        stack([], "piled")


columns = st.lists(
    st.lists(
        st.one_of(st.none(), st.floats(-1e6, 1e6, allow_nan=False)),
        min_size=4,
        max_size=4,
    ),
    min_size=1,
    max_size=5,
)


@given(columns)
def test_each_band_is_its_own_value_tall_and_the_sides_add_up(series):
    bands = stack([layer(str(i), ys) for i, ys in enumerate(series)])
    for x in range(4):
        up = down = 0.0
        for band, ys in zip(bands, series, strict=True):
            value = ys[x]
            if value is None:
                assert band.highs[x] is None
                continue
            assert band.highs[x] - band.lows[x] == pytest.approx(value, abs=1e-6)
            if value >= 0:
                up += value
                assert band.highs[x] == pytest.approx(up, abs=1e-3)
            else:
                down += value
                assert band.highs[x] == pytest.approx(down, abs=1e-3)


@given(columns)
def test_a_percentage_stack_spans_a_hundred_of_sizes(series):
    bands = stack([layer(str(i), ys) for i, ys in enumerate(series)], "percentage")
    for x in range(4):
        sizes = [abs(b.highs[x] - b.lows[x]) for b in bands if b.highs[x] is not None]
        total = sum(abs(ys[x]) for ys in series if ys[x] is not None)
        if total > 0:
            assert sum(sizes) == pytest.approx(100, abs=1e-6)
        else:
            assert sizes == []


def test_an_area_whose_total_overflows_is_a_gap_there():
    big = 1.7e308
    a, b = stack([layer("a", [big, 1]), layer("b", [big, 1])])
    assert a.highs == (big, 1)
    assert b.lows == (big, 1) and b.highs == (None, 2)


def test_a_percentage_of_a_total_past_the_largest_float():
    a, b = stack([layer("a", [1.7e308]), layer("b", [1.7e308])], "percentage")
    assert a.highs == (50.0,) and b.highs == (100.0,)
