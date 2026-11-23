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

"""An XY chart's value axis: Kibana's bounds, nice ends, and a range that
always holds what it is to show."""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses.xychart._axes import value_range


def ends(span):
    return (span.minimum, span.maximum)


def test_full_reaches_zero_and_data_does_not():
    assert ends(value_range([40, 72], bounds="full")) == (0, 80)
    assert ends(value_range([40, 72], bounds="data")) == (40, 75)
    assert ends(value_range([-40, -12], bounds="full")) == (-40, 0)


def test_with_an_area_data_is_full():
    assert ends(value_range([40, 72], bounds="data", areas=True)) == (0, 80)


def test_nice_can_be_turned_off():
    assert ends(value_range([40, 72], bounds="data", nice=False)) == (40, 72)


def test_custom_is_exact_and_falls_back_to_full_for_an_end_not_given():
    assert ends(value_range([40, 72], bounds="custom", minimum=5, maximum=95)) == (
        5,
        95,
    )
    assert ends(value_range([40, 72], bounds="custom", maximum=100)) == (0, 100)
    assert ends(value_range([40, 72], bounds="custom", minimum=50)) == (50, 72)


def test_custom_must_be_in_order():
    with pytest.raises(ValueError, match="must be above minimum"):
        value_range([1], bounds="custom", minimum=10, maximum=5)


def test_a_log_axis_spans_powers_and_never_reaches_zero():
    span = value_range([3, 0, -4, 700], bounds="full", scaletype="log")
    assert ends(span) == (1, 1000)
    with pytest.raises(ValueError, match="minimum above 0"):
        value_range([3], bounds="custom", minimum=0, maximum=10, scaletype="log")


def test_percentage_is_zero_to_a_hundred():
    assert ends(value_range([3, 9], percentage=True)) == (0, 100)


def test_no_values_and_one_value():
    assert ends(value_range([])) == (0, 1)
    assert ends(value_range([None, None], scaletype="log")) == (1, 10)
    assert ends(value_range([50, 50], bounds="data")) == (25, 75)
    assert ends(value_range([0], bounds="data")) == (0, 1)


def test_bad_bounds():
    with pytest.raises(ValueError, match="must be full, data or custom"):
        value_range([1], bounds="tight")


numbers = st.floats(-1e9, 1e9, allow_nan=False)


@given(
    st.lists(st.one_of(st.none(), numbers), max_size=20),
    st.sampled_from(["full", "data"]),
    st.booleans(),
)
def test_the_range_holds_every_value_and_full_holds_zero(values, bounds, nice):
    span = value_range(values, bounds=bounds, nice=nice)
    assert span.maximum > span.minimum
    for value in values:
        if value is not None:
            assert span.minimum <= value <= span.maximum
    if bounds == "full":
        assert span.minimum <= 0 <= span.maximum


@given(st.lists(st.floats(1e-6, 1e9), min_size=1, max_size=20))
def test_a_log_range_holds_every_value_between_powers(values):
    span = value_range(values, scaletype="log")
    assert span.minimum <= min(values) and max(values) <= span.maximum
    for end in ends(span):
        exponent = math.log10(end)
        assert math.isclose(exponent, round(exponent), abs_tol=1e-9)
