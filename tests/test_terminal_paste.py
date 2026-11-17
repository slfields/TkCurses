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

"""What Entry and Text do with ``<<TerminalPaste>>``, the event a paste the
terminal marked arrives as. TkCurses-tcbj.22.

Tk has no such event - an X11 paste is a selection, never keystrokes - so
the rules are this library's: one edit, controls out, line breaks kept
where a widget has lines.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Entry, Misc, Spinbox, StringVar, Text, ttk
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(window_factory=stub_window, panel_factory=None)
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    return root


def placed(widget):
    widget._allocate(Rect(0, 0, 22, 3))
    widget._map()
    widget.focus_set()
    return widget


def paste(widget, data):
    widget.event_generate("<<TerminalPaste>>", data=data)


ENTRIES = [Entry, Spinbox, ttk.Entry, ttk.Spinbox, ttk.Combobox]


# ------------------------------------------------------------------ entries


@pytest.mark.parametrize("kind", ENTRIES, ids=lambda k: k.__module__ + "." + k.__name__)
def test_an_entry_takes_a_paste_as_one_line(root, kind):
    entry = placed(kind(root))
    entry.insert(0, "<>")
    entry.icursor(1)
    paste(entry, "one\r\ntwo\rthree\nfour\t\x1b[31m\x07\x9b\x7f!")
    assert entry.get() == "<one two three four[31m!>"
    assert entry.index("insert") == len("<one two three four[31m!")


def test_a_paste_replaces_the_selection(root):
    entry = placed(Entry(root))
    entry.insert(0, "hello world")
    entry.icursor(0)
    entry.selection_range(6, 11)
    paste(entry, "there")
    assert entry.get() == "hello there"
    assert entry.index("insert") == 11


def test_a_paste_is_validated_once_as_a_whole(root):
    seen = []

    def check(action, index, proposed, inserted):
        seen.append((action, index, proposed, inserted))
        return True

    entry = placed(Entry(root))
    entry.insert(0, "ab")
    entry.configure(
        validate="key",
        validatecommand=(entry.register(check), "%d", "%i", "%P", "%S"),
    )
    entry.selection_range(0, 1)
    paste(entry, "XY")
    assert seen == [("1", "0", "XYb", "XY")]
    assert entry.get() == "XYb"


def test_a_validator_refusing_a_paste_leaves_the_entry_alone(root):
    entry = placed(Entry(root))
    entry.insert(0, "12")
    entry.configure(
        validate="key",
        validatecommand=(entry.register(str.isdigit), "%P"),
    )
    paste(entry, "3x")
    assert entry.get() == "12"
    paste(entry, "34")
    assert entry.get() == "1234"


@pytest.mark.parametrize("state", ["readonly", "disabled"])
def test_an_entry_that_cannot_be_edited_takes_no_paste(root, state):
    entry = placed(Entry(root))
    entry.insert(0, "x")
    entry.configure(state=state)
    paste(entry, "y")
    assert entry.get() == "x"


def test_a_paste_reaches_the_textvariable(root):
    value = StringVar(root)
    entry = placed(Entry(root, textvariable=value))
    paste(entry, "set")
    assert value.get() == "set"


def test_a_paste_of_nothing_but_controls_changes_nothing(root):
    calls = []
    entry = placed(Entry(root))
    entry.configure(
        validate="key",
        validatecommand=(entry.register(lambda: calls.append(1) or True),),
    )
    paste(entry, "\x1b\x07")
    assert entry.get() == ""
    assert calls == []


# --------------------------------------------------------------------- Text


@pytest.fixture
def text(root):
    widget = placed(Text(root, undo=True))
    widget.insert("1.0", "start\n")
    widget.edit_separator()
    widget.mark_set("insert", "end-1c")
    return widget


def test_a_text_keeps_the_lines_and_tabs_of_a_paste(text):
    paste(text, "if x:\r\n\tgo()\rdone\x1b[0m\x00\x9b\x7f")
    assert text.get("1.0", "end-1c") == "start\nif x:\n\tgo()\ndone[0m"
    assert text.index("insert") == "4.7"


def test_a_paste_is_one_undo_step(text):
    text.tag_add("sel", "1.0", "1.5")
    paste(text, "line one\rline two")
    assert text.get("1.0", "end-1c") == "line one\nline two\n"
    text.edit_undo()
    assert text.get("1.0", "end-1c") == "start\n"


def test_a_paste_is_not_indented(text):
    """Typed, Return keeps nothing here either, but a paste must never be
    indented whatever a program binds to Return."""
    text.bind("<Return>", lambda e: text.insert("insert", "\n    ") or "break")
    paste(text, "a\rb")
    assert text.get("1.0", "end-1c") == "start\na\nb"


def test_a_disabled_text_takes_no_paste(text):
    text.tag_add("sel", "1.1", "1.3")
    text.configure(state="disabled")
    paste(text, "nope")
    assert text.get("1.0", "end-1c") == "start\n"
    assert text.index("insert") == "2.0", "nor moves the cursor to the selection"


def test_a_program_can_take_the_paste_itself(root):
    got = []
    text = placed(Text(root))
    text.bind("<<TerminalPaste>>", lambda e: got.append(e.data) or "break")
    paste(text, "mine")
    assert got == ["mine"]
    assert text.get("1.0", "end-1c") == ""
