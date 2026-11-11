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

"""ttk.Treeview's cell selection and ``selecttype``, replaying Tk 9.0.2.

Every expectation here was measured through tkinter, with
``tree.tk.call(tree, "cellselection", ...)`` and with clicks and keys sent by
``event_generate``. The rules follow ttkTreeview.c's cell selection commands
and the bindings in Tk's treeview.tcl.
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
    """Rows I1 to I4 with columns a, b and c; I1 has a closed child, K1."""
    tree = ttk.Treeview(root, columns=("a", "b", "c"), **kw)
    tree.place(x=0, y=0, width=60, height=10)
    for number in range(1, 5):
        tree.insert(
            "", "end", iid=f"I{number}", text=f"row{number}",
            values=(f"a{number}", f"b{number}", f"c{number}"),
        )  # fmt: skip
    tree.insert("I1", "end", iid="K1", text="kid", values=("ka", "kb", "kc"))
    # Narrow enough that every column is in view, for the clicks.
    for column in ("#0", "a", "b", "c"):
        tree.column(column, width=8, stretch=False)
    root.update_layout()
    tree.fired = []
    tree.bind("<<TreeviewSelect>>", lambda event: tree.fired.append(1))
    return tree


@pytest.fixture
def tree(root):
    return build(root)


def events(tree, change):
    """How many ``<<TreeviewSelect>>`` one change sends."""
    before = len(tree.fired)
    change()
    return len(tree.fired) - before


# ------------------------------------------------------------- the option


def test_selecttype_is_item_unless_told(tree):
    assert tree.configure("selecttype") == (
        "selecttype", "selectType", "SelectType", "item", "item",
    )  # fmt: skip


@pytest.mark.parametrize(
    ("given", "read"), [("cell", "cell"), ("c", "cell"), ("ce", "cell"), ("i", "item")]
)
def test_a_prefix_is_taken(tree, given, read):
    tree.configure(selecttype=given)
    assert tree.cget("selecttype") == read


@pytest.mark.parametrize(
    ("given", "message"),
    [("heading", 'bad selecttype "heading": must be item or cell'),
     ("CELL", 'bad selecttype "CELL": must be item or cell'),
     ("", 'ambiguous selecttype "": must be item or cell')],
)  # fmt: skip
def test_anything_else_is_refused(tree, given, message):
    with pytest.raises(tk.TclError, match=message):
        tree.configure(selecttype=given)


# ------------------------------------------------------- what it answers


def test_it_starts_empty(tree):
    assert tree.cellselection() == ()


def test_a_column_is_reported_by_name_however_it_was_given(tree):
    for column in ("#1", "a", 0, "0"):
        tree.cellselection_set(("I1", column))
        assert tree.cellselection() == (("I1", "a"),)
    tree.cellselection_set(("I1", "#0"))
    assert tree.cellselection() == (("I1", "#0"),)
    tree.cellselection_set(("I1", 2))
    assert tree.cellselection() == (("I1", "c"),)


def test_rows_come_in_tree_order_and_cells_in_the_order_chosen(tree):
    """A closed branch's child is reported; I1's own cells stay together."""
    tree.cellselection_set(("I2", "c"))
    tree.cellselection_add([("I1", "b"), ("K1", "a"), ("I2", "a"), ("I1", "a")])
    assert tree.cellselection() == (
        ("I1", "b"), ("I1", "a"), ("K1", "a"), ("I2", "c"), ("I2", "a"),
    )  # fmt: skip


def test_a_cell_may_be_a_tcl_list(tree):
    tree.cellselection_set("I1 a")
    tree.cellselection_add(["I2 b", ("I3", "c")])
    assert tree.cellselection() == (("I1", "a"), ("I2", "b"), ("I3", "c"))


# ------------------------------------------------- set, add, remove, toggle


def test_set_replaces_and_always_reports_a_change_when_there_was_one(tree):
    """Measured: setting the same cell again still sends the event, because
    set clears first; setting nothing on nothing sends none."""
    assert events(tree, lambda: tree.cellselection_set([])) == 0
    assert events(tree, lambda: tree.cellselection_set(("I1", "a"))) == 1
    assert events(tree, lambda: tree.cellselection_set(("I1", "a"))) == 1
    assert events(tree, lambda: tree.cellselection_set([])) == 1
    assert tree.cellselection() == ()


def test_add_reports_only_a_change(tree):
    tree.cellselection_set(("I1", "c"))
    assert events(tree, lambda: tree.cellselection_add(("I2", "b"))) == 1
    assert events(tree, lambda: tree.cellselection_add(("I2", "b"))) == 0
    assert tree.cellselection() == (("I1", "c"), ("I2", "b"))


def test_remove_takes_out_and_ignores_what_is_not_there(tree):
    tree.cellselection_set([("I1", "c"), ("I3", "a")])
    assert events(tree, lambda: tree.cellselection_remove(("I4", "a"))) == 0
    assert events(tree, lambda: tree.cellselection_remove(("I3", "a"))) == 1
    assert tree.cellselection() == (("I1", "c"),)


def test_toggle_flips_each(tree):
    tree.cellselection_set([("I1", "c"), ("I2", "b")])
    assert (
        events(tree, lambda: tree.cellselection_toggle([("I2", "b"), ("I4", "a")])) == 1
    )
    assert tree.cellselection() == (("I1", "c"), ("I4", "a"))


def test_a_row_emptied_by_remove_still_counts_for_the_next_set(tree):
    """Tk keeps an emptied row's list, so clearing it is a change."""
    tree.cellselection_set(("I1", "a"))
    tree.cellselection_remove(("I1", "a"))
    assert events(tree, lambda: tree.cellselection_set([])) == 1
    assert events(tree, lambda: tree.cellselection_set([])) == 0


