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

import pytest

import tkcurses
from tkcurses import Misc, TclError
from tkcurses.ttk import (
    Combobox,
    LabeledScale,
    Notebook,
    OptionMenu,
    Progressbar,
    Separator,
    Sizegrip,
    Style,
    Treeview,
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
