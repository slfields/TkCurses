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

"""One character, one cell - the assumption every column calculation makes.

Clipping to a window, the insert cursor, ``bbox``, mapping a click back to an
index: all of them count characters and mean cells. A control character
breaks that at the only point where nothing can check it, because curses
draws it however the terminal likes and the arithmetic has already happened.

Measured before ``_one_cell_each`` existed: a Text holding ``"\tAB"`` drew A
at column 10 while reporting it at column 4; a Label holding ``"A\tB"`` lost
the B; an Entry holding ``"C\tD"`` pushed the D seven columns into a
twenty-column box. Every widget, because they all write through
``_write_line``.
"""

from __future__ import annotations

from tkcurses import _one_cell_each
from tkcurses._core.cells import cells, char_cells


def test_printable_text_is_left_exactly_alone():
    """The common case, and it must not cost anything or change anything."""
    assert _one_cell_each("hello world") == "hello world"
    assert _one_cell_each("") == ""
    assert _one_cell_each("┌──┐") == "┌──┐"


def test_a_tab_becomes_one_space():
    """A tab IS whitespace; it simply does not reach a tab stop yet."""
    assert _one_cell_each("\tAB") == " AB"
    assert _one_cell_each("a\tb\tc") == "a b c"


def test_other_control_characters_become_a_visible_mark():
    """Visible on purpose: one of these in a widget is a bug somewhere, and
    drawing nothing would hide it."""
    assert _one_cell_each("a\x00b") == "a?b"
    assert _one_cell_each("a\x1bb") == "a?b"
    assert _one_cell_each("a\x7fb") == "a?b"


def test_a_no_break_space_and_a_soft_hyphen_are_drawn_as_they_look():
    """Typed on purpose, and one cell wide, so not marked as a fault."""
    assert _one_cell_each("a\u00a0b") == "a b"
    assert _one_cell_each("a\u00adb") == "a-b"


def test_a_zero_width_format_character_is_drawn_as_nothing():
    """Measured as no cells, so drawn as none: a ``?`` put an Entry's cursor
    a column short of the end of the text. And not given to the terminal,
    where a joiner would join what is measured apart and a direction
    override would reorder the row."""
    assert _one_cell_each("a\u200bb") == "ab"
    assert _one_cell_each("\U0001f468\u200d\U0001f469") == "\U0001f468\U0001f469"
    assert _one_cell_each("a\u202eb\ufeffc") == "abc"


def test_every_space_is_drawn_as_spaces_as_wide_as_it_is():
    assert _one_cell_each("a\u2003b") == "a b"
    assert _one_cell_each("a\u3000b") == "a  b"


def test_the_width_never_changes():
    """What the clipping, the cursor and a click depend on: each measures a
    character by char_cells, so what is drawn must take exactly that many
    cells, or everything after it is drawn where it is not measured."""
    for text in (
        "\tAB",
        "a\x00b",
        "plain",
        "\t\t\t",
        "a\x1b\x7f\tz",
        "a\u00a0b\u00adc",
        "a\u200bb\u2003c\u3000d\u2028e\U000e0001f\ue000g",
        "\U0001f468\u200d\U0001f469\u202e",
    ):
        assert cells(_one_cell_each(text)) == sum(map(char_cells, text)), text
