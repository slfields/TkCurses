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


"""Prior, Next and the view of a Text, held to Tk 9.0.2.

A replay of ``tests/support/page_keys.json``, recorded from real Tk by
``tests/support/record_page_keys.py``: random runs of Prior and Next under
each modifier, the arrows, the program scrolling the view and moving the
cursor, in a Text four and twelve rows tall and one wrapped at a word.
After each step, the cursor, the selection, the first index on screen and
how far the view is scrolled sideways. TkCurses-5co5.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tkcurses import Misc, Text
from tkcurses._core.events import MOD_CTRL, MOD_SHIFT, KeyEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack

DATA = json.loads(
    (Path(__file__).parent / "support" / "page_keys.json").read_text("utf-8")
)
MODIFIERS = {"": 0, "S": MOD_SHIFT, "C": MOD_CTRL, "CS": MOD_CTRL | MOD_SHIFT}
WIDGETS = {"Text4": (4, "none"), "Text12": (12, "none"), "Wrapped4": (4, "word")}
WIDTH = 40
#: Runs where Tk's view remembers having been scrolled by a page. After
#: ``yview scroll 1 pages`` its ``see`` reaches one row further up than the
#: same view reached a line at a time, and stays so until a page back or a
#: ``moveto`` (wrapped, a page back does the same downwards): state below
#: the row the view shows, which a view kept in rows has no room for.
#: Measured, and left. See ARCHITECTURE.md, "Paging a Text".
AFTER_A_PAGE = {
    ("Text4", 100),
    ("Text4", 140),
    ("Text12", 5),
    ("Wrapped4", 48),
    ("Wrapped4", 50),
}


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 30)
    root._mapped = True
    return root


def make(root, kind):
    """The Text a case was recorded in, as big as it was there."""
    height, wrap = WIDGETS[kind]
    text = Text(root, name="t", width=16, height=height, wrap=wrap)
    text._allocate(Rect(0, 0, 18, height + 2))
    text._map()
    text.configure(exportselection=False)
    text.insert("1.0", DATA["text"])
    text.mark_set("insert", "1.0")
    text.yview_moveto(0)
    text.xview_moveto(0)
    text.focus_set()
    return text


def state(text):
    return [
        text.index("insert"),
        [str(i) for i in text.tag_ranges("sel")],
        text.index("@0,0"),
        round(text.xview()[0] * WIDTH),
    ]


def replay(text, steps):
    after = []
    for kind, *args in steps:
        if kind == "k":
            key, mods = args
            text._handle(KeyEvent(keysym=key, char="", modifiers=MODIFIERS[mods]))
        elif kind == "j":
            text.mark_set("insert", args[0])
        elif kind in "yY":
            text.yview_scroll(args[0], "units" if kind == "y" else "pages")
        elif kind in "xX":
            text.xview_scroll(args[0], "units" if kind == "x" else "pages")
        else:
            text.tag_remove("sel", "1.0", "end")
            text.tag_add("sel", *args)
        after.append(state(text))
    return after


CASES = [
    pytest.param(
        kind,
        case,
        id=f"{kind}-{n}",
        marks=[pytest.mark.xfail(strict=True, reason="see, after a page")]
        if (kind, n) in AFTER_A_PAGE
        else [],
    )
    for kind, cases in DATA["cases"].items()
    for n, case in enumerate(cases)
]


@pytest.mark.parametrize(("kind", "case"), CASES)
def test_each_recorded_run_ends_where_tk_ends(root, kind, case):
    text = make(root, kind)
    assert replay(text, case["steps"]) == case["after"], case["steps"]


# ------------------------------------------------------------ measured rules


def sized(root, height=4, width=16, wrap="none"):
    text = Text(root, name="m", width=width, height=height, wrap=wrap)
    text._allocate(Rect(0, 0, width + 2, height + 2))
    text._map()
    return text


#: Rows a page goes in a Text of each height, from Tk 9.0.2 at widths 4 to 30.
PAGE_ROWS = {1: 1, 2: 1, 3: 2, 4: 3, 5: 3, 6: 4, 10: 8}
#: Columns a page goes sideways, by width.
PAGE_COLUMNS = {1: 0, 2: 0, 3: 1, 4: 2, 8: 6, 16: 14, 30: 28}


@pytest.mark.parametrize(("height", "rows"), PAGE_ROWS.items())
def test_a_page_down_goes_as_far_as_tk(root, height, rows):
    text = sized(root, height=height)
    text.insert("1.0", "\n".join("z" * 200 for _ in range(60)))
    text.yview_scroll(1, "pages")
    assert text.index("@0,0") == f"{1 + rows}.0"


@pytest.mark.parametrize(("width", "columns"), PAGE_COLUMNS.items())
def test_a_page_sideways_goes_as_far_as_tk(root, width, columns):
    text = sized(root, height=2, width=width)
    text.insert("1.0", "z" * 200)
    text.xview_scroll(1, "pages")
    assert text._left == columns


#: Where ``see`` leaves the top of a view at line 41 of 100, for a target
#: 1 to 9 lines below it and above it: the top's offset from 41. Measured on
#: Tk 9.0.2; not a Text one line tall, whose centring in pixels leaves its
#: one line half out of view.
SEE = {
    3: ([1, 2, 3, 4, 5, 6, 7, 8, 9], [-1, -2, -3, -6, -7, -8, -9, -10, -11]),
    5: ([1, 2, 3, 5, 6, 7, 8, 9, 10], [-1, -2, -3, -7, -8, -9, -10, -11, -12]),
    6: ([1, 2, 3, 6, 7, 8, 9, 10, 11], [-1, -2, -3, -7, -8, -9, -10, -11, -12]),
    7: ([1, 2, 3, 6, 7, 8, 9, 10, 11], [-1, -2, -3, -8, -9, -10, -11, -12, -13]),
    8: ([1, 2, 3, 7, 8, 9, 10, 11, 12], [-1, -2, -3, -8, -9, -10, -11, -12, -13]),
    13: ([1, 2, 3, 4, 10, 11, 12, 13, 14], [-1, -2, -3, -4, -12, -13, -14, -15, -16]),
    15: ([1, 2, 3, 4, 5, 12, 13, 14, 15], [-1, -2, -3, -4, -5, -14, -15, -16, -17]),
    18: ([1, 2, 3, 4, 5, 6, 15, 16, 17], [-1, -2, -3, -4, -5, -6, -16, -17, -18]),
}


@pytest.mark.parametrize("height", SEE)
def test_see_reaches_and_centres_as_tk_does(root, height):
    text = sized(root, height=height)
    text.insert("1.0", "\n".join(f"line {n:03d}" for n in range(1, 101)))
    down, up = [], []
    for distance in range(1, 10):
        for target, found in ((40 + height + distance, down), (41 - distance, up)):
            text.yview_moveto(40 / 100)
            text.see(f"{target}.0")
            found.append(int(text.index("@0,0").split(".")[0]) - 41)
    assert (down, up) == SEE[height]


#: The same sideways, in a line of 200 from column 50: right, then left.
SEE_SIDEWAYS = {
    9: ([1, 2, 3, *range(8, 18)], [-1, -2, -3, *range(-8, -18, -1)]),
    16: ([1, 2, 3, 4, 5, *range(13, 21)], [-1, -2, -3, -4, -5, *range(-14, -22, -1)]),
}


@pytest.mark.parametrize("width", SEE_SIDEWAYS)
def test_see_reaches_and_centres_sideways_as_tk_does(root, width):
    text = sized(root, height=2, width=width)
    text.insert("1.0", "z" * 200)
    right, left = [], []
    for distance in range(1, 14):
        for target, found in (
            (50 + width - 1 + distance, right),
            (50 - distance, left),
        ):
            text.xview_moveto(50 / 200)
            text.see(f"1.{target}")
            found.append(text._left - 50)
    assert (right, left) == SEE_SIDEWAYS[width]


def test_an_index_outside_the_text_area_is_clamped_into_it(root):
    """Measured on Tk 9.0.2 in 16 x 4, in pixels: ``@41,0`` - in the border
    above the first row - is that row's first visible character, below the
    last row is its last character, right of the area its last column."""
    text = sized(root)
    text.insert(
        "1.0", "\n".join(f"line{n:02d} " + "abcdefghij" * (n % 4) for n in range(1, 31))
    )
    text.yview_moveto(0)
    text.xview_scroll(5, "units")
    found = [text.index("@3,0"), text.index("@3,99"), text.index("@99,1")]
    text.xview_moveto(0)
    # Tk's @41,9999: 41 pixels is the fifth column, and below the area x
    # does not count.
    found += [text.index("@99,1"), text.index("@5,99")]
    assert found == ["1.5", "4.7", "1.17", "1.15", "4.7"]


def test_a_rows_last_character_is_boxed_to_the_right_edge(root):
    """Measured on Tk 9.0.2 in 16 columns, scrolled 24 sideways: 1.3 - the
    newline of ``abc`` - spans from off the left edge to the right one;
    2.40, a newline past the right edge, is a box of no width on it."""
    text = sized(root)
    text.insert("1.0", "abc\n" + "z" * 40 + "\n\n" + "q" * 30)
    text.xview_scroll(24, "units")
    found = [text.bbox(i) for i in ("1.2", "1.3", "3.0", "4.29", "4.30", "2.40")]
    assert found == [
        None,
        (-20, 1, 37, 1),
        (-23, 3, 40, 1),
        (6, 4, 1, 1),
        (7, 4, 10, 1),
        (17, 2, 0, 1),
    ]


def test_spaces_after_a_word_that_fills_a_row_hang_past_the_edge(root):
    """Tk 9.0.2's rows, in 16 columns wrapped at a word, as (first, last)."""
    text = sized(root, height=6, wrap="word")
    text.insert(
        "1.0",
        "aaaaaaaaaaaaaaaa   bbb\nccc dddddddddddd  eee\naaaaaaaaaaaaaaaab cc\nab cdefghijklmnop",
    )
    rows = [
        (f"{line}.{start}", f"{line}.{text._row_last(line, start, stop)}")
        for line, start, stop in text._display_lines()
    ]
    assert rows == [
        ("1.0", "1.18"), ("1.19", "1.22"), ("2.0", "2.17"), ("2.18", "2.21"),
        ("3.0", "3.15"), ("3.16", "3.20"), ("4.0", "4.2"), ("4.3", "4.17"),
    ]  # fmt: skip
    found = [text.bbox(i) for i in ("1.16", "1.17", "1.18", "1.19")]
    assert found == [(17, 1, 0, 1), (18, 1, -1, 1), (17, 1, 0, 1), (1, 2, 1, 1)]


