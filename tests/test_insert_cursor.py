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

"""Tk's insertion-cursor options, and what they ask of the terminal's cursor.

TkCurses-gm66.2. Every value rule and error message here was measured on Tk
9.0.2 with real tkinter. What the options do is ``BaseWidget._cursor_style``:
the cursor is the terminal's, so one left at Tk's default asks nothing, and one
a program changed asks for the nearest shape or colour a terminal has.
"""

from __future__ import annotations

import pytest

import tkcurses
from tkcurses import Misc, TclError
from tkcurses._core.screen import TERMINALS_OWN, CursorStyle, TerminalCursor

INSERTING = ("Canvas", "Entry", "Spinbox", "Text")

#: Tk 9.0.2's defaults, except the colour: Tk's is #000000, ours is the
#: terminal's own, "" - as every colour here defaults.
DEFAULTS = {
    "insertbackground": "",
    "insertborderwidth": 0,
    "insertofftime": 300,
    "insertontime": 600,
    "insertwidth": 2,
}


@pytest.fixture
def root():
    return Misc()


# ------------------------------------------------------------- the options


@pytest.mark.parametrize("name", INSERTING)
def test_the_widgets_with_an_insert_point_take_them(root, name):
    widget = getattr(tkcurses, name)(root)
    assert {key: widget.cget(key) for key in DEFAULTS} == DEFAULTS


def test_text_has_two_more(root):
    text = tkcurses.Text(root)
    assert text.cget("blockcursor") == 0
    assert text.cget("insertunfocussed") == "none"


@pytest.mark.parametrize(
    ("option", "value", "stored"),
    [
        ("insertofftime", -5, -5),
        ("insertofftime", "250", 250),
        ("insertontime", 0, 0),
        ("insertwidth", 0, 0),
        ("insertwidth", -3, 0),
        ("insertborderwidth", -1, 0),
        ("insertborderwidth", 99, 99),
        ("insertbackground", "#ff8000", "#ff8000"),
    ],
)
def test_values_are_stored_as_tk_stores_them(root, option, value, stored):
    entry = tkcurses.Entry(root)
    entry.configure(**{option: value})
    assert entry.cget(option) == stored


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("insertofftime", "x", 'expected integer but got "x"'),
        ("insertontime", 1.5, 'expected integer but got "1.5"'),
        ("insertwidth", "x", 'expected screen distance but got "x"'),
        ("insertborderwidth", "x", 'expected screen distance but got "x"'),
        ("insertbackground", "nope", 'unknown color name "nope"'),
    ],
)
def test_bad_values_are_refused_as_tk_refuses_them(root, option, value, message):
    for build in (
        lambda: tkcurses.Entry(root, **{option: value}),
        lambda: tkcurses.Entry(root).configure(**{option: value}),
    ):
        with pytest.raises(TclError, match=message):
            build()


@pytest.mark.parametrize(
    ("value", "stored"), [("yes", 1), (2, 1), (True, 1), ("off", 0)]
)
def test_blockcursor_reads_back_as_tk_answers_it(root, value, stored):
    assert tkcurses.Text(root, blockcursor=value).cget("blockcursor") == stored


@pytest.mark.parametrize(("value", "stored"), [("h", "hollow"), ("solid", "solid")])
def test_insertunfocussed_takes_a_prefix(root, value, stored):
    assert (
        tkcurses.Text(root, insertunfocussed=value).cget("insertunfocussed") == stored
    )


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("blockcursor", "x", 'expected boolean value but got "x"'),
        (
            "insertunfocussed",
            "x",
            'bad insertunfocussed "x": must be hollow, none, or solid',
        ),
    ],
)
def test_texts_own_two_are_checked(root, option, value, message):
    with pytest.raises(TclError, match=message):
        tkcurses.Text(root, **{option: value})


# --------------------------------------------- what they ask of the terminal


@pytest.mark.parametrize("name", INSERTING)
def test_tks_defaults_ask_nothing(root, name):
    """The person's cursor, as the author chose in UAT 43 (TkCurses-lw2)."""
    assert getattr(tkcurses, name)(root)._cursor_style() == TERMINALS_OWN


@pytest.mark.parametrize(
    ("options", "shape"),
    [
        ({"blockcursor": 1}, 1),
        ({"blockcursor": 1, "insertofftime": 0}, 2),
        ({"insertwidth": 1}, 5),
        ({"insertwidth": 8}, 5),
        ({"insertofftime": 0}, 6),
        ({"insertofftime": -1}, 6),
        ({"insertwidth": 2, "insertontime": 0, "insertborderwidth": 3}, None),
    ],
)
def test_a_changed_option_asks_for_a_shape(root, options, shape):
    assert tkcurses.Text(root, **options)._cursor_style().shape == shape


def test_a_colour_is_asked_for_as_hex(root):
    entry = tkcurses.Entry(root, insertbackground="#ff8000")
    assert entry._cursor_style() == CursorStyle(shape=None, colour="#ff8000")


def test_a_widget_with_no_insert_point_asks_nothing(root):
    assert tkcurses.Button(root)._cursor_style() == TERMINALS_OWN


# ------------------------------------------------------- the terminal cursor


class _Cursor:
    """A TerminalCursor whose focused widget's style a test can change."""

    def __init__(self, cell=(0, 0)):
        self.cell = cell
        self.style = TERMINALS_OWN
        self.sent: list[bytes] = []
        self.cursor = TerminalCursor(
            lambda: self.cell, lambda: self.style, self.sent.append
        )

    def frame(self):
        self.cursor.place()
        return self.sent[-1] if self.sent else None


def test_nothing_is_sent_when_nothing_is_asked():
    cursor = _Cursor()
    for _ in range(3):
        cursor.frame()
    cursor.cursor.restore()
    assert cursor.sent == []


def test_a_request_is_sent_once_and_not_every_frame():
    cursor = _Cursor()
    cursor.style = CursorStyle(shape=2, colour="#ff8000")
    cursor.frame()
    cursor.frame()
    assert cursor.sent == [b"\x1b[2 q\x1b]12;#ff8000\x07"]


def test_moving_to_a_widget_that_asks_nothing_gives_the_cursor_back():
    cursor = _Cursor()
    cursor.style = CursorStyle(shape=6, colour="#ff8000")
    cursor.frame()
    cursor.style = TERMINALS_OWN
    assert cursor.frame() == b"\x1b[0 q\x1b]112\x07"


def test_only_what_changed_is_sent():
    cursor = _Cursor()
    cursor.style = CursorStyle(shape=6, colour="#ff8000")
    cursor.frame()
    cursor.style = CursorStyle(shape=6, colour="#0000ff")
    assert cursor.frame() == b"\x1b]12;#0000ff\x07"


def test_a_hidden_cursor_asks_nothing_new():
    """Nothing focused takes typing: the cursor is hidden, not restyled."""
    cursor = _Cursor(cell=None)
    cursor.style = CursorStyle(shape=2)
    cursor.frame()
    assert cursor.sent == []


def test_restore_gives_back_what_was_asked_for():
    cursor = _Cursor()
    cursor.style = CursorStyle(shape=1)
    cursor.frame()
    cursor.cursor.restore()
    assert cursor.sent[-1] == b"\x1b[0 q"
    cursor.cursor.restore()
    assert len(cursor.sent) == 2, "a second restore sends nothing"
