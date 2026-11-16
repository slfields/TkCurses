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

"""What a Text costs as it grows: laying out, painting, and tagging.

Each of these cost time in proportion to the whole text, on every key or
every paint: typing into a Text of 2,000 lines laid all of them out twice
a key (2.6 ms; 26 ms at 20,000), a repaint asked of every cell every range
of every tag (4.6 seconds with 10,000 ranges), and tagging every line of a
file was quadratic (14 seconds for 16,000 ranges). The tests here hold the
shortcuts to what they replaced - the same rows, the same spans, the same
ranges - and to the work they save.
"""

from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from tkcurses import Misc, Text
from tkcurses._core.events import KeyEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack
from tkcurses._core.textbuffer import Index, TextBuffer, _merge, _merged_with


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(window_factory=stub_window, panel_factory=None)
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    return root


def laid_out(root, name="t", **options):
    widget = Text(root, name=name, width=20, height=5, **options)
    widget._allocate(Rect(0, 0, 22, 7))
    widget._map()
    return widget


def fresh_rows(text):
    """The rows worked out from nothing, the cache put back as it was."""
    saved = (text._rows_key, text._rows, text._rows_lines, text._line_rows)
    first = text._line_first
    text._rows_key, text._rows_lines, text._line_rows = None, [], []
    try:
        return list(text._display_lines())
    finally:
        text._rows_key, text._rows, text._rows_lines, text._line_rows = saved
        text._line_first = first


def counting_wraps(text, monkeypatch):
    calls = []
    real = text._wrap_line

    def wrap(number, line, width, mode):
        calls.append(number)
        return real(number, line, width, mode)

    monkeypatch.setattr(text, "_wrap_line", wrap)
    return calls


PIECES = ["a", "bc", "word ", "\n", "\n\n", "\t", "界", "x" * 30, " "]


def random_edit(text, rng):
    lines = int(text.index("end-1c").split(".")[0])
    line = rng.randint(1, lines)
    length = len(text.get(f"{line}.0", f"{line}.end"))
    at = f"{line}.{rng.randint(0, length)}"
    if rng.random() < 0.6:
        text.insert(at, rng.choice(PIECES))
    else:
        text.delete(at, f"{at}+{rng.randint(1, 8)}c")


# ------------------------------------------------------------ display rows


@pytest.mark.parametrize("wrap", ["char", "word", "none"])
@pytest.mark.parametrize("spacing", [0, 1])
def test_the_rows_after_any_edit_are_the_rows_from_nothing(root, wrap, spacing):
    """Kept rows, renumbered rows and re-wrapped rows together are exactly
    what laying the whole text out again gives, edit after edit."""
    text = laid_out(root, wrap=wrap, spacing1=spacing, spacing3=spacing)
    text.insert("1.0", "one\ntwo words here and more\n\nfour\tfive\n" * 4)
    rng = random.Random(f"{wrap}{spacing}")
    for _ in range(300):
        random_edit(text, rng)
        assert text._display_lines() == fresh_rows(text)


def test_the_rows_follow_an_edit_made_in_a_peer(root):
    text = laid_out(root)
    text.insert("1.0", "alpha\nbeta gamma delta epsilon zeta\ngamma\n" * 3)
    text.peer_create(".p")
    other = text.nametowidget(".p")
    rng = random.Random(7)
    for _ in range(100):
        random_edit(other, rng)
        assert text._display_lines() == fresh_rows(text)


def test_the_rows_follow_the_layout(root):
    """Width, wrapping, spacing and tabs are the layout; a change to any of
    them lays every line out again."""
    text = laid_out(root, wrap="char")
    text.insert("1.0", "a\tb long enough to wrap at twenty\n" * 5)
    text._display_lines()
    for change in (
        {"wrap": "word"},
        {"spacing2": 1},
        {"tabs": "4c"},
        {"tabstyle": "wordprocessor"},
    ):
        text.configure(**change)
        assert text._display_lines() == fresh_rows(text), change
    text._allocate(Rect(0, 0, 12, 7))
    assert text._display_lines() == fresh_rows(text)


def test_asking_again_lays_nothing_out(root, monkeypatch):
    text = laid_out(root)
    text.insert("1.0", "line\n" * 50)
    rows = text._display_lines()
    calls = counting_wraps(text, monkeypatch)
    assert text._display_lines() is rows
    assert calls == []


