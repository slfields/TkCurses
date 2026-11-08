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

"""Tests for the PanedWindow widget."""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from tkcurses import Frame, Label, Misc, PanedWindow, TclError
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
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    return root


@pytest.fixture
def paned(root):
    """A horizontal paned window 41 cells wide with three panes."""
    widget = PanedWindow(root, name="p", orient="horizontal")
    widget._allocate(Rect(0, 0, 41, 10))
    widget._map()
    for number in range(3):
        widget.add(Label(widget, name=f"l{number}", text=f"pane {number}"))
    widget.update_layout()
    return widget


def pane(paned, index):
    return paned._paned.slaves()[index]


# ------------------------------------------------------------------- panes


def test_panes_are_laid_out_side_by_side(paned):
    first, second = pane(paned, 0), pane(paned, 1)
    assert second.winfo_rootx() > first.winfo_rootx()
    assert second.winfo_rooty() == first.winfo_rooty()


def test_a_vertical_window_stacks_them(root):
    widget = PanedWindow(root, name="p", orient="vertical")
    widget._allocate(Rect(0, 0, 20, 21))
    widget._map()
    for number in range(2):
        widget.add(Label(widget, name=f"l{number}", text="x"))
    widget.update_layout()
    first, second = widget._paned.slaves()
    assert second.winfo_rooty() > first.winfo_rooty()
    assert second.winfo_rootx() == first.winfo_rootx()


def test_the_panes_fill_the_window(paned):
    total = sum(child.winfo_width() for child in paned._paned.slaves())
    assert total + 2 == 41  # two sashes between three panes


def test_panes_are_mapped_so_they_can_draw(paned):
    """Laying a pane out and never mapping it draws nothing at all."""
    assert all(child.winfo_ismapped() for child in paned._paned.slaves())


def test_panes_reports_the_widget_paths(paned):
    assert paned.panes() == [child._w for child in paned._paned.slaves()]


def test_a_pane_can_be_inserted_in_the_middle(paned):
    extra = Label(paned, name="x", text="new")
    paned.insert(1, extra)
    assert paned._paned.slaves()[1] is extra


def test_a_pane_can_be_forgotten(paned):
    doomed = pane(paned, 1)
    paned.forget(doomed)
    assert doomed not in paned._paned.slaves()
    assert not doomed.winfo_ismapped()


def test_forget_with_no_argument_still_unmanages_the_window(root):
    """PanedWindow overloads the name, as Tk does; both meanings are wanted."""
    frame = Frame(root, name="f")
    widget = PanedWindow(frame, name="p")
    widget.pack()
    widget.forget()
    assert widget not in frame._layout_manager.slaves(frame)


def test_a_minsize_is_honoured(root):
    widget = PanedWindow(root, name="p", orient="horizontal")
    widget._allocate(Rect(0, 0, 21, 6))
    widget._map()
    widget.add(Label(widget, name="a", text="a"), minsize=15)
    widget.add(Label(widget, name="b", text="b"))
    widget.update_layout()
    assert widget._paned.slaves()[0].winfo_width() >= 15


def test_an_unknown_pane_option_is_refused(paned):
    with pytest.raises(TclError, match="unknown option"):
        paned.add(Label(paned, name="x", text="x"), colour="red")


def test_panecget_reads_a_pane_option(paned):
    child = pane(paned, 0)
    paned.paneconfigure(child, minsize=4)
    assert paned.panecget(child, "minsize") == 4


def test_panecget_of_something_that_is_not_a_pane(root, paned):
    with pytest.raises(TclError, match="not managed"):
        paned.panecget(Label(root, name="stray", text="x"), "minsize")


# ------------------------------------------------------------------ sashes


def test_identify_finds_a_sash(paned):
    x, y = paned.sash_coord(0)
    assert paned.identify(x, y) == (0, "sash")


def test_identify_finds_nothing_in_the_middle_of_a_pane(paned):
    assert paned.identify(1, 1) == ()


def test_a_sash_can_be_placed(paned):
    paned.sash_place(0, 5, 0)
    assert pane(paned, 0).winfo_width() == 5


def test_moving_a_sash_leaves_the_far_pane_alone(paned):
    before = pane(paned, 2).winfo_width()
    paned.sash_place(0, 5, 0)
    assert pane(paned, 2).winfo_width() == before


def test_a_dragged_sash_survives_a_relayout(paned):
    """The whole reason a paned window remembers its sizes.

    A relayout that asked the children what they wanted would put the sash
    back where it started and undo what a person had just done.
    """
    paned.sash_place(0, 5, 0)
    paned._invalidate_layout()
    paned.update_layout()
    assert pane(paned, 0).winfo_width() == 5


def test_dragging_moves_the_sash(paned):
    x, y = paned.sash_coord(0)
    paned._handle(MouseEvent(button=1, state="pressed", x=x, y=y))
    paned._handle(MouseEvent(button=0, state="drag", x=6, y=y))
    assert pane(paned, 0).winfo_width() == 6


def test_dragging_from_somewhere_else_moves_nothing(paned):
    before = pane(paned, 0).winfo_width()
    paned._handle(MouseEvent(button=1, state="pressed", x=2, y=2))
    paned._handle(MouseEvent(button=0, state="drag", x=9, y=2))
    assert pane(paned, 0).winfo_width() == before


def test_the_arrows_move_the_active_sash(paned):
    """A terminal user with no mouse has no other way to resize a pane."""
    before = pane(paned, 0).winfo_width()
    paned._handle(KeyEvent(keysym="Right"))
    assert pane(paned, 0).winfo_width() == before + 1
    paned._handle(KeyEvent(keysym="Left"))
    assert pane(paned, 0).winfo_width() == before


