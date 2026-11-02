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

"""Tests for the Menu widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import IntVar, Menu, Misc, StringVar, TclError
from tkcurses._core.events import KeyEvent, MouseEvent
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
    root._rect = Rect(0, 0, 60, 24)
    root._mapped = True
    return root


@pytest.fixture
def menu(root):
    widget = Menu(root, name="m")
    widget.add_command(label="New")
    widget.add_command(label="Open")
    widget.add_separator()
    widget.add_command(label="Quit")
    return widget


def posted(widget):
    """Post a menu with a screen big enough for it."""
    widget.post(0, 0)
    return widget


# ------------------------------------------------------------------ entries


def test_entries_are_added_in_order(menu):
    assert [menu.entrycget(n, "label") for n in (0, 1, 3)] == ["New", "Open", "Quit"]


def test_type_names_the_kind(menu):
    assert menu.type(0) == "command"
    assert menu.type(2) == "separator"


def test_every_kind_can_be_added(root):
    widget = Menu(root, name="m")
    other = Menu(root, name="o")
    widget.add_command(label="a")
    widget.add_cascade(label="b", menu=other)
    widget.add_checkbutton(label="c")
    widget.add_radiobutton(label="d")
    widget.add_separator()
    assert [widget.type(n) for n in range(5)] == [
        "command",
        "cascade",
        "checkbutton",
        "radiobutton",
        "separator",
    ]


def test_an_unknown_kind_is_refused(menu):
    with pytest.raises(TclError, match="bad menu entry type"):
        menu.add("submarine", label="no")


def test_an_option_the_kind_does_not_take_is_refused(menu):
    with pytest.raises(TclError, match="unknown option"):
        menu.add_command(label="a", value="no")


def test_insert_puts_an_entry_in_the_middle(menu):
    menu.insert_command(1, label="Reopen")
    assert menu.entrycget(1, "label") == "Reopen"
    assert menu.entrycget(2, "label") == "Open"


def test_delete_removes_one(menu):
    menu.delete(1)
    assert menu.entrycget(1, "label") == ""  # the separator


def test_delete_removes_a_range(menu):
    menu.delete(0, 2)
    assert menu.index("end") == 0
    assert menu.entrycget(0, "label") == "Quit"


def test_entryconfigure_changes_an_option(menu):
    menu.entryconfigure(0, label="Newer")
    assert menu.entrycget(0, "label") == "Newer"


def test_entryconfigure_of_nothing_is_refused(menu):
    with pytest.raises(TclError, match="bad menu entry index"):
        menu.entryconfigure(99, label="no")


def test_entrycget_of_an_unknown_option_is_refused(menu):
    with pytest.raises(TclError, match="unknown option"):
        menu.entrycget(0, "nonsense")


# ------------------------------------------------------------------ indices


def test_index_takes_a_number(menu):
    assert menu.index(1) == 1
    assert menu.index(99) is None


def test_index_takes_end_and_last(menu):
    assert menu.index("end") == 3
    assert menu.index("last") == 3


def test_index_takes_none(menu):
    assert menu.index("none") is None


def test_index_takes_active(menu):
    menu.activate(1)
    assert menu.index("active") == 1


def test_index_takes_a_label(menu):
    assert menu.index("Quit") == 3
    assert menu.index("Nothing") is None


def test_index_takes_a_row(menu):
    posted(menu)
    area = menu._text_area()
    assert menu.index(f"@{area.y}") == 0
    assert menu.index(f"@{area.y + 1}") == 1


def test_index_of_an_empty_menu(root):
    assert Menu(root, name="m").index("end") is None


# ----------------------------------------------------------------- invoking


def test_invoke_runs_the_command(menu):
    seen = []
    menu.entryconfigure(0, command=lambda: seen.append(1))
    menu.invoke(0)
    assert seen == [1]


def test_invoke_returns_what_the_command_returns(menu):
    menu.entryconfigure(0, command=lambda: "result")
    assert menu.invoke(0) == "result"


def test_invoking_a_separator_does_nothing(menu):
    assert menu.invoke(2) is None


def test_a_disabled_entry_does_not_run(menu):
    seen = []
    menu.entryconfigure(0, command=lambda: seen.append(1), state="disabled")
    menu.invoke(0)
    assert seen == []


def test_a_checkbutton_entry_toggles_its_variable(root):
    variable = IntVar(root, 0)
    widget = Menu(root, name="m")
    widget.add_checkbutton(label="Wrap", variable=variable)
    widget.invoke(0)
    assert variable.get() == 1
    widget.invoke(0)
    assert variable.get() == 0


def test_a_checkbutton_entry_takes_its_own_values(root):
    variable = StringVar(root, "off")
    widget = Menu(root, name="m")
    widget.add_checkbutton(
        label="Wrap", variable=variable, onvalue="on", offvalue="off"
    )
    widget.invoke(0)
    assert variable.get() == "on"


def test_a_radiobutton_entry_sets_its_variable(root):
    variable = StringVar(root, "")
    widget = Menu(root, name="m")
    for word in ("small", "large"):
        widget.add_radiobutton(label=word, variable=variable, value=word)
    widget.invoke(1)
    assert variable.get() == "large"


def test_invoking_a_cascade_opens_it_rather_than_running_anything(root):
    sub = Menu(root, name="s")
    sub.add_command(label="Nested")
    widget = Menu(root, name="m")
    widget.add_cascade(label="More", menu=sub)
    posted(widget)
    widget.invoke(0)
    assert sub._posted


def test_invoking_a_command_dismisses_the_menu(menu):
    posted(menu)
    menu.invoke(0)
    assert not menu._posted


# ------------------------------------------------------------------ activity


def test_activate_sets_the_active_entry(menu):
    menu.activate(1)
    assert menu._active == 1


def test_a_separator_cannot_be_activated(menu):
    menu.activate(1)
    menu.activate(2)
    assert menu._active == 1


def test_a_disabled_entry_cannot_be_activated(menu):
    menu.entryconfigure(1, state="disabled")
    menu.activate(0)
    menu.activate(1)
    assert menu._active == 0


def test_stepping_skips_separators_and_disabled_entries(menu):
    """An arrow landing on one would look like the key did nothing."""
    menu.entryconfigure(1, state="disabled")
    menu.activate(0)
    menu._step(1)
    assert menu._active == 3


def test_stepping_wraps_round(menu):
    menu.activate(3)
    menu._step(1)
    assert menu._active == 0


def test_stepping_backwards_wraps_too(menu):
    menu.activate(0)
    menu._step(-1)
    assert menu._active == 3


# ------------------------------------------------------------------ posting


def test_posting_puts_the_menu_on_screen(menu):
    posted(menu)
    assert menu._posted
    assert menu.winfo_ismapped()


def test_posting_takes_the_grab_and_the_focus(menu):
    """So that a click anywhere, including away from it, reaches the menu."""
    posted(menu)
    assert menu.grab_current() is menu
    assert menu.focus_get() is menu


def test_unposting_releases_them(menu):
    posted(menu)
    menu.unpost()
    assert not menu._posted
    assert menu.grab_current() is not menu


def test_unposting_twice_is_harmless(menu):
    posted(menu)
    menu.unpost()
    menu.unpost()


def test_the_postcommand_runs_before_the_menu_appears(menu):
    seen = []
    menu.configure(postcommand=lambda: seen.append(1))
    posted(menu)
    assert seen == [1]


def test_a_menu_near_the_bottom_is_flipped_above_its_point(menu):
    """The screen, not the root's rect, is what a posted menu is placed in."""
    _, screen_height = menu._screen_size()
    menu.post(0, screen_height - 1)
    assert menu.winfo_rooty() < screen_height - 1
    assert menu.winfo_rooty() + menu._rect.height <= screen_height


