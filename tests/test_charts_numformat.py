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

"""The number format: digits, decimals, rounding, scale prefixes and units."""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses.bargraph._numformat import NumberFormat, for_readout, widest


@pytest.mark.parametrize(
    ("fmt", "value", "text"),
    [
        # The examples agreed for the option, digits=3.
        (NumberFormat(digits=3), 0.1234, "0.123"),
        (NumberFormat(digits=3), 12.5, "12.5"),
        (NumberFormat(digits=3), 1234, "1.23k"),
        (NumberFormat(digits=3, units="$", placement="prefix"), 1234, "$1.23k"),
        (NumberFormat(digits=3, units="B", unitscale="binary"), 2_500_000, "2.38MiB"),
        # Unset: as {:g} wrote tick labels, never 50.0.
        (NumberFormat(), 50, "50"),
        (NumberFormat(), 2.5, "2.5"),
        (NumberFormat(), 0, "0"),
        (NumberFormat(), 100, "100"),
        # Once scaled, as far as it goes.
        (NumberFormat(), 1_234_567, "1.23457M"),
        # Fixed decimals, capped by the digits.
        (NumberFormat(digits=3, decimals=1), 5, "5.0"),
        (NumberFormat(digits=3, decimals=1), 12.34, "12.3"),
        (NumberFormat(digits=3, decimals=1), 1234, "1.2k"),
        (NumberFormat(decimals=2), 0, "0.00"),
        # Rounding that adds a digit scales: 999.6 is 1000 at three digits.
        (NumberFormat(digits=3), 999.6, "1k"),
        (NumberFormat(digits=3), 999_600, "1M"),
        # Rounding modes.
        (NumberFormat(digits=2), 0.125, "0.13"),
        (NumberFormat(digits=2, rounding="down"), 0.129, "0.12"),
        (NumberFormat(digits=2, rounding="up"), 0.121, "0.13"),
        # Spacing applies to what follows the number.
        (NumberFormat(digits=3, units="B", space=True), 1234, "1.23 kB"),
        (NumberFormat(digits=3, units="ms", space=True), 12, "12 ms"),
        (NumberFormat(digits=3, space=True), 12, "12"),
        (NumberFormat(digits=3, space=True), 1234, "1.23 k"),
        # A prefix is written against the number, space or not.
        (NumberFormat(units="$", placement="prefix", space=True), 5, "$5"),
        (NumberFormat(digits=3, units="$", placement="prefix"), -1234, "-$1.23k"),
        # No scaling: the whole number, rounded to the digits.
        (NumberFormat(digits=3, unitscale="none"), 1234, "1230"),
        (NumberFormat(units="%"), 80, "80%"),
        (NumberFormat(digits=3), -0.0001, "-0.0001"),
    ],
)
def test_examples(fmt, value, text):
    assert fmt.format(value) == text


def test_rounding_never_carries_past_the_ceiling():
    assert NumberFormat(digits=3).format(99.97, 99.97) == "99.9"
    assert NumberFormat(digits=3, rounding="up").format(99.91, 99.95) == "99.9"
    assert NumberFormat(digits=3, rounding="up").format(99.91, 100) == "100"
    # A value that is itself over the ceiling is written as it is.
    assert NumberFormat(digits=3).format(150, 100) == "150"


def test_plain_leaves_the_units_off():
    fmt = NumberFormat(digits=3, units="$", placement="prefix")
    assert fmt.plain(1234) == "1.23k"


def test_readout_writes_whole_numbers_unless_told_otherwise():
    assert for_readout(NumberFormat(units="%")).format(42.4) == "42%"
    assert for_readout(NumberFormat(decimals=1)).format(42.44) == "42.4"
    assert for_readout(NumberFormat(digits=2)).format(4.25) == "4.3"


def test_widest():
    # Whole numbers, as the readout writes them by default: 100 is widest.
    assert widest(for_readout(NumberFormat()), 100) == 3
    # Six digits: 100 * 1/256 is 0.390625.
    assert widest(NumberFormat(), 100) == 8
    assert widest(for_readout(NumberFormat(units="%")), 100) == 4
    # 99.9 is wider than 100 itself.
    assert widest(NumberFormat(digits=3, decimals=1), 100) == 5


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"digits": 0}, "digits"),
        ({"digits": 16}, "digits"),
        ({"decimals": -1}, "decimals"),
        ({"rounding": "sideways"}, "rounding"),
        ({"unitscale": "metric"}, "unitscale"),
        ({"placement": "middle"}, "placement"),
    ],
)
def test_bad_settings(kwargs, message):
    with pytest.raises(ValueError, match=message):
        NumberFormat(**kwargs)


