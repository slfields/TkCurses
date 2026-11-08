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

"""The themed widgets that only draw, where they need no terminal.

Every behaviour asserted here was measured against real ttk on Tk 9.0 first,
and the three that surprise say so where they are pinned.
"""

from __future__ import annotations

import curses

import pytest

import tkcurses
from tkcurses import Misc, TclError
from tkcurses._core.events import MOD_ALT, MOD_SHIFT, MouseEvent
from tkcurses.ttk import (
    COLUMN_WIDTH,
    Button,
    Checkbutton,
    Combobox,
    Entry,
    Frame,
    Label,
    LabeledScale,
    LabelFrame,
    Labelframe,
    Menubutton,
    Notebook,
    OptionMenu,
    PanedWindow,
    Panedwindow,
    Progressbar,
    Radiobutton,
    Scale,
    Scrollbar,
    Separator,
    Sizegrip,
    Spinbox,
    Style,
    Treeview,
    parse_padding,
)


@pytest.fixture
def root():
    return Misc()


# ------------------------------------------------------------- Separator


def test_a_separator_is_themed(root):
    assert Separator(root, name="s").winfo_class() == "TSeparator"


def test_a_separator_is_horizontal_unless_told_otherwise(root):
    assert Separator(root, name="s").cget("orient") == "horizontal"


def test_a_horizontal_separator_is_one_cell_tall(root):
    assert Separator(root, name="s").winfo_reqheight() == 1


def test_a_vertical_separator_is_one_cell_wide(root):
    assert Separator(root, name="s", orient="vertical").winfo_reqwidth() == 1


def test_changing_the_orientation_re_measures(root):
    separator = Separator(root, name="s")
    separator.configure(orient="vertical")
    assert separator.winfo_reqwidth() == 1


# -------------------------------------------------------------- Sizegrip


def test_a_sizegrip_is_themed(root):
    assert Sizegrip(root, name="g").winfo_class() == "TSizegrip"


def test_a_sizegrip_asks_for_one_cell(root):
    grip = Sizegrip(root, name="g")
    assert (grip.winfo_reqwidth(), grip.winfo_reqheight()) == (1, 1)


# ----------------------------------------------------------- Progressbar


@pytest.fixture
def bar(root):
    return Progressbar(root, name="p", length=20)


# --------------------------------------------- Progressbar's label (xe9.1)
#
# Tk 9.0 draws a label over the bar. The defaults are measured against real
# ttk, and two of them are not what a bar showing "40%" would suggest: the
# anchor is "w" and the justify "left", not centred.


@pytest.mark.parametrize(
    ("option", "default"),
    [
        ("text", ""),
        ("anchor", "w"),
        ("font", ""),
        ("justify", "left"),
        ("wraplength", 0),
    ],
)
def test_the_label_options_default_as_tks_do(bar, option, default):
    assert bar.cget(option) == default


def test_the_label_is_not_wrapped_without_a_wraplength(bar):
    """wrap()'s own rule, and Tk's: zero means no wrapping at all."""
    bar.configure(text="one two three four five")
    assert bar._label_lines() == ["one two three four five"]


def test_a_wraplength_breaks_the_label_into_lines(bar):
    bar.configure(text="one two three four five", wraplength=8)
    assert bar._label_lines() == ["one two", "three", "four", "five"]


def test_no_text_is_no_lines_rather_than_one_empty_one(bar):
    """A Label with no text still occupies a row; a bar with no text must not
    draw a blank line over itself, which would erase the glyphs under it."""
    assert bar._label_lines() == []


def test_a_progressbar_is_themed(bar):
    assert bar.winfo_class() == "TProgressbar"


def test_the_defaults_are_tkinters(root):
    bar = Progressbar(root, name="p")
    assert bar.cget("mode") == "determinate"
    assert bar.cget("maximum") == 100.0
    assert bar.cget("value") == 0.0
    assert bar.cget("orient") == "horizontal"


def test_a_bar_is_as_long_as_its_length(root):
    assert Progressbar(root, name="p", length=30).winfo_reqwidth() == 30


def test_a_vertical_bar_is_as_tall_as_its_length(root):
    bar = Progressbar(root, name="p", length=8, orient="vertical")
    assert (bar.winfo_reqwidth(), bar.winfo_reqheight()) == (1, 8)


# ------------------------------------------------------ step(), measured


def test_step_moves_one_by_default(bar):
    """Tk's default amount is 1.0."""
    bar.step()
    assert bar.cget("value") == 1.0


def test_step_takes_an_amount(bar):
    bar.step(5)
    assert bar.cget("value") == 5.0


def test_determinate_step_wraps_at_the_maximum(bar):
    """Measured against Tk 9.0: 90 + step(30) with maximum 100 lands on 20,
    and the whole sequence from zero is 30 60 90 20 50 80."""
    seen = []
    for _ in range(6):
        bar.step(30)
        seen.append(bar.cget("value"))
    assert seen == [30.0, 60.0, 90.0, 20.0, 50.0, 80.0]


def test_indeterminate_step_does_not_wrap_at_all(bar):
    """The one that surprises. Measured: the same sequence in indeterminate
    mode is 30 60 90 120 150 180 - it accumulates without bound, and it is
    the *display* that takes it modulo a sweep."""
    bar.configure(mode="indeterminate")
    seen = []
    for _ in range(6):
        bar.step(30)
        seen.append(bar.cget("value"))
    assert seen == [30.0, 60.0, 90.0, 120.0, 150.0, 180.0]


def test_setting_the_value_directly_does_not_wrap(bar):
    """Measured: configure(value=150) on a bar whose maximum is 100 leaves
    it at 150. Only step wraps."""
    bar.configure(value=150)
    assert bar.cget("value") == 150


# ------------------------------------------------- start() and stop()


def test_stop_resets_the_value_to_zero(bar):
    """Not a pause. Measured against Tk 9.0, where stop() zeroes it."""
    bar.configure(value=42)
    bar.stop()
    assert bar.cget("value") == 0.0


def test_stop_on_a_bar_that_was_never_started_is_harmless(bar):
    bar.stop()
    assert bar.cget("value") == 0.0


def test_starting_twice_does_not_stack_two_timers(bar):
    """Or the bar would step twice as fast for the rest of its life."""
    bar.start(1000)
    first = bar._timer
    bar.start(1000)
    assert bar._timer is first
    bar.stop()


def test_stop_cancels_the_timer(bar):
    bar.start(1000)
    bar.stop()
    assert bar._timer is None


# ------------------------------------------------------------- the fill


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 0), (25, 5), (50, 10), (100, 20), (150, 20)],
)
def test_a_determinate_bar_fills_in_proportion(bar, value, expected):
    """And a value past the maximum fills it rather than overflowing."""
    bar.configure(value=value)
    assert bar._filled_cells(20) == (0, expected)


def test_an_indeterminate_block_sweeps_out_and_back(bar):
    """Which is what makes it bounce rather than jump back to the start:
    the value is taken modulo twice the maximum, and the second half of that
    cycle is the first half reflected."""
    bar.configure(mode="indeterminate")
    positions = []
    for value in (0, 50, 100, 150, 200):
        bar.configure(value=value)
        positions.append(bar._filled_cells(20)[0])
    assert positions[0] == 0
    assert positions[2] == max(positions), "furthest out at the maximum"
    assert positions[4] == 0, "back where it started after a full cycle"
    assert positions[1] == positions[3], "the way out and the way back match"


def test_an_indeterminate_block_is_never_the_whole_bar(bar):
    bar.configure(mode="indeterminate")
    for value in range(0, 200, 7):
        bar.configure(value=value)
        _, count = bar._filled_cells(20)
        assert 0 < count < 20


# --------------------------------------------------------- and the style


def test_the_themed_widgets_take_a_style_option(root):
    for widget in (
        Separator(root, name="s"),
        Sizegrip(root, name="g"),
        Progressbar(root, name="p"),
    ):
        assert widget.cget("style") == ""


def test_configuring_a_class_reaches_every_bar_of_it(root):
    bars = [Progressbar(root, name=f"p{index}") for index in range(3)]
    Style(root).configure("TProgressbar", foreground="green")
    assert [b._styled("foreground") for b in bars] == ["green"] * 3


def test_a_bar_with_its_own_style_still_inherits_the_class(root):
    style = Style(root)
    style.configure("TProgressbar", background="trough")
    style.configure("Danger.TProgressbar", foreground="red")
    bar = Progressbar(root, name="p", style="Danger.TProgressbar")
    assert bar._styled("foreground") == "red"
    assert bar._styled("background") == "trough"


# ------------------------------------------------- which window a grip owns


def test_a_grip_on_a_toplevel_has_a_window_to_resize(root):
    import tkcurses

    top = tkcurses.Toplevel(root, name="t")
    grip = Sizegrip(top, name="g")
    assert grip._resizable_window() is top


def test_a_grip_on_the_root_has_none(root):
    """The one case the first version generalised from, and the only one it
    was right about: the root's size *is* the terminal's, and nothing an
    application draws changes that. Every other window here is the
    library's own."""
    assert Sizegrip(root, name="g")._resizable_window() is None


def test_a_window_locked_against_resizing_has_none(root):
    import tkcurses

    top = tkcurses.Toplevel(root, name="t")
    top.wm_resizable(False, False)
    assert Sizegrip(top, name="g")._resizable_window() is None


def test_a_window_locked_on_one_axis_is_still_resizable(root):
    import tkcurses

    top = tkcurses.Toplevel(root, name="t")
    top.wm_resizable(False, True)
    assert Sizegrip(top, name="g")._resizable_window() is top


def test_a_grip_starts_with_no_drag_in_progress(root):
    import tkcurses

    top = tkcurses.Toplevel(root, name="t")
    assert Sizegrip(top, name="g")._drag is None


