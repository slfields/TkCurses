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

"""Panel stacking, which needs no terminal: an order is an order."""

from __future__ import annotations

import pytest

from tkcurses import panel as tcpanel
from tkcurses._core.screen import ScreenBuffer
from tkcurses.curses import Window


@pytest.fixture(autouse=True)
def empty_stack():
    """The stack is process-wide, as curses.panel's is. Empty it each time."""
    tcpanel._reset()
    yield
    tcpanel._reset()


def make_window(rows=3, cols=8, y=0, x=0):
    return Window(ScreenBuffer(cols, rows), y, x, rows, cols, owns=True)


@pytest.fixture
def three():
    """Three panels, bottom to top."""
    return [tcpanel.new_panel(make_window()) for _ in range(3)]


# -------------------------------------------------------------------- order


def test_a_new_panel_goes_on_top(three):
    assert tcpanel.top_panel() is three[-1]


def test_the_first_panel_is_at_the_bottom(three):
    assert tcpanel.bottom_panel() is three[0]


def test_above_and_below_walk_the_stack(three):
    bottom, middle, top = three
    assert middle.above() is top
    assert middle.below() is bottom
    assert top.above() is None
    assert bottom.below() is None


def test_top_brings_a_panel_to_the_front(three):
    bottom = three[0]
    bottom.top()
    assert tcpanel.top_panel() is bottom
    assert bottom.above() is None


def test_bottom_sends_a_panel_to_the_back(three):
    top = three[-1]
    top.bottom()
    assert tcpanel.bottom_panel() is top
    assert top.below() is None


def test_raising_the_top_panel_changes_nothing(three):
    order = list(tcpanel._stack)
    three[-1].top()
    assert tcpanel._stack == order


# --------------------------------------------------------------- visibility


def test_a_panel_starts_visible(three):
    assert not three[0].hidden()


def test_hiding_takes_it_out_of_the_reckoning(three):
    three[-1].hide()
    assert three[-1].hidden()
    assert tcpanel.top_panel() is three[-2]


def test_hiding_every_panel_leaves_nothing_on_top(three):
    for panel in three:
        panel.hide()
    assert tcpanel.top_panel() is None
    assert tcpanel.bottom_panel() is None


def test_showing_puts_it_back(three):
    three[0].hide()
    three[0].show()
    assert not three[0].hidden()
    assert tcpanel.bottom_panel() is three[0]


# ------------------------------------------------------------- the window


def test_a_panel_remembers_its_window():
    window = make_window()
    assert tcpanel.new_panel(window).window() is window


def test_replace_swaps_the_window_and_keeps_the_place(three):
    replacement = make_window()
    three[1].replace(replacement)
    assert three[1].window() is replacement
    assert three[1].above() is three[2]


def test_move_moves_the_window():
    panel = tcpanel.new_panel(make_window())
    panel.move(4, 5)
    assert panel.window().getbegyx() == (4, 5)


def test_the_userptr_carries_anything():
    """curses' own escape hatch, and the widgets use it to find themselves."""
    panel = tcpanel.new_panel(make_window())
    assert panel.userptr() is None
    marker = object()
    panel.set_userptr(marker)
    assert panel.userptr() is marker


# ------------------------------------------------------------------ update


def test_update_panels_needs_a_screen(three):
    """It copies onto the screen, so there has to be one."""
    import curses as stdlib_curses

    with pytest.raises(stdlib_curses.error, match="initscr"):
        tcpanel.update_panels()


def test_update_panels_skips_the_hidden_ones():
    """Checked by what it asks of each window rather than by drawing, which
    is the part that needs a terminal."""
    asked = []

    class Recording(Window):
        def touchwin(self):
            asked.append(self)

        def noutrefresh(self):
            pass

    shown = Recording(ScreenBuffer(8, 3), 0, 0, 3, 8, owns=True)
    hidden = Recording(ScreenBuffer(8, 3), 0, 0, 3, 8, owns=True)
    tcpanel.new_panel(shown)
    tcpanel.new_panel(hidden).hide()
    tcpanel.update_panels()
    assert asked == [shown]


def test_update_panels_works_back_to_front():
    """Which is the entire point of a stack: the front one is copied last,
    so it is the one left on the screen."""
    order = []

    class Recording(Window):
        def __init__(self, name):
            super().__init__(ScreenBuffer(8, 3), 0, 0, 3, 8, owns=True)
            self._name = name

        def touchwin(self):
            pass

        def noutrefresh(self):
            order.append(self._name)

    for name in ("back", "middle", "front"):
        tcpanel.new_panel(Recording(name))
    tcpanel.update_panels()
    assert order == ["back", "middle", "front"]
