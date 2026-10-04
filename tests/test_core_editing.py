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

"""Tests for tkcurses._core.editing."""

from __future__ import annotations

import pytest

from tkcurses._core.editing import TextField


@pytest.fixture
def field():
    return TextField("hello")


# ------------------------------------------------------------------- basics


def test_a_new_field_puts_the_cursor_at_the_end():
    assert TextField("abc").cursor == 3


def test_an_empty_field_starts_empty():
    field = TextField()
    assert field.text == ""
    assert field.cursor == 0


def test_replacing_the_text_keeps_the_cursor_in_range(field):
    field.move_to(5)
    field.text = "ab"
    assert field.cursor == 2


def test_replacing_the_text_clamps_the_selection(field):
    """Measured on Tk 9.0.2: 1-4 over "hello" reads 1-2 once the text is "ab".
    This dropped the selection until TkCurses-elb."""
    field.select_range(1, 4)
    field.text = "ab"
    assert field.selection == (1, 2)


def test_replacing_the_text_keeps_a_selection_that_still_fits(field):
    field.select_range(0, 3)
    field.text = "new"
    assert field.selection == (0, 3)


def test_replacing_the_text_drops_a_selection_past_the_new_end(field):
    """Measured: 3-5 over "hello" is gone after "ab", not an empty 2-2."""
    field.select_range(3, 5)
    field.text = "ab"
    assert field.selection is None


def test_placing_the_cursor_keeps_the_selection(field):
    """Tk's icursor, measured: 1-3 survives icursor(0). TkCurses-elb."""
    field.select_range(1, 3)
    field.place_cursor(0)
    assert field.cursor == 0
    assert field.selection == (1, 3)


def test_placing_the_cursor_is_clamped(field):
    field.place_cursor(99)
    assert field.cursor == 5


# ----------------------------------------------------------------- inserting


def test_inserting_at_the_cursor(field):
    field.insert(5, "!")
    assert field.text == "hello!"


def test_inserting_in_the_middle(field):
    field.insert(2, "XX")
    assert field.text == "heXXllo"


def test_the_cursor_follows_text_inserted_before_it(field):
    """Otherwise typing at the start leaves the cursor behind what was typed."""
    field.move_to(0)
    field.insert(0, "abc")
    assert field.cursor == 3


def test_the_cursor_stays_put_when_text_is_inserted_after_it(field):
    field.move_to(1)
    field.insert(4, "XX")
    assert field.cursor == 1


def test_inserting_past_the_end_appends(field):
    field.insert(99, "!")
    assert field.text == "hello!"


# ------------------------------------------------------------------ deleting


def test_deleting_one_character(field):
    field.delete(0)
    assert field.text == "ello"


def test_deleting_a_range(field):
    field.delete(1, 3)
    assert field.text == "hlo"


def test_a_backwards_range_is_taken_the_right_way_round(field):
    """A selection dragged leftwards produces exactly this."""
    field.delete(3, 1)
    assert field.text == "hlo"


def test_deleting_an_empty_range_changes_nothing(field):
    field.delete(2, 2)
    assert field.text == "hello"


def test_the_cursor_moves_back_with_text_deleted_before_it(field):
    field.move_to(5)
    field.delete(0, 2)
    assert field.cursor == 3


def test_a_cursor_inside_deleted_text_lands_at_the_start(field):
    field.move_to(3)
    field.delete(1, 4)
    assert field.cursor == 1


def test_deleting_past_the_end_is_clamped(field):
    field.delete(3, 99)
    assert field.text == "hel"


# ---------------------------------------------------------------- selection


def test_there_is_no_selection_to_begin_with(field):
    assert field.selection is None
    assert field.selected_text() == ""


def test_selecting_a_range(field):
    field.select_range(1, 3)
    assert field.selection == (1, 3)
    assert field.selected_text() == "el"


def test_a_backwards_range_clears_the_selection(field):
    """Tk 9.0.2: selection range 6 2 leaves nothing selected. TkCurses-bfy."""
    field.select_range(1, 3)
    field.select_range(3, 1)
    assert field.selection is None


# ------------------------------------------------------------------ the anchor
#
# Tk's entry selection commands, measured on 9.0.2 with "abcdefghij" and the
# cursor at 5 - which none of them moves. TkCurses-bfy.


def ten():
    field = TextField("abcdefghij")
    field.place_cursor(5)
    return field


def test_the_anchor_starts_at_zero():
    field = ten()
    field.select_to(3)
    assert (field.selection, field.cursor) == ((0, 3), 5)