def test_an_indeterminate_bar_at_zero_still_draws_its_block(root):
    """The two modes differ at zero, and the UAT checklist had it wrong.

    A determinate bar at zero is an empty trough. An indeterminate one is a
    block sitting at the start - it has swept back, not emptied. Written
    down because the checklist asked a person to confirm the trough went
    empty after stop(), which would have failed correct behaviour.
    """
    span = 24
    determinate = Progressbar(root, length=span, value=0)
    assert determinate._filled_cells(span) == (0, 0)

    indeterminate = Progressbar(root, length=span, mode="indeterminate", value=0)
    start, count = indeterminate._filled_cells(span)
    assert (start, count) == (0, span // 4)


# ======================================================================
# Combobox
# ======================================================================
#
# Every value below was measured against Tk 9.0.2 before it was asserted.


@pytest.fixture
def combobox(root):
    box = Combobox(root, name="cb", values=["alpha", "beta", "gamma"])
    box.place(x=0, y=0, width=20)
    root.update_layout()
    return box


@pytest.mark.parametrize("factory", [Entry, Combobox], ids=["entry", "combobox"])
def test_a_themed_entry_validates_when_the_focus_leaves(root, factory):
    """The themed widgets bind their own focus handlers, under their own class.

    So they are their own wiring, and this is the mutation that proved it: with
    ttk's two binds pointed at a handler that does nothing, every classic Entry
    test still passed. A themed widget with no focus validation is exactly the
    gap TkCurses-jd1 was about, one layer up.
    """
    log = []
    other = factory(root, name="other")
    subject = factory(
        root,
        name="subject",
        validate="focusout",
        validatecommand=lambda proposed: log.append(proposed) or False,
    )
    for widget in (other, subject):
        widget.place(x=0, y=0, width=20)
    root.update_layout()
    subject.insert(0, "abc")

    other.focus_set()
    subject.focus_set()
    del log[:]
    other.focus_set()
    assert log == ["abc"], "the themed widget never validated on focus out"
    assert subject.get() == "abc", "a focus refusal does not change the text"


def test_a_combobox_reports_the_themed_class(combobox):
    assert combobox.winfo_class() == "TCombobox"


def test_an_empty_combobox_has_no_current_index(combobox):
    """Minus one, not zero and not None. The value most likely to be guessed
    wrong, and the one Tk actually gives.
    """
    assert combobox.get() == ""
    assert combobox.current() == -1


def test_current_selects_by_index(combobox):
    combobox.current(1)
    assert combobox.get() == "beta"
    assert combobox.current() == 1


def test_current_is_minus_one_for_a_value_not_in_the_list(combobox):
    combobox.set("typed-in")
    assert combobox.current() == -1


def test_setting_a_listed_value_moves_the_index_to_it(combobox):
    combobox.set("gamma")
    assert combobox.current() == 2


# ------------------------------------------------- set(): Combobox, Spinbox
#
# One routine in Tk - EntrySetValue - and measured against Tk 9.0.2 it is
# nothing like delete-then-insert. TkCurses-elb.

SETTABLE = pytest.mark.parametrize("cls", [Combobox, Spinbox], ids=lambda c: c.__name__)


@SETTABLE
def test_set_replaces_the_text_and_returns_none(root, cls):
    widget = cls(root)
    widget.insert(0, "old")
    assert widget.set(5) is None
    assert widget.get() == "5"


@SETTABLE
def test_set_is_not_validated(root, cls):
    """A validator refusing everything is not even asked, and the value lands."""
    asked = []
    widget = cls(
        root, validate="all", validatecommand=lambda *_: asked.append(1) or False
    )
    widget.set("anything")
    assert widget.get() == "anything"
    assert asked == []


@SETTABLE
@pytest.mark.parametrize("state", ["readonly", "disabled"])
def test_set_ignores_the_state(root, cls, state):
    widget = cls(root, state=state)
    widget.set("taken")
    assert widget.get() == "taken"


@SETTABLE
def test_set_writes_the_textvariable(root, cls):
    variable = tkcurses.StringVar(root)
    widget = cls(root, textvariable=variable)
    widget.set("shared")
    assert variable.get() == "shared"


@SETTABLE
def test_set_keeps_the_cursor_and_selection_clamped(root, cls):
    """Measured: cursor 4 and selection 1-4 over "hello" read 2 and 1-2."""
    widget = cls(root)
    widget.set("hello")
    widget.icursor(4)
    widget.selection_range(1, 4)
    widget.set("ab")
    assert widget.index("insert") == 2
    assert (widget.index("sel.first"), widget.index("sel.last")) == (1, 2)


def test_a_spinbox_set_ignores_the_range(root):
    spinbox = Spinbox(root, from_=0, to=10)
    spinbox.set(99)
    assert spinbox.get() == "99"


def test_picking_from_the_dropdown_selects_the_value_with_the_cursor_after_it(
    combobox,
):
    """Tk's ttk::combobox::SelectEntry: current, select all, cursor to end."""
    combobox._post()
    combobox._listbox.selection_set(1)
    combobox._pick()
    assert combobox.get() == "beta"
    assert (combobox.index("sel.first"), combobox.index("sel.last")) == (0, 4)
    assert combobox.index("insert") == 4


def test_current_out_of_range_is_refused(combobox):
    with pytest.raises(TclError, match="out of range"):
        combobox.current(9)


def test_reconfiguring_the_values_keeps_the_current_one(combobox):
    combobox.current(1)
    combobox.configure(values=["alpha", "beta", "gamma", "delta"])
    assert combobox.current() == 1
    assert combobox.get() == "beta"


def test_values_come_back_as_a_tuple(combobox):
    """Tk hands back a tuple; a list would break ``cget("values") + (x,)``."""
    assert combobox.cget("values") == ("alpha", "beta", "gamma")


def test_the_defaults_match_tk(combobox):
    assert combobox.cget("height") == 10
    assert combobox.cget("justify") == "left"
    assert combobox.cget("exportselection") == 1
    assert combobox.cget("postcommand") is None


# ------------------------------------------------------ the selected event


def test_neither_set_nor_current_fires_the_selected_event(combobox):
    """The fact this widget is most likely to get wrong.

    Measured with a binding installed and the loop pumped: setting the value,
    by either route, never fires ``<<ComboboxSelected>>``. It is a gesture -
    somebody picked from the list - and not a value change, so an application
    watching it to learn the value moved will miss every programmatic one, in
    Tk exactly as here.
    """
    fired = []
    combobox.bind("<<ComboboxSelected>>", lambda event: fired.append(combobox.get()))

    combobox.set("beta")
    combobox.current(2)

    assert fired == []


# -------------------------------------------------------------- the states


def test_a_readonly_combobox_refuses_typing(combobox):
    combobox.state(["readonly"])
    assert combobox._editable is False


def test_a_disabled_combobox_refuses_typing(combobox):
    combobox.state(["disabled"])
    assert combobox._editable is False


def test_an_ordinary_combobox_takes_typing(combobox):
    assert combobox._editable is True


# ======================================================================
# Notebook
# ======================================================================


@pytest.fixture
def notebook(root):
    book = Notebook(root, name="nb")
    book.place(x=0, y=0, width=40, height=10)
    pages = [tkcurses.Frame(book, name=f"p{index}") for index in range(3)]
    for index, page in enumerate(pages):
        book.add(page, text=f"T{index}")
    root.update_layout()
    book.pages = pages
    return book


def test_a_notebook_reports_the_themed_class(notebook):
    assert notebook.winfo_class() == "TNotebook"


def test_the_first_tab_added_is_selected(notebook):
    assert notebook.index("current") == 0
    assert notebook.select().endswith("p0")


def test_selecting_moves_the_current_index(notebook):
    notebook.select(1)
    assert notebook.index("current") == 1


def test_selecting_by_widget_works_too(notebook):
    notebook.select(notebook.pages[2])
    assert notebook.index("current") == 2


def test_selecting_fires_the_tab_changed_event(notebook):
    """The opposite of Combobox, and measured: a programmatic select() does
    fire ``<<NotebookTabChanged>>``, where set() on a combobox fires nothing.
    They are not one convention.
    """
    fired = []
    notebook.bind("<<NotebookTabChanged>>", lambda event: fired.append(True))

    notebook.select(1)

    assert fired == [True]


def test_selecting_the_selected_tab_fires_nothing(notebook):
    """It fires on a change, not on a call."""
    notebook.select(1)
    fired = []
    notebook.bind("<<NotebookTabChanged>>", lambda event: fired.append(True))

    notebook.select(1)

    assert fired == []


def test_index_end_counts_the_tabs(notebook):
    assert notebook.index("end") == 3


def test_an_index_out_of_bounds_is_refused(notebook):
    with pytest.raises(TclError, match="out of bounds"):
        notebook.select(9)


def test_hiding_keeps_the_tab_in_the_list(notebook):
    """hide is not forget. Measured: a hidden tab stays in tabs() and in
    index("end") - it stops being shown, not being managed.
    """
    notebook.hide(1)

    assert len(notebook.tabs()) == 3
    assert notebook.index("end") == 3


def test_hiding_the_selected_tab_moves_the_selection(notebook):
    notebook.select(1)

    notebook.hide(1)

    assert notebook.index("current") != 1


def test_adding_a_hidden_tab_again_un_hides_it_in_place(notebook):
    """Rather than appending a second copy of the same page."""
    notebook.hide(1)

    notebook.add(notebook.pages[1])

    assert notebook.index("end") == 3
    assert [notebook.tab(i, "text") for i in range(3)] == ["T0", "T1", "T2"]


def test_forget_removes_the_tab(notebook):
    notebook.forget(1)

    assert notebook.index("end") == 2
    assert [notebook.tab(i, "text") for i in range(2)] == ["T0", "T2"]


def test_the_selected_page_survives_a_tab_being_removed_before_it(notebook):
    """Measured on Tk 9.0.2: forgetting a tab before the selected one leaves
    the same page selected and shifts its index down. Holding an index
    across a mutation names the wrong page, which is why the selection is
    kept as the tab itself.
    """
    notebook.select(2)

    notebook.forget(0)

    assert notebook.index("current") == 1
    assert notebook.select().endswith("p2")


def test_insert_puts_a_page_in_the_middle(notebook):
    extra = tkcurses.Frame(notebook, name="extra")

    notebook.insert(1, extra, text="Mid")

    assert [notebook.tab(i, "text") for i in range(4)] == ["T0", "Mid", "T1", "T2"]


def test_tab_reads_and_writes_its_options(notebook):
    assert notebook.tab(0, "text") == "T0"

    notebook.tab(0, text="Renamed")

    assert notebook.tab(0, "text") == "Renamed"


def test_tab_answers_with_every_option(notebook):
    assert sorted(notebook.tab(0)) == [
        "compound",
        "image",
        "padding",
        "state",
        "sticky",
        "text",
        "underline",
    ]


def test_an_unknown_tab_option_is_refused(notebook):
    with pytest.raises(TclError, match="unknown option"):
        notebook.tab(0, nonsense=1)


def test_only_the_selected_page_is_mapped(notebook):
    """The others are taken off screen rather than merely left out of the
    layout: leaving the layout does not hide a window. What that looks like
    on a real screen is asserted in the tty tests, where there is one.
    """
    notebook.select(0)

    assert notebook.pages[0]._mapped is True
    assert notebook.pages[1]._mapped is False
    assert notebook.pages[2]._mapped is False


# ======================================================================
# Treeview
# ======================================================================


@pytest.fixture
def tree(root):
    view = Treeview(root, name="tv", columns=("size",))
    view.place(x=0, y=0, width=40, height=10)
    root.update_layout()
    return view


@pytest.fixture
def filled(tree):
    """Alpha with a child, then Beta."""
    alpha = tree.insert("", "end", text="Alpha", values=("10",))
    child = tree.insert(alpha, "end", text="Child")
    beta = tree.insert("", "end", text="Beta")
    tree.ids = (alpha, child, beta)
    return tree


def test_a_treeview_reports_treeview_not_ttreeview(tree):
    """The one themed widget without the T, measured rather than assumed.

    Binding tags name one class, so a widget reporting the wrong name gets
    no class bindings at all - the trap that has bitten five times in this
    library. Here the spelling itself is the trap.
    """
    assert tree.winfo_class() == "Treeview"


def test_insert_returns_a_generated_id(tree):
    assert tree.insert("", "end", text="One").startswith("I")


def test_insert_takes_a_given_id(tree):
    assert tree.insert("", "end", iid="mine", text="One") == "mine"


def test_a_duplicate_id_is_refused(tree):
    tree.insert("", "end", iid="mine")
    with pytest.raises(TclError, match="already exists"):
        tree.insert("", "end", iid="mine")


def test_children_and_parent_describe_the_tree(filled):
    alpha, child, beta = filled.ids
    assert filled.get_children("") == (alpha, beta)
    assert filled.get_children(alpha) == (child,)
    assert filled.parent(child) == alpha
    assert filled.parent(alpha) == ""


def test_index_is_the_position_among_siblings(filled):
    _alpha, _child, beta = filled.ids
    assert filled.index(beta) == 1


def test_next_and_prev_walk_the_siblings(filled):
    alpha, _child, beta = filled.ids
    assert filled.next(alpha) == beta
    assert filled.prev(beta) == alpha
    assert filled.next(beta) == ""


def test_set_reads_and_writes_one_cell(filled):
    alpha = filled.ids[0]
    assert filled.set(alpha, "size") == "10"

    filled.set(alpha, "size", "20")

    assert filled.set(alpha, "size") == "20"


def test_item_reads_and_writes_options(filled):
    alpha = filled.ids[0]
    assert filled.item(alpha, "text") == "Alpha"

    filled.item(alpha, text="Renamed")

    assert filled.item(alpha, "text") == "Renamed"


def test_an_unknown_item_option_is_refused(filled):
    with pytest.raises(TclError, match="unknown option"):
        filled.item(filled.ids[0], nonsense=1)


# ------------------------------------------------------- detach and delete


def test_detach_keeps_the_item_in_existence(filled):
    """The whole difference between detach and delete, measured against Tk."""
    _alpha, _child, beta = filled.ids

    filled.detach(beta)

    assert filled.exists(beta) is True
    assert beta not in filled.get_children("")


def test_move_puts_a_detached_item_back(filled):
    _alpha, _child, beta = filled.ids
    filled.detach(beta)

    filled.move(beta, "", 0)

    assert filled.get_children("")[0] == beta


def test_delete_makes_the_item_stop_existing(filled):
    _alpha, _child, beta = filled.ids

    filled.delete(beta)

    assert filled.exists(beta) is False


def test_deleting_a_branch_takes_its_children(filled):
    alpha, child, _beta = filled.ids

    filled.delete(alpha)

    assert filled.exists(child) is False


def test_move_reparents(filled):
    alpha, _child, beta = filled.ids

    filled.move(beta, alpha, 0)

    assert filled.get_children(alpha)[0] == beta
    assert beta not in filled.get_children("")


# ----------------------------------------------------------- the events


def test_selection_set_fires_every_time_even_for_a_no_op(filled):
    """Measured, and the opposite of the notebook.

    ``<<NotebookTabChanged>>`` fires only on a real change;
    ``<<TreeviewSelect>>`` fires whenever it is asked, unchanged selection
    included. Three widgets in this cycle, three different rules - none of
    them can be guessed from another.
    """
    fired = []
    filled.bind("<<TreeviewSelect>>", lambda event: fired.append(True))

    filled.selection_set(filled.ids[2])
    filled.selection_set(filled.ids[2])

    assert fired == [True, True]


def test_opening_an_item_programmatically_fires_nothing(filled):
    """``<<TreeviewOpen>>`` is a gesture event, like the combobox's."""
    fired = []
    filled.bind("<<TreeviewOpen>>", lambda event: fired.append(True))

    filled.item(filled.ids[0], open=True)

    assert fired == []


def test_selection_add_and_remove(filled):
    alpha, _child, beta = filled.ids
    filled.selection_set(alpha)

    filled.selection_add(beta)
    assert set(filled.selection()) == {alpha, beta}

    filled.selection_remove(alpha)
    assert filled.selection() == (beta,)


def test_focus_reads_and_writes_the_current_row(filled):
    assert filled.focus() == ""

    filled.focus(filled.ids[0])

    assert filled.focus() == filled.ids[0]


# ------------------------------------------------------------ what is drawn


def test_a_closed_branch_hides_its_children(filled):
    alpha, child, beta = filled.ids

    assert filled._visible() == [alpha, beta]

    filled.item(alpha, open=True)

    assert filled._visible() == [alpha, child, beta]


def test_a_detached_row_is_not_drawn(filled):
    _alpha, _child, beta = filled.ids

    filled.detach(beta)

    assert beta not in filled._visible()


def test_see_opens_whatever_hides_the_row(filled):
    alpha, child, _beta = filled.ids
    assert child not in filled._visible()

    filled.see(child)

    assert filled.item(alpha, "open")
    assert child in filled._visible()


# ======================================================================
# LabeledScale
# ======================================================================


@pytest.fixture
def labeled(root):
    widget = LabeledScale(root, name="ls", from_=0, to=10)
    widget.place(x=0, y=0, width=20, height=2)
    root.update_layout()
    return widget


def test_a_labeled_scale_is_a_frame(labeled):
    """Measured: it reports TFrame, because that is what it is - a composite
    of two ordinary widgets rather than a widget class of its own. Nothing
    is bound to a class called TLabeledScale, here or in Tk.
    """
    assert labeled.winfo_class() == "TFrame"


def test_it_has_a_label_and_a_scale(labeled):
    assert labeled.label.winfo_exists()
    assert labeled.scale.winfo_exists()


def test_the_label_starts_at_the_low_end(labeled):
    assert labeled.value == 0
    assert labeled.label.cget("text") == "0"


def test_setting_the_value_moves_both_halves(labeled):
    labeled.value = 7

    assert labeled.label.cget("text") == "7"
    assert labeled.scale.get() == 7


def test_moving_the_scale_moves_the_label(labeled):
    """The whole of what this widget adds over a scale on its own."""
    labeled.scale.set(3)

    assert labeled.value == 3
    assert labeled.label.cget("text") == "3"


def test_constructing_overwrites_the_variable_it_is_given(root):
    """Measured on Tk 9.0.2, and in tkinter's own source as
    ``self._variable.set(from_)``: a variable holding 5, handed to a scale
    running from 2, comes back holding 2.

    Surprising, and copied rather than corrected - the same program against
    tkinter sees the same thing, and a library that quietly disagreed would
    be the harder one to reason about.
    """
    shared = tkcurses.IntVar(root, value=5)

    LabeledScale(root, name="ls", variable=shared, from_=2, to=10)

    assert shared.get() == 2


def test_the_variable_drives_the_widget(root):
    shared = tkcurses.IntVar(root, value=0)
    widget = LabeledScale(root, name="ls", variable=shared, from_=0, to=10)
    widget.place(x=0, y=0, width=20, height=2)
    root.update_layout()

    shared.set(9)

    assert widget.value == 9
    assert widget.label.cget("text") == "9"


def test_the_widget_writes_the_variable_back(root):
    shared = tkcurses.IntVar(root, value=0)
    widget = LabeledScale(root, name="ls", variable=shared, from_=0, to=10)

    widget.value = 4

    assert shared.get() == 4


def test_compound_top_puts_the_label_above(labeled):
    assert labeled.label._rect.y < labeled.scale._rect.y


def test_compound_bottom_puts_the_label_below(root):
    widget = LabeledScale(root, name="b", from_=0, to=5, compound="bottom")
    widget.place(x=0, y=0, width=20, height=2)
    root.update_layout()

    assert widget.label._rect.y > widget.scale._rect.y


# ======================================================================
# OptionMenu
# ======================================================================


@pytest.fixture
def chosen(root):
    return tkcurses.StringVar(root)


@pytest.fixture
def options(root, chosen):
    widget = OptionMenu(root, chosen, "beta", "alpha", "beta", "gamma", name="om")
    widget.place(x=0, y=0, width=16)
    root.update_layout()
    return widget


def test_an_option_menu_reports_tmenubutton(options):
    """Like LabeledScale being a TFrame: a menubutton with a constructor
    that fills its menu, rather than a widget class of its own.
    """
    assert options.winfo_class() == "TMenubutton"


def test_its_bindings_land_under_the_class_it_reports(options, root):
    """The trap that has bitten five times, avoided here for free.

    Menubutton registers its class bindings under ``winfo_class()`` rather
    than the literal name - the cure that was put in when this exact widget
    first hit it - so the themed variant is bound without doing anything.
    """
    assert "TMenubutton" in options.bindtags()
    assert root.tk.bindings.sequences("TMenubutton")


def test_the_default_becomes_the_value(options, chosen):
    assert chosen.get() == "beta"
    assert options.cget("text") == "beta"


def test_the_menu_holds_every_value(options):
    menu = options.cget("menu")
    labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)]
    assert labels == ["alpha", "beta", "gamma"]


def test_the_variable_drives_the_text(options, chosen):
    chosen.set("gamma")
    assert options.cget("text") == "gamma"


def test_choosing_an_entry_sets_the_variable(options, chosen):
    options.cget("menu").invoke(0)

    assert chosen.get() == "alpha"
    assert options.cget("text") == "alpha"


def test_the_command_is_called_with_the_chosen_value(root):
    called = []
    widget = OptionMenu(
        root,
        tkcurses.StringVar(root),
        "a",
        "a",
        "b",
        command=called.append,
        name="om2",
    )

    widget.cget("menu").invoke(1)

    assert called == ["b"]


def test_a_default_of_none_leaves_the_button_blank(root):
    """Measured, and the clearest difference from the classic widget, which
    refuses to be built with nothing to show.
    """
    widget = OptionMenu(root, tkcurses.StringVar(root), None, "one", "two", name="om3")

    assert widget.cget("text") == ""
    menu = widget.cget("menu")
    assert [menu.entrycget(i, "label") for i in range(2)] == ["one", "two"]


def test_no_values_at_all_is_accepted(root):
    """The classic one raises here. Measured: ttk's does not."""
    assert OptionMenu(root, tkcurses.StringVar(root), name="om4") is not None


def test_set_menu_takes_the_default_first_and_positionally(root):
    """ttk's shape, and not the classic widget's - which takes it as a
    keyword, so a call written for one means something else to the other.
    """
    widget = OptionMenu(root, tkcurses.StringVar(root), "one", "one", name="om5")

    widget.set_menu("two", "one", "two")

    assert widget.cget("text") == "two"
    menu = widget.cget("menu")
    assert [menu.entrycget(i, "label") for i in range(2)] == ["one", "two"]


def test_the_entries_are_radiobuttons_where_the_classic_uses_commands(root, chosen):
    """Measured on Tk 9.0.2, with ``menu.type(0)``:

        ttk.OptionMenu      -> 'radiobutton'
        classic OptionMenu  -> 'command'

    Both are in this library and both are right. The classic widget's own
    comment worried about exactly this - that code asking a menu what kind
    its entries are would get a different answer than under Tk - so each one
    matches its own original rather than each other.
    """
    themed = OptionMenu(root, chosen, "a", "a", "b", name="themed")
    classic = tkcurses.OptionMenu(root, tkcurses.StringVar(root), "a", "b", name="cls")

    assert themed.cget("menu").type(0) == "radiobutton"
    assert classic.cget("menu").type(0) == "command"


# ======================================================================
# Label and Scale
# ======================================================================


def test_a_themed_label_reports_tlabel(root):
    assert Label(root, name="l", text="hi").winfo_class() == "TLabel"


def test_nothing_is_bound_to_tlabel(root):
    """A label answers no gesture, so the class-binding trap that catches
    the interactive widgets does not arise for it."""
    Label(root, name="l", text="hi")
    assert root.tk.bindings.sequences("TLabel") == ()


def test_a_themed_scale_reports_tscale(root):
    assert Scale(root, name="s", from_=0, to=10).winfo_class() == "TScale"


def test_a_themed_scale_is_bound_under_its_own_class(root):
    """The classic Scale registered its gestures under the literal "Scale",
    so a widget reporting TScale matched none of them and answered nothing.
    It registers under winfo_class() now, the cure Menubutton already
    carried for OptionMenu.
    """
    Scale(root, name="s", from_=0, to=10)
    assert root.tk.bindings.sequences("TScale")


def test_a_themed_scale_is_horizontal_by_default(root):
    """Measured: ttk's is horizontal, the classic one is vertical. A
    composite built on the wrong default draws nothing at all on one row.
    """
    assert Scale(root, name="s", from_=0, to=10).cget("orient") == "horizontal"
    assert tkcurses.Scale(root, name="c").cget("orient") == "vertical"


def test_a_themed_scale_takes_a_value_option(root):
    """Which the classic one has not - it takes a starting value only
    through set()."""
    assert Scale(root, name="s", from_=0, to=10, value=3).get() == 3


