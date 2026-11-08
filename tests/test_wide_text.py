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

"""Wide text measured in cells by the widgets that lay out text of their own.

Each test sets three ideographs - six cells - against six ASCII letters,
which a terminal draws the same width: the widget must measure them alike.
It measured them by ``len()`` and so gave the ideographs half the room.
The drawing is in test_wide_text_tty.py. TkCurses-r9k2.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Canvas, LabelFrame, Listbox, Menu, Misc, Scale, ttk
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack

WIDE = "日本語"  # three ideographs, six cells
NARROW = "abcdef"  # six letters, six cells


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(window_factory=stub_window, panel_factory=None)
    root._rect = Rect(0, 0, 60, 24)
    root._mapped = True
    return root


def laid_out(widget, width=24, height=6):
    widget._allocate(Rect(0, 0, width, height))
    widget._map()
    return widget


def test_a_menubar_asks_for_its_labels_cells(root):
    def bar(label):
        menu = Menu(root)
        menu._as_menubar = True
        menu.add_cascade(label=label)
        menu.add_cascade(label="Edit")
        menu._apply_requested_size()
        return menu

    wide, narrow = bar(WIDE), bar(NARROW)
    assert wide._requested.width == narrow._requested.width
    assert wide._label_column(1) == narrow._label_column(1)
    for column in range(wide._requested.width):
        assert wide._entry_at_column(column) == narrow._entry_at_column(column)


def test_a_listbox_scrolls_across_the_cells_of_its_widest_item(root):
    def box(item):
        widget = laid_out(Listbox(root, width=8, height=2), width=10, height=4)
        widget.insert(0, item)
        return widget

    assert box(WIDE * 2).xview() == box(NARROW * 2).xview() == (0.0, 0.5)


def test_a_scale_asks_for_room_for_a_wide_label(root):
    def scale(label):
        return Scale(root, label=label, orient="horizontal", length=2)

    assert scale(WIDE).winfo_reqwidth() == scale(NARROW).winfo_reqwidth()


@pytest.mark.parametrize("anchor", ["n", "ne"])
def test_a_wide_caption_is_placed_as_a_narrow_one_is(root, anchor):
    def frame(caption):
        return laid_out(LabelFrame(root, text=caption, labelanchor=anchor))

    assert frame(WIDE)._caption_place()[1] == frame(NARROW)._caption_place()[1]


def test_a_themed_labelframe_answers_for_every_cell_of_a_wide_caption(root):
    frame = laid_out(ttk.Labelframe(root, text=WIDE))
    row, column, _ = frame._caption_place()
    assert [frame.identify(column + i, row) for i in range(6)] == [""] * 6


def test_canvas_text_bbox_counts_cells(root):
    canvas = laid_out(Canvas(root, width=20, height=4))
    wide = canvas.create_text(0, 0, text=WIDE, anchor="nw")
    narrow = canvas.create_text(0, 4, text=NARROW, anchor="nw")
    assert canvas.bbox(wide)[2] == canvas.bbox(narrow)[2] == 5


def test_a_notebook_tab_label_answers_for_its_every_cell(root):
    book = laid_out(ttk.Notebook(root), width=30, height=6)
    book.add(ttk.Frame(book), text=WIDE)
    _, first, _ = book._tab_spans()[0]
    start = first + 2
    assert [book.identify(start + i, 1) for i in range(6)] == ["label"] * 6


def test_font_measure_counts_cells(root):
    from tkcurses import font

    assert font.Font(root=root).measure(WIDE) == 6
    assert font.Font(root=root).measure("é") == 1


@pytest.mark.parametrize(
    ("wide", "narrow", "aspect"),
    [
        (" ".join([WIDE] * 6), " ".join([NARROW] * 6), 150),
        (" ".join([WIDE[0], WIDE[0], WIDE]), "ab ab abcdef", 150),
        (WIDE[0] + " " + WIDE[0], "ab ab", 500),
    ],
    ids=["words", "a-long-word", "two-ideographs"],
)
def test_a_messages_aspect_is_reckoned_in_cells(root, wide, narrow, aspect):
    """Sized by aspect from its words: ideographs give the same shape as
    letters that take the same cells. The last two are the cases where
    counting characters would bound the search wrongly: too narrow a start,
    which breaks the long word across rows, and too short an end."""
    from tkcurses import Message

    def message(text):
        widget = Message(root, text=text, aspect=aspect)
        return widget.winfo_reqwidth(), widget.winfo_reqheight()

    assert message(wide) == message(narrow)
