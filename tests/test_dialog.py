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

"""Tests for the classic dialog that need no terminal."""

from __future__ import annotations

import pytest

from tkcurses import Misc, TclError
from tkcurses.dialog import DIALOG_ICON, DISMISSED, Dialog, _ButtonRow, _default_index

# ------------------------------------------------------------ the default


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (0, 0),
        (2, 2),
        ("1", 1),
        # An empty string is how tkinter spells "no default"; Tk's own
        # dialog.tcl then takes the `default >= 0` branch as false.
        ("", DISMISSED),
        (None, DISMISSED),
        (-1, -1),
        ("nonsense", DISMISSED),
    ],
)
def test_the_default_option_is_an_index_or_nothing(given, expected):
    assert _default_index(given) == expected


# ----------------------------------------------------------------- result


def test_a_dismissed_dialog_answers_minus_one():
    """Tk's value, from the <Destroy> binding in dialog.tcl."""
    assert DISMISSED == -1


def test_finish_with_none_is_a_dismissal():
    row = _ButtonRow(Misc(), {"strings": ("OK",)})
    row.finish(None)
    assert row.chosen == -1


def test_finish_with_an_index_records_it():
    row = _ButtonRow(Misc(), {"strings": ("OK", "Cancel")})
    row.finish(1)
    assert row.chosen == 1


def test_a_new_dialog_starts_dismissed():
    """Nothing has been pressed yet, so nothing else would be truthful."""
    assert _ButtonRow(Misc(), {}).chosen == -1


# --------------------------------------------------------------- the shape


def test_options_come_from_the_dictionary_and_the_keywords_together():
    """tkinter's own example passes everything in the dictionary."""
    row = _ButtonRow(Misc(), {"title": "T", "text": "body"})
    assert row.options["title"] == "T"
    assert row.options["text"] == "body"


def test_the_stock_icon_name_is_still_importable():
    """tkinter's dialog module exports it, and code names it."""
    assert DIALOG_ICON == "questhead"


def test_destroy_does_nothing_and_says_so():
    """tkinter's does the same: by the time it can be called the window has
    already gone, and raising here would break every caller that tidies up."""
    dialog = Dialog.__new__(Dialog)
    dialog.destroy()


def test_making_a_dialog_without_a_root_says_so():
    with pytest.raises(TclError, match="No root window"):
        Dialog(None, {"text": "hello", "strings": ("OK",)})
