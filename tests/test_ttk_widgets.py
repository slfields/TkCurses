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
    Separator,
    Sizegrip,
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


def test_an_unweighted_paned_window_still_spreads_evenly(themed_root):
    """The CLASSIC widget's documented behaviour, which must not change.

    "Surplus and shortfall are both spread across the panes rather than given to
    one of them - which is what a person expects and what Tk's own
    -stretch middle default does." Weights are what the themed widget adds, so a
    pane that names none shares evenly, and the two widgets live in one layout
    engine.

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
            pw.add(tkcurses.Label(pw, name=f"c{width}{index}", text="pane"))
        pw.update_layout()
        return [child.winfo_width() for child in pw._paned.slaves()]

    grown = [b - a for a, b in zip(widths(30), widths(42), strict=True)]
    assert grown == [4, 4, 4], (
        f"a classic paned window shared its surplus as {grown} rather than "
        "evenly - weights have leaked into the widget that has no such option"
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
