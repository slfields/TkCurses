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

"""ttk.Treeview's Left and Right on rows, and opening and closing.

Replays Tk 9.0.2 measured through tkinter: ``ttk::treeview::Keynav``,
``OpenItem``, ``CloseItem`` and ``Press`` in Tk's treeview.tcl. The tree is
A, with a child A1 that has a child A1x, then the leaves B and C.
"""

from __future__ import annotations

import pytest

import tkcurses as tk
from tkcurses import ttk


@pytest.fixture
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


def build(root, **kw):
    tree = ttk.Treeview(root, **kw)
    tree.place(x=0, y=0, width=30, height=10)
    tree.insert("", "end", "A", text="A")
    tree.insert("A", "end", "A1", text="A1")
    tree.insert("A1", "end", "A1x", text="A1x")
    tree.insert("", "end", "B", text="B")
    tree.insert("", "end", "C", text="C")
    root.update_layout()
    tree.events = []
    for name in ("Open", "Close", "Select"):
        tree.bind(
            f"<<Treeview{name}>>",
            lambda event, name=name: tree.events.append(name),
        )
    return tree


def key(tree, name):
    """One arrow: the focus row, the selection, which rows are open, and
    the events it sent."""
    tree.events.clear()
    tree.event_generate(f"<Key-{name}>")
    opened = tuple(iid for iid in ("A", "A1", "B") if tree.item(iid, "open"))
    return tree.focus(), tree.selection(), opened, tuple(tree.events)


def test_right_opens_the_branch_and_selects_it_every_time(root):
    tree = build(root)
    tree.focus("A")
    assert key(tree, "Right") == ("A", ("A",), ("A",), ("Open", "Select"))
    # Already open: opened again, and announced again.
    assert key(tree, "Right") == ("A", ("A",), ("A",), ("Open", "Select"))
    assert key(tree, "Down") == ("A1", ("A1",), ("A",), ("Select",))
    assert key(tree, "Right") == ("A1", ("A1",), ("A", "A1"), ("Open", "Select"))


def test_right_on_a_leaf_marks_it_open_too(root):
    tree = build(root)
    tree.focus("B")
    assert key(tree, "Right") == ("B", ("B",), ("B",), ("Open", "Select"))


def test_left_closes_an_open_branch_and_does_nothing_more_at_the_top(root):
    tree = build(root)
    tree.focus("A")
    key(tree, "Right")
    assert key(tree, "Left") == ("A", ("A",), (), ("Close", "Select"))
    assert key(tree, "Left") == ("A", ("A",), (), ())


def test_left_on_a_child_goes_to_its_parent(root):
    tree = build(root)
    tree.focus("A")
    key(tree, "Right")
    key(tree, "Down")
    assert key(tree, "Left") == ("A", ("A",), ("A",), ("Select",))


def test_left_on_an_open_leaf_goes_to_the_parent_rather_than_closing(root):
    """Keynav closes only a row that is open AND has children."""
    tree = build(root)
    tree.focus("A")
    key(tree, "Right")
    key(tree, "Down")
    key(tree, "Right")  # A1 opened
    key(tree, "Down")  # A1x
    key(tree, "Right")  # a leaf, marked open
    assert key(tree, "Left") == ("A1", ("A1",), ("A", "A1"), ("Select",))


def test_left_on_a_top_level_leaf_does_nothing(root):
    tree = build(root)
    tree.focus("C")
    assert key(tree, "Left") == ("C", (), (), ())


def test_with_no_row_focused_left_and_right_do_nothing(root):
    tree = build(root)
    assert key(tree, "Right") == ("", (), (), ())
    assert key(tree, "Left") == ("", (), (), ())


def test_browse_selects_as_extended_does(root):
    tree = build(root, selectmode="browse")
    tree.focus("A")
    assert key(tree, "Right") == ("A", ("A",), ("A",), ("Open", "Select"))
    key(tree, "Down")
    assert key(tree, "Left") == ("A", ("A",), ("A",), ("Select",))


def test_none_opens_and_moves_but_selects_nothing(root):
    tree = build(root, selectmode="none")
    tree.focus("A")
    assert key(tree, "Right") == ("A", (), ("A",), ("Open",))
    key(tree, "Down")
    assert key(tree, "Left") == ("A", (), ("A",), ())


def test_an_open_handler_sees_the_row_still_closed_and_a_close_one_closed(root):
    """OpenItem sends the event before it opens the row; CloseItem after it
    closes it. Measured on Tk 9.0.2, by the arrows and by a click alike."""
    tree = build(root)
    seen = []
    tree.bind("<<TreeviewOpen>>", lambda event: seen.append(tree.item("A", "open")))
    tree.bind("<<TreeviewClose>>", lambda event: seen.append(tree.item("A", "open")))
    tree.focus("A")
    tree.event_generate("<Key-Right>")
    tree.event_generate("<Key-Left>")
    assert [bool(value) for value in seen] == [False, False]


def test_a_click_on_the_marker_selects_the_branch_and_opens_it(root):
    tree = build(root)
    x, y, _width, _height = tree.bbox("A", "#0")
    marker = x + tree._marker_column("A") - tree._rows_area().x
    tree.event_generate("<Button-1>", x=marker, y=y)
    assert tree.selection() == ("A",)
    assert tree.focus() == "A"
    assert tree.item("A", "open")
