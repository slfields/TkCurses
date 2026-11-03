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

"""A Text's line spacing and its undo depth. TkCurses-gm66.8.

Spacing is Tk's in pixels and here in rows: ``spacing1`` blank rows above
each line, ``spacing2`` between the rows of a wrapped one, ``spacing3`` below
each. ``maxundo`` caps the undo stack in groups. Each rule below was measured
on Tk 9.0.2 and is cited where it is asserted.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Misc, TclError, Text
from tkcurses._core.events import KeyEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 30)
    root._mapped = True
    return root


def laid_out(root, width=10, height=20, **kw):
    """A Text with ``width`` by ``height`` cells of text area."""
    widget = Text(root, width=width, height=height, **kw)
    widget._allocate(Rect(0, 0, width + 2, height + 2))
    widget._map()
    return widget


def row_of(widget, index):
    box = widget.bbox(index)
    assert box is not None, index
    return box[1] - 1  # inside the one-cell border


def undo_count(widget):
    n = 0
    while True:
        try:
            widget.edit_undo()
        except TclError:
            return n
        n += 1


# --------------------------------------------------------------- the options


@pytest.mark.parametrize("name", ["spacing1", "spacing2", "spacing3", "maxundo"])
def test_each_defaults_to_zero(root, name):
    assert Text(root).cget(name) == 0


@pytest.mark.parametrize("name", ["spacing1", "spacing2", "spacing3"])
def test_a_negative_spacing_is_stored_as_zero(root, name):
    widget = Text(root, **{name: -3})
    assert widget.cget(name) == 0


@pytest.mark.parametrize("name", ["spacing1", "spacing2", "spacing3"])
def test_a_spacing_must_be_a_distance(root, name):
    with pytest.raises(TclError, match='expected screen distance but got "x"'):
        Text(root, **{name: "x"})


@pytest.mark.parametrize("value", ["x", 2.5, "2.5"])
def test_maxundo_must_be_an_integer(root, value):
    with pytest.raises(TclError, match="expected integer"):
        Text(root, maxundo=value)


def test_maxundo_takes_a_negative_and_a_padded_integer(root):
    widget = Text(root, maxundo=-1)
    assert widget.cget("maxundo") == -1
    widget.configure(maxundo=" 3 ")
    assert widget.cget("maxundo") == 3


# ------------------------------------------------------------------ spacing


def test_no_spacing_puts_lines_on_consecutive_rows(root):
    widget = laid_out(root)
    widget.insert("1.0", "one\ntwo")
    assert [row_of(widget, i) for i in ("1.0", "2.0")] == [0, 1]


def test_spacing1_puts_blank_rows_above_every_line(root):
    widget = laid_out(root, spacing1=2)
    widget.insert("1.0", "one\ntwo\nthree")
    assert [row_of(widget, i) for i in ("1.0", "2.0", "3.0")] == [2, 5, 8]


def test_spacing3_puts_blank_rows_below_every_line(root):
    widget = laid_out(root, spacing3=1)
    widget.insert("1.0", "one\ntwo\nthree")
    assert [row_of(widget, i) for i in ("1.0", "2.0", "3.0")] == [0, 2, 4]


def test_spacing2_only_separates_the_rows_of_a_wrapped_line(root):
    widget = laid_out(root, width=5, wrap="char", spacing2=1)
    widget.insert("1.0", "abcdefghij\nxy")
    assert row_of(widget, "1.0") == 0
    assert row_of(widget, "1.5") == 2, "one blank row inside the line"
    assert row_of(widget, "2.0") == 3, "and none after it"


def test_spacing2_is_split_with_the_larger_half_above(root):
    """Measured: spacing2 of 3 pixels put 1 under the first row and 2 over the
    second - dlineinfo heights 25 and 28 around a 19-pixel font."""
    widget = laid_out(root, width=5, wrap="char", spacing2=3)
    widget.insert("1.0", "abcdefghij")
    rows = widget._display_lines()
    assert [line for line, _, _ in rows] == [1, -1, -1, -1, 1]
    assert [start for _, start, _ in rows] == [0, 0, 5, 5, 5]


def test_all_three_together_in_order(root):
    widget = laid_out(root, width=5, wrap="char", spacing1=1, spacing2=1, spacing3=2)
    widget.insert("1.0", "abcdefgh\nxy")
    assert [line for line, _, _ in widget._display_lines()] == [
        -1, 1, -1, 1, -1, -1, -2, 2, -2, -2,
    ]  # fmt: skip


def test_a_click_on_spacing_lands_on_the_line_it_belongs_to(root):
    """Measured: spacing1 and spacing3 of 16 pixels, and every y from 2 to 40
    answered 1.0 - the spacing above AND below line 1."""
    widget = laid_out(root, spacing1=2, spacing3=2)
    widget.insert("1.0", "abc\nxy")
    for y in range(1, 6):
        assert str(widget._index_at_cell(1, y)) == "1.0", y
    assert str(widget._index_at_cell(1, 6)) == "2.0"


def test_a_click_on_spacing2_lands_on_the_row_below_it(root):
    widget = laid_out(root, width=5, wrap="char", spacing2=1)
    widget.insert("1.0", "abcdefghij")
    assert str(widget._index_at_cell(1 + 2, 2)) == "1.7"


def test_bbox_and_a_click_agree_with_spacing(root):
    widget = laid_out(root, width=5, wrap="char", spacing1=1, spacing2=2, spacing3=1)
    widget.insert("1.0", "abcdefghij\nxyz")
    for spec in ("1.0", "1.3", "1.5", "1.9", "2.0", "2.2"):
        x, y, _, _ = widget.bbox(spec)
        assert str(widget._index_at_cell(x, y)) == spec


def test_down_skips_the_spacing(root):
    widget = laid_out(root, spacing1=1, spacing3=1)
    widget.insert("1.0", "abc\nxyz\nlast")
    widget.mark_set("insert", "1.2")
    widget._handle(KeyEvent(keysym="Down"))
    assert widget.index("insert") == "2.2"
    widget._handle(KeyEvent(keysym="Up"))
    assert widget.index("insert") == "1.2"


def test_end_of_a_line_with_spacing_below_is_on_that_line(root):
    """The cursor at the end of the text is on the last line, not in the
    blank rows ``spacing3`` puts after it."""
    widget = laid_out(root, spacing3=2)
    widget.insert("1.0", "abc")
    assert row_of(widget, "end") == 0
    assert row_of(widget, "1.end") == 0


def test_spacing_counts_in_the_scrolled_height(root):
    widget = laid_out(root, height=4, spacing1=1)
    widget.insert("1.0", "1\n2\n3\n4")
    widget.yview("moveto", 0)
    assert widget.yview() == (0.0, 0.5), "eight rows, four shown"
    widget.see("4.0")
    assert row_of(widget, "4.0") == 3


def test_changing_spacing_moves_the_text(root):
    widget = laid_out(root)
    widget.insert("1.0", "one\ntwo")
    widget.configure(spacing1=1)
    assert row_of(widget, "2.0") == 3
    widget.configure(spacing1=0)
    assert row_of(widget, "2.0") == 1


def test_nothing_is_drawn_on_a_spacing_row(root):
    widget = laid_out(root, spacing1=1)
    widget.insert("1.0", "abc")
    drawn = []
    original = widget._draw_tagged
    widget._draw_tagged = lambda *a, **k: drawn.append(a)
    try:
        widget._draw_row(None, None, widget._text_area(), 0, (-1, 0, 3), ["abc"], 0)
    finally:
        widget._draw_tagged = original
    assert drawn == []


# --------------------------------------------------------------------- undo


def make_undoable(root, groups, **kw):
    widget = Text(root, undo=True, autoseparators=False, **kw)
    for word in groups:
        widget.insert("end", word)
        widget.edit_separator()
    return widget


def test_maxundo_keeps_only_the_newest_groups(root):
    """Measured: maxundo 2, four groups, two undo and the text is "ab"."""
    widget = make_undoable(root, "abcd", maxundo=2)
    assert undo_count(widget) == 2
    assert widget.get("1.0", "end") == "ab\n"


def test_what_maxundo_undid_can_all_be_redone(root):
    widget = make_undoable(root, "abcd", maxundo=2)
    undo_count(widget)
    widget.edit_redo()
    widget.edit_redo()
    assert widget.get("1.0", "end") == "abcd\n"


@pytest.mark.parametrize("value", [0, -1])
def test_zero_or_below_keeps_everything(root, value):
    widget = make_undoable(root, "x" * 50, maxundo=value)
    assert undo_count(widget) == 50


def test_lowering_maxundo_drops_the_oldest_at_once(root):
    """Measured: five groups, then maxundo 2, and two undo."""
    widget = make_undoable(root, "abcde")
    widget.configure(maxundo=2)
    assert undo_count(widget) == 2
    assert widget.get("1.0", "end") == "abc\n"


def test_a_group_counts_once_however_many_edits_it_holds(root):
    widget = Text(root, undo=True, autoseparators=False, maxundo=1)
    widget.insert("end", "a")
    widget.insert("end", "b")
    widget.edit_separator()
    assert undo_count(widget) == 1
    assert widget.get("1.0", "end") == "\n"


def test_the_cap_is_held_as_groups_keep_coming(root):
    widget = make_undoable(root, "abcdefgh", maxundo=3)
    assert widget._buffer.undo_depth == 3
