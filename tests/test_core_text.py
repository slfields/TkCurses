"""Tests for tkcurses._core.text."""

from __future__ import annotations

import pytest

from tkcurses._core.text import align_offset, measure, wrap, wrap_spans

# ------------------------------------------------------------------ wrapping


def test_text_without_a_width_is_not_wrapped():
    assert wrap("a line that goes on and on", 0) == ["a line that goes on and on"]


def test_a_negative_width_is_treated_as_no_wrapping():
    assert wrap("some text", -5) == ["some text"]


def test_text_is_broken_at_word_boundaries():
    assert wrap("one two three four", 9) == ["one two", "three", "four"]


def test_a_line_exactly_the_width_is_not_broken():
    assert wrap("abcde fghij", 5) == ["abcde", "fghij"]


def test_explicit_newlines_always_break():
    assert wrap("first\nsecond", 0) == ["first", "second"]


def test_newlines_survive_wrapping():
    assert wrap("one two\nthree", 3) == ["one", "two", "thr", "ee"]


def test_a_word_longer_than_the_line_is_split():
    """Refusing to break would put characters on top of a neighbour."""
    assert wrap("antidisestablishment", 6) == ["antidi", "sestab", "lishme", "nt"]


def test_a_long_word_after_a_short_one_starts_its_own_line():
    assert wrap("hi antidisestablishment", 6) == [
        "hi",
        "antidi",
        "sestab",
        "lishme",
        "nt",
    ]


def test_empty_text_is_one_empty_line():
    """A label holding nothing still occupies a row."""
    assert wrap("", 0) == [""]
    assert wrap("", 10) == [""]


def test_trailing_newline_leaves_a_blank_line():
    assert wrap("text\n", 0) == ["text", ""]


# ----------------------------------------------------------------- measuring


def test_measuring_reports_the_longest_line_and_the_count():
    assert measure(["ab", "abcd", "a"]) == (4, 3)


def test_measuring_nothing_is_zero_by_zero():
    assert measure([]) == (0, 0)


def test_measuring_one_empty_line_is_zero_by_one():
    assert measure([""]) == (0, 1)


# ----------------------------------------------------------------- alignment


@pytest.mark.parametrize(
    ("justify", "offset"), [("left", 0), ("center", 3), ("right", 6)]
)
def test_alignment_places_a_short_line(justify, offset):
    assert align_offset(4, 10, justify) == offset


def test_alignment_is_case_insensitive():
    assert align_offset(4, 10, "CENTER") == 3


def test_a_line_wider_than_the_space_starts_at_the_left():
    """Never negative: it is clipped by the drawer, not pushed off screen."""
    assert align_offset(20, 10, "center") == 0
    assert align_offset(20, 10, "right") == 0


def test_an_unknown_justification_is_refused():
    with pytest.raises(ValueError, match="justify"):
        align_offset(4, 10, "sideways")


# ------------------------------------------------------------- wrap_spans


def test_spans_cover_the_whole_line():
    line = "the quick brown fox jumps"
    spans = wrap_spans(line, 10, "char")
    assert "".join(line[a:b] for a, b in spans) == line


def test_no_wrapping_is_one_span():
    assert wrap_spans("anything at all", 5, "none") == [(0, 15)]


def test_a_width_of_zero_does_not_wrap():
    assert wrap_spans("anything at all", 0, "char") == [(0, 15)]


def test_char_wrapping_breaks_at_the_width():
    assert wrap_spans("abcdefgh", 3, "char") == [(0, 3), (3, 6), (6, 8)]


def test_word_wrapping_breaks_at_a_space():
    line = "the quick brown"
    spans = wrap_spans(line, 10, "word")
    assert [line[a:b] for a, b in spans] == ["the quick ", "brown"]


def test_word_wrapping_keeps_the_space_on_the_line_it_broke():
    """Otherwise every wrapped line after the first starts with a space."""
    line = "aaa bbb ccc"
    assert all(
        not line[a:b].startswith(" ") or a == 0 for a, b in wrap_spans(line, 4, "word")
    )


def test_a_word_too_long_to_fit_is_broken():
    line = "antidisestablishmentarianism"
    spans = wrap_spans(line, 10, "word")
    assert all(b - a <= 10 for a, b in spans)
    assert "".join(line[a:b] for a, b in spans) == line


def test_an_empty_line_is_one_empty_span():
    assert wrap_spans("", 10, "char") == [(0, 0)]


def test_spans_are_contiguous_and_ordered():
    spans = wrap_spans("one two three four five", 7, "word")
    assert spans[0][0] == 0
    assert all(spans[i][1] == spans[i + 1][0] for i in range(len(spans) - 1))