def test_infinity_is_refused():
    with pytest.raises(ValueError, match="inf"):
        NumberFormat().format(float("inf"))


NUMBER = re.compile(r"^-?(0|[1-9]\d*)(\.\d+)?$")

values = st.floats(0, 1e15, allow_nan=False, allow_infinity=False)
digits = st.integers(1, 6)


@given(value=values, digits=digits, rounding=st.sampled_from(["nearest", "down", "up"]))
def test_never_more_significant_digits_than_asked(value, digits, rounding):
    text = NumberFormat(digits=digits, rounding=rounding).plain(value).rstrip("kMGTPE")
    assert NUMBER.match(text), text
    significant = text.replace(".", "").lstrip("0")
    assert len(significant) <= digits or set(significant) == {"0"}


@given(value=values, digits=digits)
def test_no_leading_zeros_but_one_before_the_point(value, digits):
    text = NumberFormat(digits=digits).plain(value).rstrip("kMGTPE")
    assert NUMBER.match(text), text


@given(value=values, decimals=st.integers(0, 4))
def test_decimals_are_a_fixed_count(value, decimals):
    text = NumberFormat(digits=6, decimals=decimals).plain(value).rstrip("kMGTPE")
    shown = len(text.split(".")[1]) if "." in text else 0
    assert shown == decimals


SCALE = {"": 1, "k": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "P": 1e15, "E": 1e18}


@given(
    value=st.floats(0, 1e9, allow_nan=False),
    ceiling=st.floats(1e-3, 1e9, allow_nan=False),
    digits=digits,
    rounding=st.sampled_from(["nearest", "down", "up"]),
)
def test_a_value_under_the_ceiling_never_shows_over_it(
    value, ceiling, digits, rounding
):
    if value > ceiling:
        value, ceiling = ceiling, value
    text = NumberFormat(digits=digits, rounding=rounding).plain(value, ceiling)
    number = text.rstrip("kMGTPE")
    assert float(number) * SCALE[text[len(number) :]] <= ceiling * (1 + 1e-12)


# ------------------------------------------------------------------ time ----

TIME = NumberFormat(units="ms", unitscale="time", space=True, digits=3)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (0, "0 ms"),
        (12, "12 ms"),
        (0.25, "250 µs"),
        (0.0004, "400 ns"),
        (1000, "1 s"),
        (999.6, "1 s"),  # rounds up to the next unit
        (59_999, "1 min"),
        (90_000, "1.5 min"),
        (5_400_000, "1.5 h"),
        (3 * 86_400_000, "3 d"),
        (400 * 86_400_000, "400 d"),  # days are the last unit
    ],
)
def test_time_is_written_in_the_largest_unit_reached(value, text):
    assert TIME.format(value) == text


def test_time_units_name_the_data_unit():
    assert NumberFormat(units="s", unitscale="time").format(0.012) == "12ms"
    assert NumberFormat(units="us", unitscale="time").format(1500) == "1.5ms"
    assert NumberFormat(units="h", unitscale="time").format(36) == "1.5d"
    assert NumberFormat(units="min", unitscale="time").format(0.5) == "30s"


def test_time_needs_a_time_unit():
    with pytest.raises(ValueError, match="time unit"):
        NumberFormat(units="m", unitscale="time")


def test_time_readout_keeps_fractions():
    assert for_readout(NumberFormat(units="ms", unitscale="time")).format(90_000) == (
        "1.5min"
    )


# ---------------------------------------------------------------- SI down ----


@pytest.mark.parametrize(
    ("fmt", "value", "text"),
    [
        (NumberFormat(units="s", digits=3), 0.012, "12ms"),
        (NumberFormat(units="A", space=True), 0.0000025, "2.5 µA"),
        (NumberFormat(units="s", digits=3), 0.0009996, "1ms"),
        (NumberFormat(units="s"), 0.5, "500ms"),
        (NumberFormat(units="s"), 2.5, "2.5s"),
        # Never for a bare number, a percentage or a currency.
        (NumberFormat(), 0.5, "0.5"),
        (NumberFormat(units="%"), 0.5, "0.5%"),
        (NumberFormat(units="$", placement="prefix"), 0.5, "$0.5"),
        (NumberFormat(units="B", unitscale="binary"), 0.5, "0.5B"),
    ],
)
def test_si_scales_down_to_the_fewest_digits(fmt, value, text):
    assert fmt.format(value) == text


