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

"""Absolute and percentage scales, and value -> points."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses.bargraph._scale import (
    Scale,
    ValueRange,
    parse_level,
    parse_scale,
    to_points,
)


@pytest.mark.parametrize("value", [8, "8", 64, " 20 "])
def test_absolute(value):
    scale = parse_scale(value)
    assert not scale.relative
    assert scale.peak_points(available_cells=1) == int(str(value).strip())


@pytest.mark.parametrize(
    "value", [7, 0, -8, "7", True, 8.0, "abc", "%", "0%", "101%", "nan%"]
)
def test_rejects(value):
    with pytest.raises(ValueError):
        parse_scale(value)


def test_percentage_follows_the_frame():
    scale = parse_scale("75%")
    assert scale.relative
    assert scale.peak_points(available_cells=10) == 60  # 80 points * 75%
    assert scale.peak_points(available_cells=20) == 120


def test_percentage_never_below_one_cell():
    assert parse_scale("10%").peak_points(available_cells=2) == 8
    assert parse_scale("50%").peak_points(available_cells=0) == 8


def test_str_round_trips():
    assert str(Scale(points=64)) == "64"
    assert str(parse_scale("75%")) == "75%"


def test_levels():
    assert parse_level(90, 200) == 90
    assert parse_level("80%", 200) == 160
    with pytest.raises(ValueError):
        parse_level("x", 100)


def test_to_points_clamps():
    assert to_points(-5, 100, 64) == 0
    assert to_points(50, 100, 64) == 32
    assert to_points(500, 100, 64) == 64


@given(st.floats(-1e6, 1e6), st.integers(8, 10_000))
def test_to_points_is_within_the_peak(value, peak):
    assert 0 <= to_points(value, 100, peak) <= peak


# ------------------------------------------------------------ value range ----


def test_a_linear_range_from_a_minimum():
    span = ValueRange(100, minimum=50)
    assert [span.to_points(v, 80) for v in (0, 50, 75, 100, 200)] == [0, 0, 40, 80, 80]


def test_a_log_range_gives_each_power_the_same_length():
    span = ValueRange(1000, minimum=1, scaletype="log")
    assert [span.to_points(v, 30) for v in (0.5, 1, 10, 100, 1000, 5000)] == [
        0,
        0,
        10,
        20,
        30,
        30,
    ]
    two = ValueRange(1024, minimum=1, scaletype="log", base=2)
    assert two.to_points(32, 100) == 50


def test_a_plain_maximum_is_linear_from_zero():
    assert to_points(50, 100, 80) == to_points(50, ValueRange(100), 80) == 40


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"maximum": 10, "minimum": 10}, "above minimum"),
        ({"maximum": 10, "minimum": 0, "scaletype": "log"}, "minimum above 0"),
        ({"maximum": 10, "minimum": 1, "scaletype": "log", "base": 1}, "logbase"),
        ({"maximum": 10, "scaletype": "cubic"}, "scaletype"),
        ({"maximum": math.inf}, "finite"),
    ],
)
def test_bad_ranges(kwargs, message):
    with pytest.raises(ValueError, match=message):
        ValueRange(**kwargs)


@given(
    low=st.floats(1e-6, 1e6),
    ratio=st.floats(1.001, 1e9),
    base=st.floats(1.1, 100),
    a=st.floats(0, 1e16, allow_nan=False),
    b=st.floats(0, 1e16, allow_nan=False),
    peak=st.integers(8, 4096),
)
def test_a_log_range_keeps_order_and_bounds(low, ratio, base, a, b, peak):
    span = ValueRange(low * ratio, minimum=low, scaletype="log", base=base)
    small, large = sorted((a, b))
    assert 0 <= span.to_points(small, peak) <= span.to_points(large, peak) <= peak