def test_a_wrapped_text_does_not_scroll_sideways(root):
    text = sized(root, wrap="word")
    text.insert("1.0", "word " * 40)
    text.xview_scroll(1, "pages")
    text.xview_scroll(5, "units")
    assert text._left == 0


def test_neither_a_mark_nor_an_insert_moves_the_view(root):
    """Measured on Tk 9.0.2: the view stays at the top through both."""
    text = sized(root)
    text.insert("1.0", "\n".join(f"line {n}" for n in range(40)))
    text.mark_set("insert", "30.0")
    assert text.index("@0,0") == "1.0"


def test_typing_brings_the_cursor_into_view(root):
    text = sized(root)
    text.insert("1.0", "\n".join(f"line {n}" for n in range(40)))
    text.mark_set("insert", "30.0")
    text.focus_set()
    text._handle(KeyEvent(keysym="x", char="x"))
    assert text.bbox("insert") is not None


@pytest.mark.parametrize(
    ("mods", "expected"), [(MOD_CTRL, 14), (MOD_CTRL | MOD_SHIFT, 14)]
)
def test_control_next_pages_sideways_and_leaves_the_cursor(root, mods, expected):
    """text.tcl's Control-Next, which Control-Shift-Next is too: Shift-Next
    and Control-Next match it equally, and the one registered last wins."""
    text = sized(root)
    text.insert("1.0", "z" * 60 + "\n" + "y" * 60)
    text.mark_set("insert", "2.3")
    text.focus_set()
    text._handle(KeyEvent(keysym="Next", char="", modifiers=mods))
    assert (text.index("insert"), text._left, list(text.tag_ranges("sel"))) == (
        "2.3",
        expected,
        [],
    )


