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

"""Missing values: known values are never changed, only gaps are filled,
each by its rule, and what was filled is marked."""

from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses.xychart._fit import END_VALUES, MISSING, fit

XS = [0, 1, 2, 3, 4, 5, 6]
YS = [None, 10, None, None, 40, None, None]


@pytest.mark.parametrize(
    ("missing", "inner"),
    [
        ("zero", [0, 0]),
        ("linear", [20, 30]),
        ("last", [10, 10]),
        ("next", [40, 40]),
    ],
)
def test_each_rule_fills_a_gap_between_known_values(missing, inner):
    fitted = fit(XS, YS, missing, "hide")
    assert list(fitted.ys) == [None, 10, *inner, 40, None, None]
    assert list(fitted.filled) == [False, False, True, True, False, False, False]


def test_hide_leaves_every_gap_and_the_ends():
    for endvalues in END_VALUES:
        fitted = fit(XS, YS, "hide", endvalues)
        assert list(fitted.ys) == YS
        assert not any(fitted.filled)


@pytest.mark.parametrize(
    ("endvalues", "before", "after"),
    [("hide", None, None), ("zero", 0, 0), ("nearest", 10, 40)],
)
def test_end_values_fill_before_the_first_and_after_the_last(endvalues, before, after):
    fitted = fit(XS, YS, "linear", endvalues)
    assert fitted.ys[0] == before
    assert fitted.ys[5:] == (after, after)
    assert fitted.filled[0] == (before is not None)


def test_linear_goes_by_x_not_by_position():
    fitted = fit([0, 1, 4], [0, None, 40], "linear")
    assert fitted.ys[1] == 10


def test_a_series_with_no_values():
    assert fit([1, 2], [None, None], "linear", "zero").ys == (0, 0)
    assert fit([1, 2], [None, None], "linear", "nearest").ys == (None, None)
    assert fit([], [], "linear", "zero").ys == ()


def test_bad_names_are_refused():
    with pytest.raises(ValueError, match="bad missing"):
        fit([1], [1], "carry")
    with pytest.raises(ValueError, match="bad endvalues"):
        fit([1], [1], "zero", "far")


values = st.lists(
    st.one_of(st.none(), st.floats(-1e6, 1e6, allow_nan=False)), max_size=30
)


@given(values, st.sampled_from(MISSING), st.sampled_from(END_VALUES))
def test_known_values_are_never_changed_and_only_gaps_are_marked(ys, missing, ends):
    xs = list(range(len(ys)))
    fitted = fit(xs, ys, missing, ends)
    for y, out, filled in zip(ys, fitted.ys, fitted.filled, strict=True):
        if y is not None:
            assert out == y
            assert not filled
        else:
            assert filled == (out is not None)


@given(values, st.sampled_from(MISSING[1:]))
def test_a_filled_gap_lies_within_its_neighbours(ys, missing):
    xs = list(range(len(ys)))
    fitted = fit(xs, ys, missing, "hide")
    known = [i for i, y in enumerate(ys) if y is not None]
    for before, after in pairwise(known):
        low, high = sorted((ys[before], ys[after]))
        for i in range(before + 1, after):
            if missing == "zero":
                assert fitted.ys[i] == 0
            else:
                assert low - 1e-6 <= fitted.ys[i] <= high + 1e-6
