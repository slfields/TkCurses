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

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses.bargraph._model import AutoScale, Model
from tkcurses.bargraph._scale import round_up


def test_starts_zeroed_and_dirty():
    model = Model(segments=2, series=3)
    assert model.rows() == ((0, 0, 0), (0, 0, 0))
    assert model.dirty


@pytest.mark.parametrize(("segments", "series"), [(0, 1), (1, 0), (True, 1), (1.5, 1)])
def test_rejects_bad_shape(segments, series):
    with pytest.raises(ValueError):
        Model(segments, series)


def test_set_and_get():
    model = Model(2, 2)
    model.dirty = False
    model.set(1, [3, 4])
    assert model.get(1) == (3.0, 4.0)
    assert model.dirty


def test_set_checks_length_index_and_finiteness():
    model = Model(1, 2)
    for bad in ([1], [1, 2, 3], [1, float("nan")]):
        with pytest.raises(ValueError):
            model.set(0, bad)
    with pytest.raises(ValueError):
        model.set(1, [1, 2])


def test_set_all_needs_every_segment():
    model = Model(2, 1)
    model.set_all([[1], [2]])
    assert model.rows() == ((1.0,), (2.0,))
    with pytest.raises(ValueError):
        model.set_all([[1]])


def test_resize_keeps_values():
    model = Model(2, 2)
    model.set_all([[1, 2], [3, 4]])
    model.resize(segments=3, series=3)
    assert model.rows() == ((1, 2, 0), (3, 4, 0), (0, 0, 0))
    model.resize(segments=1, series=1)
    assert model.rows() == ((1,),)


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