def test_a_themed_scale_leaves_its_variable_alone(root):
    """Measured on Tk 9.0.2, and the opposite of LabeledScale, which
    overwrites the variable with ``from_`` as tkinter's own source does.
    """
    shared = tkcurses.IntVar(root, value=7)

    widget = Scale(root, name="s", variable=shared, from_=0, to=10)

    assert shared.get() == 7
    assert widget.get() == 7


def test_the_labeled_scales_halves_are_themed(root):
    """TkCurses-8an. They were a classic Label and Scale while the themed
    ones did not exist, so they did not draw from the style database.
    """
    widget = LabeledScale(root, name="ls", from_=0, to=10)

    assert widget.label.winfo_class() == "TLabel"
    assert widget.scale.winfo_class() == "TScale"


# ------------------------------------------------------- the containers


def test_the_container_widgets_are_themed(root):
    assert Frame(root, name="f").winfo_class() == "TFrame"
    assert Labelframe(root, name="lf").winfo_class() == "TLabelframe"
    assert Panedwindow(root, name="pw").winfo_class() == "TPanedwindow"


def test_each_container_has_ttks_second_spelling():
    """``LabelFrame`` and ``Labelframe`` are one class, as in tkinter.

    Measured: ``ttk.LabelFrame is ttk.Labelframe`` is True on Tk 9.0, and the
    same for the PanedWindow pair. They are names for one class rather than two
    implementations, so this is identity and not a subclass - two classes could
    drift apart, and a caller using tkinter's own spelling would get the one
    that was not maintained.
    """
    assert LabelFrame is Labelframe
    assert PanedWindow is Panedwindow


# ------------------------------------------------- panes and their weights


@pytest.fixture
def themed_paned(root):
    """A horizontal themed paned window, laid out, with two panes."""
    from types import SimpleNamespace

    from tkcurses._core.geometry import Rect
    from tkcurses._core.panels import PanelStack

    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    widget = Panedwindow(root, name="p", orient="horizontal")
    widget._allocate(Rect(0, 0, 41, 10))
    widget._map()
    widget.add(Frame(widget, name="a"), weight=1)
    widget.add(Frame(widget, name="b"), weight=3)
    widget.update_layout()
    return widget


def test_a_pane_reports_the_weight_it_was_added_with(themed_paned):
    assert themed_paned.pane(0) == {"weight": 1}
    assert themed_paned.pane(1) == {"weight": 3}


def test_weight_is_the_only_pane_option_ttk_reports(themed_paned):
    """Measured against ttk 9.0: ``pane(0)`` answers ``{'weight': N}``.

    The classic widget's pane options - minsize, sticky, width, height - are
    still settable through ``paneconfigure``; they are simply not what a ttk
    pane reports.
    """
    assert list(themed_paned.pane(0)) == ["weight"]


def test_a_pane_can_be_named_by_position_path_or_widget(themed_paned):
    """``panes()`` answers PATHS, which is what Tk does and what caught a bug.

    The weights were first keyed by the widget object, so ``pane(0)`` looked a
    path up in a dict of widgets and reported the pane as not managed here.
    """
    by_position = themed_paned.pane(1)
    by_path = themed_paned.pane(themed_paned.panes()[1])
    by_widget = themed_paned.pane(themed_paned._paned.slaves()[1])
    assert by_position == by_path == by_widget == {"weight": 3}


def test_a_weight_defaults_to_nought(themed_paned):
    """ttk's default, and it means "do not resize" there."""
    themed_paned.add(Frame(themed_paned, name="c"))
    assert themed_paned.pane(2) == {"weight": 0}


def test_a_weight_can_be_changed_afterwards(themed_paned):
    themed_paned.pane(0, weight=5)
    assert themed_paned.pane(0) == {"weight": 5}


def test_a_pane_that_is_not_here_is_refused(themed_paned, root):
    with pytest.raises(TclError):
        themed_paned.pane(Frame(root, name="stray"))
    with pytest.raises(TclError):
        themed_paned.pane(99)


@pytest.fixture
def themed_root(root):
    """A root a paned window can be allocated and laid out in."""
    from types import SimpleNamespace

    from tkcurses._core.geometry import Rect
    from tkcurses._core.panels import PanelStack

    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 100, 30)
    root._mapped = True
    return root


def _grown_by(root, weights, narrow, wide):
    """How much each pane of a themed paned window gains between two widths."""
    from tkcurses._core.geometry import Rect

    def widths(width):
        pw = Panedwindow(root, name=f"pw{width}{len(weights)}", orient="horizontal")
        pw._allocate(Rect(0, 0, width, 8))
        pw._map()
        for index, weight in enumerate(weights):
            pane = Frame(pw, name=f"p{width}{index}")
            if weight is None:
                pw.add(pane)
            else:
                pw.add(pane, weight=weight)
        pw.update_layout()
        return [child.winfo_width() for child in pw._paned.slaves()]

    before, after = widths(narrow), widths(wide)
    return [b - a for a, b in zip(before, after, strict=True)]


@pytest.mark.parametrize(
    ("weights", "grown"),
    [
        ([1, 3], [3, 9]),
        ([2, 1, 1], [6, 3, 3]),
        ([0, 1], [0, 12]),
        # All weights zero is ttk's DEFAULT and does not mean "nobody moves":
        # measured, the last pane takes the lot.
        ([0, 0], [0, 12]),
        ([0, 0, 0], [0, 0, 12]),
    ],
)
def test_surplus_space_is_divided_by_weight(themed_root, weights, grown):
    """ttk's rule, measured on Tk 9.0 before any of it was written.

    A horizontal ttk.Panedwindow grown by 100 pixels::

        weights [1, 3]      panes grew by [25, 75]
        weights [2, 1, 1]                 [50, 25, 25]
        weights [0, 1]                    [0, 100]
        weights [0, 0]                    [0, 100]
        weights [0, 0, 0]                 [0, 0, 100]

    The issue that asked for this predicted that all-zero weights would leave
    the panes alone. They do not: the last one absorbs everything, and since
    zero is the default that is the case most code will meet.

    This was a strict xfail from the day the widget was added, so fixing the
    layout turned the suite red with XPASS(strict) rather than leaving a stale
    marker claiming the feature was missing.
    """
    assert _grown_by(themed_root, weights, 30, 42) == grown


def test_an_unweighted_paned_window_follows_stretch_not_weights(themed_root):
    """The CLASSIC widget shares room by ``stretch``, never by weight.

    Weights are what the themed widget adds, and the two widgets live in one
    layout engine, so a weight leaking into the classic one would go unseen.
    The claim this used to hold - that the classic widget spreads surplus
    evenly, "what Tk's own -stretch middle default does" - was wrong twice
    over: Tk's default is ``last``, measured in TkCurses-g60s.

    Driven through a real tkcurses.PanedWindow, not through distribute() with the
    weights left out. The first version did the latter and was worthless:
    sizes() passes a LIST OF NONES for a classic window, so a mutation making
    "no weight named" count as weight zero - which hands everything to the last
    pane - left that test green. Found by making exactly that mutation.
    """
    from tkcurses._core.geometry import Rect

    def widths(width):
        pw = tkcurses.PanedWindow(
            themed_root, name=f"classic{width}", orient="horizontal"
        )
        pw._allocate(Rect(0, 0, width, 8))
        pw._map()
        for index in range(3):
            pw.add(
                tkcurses.Label(pw, name=f"c{width}{index}", text="pane"),
                stretch="always",
            )
        pw.update_layout()
        return [child.winfo_width() for child in pw._paned.slaves()]

    # TkCurses-g60s: the classic widget now follows Tk's -stretch, whose
    # default gives everything to the last pane; "always" shares it by size,
    # and three equal panes grow alike.
    grown = [b - a for a, b in zip(widths(30), widths(42), strict=True)]
    assert grown == [4, 4, 4], (
        f"a classic paned window shared its surplus as {grown} rather than "
        "by stretch - weights have leaked into the widget that has no such option"
    )


def test_shortfall_follows_the_weights_too(themed_root):
    """Measured: [1, 3] shrinking by 100 gives up [25, 75]."""
    assert _grown_by(themed_root, [1, 3], 42, 30) == [-3, -9]


def test_a_sash_is_read_and_moved_as_one_number(themed_paned):
    """``sashpos`` is ttk's one-dimensional sash, not a rename.

    The classic widget offers ``sash_coord`` and ``sash_place``, which are
    two-dimensional. A ttk paned window takes and gives the single number
    along its own orientation.
    """
    themed_paned.sashpos(0, 12)
    assert themed_paned.sashpos(0) == 12
    x, _ = themed_paned.sash_coord(0)
    assert x == 12


def test_a_vertical_sash_is_measured_down_the_other_axis(root):
    from types import SimpleNamespace

    from tkcurses._core.geometry import Rect
    from tkcurses._core.panels import PanelStack

    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    widget = Panedwindow(root, name="v", orient="vertical")
    widget._allocate(Rect(0, 0, 20, 15))
    widget._map()
    widget.add(Frame(widget, name="a"))
    widget.add(Frame(widget, name="b"))
    widget.update_layout()
    widget.sashpos(0, 6)
    assert widget.sashpos(0) == 6
    _, y = widget.sash_coord(0)
    assert y == 6


# --------------------------------------------------- the four that answer


@pytest.fixture
def pressable_root(root):
    """A root a button can be pressed in, as test_button.py sets one up."""
    from types import SimpleNamespace

    from tkcurses._core.geometry import Rect
    from tkcurses._core.panels import PanelStack

    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 40, 12)
    root._mapped = True
    return root


def test_the_four_gesture_widgets_are_themed(root):
    assert Button(root, name="b").winfo_class() == "TButton"
    assert Checkbutton(root, name="c").winfo_class() == "TCheckbutton"
    assert Radiobutton(root, name="r").winfo_class() == "TRadiobutton"
    assert Menubutton(root, name="m").winfo_class() == "TMenubutton"


@pytest.mark.parametrize(
    ("factory", "tag"),
    [
        (Button, "TButton"),
        (Checkbutton, "TCheckbutton"),
        (Radiobutton, "TRadiobutton"),
        (Menubutton, "TMenubutton"),
    ],
)
def test_a_themed_widget_binds_under_its_own_tag(pressable_root, factory, tag):
    """Each installs class bindings under the themed name, not the classic one.

    Measured on Tk 9.0: ``ttk.Button``'s bindtags are
    ``('.!button', 'TButton', '.', 'all')``. ``Button`` is absent, so nothing
    bound to the classic name reaches it - which is why each of these has to
    register its own, and why a widget that registered under the wrong tag
    would answer nothing at all.
    """
    widget = factory(pressable_root, name="w", text="OK")
    assert widget.bindtags()[1] == tag
    assert tag in pressable_root.tk.bound_classes
    assert "Button" not in widget.bindtags()


def test_a_themed_button_answers_a_press(pressable_root):
    """The gesture actually arrives, not merely a tag in a list.

    Asserted through the recovery timer the press handler sets, as
    test_button.py's press tests do: invoking on release also needs the
    pointer inside a laid-out widget, which would make a failure ambiguous.
    """
    button = Button(pressable_root, name="b", text="OK")
    button.event_generate("<Button-1>", x=0, y=0)
    assert getattr(button, "_press_recovery", None) is not None


def test_a_themed_checkbutton_toggles_on_the_space_bar(pressable_root):
    """Space and not Return, which is _ChoiceWidget's rule and ttk's.

    Return is left alone so it still reaches a dialog's default button from
    wherever the focus happens to be.
    """
    variable = tkcurses.IntVar(pressable_root, 0)
    box = Checkbutton(pressable_root, name="c", text="tick", variable=variable)
    box.event_generate("<Key-space>")
    assert variable.get() == 1
    box.event_generate("<Key-Return>")
    assert variable.get() == 1, "Return must be left for a dialog's default button"


def test_the_variable_defaults_match_the_classic_widget(pressable_root):
    """Measured against ttk 9.0 rather than inherited on faith.

    The issue behind this widget suspected ttk of differing from the classic
    one here. It does not: onvalue and offvalue are 1 and 0 in both, and a
    radiobutton's default variable is ``selectedButton`` in both - ttk reports
    it fully qualified, ``::selectedButton``, which is the same global under
    Tcl's namespace rules.
    """
    box = Checkbutton(pressable_root, name="c")
    assert box.cget("onvalue") == 1
    assert box.cget("offvalue") == 0


def test_a_themed_radiobutton_shares_the_default_variable(pressable_root):
    """Two radiobuttons with no variable named are in one group, as in Tk."""
    first = Radiobutton(pressable_root, name="r1", text="a", value="a")
    second = Radiobutton(pressable_root, name="r2", text="b", value="b")
    shared = first._options["variable"]
    assert shared is second._options["variable"], (
        "the two radiobuttons were given separate variables, so choosing one "
        "would not unchoose the other"
    )
    first.invoke()
    assert shared.get() == "a"
    second.invoke()
    assert shared.get() == "b"


# ----------------------------------------------------------------- padding


@pytest.fixture
def padded_root(root):
    """A root a container can be allocated and mapped in."""
    from types import SimpleNamespace

    from tkcurses._core.geometry import Rect
    from tkcurses._core.panels import PanelStack

    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 30)
    root._mapped = True
    return root


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (None, (0, 0, 0, 0)),
        ("", (0, 0, 0, 0)),
        (5, (5, 5, 5, 5)),
        ("5", (5, 5, 5, 5)),
        ("2 8", (2, 8, 2, 8)),
        ("2 8 20", (2, 8, 20, 8)),
        ("2 8 20 30", (2, 8, 20, 30)),
        ((1, 2), (1, 2, 1, 2)),
    ],
)
def test_padding_follows_tks_side_order(given, expected):
    """Left, top, right, bottom - measured on real ttk, not recalled.

    A 200x120 ttk.Frame with a child filling it, Tk 9.0::

        padding="5"         child at 5,5    sized 190x110
        padding="2 8"       child at 2,8    sized 196x104
        padding="2 8 20"    child at 2,8    sized 178x104
        padding="2 8 20 30" child at 2,8    sized 178x82

    So right defaults to left and bottom to top, and the pairs are NOT
    horizontal-then-vertical the way padx/pady would suggest.
    """
    insets = parse_padding(given)
    assert (insets.left, insets.top, insets.right, insets.bottom) == expected


@pytest.mark.parametrize("given", ["oops", -3, ["a"], object()])
def test_an_unparseable_padding_is_no_padding(given):
    """Rather than an exception from inside a layout pass.

    Tk itself raises on a malformed pad, and matching that is worth doing one
    day; drawing nothing because of it is not. The first version of the parser
    guarded only the sequence form and let a malformed STRING raise, while its
    docstring promised otherwise.
    """
    assert parse_padding(given) == tkcurses._core.geometry.Insets()


def test_padding_shrinks_what_a_themed_container_offers(padded_root):
    """The option does something, which is the whole of TkCurses-avy.

    Five widgets declared -padding and none honoured it, so code written for ttk
    got no error and no padding and a layout quietly one or two cells out.
    """
    from tkcurses._core.geometry import Rect

    plain = Frame(padded_root, name="plain", relief="flat")
    plain._allocate(Rect(0, 0, 20, 10))
    plain._map()
    assert (plain._content_rect().width, plain._content_rect().height) == (20, 10)

    padded = Frame(padded_root, name="padded", relief="flat", padding="1 2 3 4")
    padded._allocate(Rect(0, 0, 20, 10))
    padded._map()
    content = padded._content_rect()
    assert (content.x, content.y) == (1, 2), "the top-left moves in by left, top"
    assert (content.width, content.height) == (20 - 1 - 3, 10 - 2 - 4)


def test_a_padded_container_asks_its_parent_for_the_room(padded_root):
    """``_outer_size`` agrees with ``_content_rect``, or children are clipped.

    The two halves of a container's arithmetic: one places the children, the
    other asks the parent for space. They now share ``_content_padding`` because
    two places computing the same thing is how the scrollbar came to draw seven
    of its nine rows.
    """
    from tkcurses._core.geometry import Rect, Size

    padded = Frame(padded_root, name="p", relief="flat", padding="1 2 3 4")
    padded._allocate(Rect(0, 0, 20, 10))
    padded._map()
    outer = padded._outer_size(Size(5, 5))
    assert (outer.width, outer.height) == (5 + 1 + 3, 5 + 2 + 4)


def test_padding_adds_to_padx_and_pady_rather_than_replacing_them(padded_root):
    """A themed widget still answers to both, and a caller meant each."""
    from tkcurses._core.geometry import Rect

    both = Frame(padded_root, name="both", relief="flat", padding=1, padx=2, pady=3)
    both._allocate(Rect(0, 0, 20, 20))
    both._map()
    content = both._content_rect()
    assert (content.x, content.y) == (2 + 1, 3 + 1)


