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

"""Segments x series values."""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses._charts.scale import round_up
from tkcurses.bargraph._model import AutoScale, Model


def test_starts_zeroed_and_dirty():
    model = Model(segments=2, series=3)
    assert model.rows() == ((0, 0, 0), (0, 0, 0))
    assert model.dirty


@pytest.mark.parametrize(
    ("segments", "series", "message"),
    [
        (0, 1, "segments must be an integer >= 1, not 0"),
        (1, 0, "series must be an integer >= 1, not 0"),
        (True, 1, "segments must be an integer >= 1, not True"),
        (1.5, 1, "segments must be an integer >= 1, not 1.5"),
    ],
)
def test_rejects_bad_shape(segments, series, message):
    # A program sees these as the widget's TclError, so the words count.
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        Model(segments, series)


def test_set_and_get():
    model = Model(2, 2)
    model.dirty = False
    model.set(1, [3, 4])
    assert model.get(1) == (3.0, 4.0)
    assert model.dirty


def test_set_checks_length_index_and_finiteness():
    model = Model(1, 2)
    for bad, message in (
        ([1], "expected 2 values, got 1"),
        ([1, 2, 3], "expected 2 values, got 3"),
        ([1, float("nan")], "values must be finite: [1.0, nan]"),
    ):
        with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
            model.set(0, bad)
    with pytest.raises(ValueError, match=r"^segment 1 out of range 0-0$"):
        model.set(1, [1, 2])


def test_set_all_needs_every_segment():
    model = Model(2, 1)
    model.set_all([[1], [2]])
    assert model.rows() == ((1.0,), (2.0,))
    with pytest.raises(ValueError, match=r"^expected 2 segments, got 1$"):
        model.set_all([[1]])


def test_resize_keeps_values():
    model = Model(2, 2)
    model.set_all([[1, 2], [3, 4]])
    model.resize(segments=3, series=3)
    assert model.rows() == ((1, 2, 0), (3, 4, 0), (0, 0, 0))
    model.resize(segments=1, series=1)
    assert model.rows() == ((1,),)


def test_resize_marks_the_model_dirty_and_takes_the_new_shape():
    model = Model(2, 2)
    model.dirty = False
    model.resize(segments=2)
    assert model.dirty
    model.resize(series=3)
    model.set(1, [1, 2, 3])
    with pytest.raises(ValueError, match=r"^expected 3 values, got 2$"):
        model.set(1, [1, 2])
    for options, name in (({"segments": 0}, "segments"), ({"series": 0}, "series")):
        with pytest.raises(ValueError, match=f"^{name} must be an integer >= 1"):
            model.resize(**options)


# ------------------------------------------------------------- round_up ----


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ((0,), 1),
        ((0.3,), 0.5),
        ((1,), 1),
        ((1.01,), 2),
        ((7,), 10),
        ((100,), 100),
        ((101,), 200),
        ((4321,), 5000),
        ((51, 50), 100),
        ((0, 50), 100),
        ((5, 1, "log"), 10),
        ((11, 1, "log"), 100),
        ((0, 1, "log"), 10),
        ((100, 1, "log", 2), 128),
        ((40, 0, "linear", 10, 1), 60),
        ((88_000, 0, "linear", 10, "binary"), 100 * 1024),
        ((4.5e6, 0, "linear", 10, "binary"), 5 * 2**20),
        ((90, 0, "linear", 10, 1), 120),
        ((4000, 0, "linear", 10, 1), 7200),
        ((700, 0, "linear", 10, 1e-3), 1000),
        # Below one, the steps go on 1, 2, 5 down to a trillionth.
        ((0.003,), 0.005),
        ((1.5e-12,), 2e-12),
        ((5e-14,), 1e-12),
        # A minimum between 0 and 1 is still a floor.
        ((0.4, 0.5), 1),
        # On a power: that power, not the next.
        ((10, 1, "log"), 10),
        # A minimum on a power: the scale ends a power above it.
        ((10, 10, "log"), 100),
        ((100, 100, "log"), 1000),
        # Past the clock's two weeks, in days: 10, 20, 50...
        ((15 * 86400, 0, "linear", 10, 1), 20 * 86400),
        ((15 * 1440, 0, "linear", 10, 60), 20 * 1440),
        ((0.3, 0, "linear", 10, 1), 0.5),
        # In minutes, the steps below one are still seconds' steps.
        ((0.3, 0, "linear", 10, 60), 0.5),
        ((150 * 86400, 0, "linear", 10, 1), 200 * 86400),
        # A log scale's end just above its minimum is still above it.
        ((9, 6, "log"), 10),
        # Binary steps go 200, 500, then 1 KiB: never 1000 of anything.
        ((150, 0, "linear", 10, "binary"), 200),
        ((550 * 1024, 0, "linear", 10, "binary"), 1024**2),
        ((1000 * 1024, 0, "linear", 10, "binary"), 1024**2),
    ],
)
def test_round_up(args, expected):
    assert round_up(*args) == expected


# ------------------------------------------------------------- autoscale ----


def test_autoscale_grows_at_once():
    scale = AutoScale(hold_ms=5000)
    assert scale.update(42, 0) == 50
    assert scale.update(130, 10) == 200
    assert not scale.shrinking


def test_autoscale_shrinks_only_after_the_hold():
    scale = AutoScale(hold_ms=5000)
    scale.update(180, 0)
    assert scale.update(30, 1000) == 200
    assert scale.shrinking
    assert scale.update(30, 5999) == 200
    assert scale.update(30, 6000) == 50
    assert not scale.shrinking


def test_autoscale_shrinks_to_the_most_needed_in_the_hold():
    scale = AutoScale(hold_ms=1000)
    scale.update(180, 0)
    scale.update(30, 100)
    scale.update(90, 500)
    assert scale.update(10, 1100) == 100


def test_a_return_to_the_maximum_cancels_the_shrink():
    scale = AutoScale(hold_ms=1000)
    scale.update(180, 0)
    scale.update(30, 100)
    scale.update(150, 600)
    assert not scale.shrinking
    assert scale.update(30, 1200) == 200


def test_autoscale_on_a_log_scale_uses_powers():
    scale = AutoScale(hold_ms=0, minimum=1, scaletype="log")
    assert scale.update(2500, 0) == 10_000
    assert scale.update(2, 1) == 10


def test_autoscale_refuses_a_negative_hold():
    with pytest.raises(ValueError, match="hold_ms"):
        AutoScale(hold_ms=-1)


@given(
    st.lists(
        st.tuples(st.floats(0, 1e9, allow_nan=False), st.floats(0, 10_000)),
        min_size=1,
        max_size=40,
    )
)
def test_autoscale_never_cuts_a_value_off(steps):
    scale = AutoScale(hold_ms=2000)
    now = 0.0
    for value, wait in steps:
        now += wait
        maximum = scale.update(value, now)
        assert maximum >= value
        assert maximum == round_up(maximum)  # always a round number