def test_the_row_selection_is_separate(tree):
    tree.selection_set("I3")
    tree.cellselection_set([("I1", "a"), ("I2", "b")])
    assert tree.selection() == ("I3",)
    tree.selection_set("I4")
    assert tree.cellselection() == (("I1", "a"), ("I2", "b"))


# ------------------------------------------------------------- rectangles


def test_a_rectangle_covers_every_row_between_closed_branches_too(tree):
    tree.cellselection_set(("I1", "#1"), ("I3", "#2"))
    assert tree.cellselection() == (
        ("I1", "a"), ("I1", "b"), ("K1", "a"), ("K1", "b"),
        ("I2", "a"), ("I2", "b"), ("I3", "a"), ("I3", "b"),
    )  # fmt: skip


def test_its_corners_may_come_either_way_round(tree):
    tree.cellselection_set(("I4", "c"), ("I3", "#2"))
    assert tree.cellselection() == (
        ("I3", "b"), ("I3", "c"), ("I4", "b"), ("I4", "c"),
    )  # fmt: skip


def test_add_remove_and_toggle_work_on_one_too(tree):
    tree.cellselection_set(("I1", "a"), ("I2", "c"))
    tree.cellselection_remove(("I1", "a"), ("I1", "c"))
    tree.cellselection_toggle(("I2", "a"), ("I2", "b"))
    tree.cellselection_add(("I3", "#0"), ("I3", "a"))
    assert tree.cellselection() == (
        ("K1", "a"), ("K1", "b"), ("K1", "c"), ("I2", "c"),
        ("I3", "#0"), ("I3", "a"),
    )  # fmt: skip


def test_a_corner_must_be_showing(tree):
    tree.configure(displaycolumns=("a", "c"))
    with pytest.raises(tk.TclError, match="Cell id must be in a visible column"):
        tree.cellselection_set(("I1", "b"), ("I2", "c"))
    # A list may name a hidden column; it is selected and drawn nowhere.
    tree.cellselection_set(("I1", "b"))
    assert tree.cellselection() == (("I1", "b"),)


def test_a_rectangle_runs_in_display_order(tree):
    tree.configure(displaycolumns=("c", "a"))
    tree.cellselection_set(("I1", "#0"), ("I1", "a"))
    assert tree.cellselection() == (("I1", "#0"), ("I1", "c"), ("I1", "a"))


