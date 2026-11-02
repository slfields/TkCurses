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

"""The focus highlight ring's options: accepted and answered, drawing nothing.

TkCurses-gm66.1. Tk draws a ring around a widget to show it has the focus. Its
three options were refused here, which stopped a tkinter program at the line,
and they are among the most common options tkinter code passes - usually
``highlightthickness=0``, to hide X11's ring for looks.

They are accepted and stored now, and change nothing drawn: every widget that
takes the focus already shows it with a cue sized to a cell, and the cue stays
when a program sets the thickness to 0 (``test_button_tty.py`` and
``test_entry_tty.py``). The reason is in ``Widget._widget_options``.
"""

from __future__ import annotations

import pytest

import tkcurses
from tkcurses import Misc

#: Tk 9.0.2's default ``-highlightthickness``, measured with real tkinter: 1 on
#: the widgets that take the focus, 0 on the rest and on the root.
TK_DEFAULT_THICKNESS = {
    "Button": 1, "Canvas": 1, "Checkbutton": 1, "Entry": 1, "Frame": 0,
    "Label": 0, "LabelFrame": 0, "Listbox": 1, "Menubutton": 0, "Message": 0,
    "Radiobutton": 1, "Scale": 1, "Scrollbar": 0, "Spinbox": 1, "Text": 1,
    "Toplevel": 0,
}  # fmt: skip

RING = {"highlightbackground": "blue", "highlightcolor": "red", "highlightthickness": 0}


@pytest.fixture
def root():
    return Misc()


@pytest.mark.parametrize("name", sorted(TK_DEFAULT_THICKNESS))
def test_every_classic_widget_takes_the_ring_options(root, name):
    widget = getattr(tkcurses, name)(root, **RING)
    assert {key: widget.cget(key) for key in RING} == RING


@pytest.mark.parametrize("name", sorted(TK_DEFAULT_THICKNESS))
def test_the_thickness_defaults_to_tks(root, name):
    widget = getattr(tkcurses, name)(root)
    assert widget.cget("highlightthickness") == TK_DEFAULT_THICKNESS[name]


def test_an_option_menu_takes_them_too(root):
    """Built on a Menubutton, and listed by Tk on its own."""
    menu = tkcurses.OptionMenu(root, tkcurses.StringVar(root), "a", "b")
    menu.configure(**RING)
    assert menu.cget("highlightcolor") == "red"


def test_the_root_takes_them(made_root):
    made_root.configure(**RING)
    assert made_root.cget("highlightthickness") == 0
    assert made_root.cget("highlightbackground") == "blue"


def test_configure_answers_them_with_tks_database_names(root):
    button = tkcurses.Button(root, highlightcolor="red")
    assert button.configure("highlightcolor") == (
        "highlightcolor",
        "highlightColor",
        "HighlightColor",
        "",
        "red",
    )
    assert button.configure("highlightthickness")[1:] == (
        "highlightThickness",
        "HighlightThickness",
        1,
        1,
    )


@pytest.fixture
def made_root():
    root = tkcurses.Tk(useTk=False)
    yield root
    root.destroy()
