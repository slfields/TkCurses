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

"""Threshold zones: only the part above each level changes color."""

from __future__ import annotations

import pytest

from tkcurses.bargraph._thresholds import Zone, parse_thresholds, zones

LEVELS = [80.0, 90.0]  # yellow at 80, red at 90; maximum 100, peak 100 points


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, []),
        (70, [Zone(0, 0, 70)]),
        (80, [Zone(0, 0, 80)]),
        (85, [Zone(0, 0, 80), Zone(1, 80, 85)]),
        (95, [Zone(0, 0, 80), Zone(1, 80, 90), Zone(2, 90, 95)]),
        (100, [Zone(0, 0, 80), Zone(1, 80, 90), Zone(2, 90, 100)]),
    ],
)
def test_zones(value, expected):
    assert zones(value, LEVELS, maximum=100, peak_points=100) == expected


def test_parse_sorts_and_converts_percentages():
    parsed = parse_thresholds([("90%", "red"), (40, "yellow")], maximum=50)
    assert parsed == ((40.0, "yellow"), (45.0, "red"))


def test_parse_rejects_duplicates():
    with pytest.raises(ValueError):
        parse_thresholds([(80, "yellow"), ("80%", "red")], maximum=100)