# ------------------------------------------------------------ the refusals


@pytest.mark.parametrize(
    ("cells", "message"),
    [([("I9", "a")], "Item I9 not found"),
     ([("I1", "zz")], 'Invalid column index "zz"'),
     ([("I1", "#9")], "Column #9 out of range"),
     ([("I1", "#-1")], "Column #-1 out of range"),
     ([("I1", "7")], 'Column index "7" out of bounds'),
     ([("I1", "-1")], 'Column index "-1" out of bounds'),
     ([("I1", "end")], 'Column index "end" out of bounds'),
     ([("I1", "a", "b")], "Cell id must be a list of two elements"),
     ([("I1",)], "Cell id must be a list of two elements"),
     # One pair that is not a cell is read as a list of two non-cells.
     (("I9", "a"), "Cell id must be a list of two elements")],
)  # fmt: skip
def test_a_bad_cell_is_refused_in_tks_words_and_changes_nothing(tree, cells, message):
    tree.cellselection_set(("I2", "b"))
    before = len(tree.fired)
    with pytest.raises(tk.TclError, match=message):
        tree.cellselection_set(cells)
    assert tree.cellselection() == (("I2", "b"),)
    assert len(tree.fired) == before


def test_a_rectangle_corner_is_checked_the_same_way(tree):
    with pytest.raises(tk.TclError, match="Item I9 not found"):
        tree.cellselection_set(("I9", "a"), ("I1", "b"))
    with pytest.raises(tk.TclError, match="two elements"):
        tree.cellselection_set(("I1",), ("I1", "b"))


# ------------------------------------------------- what else changes it


def test_detaching_hides_a_rows_cells_and_moving_it_back_restores_them(tree):
    tree.cellselection_set([("I1", "a"), ("I2", "b")])
    assert events(tree, lambda: tree.detach("I2")) == 0
    assert tree.cellselection() == (("I1", "a"),)
    tree.move("I2", "", 1)
    assert tree.cellselection() == (("I1", "a"), ("I2", "b"))


def test_deleting_a_selected_row_or_cell_sends_the_event(tree):
    tree.cellselection_set([("I1", "a"), ("I2", "b")])
    tree.selection_set("I3")
    assert events(tree, lambda: tree.delete("I2")) == 1
    assert tree.cellselection() == (("I1", "a"),)
    assert events(tree, lambda: tree.delete("I4")) == 0
    assert events(tree, lambda: tree.delete("I3")) == 1


def test_new_columns_clear_it_quietly(tree):
    tree.cellselection_set(("I1", "a"))
    assert events(tree, lambda: tree.configure(columns=("a", "b", "c", "d"))) == 0
    assert tree.cellselection() == ()


def test_new_displaycolumns_keep_it(tree):
    tree.cellselection_set(("I1", "b"))
    tree.configure(displaycolumns=("a", "c"))
    assert tree.cellselection() == (("I1", "b"),)


def test_changing_selecttype_clears_neither(tree):
    tree.selection_set("I1")
    tree.cellselection_set(("I2", "a"))
    tree.configure(selecttype="cell")
    tree.configure(selecttype="item")
    assert tree.selection() == ("I1",)
    assert tree.cellselection() == (("I2", "a"),)


# ---------------------------------------------------------------- drawing


def test_only_the_selected_cells_span_is_painted(tree):
    """The column's own cells, not the space joining it to the next; what
    they look like on a terminal is the tty test's."""
    tree.cellselection_set(("I2", "b"))
    _name, start, end = next(s for s in tree._column_spans() if s[0] == "b")
    assert tree._selected_spans("I2", 60) == [(start, end)]
    assert tree._selected_spans("I1", 60) == []