def test_a_menu_near_the_right_is_pulled_left(menu):
    screen_width, _ = menu._screen_size()
    menu.post(screen_width - 1, 0)
    assert menu.winfo_rootx() + menu._rect.width <= screen_width


def test_tk_popup_can_make_an_entry_active(menu):
    menu.tk_popup(0, 0, 1)
    assert menu._active == 1


def test_unposting_closes_any_submenu(root):
    sub = Menu(root, name="s")
    sub.add_command(label="Nested")
    widget = Menu(root, name="m")
    widget.add_cascade(label="More", menu=sub)
    posted(widget)
    widget.invoke(0)
    widget.unpost()
    assert not sub._posted


def test_closing_a_submenu_gives_the_grab_back(root):
    sub = Menu(root, name="s")
    sub.add_command(label="Nested")
    widget = Menu(root, name="m")
    widget.add_cascade(label="More", menu=sub)
    posted(widget)
    widget.invoke(0)
    sub.unpost()
    assert widget.grab_current() is widget


# ----------------------------------------------------------------- keyboard


def test_arrows_move_the_active_entry(menu):
    posted(menu)
    menu._handle(KeyEvent(keysym="Down"))
    assert menu._active == 0
    menu._handle(KeyEvent(keysym="Down"))
    assert menu._active == 1


def test_home_and_end_reach_the_two_ends(menu):
    posted(menu)
    menu._handle(KeyEvent(keysym="End"))
    assert menu._active == 3
    menu._handle(KeyEvent(keysym="Home"))
    assert menu._active == 0


