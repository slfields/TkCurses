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

"""Tests for the Listbox widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Listbox, Misc, TclError
from tkcurses._core.events import MOD_SHIFT, KeyEvent, MouseEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def stack():
    return PanelStack(window_factory=stub_window, panel_factory=None)


@pytest.fixture
def root(stack):
    root = Misc()
    root.tk.panels = stack
    root._rect = Rect(0, 0, 40, 20)
    root._mapped = True
    return root


@pytest.fixture
def listbox(root):
    box = Listbox(root, name="lb", height=4, width=16)
    box._allocate(Rect(0, 0, 18, 6))
    box._map()
    box.insert("end", *[f"item {n}" for n in range(8)])
    return box


def press(widget, keysym, state=0):
    widget._handle(KeyEvent(keysym=keysym, char="", modifiers=state))


# ------------------------------------------------------------------ contents


def test_a_new_listbox_is_empty(root):
    assert Listbox(root, name="lb").size() == 0


def test_inserting_at_the_end(listbox):
    listbox.insert("end", "last")
    assert listbox.get("end") == ""
    assert listbox.size() == 9
    assert listbox.get(8) == "last"


def test_inserting_in_the_middle(listbox):
    listbox.insert(1, "wedged")
    assert listbox.get(1) == "wedged"
    assert listbox.size() == 9


def test_getting_a_range(listbox):
    assert listbox.get(1, 3) == ("item 1", "item 2", "item 3")


def test_deleting_one_item(listbox):
    listbox.delete(0)
    assert listbox.get(0) == "item 1"
    assert listbox.size() == 7


def test_deleting_a_range_is_inclusive(listbox):
    """Tk's listbox ranges include the last index, unlike an entry's."""
    listbox.delete(0, 2)
    assert listbox.size() == 5
    assert listbox.get(0) == "item 3"


def test_deleting_everything(listbox):
    listbox.delete(0, "end")
    assert listbox.size() == 0


# ------------------------------------------------------------------ indices


def test_end_is_the_count(listbox):
    assert listbox.index("end") == 8


def test_active_is_the_active_item(listbox):
    listbox.activate(3)
    assert listbox.index("active") == 3


def test_a_bad_index_is_refused(listbox):
    with pytest.raises(TclError, match="bad listbox index"):
        listbox.index("sideways")


# ---------------------------------------------------------------- selection


def test_nothing_is_selected_to_begin_with(listbox):
    assert listbox.curselection() == ()


def test_selecting_one_item(listbox):
    listbox.selection_set(2)
    assert listbox.curselection() == (2,)
    assert listbox.selection_includes(2)


def test_clearing_the_selection(listbox):
    listbox.selection_set(2)
    listbox.selection_clear(0, "end")
    assert listbox.curselection() == ()


def test_browse_mode_keeps_one_selection(listbox):
    listbox.selection_set(1)
    listbox.selection_set(3)
    assert listbox.curselection() == (3,)


def test_multiple_mode_keeps_several(listbox):
    listbox.configure(selectmode="multiple")
    listbox.selection_set(1)
    listbox.selection_set(3)
    assert listbox.curselection() == (1, 3)


def test_extended_mode_selects_a_range(listbox):
    listbox.configure(selectmode="extended")
    listbox.selection_set(1, 3)
    assert listbox.curselection() == (1, 2, 3)


def test_selecting_fires_the_virtual_event(listbox):
    seen = []
    listbox.bind("<<ListboxSelect>>", lambda event: seen.append(1))
    listbox.selection_set(1)
    assert seen == [1]


def test_the_selection_follows_deleted_items(listbox):
    listbox.configure(selectmode="multiple")
    listbox.selection_set(4)
    listbox.delete(0, 1)
    assert listbox.curselection() == (2,)


def test_deleting_a_selected_item_deselects_it(listbox):
    listbox.selection_set(2)
    listbox.delete(2)
    assert listbox.curselection() == ()


def test_inserting_moves_the_selection_along(listbox):
    listbox.selection_set(3)
    listbox.insert(0, "new")
    assert listbox.curselection() == (4,)


# ------------------------------------------------------------------ keyboard


def test_the_arrows_move_the_active_item(listbox):
    listbox.activate(0)
    press(listbox, "Down")
    assert listbox.index("active") == 1
    press(listbox, "Up")
    assert listbox.index("active") == 0


def test_browse_mode_drags_the_selection_with_the_arrows(listbox):
    listbox.activate(0)
    press(listbox, "Down")
    assert listbox.curselection() == (1,)


def test_single_mode_moves_without_selecting(listbox):
    """The active item and the selection are different things."""
    listbox.configure(selectmode="single")
    listbox.activate(0)
    press(listbox, "Down")
    assert listbox.index("active") == 1
    assert listbox.curselection() == ()


def test_space_selects_the_active_item(listbox):
    listbox.configure(selectmode="multiple")
    listbox.activate(2)
    press(listbox, "space")
    assert listbox.curselection() == (2,)


def test_space_toggles_in_multiple_mode(listbox):
    listbox.configure(selectmode="multiple")
    listbox.activate(2)
    press(listbox, "space")
    press(listbox, "space")
    assert listbox.curselection() == ()


def test_home_and_end_jump(listbox):
    listbox.activate(3)
    press(listbox, "Home")
    assert listbox.index("active") == 0
    press(listbox, "End")
    assert listbox.index("active") == 7


def test_an_unhandled_key_is_left_alone(listbox):
    assert listbox._handle(KeyEvent(keysym="F1", char="")) is False


def test_a_handled_key_stops_there(listbox):
    assert listbox._handle(KeyEvent(keysym="Down", char="")) is True


# --------------------------------------------------------------------- mouse


def test_clicking_selects_a_row(listbox):
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=2))
    assert listbox.curselection() == (1,)


def test_clicking_takes_the_focus(listbox):
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=1))
    assert listbox.focus_get() is listbox


def test_clicking_past_the_last_item_selects_nothing(listbox):
    listbox.delete(0, "end")
    listbox.insert("end", "only")
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=4))
    assert listbox.curselection() == ()


def test_shift_clicking_extends_in_extended_mode(listbox):
    listbox.configure(selectmode="extended")
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=1))
    listbox._handle(
        MouseEvent(button=1, state="pressed", x=2, y=3, modifiers=MOD_SHIFT)
    )
    assert listbox.curselection() == (0, 1, 2)


def test_the_wheel_scrolls_without_selecting(listbox):
    listbox.selection_set(0)
    listbox._handle(MouseEvent(button=5, state="pressed", x=2, y=2))
    assert listbox._top == 1
    assert listbox.curselection() == (0,)


# ------------------------------------------------------------------ scrolling


def test_a_short_list_does_not_scroll(listbox):
    listbox.delete(0, "end")
    listbox.insert("end", "one", "two")
    assert listbox._top == 0


def test_see_scrolls_an_item_into_view(listbox):
    listbox.see(7)
    assert listbox._top == 7 - 4 + 1


def test_see_only_moves_as_far_as_it_must(listbox):
    listbox.see(7)
    before = listbox._top
    listbox.see(5)
    assert listbox._top == before


def test_activating_scrolls_into_view(listbox):
    listbox.activate(7)
    assert listbox._top > 0


def test_the_view_is_clamped_to_the_list(listbox):
    listbox.yview(99)
    assert listbox._top == 8 - 4


def test_bbox_reports_a_visible_row(listbox):
    assert listbox.bbox(0) is not None


def test_bbox_of_a_scrolled_out_row_is_nothing(listbox):
    assert listbox.bbox(7) is None


def test_nearest_finds_the_row_under_a_position_in_the_widget(listbox):
    # Widget-relative, as Tk's is. This asserted a screen row until
    # TkCurses-9hr, which is why listbox.nearest(event.y) - the tkinter
    # idiom - answered with the first item for every click.
    assert listbox.nearest(2) == 1


# -------------------------------------------------------------------- state


def test_a_disabled_listbox_ignores_keys(listbox):
    listbox.configure(state="disabled")
    listbox.activate(0)
    press(listbox, "Down")
    assert listbox.index("active") == 0


def test_a_disabled_listbox_ignores_clicks(listbox):
    listbox.configure(state="disabled")
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=2))
    assert listbox.curselection() == ()


def test_a_listbox_asks_for_its_rows_and_columns(root):
    box = Listbox(root, name="lb", width=30, height=5)
    assert box.winfo_reqwidth() == 30 + 2
    assert box.winfo_reqheight() == 5 + 2


# ----------------------------------------------------------- scrollbar pair


def test_yview_reports_the_window_as_fractions(listbox):
    """What a scrollbar wants, and what tkinter's yview() returns."""
    first, last = listbox.yview()
    assert first == 0.0
    assert 0.0 < last <= 1.0


