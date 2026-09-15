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

"""Tests for the Frame widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Frame, Misc, TclError
from tkcurses._core.geometry import Rect, Size
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
    root._rect = Rect(0, 0, 40, 12)
    root._mapped = True
    return root


# ------------------------------------------------------------------ options


def test_a_frame_accepts_the_standard_options(root):
    keys = Frame(root, name="f").keys()
    for option in ("background", "borderwidth", "relief", "padx", "pady"):
        assert option in keys


def test_a_frame_adds_width_and_height(root):
    keys = Frame(root, name="f").keys()
    assert "width" in keys
    assert "height" in keys


def test_a_frame_has_no_border_by_default(root):
    """tkinter's default too: a plain frame is invisible until asked otherwise."""
    frame = Frame(root, name="f")
    assert frame.cget("borderwidth") == 0
    assert not frame._bordered


def test_a_borderwidth_gives_it_a_border(root):
    assert Frame(root, name="f", borderwidth=1)._bordered


def test_a_relief_gives_it_a_border_without_a_borderwidth(root):
    assert Frame(root, name="f", relief="raised")._bordered


def test_an_unknown_option_is_refused(root):
    with pytest.raises(TclError, match="unknown option"):
        Frame(root, name="f", nonsense=1)


def test_the_class_can_be_set_at_construction(root):
    frame = Frame(root, name="f", class_="Sidebar")
    assert frame.winfo_class() == "Sidebar"
    assert frame.bindtags()[1] == "Sidebar"


def test_a_frame_is_its_own_class_by_default(root):
    assert Frame(root, name="f").winfo_class() == "Frame"


# -------------------------------------------------------------------- size


def test_a_frame_asks_for_nothing_of_its_own_by_default(root):
    """Its size is whatever its children need."""
    frame = Frame(root, name="f")
    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (0, 0)


def test_an_explicit_size_is_requested(root):
    frame = Frame(root, name="f", width=20, height=6)
    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (20, 6)


def test_setting_only_a_width_leaves_the_height_to_the_children(root):
    frame = Frame(root, name="f")
    frame._requested = Size(8, 3)
    frame.configure(width=20)
    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (20, 3)


def test_resizing_by_configure_takes_effect(root):
    frame = Frame(root, name="f", width=10, height=2)
    frame.configure(width=30, height=8)
    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (30, 8)


# ---------------------------------------------------------------- as a tree


def test_a_frame_can_hold_children(root):
    frame = Frame(root, name="f")
    child = Frame(frame, name="child")
    assert frame.winfo_children() == [child]
    assert child.winfo_toplevel() is root


def test_a_frame_lays_its_children_out_with_its_own_manager(root):
    frame = Frame(root, name="f")
    frame._allocate(Rect(0, 0, 20, 6))
    frame._map()
    child = Frame(frame, name="child", width=4, height=1)
    child.pack(fill="both", expand=True)
    root.update_layout()
    assert child.winfo_width() == 20


def test_a_frame_packs_into_its_parent_like_any_widget(root):
    frame = Frame(root, name="f", width=10, height=2)
    frame.pack()
    root.update_layout()
    assert frame.winfo_manager() == "pack"
    assert frame.winfo_ismapped()


# ---------------------------------------------------------------- painting


def test_redrawing_without_a_screen_is_silent(root):
    """Every frame is in this state until the terminal is running."""
    frame = Frame(root, name="f", borderwidth=1)
    frame._allocate(Rect(0, 0, 10, 3))
    frame._map()
    frame._redraw()


def test_the_border_needs_room_for_two_edges(root):
    """A frame one cell wide has no interior and must not try to draw one."""
    frame = Frame(root, name="f", borderwidth=1)
    frame._allocate(Rect(0, 0, 1, 1))
    frame._map()
    frame._redraw()


def test_a_bordered_frame_offers_less_room_to_its_children(root):
    frame = Frame(root, name="f", borderwidth=1)
    frame._allocate(Rect(0, 0, 30, 8))
    content = frame._content_rect()
    assert (content.width, content.height) == (28, 6)


def test_an_unbordered_frame_offers_everything(root):
    frame = Frame(root, name="f")
    frame._allocate(Rect(0, 0, 30, 8))
    content = frame._content_rect()
    assert (content.width, content.height) == (30, 8)


def test_children_override_an_explicit_size(root):
    """Tk's rule, and the gotcha every tkinter user meets once.

    A frame's width and height are a request. Once it has children, its
    geometry manager works out what they need and that wins.
    """
    frame = Frame(root, name="f", width=24, height=8)
    child = Frame(frame, name="child", width=6, height=2)
    child.pack()
    root.update_layout()
    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (6, 2)


def test_propagation_off_keeps_the_explicit_size(root):
    frame = Frame(root, name="f", width=24, height=8)
    frame.pack_propagate(False)
    child = Frame(frame, name="child", width=6, height=2)
    child.pack()
    root.update_layout()
    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (24, 8)


# ------------------------------------------------- asking for its own border


def test_a_bordered_frame_asks_for_room_for_its_border(root):
    """It lays its children out *inside* the border, so it has to ask for
    the border as well as for them - or it clips them by exactly that much.

    This was real: a bordered frame holding three stacked rows reported that
    it needed three rows, drew a border on the first and last of them, and
    showed one row of the three.
    """
    frame = Frame(root, name="f", borderwidth=1)
    for index in range(3):
        Frame(frame, name=f"band{index}", width=9, height=1).pack()
    root.update_layout()
    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (11, 5)


def test_an_unbordered_frame_asks_for_exactly_its_children(root):
    frame = Frame(root, name="f")
    for index in range(3):
        Frame(frame, name=f"band{index}", width=9, height=1).pack()
    root.update_layout()
    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (9, 3)


def test_a_bordered_frame_gives_its_children_what_it_asked_for(root):
    """The two halves have to agree: whatever the frame asks its parent for,
    laying out inside it must leave the children the room they wanted."""
    frame = Frame(root, name="f", borderwidth=1)
    bands = [Frame(frame, name=f"band{i}", width=9, height=1) for i in range(3)]
    for band in bands:
        band.pack()
    root.update_layout()
    frame._allocate(Rect(0, 0, frame.winfo_reqwidth(), frame.winfo_reqheight()))
    root.update_layout()
    for band in bands:
        assert (band.winfo_width(), band.winfo_height()) == (9, 1), band


def test_padding_is_asked_for_too(root):
    """padx and pady come out of the content area the same way a border
    does, so they have to be added back the same way."""
    frame = Frame(root, name="f", padx=2, pady=1)
    Frame(frame, name="child", width=9, height=1).pack()
    root.update_layout()
    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (13, 3)
