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


"""One variable, several widgets, and the sharing that is the whole point.

A ``Variable`` is not a widget's storage. It is the thing two widgets can
both be bound to so that changing either changes the other, and that claim
is untestable with one widget - which is why nothing tested it until now.

Three shapes, because they fail differently: a ``StringVar`` read and written
by text widgets, an ``IntVar`` that decides which of a radio group is chosen,
and a ``BooleanVar`` two checkbuttons share.
"""

from __future__ import annotations

import pytest

import tkcurses


@pytest.fixture
def text_widgets(app):
    """An Entry, a Label and a Spinbox on one StringVar."""
    var = tkcurses.StringVar(app, value="start")
    entry = tkcurses.Entry(app, name="e", textvariable=var)
    label = tkcurses.Label(app, name="l", textvariable=var)
    spin = tkcurses.Spinbox(app, name="s", textvariable=var, values=("start", "next"))
    for widget in (entry, label, spin):
        widget.pack()
    app.update_layout()
    return var, entry, label, spin


# ------------------------------------------------------------ one to many


def test_setting_the_variable_reaches_every_widget_bound_to_it(text_widgets):
    var, entry, label, spin = text_widgets

    var.set("changed")

    assert entry.get() == "changed"
    assert label._text() == "changed"
    assert spin.get() == "changed"


def test_every_widget_starts_from_the_variables_value(text_widgets):
    _var, entry, label, spin = text_widgets
    assert (entry.get(), label._text(), spin.get()) == ("start",) * 3


# ------------------------------------------------------------ many to one


def test_editing_one_widget_reaches_the_others_through_the_variable(text_widgets):
    """The direction that makes it sharing rather than broadcasting."""
    var, entry, label, spin = text_widgets

    entry.delete(0, "end")
    entry.insert(0, "typed")

    assert var.get() == "typed"
    assert label._text() == "typed"
    assert spin.get() == "typed"


def test_a_widget_that_writes_does_not_reset_the_others_position(text_widgets):
    """Writing through the variable must not disturb a field the user is in
    the middle of - the insertion point stays where it was."""
    var, entry, _label, _spin = text_widgets
    entry.icursor(2)

    var.set("start")

    assert entry.index("insert") == 2


# ---------------------------------------------------------------- traces


def test_a_trace_fires_once_per_change_not_once_per_widget(text_widgets):
    """Three widgets are bound to this variable. A trace that fired per
    listener would report three writes for one set, which is the shape of
    bug that makes an application's own handler run in triplicate.
    """
    var, _entry, _label, _spin = text_widgets
    fired = []
    var.trace_add("write", lambda *args: fired.append(var.get()))

    var.set("once")

    assert fired == ["once"]


def test_a_trace_fires_for_a_change_made_through_a_widget(text_widgets):
    var, entry, _label, _spin = text_widgets
    fired = []
    var.trace_add("write", lambda *args: fired.append(var.get()))

    entry.delete(0, "end")
    entry.insert(0, "x")

    assert fired[-1] == "x"


def test_removing_a_trace_stops_it(text_widgets):
    var, _entry, _label, _spin = text_widgets
    fired = []
    name = var.trace_add("write", lambda *args: fired.append(var.get()))
    var.trace_remove("write", name)

    var.set("quiet")

    assert fired == []


# ------------------------------------------------------------- destruction


def test_destroying_one_widget_leaves_the_others_following(text_widgets):
    """The failure this guards against is a shared variable keeping a dead
    widget on its list and taking the rest down with it.
    """
    var, entry, label, spin = text_widgets

    entry.destroy()
    var.set("after")

    assert label._text() == "after"
    assert spin.get() == "after"


def test_a_destroyed_widget_does_not_answer_for_the_variable(text_widgets):
    var, entry, _label, _spin = text_widgets
    entry.destroy()

    var.set("after")

    assert not entry.winfo_exists()


# -------------------------------------------------------------- a radio group


def test_an_intvar_chooses_exactly_one_of_a_radio_group(app):
    chosen = tkcurses.IntVar(app, value=1)
    buttons = [
        tkcurses.Radiobutton(app, name=f"r{index}", variable=chosen, value=index)
        for index in range(3)
    ]
    for button in buttons:
        button.pack()
    app.update_layout()

    assert [button.cget("value") == chosen.get() for button in buttons] == [
        False,
        True,
        False,
    ]

    chosen.set(2)

    assert [button.cget("value") == chosen.get() for button in buttons] == [
        False,
        False,
        True,
    ]


def test_selecting_a_radiobutton_moves_the_choice_away_from_the_others(app):
    chosen = tkcurses.IntVar(app, value=0)
    buttons = [
        tkcurses.Radiobutton(app, name=f"r{index}", variable=chosen, value=index)
        for index in range(3)
    ]
    for button in buttons:
        button.pack()
    app.update_layout()

    buttons[2].select()

    assert chosen.get() == 2


def test_a_scale_and_a_radio_group_can_share_one_variable(app):
    """Different widget kinds on one variable, which is where a per-widget
    assumption about the value's type shows up.
    """
    shared = tkcurses.IntVar(app, value=2)
    button = tkcurses.Radiobutton(app, name="r", variable=shared, value=2)
    scale = tkcurses.Scale(app, name="sc", variable=shared, from_=0, to=10)
    for widget in (button, scale):
        widget.pack()
    app.update_layout()
    assert scale.get() == 2

    shared.set(7)

    assert scale.get() == 7
    assert button.cget("value") != shared.get()


# ------------------------------------------------------------- checkbuttons


def test_two_checkbuttons_on_one_variable_move_together(app):
    shared = tkcurses.BooleanVar(app, value=False)
    first = tkcurses.Checkbutton(app, name="c1", variable=shared)
    second = tkcurses.Checkbutton(app, name="c2", variable=shared)
    for widget in (first, second):
        widget.pack()
    app.update_layout()

    first.select()

    assert shared.get() is True

    second.deselect()

    assert shared.get() is False


# ---------------------------------------------------- what cget reports


@pytest.mark.xfail(reason="TkCurses-u4y: cget('text') does not follow a textvariable")
def test_cget_text_reports_what_the_variable_holds(text_widgets):
    """Measured against Tk 9.0.2, where a Label built with textvariable= and
    no text= answers cget('text') with the variable's value, and keeps
    answering with it as the variable changes.

    The display is already right - _text() prefers the variable - so this is
    only what cget reports, which is why every screen looks correct and the
    divergence went unnoticed. Reading cget('text') to find what a label is
    showing is ordinary tkinter code, and here it answers with something
    that is not on the screen.
    """
    var, _entry, label, _spin = text_widgets
    assert label.cget("text") == "start"

    var.set("changed")

    assert label.cget("text") == "changed"