TIME_SECONDS = {"ns": 1e-9, "µs": 1e-6, "ms": 1e-3, "s": 1, "min": 60, "h": 3600}
TIME_SECONDS["d"] = 86400
TIME_TEXT = re.compile(r"^(\d+(?:\.\d+)?) (ns|µs|ms|s|min|h|d)$")


@given(
    value=st.floats(1e-6, 1e12, allow_nan=False),
    ceiling=st.floats(1e-6, 1e12, allow_nan=False),
    digits=digits,
    rounding=st.sampled_from(["nearest", "down", "up"]),
)
def test_time_in_one_unit_never_over_the_ceiling(value, ceiling, digits, rounding):
    if value > ceiling:
        value, ceiling = ceiling, value
    fmt = NumberFormat(
        units="ms", unitscale="time", space=True, digits=digits, rounding=rounding
    )
    match = TIME_TEXT.match(fmt.format(value, ceiling))
    assert match, fmt.format(value, ceiling)
    number, unit = float(match[1]), match[2]
    assert number * TIME_SECONDS[unit] * 1000 <= ceiling * (1 + 1e-9)
    # The largest unit reached: never 1000 ms, never 60 s.
    units = list(TIME_SECONDS)
    if unit != "d" and number:
        assert number < TIME_SECONDS[units[units.index(unit) + 1]] / TIME_SECONDS[unit]


@pytest.mark.parametrize(
    ("fmt", "maximum", "expected"),
    [
        # Each is found only by sampling just under a power of ten, a
        # step of 1024 or a minute, where a value gains a digit or scales:
        # evenly spaced samples find a column a cell or two narrower.
        (NumberFormat(digits=2), 7, 7),
        (NumberFormat(), 1_536_000, 8),
        (NumberFormat(digits=2, unitscale="binary"), 5000, 7),
        (NumberFormat(digits=3, unitscale="time", units="s"), 1_536_000, 7),
    ],
)
def test_widest_finds_the_values_just_under_an_edge(fmt, maximum, expected):
    assert widest(fmt, maximum) == expected


def test_for_readout_writes_time_to_three_digits_and_keeps_the_rest():
    time = for_readout(NumberFormat(unitscale="time", units="s", space=True))
    assert (time.digits, time.decimals, time.space) == (3, None, True)
    plain = for_readout(NumberFormat(units="%", space=True, rounding="down"))
    assert (plain.digits, plain.decimals) == (None, 0)
    assert (plain.space, plain.rounding, plain.units) == (True, "down", "%")


_SPREAD = [
    (
        {"digits": 3},
        [(9.996, "10"), (99.96, "100"), (0.009996, "0.01"), (1234567, "1.23M")],
    ),
    (
        {"units": "B", "unitscale": "binary", "digits": 3},
        [
            (1023.9, "1KiB"),
            (1024, "1KiB"),
            (1536, "1.5KiB"),
            (1048000, "0.999MiB"),
            (0.5, "0.5B"),
        ],
    ),
    (
        {"units": "s", "unitscale": "time", "digits": 3},
        [
            (59.99, "1min"),
            (59.4, "59.4s"),
            (90, "1.5min"),
            (3599.9, "1h"),
            (259200, "3d"),
            (0.012, "12ms"),
            (0.0005, "500µs"),
            (0, "0s"),
        ],
    ),
    (
        {"units": "min", "unitscale": "time", "digits": 2},
        [(0.5, "30s"), (59.99, "1h"), (90, "1.5h"), (3600, "2.5d")],
    ),
    (
        {"units": "ms", "unitscale": "time", "digits": 3},
        [(999.6, "1s"), (0.4, "400µs")],
    ),
    ({"decimals": 1}, [(0.04, "0.0"), (9.96, "10.0"), (1234.56, "1234.6")]),
    ({"digits": 2, "rounding": "down"}, [(9.99, "9.9"), (0.0199, "0.019")]),
    ({"digits": 2, "rounding": "up"}, [(9.01, "9.1"), (0.0101, "0.011")]),
]


@pytest.mark.parametrize(
    ("options", "value", "text"),
    [(options, value, text) for options, pairs in _SPREAD for value, text in pairs],
)
def test_a_spread_of_values_on_each_scale(options, value, text):
    # Each side of where rounding carries a value to the next unit or the
    # next digit, on every kind of scale.
    assert NumberFormat(**options).format(value, 1) == text
