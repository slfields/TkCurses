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

"""Where each character sits once a tab can be wider than one cell.

Every expectation was compared against real tkinter (Tk 9.0) in a monospace
font before it was written down, so the numbers below are measurements
rather than beliefs. Nine cases matched on the first run, the click inverse
included.
"""

from __future__ import annotations

import pytest

from tkcurses._core.textlayout import (
    TabStops,
    char_at,
    column_of,
    columns_of,
)

# --------------------------------------------------------------------- stops


def test_the_default_is_every_eight_columns():
    """Tk's default, and exact here rather than an average character width."""
    stops = TabStops()
    assert [stops.nth(n) for n in range(4)] == [8, 16, 24, 32]


def test_explicit_stops_come_back_as_given():
    stops = TabStops((4, 10, 20))
    assert [stops.nth(n) for n in range(3)] == [4, 10, 20]


def test_extrapolation_repeats_the_last_interval():
    """Measured: 4 and 10 continue 16, 22 - the gap between the last two."""
    stops = TabStops((4, 10))
    assert [stops.nth(n) for n in range(5)] == [4, 10, 16, 22, 28]


def test_a_single_stop_extrapolates_by_itself():
    """Nothing to subtract from, so the stop IS the interval. Measured: a
    lone stop at 10 continued 20, 30, 40."""
    stops = TabStops((10,))
    assert [stops.nth(n) for n in range(4)] == [10, 20, 30, 40]


def test_after_finds_the_first_stop_strictly_past_a_column():
    """Strictly: a tab already sitting on a stop must move, or it takes no
    room at all."""
    stops = TabStops((4, 10))
    assert stops.after(0) == 4
    assert stops.after(3) == 4
    assert stops.after(4) == 10, "on a stop, so the next one"
    assert stops.after(11) == 16, "and past the list, by extrapolation"


# -------------------------------------------------------------------- layout


def test_a_line_without_tabs_is_the_identity():
    assert columns_of("hello") == [0, 1, 2, 3, 4]


def test_a_line_without_tabs_starts_at_its_margin():
    assert columns_of("hello", start=4) == [4, 5, 6, 7, 8]


def test_a_tab_advances_to_the_next_stop():
    assert columns_of("a\tb", stops=TabStops((10,))) == [0, 1, 10]


def test_the_nth_tab_takes_the_nth_stop():
    """Tabular, which is Tk's default. Measured against tkinter."""
    laid = columns_of("a\tb\tc\td\te", stops=TabStops((4, 10)))
    assert laid == [0, 1, 4, 5, 10, 11, 16, 17, 22]


def test_a_tabular_tab_past_its_stop_inserts_one_space():
    """The documented fallback, and measured: text ending at column 8 with a
    stop at 4 put the next character at 9 - not back at 4, and not at the
    stop after."""
    laid = columns_of("abcdefgh\tX", stops=TabStops((4, 20)))
    assert laid[-1] == 9


def test_wordprocessor_takes_the_next_stop_to_the_right():
    """The same line, the other style: 20 rather than 9."""
    laid = columns_of("abcdefgh\tX", stops=TabStops((4, 20)), style="wordprocessor")
    assert laid[-1] == 20


def test_stops_are_measured_from_the_widget_not_from_the_margin():
    """The finding that would have been got wrong by assuming.

    An indented line puts its first character at the margin and its tab
    still lands on the widget's own grid, which is what makes columns line
    up down the page whatever the indent. Measured: indent 8, stops 10 and
    20, gave 8, 9, 10, 11, 20 - identical stop columns to an unindented
    line.
    """
    laid = columns_of("a\tb\tc", start=8, stops=TabStops((10, 20)))
    assert laid == [8, 9, 10, 11, 20]


# ------------------------------------------------------------------- reading


def test_column_of_reads_a_character_off_the_line():
    assert column_of("ab\tcd", 3, stops=TabStops((10,))) == 10


def test_column_of_past_the_end_is_where_the_line_ends():
    """Where an insert cursor at the end of the line belongs."""
    assert column_of("abc", 3) == 3
    assert column_of("ab\t", 3, stops=TabStops((10,))) == 10, "a trailing tab"


def test_a_click_anywhere_in_a_tab_answers_with_the_tab():
    """Measured from tkinter, column by column: with a stop at 10,
    ``ab<TAB>cd`` answered every click from 2 to 9 with the tab's index."""
    stops = TabStops((10,))
    assert [char_at("ab\tcd", c, stops=stops) for c in range(13)] == [
        0,
        1,
        2,
        2,
        2,
        2,
        2,
        2,
        2,
        2,
        3,
        4,
        5,
    ]


def test_a_column_before_the_line_lands_on_its_first_character():
    assert char_at("abc", 0, start=4) == 0


def test_a_column_past_the_line_lands_past_its_last():
    assert char_at("abc", 99) == 3


# ------------------------------------------------------------------ inverses


@pytest.mark.parametrize(
    ("text", "start", "stops"),
    [
        ("hello", 0, TabStops()),
        ("a\tb\tc", 0, TabStops()),
        ("a\tb\tc", 8, TabStops((10, 20))),
        ("\tleading", 0, TabStops((4,))),
        ("trailing\t", 0, TabStops((4, 20))),
        ("a\t\tb", 0, TabStops((4, 8))),
        ("abcdefgh\tX", 0, TabStops((4, 20))),
    ],
)
def test_the_two_directions_are_exact_inverses(text, start, stops):
    """The property the epic rests on.

    bbox resolves an index to a cell and _index_at_cell resolves a cell back
    to an index. If they ever disagree, clicking a character selects a
    different one from the one drawn under the pointer - and neither side
    looks wrong on its own, which is why this is asserted directly.
    """
    for index in range(len(text)):
        column = column_of(text, index, start=start, stops=stops)
        assert char_at(text, column, start=start, stops=stops) == index, (
            f"{text!r} index {index} -> column {column} -> "
            f"{char_at(text, column, start=start, stops=stops)}"
        )


@pytest.mark.parametrize("style", ["tabular", "wordprocessor"])
def test_every_column_of_a_line_maps_back_into_it(style):
    """Going the other way: no column inside the line is unreachable.

    A column in the middle of a tab's span belongs to that tab, so the round
    trip lands on the START of the run rather than on the column itself.
    That is not a failure of the inverse - it is what a run means - so the
    check is that the answer is a real character whose span contains the
    column.
    """
    text, stops = "a\tbc\td", TabStops((4, 10))
    laid = columns_of(text, stops=stops, style=style)
    for column in range(laid[0], laid[-1] + 1):
        index = char_at(text, column, stops=stops, style=style)
        assert 0 <= index < len(text)
        assert laid[index] <= column
        if index + 1 < len(laid):
            assert column < laid[index + 1]
