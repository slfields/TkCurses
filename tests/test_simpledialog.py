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

"""Prompt-dialog rules that need no terminal."""

from __future__ import annotations

import pytest

from tkcurses import TclError
from tkcurses.simpledialog import (
    Dialog,
    _QueryFloat,
    _QueryInteger,
    _QueryString,
    askfloat,
    askinteger,
    askstring,
)


class Bare(_QueryInteger):
    """A query dialog whose fields are set without any window being built."""

    def __init__(self, text, **kw):
        self.prompt = ""
        self.minvalue = kw.get("minvalue")
        self.maxvalue = kw.get("maxvalue")
        self.initialvalue = None
        self.entry = _Entry(text)
        self.result = None
        self.warnings: list[tuple[str, str]] = []

    def getint(self, value):
        return int(value)


class _Entry:
    def __init__(self, text):
        self._text = text

    def get(self):
        return self._text


@pytest.fixture
def no_boxes(monkeypatch):
    """Record the warnings validate() would show rather than showing them."""
    shown: list[tuple[str, str]] = []

    def showwarning(title=None, message=None, **kw):
        shown.append((title, message))
        return "ok"

    monkeypatch.setattr("tkcurses.simpledialog.messagebox.showwarning", showwarning)
    return shown


# -------------------------------------------------------------- validation


def test_a_value_that_reads_is_kept(no_boxes):
    dialog = Bare("42")
    assert dialog.validate() is True
    assert dialog.result == 42
    assert no_boxes == []


def test_a_value_that_will_not_read_is_refused_with_a_reason(no_boxes):
    """And nothing is kept: the caller must not be handed a bad value."""
    dialog = Bare("abc")
    assert dialog.validate() is False
    assert dialog.result is None
    assert no_boxes[0][0] == "Illegal value"
    assert "Not an integer." in no_boxes[0][1]


def test_a_value_below_the_minimum_is_refused(no_boxes):
    dialog = Bare("0", minvalue=1)
    assert dialog.validate() is False
    assert dialog.result is None
    assert no_boxes[0][0] == "Too small"
    assert "minimum value is 1" in no_boxes[0][1]


def test_a_value_above_the_maximum_is_refused(no_boxes):
    dialog = Bare("99", maxvalue=10)
    assert dialog.validate() is False
    assert no_boxes[0][0] == "Too large"
    assert "maximum value is 10" in no_boxes[0][1]


def test_a_value_on_the_boundary_is_allowed(no_boxes):
    """The limits are inclusive, as Tk's < and > comparisons make them."""
    assert Bare("1", minvalue=1, maxvalue=10).validate() is True
    assert Bare("10", minvalue=1, maxvalue=10).validate() is True
    assert no_boxes == []


# ------------------------------------------------------------- the message


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        (_QueryInteger, "Not an integer."),
        (_QueryFloat, "Not a floating-point value."),
    ],
)
def test_each_kind_says_what_it_wanted(kind, message):
    assert kind.errormessage == message


def test_a_string_prompt_takes_anything_and_so_needs_no_message():
    """It has no getresult that can raise, so it never shows a warning."""
    assert _QueryString.getresult is not _QueryInteger.getresult


# ----------------------------------------------------------------- the hooks


def test_validate_allows_by_default():
    """A dialog that checks nothing must not refuse everything."""
    assert Dialog.validate(object()) is True  # type: ignore[arg-type]


def test_apply_keeps_nothing_by_default():
    Dialog.apply(object())  # type: ignore[arg-type]


def test_body_asks_for_no_focus_by_default():
    assert Dialog.body(object(), object()) is None  # type: ignore[arg-type]


# ----------------------------------------------------------------- no root


@pytest.mark.parametrize("ask", [askstring, askinteger, askfloat])
def test_asking_without_a_root_says_so(ask):
    with pytest.raises(TclError, match="No root window"):
        ask("Title", "Prompt")