@pytest.mark.parametrize(
    "widget", [Label, Button, Checkbutton, Radiobutton, Menubutton]
)
def test_padding_enlarges_a_widget_whose_content_is_its_text(padded_root, widget):
    """Measured on Tk 9.0.2 with padding=9: Label 50x21 -> 68x39, Checkbutton
    72x23 -> 88x39, Button 83x30 -> 95x42. Tk's padding replaces the theme's
    own, a pixel or three, which is no cell here, so here it is added."""
    plain = widget(padded_root, text="Sample")
    padded = widget(padded_root, text="Sample", padding="1 2 3 4")
    assert padded.winfo_reqwidth() == plain.winfo_reqwidth() + 1 + 3
    assert padded.winfo_reqheight() == plain.winfo_reqheight() + 2 + 4
    plain.configure(padding=2)
    assert plain.winfo_reqwidth() == padded.winfo_reqwidth()
    assert plain.winfo_reqheight() == padded.winfo_reqheight() - 2


@pytest.mark.parametrize(
    "widget", [Label, Button, Checkbutton, Radiobutton, Menubutton]
)
def test_padding_moves_a_widgets_text_in_from_its_left_and_top(padded_root, widget):
    from tkcurses._core.geometry import Rect

    plain = widget(padded_root, text="Sample")
    padded = widget(padded_root, text="Sample", padding="1 2 3 4")
    for each in (plain, padded):
        each._allocate(Rect(0, 0, each.winfo_reqwidth(), each.winfo_reqheight()))
    before, after = plain._text_area(), padded._text_area()
    assert (after.x, after.y) == (before.x + 1, before.y + 2)
    assert (after.width, after.height) == (before.width, before.height)


# ------------------------------------------------- Treeview -striped (xe9.4)
#
# Tk 9.0's alternating row tint. Measured: a boolean, default 0, rejecting
# anything else with 'expected boolean value but got "..."' - and the COLOUR
# comes from the style, not the widget: style.lookup("Treeview",
# "stripedbackground") answers '#e8e8e8' against a white background.
#
# The style is only half of it, which TkCurses-67u found: stripedbackground is
# a TAG option in Tk, and a tag's beats the style's. The tag section below
# covers that half.


def test_striped_defaults_to_off(tree):
    assert tree.cget("striped") == 0
    assert not tree._striped()


@pytest.mark.parametrize("value", [1, True, "yes", "1", "true"])
def test_striped_takes_every_spelling_of_true(tree, value):
    tree.configure(striped=value)
    assert tree._striped()


@pytest.mark.parametrize("value", [0, False, "no", "0", "false"])
def test_striped_takes_every_spelling_of_false(tree, value):
    tree.configure(striped=value)
    assert not tree._striped()


@pytest.mark.parametrize("how", ["constructor", "configure"])
def test_striped_refuses_what_is_not_a_boolean(root, how):
    """Both paths, because Tk rejects it on both and the constructor does not
    go through configure - with the check in configure alone,
    Treeview(striped='rubbish') was accepted while configure(striped='rubbish')
    raised, which no caller could have predicted."""
    with pytest.raises(TclError, match='expected boolean value but got "rubbish"'):
        if how == "constructor":
            Treeview(root, name="bad", striped="rubbish")
        else:
            Treeview(root, name="bad2").configure(striped="rubbish")


def test_the_stripe_falls_on_alternate_rows(filled):
    """Odd rows of what is on screen, so the banding does not crawl as the
    tree scrolls. Which parity Tk picks is recorded as open on the issue: its
    row element takes a -rownumber and the theme decides, which needs eyes on
    a GUI to read."""
    filled.configure(striped=1)
    rows = filled._visible()
    dim = [
        bool(filled._row_attribute(iid, offset, 0) & curses.A_DIM)
        for offset, iid in enumerate(rows)
    ]
    assert dim[::2] == [False] * len(dim[::2]), f"even rows are tinted: {dim}"
    assert dim[1::2] == [True] * len(dim[1::2]), f"odd rows are not tinted: {dim}"


def test_nothing_is_tinted_while_striped_is_off(filled):
    filled.configure(striped=0)
    for offset, iid in enumerate(filled._visible()):
        assert not filled._row_attribute(iid, offset, 0) & curses.A_DIM


def test_a_selected_row_is_reversed_and_never_tinted(filled):
    """Selection wins: reverse-and-dim together is whatever the terminal
    decides, and the selection is the more important signal. The same reasoning
    as a focused entry border dropping A_DIM before adding A_BOLD."""
    filled.configure(striped=1)
    rows = filled._visible()
    odd = rows[1]
    assert filled._row_attribute(odd, 1, 0) & curses.A_DIM, "row 1 should be tinted"
    filled.selection_set(odd)
    attribute = filled._row_attribute(odd, 1, 0)
    assert attribute & curses.A_REVERSE
    assert not attribute & curses.A_DIM, "a selected row must not also be dim"


def test_the_stripe_takes_its_colour_from_the_style_when_one_is_set(filled):
    """stripedbackground is a STYLE option in Tk, not a widget one - measured.

    With no colour manager running there is nothing to resolve, so the dim
    fallback stands; what this pins is that the style is consulted at all, so
    an application that sets the colour is not ignored.
    """
    style = Style(filled)
    style.configure("Treeview", stripedbackground="blue")
    assert style.lookup("Treeview", "stripedbackground") == "blue"
    filled.configure(striped=1)
    # No colours in this harness, so it falls back - the point is that it did
    # not raise and still marks the row.
    assert filled._row_attribute(filled._visible()[1], 1, 0) & curses.A_DIM


# ------------------------------------------- Treeview's tag API (TkCurses-67u)
#
# Measured against Tcl/Tk 9.0.2 and real tkinter on Python 3.14.7.
#
# SEVEN tag options, not the two the issue guessed, and -stripedbackground is
# among them: striping is a TAG feature in Tk, which is why this and xe9.4 are
# the same work seen from two sides.
#
# TWO DIFFERENT ORDERS, both from man ttk_treeview and neither guessable:
# a tag OPTION is resolved by CREATION order ("tags created first receive
# higher priority"), while a tag BINDING runs in the order of the ROW's own
# tags list ("for each of the item's tags option ... as per bindtags(n)").
# Anyone would assume one rule for both.

#: The first row of the fixture below, in screen coordinates: the tree shows
#: its headings by default, so row 0 is the heading and the first item is at 2.
FIRST_ROW_Y = 2


class _Recorder:
    """Stands in for the colour manager, which needs a real terminal.

    ``attribute_for`` is the only thing the row painter asks of it, so this
    records the colour pair it was asked for and hands back a marker the
    tests can see in the attribute.
    """

    MARK = 1 << 20

    def __init__(self):
        self.calls = []

    def attribute_for(self, fg, bg, attr=0):
        self.calls.append((fg, bg))
        return self.MARK


@pytest.fixture
def tagged(tree):
    """Three rows: Alpha tagged 'warn', Beta tagged 'warn' and 'cold', Gamma bare."""
    tree.ids = (
        tree.insert("", "end", text="Alpha", tags=("warn",)),
        tree.insert("", "end", text="Beta", tags=("warn", "cold")),
        tree.insert("", "end", text="Gamma"),
    )
    return tree


@pytest.fixture
def recorder(tagged):
    """``tagged``, with the colour manager replaced by a recorder."""
    tagged.tk.colors = _Recorder()
    return tagged


# ----------------------------------------------------------- tag_configure


def test_tag_configure_answers_all_seven_options(tree):
    """Seven, measured - the issue that asked for this named two."""
    assert tree.tag_configure("warn") == {
        "background": "",
        "foreground": "",
        "font": "",
        "image": "",
        "imageanchor": "",
        "padding": "",
        "stripedbackground": "",
    }


def test_tag_configure_answers_one_option(tree):
    tree.tag_configure("warn", background="red")
    assert tree.tag_configure("warn", "background") == "red"


def test_an_option_never_set_answers_empty_rather_than_raising(tree):
    tree.tag_configure("warn", background="red")
    assert tree.tag_configure("warn", "foreground") == ""


def test_the_leading_dash_is_accepted_on_both_forms(tree):
    tree.tag_configure("warn", **{"-background": "red"})
    assert tree.tag_configure("warn", "-background") == "red"


def test_setting_a_tag_option_returns_none(tree):
    assert tree.tag_configure("warn", background="red") is None


def test_tag_configure_refuses_an_unknown_option(tree):
    with pytest.raises(TclError, match='unknown option "-rubbish"'):
        tree.tag_configure("warn", rubbish="x")


def test_querying_a_tag_nobody_configured_is_not_an_error(tree):
    assert tree.tag_configure("never-mentioned")["background"] == ""


# --------------------------------------------------------------- tag_has


def test_tag_has_lists_the_rows_carrying_a_tag(tagged):
    alpha, beta, _gamma = tagged.ids
    assert tagged.tag_has("warn") == (alpha, beta)
    assert tagged.tag_has("cold") == (beta,)


def test_tag_has_answers_a_bool_when_given_a_row(tagged):
    alpha, _beta, gamma = tagged.ids
    assert tagged.tag_has("warn", alpha) is True
    assert tagged.tag_has("warn", gamma) is False


def test_a_tag_nothing_carries_is_empty_rather_than_an_error(tagged):
    """Measured: Tk answers (), it does not raise."""
    assert tagged.tag_has("nosuch") == ()


def test_a_bare_string_is_one_tag_and_not_its_characters(tree):
    """``tags="single"`` reads back from real ttk as ``('single',)``.

    Worth a test of its own rather than tidiness: iterating the string would
    have asked whether each CHARACTER was a tag, so tag_has('s') would have
    answered True for a row tagged 'single'.
    """
    iid = tree.insert("", "end", text="One", tags="single")
    assert tree.item(iid, "tags") == ("single",)
    assert tree.tag_has("single", iid) is True
    assert tree.tag_has("s", iid) is False


def test_tag_has_on_a_row_that_does_not_exist_is_false(tree):
    assert tree.tag_has("warn", "I999") is False


# ------------------------------------------------- which tag wins, and why


def test_the_earliest_created_tag_wins(recorder):
    """man ttk_treeview: "tag priority is decided by the creation order: tags
    created first receive higher priority."

    Beta carries ('warn', 'cold') in that order, and 'cold' is created first
    here - so 'cold' wins, which is what the ROW's own order would deny. The
    fixture names them the other way round on purpose.
    """
    recorder.tag_configure("cold", background="blue")
    recorder.tag_configure("warn", background="red")
    _alpha, beta, _gamma = recorder.ids
    recorder._row_attribute(beta, 0, 0)
    assert recorder.tk.colors.calls == [("white", "blue")]


def test_configuring_a_tag_again_does_not_promote_it(recorder):
    """Creation order, not the order of the most recent configure call."""
    recorder.tag_configure("cold", background="blue")
    recorder.tag_configure("warn", background="red")
    recorder.tag_configure("cold", background="green")
    _alpha, beta, _gamma = recorder.ids
    recorder._row_attribute(beta, 0, 0)
    assert recorder.tk.colors.calls == [("white", "green")]


def test_a_tag_that_does_not_set_the_option_is_passed_over(recorder):
    """Priority is per option. 'cold' is older but says nothing about the
    background, so 'warn' answers for it - rather than the oldest tag
    blanking what a younger one set."""
    recorder.tag_configure("cold", foreground="cyan")
    recorder.tag_configure("warn", background="red")
    _alpha, beta, _gamma = recorder.ids
    recorder._row_attribute(beta, 0, 0)
    assert recorder.tk.colors.calls == [("cyan", "red")]


def test_a_tag_setting_only_one_colour_keeps_the_widgets_own_other(recorder):
    recorder.tag_configure("warn", background="red")
    alpha, _beta, _gamma = recorder.ids
    assert recorder._row_attribute(alpha, 0, 0) & _Recorder.MARK
    assert recorder.tk.colors.calls == [("white", "red")]


def test_a_tag_colour_replaces_the_rows_own_pair_rather_than_mixing(recorder):
    """The row's attribute already carries the widget's colour pair; the tag's
    must REPLACE it. OR-ing them made a third pair - a cyan tag drew red,
    found by UAT 42. The other tests here start from 0 with a marker outside
    the pair field, which is why none of them could see it. TkCurses-mur."""
    widget_pair, tag_pair = 5 << 8, 2 << 8
    recorder.tk.colors.attribute_for = lambda fg, bg, attr=0: tag_pair
    recorder.tag_configure("warn", foreground="cyan")
    alpha, _beta, _gamma = recorder.ids
    drawn = recorder._row_attribute(alpha, 0, widget_pair | curses.A_BOLD)
    assert drawn & curses.A_COLOR == tag_pair
    assert drawn & curses.A_BOLD


def test_an_untagged_row_is_not_recoloured(recorder):
    recorder.tag_configure("warn", background="red")
    _alpha, _beta, gamma = recorder.ids
    assert recorder._row_attribute(gamma, 0, 0) == 0
    assert recorder.tk.colors.calls == []


def test_a_tag_with_no_colours_leaves_the_row_alone(recorder):
    """font, image, imageanchor and padding are stored and have nothing to do
    on a character grid - one cell is one cell. Setting one must not send the
    row through the colour resolver."""
    recorder.tag_configure("warn", font="Courier 12", padding=4)
    alpha, _beta, _gamma = recorder.ids
    assert recorder._row_attribute(alpha, 0, 0) == 0
    assert recorder.tk.colors.calls == []


def test_a_selected_row_ignores_its_tags(recorder):
    """Selection wins over a tag for the same reason it wins over the stripe:
    reverse plus a colour pair is whatever the terminal decides."""
    recorder.tag_configure("warn", background="red")
    alpha, _beta, _gamma = recorder.ids
    recorder.selection_set(alpha)
    assert recorder._row_attribute(alpha, 0, 0) == curses.A_REVERSE
    assert recorder.tk.colors.calls == []


# ------------------------------------ stripedbackground, where xe9.4 and this meet


def test_a_tags_stripedbackground_is_what_a_striped_row_takes(recorder):
    """The option is Tk's TAG option - "the cell or item background color for
    alternate lines, if -striped is true". xe9.4 could only read the style
    because no tag machinery existed yet."""
    recorder.configure(striped=1)
    recorder.tag_configure("warn", stripedbackground="purple")
    Style(recorder).configure("Treeview", stripedbackground="blue")
    _alpha, beta, _gamma = recorder.ids
    assert recorder._row_attribute(beta, 1, 0) & _Recorder.MARK
    assert recorder.tk.colors.calls == [("white", "purple")]


def test_the_style_answers_when_no_tag_sets_one(recorder):
    """The half of the feature Tk reaches when no tag answers, and the half
    xe9.4 built."""
    recorder.configure(striped=1)
    Style(recorder).configure("Treeview", stripedbackground="blue")
    _alpha, beta, _gamma = recorder.ids
    recorder._row_attribute(beta, 1, 0)
    assert recorder.tk.colors.calls == [("white", "blue")]


def test_a_striped_row_still_takes_its_tags_foreground(recorder):
    recorder.configure(striped=1)
    recorder.tag_configure("warn", foreground="cyan", stripedbackground="purple")
    _alpha, beta, _gamma = recorder.ids
    recorder._row_attribute(beta, 1, 0)
    assert recorder.tk.colors.calls == [("cyan", "purple")]


def test_an_even_row_takes_the_plain_tag_colour_while_striped(recorder):
    """The stripe is every other row, so the rows between it are still
    coloured by their tags rather than left plain."""
    recorder.configure(striped=1)
    recorder.tag_configure("warn", background="red", stripedbackground="purple")
    alpha, _beta, _gamma = recorder.ids
    recorder._row_attribute(alpha, 0, 0)
    assert recorder.tk.colors.calls == [("white", "red")]


def test_a_tag_colour_survives_the_dim_fallback(recorder):
    """A striped row whose tags name no stripedbackground still takes their
    ORDINARY colours, and the dim banding goes on top.

    The alternative was dropping them: the stripe reached A_DIM by way of the
    plain `attribute` it was handed, so a tag that coloured every other row
    coloured only half of them. Added because mutation found it - deleting the
    fallback's tag lookup broke no test until this one.
    """
    recorder.configure(striped=1)
    recorder.tag_configure("warn", background="red")
    _alpha, beta, _gamma = recorder.ids
    attribute = recorder._row_attribute(beta, 1, 0)
    assert recorder.tk.colors.calls == [("white", "red")]
    assert attribute & _Recorder.MARK, "the tag colour was dropped"
    assert attribute & curses.A_DIM, "the stripe was dropped"


def test_the_dim_fallback_stands_when_there_are_no_colours_at_all(tagged):
    """No colour manager, nothing to resolve: the banding is all that is left,
    and asking for a colour must not raise on the way there."""
    tagged.tk.colors = None
    tagged.configure(striped=1)
    tagged.tag_configure("warn", background="red")
    _alpha, beta, _gamma = tagged.ids
    assert tagged._row_attribute(beta, 1, 0) == curses.A_DIM


# -------------------------------------------------------------- tag_bind


def test_a_tag_binding_fires_for_a_click_on_a_tagged_row(tagged):
    fired = []
    tagged.tag_bind("warn", "<Button-1>", lambda event: fired.append(event.y))
    tagged.event_generate("<Button-1>", x=1, y=FIRST_ROW_Y)
    assert fired == [FIRST_ROW_Y]


def test_a_tag_binding_does_not_fire_for_an_untagged_row(tagged):
    fired = []
    tagged.tag_bind("warn", "<Button-1>", lambda event: fired.append("x"))
    tagged.event_generate("<Button-1>", x=1, y=FIRST_ROW_Y + 2)
    assert fired == []