def test_select_from_sets_only_the_anchor():
    field = ten()
    field.select_range(2, 6)
    field.select_from(3)
    assert (field.selection, field.cursor) == ((2, 6), 5)
    field.select_to(8)
    assert field.selection == (3, 8)


def test_select_range_leaves_the_anchor():
    field = ten()
    field.select_range(2, 6)
    field.select_to(8)
    assert field.selection == (0, 8)


def test_clearing_keeps_the_anchor():
    field = ten()
    field.select_from(4)
    field.select_to(7)
    field.select_clear()
    field.select_to(1)
    assert field.selection == (1, 4)


def test_selecting_onto_the_anchor_selects_nothing():
    """Tk reports an empty selection as present here; deliberately not copied."""
    field = ten()
    field.select_from(4)
    field.select_to(7)
    field.select_to(4)
    assert field.selection is None


@pytest.mark.parametrize(
    ("index", "selected", "then_to", "after"),
    [
        (8, (2, 8), 1, (1, 2)),  # past the end: the start becomes the anchor
        (1, (1, 6), 8, (6, 8)),  # before the start: the end does
        (3, (3, 6), 8, (6, 8)),  # nearer the start
        (5, (2, 5), 1, (1, 2)),  # nearer the end
        (4, (0, 4), 8, (0, 8)),  # the exact middle keeps the old anchor, 0
    ],
)
def test_adjust_moves_the_nearer_end(index, selected, then_to, after):
    field = ten()
    field.select_range(2, 6)
    field.select_adjust(index)
    assert (field.selection, field.cursor) == (selected, 5)
    field.select_to(then_to)
    assert field.selection == after


def test_adjust_with_nothing_selected_is_select_to():
    field = ten()
    field.select_from(3)
    field.select_adjust(7)
    assert field.selection == (3, 7)


def test_a_plain_arrow_keeps_the_anchor():
    """Tk: from 2, to 6, Left - then selection to 8 reads 2-8."""
    field = ten()
    field.select_from(2)
    field.select_to(6)
    field.move_by(-1)
    assert field.selection is None
    field.select_to(8)
    assert field.selection == (2, 8)


def test_shift_arrow_adjusts_a_selection_it_did_not_make():
    """Tk: range 2-4, cursor at 5, Shift-Right reads 2-6 with the cursor at 6."""
    field = ten()
    field.select_range(2, 4)
    field.move_by(1, extend=True)
    assert (field.selection, field.cursor) == ((2, 6), 6)


@pytest.mark.parametrize(
    ("moves", "expected"),
    [
        ([1, 1], (5, 7)),
        ([1, 1, -1], (5, 6)),
        ([1, 1, -1, -1], None),
        ([1, 1, -1, -1, -1], (4, 5)),  # through the anchor: starts afresh
        ([-1, -1, 1], (4, 5)),
    ],
)
def test_shift_arrows_grow_and_shrink_from_the_cursor(moves, expected):
    """Measured in Tk with Shift-Left/Right from the cursor at 5. Tk reports the
    third row as an empty selection 5-5 that is present; that is not copied."""
    field = ten()
    for move in moves:
        field.move_by(move, extend=True)
    assert field.selection == expected


def test_new_text_leaves_the_anchor_where_it_was():
    """Tk: from 6, the variable set to 'abc', six characters inserted at 3,
    then selection to 0 reads 0-9 - the anchor stayed at 6 and moved to 12."""
    field = ten()
    field.select_from(6)
    field.text = "abc"
    field.insert(3, "XYZWVU")
    field.select_to(0)
    assert field.selection == (0, 9)


def test_an_empty_selection_is_no_selection(field):
    field.select_range(2, 2)
    assert field.selection is None


def test_select_all_takes_everything(field):
    field.select_all()
    assert field.selected_text() == "hello"
    assert field.cursor == 5


def test_clearing_leaves_the_cursor_alone(field):
    field.move_to(2)
    field.select_range(0, 4)
    field.select_clear()
    assert field.selection is None
    assert field.cursor == 2


def test_deleting_the_selection_removes_it(field):
    field.select_range(1, 3)
    assert field.delete_selection() is True
    assert field.text == "hlo"


def test_deleting_no_selection_reports_nothing_done(field):
    assert field.delete_selection() is False
    assert field.text == "hello"


