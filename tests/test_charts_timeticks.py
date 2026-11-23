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

"""Ticks on a time axis: on local time, counted on the calendar through a
change of clocks, labelled with what changes, and never overlapping."""

import datetime as dt
import os
import time
from itertools import pairwise

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tkcurses._charts.timeticks import time_ticks

# US Central, with daylight saving, written out so no tz database is needed.
ZONE = "CST6CDT,M3.2.0,M11.1.0"


@pytest.fixture(autouse=True)
def zone():
    before = os.environ.get("TZ")
    os.environ["TZ"] = ZONE
    time.tzset()
    yield
    if before is None:
        del os.environ["TZ"]
    else:
        os.environ["TZ"] = before
    time.tzset()


def at(*fields):
    return dt.datetime(*fields).timestamp()


def test_an_hour_in_minutes():
    ticks = time_ticks(at(2026, 11, 23, 14), at(2026, 11, 23, 15), 60)
    assert ticks.unit == "minute"
    assert ticks.labels[:3] == ("14:00", "14:10", "14:20")
    assert ticks.context == "Nov 23, 2026"


def test_midnight_says_the_day():
    ticks = time_ticks(at(2026, 11, 23, 18), at(2026, 11, 24, 6), 60)
    assert "Nov 24" in ticks.labels
    assert "00:00" not in ticks.labels


def test_january_says_the_year():
    ticks = time_ticks(at(2026, 9, 1), at(2027, 4, 1), 60)
    assert ticks.unit == "month"
    assert ticks.labels == ("Sep", "Oct", "Nov", "Dec", "2027", "Feb", "Mar", "Apr")
    assert ticks.context == "2026"


def test_days_through_the_end_of_daylight_saving_are_each_midnight():
    # Clocks went back at 02:00 on 1 November 2026: that day was 25 hours.
    ticks = time_ticks(at(2026, 10, 30), at(2026, 11, 3), 50)
    assert ticks.unit == "day"
    hours = {dt.datetime.fromtimestamp(v).hour for v in ticks.values}
    assert hours == {0}
    assert ticks.labels == ("Oct 30", "Oct 31", "Nov 1", "Nov 2", "Nov 3")


def test_weeks_start_on_monday():
    ticks = time_ticks(at(2026, 11, 1), at(2026, 12, 31), 40)
    if ticks.unit == "week":
        assert {dt.datetime.fromtimestamp(v).weekday() for v in ticks.values} == {0}


def test_years():
    ticks = time_ticks(at(1990, 1, 1), at(2030, 1, 1), 60)
    assert ticks.unit == "year"
    assert ticks.labels[0] == "1990"


def test_nothing_fits_or_nothing_spans():
    assert time_ticks(at(2026, 1, 1), at(2026, 1, 2), 3).values == ()
    assert time_ticks(at(2026, 1, 1), at(2026, 1, 1), 60).values == ()


@settings(max_examples=60, deadline=None)
@given(
    st.datetimes(dt.datetime(1980, 1, 1), dt.datetime(2060, 1, 1)),
    st.integers(1, 10**9),
    st.integers(8, 160),
)
def test_ticks_rise_stay_inside_and_their_labels_do_not_overlap(start, seconds, length):
    low = start.timestamp()
    high = low + seconds
    ticks = time_ticks(low, high, length)
    values = list(ticks.values)
    assert values == sorted(set(values))
    assert all(low <= v <= high for v in values)
    places = []
    for value, label in zip(values, ticks.labels, strict=True):
        centre = (value - low) / (high - low) * (length - 1)
        begin = max(0, min(round(centre - (len(label) - 1) / 2), length - len(label)))
        places.append((begin, begin + len(label)))
    for (_, end), (begin, _) in pairwise(places):
        assert begin >= end + 2