def test_a_click_below_the_last_row_reaches_nothing(tagged):
    """There is no row there to own the event, which _row_at answers None
    for - and None is not a row id to look tags up on."""
    fired = []
    tagged.tag_bind("warn", "<Button-1>", lambda event: fired.append("x"))
    tagged.event_generate("<Button-1>", x=1, y=FIRST_ROW_Y + 6)
    assert fired == []


def test_a_key_binding_goes_to_the_focus_row_not_the_pointer(tagged):
    """man ttk_treeview: key and virtual events go to the focus item, pointer
    events to the item under the pointer. A key event has no row under it."""
    alpha, _beta, gamma = tagged.ids
    fired = []
    tagged.tag_bind("warn", "<Key-Return>", lambda event: fired.append("warn"))
    tagged.focus(gamma)
    tagged.event_generate("<Key-Return>")
    assert fired == []
    tagged.focus(alpha)
    tagged.event_generate("<Key-Return>")
    assert fired == ["warn"]


def test_a_key_binding_with_no_focus_row_reaches_nothing(tree):
    fired = []
    tree.insert("", "end", text="One", tags=("warn",))
    tree.tag_bind("warn", "<Key-Return>", lambda event: fired.append("x"))
    assert tree.focus() == ""
    tree.event_generate("<Key-Return>")
    assert fired == []


def test_tag_bindings_run_in_the_rows_own_tag_order(tagged):
    """The OTHER order, and the one a tag's colour does not use: man
    ttk_treeview sends a binding to "each of the item's tags option ... in
    order as per bindtags(n)". Beta names warn before cold while cold is
    created first, so the two orders disagree here on purpose."""
    order = []
    tagged.tag_configure("cold")
    tagged.tag_configure("warn")
    tagged.tag_bind("cold", "<Button-1>", lambda event: order.append("cold"))
    tagged.tag_bind("warn", "<Button-1>", lambda event: order.append("warn"))
    tagged.event_generate("<Button-1>", x=1, y=FIRST_ROW_Y + 1)
    assert order == ["warn", "cold"]


def test_every_matching_tag_binding_runs(tagged):
    both = []
    tagged.tag_bind("warn", "<Button-1>", lambda event: both.append("warn"))
    tagged.tag_bind("cold", "<Button-1>", lambda event: both.append("cold"))
    tagged.event_generate("<Button-1>", x=1, y=FIRST_ROW_Y + 1)
    assert sorted(both) == ["cold", "warn"]


def test_tag_bind_returns_none_in_every_form(tagged):
    """All three, measured against tkinter - including the one that looks like
    a query, so there is no form that reads a binding back."""
    assert tagged.tag_bind("warn") is None
    assert tagged.tag_bind("warn", "<Button-1>") is None
    assert tagged.tag_bind("warn", "<Button-1>", lambda event: None) is None


def test_the_query_form_does_not_erase_a_binding(tagged):
    """A callback of None is the query form, not an unbind - so asking must
    not take the binding away."""
    fired = []
    tagged.tag_bind("warn", "<Button-1>", lambda event: fired.append("x"))
    tagged.tag_bind("warn", "<Button-1>")
    tagged.event_generate("<Button-1>", x=1, y=FIRST_ROW_Y)
    assert fired == ["x"]


def test_one_widget_binding_serves_every_tag_on_a_sequence(tagged):
    """A tag is not a window, so the binding goes on the widget and the
    dispatcher picks the row. One per sequence however many tags bind it,
    or a row with two tags would be visited twice over."""
    tagged.tag_bind("warn", "<Button-1>", lambda event: None)
    tagged.tag_bind("cold", "<Button-1>", lambda event: None)
    assert list(tagged._tag_dispatch) == ["<Button-1>"]


def test_a_tag_binding_does_not_displace_the_programs_own(tagged):
    """add='+', because a program that bound <Button-1> itself keeps it."""
    fired = []
    tagged.bind("<Button-1>", lambda event: fired.append("mine"))
    tagged.tag_bind("warn", "<Button-1>", lambda event: fired.append("tag"))
    tagged.event_generate("<Button-1>", x=1, y=FIRST_ROW_Y)
    assert sorted(fired) == ["mine", "tag"]


def test_clicking_a_tagged_row_still_selects_it(tagged):
    """The dispatcher returns nothing, so the class binding that selects the
    row still runs - a tag binding adds to the widget's behaviour rather than
    replacing it."""
    alpha, _beta, _gamma = tagged.ids
    tagged.tag_bind("warn", "<Button-1>", lambda event: None)
    tagged.event_generate("<Button-1>", x=1, y=FIRST_ROW_Y)
    assert tagged.selection() == (alpha,)


# ----------------------------------------------------------- set_children


def test_set_children_replaces_the_children_in_order(filled):
    alpha, _child, beta = filled.ids
    filled.set_children("", beta, alpha)
    assert filled.get_children("") == (beta, alpha)


def test_set_children_detaches_what_it_omits_rather_than_deleting_it(filled):
    """The name hides that this is detach, not delete: exists() still answers
    True and move puts the row back."""
    alpha, _child, beta = filled.ids
    filled.set_children("", alpha)
    assert filled.get_children("") == (alpha,)
    assert filled.exists(beta) is True


def test_a_detached_row_reports_no_parent(filled):
    """Measured: Tk answers "" for a detached row's parent, which is
    indistinguishable from a row at the top level. Tk's own quirk, and
    'detached' is what tells the two apart.

    The row dropped here is Alpha's child rather than a root child, because a
    root child's parent is "" before anything happens to it - a test that
    detached one would pass whether or not the parent was ever cleared.
    """
    alpha, child, _beta = filled.ids
    filled.set_children(alpha)
    assert filled.get_children(alpha) == ()
    assert filled.parent(child) == ""
    assert filled._items[child].detached is True


def test_set_children_moves_a_row_from_another_parent(filled):
    alpha, _child, beta = filled.ids
    filled.set_children(alpha, beta)
    assert filled.parent(beta) == alpha
    assert filled.get_children(alpha) == (beta,)
    assert filled.get_children("") == (alpha,)


def test_what_the_moved_row_displaces_is_detached_in_turn(filled):
    alpha, child, beta = filled.ids
    filled.set_children(alpha, beta)
    assert filled.exists(child) is True
    assert filled.parent(child) == ""


def test_a_row_put_back_is_no_longer_detached(filled):
    alpha, _child, beta = filled.ids
    filled.set_children("", alpha)
    filled.set_children("", alpha, beta)
    assert filled._items[beta].detached is False
    assert filled.get_children("") == (alpha, beta)


def test_set_children_with_nothing_detaches_every_child(filled):
    alpha, _child, beta = filled.ids
    filled.set_children("")
    assert filled.get_children("") == ()
    assert filled.exists(alpha) and filled.exists(beta)


def test_set_children_refuses_a_row_as_its_own_child(filled):
    alpha, _child, _beta = filled.ids
    with pytest.raises(TclError, match="descendant"):
        filled.set_children(alpha, alpha)


def test_set_children_refuses_an_ancestors_row(filled):
    """A cycle at one remove: putting Alpha under its own child would leave
    the tree with no root for either.

    The message names the refused row and then the parent it was offered
    to - measured, Tk says ``Cannot insert I001 as descendant of I002`` for
    ``set_children("I002", "I001")``. It once named the row twice, which a
    test using the same row for both could never have noticed."""
    alpha, child, _beta = filled.ids
    with pytest.raises(
        TclError, match=f"^Cannot insert {alpha} as descendant of {child}$"
    ):
        filled.set_children(child, alpha)


def test_set_children_refuses_a_row_that_does_not_exist(filled):
    with pytest.raises(TclError, match="not found"):
        filled.set_children("", "I999")


def test_a_refused_set_children_changes_nothing(filled):
    """Both checks run over every argument before anything moves, so a call
    that names one good row and one bad leaves the tree as it was."""
    alpha, _child, beta = filled.ids
    with pytest.raises(TclError):
        filled.set_children("", beta, "I999")
    assert filled.get_children("") == (alpha, beta)


# ------------------------- Treeview's horizontal layout (p9h, step one)
#
# These pin behaviour that ALREADY EXISTED and was never tested. Measured
# before touching anything: adding 2 cells to every column width left all 245
# ttk tests passing, and so did dropping the space that joins one column to
# the next. The column layout was unverified, so "the refactor is
# behaviour-neutral because the tests still pass" would have been worth
# nothing. They pass now because of these.


@pytest.fixture
def laid_out(root):
    """A tree with explicit column widths, so the arithmetic is visible.

    Unstretched, as the real-Tk scans below were measured: with Tk's default
    ``stretch=1`` these columns would fill the 60 cells (TkCurses-a01) and the
    widths written into these tests would be the starting sizes, not the
    drawn ones.
    """
    view = Treeview(root, name="lo", columns=("size", "kind"))
    view.place(x=0, y=0, width=60, height=10)
    view.column("#0", width=8, stretch=False)
    view.column("size", width=5, stretch=False)
    view.column("kind", width=4, stretch=False)
    view.heading("#0", text="Name")
    view.heading("size", text="Size")
    view.heading("kind", text="Kind")
    root.update_layout()
    view.row = view.insert("", "end", text="Alpha", values=("10", "dir"))
    return view


def test_the_column_spans_are_widths_plus_one_joining_space(laid_out):
    """8, then a space, then 5, then a space, then 4.

    The joining space is the thing that was written down nowhere: a column
    starts at the sum of the widths before it PLUS one cell per gap, which is
    what " ".join puts there.
    """
    assert laid_out._column_spans() == [
        ("#0", 0, 8),
        ("size", 9, 14),
        ("kind", 15, 19),
    ]


def test_the_tree_column_leads_the_spans_only_when_it_is_shown(laid_out):
    assert laid_out._column_spans()[0][0] == "#0"
    laid_out.configure(show="headings")
    assert [name for name, _s, _e in laid_out._column_spans()] == ["size", "kind"]
    assert laid_out._column_spans()[0][1] == 0, "the first column must start at 0"


def test_a_row_pads_each_cell_to_its_own_span(laid_out):
    """What keeps the values under their headings: a row that padded nothing
    would start each value wherever the previous one ended."""
    assert laid_out._row_text(laid_out.row, 60) == " Alpha   10    dir "


def test_the_heading_row_uses_the_same_spans(laid_out):
    """The headings and the rows must agree, which is why one function answers
    for both - they were separate arithmetic before."""
    assert laid_out._heading_text(60) == "Name     Size  Kind"
    row = laid_out._row_text(laid_out.row, 60)
    for _name, start, _end in laid_out._column_spans():
        assert len(row) > start and len(laid_out._heading_text(60)) > start


def test_a_row_is_truncated_to_the_width_it_is_given(laid_out):
    assert laid_out._row_text(laid_out.row, 12) == " Alpha   10 "


def test_a_cell_with_no_value_is_blank_rather_than_missing(laid_out):
    """A short values tuple must still pad, or every later column shifts left."""
    sparse = laid_out.insert("", "end", text="Beta", values=("1",))
    assert laid_out._row_text(sparse, 60) == " Beta    1         "


# --------------------------------- Treeview identify and bbox (p9h, step two)


def test_identify_column_answers_display_identifiers(laid_out):
    """Tk's ids, not our internal names: '#0' then '#1', never 'size'."""
    area = laid_out._rows_area()
    assert laid_out.identify_column(area.x + 0) == "#0"
    assert laid_out.identify_column(area.x + 7) == "#0"
    assert laid_out.identify_column(area.x + 9) == "#1"
    assert laid_out.identify_column(area.x + 15) == "#2"


def test_the_cell_joining_two_columns_belongs_to_the_one_on_its_left(laid_out):
    """Tk's columns abut and have no such cell; ours are joined by a space, and
    leaving it unassigned would make one cell per gap unclickable."""
    area = laid_out._rows_area()
    assert laid_out.identify_column(area.x + 8) == "#0", "the first gap"
    assert laid_out.identify_column(area.x + 14) == "#1", "the second gap"


def test_identify_column_is_empty_outside_the_columns(laid_out):
    """Left of the content and past the last column.

    Past the last column Tk answers the last column's id, because it stretches
    columns to fill the widget and we do not yet - TkCurses-a01. When that
    lands the spans grow and this answer changes with them.
    """
    area = laid_out._rows_area()
    assert laid_out.identify_column(area.x - 1) == ""
    assert laid_out.identify_column(area.x + 19) == ""
    assert laid_out.identify_column(area.x + 30) == ""


def test_identify_row_is_empty_over_the_heading(laid_out):
    """Measured on real Tk: identify_row over the heading answers empty while
    identify_region answers 'heading', so the two are independent."""
    area = laid_out._rows_area()
    assert laid_out.identify_row(area.y) == ""
    assert laid_out.identify_region(area.x + 2, area.y) == "heading"


def test_identify_row_finds_the_rows_and_stops(laid_out):
    area = laid_out._rows_area()
    assert laid_out.identify_row(area.y + 1) == laid_out.row
    assert laid_out.identify_row(area.y + 5) == ""


@pytest.mark.parametrize(
    ("dx", "expected"),
    [(-1, "nothing"), (2, "tree"), (10, "cell"), (16, "cell"), (30, "nothing")],
)
def test_identify_region_names_the_part_of_the_tree(laid_out, dx, expected):
    area = laid_out._rows_area()
    assert laid_out.identify_region(area.x + dx, area.y + 1) == expected


def test_identify_region_never_answers_separator(laid_out):
    """Decided, not overlooked: Tk's separator is the draggable gap between
    column HEADINGS, and this widget draws none and offers no such drag."""
    area = laid_out._rows_area()
    answers = {
        laid_out.identify_region(area.x + dx, area.y + dy)
        for dx in range(-2, 24)
        for dy in range(-2, 8)
    }
    assert "separator" not in answers
    assert answers <= {"heading", "tree", "cell", "nothing"}, answers


def test_identify_dispatches_every_component_tk_defines(laid_out):
    area = laid_out._rows_area()
    x, y = area.x + 2, area.y + 1
    assert laid_out.identify("item", x, y) == laid_out.row
    assert laid_out.identify("row", x, y) == laid_out.row, "Tk's obsolescent synonym"
    assert laid_out.identify("column", x, y) == "#0"
    assert laid_out.identify("region", x, y) == "tree"
    assert laid_out.identify("cell", x, y) == (laid_out.row, "#0")
    assert laid_out.identify("element", x, y) == ""


def test_identify_cell_is_offered_although_tkinter_lacks_it(laid_out):
    """Tk documents 'identify cell' and tkinter has no wrapper for it, so a
    tkinter program composes identify_row with identify_column by hand. This
    answers the pair, deliberately beyond tkinter's surface."""
    area = laid_out._rows_area()
    assert laid_out.identify("cell", area.x + 10, area.y + 1) == (laid_out.row, "#1")
    assert laid_out.identify("cell", area.x + 10, area.y + 5) == "", "no row there"


def test_identify_refuses_a_component_tk_does_not_define(laid_out):
    with pytest.raises(TclError, match='bad command "nonsense"'):
        laid_out.identify("nonsense", 0, 0)


def test_bbox_answers_the_row_then_the_cell(laid_out):
    area = laid_out._rows_area()
    assert laid_out.bbox(laid_out.row) == (area.x, area.y + 1, area.width, 1)
    assert laid_out.bbox(laid_out.row, "size") == (area.x + 9, area.y + 1, 5, 1)


def test_bbox_takes_a_display_identifier_as_well_as_a_name(laid_out):
    """Measured: Tk accepts bbox(item, '#0') as well as bbox(item, 'size')."""
    assert laid_out.bbox(laid_out.row, "#0") == laid_out.bbox(laid_out.row, "#0")
    assert laid_out.bbox(laid_out.row, "#1") == laid_out.bbox(laid_out.row, "size")


def test_bbox_is_empty_for_an_item_that_is_not_visible(laid_out):
    """A descendant of a closed item. Measured on real Tk: empty while the
    parent is closed, a rectangle once it is opened."""
    child = laid_out.insert(laid_out.row, "end", text="Child")
    assert laid_out.bbox(child) == ""
    laid_out.item(laid_out.row, open=True)
    assert laid_out.bbox(child) != ""


def test_bbox_raises_for_an_item_that_does_not_exist(laid_out):
    """The opposite of how it treats an invisible one, and measured: Tk raises
    'Item nosuch not found' rather than answering empty."""
    with pytest.raises(TclError, match="Item nosuch not found"):
        laid_out.bbox("nosuch")


def test_identify_element_is_empty_rather_than_absent(laid_out):
    """Tk answers a themed element name from an element tree this library does
    not have, and documents no fixed set of values. Present and empty so the
    dispatcher has something to call."""
    assert laid_out.identify_element(0, 0) == ""
    assert laid_out.identify_element(99, 99) == ""


# ------------------------------------------------- -stretch (TkCurses-a01)
#
# Measured on Tk 9.0.2: a column's -width is where it starts, and the space
# left over is shared EVENLY among the shown columns whose -stretch is true -
# 80/60/60 in 598 pixels draws 213/193/192, and 100/50/50 gets the same
# +133/+133/+132 - the odd units to the leftmost. stretch=0 columns take no
# share; with none stretchable nothing grows; a hidden #0 takes none. The
# option was stored and never read before this, so the space past the last
# column was blank.