# Insert and delete carry the selection with the text. Measured on Tk 9.0.2,
# tk.Entry holding "abcdefgh" with 2-5 ("cde") selected. Until TkCurses-61v any
# insert or delete dropped the selection outright.


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        (0, (4, 7)),  # before it: both ends move
        (1, (4, 7)),
        (2, (4, 7)),  # exactly at its start: lands outside it
        (3, (2, 7)),  # inside it: it grows
        (4, (2, 7)),
        (5, (2, 5)),  # exactly at its end: lands outside it
        (6, (2, 5)),  # after it: untouched
        (8, (2, 5)),
    ],
)
def test_inserting_carries_the_selection_with_the_text(index, expected):
    field = TextField("abcdefgh")
    field.select_range(2, 5)
    field.insert(index, "XY")
    assert field.selection == expected


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [
        (0, 1, (1, 4)),
        (0, 2, (0, 3)),
        (1, 3, (1, 3)),  # overlapping its start: its start goes to the cut
        (2, 3, (2, 4)),
        (3, 4, (2, 4)),  # inside it: it shrinks
        (2, 4, (2, 3)),
        (4, 5, (2, 4)),
        (4, 6, (2, 4)),  # overlapping its end
        (5, 7, (2, 5)),  # after it: untouched
        (6, 8, (2, 5)),
        (2, 5, None),  # all of it: gone
        (1, 6, None),
        (0, 8, None),
    ],
)
def test_deleting_carries_the_selection_with_the_text(first, last, expected):
    field = TextField("abcdefgh")
    field.select_range(2, 5)
    field.delete(first, last)
    assert field.selection == expected


@pytest.mark.parametrize(
    ("anchor", "other", "edit", "moved_to"),
    [
        # Tk: selection_from(anchor), selection_to(other), the edit, then a
        # selection_to(n) whose result - in the comment - shows the anchor.
        (2, 5, ("insert", 0), 4),  # to(7) -> 4-7
        (2, 5, ("insert", 2), 4),  # on the point, selection starts there: moves
        (5, 2, ("insert", 5), 5),  # on the point, selection does not: stays
        (2, 5, ("insert", 5), 2),  # to(0) -> 0-2
        (2, 5, ("insert", 3), 2),  # to(7) -> 2-7
        (5, 2, ("insert", 0), 7),  # to(1) -> 1-7
        (2, 5, ("delete", 0, 1), 1),  # to(7) -> 1-7
        (2, 5, ("delete", 1, 3), 1),  # to(7) -> 1-6
        (2, 5, ("delete", 2, 5), 2),  # selection gone, anchor kept; to(4) -> 2-4
        (5, 2, ("delete", 3, 7), 3),  # to(0) -> 0-3
    ],
)
def test_the_anchor_moves_with_the_text(anchor, other, edit, moved_to):
    field = TextField("abcdefgh")
    field.move_to(anchor)
    field.move_to(other, extend=True)
    if edit[0] == "insert":
        field.insert(edit[1], "XY")
    else:
        field.delete(edit[1], edit[2])
    assert field._anchor == moved_to


def test_shift_arrow_after_typing_over_a_selection_starts_afresh():
    """Tk: select 2-5 of abcdefgh, type X, Shift-Right selects only the f."""
    field = TextField("abcdefgh")
    field.select_range(2, 5)
    field.place_cursor(5)
    field.delete_selection()
    field.insert(field.cursor, "X")
    field.move_by(1, extend=True)
    assert field.selection == (3, 4)


# ------------------------------------------------------------- moving about


def test_moving_drops_the_selection(field):
    field.select_range(0, 3)
    field.move_to(1)
    assert field.selection is None


def test_extending_grows_the_selection_from_the_anchor(field):
    field.move_to(1)
    field.move_by(2, extend=True)
    assert field.selection == (1, 3)


def test_extending_backwards_over_the_anchor(field):
    field.move_to(3)
    field.move_by(-2, extend=True)
    assert field.selection == (1, 3)


def test_extending_keeps_the_same_anchor_across_moves(field):
    field.move_to(1)
    field.move_by(3, extend=True)
    field.move_by(-1, extend=True)
    assert field.selection == (1, 3)


def test_moving_is_clamped_to_the_text(field):
    field.move_to(99)
    assert field.cursor == 5
    field.move_to(-99)
    assert field.cursor == 0


@pytest.mark.parametrize("index", [-1, -3, -99])
def test_a_negative_index_is_the_start(field, index):
    """Tk 9.0.2: index(-1), index(-3) and index(-99) all answer 0. This counted
    from the end, Python-style, until TkCurses-11m."""
    assert field.clamp(index) == 0


def test_left_at_the_start_stays_there(field):
    """It jumped to the far end: move_by(-1) from 0 asked for index -1."""
    field.place_cursor(0)
    field.move_by(-1)
    assert field.cursor == 0
    field.move_by(-1, extend=True)
    assert (field.cursor, field.selection) == (0, None)


