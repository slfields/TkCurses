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

"""Tests for the Text widget's contents: indices, marks and tags."""

from __future__ import annotations

import pytest

from tkcurses._core.textbuffer import Index, TextBuffer, TextIndexError


@pytest.fixture
def buffer():
    return TextBuffer("hello world\nsecond line\nthird")


# ----------------------------------------------------------------- the shape


def test_an_empty_buffer_still_has_a_line():
    """An empty Text has a line 1 for the cursor to sit on."""
    assert TextBuffer().lines == [""]
    assert TextBuffer().line_count() == 1


def test_there_is_always_a_final_newline():
    """Tk's rule, and the reason end is 2.0 rather than 1.3."""
    assert TextBuffer("abc").text == "abc\n"
    assert TextBuffer("abc\n").text == "abc\n"
    assert TextBuffer("abc").end() == Index(2, 0)


def test_get_from_the_start_to_end_includes_that_newline(buffer):
    assert buffer.get("1.0", "end").endswith("third\n")


def test_lines_do_not_include_their_newlines(buffer):
    assert buffer.lines == ["hello world", "second line", "third"]


def test_end_is_past_the_last_line(buffer):
    assert buffer.end() == Index(4, 0)


# --------------------------------------------------------------- index strings


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("1.0", Index(1, 0)),
        ("2.3", Index(2, 3)),
        ("1.end", Index(1, 11)),
        ("3.end", Index(3, 5)),
        ("end", Index(4, 0)),
        ("1.0 lineend", Index(1, 11)),
        ("2.5 linestart", Index(2, 0)),
        ("1.0 +3c", Index(1, 3)),
        ("1.0+3c", Index(1, 3)),
        ("1.0 + 3 chars", Index(1, 3)),
        ("1.3 -2c", Index(1, 1)),
        ("1.0 +1l", Index(2, 0)),
        ("2.4 -1 lines", Index(1, 4)),
        ("1.3 wordstart", Index(1, 0)),
        ("1.3 wordend", Index(1, 5)),
        ("2.0 wordend", Index(2, 6)),
    ],
)
def test_index_strings_resolve(buffer, spec, expected):
    assert buffer.index(spec) == expected


def test_chars_cross_a_line_boundary(buffer):
    """+Nc counts through the newline, which is what makes it different from +Nl."""
    assert buffer.index("1.end +1c") == Index(2, 0)
    assert buffer.index("2.0 -1c") == Index(1, 11)


def test_lines_keep_the_column_where_they_can(buffer):
    assert buffer.index("2.7 +1l") == Index(3, 5)  # third is shorter


def test_modifiers_apply_in_order(buffer):
    assert buffer.index("1.0 +1l lineend") == Index(2, 11)


def test_an_index_past_the_end_is_clamped(buffer):
    assert buffer.index("99.0") == buffer.end()
    assert buffer.index("1.99") == Index(1, 11)
    assert buffer.index("0.0") == Index(1, 0)


def test_a_character_past_the_end_of_a_line_does_not_wrap(buffer):
    """Tk clamps to the line's end, which keeps `insert lineend` meaningful."""
    assert buffer.index(Index(1, 50)) == Index(1, 11)


@pytest.mark.parametrize("spec", ["", "rubbish", "1.x", "1.0 +3 fortnights", "@2,3"])
def test_a_meaningless_index_is_refused(buffer, spec):
    with pytest.raises(TextIndexError):
        buffer.index(spec)


def test_a_word_of_punctuation_is_one_character(buffer):
    """Tk's rule: a run of word characters is a word, anything else is not."""
    buffer.insert("1.0", "a, b")
    assert buffer.index("1.1 wordstart") == Index(1, 1)
    assert buffer.index("1.1 wordend") == Index(1, 2)


# ------------------------------------------------------------------- compare


@pytest.mark.parametrize(
    ("op", "expected"),
    [
        ("<", True),
        ("<=", True),
        ("==", False),
        ("!=", True),
        (">", False),
        (">=", False),
    ],
)
def test_compare(buffer, op, expected):
    assert buffer.compare("1.0", op, "2.0") is expected


