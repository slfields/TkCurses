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

"""Entry validation, every condition against every kind of validator.

The classic Entry and ttk's follow different rules, and the ttk entries here
inherited the classic ones until TkCurses-4ag. Each row below was MEASURED on
Tcl/Tk 9.0.2 by running the same scenario through tkinter's ``tk.Entry`` and
``ttk.Entry``: an entry holding ``hello`` behind a textvariable, a validator
that approves, refuses, raises or appends ``!`` to the entry, and one of the
four conditions -

* ``key``: ``insert(0, "X")`` under ``validate="key"``
* ``focusin`` / ``focusout``: the focus arriving, or leaving, under that mode
* ``forced``: the variable set to ``world`` under ``validate="all"``

- then the text, the ``validate`` option, the ``invalid`` state, whether the
``invalidcommand`` ran, and whether anything was raised.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Entry, Misc, StringVar, TclError, ttk
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack

#: (condition, validator) -> (text, validate, invalid, invalidcommand ran, raises)
TTK = {
    ("key", "accept"): ("Xhello", "key", False, False, False),
    ("key", "refuse"): ("hello", "key", False, True, False),
    ("key", "raise"): ("hello", "none", False, False, True),
    ("key", "edit"): ("hello!", "key", False, False, False),
    ("focusin", "accept"): ("hello", "focusin", False, False, False),
    ("focusin", "refuse"): ("hello", "focusin", True, True, False),
    ("focusin", "raise"): ("hello", "none", False, False, False),
    ("focusin", "edit"): ("hello!", "focusin", True, False, False),
    ("focusout", "accept"): ("hello", "focusout", False, False, False),
    ("focusout", "refuse"): ("hello", "focusout", True, True, False),
    ("focusout", "raise"): ("hello", "none", False, False, False),
    ("focusout", "edit"): ("hello!", "focusout", True, False, False),
    # ttk does not validate a textvariable write at all.
    ("forced", "accept"): ("world", "all", False, False, False),
    ("forced", "refuse"): ("world", "all", False, False, False),
    ("forced", "raise"): ("world", "all", False, False, False),
    ("forced", "edit"): ("world", "all", False, False, False),
}

#: The classic Entry has no state, so its invalid column is always False.
CLASSIC = {
    ("key", "accept"): ("Xhello", "key", False, False, False),
    ("key", "refuse"): ("hello", "key", False, True, False),
    ("key", "raise"): ("hello", "none", False, False, False),
    ("key", "edit"): ("hello!", "none", False, False, False),
    ("focusin", "accept"): ("hello", "focusin", False, False, False),
    ("focusin", "refuse"): ("hello", "focusin", False, True, False),
    ("focusin", "raise"): ("hello", "none", False, False, False),
    ("focusin", "edit"): ("hello!", "focusin", False, False, False),
    ("focusout", "accept"): ("hello", "focusout", False, False, False),
    ("focusout", "refuse"): ("hello", "focusout", False, True, False),
    ("focusout", "raise"): ("hello", "none", False, False, False),
    ("focusout", "edit"): ("hello!", "focusout", False, False, False),
    ("forced", "accept"): ("world", "all", False, False, False),
    ("forced", "refuse"): ("world", "none", False, False, False),
    ("forced", "raise"): ("world", "none", False, False, False),
    # Tk abandons the update and is left holding "hello" while its variable
    # holds "world"; here both edits land. The one recorded divergence of the
    # forced condition - TkCurses-doh.
    ("forced", "edit"): ("world!", "none", False, False, False),
}

MODES = {"key": "key", "focusin": "focusin", "focusout": "focusout", "forced": "all"}


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(window_factory=stub_window, panel_factory=None)
    root._rect = Rect(0, 0, 40, 12)
    root._mapped = True
    return root


def placed(widget, row):
    widget._allocate(Rect(0, row, 22, 3))
    widget._map()
    return widget


def scenario(root, cls, condition, behaviour, *, preset_invalid=False):
    """Run one cell of the table and report what came of it."""
    other = placed(Entry(root, name="other"), 0)
    variable = StringVar(root, value="hello")
    entry = placed(cls(root, name="e", textvariable=variable), 4)
    refused: list[str] = []

    def validator(proposed):
        if behaviour == "raise":
            raise ZeroDivisionError
        if behaviour == "edit":
            entry.insert("end", "!")
        return behaviour != "refuse"

    entry.configure(
        validate=MODES[condition],
        validatecommand=validator,
        invalidcommand=lambda proposed: refused.append(proposed),
    )
    if preset_invalid:
        entry.state(["invalid"])
    other.focus_set()
    raised = False
    try:
        if condition == "key":
            entry.insert(0, "X")
        elif condition == "focusin":
            entry.focus_set()
        elif condition == "focusout":
            entry.focus_set()
            other.focus_set()
        else:
            variable.set("world")
    except TclError:
        raised = True
    invalid = "invalid" in entry.state() if hasattr(entry, "state") else False
    return (entry.get(), str(entry.cget("validate")), invalid, bool(refused), raised)


@pytest.mark.parametrize(("cell", "expected"), list(TTK.items()), ids=str)
def test_ttk_entry_validates_as_ttk_does(root, cell, expected):
    assert scenario(root, ttk.Entry, *cell) == expected


@pytest.mark.parametrize(("cell", "expected"), list(CLASSIC.items()), ids=str)
def test_the_classic_entry_validates_as_tk_does(root, cell, expected):
    assert scenario(root, Entry, *cell) == expected


@pytest.mark.parametrize("cls", [ttk.Combobox, ttk.Spinbox])
def test_no_ttk_entry_validates_a_variable_write(root, cls):
    """Measured on all three: the validator is not called at all."""
    asked: list[str] = []
    variable = StringVar(root, value="a")
    entry = cls(root, name="e", textvariable=variable)
    entry.configure(validate="all", validatecommand=lambda p: asked.append(p) or True)
    variable.set("b")
    assert asked == []


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        # Key validation never touches the state: a preset invalid stays.
        ("key", True),
        # A focus approval clears it, even set by hand.
        ("focusin", False),
        ("focusout", False),
        # No validation runs on a variable write, so nothing clears it.
        ("forced", True),
    ],
)
def test_an_approval_and_the_invalid_state_set_by_hand(root, condition, expected):
    assert scenario(root, ttk.Entry, condition, "accept", preset_invalid=True)[2] is (
        expected
    )