def stretching(root, widths, stretch=(True, True, True), show="tree headings"):
    view = Treeview(root, name="st", columns=("size", "kind"), show=show)
    view.place(x=0, y=0, width=42, height=8)
    for name, width, grows in zip(("#0", "size", "kind"), widths, stretch, strict=True):
        view.column(name, width=width, stretch=grows)
    root.update_layout()
    return view


def drawn(view):
    return [end - start for _name, start, end in view._column_spans()]


def test_the_columns_fill_the_rows_area(root):
    view = stretching(root, (12, 8, 8))
    area = view._rows_area().width
    assert view._column_spans()[-1][2] == area


def test_the_surplus_is_shared_evenly_not_by_width(root):
    view = stretching(root, (12, 8, 8))
    surplus = view._rows_area().width - (12 + 8 + 8 + 2)
    assert drawn(view) == [
        12 + surplus // 3 + (1 if surplus % 3 > 0 else 0),
        8 + surplus // 3 + (1 if surplus % 3 > 1 else 0),
        8 + surplus // 3,
    ]


def test_the_odd_cells_go_to_the_leftmost_columns(root):
    view = stretching(root, (12, 8, 8))
    view.place(x=0, y=0, width=view._rect.width + 2, height=8)
    root.update_layout()
    gains = [w - start for w, start in zip(drawn(view), (12, 8, 8), strict=True)]
    assert gains[0] >= gains[1] >= gains[2] >= gains[0] - 1


def test_a_column_that_does_not_stretch_keeps_its_width(root):
    view = stretching(root, (12, 8, 8), stretch=(True, False, True))
    widths = drawn(view)
    assert widths[1] == 8
    assert abs(widths[0] - 12 - (widths[2] - 8)) <= 1


def test_with_nothing_stretchable_nothing_grows(root):
    view = stretching(root, (12, 8, 8), stretch=(False, False, False))
    assert drawn(view) == [12, 8, 8]


def test_a_hidden_tree_column_takes_no_share(root):
    view = stretching(root, (12, 8, 8), show="headings")
    widths = drawn(view)
    assert sum(widths) + 1 == view._rows_area().width
    assert abs((widths[0] - 8) - (widths[1] - 8)) <= 1


def test_a_tree_narrower_than_its_columns_does_not_shrink_them(root):
    """Tk, creating a tree narrower than its columns, does not shrink them."""
    view = stretching(root, (30, 20, 20))
    assert drawn(view) == [30, 20, 20]


def test_column_reports_the_width_it_is_drawn_at(root):
    """Tk: a 600-pixel tree's 80-wide column reads back 213."""
    view = stretching(root, (12, 8, 8))
    assert view.column("#0", "width") == drawn(view)[0]
    assert view.column("#0")["width"] == drawn(view)[0]


def test_writing_a_drawn_width_back_does_not_drift(root):
    view = stretching(root, (12, 8, 8))
    before = drawn(view)
    for name in ("#0", "size", "kind"):
        view.column(name, width=view.column(name, "width"))
    root.update_layout()
    assert drawn(view) == before


def test_setting_one_width_leaves_the_others_where_they_were_drawn(root):
    """Tk: 213/193/192, then the middle set to 60, reads 257/104/237 - the
    others start from where they were DRAWN and the freed space is shared
    evenly among all three, the narrowed one included."""
    view = stretching(root, (12, 8, 8))
    first, middle, last = drawn(view)
    view.column("size", width=4)
    root.update_layout()
    freed = middle - 4
    gains = [a - b for a, b in zip(drawn(view), (first, 4, last), strict=True)]
    assert sum(gains) == freed
    assert max(gains) - min(gains) <= 1


#: Measured on Tk 9.0.2, the same 120/80/80 columns as the unstretched scans
#: below but with Tk's default stretch: they fill a 420-pixel window and the
#: scan ends on the last column, where unstretched it ends on "". Scanned from
#: the left border to the last cell of the rows area.
TK_STRETCHED_COLUMN_IDS = ["", "#0", "#1", "#2"]


def test_a_stretched_scan_meets_the_column_ids_tk_meets(root):
    view = stretching(root, (12, 8, 8))
    area = view._rows_area()
    xs = range(area.x - 1, area.x + area.width)
    assert _squash([view.identify_column(x) for x in xs]) == TK_STRETCHED_COLUMN_IDS


# ---------------------- the identify scans, against measured real Tk answers
#
# Cells are not pixels, so coordinates cannot be compared across the two
# libraries. What CAN be compared is the sequence of distinct answers a scan
# meets - which is what a caller relies on: "left of the content, nothing;
# then the tree column; then cells; then nothing again".
#
# The real-Tk sequences below are MEASURED, with three unstretched columns of
# 120/80/80 pixels in a 420x200 window, scanning every 4 pixels. They are
# transcribed rather than computed live because a live comparison needs a
# MAPPED window: the real_root fixture withdraws its root, so every
# identify answers "nothing" there, and in CI - which has no display at all -
# such a test would skip and give false comfort. That is also why
# tests/test_pad_options.py carries its Tk answers as a table.
#
# Re-measure with:
#   python3 <scratch>/diff_identify.py real
# which prints exactly these three lines. TkCurses-p9h.

TK_ACROSS_A_ROW = ["nothing", "tree", "cell", "nothing"]
TK_DOWN_A_COLUMN = ["nothing", "heading", "tree", "nothing"]
TK_COLUMN_IDS = ["", "#0", "#1", "#2", ""]


def _squash(values):
    out = []
    for value in values:
        if not out or out[-1] != value:
            out.append(value)
    return out


def test_scanning_across_a_row_meets_the_regions_tk_meets(laid_out):
    assert (
        _squash(
            [
                laid_out.identify_region(x, laid_out._rows_area().y + 1)
                for x in range(34)
            ]
        )
        == TK_ACROSS_A_ROW
    )


def test_scanning_down_meets_the_regions_tk_meets(laid_out):
    assert (
        _squash(
            [laid_out.identify_region(laid_out._rows_area().x + 2, y) for y in range(9)]
        )
        == TK_DOWN_A_COLUMN
    )


def test_scanning_across_meets_the_column_ids_tk_meets(laid_out):
    assert _squash([laid_out.identify_column(x) for x in range(34)]) == TK_COLUMN_IDS


def test_identify_column_numbers_data_columns_from_one_without_a_tree_column(root):
    """The first data column is '#1' whether or not the tree column is shown.

    Added because mutation found it missing: with the tree column shown, the
    index of the first data column IS one, so numbering from the index and
    numbering from one agree and a wrong formula passes. Only a headings-only
    tree tells them apart.
    """
    view = Treeview(root, name="ho", columns=("size", "kind"), show="headings")
    view.place(x=0, y=0, width=40, height=6)
    view.column("size", width=5, stretch=False)
    view.column("kind", width=4, stretch=False)
    root.update_layout()
    area = view._rows_area()
    assert view.identify_column(area.x + 0) == "#1"
    assert view.identify_column(area.x + 6) == "#2"


def test_identify_region_is_nothing_outside_the_area_even_on_the_heading_row(
    laid_out,
):
    """The heading check must not outrank the area check.

    Mutation found this: with the area test removed everything still passed,
    because a point outside horizontally gets no column and a point outside
    vertically gets no row - EXCEPT on the heading row, where the heading
    answer was returned without ever asking whether the point was in the
    widget at all.
    """
    area = laid_out._rows_area()
    assert laid_out.identify_region(area.x - 1, area.y) == "nothing"
    assert laid_out.identify_region(area.x + area.width + 1, area.y) == "nothing"
    assert laid_out.identify_region(area.x + 2, area.y) == "heading", "the control"


# -------------------------------------------------- the named scroll methods


def test_a_treeview_scrolls_by_the_named_methods(root):
    """``tree.yview_moveto(0.0)`` is 'back to the top' - TkCurses-019."""
    tree = Treeview(root, height=3)
    for n in range(20):
        tree.insert("", "end", text=str(n))
    assert tree.yview_scroll(2, "units") is None
    assert tree.yview()[0] == 2 / 20
    tree.yview_moveto(0.0)
    assert tree.yview()[0] == 0.0


@pytest.mark.parametrize(("rows", "top"), [(2.3, 2), (2.5, 3), (2.7, 3)])
def test_a_treeview_moveto_rounds_to_the_nearest_row(root, rows, top):
    """Measured on Tk 9.0.2, 30 rows: Tk rounds, halves up, where this
    truncated. TkCurses-md5."""
    tree = Treeview(root, height=5)
    for n in range(30):
        tree.insert("", "end", text=str(n))
    tree.yview_moveto(rows / 30)
    assert tree.yview()[0] * 30 == pytest.approx(top)


def test_a_treeview_answers_the_horizontal_methods_and_stays_whole(root):
    """An unplaced tree has nothing to scroll - measured, Tk answers (0, 1) too."""
    tree = Treeview(root)
    assert tree.xview_moveto(0.5) is None
    assert tree.xview_scroll(1, "units") is None
    assert tree.xview() == (0.0, 1.0)


# ------------------------------------------- validate() and bbox (TkCurses-52q)
#
# Both are ttk-only in tkinter - defined on ttk.Entry, inherited by Combobox
# and Spinbox - and were missing on all three. validate() was measured on Tk
# 9.0.2 and disagrees with the classic validation paths in several places; see
# the method's docstring.

THEMED_ENTRIES = (Entry, Combobox, Spinbox)


def themed(root, cls=Entry, mode="none", verdict=True):
    asked: list[str] = []
    refused: list[str] = []
    widget = cls(root, name="v")
    widget.delete(0, "end")  # a Spinbox starts out holding its first value
    widget.insert(0, "hello")
    widget.configure(
        validate=mode,
        validatecommand=lambda proposed: asked.append(proposed) or verdict,
        invalidcommand=lambda proposed: refused.append(proposed),
    )
    return widget, asked, refused


@pytest.mark.parametrize("mode", ["none", "key", "focus", "focusout", "all"])
@pytest.mark.parametrize("verdict", [True, False])
def test_validate_runs_under_every_mode(root, mode, verdict):
    """Tk: under every mode, 'none' included, once, with the current text."""
    widget, asked, _refused = themed(root, mode=mode, verdict=verdict)
    assert widget.validate() is verdict
    assert asked == ["hello"]


@pytest.mark.parametrize("cls", THEMED_ENTRIES)
def test_a_refusal_sets_invalid_and_runs_the_invalidcommand(root, cls):
    widget, _asked, refused = themed(root, cls, verdict=False)
    assert widget.validate() is False
    assert "invalid" in widget.state()
    assert refused == ["hello"]


def test_an_approval_clears_invalid_even_set_by_hand(root):
    widget, _asked, refused = themed(root, verdict=True)
    widget.state(["invalid"])
    assert widget.validate() is True
    assert "invalid" not in widget.state()
    assert refused == []


def test_validate_without_a_validatecommand_is_true(root):
    widget = Entry(root, name="v")
    widget.state(["invalid"])
    assert widget.validate() is True
    assert "invalid" not in widget.state()


def test_validate_keeps_the_mode(root):
    """Unlike a refused textvariable write on the classic Entry, nothing here
    turns validation off."""
    widget, _asked, _refused = themed(root, mode="key", verdict=False)
    widget.validate()
    assert widget.cget("validate") == "key"


def test_a_validator_that_raises_makes_validate_raise(root):
    """Tk: TclError 'expected boolean value but got "None"', validation off,
    the state untouched."""
    widget = Entry(root, name="v")
    widget.configure(validate="all", validatecommand=lambda proposed: 1 / 0)
    with pytest.raises(TclError, match="expected boolean value"):
        widget.validate()
    assert widget.cget("validate") == "none"
    assert "invalid" not in widget.state()


def test_a_validator_that_edits_the_entry_fails_validate_but_stays_on(root):
    """Tk: the edit lands, validate() is False with no invalidcommand,
    invalid is set, and validation stays on - which the classic Entry's
    recursion guard would have turned off."""
    refused: list[str] = []
    widget = Entry(root, name="v")
    widget.insert(0, "hello")

    def editing(proposed):
        widget.insert("end", "!")
        return True

    widget.configure(
        validate="all",
        validatecommand=editing,
        invalidcommand=lambda proposed: refused.append(proposed),
    )
    assert widget.validate() is False
    assert widget.get() == "hello!"
    assert widget.cget("validate") == "all"
    assert "invalid" in widget.state()
    assert refused == []


@pytest.mark.parametrize("cls", [Entry, Combobox, Spinbox, tkcurses.Spinbox])
def test_bbox_is_the_cell_of_one_character(root, cls):
    """Measured on Tk 9.0.2, ttk.Entry and tk.Spinbox alike."""
    widget = cls(root, name="b")
    widget.place(x=0, y=0, width=12, height=3)
    root.update_layout()
    widget.delete(0, "end")  # a Spinbox starts out holding its first value
    widget.insert(0, "abcdefghijklmnopqrstuvwxyz")
    x, y, width, height = widget.bbox(0)
    assert (width, height) == (1, 1)
    assert widget.bbox(4) == (x + 4, y, 1, 1)
    # Past the end is the last character's box, as Tk's is.
    assert widget.bbox("end") == widget.bbox(25) == widget.bbox(99) == (x + 25, y, 1, 1)
    # Where the character IS: scrolled off the left, x is negative of it.
    widget.xview(10)
    assert widget.bbox(0) == (x - 10, y, 1, 1)


def test_bbox_of_an_empty_entry_has_no_width(root):
    widget = Entry(root, name="b")
    widget.place(x=0, y=0, width=12, height=3)
    root.update_layout()
    x, y, width, height = widget.bbox(0)
    assert width == 0
    assert widget.bbox("end") == (x, y, 0, height)


# --------------------------------------------- identify, the themed-element form
#
# ttk.Widget.identify answers the name of the style ELEMENT at a point. These
# are the default theme's names as MEASURED on Tk 9.0.2, every 2 pixels over
# each widget - the complete set each one can answer. Ours draw no focus ring
# and may draw no padding, so they answer a SUBSET, and never anything else.
# TkCurses-d5u.

TK_ELEMENTS = {
    "Button": {"border", "padding", "label", "focus"},
    "Checkbutton": {"padding", "Checkbutton.indicator", "label", "focus"},
    "Radiobutton": {"padding", "Radiobutton.indicator", "label", "focus"},
    "Label": {"border", "padding", "label"},
    "Entry": {"field", "padding", "textarea"},
    "Combobox": {"field", "textarea", "padding", "Combobox.downarrow"},
    "Spinbox": {"field", "padding", "textarea", "Spinbox.uparrow", "Spinbox.downarrow"},
    "Progressbar": {"trough", "pbar"},
    "Scale": {"focus", "slider", "trough"},
    "Scrollbar": {"trough", "leftarrow", "thumb", "rightarrow"},
    "Separator": {"separator"},
    "Sizegrip": {"sizegrip"},
    "Frame": {"border"},
    "Labelframe": {"", "border"},
    "Menubutton": {"border", "padding", "focus", "label", "Menubutton.indicator"},
    "LabeledScale": {"border"},
}


def _identify_scan(root, widget, width, height):
    widget.place(x=0, y=0, width=width, height=height)
    root.update_layout()
    return {widget.identify(x, y) for y in range(height) for x in range(width)}


ELEMENT_WIDGETS = [
    ("Button", lambda r: Button(r, name="w", text="Press", padding=1), (13, 5)),
    ("Checkbutton", lambda r: Checkbutton(r, name="w", text="Check"), (12, 1)),
    ("Radiobutton", lambda r: Radiobutton(r, name="w", text="Radio"), (12, 1)),
    ("Label", lambda r: Label(r, name="w", text="Hi", relief="solid"), (8, 3)),
    ("Entry", lambda r: Entry(r, name="w"), (12, 3)),
    ("Combobox", lambda r: Combobox(r, name="w", values=("a",)), (12, 3)),
    ("Spinbox", lambda r: Spinbox(r, name="w", from_=0, to=9), (12, 3)),
    ("Progressbar", lambda r: Progressbar(r, name="w", value=40), (20, 1)),
    ("Scale", lambda r: Scale(r, name="w", length=20), (20, 1)),
    ("Scrollbar", lambda r: Scrollbar(r, name="w", orient="horizontal"), (20, 1)),
    ("Separator", lambda r: Separator(r, name="w"), (10, 1)),
    ("Sizegrip", lambda r: Sizegrip(r, name="w"), (2, 2)),
    ("Frame", lambda r: Frame(r, name="w"), (10, 4)),
    ("Labelframe", lambda r: Labelframe(r, name="w", text="Cap"), (12, 4)),
    ("Menubutton", lambda r: OptionMenu(r, tkcurses.StringVar(r), "a", "a"), (10, 3)),
    ("LabeledScale", lambda r: LabeledScale(r, name="w"), (20, 3)),
]


@pytest.mark.parametrize(
    ("kind", "make", "size"), ELEMENT_WIDGETS, ids=[c[0] for c in ELEMENT_WIDGETS]
)
def test_identify_answers_only_names_tk_answers(root, kind, make, size):
    answered = _identify_scan(root, make(root), *size)
    assert answered <= TK_ELEMENTS[kind], answered - TK_ELEMENTS[kind]
    # And something besides the empty answer, except where Tk's is mostly that.
    assert answered - {""}