def test_next_also_reaches_all(root):
    """None of text.tcl's bindings breaks. Measured on Tk 9.0.2."""
    seen = []
    root.bind_all("<Key>", lambda event: seen.append(event.keysym))
    text = sized(root)
    text.focus_set()
    for mods in (0, MOD_CTRL):
        text._handle(KeyEvent(keysym="Next", char="", modifiers=mods))
    assert seen == ["Next", "Next"]


def test_a_cursor_off_screen_pages_to_the_top_rows_start(root):
    """Measured on Tk 9.0.2: 9.5 out of view below, Next puts the view at
    4.0 and the cursor there; scrolled 5 sideways, at 4.5."""
    text = sized(root)
    text.insert(
        "1.0", "\n".join(f"line{n:02d} " + "abcdefghij" * (n % 4) for n in range(1, 21))
    )
    text.yview_moveto(0)
    text.mark_set("insert", "9.5")
    text.focus_set()
    text._handle(KeyEvent(keysym="Next", char=""))
    found = [text.index("insert")]
    text.yview_moveto(0)
    text.mark_set("insert", "9.5")
    text.xview_scroll(5, "units")
    text._handle(KeyEvent(keysym="Next", char=""))
    found.append(text.index("insert"))
    assert found == ["4.0", "4.5"]
