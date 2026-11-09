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

"""Canvas window items: the canvas as a geometry manager.

Each rule was measured on Tk 9.0.2 through tkinter. Coordinates here are
canvas pixels, a cell wide and half a cell high, so a window at pixel row 10
starts on cell row 5.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

import tkcurses as tk
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


@pytest.fixture
def root():
    root = tk.Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    return root


@pytest.fixture
def canvas(root):
    widget = tk.Canvas(root, name="c", width=40, height=10, relief="flat")
    widget.place(x=0, y=0)
    root.update_layout()
    return widget


@pytest.fixture
def button(canvas):
    return tk.Button(canvas, text="hi")


def geometry(widget):
    return (
        widget.winfo_x(),
        widget.winfo_y(),
        widget.winfo_width(),
        widget.winfo_height(),
    )


def test_a_window_items_defaults_are_tks(canvas):
    item = canvas.create_window(50, 50)
    assert canvas.type(item) == "window"
    assert canvas.itemcget(item, "window") == ""
    assert canvas.itemcget(item, "anchor") == "center"
    assert canvas.itemcget(item, "width") == 0
    assert canvas.itemcget(item, "height") == 0


def test_with_no_window_the_bbox_is_one_pixel(canvas):
    """Measured: (50, 50, 51, 51)."""
    item = canvas.create_window(50, 50)
    assert canvas.bbox(item) == (50, 50, 51, 51)


def test_the_canvas_manages_its_window(root, canvas, button):
    item = canvas.create_window(20, 10, window=button)
    root.update_layout()
    assert canvas.itemcget(item, "window") == str(button)
    assert button.winfo_manager() == "canvas"
    assert button.winfo_ismapped()
    # 8 cells by 3 rows is 8 pixels by 6, centred on (20, 10): its top is
    # pixel 7, which snaps to the row that starts at pixel 6 - row 3.
    assert geometry(button) == (16, 3, 8, 3)
    assert canvas.bbox(item) == (16, 6, 24, 12)


def test_a_window_moves_with_its_item(root, canvas, button):
    item = canvas.create_window(0, 0, window=button, anchor="nw")
    root.update_layout()
    canvas.move(item, 4, 2)
    root.update_layout()
    assert geometry(button)[:2] == (4, 1)
    canvas.coords(item, 10, 6)
    root.update_layout()
    assert geometry(button)[:2] == (10, 3)


def test_width_and_height_size_the_window_in_pixels(root, canvas, button):
    """Tk's 0 is the size the window asks for, as measured."""
    item = canvas.create_window(0, 0, window=button, anchor="nw", width=10, height=6)
    root.update_layout()
    assert geometry(button)[2:] == (10, 3)
    canvas.itemconfigure(item, width=0, height=0)
    root.update_layout()
    assert geometry(button)[2:] == (8, 3)


def test_a_window_moves_with_the_view_and_leaves_it(root, canvas, button):
    """Measured: scrolled wholly out of view, the window is unmapped."""
    canvas.configure(scrollregion=(0, 0, 200, 200))
    canvas.create_window(10, 4, window=button, anchor="nw")
    root.update_layout()
    canvas.xview_scroll(5, "units")
    root.update_layout()
    assert button.winfo_ismapped()
    assert geometry(button)[0] == 10 - canvas._left
    canvas.xview_moveto(0.5)
    root.update_layout()
    assert not button.winfo_ismapped()
    canvas.xview_moveto(0)
    root.update_layout()
    assert button.winfo_ismapped()
    assert geometry(button)[:2] == (10, 2)


def test_a_hidden_item_unmaps_its_window(root, canvas, button):
    item = canvas.create_window(10, 4, window=button)
    root.update_layout()
    canvas.itemconfigure(item, state="hidden")
    root.update_layout()
    assert not button.winfo_ismapped()
    canvas.itemconfigure(item, state="normal")
    root.update_layout()
    assert button.winfo_ismapped()


def test_a_second_item_takes_the_window(root, canvas, button):
    first = canvas.create_window(10, 4, window=button)
    second = canvas.create_window(0, 0, window=button, anchor="nw")
    root.update_layout()
    assert canvas.itemcget(first, "window") == ""
    assert canvas.itemcget(second, "window") == str(button)
    assert geometry(button)[:2] == (0, 0)


def test_packing_the_window_takes_it_from_its_item(root, canvas, button):
    item = canvas.create_window(10, 4, window=button)
    root.update_layout()
    button.pack()
    assert canvas.itemcget(item, "window") == ""
    assert button.winfo_manager() == "pack"


def test_embedding_a_packed_window_takes_it_from_pack(root, canvas, button):
    button.pack()
    root.update_layout()
    canvas.create_window(10, 4, window=button)
    assert button.winfo_manager() == "canvas"
    assert button not in canvas.pack_slaves()


def test_deleting_the_item_unmaps_and_releases_the_window(root, canvas, button):
    item = canvas.create_window(10, 4, window=button)
    root.update_layout()
    canvas.delete(item)
    root.update_layout()
    assert button.winfo_manager() == ""
    assert not button.winfo_ismapped()


def test_destroying_the_window_empties_its_item(root, canvas, button):
    item = canvas.create_window(10, 4, window=button)
    root.update_layout()
    button.destroy()
    assert canvas.itemcget(item, "window") == ""
    assert canvas.bbox(item) == (10, 4, 11, 5)


def test_a_new_window_releases_the_old_one(root, canvas, button):
    other = tk.Label(canvas, text="other")
    item = canvas.create_window(10, 4, window=button)
    root.update_layout()
    canvas.itemconfigure(item, window=other)
    root.update_layout()
    assert button.winfo_manager() == ""
    assert not button.winfo_ismapped()
    assert other.winfo_manager() == "canvas"


def test_a_window_may_be_a_child_of_the_canvas_parent(root, canvas):
    """Measured: Tk takes any child of the canvas or of an ancestor."""
    label = tk.Label(root, text="sib")
    canvas.create_window(3, 4, window=label, anchor="nw")
    root.update_layout()
    assert label.winfo_manager() == "canvas"
    assert geometry(label) == (3, 2, 3, 1)


def test_a_window_follows_a_new_request(root, canvas, button):
    canvas.create_window(0, 0, window=button, anchor="nw")
    root.update_layout()
    button.configure(text="much longer")
    root.update_layout()
    assert geometry(button)[2] == button.winfo_reqwidth()


def test_a_window_item_can_be_found(root, canvas, button):
    item = canvas.create_window(10, 4, window=button, anchor="nw")
    root.update_layout()
    assert canvas.find_overlapping(12, 5, 13, 6) == (item,)
    assert canvas.find_closest(12, 5) == (item,)


@pytest.mark.parametrize(
    ("window", "message"),
    [
        (".nosuch", 'bad window path name ".nosuch"'),
        (".", "can't use . in a window item of this canvas"),
        (".c", "can't use .c in a window item of this canvas"),
    ],
)
def test_windows_tk_will_not_take_are_refused(canvas, window, message):
    with pytest.raises(tk.TclError, match=re.escape(message)):
        canvas.create_window(1, 1, window=window)


def test_a_window_from_another_toplevel_is_refused(root, canvas):
    elsewhere = tk.Label(tk.Toplevel(root))
    with pytest.raises(tk.TclError, match=r"can't use .* in a window item"):
        canvas.create_window(1, 1, window=elsewhere)
