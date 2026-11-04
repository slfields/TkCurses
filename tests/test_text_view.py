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


"""Where a Text's view goes when its text changes, held to Tk 9.0.2.

A replay of ``tests/support/text_view.json``, recorded from real Tk by
``tests/support/record_text_view.py``: a Text scrolled, then edited by
itself and by a peer, and scrolled again, with the first index on screen
and ``xview`` after every step. Tk keeps its view as an index, so the text
it shows stays put through an edit above it (TkCurses-ntu4), and bounds how
far it scrolls sideways by the rows on screen (TkCurses-8tjr).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tkcurses import Misc, Text
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack

DATA = json.loads(
    (Path(__file__).parent / "support" / "text_view.json").read_text("utf-8")
)
WIDGETS = {"Text": "none", "Wrapped": "word"}
#: The first probe's text: forty lines, a third of them wider than the view.
LINES = "\n".join(f"line {k:02d} " + "abcdefghij" * (k % 3) for k in range(1, 41))


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 30)
    root._mapped = True
    return root


def make(root, wrap, body, name="t"):
    """A Text as big as the recorded one: 16 columns, 4 rows."""
    text = Text(root, name=name, width=16, height=4, wrap=wrap)
    text._allocate(Rect(0, 0, 18, 6))
    text._map()
    text.insert("1.0", body)
    text.yview_moveto(0)
    text.xview_moveto(0)
    return text


def top(text):
    return text.index("@0,0"), text.get("@0,0", "@0,0 +7c")


def scroll_to(text, lines):
    """``yview N``, which puts line N + 1 at the top: N units unwrapped."""
    text.yview_moveto(0)
    text.yview_scroll(lines, "units")


CASES = [
    (wrap, n) for wrap in WIDGETS for n in range(len(DATA["cases"][wrap]))
]  # fmt: skip


@pytest.mark.parametrize(("kind", "n"), CASES, ids=[f"{k}-{n}" for k, n in CASES])
def test_each_recorded_run_ends_where_tk_ends(root, kind, n):
    case = DATA["cases"][kind][n]
    text = make(root, WIDGETS[kind], case["text"])
    text.peer_create(".p")
    peer = text.nametowidget(".p")
    after = []
    for step, *args in case["steps"]:
        if step == "y":
            scroll_to(text, args[0])
        elif step == "x":
            text.xview_scroll(args[0], "units")
        elif step == "m":
            text.xview_moveto(args[0])
        elif step in "ip":
            (text if step == "i" else peer).insert(args[0], args[1])
        else:
            (text if step == "d" else peer).delete(args[0], args[1])
        after.append([text.index("@0,0"), [round(f, 4) for f in text.xview()]])
    assert after == case["after"]


ABOVE_AND_ACROSS = [
    ("insert 3 lines at 1.0", "insert", ("1.0", "a\nb\nc\n"), ("14.0", "line 11")),
    ("insert at the top", "insert", ("11.0", "NEW\n"), ("11.0", "NEW\nlin")),
    ("insert in the top line", "insert", ("11.3", "QQ\n"), ("11.0", "linQQ\ne")),
    ("insert at the end above", "insert", ("10.end", "\nX"), ("12.0", "line 11")),
    ("insert at the top, no newline", "insert", ("11.0", "ZZ"), ("11.0", "ZZline ")),
    ("delete above", "delete", ("1.0", "4.0"), ("8.0", "line 11")),
    ("delete across the top", "delete", ("9.0", "12.0"), ("9.0", "line 12")),
    ("delete the top line", "delete", ("11.0", "12.0"), ("11.0", "line 12")),
    ("delete into the top line", "delete", ("10.3", "11.4"), ("10.0", "lin 11 ")),
    ("delete in the top line", "delete", ("11.2", "11.5"), ("11.0", "li11 ab")),
    ("delete it all", "delete", ("1.0", "end"), ("1.0", "\n")),
    ("delete below", "delete", ("20.0", "end"), ("11.0", "line 11")),
    ("delete all but the view", "delete", ("5.0", "end"), ("1.0", "line 01")),
]


@pytest.mark.parametrize(
    ("change", "args", "shown"),
    [case[1:] for case in ABOVE_AND_ACROSS],
    ids=[case[0] for case in ABOVE_AND_ACROSS],
)
def test_an_edit_leaves_the_view_on_the_text_it_showed(root, change, args, shown):
    """Measured on Tk 9.0.2, the view at 11.0 of forty lines."""
    text = make(root, "none", LINES)
    scroll_to(text, 10)
    getattr(text, change)(*args)
    assert top(text) == shown


def test_an_edit_through_a_peer_leaves_the_view_too(root):
    text = make(root, "none", LINES)
    scroll_to(text, 10)
    text.peer_create(".p")
    text.nametowidget(".p").insert("1.0", "a\nb\nc\n")
    assert top(text) == ("14.0", "line 11")


def test_a_wrapped_view_keeps_the_row_it_showed(root):
    """Measured on Tk 9.0.2: the view at 14.8, the second row of its line,
    follows that row as text goes in ahead of it, and a deletion that ends
    on its line before it keeps the deletion's END line, as Tk's does - a
    line further down than where the text went."""
    text = make(root, "word", LINES)
    while text.index("@0,0") != "14.8":
        text.yview_scroll(1, "units")
    assert top(text) == ("14.8", "abcdefg")
    text.insert("14.0", "XXXX")
    assert top(text) == ("14.12", "abcdefg")
    text.delete("14.0", "14.4")
    assert top(text) == ("14.8", "abcdefg")
    text.insert("14.0", "\n")
    assert top(text) == ("15.8", "abcdefg")
    text.delete("14.0", "15.0")
    assert top(text) == ("15.0", "line 15")


def test_resizing_or_rewrapping_keeps_the_top_line(root):
    text = make(root, "none", LINES)
    scroll_to(text, 10)
    text.configure(width=10)
    text._allocate(Rect(0, 0, 12, 6))
    assert top(text) == ("11.0", "line 11")
    text.configure(wrap="char")
    assert top(text) == ("11.0", "line 11")


def test_a_spacing_row_at_the_top_stays_at_the_top(root):
    """Ours alone: a row of ``spacing1`` is a row here and part of its
    line's height in Tk, whose units scroll never stops inside one. A view
    that starts on the second of two such rows starts on it still after an
    edit above, as the text Tk shows stays where it is."""
    text = make(root, "none", LINES)
    text.configure(spacing1=2)
    text.yview_scroll(3 * 12 + 1, "units")
    rows = text._display_lines()
    assert (rows[text._top - 1][0], rows[text._top][0]) == (-13, -13)
    text.insert("1.0", "new\n")
    rows = text._display_lines()
    assert (rows[text._top - 1][0], rows[text._top][0]) == (-14, -14)


def test_margins_or_a_tab_above_leave_the_view_on_its_line(root):
    """Measured on Tk 9.0.2, wrapped at a word with the view at 13.0: a
    margin of four over lines 1 to 11 wraps them onto more rows, and a tab
    put into line 2, and the view is at 13.0 after each."""
    text = make(root, "word", LINES)
    while text.index("@0,0") != "13.0":
        text.yview_scroll(1, "units")
    text.tag_configure("m", lmargin1=4, lmargin2=4)
    text.tag_add("m", "1.0", "12.0")
    assert top(text) == ("13.0", "line 13")
    text.configure(tabs=(8,))
    text.insert("2.0", "\t")
    assert top(text) == ("13.0", "line 13")


def above(text):
    """How many display rows come before line 13."""
    return text._row_of(text._buffer.index("13.0"))


def test_more_margins_leave_the_view_on_its_line(root):
    """Measured on Tk 9.0.2, wrapped at a word with the view at 13.0 and
    line 30 already margined, so adding more changes nothing but the rows:
    a margin of eight over lines 1 to 11 takes the rows above from 24 to
    32, and the view stays at 13.0."""
    text = make(root, "word", LINES)
    text.tag_configure("m", lmargin1=8, lmargin2=8)
    text.tag_add("m", "30.0", "31.0")
    while text.index("@0,0") != "13.0":
        text.yview_scroll(1, "units")
    assert above(text) == 24
    text.tag_add("m", "1.0", "12.0")
    assert above(text) == 32
    assert top(text) == ("13.0", "line 13")


@pytest.mark.parametrize(("change", "rows"), [("tabs", 29), ("width", 38)])
def test_wider_tabs_or_a_narrower_text_leave_it_too(root, change, rows):
    """Measured on Tk 9.0.2, wrapped at a word with the view at 13.0 and a
    line of tabs above it: tabs thirty wide take the rows above from 27 to
    29, and the Text seven columns wide to 38. The view stays at 13.0."""
    text = make(root, "word", LINES)
    text.insert("2.0", "a\tb\tc\td\te\tf ")
    while text.index("@0,0") != "13.0":
        text.yview_scroll(1, "units")
    assert above(text) == 27
    if change == "tabs":
        text.configure(tabs=(30,))
    else:
        text.configure(width=7)
        text._allocate(Rect(0, 0, 9, 6))
    assert above(text) == rows
    assert top(text) == ("13.0", "line 13")


def test_a_view_pulled_up_to_fill_stays_up(root):
    """A deletion below a view at the end of the text pulls it up, and it
    stays there when text comes back - Tk resets its top, not just what it
    draws. Measured on Tk 9.0.2: from 31.0, deleting 33.0 to the end (which
    takes line 32's newline too) shows 29.0, and adding lines keeps it."""
    text = make(root, "none", LINES)
    scroll_to(text, 30)
    assert top(text)[0] == "31.0"
    text.delete("33.0", "end")
    assert top(text) == ("29.0", "line 29")
    text.insert("end", "\nmore\nand more")
    assert top(text) == ("29.0", "line 29")


#: One Text, 16 by 4, over ten short lines, one of 60, one of 30 and ten
#: more short ones: each step and Tk 9.0.2's xview, and ``@0,0`` after it -
#: the top row's first character in view, so a column into a short line is
#: its end.
SIDEWAYS = [
    (("y", 8), (0.0, 0.2667), "9.0"),
    (("x", 40), (0.6667, 0.9333), "9.5"),
    (("y", 11), (0.4667, 1.0), "12.14"),
    (("y", 13), (0.0, 1.0), "14.0"),
    (("x", -5), (0.0, 1.0), "14.0"),
    (("m", 0.5), (0.0, 1.0), "14.0"),
    (("y", 8), (0.0, 0.2667), "9.0"),
    (("m", 0.0), (0.0, 0.2667), "9.0"),
    (("y", 11), (0.0, 0.5333), "12.0"),
    (("m", 1.0), (0.4667, 1.0), "12.14"),
    (("y", 10), (0.2333, 0.5), "11.14"),
]


def test_sideways_the_view_goes_as_far_as_the_rows_it_shows(root):
    lines = ["short"] * 10 + ["L" * 60, "M" * 30] + ["short"] * 10
    text = make(root, "none", "\n".join(lines))
    for (step, value), fractions, shown in SIDEWAYS:
        if step == "y":
            # Straight there, as ``yview N`` goes: by way of the top, whose
            # rows are all short, the view would come back at column 0.
            text.yview_scroll(value - text._top, "units")
        elif step == "x":
            text.xview_scroll(value, "units")
        else:
            text.xview_moveto(value)
        assert (tuple(round(f, 4) for f in text.xview()), text.index("@0,0")) == (
            fractions,
            shown,
        ), (step, value)


def test_see_goes_sideways_as_far_as_the_rows_it_comes_to(root):
    lines = ["short"] * 10 + ["L" * 60, "M" * 30] + ["short"] * 10
    text = make(root, "none", "\n".join(lines))
    text.see("11.50")
    assert (tuple(round(f, 4) for f in text.xview()), top(text)[0]) == (
        (0.7, 0.9667),
        "9.5",
    )


def test_a_wrapped_text_is_all_in_view_sideways(root):
    text = make(root, "word", "a few words that hang a space past the edge")
    assert text.xview() == (0.0, 1.0)


def test_wrapping_puts_the_sideways_scroll_back_to_the_start(root):
    """Measured on Tk 9.0.2: scrolled ten across line 1, wrapped, and
    unwrapped again, the view is at 1.0 - not back at 1.10."""
    text = make(root, "none", LINES)
    text.xview_scroll(10, "units")
    assert text.index("@0,0") == "1.10"
    text.configure(wrap="word")
    assert (text.index("@0,0"), text.xview()) == ("1.0", (0.0, 1.0))
    text.configure(wrap="none")
    assert (text.index("@0,0"), round(text.xview()[1], 4)) == ("1.0", 0.5714)


def test_a_wrapped_row_past_the_edge_does_not_scroll_it(root):
    """Spaces hanging past the edge make a row wider than the view, and
    still it does not scroll: measured on Tk 9.0.2, 1.10 unwrapped is 1.0
    wrapped at a word, over a word of sixteen and four spaces."""
    text = make(root, "none", "abcdefghijklmnop    qrstuvwxyz and more text here")
    text.xview_scroll(10, "units")
    assert text.index("@0,0") == "1.10"
    text.configure(wrap="word")
    assert (text.index("@0,0"), text.xview()) == ("1.0", (0.0, 1.0))


def test_a_margin_counts_in_the_widest_row(root):
    """Measured on Tk 9.0.2: a margin of four on line 2, 28 long, makes the
    widest row in view 32 and the view half of it."""
    text = make(root, "none", LINES)
    text.tag_configure("m", lmargin1=4)
    text.tag_add("m", "2.0", "3.0")
    assert text.xview() == (0.0, 0.5)