def test_yview_moveto_scrolls(listbox):
    listbox.yview("moveto", 0.5)
    assert listbox._top == 4


def test_yview_scroll_by_units(listbox):
    listbox.yview("scroll", 2, "units")
    assert listbox._top == 2


def test_yview_scroll_by_pages(listbox):
    listbox.yview("scroll", 1, "pages")
    assert listbox._top == 4


def test_the_scroll_command_is_told_where_the_view_is(listbox):
    reports = []
    listbox.configure(yscrollcommand=lambda first, last: reports.append((first, last)))
    listbox.yview("scroll", 1, "units")
    assert reports
    assert reports[-1][0] > 0


def test_a_scrollbar_and_a_listbox_drive_each_other(root):
    """Neither knows what the other is; both speak Tk's scrolling protocol."""
    from tkcurses import Scrollbar

    listbox = Listbox(root, name="lb", height=4, width=16)
    listbox._allocate(Rect(0, 0, 18, 6))
    listbox._map()
    listbox.insert("end", *[f"item {n}" for n in range(20)])
    bar = Scrollbar(root, name="sb", command=listbox.yview)
    listbox.configure(yscrollcommand=bar.set)

    listbox.yview("scroll", 4, "units")
    first, _ = bar.get()
    assert first > 0

    bar._options["command"]("moveto", 0.0)
    assert listbox._top == 0