def test_a_vertical_window_answers_the_other_two_arrows(root):
    widget = PanedWindow(root, name="p", orient="vertical")
    widget._allocate(Rect(0, 0, 20, 21))
    widget._map()
    for number in range(2):
        widget.add(Label(widget, name=f"l{number}", text="x"))
    widget.update_layout()
    before = widget._paned.slaves()[0].winfo_height()
    widget._handle(KeyEvent(keysym="Down"))
    assert widget._paned.slaves()[0].winfo_height() == before + 1


def test_an_unrelated_key_is_left_alone(paned):
    assert paned._handle(KeyEvent(keysym="Tab")) != "break"


def test_sash_coord_reports_where_the_sash_is(paned):
    paned.sash_place(0, 7, 0)
    assert paned.sash_coord(0)[0] == 7


def test_a_paned_window_takes_the_focus(root):
    assert PanedWindow(root, name="p")._takefocus is True


# --------------------------------- changing a pane keeps what is not changed
#
# TkCurses-z6pp. Measured on Tk 9.0.2: paneconfigure and a second add change
# only the options they are given. Here every option left out went back to its
# default, so setting a pane's sticky dropped its minsize to 0.


def _pane(paned, child):
    return {o: paned.panecget(child, o) for o in ("minsize", "sticky", "width")}


def test_paneconfigure_changes_only_what_it_is_given(root):
    paned = PanedWindow(root, name="q", orient="horizontal")
    child = Frame(paned, name="f")
    paned.add(child, minsize=10, sticky="n", width=50)
    paned.paneconfigure(child, sticky="s")
    assert _pane(paned, child) == {"minsize": 10, "sticky": "s", "width": 50}
    paned.paneconfigure(child, minsize=3)
    assert _pane(paned, child) == {"minsize": 3, "sticky": "s", "width": 50}
    paned.paneconfigure(child, width=20)
    assert _pane(paned, child) == {"minsize": 3, "sticky": "s", "width": 20}


def test_adding_a_pane_again_is_a_paneconfigure(root):
    paned = PanedWindow(root, name="q", orient="horizontal")
    child = Frame(paned, name="f")
    paned.add(child, minsize=10, sticky="n")
    paned.add(child, minsize=7)
    assert _pane(paned, child) == {"minsize": 7, "sticky": "n", "width": None}
    assert paned.panes() == [".q.f"], "still one pane, not two"


# ---------------------------------------------------------------------------
# Pack and grid beside the panes (TkCurses-ect9). Measured on Tk 9.0.2: both
# are accepted in a PanedWindow that has panes, and refuse only each other; a
# pane reports its manager as "panedwindow", and moving a widget between the
# panes and pack takes it out of the one it leaves.


def window_with_a_pane(root):
    window = PanedWindow(root, name="pw", bd=0, sashwidth=1, showhandle=0)
    window.place(x=0, y=0, width=30, height=10)
    pane = Frame(window, name="pane", width=5, height=2)
    window.add(pane)
    root.update_layout()
    return window, pane


def test_pack_lays_a_child_out_beside_the_panes(root):
    window, pane = window_with_a_pane(root)
    packed = Frame(window, name="packed", width=4, height=1)
    packed.pack(side="bottom")
    root.update_layout()
    assert packed.winfo_manager() == "pack"
    assert (packed.winfo_x(), packed.winfo_y()) == (13, 9)
    # The pane still has the whole window, as in Tk.
    assert (pane.winfo_width(), pane.winfo_height()) == (30, 10)
    assert window.panes() == [".pw.pane"]
    assert window.pack_slaves() == [packed]


def test_the_window_asks_for_what_pack_asks_while_pack_has_children(root):
    # Tk takes the request of whichever manager asked last.
    window, _pane = window_with_a_pane(root)
    assert (window.winfo_reqwidth(), window.winfo_reqheight()) == (5, 2)
    packed = Frame(window, width=4, height=1)
    packed.pack()
    root.update_layout()
    assert (window.winfo_reqwidth(), window.winfo_reqheight()) == (4, 1)
    packed.pack_forget()
    root.update_layout()
    assert (window.winfo_reqwidth(), window.winfo_reqheight()) == (5, 2)


def test_grid_is_accepted_and_then_refuses_pack(root):
    window, _pane = window_with_a_pane(root)
    Frame(window).grid()
    with pytest.raises(
        TclError,
        match=re.escape(
            'cannot use geometry manager "pack" inside ".pw": '
            "grid is already managing its content windows"
        ),
    ):
        Frame(window).pack()


def test_grid_is_refused_once_pack_has_a_child(root):
    window, _pane = window_with_a_pane(root)
    Frame(window).pack()
    with pytest.raises(
        TclError,
        match=re.escape(
            'cannot use geometry manager "grid" inside ".pw": '
            "pack is already managing its content windows"
        ),
    ):
        Frame(window).grid()


def test_a_pane_reports_panedwindow_and_forget_clears_it(root):
    window, pane = window_with_a_pane(root)
    assert pane.winfo_manager() == "panedwindow"
    window.forget(pane)
    assert pane.winfo_manager() == ""


def test_adding_a_packed_widget_takes_it_from_pack(root):
    window, _pane = window_with_a_pane(root)
    packed = Frame(window, name="packed")
    packed.pack()
    window.add(packed)
    assert packed.winfo_manager() == "panedwindow"
    assert window.pack_slaves() == []
    assert window.panes() == [".pw.pane", ".pw.packed"]


def test_packing_a_pane_takes_it_out_of_the_panes(root):
    window, pane = window_with_a_pane(root)
    pane.pack()
    assert pane.winfo_manager() == "pack"
    assert window.panes() == []
