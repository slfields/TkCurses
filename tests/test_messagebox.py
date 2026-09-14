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

"""Message box rules that need no terminal.

Most of a message box is a table, and the table is Tk's: which buttons each
type has, which is the default when nobody says, and what dismissing the box
answers. Those are checked here against the values in Tk 9.0's msgbox.tcl.
"""

from __future__ import annotations

import pytest

from tkcurses import Misc, TclError
from tkcurses.messagebox import (
    _TYPES,
    ABORT,
    ABORTRETRYIGNORE,
    CANCEL,
    NO,
    OK,
    OKCANCEL,
    RETRY,
    RETRYCANCEL,
    YES,
    YESNO,
    YESNOCANCEL,
    Message,
    _label,
)


def box(**options):
    """A message box that has had its options settled but is not shown."""
    message = Message(Misc(), **options)
    message._fixoptions()
    return message


# ------------------------------------------------------------- the buttons


@pytest.mark.parametrize(
    ("kind", "names"),
    [
        (ABORTRETRYIGNORE, [ABORT, RETRY, "ignore"]),
        (OK, [OK]),
        (OKCANCEL, [OK, CANCEL]),
        (RETRYCANCEL, [RETRY, CANCEL]),
        (YESNO, [YES, NO]),
        (YESNOCANCEL, [YES, NO, CANCEL]),
    ],
)
def test_each_type_has_the_buttons_tk_gives_it(kind, names):
    assert [name for name, _ in _TYPES[kind][0]] == names


@pytest.mark.parametrize(
    ("marked", "text", "underline"),
    [("&Abort", "Abort", 0), ("&OK", "OK", 0), ("plain", "plain", -1)],
)
def test_the_ampersand_marks_the_underlined_letter(marked, text, underline):
    """Tk writes its labels as &Abort; the & is the mark, not a character."""
    assert _label(marked) == (text, underline)


# ------------------------------------------------------------- the default


def test_the_first_button_is_the_default_when_nobody_says():
    """msgbox.tcl: 'If no default button was specified, the default default
    is the first button', with the bug number that made it so."""
    assert box(type=YESNOCANCEL).options["default"] == YES


def test_a_named_default_is_kept():
    assert box(type=YESNO, default=NO).options["default"] == NO


def test_a_default_naming_a_button_this_type_has_not_got_is_refused():
    with pytest.raises(TclError, match="bad -default"):
        box(type=YESNO, default=CANCEL)


def test_an_unknown_type_is_refused():
    """Tk raises rather than showing a box nobody asked for."""
    with pytest.raises(TclError, match="bad -type"):
        box(type="maybe")


def test_the_type_defaults_to_ok():
    assert box().options["type"] == OK


# -------------------------------------------------------------- dismissal


@pytest.mark.parametrize(
    ("kind", "answer"),
    [
        (ABORTRETRYIGNORE, ABORT),
        (OK, OK),
        (OKCANCEL, CANCEL),
        (RETRYCANCEL, CANCEL),
        (YESNO, NO),
        (YESNOCANCEL, CANCEL),
    ],
)
def test_dismissing_answers_what_the_type_stands_for(kind, answer):
    """A yesno box closed with Escape answers 'no', not nothing.

    The caller is meant to be able to rely on one of the type's own answers
    coming back rather than handle a third case it never asked for.
    """
    message = box(type=kind)
    assert message._fixresult(Misc(), None) == answer


def test_a_pressed_button_answers_with_its_own_name():
    message = box(type=YESNO)
    assert message._fixresult(Misc(), YES) == YES


# --------------------------------------------------------------- the icon


def test_the_icon_is_kept_in_the_options_though_nothing_draws_it():
    """A terminal has no stock pictures. The option is carried anyway, so
    anything reading the options back sees what was asked for."""
    assert box(icon="warning").options["icon"] == "warning"