def test_typing_lays_out_the_line_typed_into_and_no_other(root, monkeypatch):
    text = laid_out(root)
    text.insert("1.0", "line\n" * 2000)
    text.mark_set("insert", "1000.2")
    text._display_lines()
    calls = counting_wraps(text, monkeypatch)
    for _ in range(5):
        text._handle(KeyEvent(keysym="x", char="x"))
    assert calls == [1000] * 5


def test_a_new_line_lays_out_only_the_two_halves(root, monkeypatch):
    """The lines after it move down a line, and keep their rows."""
    text = laid_out(root)
    text.insert("1.0", "line\n" * 200)
    text._display_lines()
    calls = counting_wraps(text, monkeypatch)
    text.insert("100.2", "\n")
    rows = text._display_lines()
    assert sorted(set(calls)) == [100, 101]
    assert rows == fresh_rows(text)


def test_margins_are_laid_out_every_time(root, monkeypatch):
    """A margin lives in a tag's ranges and options, which no key follows."""
    text = laid_out(root, wrap="char")
    text.insert("1.0", "a line long enough to wrap\n" * 3)
    text.tag_configure("m", lmargin1=4)
    text.tag_add("m", "1.0", "end")
    text._display_lines()
    calls = counting_wraps(text, monkeypatch)
    text._display_lines()
    assert calls
    text.tag_configure("m", lmargin1=8)
    assert text._display_lines() == fresh_rows(text)


def test_an_embedded_window_growing_lays_its_line_out_again(root):
    """A window's height gives its line rows, and changes with nothing in
    the text or its layout changing: such a text is laid out every time."""
    from tkcurses import Frame

    text = laid_out(root)
    text.insert("1.0", "one\ntwo\nthree\n")
    frame = Frame(text, width=3, height=1)
    text.window_create("2.0", window=frame)
    before = len(text._display_lines())
    frame.configure(height=5)
    after = text._display_lines()
    assert after == fresh_rows(text)
    assert len(after) > before


# ------------------------------------------------------------ tag spans


def spans_by_asking(buffer, name, line, start, stop):
    """What tag_spans answers, the slow way: tag_names of each character."""
    out = []
    for char in range(start, stop):
        if name in buffer.tag_names(Index(line, char)):
            if out and out[-1][1] == char:
                out[-1] = (out[-1][0], char + 1)
            else:
                out.append((char, char + 1))
    return out


@pytest.mark.parametrize("window", [None, (3, 9)])
def test_tag_spans_are_what_tag_names_says_of_each_character(window):
    rng = random.Random(str(window))
    whole = TextBuffer()
    whole.insert(Index(1, 0), "\n".join("0123456789abcdef" for _ in range(12)))
    for _ in range(60):
        line, char = rng.randint(1, 12), rng.randint(0, 16)
        name = rng.choice(["a", "b", "sel"])
        length = rng.randint(1, 40)
        if rng.random() < 0.75:
            whole.tag_add(
                name, Index(line, char), whole.index(f"{line}.{char}+{length}c")
            )
        else:
            whole.tag_remove(
                name, Index(line, char), whole.index(f"{line}.{char}+{length}c")
            )
    buffer = whole
    if window is not None:
        buffer = whole.peer()
        buffer.set_window(*window)
    lines = len(buffer.lines)
    for name in ("a", "b", "sel", "never"):
        for line in range(1, lines + 1):
            for start, stop in ((0, 17), (3, 9), (15, 17)):
                assert buffer.tag_spans(name, line, start, stop) == spans_by_asking(
                    buffer, name, line, start, stop
                ), (name, line, start, stop)


# ------------------------------------------------------------ tag_add


def test_a_range_added_merges_as_merging_them_all_would():
    rng = random.Random(3)
    for _ in range(5000):
        starts = rng.sample(range(40), rng.randint(0, 8))
        ranges = _merge((start, start + rng.randint(1, 4)) for start in starts)
        start = rng.randint(0, 45)
        span = (start, start + rng.randint(1, 6))
        assert _merged_with(ranges, span) == _merge([*ranges, span])


def test_adding_a_range_leaves_the_old_list_alone():
    """Something may hold it: a new list is made, as merging made one."""
    ranges = [(0, 2), (5, 7)]
    _merged_with(ranges, (2, 5))
    assert ranges == [(0, 2), (5, 7)]
