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

"""Tests for tkcurses._core.screen.

ScreenBuffer is pure, so it is tested directly and by property. CursesScreen
touches a real terminal, so it is tested through the pty harness.
"""

from __future__ import annotations

import curses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses._core.geometry import Rect
from tkcurses._core.screen import BLANK, Cell, ScreenBuffer


@pytest.fixture
def buffer():
    return ScreenBuffer(10, 4)


# ------------------------------------------------------------------- cells


def test_cell_defaults():
    cell = Cell()
    assert cell.char == BLANK
    assert cell.attr == curses.A_NORMAL
    assert not cell.dirty


def test_setting_a_cell_to_the_same_value_is_not_a_change():
    """An unchanged frame must not cost a repaint."""
    cell = Cell(char="x", fg="white", bg="black", attr=curses.A_NORMAL)
    assert not cell.set("x", "white", "black", curses.A_NORMAL)
    assert not cell.dirty
    assert cell.set("y", "white", "black", curses.A_NORMAL)
    assert cell.dirty


def test_changing_only_the_attribute_is_a_change():
    cell = Cell(char="x")
    assert cell.set("x", "white", "black", curses.A_BOLD)
    assert cell.attr == curses.A_BOLD


# ------------------------------------------------------------------ buffer


def test_dimensions(buffer):
    assert (buffer.width, buffer.height) == (10, 4)
    assert buffer.bounds == Rect(0, 0, 10, 4)


def test_negative_dimensions_are_rejected():
    with pytest.raises(ValueError, match="negative buffer size"):
        ScreenBuffer(-1, 4)


def test_write_and_read_back(buffer):
    assert buffer.write(1, 2, "hello") == 5
    assert buffer.text_at(1) == "  hello   "
    assert buffer.text_at(1, 2, 5) == "hello"


def test_write_truncates_at_the_right_edge(buffer):
    assert buffer.write(0, 7, "abcdef") == 3
    assert buffer.text_at(0) == "       abc"


def test_write_at_a_negative_column_shows_the_visible_part(buffer):
    """A partly off-screen widget draws what fits instead of failing."""
    assert buffer.write(0, -2, "abcdef") == 4
    assert buffer.text_at(0) == "cdef      "


def test_write_entirely_off_screen_does_nothing(buffer):
    assert buffer.write(0, -10, "abc") == 0
    assert buffer.write(0, 50, "abc") == 0
    assert buffer.write(99, 0, "abc") == 0
    assert buffer.write(-1, 0, "abc") == 0
    assert not buffer.is_dirty


def test_write_starting_past_the_right_edge_writes_nothing():
    """Regression: a negative available width used to slice a prefix and then
    write it out of bounds. Found by the property test below."""
    narrow = ScreenBuffer(1, 1)
    assert narrow.write(0, 2, "aa") == 0
    assert narrow.lines == [BLANK]
    assert not narrow.is_dirty


def test_empty_write_does_nothing(buffer):
    assert buffer.write(0, 0, "") == 0
    assert not buffer.is_dirty


def test_reads_outside_the_grid_are_an_error(buffer):
    """Writes clip, but an out-of-range read is a caller bug."""
    with pytest.raises(IndexError):
        buffer.cell(99, 0)


def test_fill(buffer):
    buffer.fill(Rect(1, 1, 3, 2), "#")
    assert buffer.lines[1] == " ###      "
    assert buffer.lines[2] == " ###      "
    assert buffer.lines[0] == BLANK * 10


def test_fill_is_clipped_to_the_grid(buffer):
    buffer.fill(Rect(8, 3, 10, 10), "#")
    assert buffer.lines[3] == "        ##"


def test_fill_outside_the_grid_does_nothing(buffer):
    buffer.fill(Rect(50, 50, 4, 4), "#")
    assert not buffer.is_dirty


def test_fill_requires_a_character(buffer):
    with pytest.raises(ValueError, match="must not be empty"):
        buffer.fill(buffer.bounds, "")


def test_clear_blanks_everything(buffer):
    buffer.write(0, 0, "text")
    buffer.clear_dirty()
    buffer.clear()
    assert buffer.lines == [BLANK * 10] * 4
    assert buffer.is_dirty


# ------------------------------------------------------------------- dirty


def test_a_fresh_buffer_is_clean(buffer):
    assert not buffer.is_dirty
    assert buffer.get_dirty() == []


def test_writing_marks_only_the_changed_span(buffer):
    buffer.write(1, 2, "abc")
    assert buffer.get_dirty() == [Rect(2, 1, 3, 1)]


def test_rewriting_the_same_text_marks_nothing(buffer):
    buffer.write(1, 2, "abc")
    buffer.clear_dirty()
    buffer.write(1, 2, "abc")
    assert not buffer.is_dirty
    assert buffer.get_dirty() == []


