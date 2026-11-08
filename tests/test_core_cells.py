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

"""Tests for tkcurses._core.cells: how many cells text takes on a terminal."""

from __future__ import annotations

import pytest

from tkcurses._core.cells import cells, char_cells, clip_cells, skip_cells

WIDE = "\u65e5"  # a CJK ideograph
EMOJI = "\U0001f600"
ACUTE = "\u0301"  # combining acute accent

SAMPLES = [
    ("A", 1),
    ("\u00e9", 1),
    (WIDE, 2),
    ("\uff21", 2),  # fullwidth A
    ("\u3000", 2),  # ideographic space
    (EMOJI, 2),
    ("\U0001f1e6", 2),  # a regional indicator, half a flag
    ("\u1100", 2),  # a Hangul leading jamo
    (ACUTE, 0),
    ("\u20dd", 0),  # an enclosing circle
    ("\u0903", 0),  # a Devanagari spacing mark
    ("\u200b", 0),  # zero width space
    ("\u200d", 0),  # zero width joiner
    ("\u1161", 0),  # a Hangul medial jamo, joining the syllable before
    ("\u00ad", 1),  # the soft hyphen is drawn
    ("\u0600", 1),  # a prepended concatenation mark is drawn
    ("\u0e33", 1),  # Thai sara am
]


@pytest.mark.parametrize(("character", "width"), SAMPLES)
def test_a_character_takes_the_cells_a_terminal_gives_it(character, width):
    assert char_cells(character) == width


@pytest.mark.parametrize(("character", "width"), SAMPLES)
def test_the_widths_agree_with_wcwidth(character, width):
    """What pyte, and so the test harness's terminal, measures with."""
    wcwidth = pytest.importorskip("wcwidth")
    assert wcwidth.wcwidth(character) == width


def test_a_text_is_the_sum_of_its_characters():
    assert cells("A" + WIDE + "B") == 4
    assert cells("x" + EMOJI + "y") == 4
    assert cells("e" + ACUTE + "z") == 2
    assert cells("plain") == 5
    assert cells("") == 0


def test_clipping_never_cuts_a_wide_character_in_half():
    text = "A" + WIDE * 3 + "B"
    assert clip_cells(text, 4) == "A" + WIDE
    assert clip_cells(text, 5) == "A" + WIDE * 2
    assert clip_cells(text, 8) == text
    assert clip_cells(text, 0) == ""


def test_clipping_keeps_a_mark_with_its_letter():
    assert clip_cells("e" + ACUTE + "z", 1) == "e" + ACUTE


def test_skipping_into_a_wide_character_leaves_a_blank_for_its_half():
    text = "A" + WIDE * 3 + "B"
    assert skip_cells(text, 1) == (WIDE * 3 + "B", 0)
    assert skip_cells(text, 2) == (WIDE * 2 + "B", 1)
    assert skip_cells(text, 3) == (WIDE * 2 + "B", 0)
    assert skip_cells(text, 0) == (text, 0)
    assert skip_cells("abc", 5) == ("", 0)


def test_skipping_takes_a_letters_marks_with_it():
    assert skip_cells("e" + ACUTE + "z", 1) == ("z", 0)
