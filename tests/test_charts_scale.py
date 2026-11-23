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

"""What XYChart added to the shared scale: a square-root scale, positions
that are not clamped, rounding down, and ticks whose labels fit."""

import math
from itertools import pairwise, takewhile

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from tkcurses._charts.scale import (
    ValueRange,
    fitted_ticks,
    label_start,
    round_steps,
)


def test_a_square_root_scale_gives_a_quarter_of_the_top_half_the_length():
    span = ValueRange(100, 0, "sqrt")
    assert span.position(25) == pytest.approx(0.5)
    assert span.fraction(100) == 1.0


def test_a_square_root_scale_mirrors_negative_values():
    span = ValueRange(100, -100, "sqrt")
    assert span.position(-25) == pytest.approx(0.25)
    assert span.position(0) == pytest.approx(0.5)


def test_positions_are_not_clamped():
    span = ValueRange(10, 0)
    assert span.position(20) == 2.0
    assert span.position(-5) == -0.5
    assert span.fraction(20) == 1.0  # BarGraph's stays clamped


def test_a_log_scale_cannot_place_zero_or_below():
    span = ValueRange(1000, 1, "log")
    assert span.position(0) is None
    assert span.position(-1) is None
    assert span.position(10) == pytest.approx(1 / 3)


def test_an_unknown_scale_type_names_all_three():
    with pytest.raises(ValueError, match="must be linear, log or sqrt"):
        ValueRange(10, 0, "cubic")


def width_of(tick):
    return len(f"{tick:g}")


def label_spans(span, ticks, length):
    out = []
    for tick in ticks:
        width = width_of(tick)
        start = label_start(span.position(tick), width, length)
        out.append((start, start + width))
    return out


def test_ticks_take_the_smallest_round_step_that_fits():
    assert fitted_ticks(ValueRange(100, 0), 60, width_of) == [
        0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100
    ]  # fmt: skip
    assert fitted_ticks(ValueRange(100, 0), 20, width_of) == [0, 50, 100]


def test_a_log_axis_takes_powers():
    # 1, 2, 5, 10, 20... would need 59 cells; the powers alone fit in 40.
    assert fitted_ticks(ValueRange(10000, 1, "log"), 40, width_of) == [
        1, 10, 100, 1000, 10000
    ]  # fmt: skip
    # With room, 2 and 5 times each power as well.
    assert fitted_ticks(ValueRange(1000, 1, "log"), 80, width_of)[:3] == [1, 2, 5]
    assert fitted_ticks(ValueRange(10000, 1, "log"), 20, width_of) == [1, 100, 10000]


def test_no_ticks_when_no_label_fits():
    assert fitted_ticks(ValueRange(100500, 100000), 3, width_of) == []


spans = st.tuples(
    st.floats(-1e6, 1e6, allow_nan=False), st.floats(1e-3, 1e6, allow_nan=False)
).map(lambda pair: (pair[0], pair[0] + pair[1]))


@given(spans, st.integers(1, 120), st.sampled_from(["linear", "sqrt"]))
def test_labels_never_overlap_and_ticks_are_round_and_inside(pair, length, kind):
    low, high = pair
    assume(high - low > abs(high) * 1e-9)
    span = ValueRange(high, low, kind)
    ticks = fitted_ticks(span, length, width_of)
    assert ticks == sorted(ticks)
    slack = 1e-9 * (high - low) + 1e-9 * max(abs(low), abs(high))
    assert all(low - slack <= t <= high + slack for t in ticks)
    places = label_spans(span, ticks, length)
    for (_, end), (start, _) in pairwise(places):
        assert start >= end + 2
    assert all(start >= 0 and end <= length for start, end in places)
    if len(ticks) > 1:
        step = ticks[1] - ticks[0]
        assert any(math.isclose(step, r, rel_tol=1e-6) for r in _steps_near(step))


def _steps_near(step):
    return [r for r in takewhile(lambda r: r < step * 2, round_steps()) if r > step / 2]
