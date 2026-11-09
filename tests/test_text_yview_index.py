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

"""Tk's older form of ``yview``: an index, a line number, or ``-pickplace``.

Every expectation was measured on Tk 9.0.2 through tkinter, on a Text 20
columns by 4 rows holding 29 lines, the sixth of them wrapped once.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from tkcurses import Misc, TclError, Text
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


@pytest.fixture
def text():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 30)
    root._mapped = True
    widget = Text(root, width=20, height=4)
    widget._allocate(Rect(0, 0, 22, 6))
    widget._map()
    widget.insert(
        "1.0",
        "\n".join(f"line {n} " + "x" * (30 if n == 6 else 0) for n in range(1, 30)),
    )
    return widget


@pytest.mark.parametrize(
    ("where", "top"),
    [
        ("0", "1.0"),
        ("-1", "1.0"),
        ("100", "26.0"),
        ("3", "4.0"),
        (3, "4.0"),
        (" 3", "4.0"),
        ("0x3", "4.0"),
        ("2.5", "2.0"),
        ("end", "26.0"),
        ("6.25", "6.20"),
    ],
)
def test_one_index_or_line_number_goes_to_the_top(text, where, top):
    assert text.yview(where) is None
    assert text.index("@0,0") == top


@pytest.mark.parametrize(
    ("args", "top"),
    [
        (("-pick", "20.0"), "18.0"),
        (("-p", "10"), "11.0"),
        (("-pickplace", "6.25"), "4.0"),
        (("-pickplace", 10), "11.0"),
    ],
)
def test_pickplace_brings_it_into_view(text, args, top):
    """A whole number still goes to the top: Tk tries it before the index."""
    text.yview(*args)
    assert text.index("@0,0") == top


def test_pickplace_moves_only_as_far_as_it_must(text):
    """Measured one after another, each from where the last left the view."""
    text.yview("-pickplace", "6.25")
    assert text.index("@0,0") == "4.0"
    text.yview("-pickplace", "8.0")
    assert text.index("@0,0") == "6.0"
    text.yview("-pickplace", "3.0")
    assert text.index("@0,0") == "3.0"
    text.yview_pickplace("12")
    assert text.index("@0,0") == "13.0"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("moveto",), 'bad text index "moveto"'),
        (("scroll",), 'bad text index "scroll"'),
        (("-x",), 'bad text index "-x"'),
        (("-",), 'bad text index "-"'),
        (("nosuch",), 'bad text index "nosuch"'),
        (("-pickplace", "nosuch"), 'bad text index "nosuch"'),
        (("-pickplace",), "yview -pickplace lineNum|index"),
        (("-pickplace", "1", "2"), "yview -pickplace lineNum|index"),
        (("1.0", "x"), 'bad option "1.0": must be moveto or scroll'),
    ],
)
def test_the_refusals_are_tks(text, args, message):
    with pytest.raises(TclError, match=re.escape(message)):
        text.yview(*args)


def test_a_tall_lines_top_goes_to_the_top(text):
    """Not only its text row: the blank rows a tall embedded window gives
    its line come too."""
    from tkcurses import Frame

    text.window_create("5.0", window=Frame(text, width=3, height=3))
    text.yview("5.0")
    rows = text._display_lines()
    assert text.index("@0,0") == "5.0"
    assert rows[text._top][0] == -5
    assert rows[text._top - 1][0] == 4
