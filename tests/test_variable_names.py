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

"""Widgets bound to a variable by NAME, and traces kept by name.

Every expectation here was measured through tkinter on Tk 9.0.2: a name
binds both ways, so ``setvar``, any ``Variable`` of that name and the
widget all see each other's writes, and a trace is on the name rather
than on the object that added it.
"""

from __future__ import annotations

import gc
from types import SimpleNamespace

import pytest

import tkcurses
from tkcurses import Misc, StringVar, TclError, Variable, ttk
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 40, 12)
    root._mapped = True
    return root


# ------------------------------------------------------------------ widgets


def test_a_label_bound_by_name_creates_it_from_its_text(root):
    label = tkcurses.Label(root, text="hello", textvariable="g")
    assert root.getvar("g") == "hello"
    assert label.cget("text") == "hello"
    assert label.cget("textvariable") == "g"


def test_setvar_reaches_a_widget_bound_by_name(root):
    label = tkcurses.Label(root, text="hello", textvariable="g")
    root.setvar("g", "x")
    assert label.cget("text") == "x"


def test_any_variable_of_the_name_reaches_it(root):
    label = tkcurses.Label(root, textvariable="g")
    StringVar(root, name="g").set("z")
    assert label.cget("text") == "z"


def test_a_number_is_a_name(root):
    label = tkcurses.Label(root, textvariable=5)
    assert label.cget("textvariable") == "5"
    root.setvar("5", "five")
    assert label.cget("text") == "five"


def test_an_existing_value_wins_over_the_widgets(root):
    root.setvar("g", "kept")
    label = tkcurses.Label(root, text="hello", textvariable="g")
    assert (root.getvar("g"), label.cget("text")) == ("kept", "kept")


@pytest.mark.parametrize(
    ("make", "options", "first"),
    [
        (tkcurses.Entry, {"textvariable": "v"}, ""),
        (tkcurses.Spinbox, {"textvariable": "v", "from_": 2, "to": 5}, "2"),
        (tkcurses.Checkbutton, {"variable": "v"}, "0"),
        (tkcurses.Radiobutton, {"variable": "v", "value": "a"}, ""),
        (tkcurses.Scale, {"variable": "v", "from_": 3, "to": 9}, "3"),
        (tkcurses.Button, {"text": "btn", "textvariable": "v"}, "btn"),
        (tkcurses.Menubutton, {"text": "mb", "textvariable": "v"}, "mb"),
        (tkcurses.Message, {"text": "msg", "textvariable": "v"}, "msg"),
    ],
)
def test_a_classic_widget_creates_the_variable_from_itself(root, make, options, first):
    make(root, **options)
    assert str(root.getvar("v")) == first


@pytest.mark.parametrize(
    ("make", "option"),
    [
        (ttk.Label, "textvariable"),
        (ttk.Entry, "textvariable"),
        (ttk.Checkbutton, "variable"),
        (ttk.Radiobutton, "variable"),
        (ttk.Progressbar, "variable"),
        (ttk.Combobox, "textvariable"),
    ],
)
def test_a_themed_widget_leaves_it_uncreated(root, make, option):
    make(root, **{option: "v"})
    with pytest.raises(TclError, match="no such variable"):
        root.getvar("v")


def test_typing_into_an_entry_bound_by_name_writes_it(root):
    entry = tkcurses.Entry(root, textvariable="e")
    entry.insert(0, "typed")
    assert root.getvar("e") == "typed"
    root.setvar("e", "set")
    assert entry.get() == "set"


def test_a_checkbutton_bound_by_name_follows_setvar(root):
    button = tkcurses.Checkbutton(root, variable="c")
    root.setvar("c", "1")
    assert button._indicator_state == "on"


# ------------------------------------------------------------------- traces


def test_setvar_and_getvar_fire_traces_on_the_name(root):
    seen = []
    variable = StringVar(root, name="g")
    variable.trace_add("write", lambda *args: seen.append(("w", *args)))
    variable.trace_add("read", lambda *args: seen.append(("r", *args)))
    root.setvar("g", "y")
    root.getvar("g")
    assert seen == [("w", "g", "", "write"), ("r", "g", "", "read")]


def test_another_variable_of_the_name_fires_them(root):
    seen = []
    first = StringVar(root, name="g")
    first.trace_add("write", lambda *args: seen.append(args))
    other = StringVar(root, name="g")
    other.set("z")
    assert seen == [("g", "", "write")]


def test_every_variable_of_the_name_lists_and_removes_them(root):
    first = StringVar(root, name="g")
    handle = first.trace_add("write", lambda *args: None)
    second = StringVar(root, name="g")
    assert second.trace_info() == [(("write",), handle)]
    second.trace_remove("write", handle)
    assert first.trace_info() == []


def test_a_widgets_own_trace_is_not_listed(root):
    """Tk keeps them in C, where trace info cannot see them."""
    variable = StringVar(root, name="g")
    tkcurses.Label(root, textvariable=variable)
    assert variable.trace_info() == []


def test_a_variable_collected_takes_only_its_own_traces(root):
    seen = []
    keeper = StringVar(root, name="g")
    keeper.trace_add("write", lambda *args: seen.append("keeper"))
    gone = StringVar(root, name="g")
    gone.trace_add("write", lambda *args: seen.append("gone"))
    del gone
    gc.collect()
    root.setvar("g", "x")
    assert seen == ["keeper"]


def test_a_widget_keeps_its_variable_alive(root):
    """Measured: a Label's variable outlives every StringVar of its name."""
    label = tkcurses.Label(root, textvariable="g")
    variable = StringVar(root, name="g", value="z")
    del variable
    gc.collect()
    assert root.getvar("g") == "z"
    root.setvar("g", "again")
    assert label.cget("text") == "again"


def test_a_variable_with_nothing_on_it_goes_with_its_object(root):
    variable = Variable(root, name="lonely", value="v")
    del variable
    gc.collect()
    with pytest.raises(TclError, match="no such variable"):
        root.getvar("lonely")


def test_wait_variable_takes_a_name(root):
    root.after(0, lambda: root.setvar("done", 1))
    root.wait_variable("done")