def test_an_unknown_operator_is_refused(buffer):
    with pytest.raises(TextIndexError):
        buffer.compare("1.0", "<>", "2.0")


# ------------------------------------------------------------------ contents


def test_get_a_range(buffer):
    assert buffer.get("1.0", "1.5") == "hello"


def test_get_one_character(buffer):
    assert buffer.get("1.1") == "e"


def test_a_backwards_range_is_taken_the_right_way_round(buffer):
    """A selection dragged upwards produces exactly that."""
    assert buffer.get("1.5", "1.0") == "hello"


def test_insert_returns_the_far_end(buffer):
    assert buffer.insert("1.0", "abc") == Index(1, 3)


def test_insert_can_add_lines(buffer):
    buffer.insert("1.0", "one\ntwo\n")
    assert buffer.lines[:3] == ["one", "two", "hello world"]


def test_insert_at_end_goes_before_the_final_newline(buffer):
    buffer.insert("end", "!")
    assert buffer.text.endswith("third!\n")
    assert buffer.line_count() == 3


def test_delete_a_range(buffer):
    buffer.delete("1.0", "1.6")
    assert buffer.lines[0] == "world"


def test_delete_one_character(buffer):
    buffer.delete("1.0")
    assert buffer.lines[0] == "ello world"


def test_delete_can_join_lines(buffer):
    buffer.delete("1.end", "2.0")
    assert buffer.lines[0] == "hello worldsecond line"


def test_the_final_newline_cannot_be_deleted(buffer):
    buffer.delete("1.0", "end")
    assert buffer.text == "\n"
    assert buffer.lines == [""]


def test_deleting_nothing_is_harmless(buffer):
    buffer.delete("1.3", "1.3")
    assert buffer.lines[0] == "hello world"


# --------------------------------------------------------------------- marks


def test_a_mark_survives_an_edit_elsewhere(buffer):
    buffer.mark_set("insert", "2.3")
    buffer.insert("1.0", "XX")
    assert buffer.mark_index("insert") == Index(2, 3)


def test_a_mark_moves_with_text_inserted_before_it(buffer):
    buffer.mark_set("insert", "1.5")
    buffer.insert("1.0", "XX")
    assert buffer.mark_index("insert") == Index(1, 7)


def test_right_gravity_puts_a_mark_after_text_inserted_at_it(buffer):
    """Which is what makes typing push the insert cursor along."""
    buffer.mark_set("insert", "1.5")
    buffer.insert("1.5", "XX")
    assert buffer.mark_index("insert") == Index(1, 7)


def test_left_gravity_leaves_it_before(buffer):
    buffer.mark_set("here", "1.5")
    buffer.mark_gravity("here", "left")
    buffer.insert("1.5", "XX")
    assert buffer.mark_index("here") == Index(1, 5)


def test_a_mark_inside_deleted_text_collapses_to_the_start(buffer):
    buffer.mark_set("insert", "1.8")
    buffer.delete("1.2", "1.10")
    assert buffer.mark_index("insert") == Index(1, 2)


def test_marks_can_be_removed(buffer):
    buffer.mark_set("here", "1.0")
    buffer.mark_unset("here")
    assert "here" not in buffer.mark_names()
    assert buffer.mark_index("here") is None


def test_unsetting_an_unknown_mark_is_harmless(buffer):
    buffer.mark_unset("nothing")


def test_gravity_of_an_unknown_mark_is_refused(buffer):
    with pytest.raises(TextIndexError, match="no mark named"):
        buffer.mark_gravity("nothing")


def test_a_bad_gravity_is_refused(buffer):
    buffer.mark_set("here", "1.0")
    with pytest.raises(TextIndexError, match="bad mark gravity"):
        buffer.mark_gravity("here", "sideways")


def test_a_mark_can_be_used_as_an_index(buffer):
    buffer.mark_set("insert", "2.3")
    assert buffer.index("insert +2c") == Index(2, 5)


