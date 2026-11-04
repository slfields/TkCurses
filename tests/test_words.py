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


"""Word boundaries, held to what Tk 9.0.2 answers. TkCurses-wmaq."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tkcurses._core.words import end_of_word, start_of_next_word, start_of_previous_word

DATA = json.loads(
    (Path(__file__).parent / "support" / "word_boundaries.json").read_text("utf-8")
)
PROCEDURES = {
    "endOfWord": end_of_word,
    "startOfNextWord": start_of_next_word,
    "startOfPreviousWord": start_of_previous_word,
}


@pytest.mark.parametrize("case", DATA["cases"], ids=lambda case: repr(case["s"]))
@pytest.mark.parametrize("name", PROCEDURES)
def test_each_index_answers_as_tk_does(case, name):
    text = case["s"]
    assert [PROCEDURES[name](text, i) for i in range(len(text) + 1)] == case[name]


def test_a_space_beside_a_newline_is_two_stops():
    """None of the three loops: from the end of ``abc``, the next word
    starts at the newline, not at ``def``."""
    assert start_of_next_word("abc  \n  def", 0) == 5


def test_the_end_of_the_string_is_no_answer():
    assert end_of_word("hello", 0) is None
    assert start_of_next_word("hello", 0) is None