def test_identify_outside_the_widget_is_empty(root):
    widget = Button(root, name="w", text="Press")
    widget.place(x=0, y=0, width=9, height=3)
    root.update_layout()
    assert (
        widget.identify(9, 0) == widget.identify(0, 3) == widget.identify(-1, 0) == ""
    )


def test_identify_follows_the_drawn_rings(root):
    """A bordered button: the edge is the border, the text area the label,
    and with padding the band between them is padding."""
    widget = Button(root, name="w", text="Hi", padx=1, relief="raised")
    widget.place(x=0, y=0, width=8, height=3)
    root.update_layout()
    area = widget._text_area()
    assert widget.identify(0, 0) == "border"
    assert widget.identify(area.x, area.y) == "label"
    assert widget.identify(area.x - 1, area.y) == "padding"


def test_identify_answers_no_border_where_none_is_drawn(root):
    """A flat label draws no border, so its edge is padding, not border."""
    widget = Label(root, name="w", text="Hi", padx=1)
    widget.place(x=0, y=0, width=6, height=1)
    root.update_layout()
    assert widget.identify(0, 0) == "padding"
    assert widget.identify(1, 0) == "label"


def test_identify_names_the_entry_parts(root):
    combobox = Combobox(root, name="c", values=("a",))
    combobox.place(x=0, y=0, width=12, height=3)
    spinbox = Spinbox(root, name="s", from_=0, to=9)
    spinbox.place(x=0, y=4, width=12, height=3)
    root.update_layout()
    assert combobox.identify(0, 0) == "field"
    assert combobox.identify(1, 1) == "textarea"
    assert combobox.identify(10, 1) == "Combobox.downarrow"
    up, down = spinbox._arrow_columns()
    assert spinbox.identify(up, 1) == "Spinbox.uparrow"
    assert spinbox.identify(down, 1) == "Spinbox.downarrow"
    assert spinbox.identify(1, 1) == "textarea"


def test_identify_names_the_indicators(root):
    check = Checkbutton(root, name="c", text="Check")
    check.place(x=0, y=0, width=12, height=1)
    menu = OptionMenu(root, tkcurses.StringVar(root), "a", "a")
    menu.place(x=0, y=2, width=10, height=3)
    root.update_layout()
    column, row = check._indicator_place()
    assert check.identify(column, row) == "Checkbutton.indicator"
    assert check.identify(check._text_area().x, row) == "label"
    assert menu.identify(*menu._indicator_cell()) == "Menubutton.indicator"


def test_identify_names_the_progressbar_fill(root):
    bar = Progressbar(root, name="p", value=50, maximum=100)
    bar.place(x=0, y=0, width=10, height=1)
    tall = Progressbar(root, name="q", value=50, maximum=100, orient="vertical")
    tall.place(x=12, y=0, width=1, height=10)
    root.update_layout()
    assert [bar.identify(x, 0) for x in range(10)] == ["pbar"] * 5 + ["trough"] * 5
    # A vertical bar fills from the bottom.
    assert [tall.identify(0, y) for y in range(10)] == ["trough"] * 5 + ["pbar"] * 5


@pytest.mark.parametrize("orient", ["horizontal", "vertical"])
def test_identify_gives_scale_and_scrollbar_their_ttk_names(root, orient):
    """The classic widgets answer trough1/trough2/arrow1/slider; ttk's do not."""
    scale = Scale(root, name="s", orient=orient, length=20)
    bar = Scrollbar(root, name="b", orient=orient)
    size = (20, 1) if orient == "horizontal" else (1, 20)
    found_scale = _identify_scan(root, scale, *size)
    found_bar = _identify_scan(root, bar, *size)
    assert found_scale <= {"slider", "trough"} and "slider" in found_scale
    arrows = (
        {"leftarrow", "rightarrow"}
        if orient == "horizontal"
        else {"uparrow", "downarrow"}
    )
    assert found_bar == arrows | {"thumb"} or found_bar == arrows | {"thumb", "trough"}


def test_identify_over_notebook_tabs(root):
    """Measured: tab holding padding holding label; past the tabs and on the
    page, nothing. Not a tab index - that is index('@x,y')."""
    book = Notebook(root, name="n")
    book.place(x=0, y=0, width=30, height=8)
    for title in ("One", "Two"):
        book.add(Frame(book), text=title)
    root.update_layout()
    _index, first, _last = book._tab_spans()[0]
    assert book.identify(first, 1) == book.identify(first + 1, 0) == "tab"
    assert book.identify(first + 1, 1) == "padding"
    assert book.identify(first + 2, 1) == "label"
    assert book.identify(29, 1) == ""
    # The page's frame line under a tab, and the page itself.
    assert book.identify(first + 2, 2) == ""
    assert book.identify(5, 4) == ""


def test_identify_over_a_panedwindow_sash_is_its_index(root):
    """Measured: ttk answers the bare index, 0, where the classic answers
    (0, 'sash')."""
    panes = PanedWindow(root, name="p", orient="horizontal")
    panes.place(x=0, y=0, width=21, height=4)
    panes.add(Frame(panes, name="a"), weight=1)
    panes.add(Frame(panes, name="b"), weight=1)
    root.update_layout()
    row = [panes.identify(x, 1) for x in range(21)]
    assert 0 in row
    assert set(row) == {0, ""}


def test_identify_over_a_labelframe_caption_is_empty(root):
    frame = Labelframe(root, name="f", text="Cap")
    frame.place(x=0, y=0, width=12, height=4)
    root.update_layout()
    row, column, text = frame._caption_place()
    assert frame.identify(column, row) == ""
    assert frame.identify(column + len(text), row) == "border"
    assert frame.identify(5, 2) == "border"


@pytest.mark.parametrize("cls", [Spinbox, tkcurses.Spinbox])
def test_clicking_a_spinbox_arrow_still_steps_it(root, cls):
    """The click binding asks which part was hit. A ttk Spinbox's own
    identify now answers ttk's element names, so the binding must ask the
    classic question by name - or a click on ttk's arrows did nothing."""
    from types import SimpleNamespace

    from tkcurses import _spinbox_click, _spinbox_release

    spin = cls(root, name="s", from_=0, to=9)
    # A ttk spinbox starts empty, as Tk's does - TkCurses-fdl9.
    spin.delete(0, "end")
    spin.insert(0, "0")
    spin.place(x=0, y=0, width=12, height=3)
    root.update_layout()
    up, _down = spin._arrow_columns()
    _spinbox_click(SimpleNamespace(widget=spin, x=up, y=1))
    # The classic one steps on the release, as tk::spinbox::ButtonUp does.
    _spinbox_release(SimpleNamespace(widget=spin, x=up, y=1))
    assert spin.get() == "1"


@pytest.mark.parametrize("flag", ["invalid", "disabled", "pressed"])
def test_a_state_change_repaints_the_widget(root, flag):
    """Tk repaints a themed widget when its state changes; a state is how it
    looks. state() changed the flags and repainted nothing, so validate()'s
    "invalid" showed only at the next keystroke - found by a person running
    UAT 42. A call that changes nothing need not repaint. TkCurses-b9q."""
    widget = Entry(root, name="e")
    painted = []
    widget._redraw = lambda: painted.append(widget.state())
    widget.state([flag])
    assert painted == [(flag,)]
    widget.state([flag])
    assert len(painted) == 1, "nothing changed, so nothing to repaint"
    widget.state([f"!{flag}"])
    assert painted[-1] == ()


# --------------------------------------------- the -state option and flags
#
# Measured on Tk 9.0.2, on every themed widget that has the option: setting it
# clears active, disabled and readonly and sets the one named - normal sets
# none - and leaves every other flag alone; the other direction is not tied.
# Ours stored the option and left the flags, at construction and on configure
# alike. TkCurses-fgke.

WITH_STATE = (
    "Entry",
    "Combobox",
    "Spinbox",
    "Button",
    "Checkbutton",
    "Radiobutton",
    "Label",
    "Scale",
    "Menubutton",
)


def with_state(root, kind, **kw):
    import tkcurses.ttk as ttk_module

    return getattr(ttk_module, kind)(root, **kw)


@pytest.mark.parametrize("kind", WITH_STATE)
@pytest.mark.parametrize("value", ["readonly", "disabled", "active"])
def test_a_state_given_at_construction_sets_its_flag(root, kind, value):
    assert value in with_state(root, kind, state=value).state()


@pytest.mark.parametrize("kind", WITH_STATE)
def test_configuring_the_state_replaces_the_flag_and_keeps_the_rest(root, kind):
    widget = with_state(root, kind)
    widget.configure(state="readonly")
    assert "readonly" in widget.state()
    widget.configure(state="disabled")
    assert "disabled" in widget.state() and "readonly" not in widget.state()
    widget.state(["readonly", "focus"])
    widget.configure(state="normal")
    assert {"active", "disabled", "readonly"} & set(widget.state()) == set()
    assert "focus" in widget.state(), "flags the option does not name are kept"


def test_the_flags_do_not_set_the_option(root):
    widget = with_state(root, "Entry")
    widget.state(["disabled"])
    assert str(widget.cget("state")) == "normal"


def test_a_widget_without_the_option_still_refuses_it(root):
    with pytest.raises(TclError):
        with_state(root, "Scrollbar", state="disabled")


def test_a_combobox_made_readonly_by_its_option_refuses_typing(root):
    """The symptom: the usual pick-from-a-list combobox took typing. The
    test above sets the flag with state(); this is the option, which is how
    programs write it."""
    from tkcurses._core.events import KeyEvent

    box = with_state(root, "Combobox", state="readonly", values=["one", "two"])
    box.focus_set()
    box._handle(KeyEvent(keysym="x", char="x"))
    assert box.get() == ""


def test_a_themed_scrollbar_refuses_activate_as_tk_does(root):
    """ttk::scrollbar has no activate; tkinter's inherited method raises."""
    bar = Scrollbar(root, name="sa")
    for args in ((), ("slider",)):
        with pytest.raises(TclError, match='bad command "activate"'):
            bar.activate(*args)


# ------------------------------- Treeview scrolled sideways (TkCurses-xe9.6)
#
# Measured on Tk 9.0.2 in pixels and asserted here in cells: one unit is one,
# one page is the width the scrolling columns are seen through, a bare number
# is an offset, and the fractions are of the scrolling columns only.


@pytest.fixture
def wide(root):
    """Columns 26 cells wide in a rows area 20 wide: six cells to scroll."""
    view = Treeview(root, name="wide", columns=("a", "b", "c"))
    view.place(x=0, y=0, width=22, height=8)
    view.column("#0", width=8, stretch=False)
    for name in ("a", "b", "c"):
        view.column(name, width=5, stretch=False)
        view.heading(name, text=name.upper())
    view.heading("#0", text="Name")
    root.update_layout()
    view.row = view.insert("", "end", text="Alpha", values=("aa", "bb", "cc"))
    assert view._rows_area().width == 20
    assert view._column_spans()[-1][2] == 26
    return view


def _whole_row(tree):
    """The row as it would be drawn with nothing scrolled and room for all."""
    tree._left = 0
    return tree._row_text(tree.row, 99)


def test_columns_wider_than_the_tree_can_be_scrolled_to(wide):
    whole = _whole_row(wide)
    assert wide.xview() == (0.0, 20 / 26)
    wide.xview_moveto(1.0)
    assert wide.xview() == (6 / 26, 1.0)
    assert wide._row_text(wide.row, 20) == whole[6:26], "the last column is reachable"


def test_the_heading_scrolls_with_the_rows(wide):
    wide.xview_scroll(4, "units")
    assert wide._heading_text(20) == "Name     A     B     C    "[4:24]


def test_a_unit_is_a_cell_and_a_page_is_the_view(wide):
    wide.xview_scroll(1, "units")
    assert wide._left == 1
    wide.xview_moveto(0)
    wide.xview(20 - 20)  # a bare offset
    wide.xview("scroll", 1, "pages")
    assert wide._left == 6, "a page is 20 cells, clamped to the 6 there are"


def test_a_bare_number_is_an_offset(wide):
    wide.xview(3)
    assert wide._left == 3


@pytest.mark.parametrize(("fraction", "left"), [(2.4 / 26, 2), (2.5 / 26, 3)])
def test_xview_moveto_rounds_as_yview_does(wide, fraction, left):
    wide.xview_moveto(fraction)
    assert wide._left == left


def test_the_view_cannot_run_past_either_end(wide):
    wide.xview(-5)
    assert wide._left == 0
    wide.xview(50)
    assert wide._left == 6


def test_the_scrollbar_is_told_the_horizontal_view(wide):
    seen = []
    wide.configure(xscrollcommand=lambda *f: seen.append(f))
    wide.xview_moveto(1.0)
    assert seen[-1] == (6 / 26, 1.0)


def test_columns_that_fit_leave_nothing_to_scroll(laid_out):
    laid_out.xview_moveto(0.5)
    assert laid_out.xview() == (0.0, 1.0)
    assert laid_out._left == 0


def test_identify_column_reads_through_the_scroll(wide):
    area = wide._rows_area()
    assert wide.identify_column(area.x + 9) == "#1"
    wide.xview(6)
    assert wide.identify_column(area.x + 9) == "#2", "a moved under the pointer"
    assert wide.identify_column(area.x + 20) == "", "past the rows area"


def test_bbox_follows_the_scroll_unclipped(wide):
    """Tk answers a column scrolled off the left with a negative x (-101)."""
    area = wide._rows_area()
    wide.xview(6)
    assert wide.bbox(wide.row, "#0")[0] == area.x - 6
    assert wide.bbox(wide.row, "a")[0] == area.x + 3


def test_a_marker_scrolled_away_cannot_be_clicked(wide):
    parent = wide.insert("", "end", text="P")
    wide.insert(parent, "end", text="child")
    area = wide._rows_area()
    assert wide._marker_column(parent) == area.x
    wide.xview(1)
    assert wide._marker_column(parent) == -1


# ------------------------------------ Treeview's title rows (TkCurses-xe9.6)
#
# Replays the Tk 9.0.2 probe: twenty rows, eight showing, three frozen.


@pytest.fixture
def titled(root):
    view = Treeview(root, name="titled", titleitems=3)
    view.place(x=0, y=0, width=30, height=11)
    root.update_layout()
    for n in range(20):
        view.insert("", "end", iid=f"i{n}", text=f"row{n}")
    assert view._content_height() == 8
    return view


def _rows_shown(tree):
    first = tree._rows_area().y + 1
    return [tree.identify_row(first + n) for n in range(tree._content_height())]


def test_title_rows_stay_on_top_while_the_rest_scroll(titled):
    titled.yview_moveto(0.5)
    assert titled.yview() == (9 / 17, 14 / 17)
    assert _rows_shown(titled) == ["i0", "i1", "i2", "i12", "i13", "i14", "i15", "i16"]


def test_the_fractions_are_of_the_rows_that_scroll(titled):
    assert titled.yview() == (0.0, 5 / 17)


def test_a_page_is_the_rows_under_the_titles(titled):
    titled.yview_scroll(1, "pages")
    assert titled._top == 5


def test_bbox_answers_for_titles_and_not_for_rows_scrolled_under_them(titled):
    titled.yview_moveto(0.5)
    first = titled._rows_area().y + 1
    assert titled.bbox("i1")[1] == first + 1
    assert titled.bbox("i12")[1] == first + 3
    assert titled.bbox("i10") == ""
    assert titled.bbox("i3") == "", "scrolled up under the titles, so not drawn"


def test_seeing_a_title_row_moves_nothing(titled):
    titled.yview_moveto(0.5)
    titled.see("i1")
    assert titled._top == 9


def test_seeing_a_scrolled_row_counts_only_the_rows_that_scroll(titled):
    titled.see("i19")
    assert titled._top == 12
    assert "i19" in _rows_shown(titled)


def test_the_titles_are_counted_in_display_order(root):
    """Measured: two frozen, an open first branch - the branch and its child."""
    tree = Treeview(root, name="nested", titleitems=2)
    tree.place(x=0, y=0, width=30, height=6)
    root.update_layout()
    tree.insert("", "end", iid="p", text="p", open=True)
    tree.insert("p", "end", iid="c0", text="c0")
    for n in range(10):
        tree.insert("", "end", iid=f"i{n}", text=f"i{n}")
    assert tree._split_rows()[0] == ["p", "c0"]
    tree.item("p", open=False)
    assert tree._split_rows()[0] == ["p", "i0"]


def test_titles_past_the_end_freeze_every_row(titled):
    titled.configure(titleitems=99)
    assert titled.cget("titleitems") == 99, "kept as given, as Tk keeps it"
    assert titled.yview() == (0.0, 1.0)


def test_titles_that_do_not_fit_leave_no_room_to_scroll(titled):
    titled.configure(titleitems=10)
    assert _rows_shown(titled) == [f"i{n}" for n in range(8)]
    titled.yview_scroll(5, "units")
    assert _rows_shown(titled)[-1] == "i7"


@pytest.mark.parametrize(
    ("value", "message"),
    [(-1, '"-1" is out of range'), ("x", 'expected integer but got "x"')],
)
def test_titleitems_refuses_what_tk_refuses(root, value, message):
    with pytest.raises(TclError, match=message):
        Treeview(root, titleitems=value)
    tree = Treeview(root)
    with pytest.raises(TclError, match=message):
        tree.configure(titleitems=value)
    assert tree.cget("titleitems") == 0


