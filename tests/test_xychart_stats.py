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

"""The legend's statistics: each against the plain way of working it out."""

from __future__ import annotations

import math
import statistics as reference

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses.xychart._stats import LABELS, STATISTICS, statistics


def test_every_statistic_has_a_label():
    assert set(LABELS) == set(STATISTICS)
    assert len(STATISTICS) == 16


def test_a_series_with_gaps():
    got = statistics([None, 4.0, 1.0, None, 7.0, 4.0, None], STATISTICS)
    assert got == {
        "average": 4.0,
        "median": 4.0,
        "min": 1.0,
        "max": 7.0,
        "range": 6.0,
        "last": None,
        "lastnonnull": 4.0,
        "first": None,
        "firstnonnull": 4.0,
        "difference": 0.0,
        "differencepercent": 0.0,
        "sum": 16.0,
        "count": 4.0,
        "distinctcount": 3.0,
        "variance": pytest.approx(4.5),
        "stddev": pytest.approx(math.sqrt(4.5)),
    }


def test_nothing_known_is_none_but_the_counts():
    got = statistics([None, None], STATISTICS)
    assert got["count"] == 0 and got["distinctcount"] == 0
    assert all(value is None for name, value in got.items() if "count" not in name)
    assert statistics([], ["last", "average"]) == {"last": None, "average": None}


def test_a_difference_from_zero_has_no_percentage():
    got = statistics([0.0, 5.0], ["difference", "differencepercent"])
    assert got == {"difference": 5.0, "differencepercent": None}
    assert statistics([-4.0, -2.0], ["differencepercent"]) == {
        "differencepercent": 50.0
    }


def test_only_what_is_asked_is_given_in_its_order():
    assert list(statistics([1.0], ["max", "min"])) == ["max", "min"]


values = st.lists(
    st.one_of(st.none(), st.floats(-1e6, 1e6, allow_nan=False)), min_size=1, max_size=60
)


@given(values)
def test_each_figure_is_the_plain_one(given_values):
    known = [v for v in given_values if v is not None]
    got = statistics(given_values, STATISTICS)
    if not known:
        return
    assert got["average"] == pytest.approx(reference.fmean(known), rel=1e-9, abs=1e-6)
    assert got["median"] == reference.median(known)
    assert got["sum"] == pytest.approx(math.fsum(known), rel=1e-9, abs=1e-6)
    assert got["variance"] == pytest.approx(
        reference.pvariance(known), rel=1e-6, abs=1e-3
    )
    assert got["min"] == min(known) and got["max"] == max(known)
    assert got["last"] == given_values[-1] and got["lastnonnull"] == known[-1]
