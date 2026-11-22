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

"""The chart widgets' shared text and colour helpers."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from tkcurses._charts.color import hex_color, shade_rgb
from tkcurses._charts.text import ELLIPSIS, clusters, fit
from tkcurses._core.cells import cells


def test_clusters_give_a_wide_character_two_cells():
    assert clusters("a界") == [("a", 1), ("界", 2)]


def test_a_combining_mark_joins_the_character_before_it():
    assert clusters("Café") == [("C", 1), ("a", 1), ("f", 1), ("é", 1)]


def test_a_leading_combining_mark_is_dropped():
    assert clusters("́a") == [("a", 1)]


def test_fit_keeps_text_that_fits():
    assert fit("web", 3) == "web"


def test_fit_cuts_with_an_ellipsis():
    assert fit("postgres", 5) == "post" + ELLIPSIS
    assert fit("postgres", 1) == ELLIPSIS
    assert fit("postgres", 0) == ""


@given(st.text(max_size=12), st.integers(0, 14))
def test_fit_never_takes_more_cells_than_it_is_given(text, width):
    assert cells(fit(text, width)) <= width


def test_shade_rgb_runs_from_start_to_end():
    assert shade_rgb((0, 0, 0), (200, 100, 50), 0, 3) == (0, 0, 0)
    assert shade_rgb((0, 0, 0), (200, 100, 50), 1, 3) == (100, 50, 25)
    assert shade_rgb((0, 0, 0), (200, 100, 50), 2, 3) == (200, 100, 50)
    assert shade_rgb((0, 0, 0), (1, 2, 3), 0, 1) == (1, 2, 3)


def test_hex_color():
    assert hex_color((255, 0, 16)) == "#ff0010"


def test_one_value_where_a_list_is_wanted_is_a_list_of_one():
    from tkcurses._charts.options import items

    assert items(5) == (5,)
    assert items("red blue") == ("red", "blue")
    assert items(("red",)) == ("red",)
    assert items(None) == ()
