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

"""Tests for tkcurses._core.panels.

The stack is driven without curses by supplying stub factories, so ordering,
visibility and hit testing are exercised directly. Real curses stacking is
covered by the terminal tests.
"""

from __future__ import annotations

import threading

import pytest

from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


class FakeWindow:
    """Stands in for a curses window."""

    def __init__(self, rect: Rect) -> None:
        self.rect = rect
        self.touched = 0

    def touchwin(self) -> None:
        self.touched += 1


class FakePanel:
    """Stands in for a curses panel, so the stack believes curses is there."""

    def __init__(self, window: FakeWindow) -> None:
        self.window = window
        self.hidden = False

    def top(self) -> None:
        pass

    def bottom(self) -> None:
        pass

    def hide(self) -> None:
        self.hidden = True

    def show(self) -> None:
        self.hidden = False

    def move(self, y: int, x: int) -> None:
        pass

    def replace(self, window: FakeWindow) -> None:
        self.window = window


@pytest.fixture
def stack():
    """A stack with no curses behind it, so ordering can be tested directly."""
    return PanelStack(
        dispatcher=CursesDispatcher(owner_thread_id=threading.get_ident()),
        window_factory=FakeWindow,
        panel_factory=None,
    )


@pytest.fixture
def touchable_stack():
    """A stack that believes it has curses, for the output side."""
    return PanelStack(
        dispatcher=CursesDispatcher(owner_thread_id=threading.get_ident()),
        window_factory=FakeWindow,
        panel_factory=FakePanel,
    )


def make(stack, x=0, y=0, w=10, h=4, **kwargs):
    return stack.new_panel(Rect(x, y, w, h), **kwargs)


# ------------------------------------------------------------------ basics


def test_a_new_stack_is_empty(stack):
    assert len(stack) == 0
    assert stack.top() is None
    assert stack.bottom() is None


def test_new_panels_go_on_top(stack):
    first = make(stack)
    second = make(stack)
    assert stack.panels == (first, second)
    assert stack.top() is second
    assert stack.bottom() is first


def test_panel_carries_its_geometry(stack):
    panel = make(stack, x=3, y=2, w=8, h=5)
    assert panel.rect == Rect(3, 2, 8, 5)
    assert isinstance(panel.window, FakeWindow)


def test_empty_panels_are_rejected(stack):
    with pytest.raises(ValueError, match="non-zero size"):
        stack.new_panel(Rect(0, 0, 0, 4))


def test_userptr_round_trips(stack):
    marker = object()
    panel = make(stack, userptr=marker)
    assert panel.userptr() is marker
    replacement = object()
    panel.set_userptr(replacement)
    assert panel.userptr() is replacement


def test_membership_and_iteration(stack):
    first, second = make(stack), make(stack)
    assert first in stack
    assert list(stack) == [first, second]


def test_repr_reports_state(stack):
    panel = make(stack, x=1, y=2, w=6, h=3)
    assert "6x3" in repr(panel)
    assert "shown" in repr(panel)
    stack.hide(panel)
    assert "hidden" in repr(panel)


# ---------------------------------------------------------------- ordering


def test_raise_to_top(stack):
    first, second, third = make(stack), make(stack), make(stack)
    stack.raise_to_top(first)
    assert stack.panels == (second, third, first)
    assert stack.top() is first


def test_lower_to_bottom(stack):
    first, second, third = make(stack), make(stack), make(stack)
    stack.lower_to_bottom(third)
    assert stack.panels == (third, first, second)


def test_above_and_below(stack):
    first, second, third = make(stack), make(stack), make(stack)
    assert stack.above(first) is second
    assert stack.below(third) is second
    assert stack.above(third) is None
    assert stack.below(first) is None


def test_raise_above_a_specific_panel(stack):
    first, second, third = make(stack), make(stack), make(stack)
    stack.raise_above(first, second)
    assert stack.panels == (second, first, third)


def test_lower_below_a_specific_panel(stack):
    first, second, third = make(stack), make(stack), make(stack)
    stack.lower_below(third, second)
    assert stack.panels == (first, third, second)


def test_stacking_a_panel_against_itself_is_rejected(stack):
    panel = make(stack)
    with pytest.raises(ValueError, match="relative to itself"):
        stack.raise_above(panel, panel)
    with pytest.raises(ValueError, match="relative to itself"):
        stack.lower_below(panel, panel)


def test_raising_the_top_panel_changes_nothing(stack):
    first, second = make(stack), make(stack)
    stack.raise_to_top(second)
    assert stack.panels == (first, second)


# -------------------------------------------------------------- visibility


def test_hide_and_show(stack):
    panel = make(stack)
    assert not panel.hidden
    stack.hide(panel)
    assert panel.hidden
    assert stack.visible == ()
    stack.show(panel)
    assert not panel.hidden
    assert stack.visible == (panel,)


