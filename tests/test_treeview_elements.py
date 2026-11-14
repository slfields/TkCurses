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

"""Treeview's ``identify_element``, against real tkinter.

Tk answers in pixels and this in cells, so what is compared is the order of
the elements across each row - indent, indicator, text, padding, the gap
before a cell, the cell's text - as a run of names, the edges trimmed.
"""

from __future__ import annotations

from typing import Any

import pytest

import tkcurses
from tkcurses import ttk
from tkcurses._core.geometry import Rect

tkinter = pytest.importorskip("tkinter")
from tkinter import ttk as real_ttk  # noqa: E402

#: (show, the e-anchored column or None): each makes a tree of a parent with
#: a value, its child with one, and a leaf with one.
CASES = [
    (("tree", "headings"), None),
    (("tree", "headings"), "a"),
    ("tree", None),
    ("headings", None),
]


def _build(module: Any, master: Any, show: Any, right: Any) -> tuple[Any, list[str]]:
    tree = module.Treeview(master, columns=("a",), show=show)
    if right:
        tree.column(right, anchor="e")
    parent = tree.insert("", "end", text="parent", values=("v1",))
    child = tree.insert(parent, "end", text="kid", values=("v2",))
    tree.item(parent, open=True)
    leaf = tree.insert("", "end", text="leaf", values=("v3",))
    return tree, [parent, child, leaf]


def _runs(names: list[str]) -> list[str]:
    runs: list[str] = []
    for name in names:
        if not runs or runs[-1] != name:
            runs.append(name)
    while runs and runs[0] == "":
        runs.pop(0)
    while runs and runs[-1] == "":
        runs.pop()
    return runs


def _theirs(show: Any, right: Any) -> list[list[str]]:
    try:
        root = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    try:
        real_ttk.Style(root).theme_use("default")
        tree, items = _build(real_ttk, root, show, right)
        tree.pack()
        root.update()
        found = []
        for iid in items:
            y = tree.bbox(iid)[1] + 5
            width = tree.winfo_width()
            found.append(_runs([tree.identify_element(x, y) for x in range(width)]))
        return found
    finally:
        root.destroy()


def _ours(show: Any, right: Any) -> list[list[str]]:
    tree, items = _build(ttk, tkcurses.Misc(), show, right)
    tree._allocate(Rect(0, 0, 60, 8))
    tree._map()
    area = tree._rows_area()
    found = []
    for iid in items:
        y = next(row for row in range(area.y, area.bottom) if tree._row_at(row) == iid)
        names = [tree.identify_element(x, y) for x in range(area.x, area.right)]
        found.append(_runs(names))
    return found


@pytest.mark.parametrize(("show", "right"), CASES)
def test_the_elements_across_a_row_are_tks(show, right):
    assert _ours(show, right) == _theirs(show, right)


def test_a_heading_and_the_space_below_the_items_name_nothing():
    tree, _ = _build(ttk, tkcurses.Misc(), ("tree", "headings"), None)
    tree._allocate(Rect(0, 0, 60, 8))
    tree._map()
    area = tree._rows_area()
    for x in range(area.x, area.right):
        assert tree.identify_element(x, area.y) == ""
        assert tree.identify_element(x, area.bottom - 1) == ""
    assert tree.identify("element", area.x, area.y + 1) == "Treeitem.indicator"