def test_next_and_previous_marks(buffer):
    buffer.mark_set("a", "1.0")
    buffer.mark_set("b", "2.0")
    assert buffer.mark_next("1.0") == "b"
    assert buffer.mark_previous("2.0") == "a"
    assert buffer.mark_next("end") is None
    assert buffer.mark_previous("1.0") is None


# ---------------------------------------------------------------------- tags


def test_a_tag_covers_a_range(buffer):
    buffer.tag_add("bold", "1.0", "1.5")
    assert buffer.tag_ranges("bold") == [Index(1, 0), Index(1, 5)]
    assert buffer.tag_names("1.2") == ("bold",)
    assert buffer.tag_names("1.7") == ()


def test_the_end_of_a_range_is_not_covered(buffer):
    """Ranges are half-open, as everywhere else here."""
    buffer.tag_add("bold", "1.0", "1.5")
    assert "bold" not in buffer.tag_names("1.5")


def test_adjacent_ranges_merge(buffer):
    buffer.tag_add("bold", "1.0", "1.5")
    buffer.tag_add("bold", "1.5", "1.8")
    assert buffer.tag_ranges("bold") == [Index(1, 0), Index(1, 8)]


def test_overlapping_ranges_merge(buffer):
    buffer.tag_add("bold", "1.0", "1.5")
    buffer.tag_add("bold", "1.3", "1.8")
    assert buffer.tag_ranges("bold") == [Index(1, 0), Index(1, 8)]


def test_separate_ranges_stay_separate(buffer):
    buffer.tag_add("bold", "1.0", "1.2")
    buffer.tag_add("bold", "1.6", "1.8")
    assert len(buffer.tag_ranges("bold")) == 4


def test_removing_the_middle_splits_a_range(buffer):
    buffer.tag_add("bold", "1.0", "1.10")
    buffer.tag_remove("bold", "1.3", "1.6")
    assert buffer.tag_ranges("bold") == [
        Index(1, 0),
        Index(1, 3),
        Index(1, 6),
        Index(1, 10),
    ]


def test_removing_an_untagged_range_is_harmless(buffer):
    buffer.tag_remove("bold", "1.0", "1.5")
    assert buffer.tag_ranges("bold") == []


def test_a_tag_follows_an_edit_before_it(buffer):
    buffer.tag_add("bold", "1.6", "1.11")
    buffer.insert("1.0", "XX")
    assert buffer.tag_ranges("bold") == [Index(1, 8), Index(1, 13)]


def test_deleting_a_tagged_range_removes_it(buffer):
    buffer.tag_add("bold", "1.0", "1.5")
    buffer.delete("1.0", "1.5")
    assert buffer.tag_ranges("bold") == []


def test_deleting_part_of_a_tagged_range_shortens_it(buffer):
    buffer.tag_add("bold", "1.0", "1.10")
    buffer.delete("1.2", "1.5")
    assert buffer.tag_ranges("bold") == [Index(1, 0), Index(1, 7)]


def test_tag_delete_forgets_it_entirely(buffer):
    buffer.tag_add("bold", "1.0", "1.5")
    buffer.tag_delete("bold")
    assert "bold" not in buffer.tag_names()
    assert buffer.tag_ranges("bold") == []


def test_tag_first_and_last_are_indices(buffer):
    buffer.tag_add("sel", "1.2", "1.5")
    buffer.tag_add("sel", "2.0", "2.3")
    assert buffer.index("sel.first") == Index(1, 2)
    assert buffer.index("sel.last") == Index(2, 3)


def test_tag_first_on_an_empty_tag_is_refused(buffer):
    buffer.tag_add("sel", "1.0", "1.0")
    with pytest.raises(TextIndexError):
        buffer.index("sel.first")


def test_tag_nextrange_and_prevrange(buffer):
    buffer.tag_add("bold", "1.0", "1.3")
    buffer.tag_add("bold", "2.0", "2.4")
    assert buffer.tag_nextrange("bold", "1.3") == (Index(2, 0), Index(2, 4))
    assert buffer.tag_prevrange("bold", "2.0") == (Index(1, 0), Index(1, 3))
    assert buffer.tag_nextrange("bold", "end") is None
    assert buffer.tag_prevrange("bold", "1.0") is None