def test_hiding_keeps_the_panel_in_the_order(stack):
    """Showing a panel again must restore its place, not bring it to front."""
    first, second, third = make(stack), make(stack), make(stack)
    stack.hide(second)
    assert stack.panels == (first, second, third)
    stack.show(second)
    assert stack.panels == (first, second, third)


def test_hidden_panels_are_skipped_by_top_and_bottom(stack):
    first, second, third = make(stack), make(stack), make(stack)
    stack.hide(third)
    assert stack.top() is second
    stack.hide(first)
    assert stack.bottom() is second


def test_hiding_twice_is_harmless(stack):
    panel = make(stack)
    stack.hide(panel)
    stack.hide(panel)
    assert panel.hidden
    stack.show(panel)
    stack.show(panel)
    assert not panel.hidden


# ------------------------------------------------------------------ layout


def test_move_updates_the_rectangle(stack):
    panel = make(stack, x=1, y=1, w=6, h=3)
    stack.move(panel, 10, 5)
    assert panel.rect == Rect(10, 5, 6, 3)


def test_replace_window_resizes(stack):
    """Curses windows cannot resize in place, so a new one is built."""
    panel = make(stack, w=6, h=3)
    original = panel.window
    stack.replace_window(panel, Rect(0, 0, 12, 8))
    assert panel.rect == Rect(0, 0, 12, 8)
    assert panel.window is not original


def test_replace_window_rejects_an_empty_size(stack):
    panel = make(stack)
    with pytest.raises(ValueError, match="non-zero size"):
        stack.replace_window(panel, Rect(0, 0, 4, 0))


# ------------------------------------------------------------- hit testing


def test_panel_at_finds_the_covering_panel(stack):
    panel = make(stack, x=2, y=1, w=6, h=3)
    assert stack.panel_at(2, 1) is panel
    assert stack.panel_at(7, 3) is panel
    assert stack.panel_at(8, 3) is None
    assert stack.panel_at(0, 0) is None


def test_panel_at_returns_the_frontmost(stack):
    """Overlapping windows: the click belongs to whichever is in front."""
    back = make(stack, x=0, y=0, w=10, h=5)
    front = make(stack, x=2, y=1, w=4, h=2)
    assert stack.panel_at(3, 2) is front
    assert stack.panel_at(9, 4) is back
    stack.raise_to_top(back)
    assert stack.panel_at(3, 2) is back


def test_panel_at_ignores_hidden_panels(stack):
    back = make(stack, x=0, y=0, w=10, h=5)
    front = make(stack, x=2, y=1, w=4, h=2)
    stack.hide(front)
    assert stack.panel_at(3, 2) is back


def test_panels_at_lists_every_cover_front_first(stack):
    back = make(stack, x=0, y=0, w=10, h=5)
    front = make(stack, x=2, y=1, w=4, h=2)
    assert stack.panels_at(3, 2) == (front, back)
    assert stack.panels_at(9, 4) == (back,)
    assert stack.panels_at(50, 50) == ()


# ------------------------------------------------------------- destruction


def test_destroy_removes_the_panel(stack):
    first, second = make(stack), make(stack)
    stack.destroy(first)
    assert stack.panels == (second,)
    assert first.destroyed
    assert first not in stack


def test_destroying_twice_is_harmless(stack):
    panel = make(stack)
    stack.destroy(panel)
    stack.destroy(panel)
    assert len(stack) == 0


def test_using_a_destroyed_panel_is_rejected(stack):
    panel = make(stack)
    stack.destroy(panel)
    for action in (
        lambda: stack.raise_to_top(panel),
        lambda: stack.hide(panel),
        lambda: stack.show(panel),
        lambda: stack.move(panel, 1, 1),
        lambda: stack.above(panel),
        lambda: stack.replace_window(panel, Rect(0, 0, 4, 4)),
    ):
        with pytest.raises(ValueError, match="not part of this stack"):
            action()


def test_clear_destroys_everything(stack):
    make(stack), make(stack), make(stack)
    stack.clear()
    assert len(stack) == 0
    assert stack.top() is None


def test_update_without_curses_is_a_no_op(stack):
    stack.update()  # panel_factory is None; nothing to push


def test_touch_all_without_curses_is_a_no_op(stack):
    stack.touch_all()  # same: there is nothing behind the stack to touch


def test_touch_all_marks_the_visible_panels(touchable_stack):
    """After the screen is cleared, an unchanged panel must be written again."""
    first, second, third = (make(touchable_stack) for _ in range(3))
    touchable_stack.hide(second)
    touchable_stack.touch_all()
    assert first.window.touched == 1
    assert third.window.touched == 1
    assert second.window.touched == 0, "a hidden panel has nothing to put back"