def test_return_invokes_the_active_entry(menu):
    seen = []
    menu.entryconfigure(0, command=lambda: seen.append(1))
    posted(menu)
    menu.activate(0)
    menu._handle(KeyEvent(keysym="Return"))
    assert seen == [1]


def test_escape_dismisses(menu):
    posted(menu)
    menu._handle(KeyEvent(keysym="Escape"))
    assert not menu._posted


def test_a_mnemonic_chooses_its_entry(menu):
    seen = []
    menu.entryconfigure(3, underline=0, command=lambda: seen.append("quit"))
    posted(menu)
    menu._handle(KeyEvent(keysym="q", char="q"))
    assert seen == ["quit"]


def test_an_unrelated_key_is_not_swallowed(menu):
    posted(menu)
    assert menu._handle(KeyEvent(keysym="z", char="z")) != "break"


def test_right_opens_a_cascade(root):
    sub = Menu(root, name="s")
    sub.add_command(label="Nested")
    widget = Menu(root, name="m")
    widget.add_cascade(label="More", menu=sub)
    posted(widget)
    widget.activate(0)
    widget._handle(KeyEvent(keysym="Right"))
    assert sub._posted


def test_left_closes_a_submenu(root):
    sub = Menu(root, name="s")
    sub.add_command(label="Nested")
    widget = Menu(root, name="m")
    widget.add_cascade(label="More", menu=sub)
    posted(widget)
    widget.invoke(0)
    sub._handle(KeyEvent(keysym="Left"))
    assert not sub._posted
    assert widget._posted


# -------------------------------------------------------------------- mouse


def test_clicking_an_entry_invokes_it(menu):
    seen = []
    menu.entryconfigure(1, command=lambda: seen.append(1))
    posted(menu)
    area = menu._text_area()
    menu._handle(MouseEvent(button=1, state="pressed", x=area.x, y=area.y + 1))
    assert seen == [1]


def test_clicking_away_dismisses(menu):
    """The grab is what makes a click anywhere reach the menu at all."""
    posted(menu)
    menu._handle(MouseEvent(button=1, state="pressed", x=55, y=20))
    assert not menu._posted


def test_moving_over_an_entry_activates_it(menu):
    posted(menu)
    area = menu._text_area()
    menu._handle(MouseEvent(button=0, state="motion", x=area.x, y=area.y + 1))
    assert menu._active == 1


# ----------------------------------------------------------------- scrolling


def test_a_menu_taller_than_the_screen_is_clipped_to_it(root):
    widget = Menu(root, name="m")
    for n in range(40):
        widget.add_command(label=f"Item {n}")
    widget.post(0, 0)
    assert widget._rect.height <= 24


def test_the_view_follows_the_active_entry(root):
    widget = Menu(root, name="m")
    for n in range(40):
        widget.add_command(label=f"Item {n}")
    widget.post(0, 0)
    widget.activate(39)
    assert widget._first > 0
    assert widget._first <= 39 < widget._first + widget._rows()


# ----------------------------------------------------------------- menubar


def test_a_menubar_entry_is_found_by_column(root):
    bar = Menu(root, name="b")
    bar._as_menubar = True
    bar.add_cascade(label="File")
    bar.add_cascade(label="Edit")
    bar._apply_requested_size()
    bar._allocate(Rect(0, 0, bar._requested.width, 1))
    assert bar._entry_at_column(1) == 0
    assert bar._entry_at_column(8) == 1


def test_choosing_from_a_bar_dropdown_closes_it(root):
    """A menubar is never itself posted, so dismissal cannot stop at it.

    Walking up to the root menu and unposting that left the dropdown on
    screen: the root was the bar, and the bar had nothing to unpost.
    """
    seen = []
    bar = Menu(root, name="b")
    bar._as_menubar = True
    dropdown = Menu(root, name="d")
    dropdown.add_command(label="Quit", command=lambda: seen.append(1))
    bar.add_cascade(label="File", menu=dropdown)
    bar._apply_requested_size()
    bar._allocate(Rect(0, 0, bar._requested.width, 1))
    bar.invoke(0)
    assert dropdown._posted
    dropdown.invoke(0)
    assert seen == [1]
    assert not dropdown._posted
    assert bar._open_cascade is None


def test_clicking_away_from_a_bar_dropdown_closes_it(root):
    bar = Menu(root, name="b")
    bar._as_menubar = True
    dropdown = Menu(root, name="d")
    dropdown.add_command(label="Quit")
    bar.add_cascade(label="File", menu=dropdown)
    bar._apply_requested_size()
    bar._allocate(Rect(0, 0, bar._requested.width, 1))
    bar.invoke(0)
    dropdown._handle(MouseEvent(button=1, state="pressed", x=55, y=20))
    assert not dropdown._posted