# --------------------------------------------------------------------- view


def test_a_short_field_shows_everything(field):
    assert field.visible(10) == "hello"


def test_a_narrow_field_shows_what_fits(field):
    assert field.visible(3) == "hel"


def test_a_zero_width_field_shows_nothing(field):
    assert field.visible(0) == ""


def test_the_view_follows_the_cursor_to_the_right():
    """The cursor sits after the last character and needs a cell of its own.

    So a four-wide field with the cursor at the end shows three characters
    and keeps the fourth column for the cursor.
    """
    field = TextField("abcdefghij")
    field.move_to(10)
    field.scroll_into_view(4)
    assert field.visible(4) == "hij"


def test_the_view_follows_the_cursor_back_to_the_left():
    field = TextField("abcdefghij")
    field.move_to(10)
    field.scroll_into_view(4)
    field.move_to(0)
    field.scroll_into_view(4)
    assert field.visible(4) == "abcd"


def test_the_view_only_moves_as_far_as_it_must():
    """A cursor in the middle must not recentre the text every keystroke."""
    field = TextField("abcdefghij")
    field.move_to(10)
    field.scroll_into_view(4)
    field.move_by(-1)
    field.scroll_into_view(4)
    assert field.visible(4) == "hij"


def test_deleting_pulls_the_view_back_into_the_text():
    field = TextField("abcdefghij")
    field.move_to(10)
    field.scroll_into_view(4)
    field.delete(0, 10)
    assert field.view == 0


# How edits and xview move the view, measured on Tk 9.0.2: an entry 5 wide
# holding a-z with its view at 10. TkCurses-i8s.


def scrolled(view=10):
    field = TextField("abcdefghijklmnopqrstuvwxyz")
    field.set_view(view, 5)
    return field


@pytest.mark.parametrize(
    ("edit", "view"),
    [
        (("insert", 9), 12),  # before the view: it moves, the same text stays shown
        (("insert", 10), 10),  # exactly at it: it stays
        (("insert", 26), 10),
        (("delete", 5, 10), 5),
        (("delete", 8, 12), 8),  # across it: it goes to the cut
        (("delete", 10, 12), 10),
        (("delete", 20, 26), 10),
    ],
)
def test_edits_move_the_view_with_the_text(edit, view):
    field = scrolled()
    if edit[0] == "insert":
        field.insert(edit[1], "XY")
    else:
        field.delete(edit[1], edit[2])
    assert field.view == view


def test_editing_does_not_bring_the_cursor_into_view():
    """Tk's insert and icursor leave the view alone; only its bindings scroll."""
    field = scrolled()
    field.place_cursor(0)
    field.insert(26, "XYZ")
    assert field.view == 10


@pytest.mark.parametrize(
    ("index", "view"), [(0, 0), (10, 10), (21, 21), (22, 21), (99, 21), (-3, 0)]
)
def test_setting_the_view_stops_at_the_last_full_field(index, view):
    field = scrolled()
    field.set_view(index, 5)
    assert field.view == view


def test_setting_the_view_leaves_the_cursor_and_the_selection():
    field = scrolled(0)
    field.place_cursor(3)
    field.select_range(1, 4)
    field.set_view(10, 5)
    assert (field.cursor, field.selection) == (3, (1, 4))


def test_a_text_shorter_than_the_field_never_scrolls():
    field = TextField("abc")
    field.set_view(2, 5)
    assert field.view == 0


def test_a_shrunken_text_pulls_the_view_back_to_fill_the_field():
    """Tk: view 10, delete(12, end) leaves 12 characters, shown from 7."""
    field = scrolled()
    field.place_cursor(0)
    field.delete(12, 26)
    field.fit_view(5)
    assert field.view == 7


def test_a_cursor_at_the_end_keeps_its_cell():
    """Our cursor occupies a cell, so it may hold the view one past Tk's limit."""
    field = TextField("abcdefghij")
    field.move_to(10)
    field.scroll_into_view(4)
    field.fit_view(4)
    assert field.visible(4) == "hij"


def test_a_column_maps_to_an_index():
    field = TextField("abcdefghij")
    field.move_to(10)
    field.scroll_into_view(4)
    assert field.index_at(0) == 7
    assert field.index_at(2) == 9


def test_an_index_maps_to_a_column():
    field = TextField("abcdefghij")
    field.move_to(10)
    field.scroll_into_view(4)
    assert field.column_of(7) == 0


def test_a_click_past_the_end_lands_at_the_end(field):
    assert field.index_at(99) == 5
