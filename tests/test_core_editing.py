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


def test_replacing_the_text_drops_the_selection(field):
    field.select_range(0, 3)
    field.text = "new"
    assert field.selection is None


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


def test_a_backwards_selection_is_normalised(field):
    field.select_range(3, 1)
    assert field.selection == (1, 3)


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


def test_inserting_drops_the_selection(field):
    field.select_range(0, 2)
    field.insert(0, "X")
    assert field.selection is None


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


def test_a_negative_index_counts_from_the_end(field):
    assert field.clamp(-1) == 4


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
