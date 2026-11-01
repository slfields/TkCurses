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

"""``configure("name")``: one option asked for, on every widget. TkCurses-kifn.

It crashed on all of them - every override of ``configure`` merged ``cnf``
into a dict first - and Tk answers it with a five-tuple. The fixed cases below
were measured on Tcl/Tk 9.0.2; the last test compares every option of every
widget against the real toolkit, where there is a display to start one.
"""

from __future__ import annotations

import tkinter
from tkinter import ttk as real_ttk

import pytest

import tkcurses
from tkcurses import Misc, TclError, ttk
from tkcurses._core.option_names import WIDGET_CLASSES

CLASSIC = [
    "Button", "Canvas", "Checkbutton", "Entry", "Frame", "Label", "LabelFrame",
    "Listbox", "Menu", "Menubutton", "Message", "PanedWindow", "Radiobutton",
    "Scale", "Scrollbar", "Spinbox", "Text", "Toplevel",
]  # fmt: skip
THEMED = [
    "Button", "Checkbutton", "Combobox", "Entry", "Frame", "Label",
    "Labelframe", "LabeledScale", "Menubutton", "Notebook", "Panedwindow",
    "Progressbar", "Radiobutton", "Scale", "Scrollbar", "Separator",
    "Sizegrip", "Spinbox", "Treeview",
]  # fmt: skip


@pytest.fixture
def root():
    return Misc()


@pytest.fixture
def made():
    """Roots built by a test, destroyed after it: only one may exist at once."""
    roots = []
    yield roots
    for window in roots:
        window.destroy()


def _ours(root, key, made):
    """One of our widgets, by its table name: ``"tk.Button"``, ``"ttk.Entry"``."""
    module, name = key.split(".")
    if key == "tk.Tk":
        made.append(tkcurses.Tk(useTk=False))
        return made[-1]
    if name == "OptionMenu":
        owner = ttk if module == "ttk" else tkcurses
        return owner.OptionMenu(root, tkcurses.StringVar(root), "a")
    return getattr(ttk if module == "ttk" else tkcurses, name)(root)


def test_every_widget_class_is_in_the_table():
    expected = {f"tk.{n}" for n in CLASSIC} | {f"ttk.{n}" for n in THEMED}
    expected |= {"tk.Tk", "tk.OptionMenu", "ttk.OptionMenu"}
    assert expected == WIDGET_CLASSES


@pytest.mark.parametrize("key", sorted(WIDGET_CLASSES))
def test_every_widget_answers_a_query_for_every_option(root, key, made):
    widget = _ours(root, key, made)
    options = widget.keys()  # a widget's, not a dict's
    for option in options:
        answer = widget.configure(option)
        assert len(answer) == 5, (key, option, answer)
        assert answer[0] == option
        assert answer[4] == widget.cget(option), (key, option)
        assert widget.config(option) == answer


@pytest.mark.parametrize(
    ("make", "option", "names"),
    [
        (lambda r: tkcurses.Checkbutton(r), "onvalue", ("onValue", "Value")),
        (lambda r: ttk.Checkbutton(r), "onvalue", ("onValue", "OnValue")),
        (lambda r: ttk.Combobox(r), "postcommand", ("postCommand", "PostCommand")),
        (lambda r: ttk.Frame(r), "class", ("", "")),
        (lambda r: ttk.Entry(r), "background", ("windowColor", "WindowColor")),
        (lambda r: ttk.Label(r), "background", ("frameColor", "FrameColor")),
        (lambda r: ttk.Radiobutton(r), "value", ("Value", "Value")),
        (lambda r: ttk.Treeview(r), "displaycolumns", ("displayColumns", "DisplayColumns")),
    ],
)  # fmt: skip
def test_the_database_names_are_tks(root, make, option, names):
    assert make(root).configure(option)[1:3] == names


def test_the_default_and_the_value_are_the_widgets(root):
    button = tkcurses.Button(root, text="OK")
    assert button.configure("text") == ("text", "text", "Text", "", "OK")


def test_a_short_spelling_answers_the_full_entry(root):
    """Measured: ``configure("bg")`` is background's five-tuple, under its name."""
    button = tkcurses.Button(root, background="red")
    assert button.configure("bg") == button.configure("background")
    assert button.configure("bg")[0] == "background"


@pytest.mark.parametrize(
    ("make", "option", "message"),
    [
        (lambda r: tkcurses.Button(r), "-text", 'unknown option "--text"'),
        (lambda r: tkcurses.Button(r), "nope", 'unknown option "-nope"'),
        (lambda r: ttk.Button(r), "bg", 'unknown option "-bg"'),
    ],
)
def test_a_query_refuses_what_tk_refuses(root, make, option, message):
    with pytest.raises(TclError, match=message):
        make(root).configure(option)


def test_the_root_window_answers_a_query(root, made):
    window = _ours(root, "tk.Tk", made)
    assert window.configure("menu")[:3] == ("menu", "menu", "Menu")


def test_a_programs_own_override_still_answers(root):
    """A subclass's configure is wrapped too, as it is defined."""

    class Mine(ttk.Entry):
        def configure(self, cnf=None, **kw):
            self.seen = True
            return super().configure(cnf, **kw)

    entry = Mine(root)
    assert entry.configure("foreground")[1:3] == ("textColor", "TextColor")
    entry.configure(foreground="red")
    assert entry.seen and entry.cget("foreground") == "red"


def test_setting_and_listing_are_unchanged(root):
    button = tkcurses.Button(root)
    assert button.configure(text="x") is None
    assert button.configure({"text": "y"}) is None
    assert button.configure()["text"] == "y"


# ----------------------------------------------- against the real toolkit


@pytest.fixture(scope="module")
def real_root():
    try:
        real = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    real.withdraw()
    yield real
    real.destroy()


def _theirs(real, key):
    module, name = key.split(".")
    if key == "tk.Tk":
        return real
    owner = real_ttk if module == "ttk" else tkinter
    if name == "OptionMenu":
        return owner.OptionMenu(real, tkinter.StringVar(real), "a")
    return getattr(owner, name)(real)


@pytest.mark.parametrize("key", sorted(WIDGET_CLASSES))
def test_the_database_names_match_the_real_toolkit(root, real_root, key, made):
    ours = _ours(root, key, made)
    theirs = _theirs(real_root, key)
    shared = set(ours.keys()) & set(theirs.keys())
    wrong = {
        option: (ours.configure(option)[1:3], theirs.configure(option)[1:3])
        for option in shared
        if ours.configure(option)[1:3] != tuple(theirs.configure(option)[1:3])
    }
    assert not wrong
