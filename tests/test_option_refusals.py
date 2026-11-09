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

"""Option values Tk refuses, refused here too, and the forms it takes.

Each case was measured on Tk 9.0.2 through tkinter (TkCurses-m595). The
full sweep against real Tk is tests/test_option_values_against_tk.py, which
needs a display; these are the edges it does not try.
"""

from __future__ import annotations

import pytest

import tkcurses
from tkcurses import Misc, TclError, ttk


@pytest.fixture
def root():
    return Misc()


#: (class, option, value, what Tk reads back)
TAKEN = [
    (tkcurses.Canvas, "state", "dis", "disabled"),
    (tkcurses.Canvas, "state", "", ""),
    (tkcurses.Canvas, "state", "n", "normal"),
    (tkcurses.Scrollbar, "orient", "", "horizontal"),
    (tkcurses.Scrollbar, "orient", "v", "vertical"),
    (tkcurses.Scale, "orient", "h", "horizontal"),
    (tkcurses.Label, "underline", "", ""),
    (tkcurses.Label, "underline", "end", "end"),
    (tkcurses.Label, "underline", "end-1", "end-1"),
    (tkcurses.Label, "underline", "3+1", 4),
    (tkcurses.Label, "underline", "+2", 2),
    (tkcurses.Label, "underline", " 3", 3),
    (tkcurses.Label, "underline", "-1", ""),
    (tkcurses.Label, "borderwidth", "-3", 0),
    (tkcurses.Label, "anchor", "c", "center"),
    (tkcurses.Label, "relief", "f", "flat"),
    (tkcurses.Button, "compound", "t", "top"),
    (tkcurses.Button, "state", "a", "active"),
    (tkcurses.Entry, "state", "r", "readonly"),
    (tkcurses.Listbox, "state", "d", "disabled"),
    (tkcurses.Listbox, "activestyle", "d", "dotbox"),
    (tkcurses.Text, "wrap", "c", "char"),
    (tkcurses.Text, "tabstyle", "t", "tabular"),
    (tkcurses.Menubutton, "direction", "f", "flush"),
    (tkcurses.LabelFrame, "labelanchor", "e", "e"),
    (tkcurses.Message, "aspect", "0x10", 16),
    (tkcurses.Scale, "bigincrement", "1e2", 100.0),
    (ttk.Labelframe, "labelanchor", "nsew", "nsew"),
    (ttk.Labelframe, "labelanchor", "nn", "nn"),
    (ttk.Frame, "padding", "1 2 3 4", "1 2 3 4"),
    (ttk.Frame, "padding", "", ""),
    (ttk.Frame, "relief", "", ""),
    (ttk.Frame, "borderwidth", "", ""),
    (ttk.Button, "compound", "", ""),
    (ttk.Button, "compound", "c", "center"),
    (ttk.Progressbar, "anchor", "", ""),
    (ttk.Progressbar, "wraplength", "", ""),
    (ttk.Treeview, "selectmode", "b", "browse"),
]


@pytest.mark.parametrize(
    "cls, option, value, expected",
    TAKEN,
    ids=[f"{c.__name__}-{o}-{v!r}" for c, o, v, _ in TAKEN],
)
def test_tk_takes_it_and_so_do_we(root, cls, option, value, expected):
    assert cls(root, **{option: value}).cget(option) == expected


#: (class, option, value, Tk's message)
REFUSED = [
    (
        tkcurses.Canvas,
        "state",
        "hidden",
        'bad state value "hidden": must be normal or disabled',
    ),
    (
        tkcurses.Canvas,
        "state",
        "NORMAL",
        'bad state value "NORMAL": must be normal or disabled',
    ),
    (
        tkcurses.Scrollbar,
        "orient",
        "x",
        'bad orientation "x": must be vertical or horizontal',
    ),
    (
        tkcurses.Scale,
        "orient",
        "",
        'ambiguous orient "": must be horizontal or vertical',
    ),
    (
        tkcurses.Label,
        "underline",
        "end+",
        'bad index "end+": must be integer?[+-]integer?, end?[+-]integer?, or ""',
    ),
    (tkcurses.Label, "borderwidth", "", 'expected screen distance but got ""'),
    (
        tkcurses.Label,
        "anchor",
        "",
        'ambiguous anchor "": must be n, ne, e, se, s, sw, w, nw, or center',
    ),
    (
        tkcurses.Label,
        "anchor",
        "N",
        'bad anchor "N": must be n, ne, e, se, s, sw, w, nw, or center',
    ),
    (
        tkcurses.Label,
        "relief",
        "s",
        'ambiguous relief "s": must be flat, groove, raised, ridge, solid, or sunken',
    ),
    (
        tkcurses.Button,
        "compound",
        "",
        'ambiguous compound "": must be bottom, center, left, none, right, or top',
    ),
    (tkcurses.Listbox, "state", "", 'ambiguous state "": must be disabled or normal'),
    (tkcurses.Message, "aspect", "2.0", 'expected integer but got "2.0"'),
    (tkcurses.Scale, "bigincrement", "nan", "floating point value is Not a Number"),
    (tkcurses.Canvas, "closeenough", "", 'expected floating-point number but got ""'),
    (ttk.Labelframe, "labelanchor", "", "Bad label anchor specification "),
    (ttk.Labelframe, "labelanchor", "N", "Bad label anchor specification N"),
    (ttk.Frame, "padding", "1 2 3 4 5", "Wrong #elements in padding spec"),
    (ttk.Frame, "padding", "2.5 x", 'expected screen distance but got "x"'),
    (
        ttk.Button,
        "compound",
        "t",
        'ambiguous compound "t": must be none, text, image, center, top, bottom, left, right, or ""',
    ),
    (ttk.Progressbar, "maximum", "", 'expected floating-point number but got ""'),
    (
        ttk.Label,
        "anchor",
        "",
        'ambiguous anchor "": must be n, ne, e, se, s, sw, w, nw, or center',
    ),
]


@pytest.mark.parametrize(
    "cls, option, value, message",
    REFUSED,
    ids=[f"{c.__name__}-{o}-{v!r}" for c, o, v, _ in REFUSED],
)
def test_tk_refuses_it_and_so_do_we(root, cls, option, value, message):
    with pytest.raises(TclError) as caught:
        cls(root, **{option: value})
    assert str(caught.value) == message


def test_a_label_with_an_end_underline_draws(root):
    """Tk keeps "end" as written; drawing has to read it."""
    label = tkcurses.Label(root, text="Quit", underline="end")
    assert tkcurses._underline_position(label.cget("underline"), "Quit") == 3
