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


def test_the_length_never_changes():
    """What the clipping either side of it depends on.

    If a substitution were wider or narrower, the slice that keeps a write
    inside its window would be cutting the wrong number of cells - which is
    the bug this function exists to prevent, reintroduced one level down.
    """
    for text in ("\tAB", "a\x00b", "plain", "\t\t\t", "a\x1b\x7f\tz"):
        assert len(_one_cell_each(text)) == len(text), text