def test_dismissing_a_menu_does_not_keep_the_keyboard(root):
    """Reported from UAT 25: Escape stopped closing the application.

    When nothing held the focus before a menu was posted there was nothing
    to give it back to, and the focus was left on the menu - which by then
    was unmapped. Every key afterwards went to a widget nobody could see,
    so bindings further out, including the Escape that quits, never fired.
    """
    menu = Menu(root, name="m")
    menu.add_command(label="One")
    assert root.focus_get() is None
    menu.post(0, 0)
    assert menu.focus_get() is menu
    menu.unpost()
    assert root.focus_get() is None


def test_dismissing_gives_the_focus_back_to_whoever_had_it(root):
    holder = Menu(root, name="other")
    holder.add_command(label="x")
    holder.focus_set()
    menu = Menu(root, name="m")
    menu.add_command(label="One")
    menu.post(0, 0)
    menu.unpost()
    assert root.focus_get() is holder


def test_clicking_away_from_a_bar_dropdown_frees_the_keyboard(root):
    bar = Menu(root, name="b")
    bar._as_menubar = True
    dropdown = Menu(root, name="d")
    dropdown.add_command(label="Quit")
    bar.add_cascade(label="File", menu=dropdown)
    bar._apply_requested_size()
    bar._allocate(Rect(0, 0, bar._requested.width, 1))
    bar.invoke(0)
    dropdown._handle(MouseEvent(button=1, state="pressed", x=55, y=20))
    assert root.focus_get() is None


# ------------------------------------- setting and removing a window's menubar
#
# TkCurses-un8i. Measured on Tk 9.0.2: menu="" removes the bar and leaves the
# menu in existence; a path name works as well as the widget; a name that
# matches nothing is stored as given and shows no bar.


@pytest.fixture
def window(root):
    from tkcurses import Frame, Toplevel

    top = Toplevel(root, name="top")
    top._allocate(Rect(0, 0, 30, 10))
    top._map()
    top.body = Frame(top, name="body")
    top.body.pack(fill="both", expand=True)
    top.bars = []
    for label in ("One", "Two"):
        bar = Menu(top, name=label.lower())
        bar.add_cascade(label=label)
        top.bars.append(bar)
    top.top_row = _body_row(top)
    return top


def _body_row(window):
    """How far down the window its contents start: its border, plus any bar."""
    window.update_layout()
    return window.body.winfo_y()


def _shows_bar(window):
    return _body_row(window) == window.top_row + 1


def test_an_empty_menu_removes_the_menubar(window):
    one = window.bars[0]
    window.configure(menu=one)
    assert _shows_bar(window)
    window.configure(menu="")
    assert window.cget("menu") == ""
    assert not _shows_bar(window), "the row goes back to the children"
    assert not one.winfo_ismapped() and not one._as_menubar
    assert one.winfo_exists(), "removed from the window, not destroyed"


def test_a_window_can_be_built_with_no_menubar(root):
    """It never crashed, but it took a row from the children for a bar not there."""
    from tkcurses import Toplevel

    plain = Toplevel(root, name="plain")
    empty = Toplevel(root, name="empty", menu="")
    for top in (plain, empty):
        top._allocate(Rect(0, 0, 30, 10))
    assert empty.cget("menu") == ""
    assert empty._content_rect() == plain._content_rect()


def test_a_new_menubar_replaces_the_old_one(window):
    one, two = window.bars
    window.configure(menu=one)
    window.configure(menu=two)
    assert _shows_bar(window)
    assert two.winfo_ismapped() and two._as_menubar
    assert not one.winfo_ismapped(), "the old bar was left drawn over the new"
    assert not one._as_menubar


def test_a_menubar_can_be_named_by_its_path(window):
    one = window.bars[0]
    window.configure(menu=str(one))
    assert _shows_bar(window)
    assert one.winfo_ismapped() and one._as_menubar


@pytest.mark.parametrize("name", [".nosuch", ".top.body"])
def test_a_name_that_is_no_menu_is_kept_and_shows_no_bar(window, name):
    window.configure(menu=window.bars[0])
    window.configure(menu=name)
    assert window.cget("menu") == name
    assert not _shows_bar(window)
    assert not window.bars[0].winfo_ismapped()


def test_none_removes_the_bar_it_used_to_leave_drawn(window):
    """Before, None gave the row back to the children with the bar still on it.

    tkinter itself ignores an option given as None (TkCurses-bx5b); until this
    library does too, None at least has to leave the window consistent.
    """
    one = window.bars[0]
    window.configure(menu=one)
    window.configure(menu=None)
    assert not _shows_bar(window)
    assert not one.winfo_ismapped()