def test_partial_rewrite_marks_only_what_differs(buffer):
    buffer.write(0, 0, "abcdef")
    buffer.clear_dirty()
    buffer.write(0, 0, "abXdef")
    assert buffer.get_dirty() == [Rect(2, 0, 1, 1)]


def test_dirty_spans_widen_across_writes(buffer):
    buffer.write(0, 1, "a")
    buffer.write(0, 7, "b")
    assert buffer.get_dirty() == [Rect(1, 0, 7, 1)]


def test_identical_rows_merge_into_one_region(buffer):
    """A full repaint is one region, not one per row."""
    buffer.fill(Rect(0, 0, 10, 4), "#")
    assert buffer.get_dirty() == [Rect(0, 0, 10, 4)]


def test_differing_rows_stay_separate(buffer):
    buffer.write(0, 0, "ab")
    buffer.write(2, 5, "cd")
    assert buffer.get_dirty() == [Rect(0, 0, 2, 1), Rect(5, 2, 2, 1)]


def test_clear_dirty_resets_cells_and_spans(buffer):
    buffer.write(0, 0, "abc")
    buffer.clear_dirty()
    assert not buffer.is_dirty
    assert buffer.get_dirty() == []
    assert not buffer.cell(0, 0).dirty


# ------------------------------------------------------------------ resize


def test_resize_preserves_what_still_fits():
    buffer = ScreenBuffer(10, 3)
    buffer.write(0, 0, "preserved")
    buffer.resize(6, 2)
    assert buffer.size.width == 6 and buffer.size.height == 2
    assert buffer.text_at(0) == "preser"


def test_growing_adds_blank_cells():
    buffer = ScreenBuffer(4, 1)
    buffer.write(0, 0, "abcd")
    buffer.resize(8, 2)
    assert buffer.lines == ["abcd    ", BLANK * 8]


def test_resize_marks_everything_dirty():
    """Curses discarded the old screen, so all of it must be repainted."""
    buffer = ScreenBuffer(4, 2)
    buffer.clear_dirty()
    buffer.resize(6, 3)
    assert buffer.get_dirty() == [Rect(0, 0, 6, 3)]


def test_resize_to_the_same_size_is_a_no_op():
    buffer = ScreenBuffer(4, 2)
    buffer.clear_dirty()
    buffer.resize(4, 2)
    assert not buffer.is_dirty


def test_resize_rejects_negative_dimensions(buffer):
    with pytest.raises(ValueError, match="negative buffer size"):
        buffer.resize(-1, 2)


def test_zero_width_buffer_is_usable():
    buffer = ScreenBuffer(0, 0)
    assert buffer.lines == []
    assert buffer.write(0, 0, "x") == 0


# -------------------------------------------------------------- properties

sizes = st.integers(min_value=0, max_value=20)


@given(
    width=st.integers(1, 20),
    height=st.integers(1, 5),
    row=st.integers(-5, 25),
    col=st.integers(-25, 25),
    text=st.text(alphabet="abcdef", max_size=30),
)
def test_writes_never_escape_the_buffer(width, height, row, col, text):
    """However a widget miscomputes its position, the buffer stays intact."""
    buffer = ScreenBuffer(width, height)
    buffer.write(row, col, text)
    assert len(buffer.lines) == height
    assert all(len(line) == width for line in buffer.lines)


@given(width=st.integers(1, 20), height=st.integers(1, 5))
def test_dirty_regions_always_lie_inside_the_buffer(width, height):
    buffer = ScreenBuffer(width, height)
    buffer.fill(buffer.bounds, "#")
    for region in buffer.get_dirty():
        assert buffer.bounds.contains(region)


@given(w1=st.integers(0, 15), h1=st.integers(0, 6), w2=sizes, h2=st.integers(0, 6))
def test_resize_always_yields_a_consistent_grid(w1, h1, w2, h2):
    buffer = ScreenBuffer(w1, h1)
    buffer.resize(w2, h2)
    assert len(buffer.lines) == h2
    assert all(len(line) == w2 for line in buffer.lines)


def test_rows_iterates_the_grid():
    buffer = ScreenBuffer(3, 2)
    buffer.write(0, 0, "abc")
    rows = list(buffer.rows())
    assert len(rows) == 2
    assert "".join(cell.char for cell in rows[0]) == "abc"


def test_resize_to_zero_width():
    buffer = ScreenBuffer(4, 2)
    buffer.resize(0, 3)
    assert buffer.lines == ["", "", ""]
    assert not buffer.is_dirty, "no cells means nothing to repaint"


def test_repr_reports_size_and_dirtiness():
    buffer = ScreenBuffer(4, 2)
    assert "4x2" in repr(buffer)
    assert "dirty=False" in repr(buffer)
    buffer.write(0, 0, "x")
    assert "dirty=True" in repr(buffer)
