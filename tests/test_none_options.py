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

"""An option given as None is ignored, as tkinter ignores it. TkCurses-bx5b.

tkinter's ``Misc._options`` leaves out any option whose value is None, so
``configure(text=None)`` leaves the text alone. This library stored the None,
and ``cget`` answered it back. Every case below was measured on Tcl/Tk 9.0.2.

The ttk methods that format their options with ``_format_optdict`` - item,
heading, column, tag_configure, tab, pane, Style.configure - do something
else in tkinter, by accident: a lone None becomes a query for that option,
and a None beside a real value garbles the call (``item(i, text=None,
open=True)`` raises ``unknown option "1"``). Nothing can rely on that, so
there None is ignored like everywhere else, and recorded in ARCHITECTURE.md.
"""

from __future__ import annotations

import pytest

import tkcurses as tk
from tkcurses import Misc, TclError, ttk


@pytest.fixture
def root():
    return Misc()


def test_a_constructor_ignores_none(root):
    assert tk.Button(root, text=None).cget("text") == ""
    assert ttk.Button(root, text=None).cget("text") == ""


def test_a_none_that_would_be_refused_is_never_looked_at(root):
    """striped=None reached the boolean check before and raised."""
    assert ttk.Treeview(root, striped=None).cget("striped") == 0


@pytest.mark.parametrize(
    "make", [lambda r: tk.Button(r, text="a"), lambda r: ttk.Button(r, text="a")]
)
def test_configure_ignores_none_and_answers_none(root, make):
    widget = make(root)
    assert widget.configure(text=None) is None, "not the listing an empty call gives"
    assert widget.configure({"text": None}) is None
    widget.config(text=None, underline=0)
    widget["text"] = None
    assert widget.cget("text") == "a"
    assert widget.cget("underline") == 0


def test_canvas_items_ignore_none(root):
    canvas = tk.Canvas(root)
    plain = canvas.create_text(1, 1, text="x")
    given = canvas.create_text(1, 1, text="x", fill=None)
    assert canvas.itemcget(given, "fill") == canvas.itemcget(plain, "fill")
    assert canvas.itemconfigure(plain, text=None) is None
    assert canvas.itemcget(plain, "text") == "x"


def test_menu_entries_ignore_none(root):
    menu = tk.Menu(root)
    menu.add_command(label="a")
    menu.add_command(label=None)
    assert menu.entrycget("end", "label") == ""
    assert menu.entryconfigure(0, label=None) is None
    assert menu.entrycget(0, "label") == "a"


def test_text_tags_ignore_none(root):
    text = tk.Text(root)
    text.tag_configure("x", foreground="red")
    assert text.tag_configure("x", foreground=None) is None
    assert text.tag_cget("x", "foreground") == "red"


def test_the_treeview_ignores_none(root):
    tree = ttk.Treeview(root, columns=("a",))
    row = tree.insert("", "end", text="a", values=(1,), open=None)
    assert tree.item(row, "open") == 0
    tree.heading("a", text="H")
    tree.column("a", width=50)
    tree.tag_configure("t", foreground="red")
    assert tree.item(row, text=None) is None
    assert tree.heading("a", text=None) is None
    assert tree.column("a", width=None) is None
    assert tree.tag_configure("t", foreground=None) is None
    assert tree.item(row, "text") == "a"
    assert tree.heading("a", "text") == "H"
    assert tree.column("a", "width") == 50
    assert tree.tag_configure("t", "foreground") == "red"


def test_a_none_beside_a_real_value_is_dropped_alone(root):
    """tkinter raises 'unknown option "1"' here; nothing can depend on that."""
    tree = ttk.Treeview(root)
    row = tree.insert("", "end", text="a")
    tree.item(row, text=None, open=True)
    assert (tree.item(row, "text"), tree.item(row, "open")) == ("a", True)


def test_style_ignores_none(root):
    style = ttk.Style(root)
    style.configure("X.TButton", foreground="red")
    assert style.configure("X.TButton", foreground=None) is None
    assert style.lookup("X.TButton", "foreground") == "red"


def test_notebook_tabs_ignore_none(root):
    book = ttk.Notebook(root)
    first, second = tk.Frame(book), tk.Frame(book)
    book.add(first, text="a")
    book.add(second, text=None)
    assert book.tab(second, "text") == ""
    assert book.tab(first, text=None) is None
    assert book.tab(first, "text") == "a"


def test_panes_ignore_none(root):
    paned = tk.PanedWindow(root)
    child = tk.Frame(paned)
    paned.add(child, minsize=10, sticky=None)
    assert paned.paneconfigure(child, minsize=None) is None
    assert paned.panecget(child, "minsize") == 10
    themed = ttk.Panedwindow(root)
    pane = tk.Frame(themed)
    themed.add(pane, weight=2)
    assert themed.pane(pane, weight=None) is None
    assert themed.pane(pane)["weight"] == 2


def test_the_geometry_managers_ignore_none(root):
    packed_in, gridded_in = tk.Frame(root), tk.Frame(root)
    packed = tk.Label(packed_in)
    packed.pack(padx=3)
    packed.pack_configure(padx=None)
    gridded = tk.Label(gridded_in)
    gridded.grid(row=1, padx=2)
    gridded.grid_configure(padx=None)
    placed = tk.Label(root)
    placed.place(x=5)
    placed.place_configure(x=None)
    assert packed.pack_info()["padx"] == 3
    assert gridded.grid_info()["padx"] == 2
    assert placed.place_info()["x"] == 5


def test_a_grid_line_ignores_none_and_then_lists(root):
    """Measured: unlike configure, an all-None call here DOES answer the listing."""
    frame = tk.Frame(root)
    frame.grid_columnconfigure(0, weight=2)
    listing = frame.grid_columnconfigure(0, weight=None)
    assert listing["weight"] == 2


def test_a_grid_line_answers_one_option_by_name(root):
    """It crashed on "'str' object is not a mapping", as configure did."""
    frame = tk.Frame(root)
    frame.grid_columnconfigure(0, weight=2)
    assert frame.grid_columnconfigure(0, "weight") == 2
    assert frame.grid_rowconfigure(1, "minsize") == 0
    with pytest.raises(
        TclError,
        match='bad option "-nope": must be -minsize, -pad, -uniform, or -weight',
    ):
        frame.grid_columnconfigure(0, "nope")
