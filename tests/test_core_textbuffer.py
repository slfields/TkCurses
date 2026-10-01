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


# ------------------------------------------------------- the cached split


def test_the_lines_follow_an_insert(buffer):
    """The split is kept until the text changes, so every edit has to clear
    it. TkCurses-g9w.
    """
    before = list(buffer.lines)

    buffer.insert(Index(1, 0), "new\n")

    assert buffer.lines != before
    assert buffer.lines[0] == "new"


def test_the_lines_follow_a_delete(buffer):
    buffer.insert(Index(1, 0), "gone\n")
    assert buffer.lines[0] == "gone"

    buffer.delete(Index(1, 0), Index(2, 0))

    assert buffer.lines[0] != "gone"


def test_offset_of_follows_an_edit(buffer):
    """The line starts are built with the split and thrown away with it, so
    an edit that moved a line has to move its offset too."""
    buffer.insert(Index(1, 0), "one\ntwo\n")
    assert buffer.offset_of(Index(2, 0)) == 4

    buffer.insert(Index(1, 0), "zero\n")

    assert buffer.offset_of(Index(2, 0)) == 5
    assert buffer.offset_of(Index(3, 0)) == 9


def test_offset_of_agrees_with_walking_the_lines(buffer):
    """The answer the old implementation gave, which walked every line to
    reach one. Asserted directly because the fast path is a lookup and a
    lookup into the wrong list is silently plausible.
    """
    buffer.insert(Index(1, 0), "alpha\nbeta\ngamma\n")

    for line in range(1, 4):
        walked, start = None, 0
        for number, text in enumerate(buffer.lines, start=1):
            if number == line:
                walked = start + 2
                break
            start += len(text) + 1
        assert buffer.offset_of(Index(line, 2)) == walked


# --------------------------------------------------------------------- undo
#
# The widget's behaviour is asserted in test_text.py against measurements of
# real tkinter. What is checked here is what only the buffer can show: that
# the two edit primitives are the only way in, and that replaying an edit
# does not record itself.


def test_nothing_is_recorded_until_it_is_asked_for():
    buffer = TextBuffer()
    buffer.insert("1.0", "x")
    assert not buffer.can_undo


def test_both_primitives_reach_the_stack():
    """insert() and delete() are the only two ways the text can change.

    If a third ever appears it must record too, and this is what notices:
    the count below is of GROUPS, and each primitive opened its own.
    """
    buffer = TextBuffer()
    buffer.undo_enabled = True
    buffer.insert("1.0", "abc")
    buffer.edit_separator()
    buffer.delete("1.0", "1.1")
    assert buffer.can_undo
    buffer.edit_undo()
    assert buffer.text == "abc\n"
    buffer.edit_undo()
    assert buffer.text == "\n"
    assert not buffer.can_undo


def test_undoing_does_not_record_its_own_reversal():
    """Without suppression the stack never empties.

    Each undo would push the inverse edit it just made, so the next undo
    would put the text straight back and the two would alternate for ever.
    """
    buffer = TextBuffer()
    buffer.undo_enabled = True
    buffer.insert("1.0", "one")
    buffer.edit_undo()
    assert not buffer.can_undo
    assert buffer.can_redo
    buffer.edit_redo()
    assert buffer.can_undo
    assert not buffer.can_redo


def test_a_group_is_reversed_newest_edit_first():
    """The only order that works: earlier offsets describe earlier text."""
    buffer = TextBuffer()
    buffer.undo_enabled = True
    buffer.insert("1.0", "hello")
    buffer.delete("1.0", "1.2")
    buffer.insert("end", "!")
    assert buffer.text == "llo!\n"
    buffer.edit_undo()
    assert buffer.text == "\n"


def test_a_round_trip_leaves_the_text_identical():
    buffer = TextBuffer()
    buffer.undo_enabled = True
    for chunk in ("alpha\n", "beta\n", "gamma"):
        buffer.edit_separator()
        buffer.insert("end", chunk)
    wanted = buffer.text
    for _ in range(3):
        buffer.edit_undo()
    assert buffer.text == "\n"
    for _ in range(3):
        buffer.edit_redo()
    assert buffer.text == wanted


# ------------------------------------------------------- tag inheritance
#
# Tk's rule for text inserted with no tags of its own, from the manual:
# "the new text will receive the tags of the characters both before and
# after the insertion point; if a tag is present on only one of these
# characters then it will not be applied to the new text."
#
# The INTERSECTION, and all five positions below were measured against real
# tkinter before being written down. The last one is the decisive case: it
# rules out "the tags of the character before" and "of the character after"
# alike, because the answer is neither.


def tagged(*steps):
    """Build a buffer from (index, text, tags) steps and read 1.3's tags."""
    buffer = TextBuffer()
    for where, text, tags in steps:
        start = buffer.index(where)
        end = buffer.insert(where, text)
        for tag in tags:
            buffer.tag_add(tag, start, end)
    return tuple(sorted(buffer.tag_names("1.3")))


def test_text_inserted_inside_a_tagged_run_inherits_the_tag():
    """Both sides carry it, so the intersection has it. This is what makes
    typing in the middle of bold text stay bold."""
    assert tagged(("1.0", "aaabbb", "m"), ("1.3", "X", "")) == ("m",)


def test_text_inserted_at_a_tags_leading_edge_does_not_inherit():
    assert tagged(("1.0", "aaa", ""), ("1.3", "bbb", "m"), ("1.3", "X", "")) == ()


def test_text_inserted_at_a_tags_trailing_edge_does_not_inherit():
    """The bug this rule was written for: the tag used to swallow whatever
    was typed after it, so an indented paragraph spread its indent and a
    bold run made the next word bold. TkCurses-lx3."""
    assert tagged(("1.0", "aaa", "m"), ("1.3", "bbb", ""), ("1.3", "X", "")) == ()


def test_text_inserted_between_two_different_tags_inherits_neither():
    assert tagged(("1.0", "aaa", "m"), ("1.3", "bbb", "n"), ("1.3", "X", "")) == ()


def test_only_the_tag_present_on_both_sides_is_inherited():
    """The decisive case, and the reason this is the intersection rather than
    either side: 'm' and 'n' before, 'n' after, and the answer is 'n' alone.
    Measured against tkinter, which agrees."""
    assert tagged(("1.0", "aaa", "mn"), ("1.3", "bbb", "n"), ("1.3", "X", "")) == ("n",)


def test_a_tag_still_grows_when_text_is_added_inside_it():
    """The other half of the same gravity rule, asserted so a fix for the
    edges cannot quietly break the middle."""
    buffer = TextBuffer()
    buffer.insert("1.0", "aaabbb")
    buffer.tag_add("m", "1.0", "1.6")
    buffer.insert("1.3", "XYZ")
    assert [str(i) for i in buffer.tag_ranges("m")] == ["1.0", "1.9"]