def test_a_scrolled_cell_is_cut_where_the_frozen_columns_cover_it(root):
    tree = build(root, titlecolumns=1)
    tree.column("#0", width=6)
    for name in "abc":
        tree.column(name, width=10)
    root.update_layout()
    tree.cellselection_set(("I1", "a"))
    _name, start, end = next(s for s in tree._column_spans() if s[0] == "a")
    frozen = tree._frozen_width()
    tree.xview("scroll", 3, "units")
    left = tree._left
    assert tree._selected_spans("I1", 60) == [(max(start - left, frozen), end - left)]


# --------------------------------------------------------------- bindings


def at(tree, item, column):
    x, y, width, _height = tree.bbox(item, column)
    return {"x": x + width // 2, "y": y}


def click(tree, item, column, modifier=""):
    tree.event_generate(f"<{modifier}Button-1>", **at(tree, item, column))
    tree.event_generate("<ButtonRelease-1>", **at(tree, item, column))


def key(tree, name):
    tree.event_generate(f"<Key-{name}>")


def state(tree):
    return tree.cellselection(), tree.selection(), tree.focus()


def test_a_click_selects_one_cell_and_leaves_the_rows_alone(root):
    tree = build(root, selecttype="cell")
    click(tree, "I2", "b")
    assert state(tree) == ((("I2", "b"),), (), "I2")
    click(tree, "I2", "#0")
    assert state(tree) == ((("I2", "#0"),), (), "I2")


def test_control_click_toggles_and_shift_click_adds_a_rectangle_after_it(root):
    tree = build(root, selecttype="cell")
    click(tree, "I2", "b")
    click(tree, "I3", "c", "Control-")
    assert state(tree) == ((("I2", "b"), ("I3", "c")), (), "I2")
    click(tree, "I4", "a", "Shift-")
    assert state(tree) == (
        (("I2", "b"), ("I3", "c"), ("I3", "a"), ("I3", "b"),
         ("I4", "a"), ("I4", "b"), ("I4", "c")),
        (), "I2",
    )  # fmt: skip


def test_shift_click_after_a_plain_click_sets_the_rectangle(root):
    tree = build(root, selecttype="cell")
    click(tree, "I1", "a")
    click(tree, "I3", "b", "Shift-")
    assert state(tree) == (
        (("I1", "a"), ("I1", "b"), ("K1", "a"), ("K1", "b"),
         ("I2", "a"), ("I2", "b"), ("I3", "a"), ("I3", "b")),
        (), "I1",
    )  # fmt: skip


def test_the_arrows_move_the_cell_and_right_reaches_the_last_column(root):
    """Right goes as far as c and stops there; Left stops at the tree
    column. Tk 9.0.2's Right stops at b, one short - a deliberate
    difference."""
    tree = build(root, selecttype="cell")
    tree.focus_set()
    click(tree, "I1", "a")
    seen = []
    for name in ["Right"] * 3 + ["Left"] * 4 + ["Down", "Up"]:
        key(tree, name)
        seen.append(tree.cellselection())
    assert seen == [
        (("I1", "b"),), (("I1", "c"),), (("I1", "c"),),
        (("I1", "b"),), (("I1", "a"),), (("I1", "#0"),), (("I1", "#0"),),
        (("I2", "#0"),), (("I1", "#0"),),
    ]  # fmt: skip
    assert tree.selection() == ()


def test_right_stops_at_the_last_column_displayed(root):
    tree = build(root, selecttype="cell", displaycolumns=("c", "a"))
    click(tree, "I1", "c")
    key(tree, "Right")
    key(tree, "Right")
    assert tree.cellselection() == (("I1", "a"),)


def test_without_the_tree_column_left_stops_at_the_first_data_column(root):
    tree = build(root, selecttype="cell", show="headings")
    click(tree, "I1", "b")
    key(tree, "Left")
    key(tree, "Left")
    assert tree.cellselection() == (("I1", "a"),)


def test_an_arrow_with_no_cell_chosen_yet_takes_the_first_data_column(root):
    tree = build(root, selecttype="cell")
    tree.focus("I1")
    key(tree, "Down")
    assert tree.cellselection() == (("I2", "a"),)


def test_in_cell_mode_right_does_not_open_a_branch(root):
    tree = build(root, selecttype="cell")
    click(tree, "I1", "a")
    key(tree, "Right")
    assert tree.item("I1", "open") in (0, False)


def test_browse_takes_one_cell_whatever_the_modifier(root):
    tree = build(root, selecttype="cell", selectmode="browse")
    click(tree, "I1", "a")
    click(tree, "I2", "b", "Control-")
    assert state(tree) == ((("I2", "b"),), (), "I2")
    click(tree, "I3", "c", "Shift-")
    assert state(tree) == ((("I3", "c"),), (), "I3")


def test_none_only_moves_the_keyboard(root):
    tree = build(root, selecttype="cell", selectmode="none")
    click(tree, "I1", "a")
    key(tree, "Down")
    assert state(tree) == ((), (), "I2")


def test_rows_follow_the_same_modes(root):
    """Measured with the default selecttype: Control-click toggles a row,
    Shift-click selects from the keyboard's row to the one clicked."""
    tree = build(root)
    click(tree, "I2", "b")
    click(tree, "I4", "a", "Control-")
    assert state(tree) == ((), ("I2", "I4"), "I2")
    click(tree, "I4", "a", "Shift-")
    assert state(tree) == ((), ("I2", "I3", "I4"), "I2")


def test_a_row_click_leaves_the_cells_alone(root):
    tree = build(root)
    tree.cellselection_set(("I1", "a"))
    click(tree, "I3", "a")
    assert state(tree) == ((("I1", "a"),), ("I3",), "I3")


# ---------------------------------------------------------------- tk.call


def call(tree, *args):
    return tree.tk.call(tree, "cellselection", *args)


def test_tk_call_reads_and_changes_it_as_tkinter_does(tree):
    """tkinter's only way in, so a program written for it runs unchanged:
    nothing reads back as "", a change answers "", cells as tuples."""
    assert call(tree) == ""
    assert call(tree, "set", [("I1", "a"), ("I2", "b")]) == ""
    assert call(tree) == (("I1", "a"), ("I2", "b"))
    call(tree, "add", ("I3", "#1"), ("I3", "b"))
    call(tree, "toggle", [("I1", "a")])
    call(tree, "remove", ("I2", "b"))
    assert call(tree) == (("I3", "a"), ("I3", "b"))
    assert tree.tk.call((str(tree), "cellselection")) == call(tree)


def test_tk_call_takes_a_prefix_of_the_operation(tree):
    call(tree, "s", ("I1", "a"))
    assert tree.cellselection() == (("I1", "a"),)


@pytest.mark.parametrize(
    ("args", "message"),
    [(("frob", ("I1", "a")), 'bad cellselection operation "frob": must be set,'
                             " add, remove, or toggle"),
     (("set",), "wrong # args: should be"),
     (("set", "a", "b", "c"), "wrong # args: should be"),
     (("I1",), "wrong # args: should be")],
)  # fmt: skip
def test_tk_call_refuses_in_tks_words(tree, args, message):
    """Measured on Tk 9.0.2."""
    with pytest.raises(tk.TclError, match=message):
        call(tree, *args)


def test_tk_call_names_a_missing_widget_as_tk_does(tree):
    with pytest.raises(tk.TclError, match=r'invalid command name "\.nosuch"'):
        tree.tk.call(".nosuch", "cellselection")


def test_tk_call_says_plainly_what_it_does_not_interpret(tree):
    with pytest.raises(tk.TclError, match="no Tcl interpreter"):
        tree.tk.call("source", "x.tcl")
    with pytest.raises(tk.TclError, match=r'does not interpret ".*selection"'):
        tree.tk.call(tree, "selection")


@pytest.mark.parametrize(
    ("value", "split"),
    [(("I1", "a"), ("I1", "a")), (["I1", "a"], ("I1", "a")),
     ("I1 a", ("I1", "a")), ("{I 1} a", ("I 1", "a")), ("", ())],
)  # fmt: skip
def test_splitlist_splits_as_tkinter_does(tree, value, split):
    assert tree.tk.splitlist(value) == split