# ------------------------------- Treeview's title columns (TkCurses-xe9.6)
#
# The wide tree again: #0 is 8 cells and the joining cell makes the frozen
# part 9, leaving 17 cells of columns seen through 11.


def test_title_columns_stay_put_while_the_rest_scroll(wide):
    whole = _whole_row(wide)
    wide.configure(titlecolumns=1)
    assert wide._frozen_width() == 9
    wide.xview_moveto(1.0)
    assert wide._row_text(wide.row, 20) == whole[:9] + whole[15:26]
    assert wide._heading_text(20).startswith("Name     ")


def test_the_fractions_are_of_the_columns_that_scroll(wide):
    """Tk's (0.0, 0.596) became (0.0, 0.327) with two frozen; here 20/26 to 11/17."""
    wide.configure(titlecolumns=1)
    assert wide.xview() == (0.0, 11 / 17)
    wide.xview_moveto(1.0)
    assert wide.xview() == (6 / 17, 1.0)


def test_a_page_is_the_view_beside_the_title_columns(wide):
    wide.configure(titlecolumns=1)
    wide.xview_scroll(1, "pages")
    assert wide._left == 6, "11 cells, clamped to the 6 there are"


def test_a_click_on_a_title_column_finds_it_however_far_scrolled(wide):
    area = wide._rows_area()
    wide.configure(titlecolumns=1)
    wide.xview(6)
    assert wide.identify_column(area.x + 3) == "#0"
    assert wide.identify_column(area.x + 8) == "#0", "the joining cell is #0's"
    assert wide.identify_column(area.x + 9) == "#2", "b, scrolled to the frozen edge"


def test_scrolled_columns_pass_under_the_title_columns(wide):
    """Measured: Tk's bbox puts a scrolled column inside the frozen ones."""
    area = wide._rows_area()
    wide.configure(titlecolumns=1)
    wide.xview(6)
    assert wide.bbox(wide.row, "#0")[0] == area.x
    assert wide.bbox(wide.row, "a")[0] == area.x + 3


def test_a_frozen_marker_can_still_be_clicked(wide):
    parent = wide.insert("", "end", text="P")
    wide.insert(parent, "end", text="child")
    wide.configure(titlecolumns=1)
    wide.xview(6)
    assert wide._marker_column(parent) == wide._rows_area().x


@pytest.mark.parametrize(("count", "frozen"), [(1, 0), (2, 6)])
def test_the_hidden_tree_column_is_still_counted(wide, count, frozen):
    """Measured: with show="headings", 1 freezes nothing and 2 freezes a."""
    wide.configure(show="headings", titlecolumns=count)
    assert wide._frozen_width() == frozen


def test_title_columns_past_the_end_freeze_everything(wide):
    wide.configure(titlecolumns=99)
    assert wide.cget("titlecolumns") == 99
    assert wide._frozen_width() == 26
    assert wide.xview() == (0.0, 1.0)
    wide.xview_moveto(1.0)
    assert wide._row_text(wide.row, 20) == _whole_row(wide)[:20]


@pytest.mark.parametrize(
    ("value", "message"),
    [(-1, '"#-1" is out of range'), ("x", 'expected integer but got "x"')],
)
def test_titlecolumns_refuses_what_tk_refuses(root, value, message):
    with pytest.raises(TclError, match=message):
        Treeview(root, titlecolumns=value)
    tree = Treeview(root)
    with pytest.raises(TclError, match=message):
        tree.configure(titlecolumns=value)
    assert tree.cget("titlecolumns") == 0


def test_a_page_moves_the_whole_view_when_there_is_room(wide):
    wide.column("c", width=30, stretch=False)
    wide.xview("scroll", 1, "pages")
    assert wide._left == 20


def test_identify_column_answers_nothing_outside_the_rows_area(wide):
    """Even where scrolled-away columns would be, were the tree wider."""
    area = wide._rows_area()
    assert wide.identify_column(area.x + 21) == ""
    wide.xview(6)
    assert wide.identify_column(area.x - 1) == ""


def test_identify_row_keeps_counting_below_the_titles_as_tk_does(titled):
    """Measured: Tk answers rows past the bottom, titles too when they overflow."""
    titled.configure(titleitems=10)
    first = titled._rows_area().y + 1
    assert titled.identify_row(first + 9) == "i9"


# ------------------------------- Treeview -displaycolumns (TkCurses-aq04)
#
# Every case measured on Tk 9.0.2 with columns ("a", "b", "c") before it was
# asserted. The wide tree's columns are 5 cells each after an 8-cell #0.


def test_displaycolumns_draws_the_listed_columns_in_their_order(wide):
    wide.configure(displaycolumns=("c", "a"))
    assert [name for name, _s, _e in wide._column_spans()] == ["#0", "c", "a"]
    assert wide._row_text(wide.row, 20) == " Alpha   cc    aa   "
    assert wide._heading_text(20).startswith("Name     C     A")


def test_display_identifiers_count_in_display_order(wide):
    """Tk: identify answers #1 over c; column("#1") is c; "#3" is refused."""
    area = wide._rows_area()
    wide.configure(displaycolumns=("c", "a"))
    assert wide.identify_column(area.x + 10) == "#1"
    assert wide.column("#1", "id") == "c"
    assert wide.column("#2", "id") == "a"
    with pytest.raises(TclError, match="Column #3 out of range"):
        wide.column("#3", "id")
    wide.heading("#1", text="H")
    assert wide.heading("c", "text") == "H"


def test_a_hidden_column_has_no_bbox_and_keeps_its_value(wide):
    wide.configure(displaycolumns=("c", "a"))
    assert wide.bbox(wide.row, "a")[0] == wide._rows_area().x + 15
    assert wide.bbox(wide.row, "b") == ""
    assert wide.set(wide.row) == {"a": "aa", "b": "bb", "c": "cc"}


def test_set_names_a_cell_by_its_display_identifier(wide):
    wide.configure(displaycolumns=("c", "b"))
    wide.set(wide.row, "#2", "Z")
    assert wide.set(wide.row) == {"a": "aa", "b": "Z", "c": "cc"}
    assert wide.set(wide.row, "#1") == "cc"
    with pytest.raises(TclError, match="Display column #0 cannot be set"):
        wide.set(wide.row, "#0")
    with pytest.raises(TclError, match="Column #9 out of range"):
        wide.set(wide.row, "#9")


@pytest.mark.parametrize(
    ("given", "drawn"),
    [
        ((2, 0), ["c", "a"]),
        (("2", "0"), ["c", "a"]),
        (("01",), ["b"]),
        ("b a", ["b", "a"]),
        (("a", "a"), ["a", "a"]),
        ((), []),
        ("#all", ["a", "b", "c"]),
    ],
)
def test_displaycolumns_takes_names_indices_and_repeats(wide, given, drawn):
    wide.configure(displaycolumns=given)
    assert wide._displayed_names() == drawn


@pytest.mark.parametrize(
    ("given", "message"),
    [
        (("zz",), 'Invalid column index "zz"'),
        ((5,), 'Column index "5" out of bounds'),
        ((-1,), 'Column index "-1" out of bounds'),
        (("#0",), 'Invalid column index "#0"'),
        (("#1",), 'Invalid column index "#1"'),
        (("#all", "a"), 'Invalid column index "#all"'),
        (("1.0",), 'Invalid column index "1.0"'),
        (("1_0",), 'Invalid column index "1_0"'),
    ],
)
def test_displaycolumns_refuses_what_tk_refuses(root, given, message):
    with pytest.raises(TclError, match=message):
        Treeview(root, columns=("a", "b", "c"), displaycolumns=given)
    tree = Treeview(root, columns=("a", "b", "c"), displaycolumns=(2, 0))
    with pytest.raises(TclError, match=message):
        tree.configure(displaycolumns=given)
    assert tree.cget("displaycolumns") == (2, 0)


def test_columns_cannot_drop_a_displayed_column(wide):
    """Tk refuses this too, but applies half of it first; here nothing changes."""
    wide.configure(displaycolumns=("c", "a"))
    with pytest.raises(TclError, match='Invalid column index "c"'):
        wide.configure(columns=("a", "b"))
    assert wide.cget("columns") == ("a", "b", "c")
    assert wide.set(wide.row) == {"a": "aa", "b": "bb", "c": "cc"}
    wide.configure(columns=("a", "b"), displaycolumns="#all")
    assert wide._displayed_names() == ["a", "b"]


def test_new_columns_keep_the_display_list(wide):
    wide.configure(displaycolumns=("c", "a"))
    wide.configure(columns=("a", "b", "c", "d"))
    assert wide.cget("displaycolumns") == ("c", "a")
    assert wide._displayed_names() == ["c", "a"]


def test_title_columns_count_the_displayed_columns(wide):
    """Measured: displaycolumns=(c, a, b) with 2 frozen freezes #0 and c."""
    wide.configure(displaycolumns=("c", "a", "b"), titlecolumns=2)
    assert wide._frozen_width() == 15
    wide.xview_moveto(1.0)
    assert wide.identify_column(wide._rows_area().x + 10) == "#1"


def test_a_column_string_is_a_list_of_names(root):
    tree = Treeview(root, columns="one two")
    assert tree._column_names() == ["one", "two"]


# ------------------------------------ Treeview's mouse wheel (TkCurses-94fn)
#
# Measured on Tk 9.0.2 with event_generate("<MouseWheel>", delta=-120): a
# notch moves 3 rows, 10 with Alt; with Shift the same counts move sideways.


@pytest.fixture
def tall(root):
    """Forty rows in a tree twenty cells wide, scrolled down to row 10."""
    view = Treeview(root, name="tall", columns=("a", "b", "c"))
    view.place(x=0, y=0, width=22, height=8)
    view.column("#0", width=8, stretch=False)
    for name in ("a", "b", "c"):
        view.column(name, width=20, stretch=False)
    for n in range(40):
        view.insert("", "end", iid=f"i{n}", text=f"row {n}")
    root.update_layout()
    view.selection_set("i0")
    view.yview(10)
    view.xview(20)
    return view


def _wheel(tree, button, modifiers=0):
    area = tree._rows_area()
    tree._handle(
        MouseEvent(
            button=button, state="pressed", x=area.x, y=area.y, modifiers=modifiers
        )
    )


@pytest.mark.parametrize(
    ("button", "modifiers", "top", "left"),
    [
        (5, 0, 13, 20),
        (4, 0, 7, 20),
        (5, MOD_ALT, 20, 20),
        (4, MOD_ALT, 0, 20),
        (5, MOD_SHIFT, 10, 23),
        (4, MOD_SHIFT, 10, 17),
        (5, MOD_SHIFT | MOD_ALT, 10, 30),
        (4, MOD_SHIFT | MOD_ALT, 10, 10),
    ],
)
def test_the_wheel_scrolls_the_tree(tall, button, modifiers, top, left):
    _wheel(tall, button, modifiers)
    assert (tall._top, tall._left) == (top, left)
    assert tall.selection() == ("i0",), "a wheel is not a click"


# -------------------------- ttk.Panedwindow keeps a weight (TkCurses-z6pp)


def test_inserting_a_pane_again_moves_it_and_keeps_its_weight(root):
    """Measured on ttk 9.0.2; here the weight went back to 0."""
    paned = Panedwindow(root, name="pw")
    first, second = tkcurses.Frame(paned, name="a"), tkcurses.Frame(paned, name="b")
    paned.add(first, weight=3)
    paned.add(second)
    paned.insert(0, second)
    paned.insert(0, first)
    assert paned.pane(first) == {"weight": 3}
    assert paned.pane(second) == {"weight": 0}
    paned.insert(0, first, weight=9)
    assert paned.pane(first) == {"weight": 9}


def test_adding_a_pane_again_is_refused(root):
    """ttk, unlike the classic widget, refuses it - measured on 9.0.2."""
    paned = Panedwindow(root, name="pw")
    child = tkcurses.Frame(paned, name="a")
    paned.add(child, weight=3)
    with pytest.raises(TclError, match=r"\.pw\.a already added"):
        paned.add(child)
    assert paned.pane(child) == {"weight": 3}


# -------------------------------- ttk.Panedwindow.pane(child, option) (kopw)


def test_pane_answers_one_option_by_name(root):
    """Measured on ttk 9.0.2: by widget or by index, with ttk's default 0."""
    paned = Panedwindow(root, name="pw")
    weighted, plain = tkcurses.Frame(paned, name="a"), tkcurses.Frame(paned, name="b")
    paned.add(weighted, weight=2)
    paned.add(plain)
    assert paned.pane(weighted, "weight") == 2
    assert paned.pane(0, "weight") == 2
    assert paned.pane(plain, "weight") == 0
    assert paned.pane(weighted, option="weight") == 2


@pytest.mark.parametrize("name", ["nope", "minsize", "-weight"])
def test_pane_refuses_an_option_ttk_panes_lack(root, name):
    paned = Panedwindow(root, name="pw")
    child = tkcurses.Frame(paned, name="a")
    paned.add(child)
    with pytest.raises(TclError, match=f'unknown option "-{name}"'):
        paned.pane(child, name)


def test_opening_the_dropdown_leaves_another_entrys_selection_alone(combobox):
    """combobox.tcl makes its list with -exportselection false, so selecting
    the current value there takes nothing from PRIMARY. TkCurses-9e8."""
    from tkcurses import Entry

    entry = Entry(combobox.master, name="other")
    entry.insert(0, "kept")
    entry.selection_range(0, 2)
    combobox.current(1)
    combobox._post()
    assert combobox._listbox.curselection() == (1,)
    assert entry.selection_present()


# A Treeview asks for its shown columns and its rows. It inherited a Frame's
# request, which waits for children a tree never has, so a packed tree asked
# for no width and drew nothing. Measured on Tk 9.0.2: a packed tree asks for
# its displayed columns' widths and `height` rows under the heading row, plus
# the border - 202x233 by default. Columns here are joined by a space each,
# and the sunken border is a cell each side.

EDGES = 2


def _tree_size(tree):
    return tree.winfo_reqwidth(), tree.winfo_reqheight()


def test_a_treeview_asks_for_its_columns_and_rows(root):
    tree = Treeview(root, name="t", columns=("a", "b"), height=4)
    tree.column("#0", width=8)
    tree.column("a", width=5)
    tree.column("b", width=3)
    assert _tree_size(tree) == (8 + 1 + 5 + 1 + 3 + EDGES, 4 + 1 + EDGES)


def test_a_treeview_without_headings_asks_for_no_heading_row(root):
    tree = Treeview(root, name="t", show="tree", height=3)
    assert _tree_size(tree) == (COLUMN_WIDTH + EDGES, 3 + EDGES)


def test_a_treeview_asks_only_for_the_columns_it_shows(root):
    tree = Treeview(
        root, name="t", columns=("a", "b"), displaycolumns=("b",), show="headings"
    )
    tree.column("b", width=6)
    assert tree.winfo_reqwidth() == 6 + EDGES


def test_a_treeview_asks_again_when_its_shape_changes(root):
    tree = Treeview(root, name="t", columns=("a",), show="headings", height=2)
    tree.column("a", width=9)
    tree.configure(height=6, columns=("a", "b"))
    tree.column("b", width=4)
    assert _tree_size(tree) == (9 + 1 + 4 + EDGES, 6 + 1 + EDGES)


# A heading's command runs when a click on it is released over it - Tk's
# ttk::treeview::heading.press and heading.release - through `after 0`, so a
# pass of the loop (update) runs it. It was stored and never called.


def _click_heading(tree, press_x, release_x=None, release_y=None):
    area = tree._rows_area()
    tree._handle(MouseEvent(button=1, state="pressed", x=press_x, y=area.y))
    tree._handle(
        MouseEvent(
            button=1,
            state="released",
            x=press_x if release_x is None else release_x,
            y=area.y if release_y is None else release_y,
        )
    )


def _column_x(tree, name):
    start = next(s for n, s, _ in tree._column_spans() if n == name)
    return tree._rows_area().x + start


def test_clicking_a_heading_runs_its_command(root, tree):
    calls = []
    tree.heading("size", command=lambda: calls.append("size"))
    tree.heading("#0", command=lambda: calls.append("#0"))
    _click_heading(tree, _column_x(tree, "size"))
    assert calls == []  # through after 0, not inside the release
    root.update()
    assert calls == ["size"]
    _click_heading(tree, _column_x(tree, "#0"))
    root.update()
    assert calls == ["size", "#0"]


def test_a_heading_release_elsewhere_runs_nothing(root, tree):
    calls = []
    tree.heading("size", command=lambda: calls.append("size"))
    tree.heading("#0", command=lambda: calls.append("#0"))
    size = _column_x(tree, "size")
    _click_heading(tree, size, release_x=_column_x(tree, "#0"))
    _click_heading(tree, size, release_y=tree._rows_area().y + 1)
    root.update()
    assert calls == []


def test_a_click_on_a_heading_takes_the_focus_and_selects_nothing(root, filled):
    filled.heading("size", command=lambda: None)
    _click_heading(filled, _column_x(filled, "size"))
    root.update()
    assert filled.selection() == ()
    assert root.focus_get() is filled


def test_a_heading_without_a_command_is_clicked_quietly(root, tree):
    _click_heading(tree, _column_x(tree, "size"))
    root.update()
