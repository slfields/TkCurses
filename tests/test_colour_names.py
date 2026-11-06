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

"""A widget's colours take every name Tk knows, and refuse one it does not.

Tk refuses an unknown colour name when it is set - ``unknown color name
"x"`` - and so does this now. Before, the five commonest colour options were
stored unchecked and resolved only when drawn, and the library knew 28 names
to Tk's 665: ``bg="SteelBlue"`` was accepted, then raised in the middle of
laying the window out, and everything packed after that widget was never
placed. TkCurses-f760.
"""

from __future__ import annotations

import pytest

import tkcurses
from tkcurses import Misc, TclError, ttk

#: The colour options that used to go unchecked, on a widget that has each.
CASES = [
    ("Label", "background"),
    ("Label", "bg"),
    ("Label", "foreground"),
    ("Label", "fg"),
    ("Label", "highlightbackground"),
    ("Label", "highlightcolor"),
    ("Button", "background"),
    ("Frame", "background"),
    ("Text", "foreground"),
    ("Canvas", "background"),
    ("Listbox", "foreground"),
    ("Entry", "placeholderforeground"),
]


@pytest.fixture
def root():
    return Misc()


def make(root, name, **options):
    return getattr(tkcurses, name)(root, **options)


@pytest.mark.parametrize(("name", "option"), CASES)
def test_an_unknown_name_is_refused_when_set(root, name, option):
    widget = make(root, name)
    with pytest.raises(TclError, match='unknown color name "nocolour"'):
        widget.configure(**{option: "nocolour"})


@pytest.mark.parametrize(("name", "option"), CASES)
def test_an_unknown_name_is_refused_when_the_widget_is_made(root, name, option):
    with pytest.raises(TclError, match='unknown color name "nocolour"'):
        make(root, name, **{option: "nocolour"})


@pytest.mark.parametrize(("name", "option"), CASES)
@pytest.mark.parametrize("colour", ["SteelBlue", "steel blue", "gray90", "#4682b4"])
def test_tks_names_are_taken(root, name, option, colour):
    widget = make(root, name, **{option: colour})
    assert widget.cget(option) == colour


def test_a_themed_widget_refuses_one_too(root):
    with pytest.raises(TclError, match='unknown color name "nocolour"'):
        ttk.Label(root, background="nocolour")


@pytest.mark.tty
def test_a_widget_in_one_of_tks_colours_is_laid_out_with_the_rest(terminal, tmp_path):
    """The program that found it: a Label in SteelBlue, and one after it."""
    term = terminal(cols=40, rows=6)
    term.run_source(
        "import tkcurses as tk\n"
        "root = tk.Tk()\n"
        "tk.Label(root, text='first', bg='SteelBlue').pack()\n"
        "tk.Label(root, text='second', bg='light goldenrod yellow').pack()\n"
        "tk.Label(root, text='third').pack()\n"
        "root.mainloop()\n",
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: t.contains("first") and t.contains("second") and t.contains("third"),
        message="all three labels",
    )


@pytest.mark.parametrize("option", ["background", "foreground", "lmargincolor"])
def test_a_text_tag_refuses_one(root, option):
    """Measured on Tk 9.0.2: tag_configure refuses it then and there."""
    text = tkcurses.Text(root)
    text.tag_configure("k", **{option: "SteelBlue"})
    with pytest.raises(TclError, match='unknown color name "nocolour"'):
        text.tag_configure("k", **{option: "nocolour"})
    assert text.tag_cget("k", option) == "SteelBlue"


@pytest.mark.parametrize("option", ["fill", "outline"])
def test_a_canvas_item_refuses_one(root, option):
    """Measured on Tk 9.0.2: so does create_rectangle, and itemconfigure."""
    canvas = tkcurses.Canvas(root)
    with pytest.raises(TclError, match='unknown color name "nocolour"'):
        canvas.create_rectangle(0, 0, 4, 4, **{option: "nocolour"})
    item = canvas.create_rectangle(0, 0, 4, 4, **{option: "SteelBlue"})
    with pytest.raises(TclError, match='unknown color name "nocolour"'):
        canvas.itemconfigure(item, **{option: "nocolour"})
    assert canvas.itemcget(item, option) == "SteelBlue"
    canvas.create_rectangle(0, 0, 4, 4, fill="", outline="")


@pytest.mark.tty
def test_a_style_naming_an_unknown_colour_is_drawn_without_it(terminal, tmp_path):
    """Style.configure takes any value, as Tk's does, and Tk draws the
    widget without the colour it cannot find - measured on Tk 9.0.2."""
    term = terminal(cols=40, rows=6)
    term.run_source(
        "import tkcurses as tk\n"
        "from tkcurses import ttk\n"
        "root = tk.Tk()\n"
        "ttk.Style().configure('TLabel', background='nocolour')\n"
        "ttk.Label(root, text='styled').pack()\n"
        "tk.Label(root, text='after it').pack()\n"
        "root.mainloop()\n",
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: t.contains("styled") and t.contains("after it"),
        message="both labels",
    )