# ------------------------------------------------------ the horizontal view
#
# Missing outright until TkCurses-019. Every expectation below was measured
# on Tk 9.0.2 with a 10-character-wide listbox holding a 30-character item.


@pytest.fixture
def wide(root):
    """Ten cells of text between the markers, as Tk's width=10 has."""
    box = Listbox(root, name="wide", height=4)
    box._allocate(Rect(0, 0, 14, 6))
    box._map()
    box.insert("end", "x" * 30, "short")
    assert box._body_width() == 10
    return box


def test_xview_reports_the_columns_as_fractions_of_the_widest_item(wide):
    assert wide.xview() == (0.0, 10 / 30)


def test_xview_scroll_a_unit_is_one_character(wide):
    wide.xview_scroll(1, "units")
    assert wide.xview() == (1 / 30, 11 / 30)


def test_xview_scroll_a_page_is_the_width_less_two(wide):
    wide.xview_scroll(1, "pages")
    assert wide._left == 8


def test_a_page_is_never_less_than_one_character(root):
    box = Listbox(root, name="narrow")
    box._allocate(Rect(0, 0, 7, 6))  # three cells of text
    box._map()
    box.insert("end", "x" * 100)
    box.xview_scroll(1, "pages")
    assert box._left == 1


@pytest.mark.parametrize("fraction", [0.49, 0.51])
def test_xview_moveto_rounds_to_the_nearest_character(wide, fraction):
    wide.xview_moveto(fraction)
    assert wide._left == 15


@pytest.mark.parametrize(("half", "expected"), [(0.5, 1), (2.5, 3), (4.5, 5)])
def test_xview_moveto_rounds_halves_up(wide, half, expected):
    """Measured on Tk 9.0.2 over a 30-character item: 2.5 -> 3, 4.5 -> 5.

    Python's round() sends halves to the even neighbour - 2.5 -> 2 - which is
    what this did until TkCurses-5e0.
    """
    wide.xview_moveto(half / 30)
    assert wide._left == expected


def test_xview_moveto_stops_at_the_end_of_the_widest_item(wide):
    wide.xview_moveto(1.0)
    assert wide.xview() == (20 / 30, 1.0)


def test_xview_moveto_stops_at_the_start(wide):
    wide.xview_moveto(-1)
    assert wide._left == 0


def test_xview_with_an_index_is_a_character_offset_clamped_to_the_end(wide):
    wide.xview(3)
    assert wide._left == 3
    wide.xview(99)
    assert wide._left == 20


def test_the_offset_holds_when_the_wide_item_goes(wide):
    """Tk's own: measured (0.2, 1.0) over the five-character remainder."""
    wide.xview_scroll(1, "units")
    wide.delete(0)
    assert wide.xview() == (0.2, 1.0)


def test_an_empty_listbox_is_all_showing_both_ways(root):
    box = Listbox(root, name="empty")
    assert box.xview() == (0.0, 1.0)
    assert box.yview() == (0.0, 1.0)


def test_xview_refuses_a_bad_unit(wide):
    with pytest.raises(TclError, match='bad argument "bogus": must be pages or units'):
        wide.xview("scroll", 1, "bogus")


def test_xview_refuses_a_bad_subcommand(wide):
    with pytest.raises(TclError, match='expected integer but got "bogus"'):
        wide.xview("bogus")


def test_the_horizontal_scroll_command_is_told_where_the_view_is(wide):
    reports = []
    wide.configure(xscrollcommand=lambda first, last: reports.append((first, last)))
    wide.xview_scroll(2, "units")
    assert reports[-1] == (2 / 30, 12 / 30)


@pytest.mark.parametrize(
    ("call", "args"),
    [
        ("xview_moveto", (0.5,)),
        ("xview_scroll", (1, "units")),
        ("yview_moveto", (0.0,)),
        ("yview_scroll", (1, "units")),
    ],
)
def test_the_named_scroll_methods_return_none(wide, call, args):
    assert getattr(wide, call)(*args) is None


def test_yview_scroll_and_moveto_are_the_named_forms(listbox):
    listbox.yview_scroll(2, "units")
    assert listbox._top == 2
    listbox.yview_moveto(0.0)
    assert listbox._top == 0
