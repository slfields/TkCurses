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

"""Tests for the Radiobutton widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import IntVar, Misc, Radiobutton, StringVar
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
    root._rect = Rect(0, 0, 40, 12)
    root._mapped = True
    return root


@pytest.fixture
def group(root):
    """Three radiobuttons over one variable, which is what a group is."""
    variable = StringVar(root, "")
    buttons = [
        Radiobutton(root, name=word, text=word.title(), variable=variable, value=word)
        for word in ("small", "medium", "large")
    ]
    return variable, buttons


def laid_out(widget, width=16, height=1):
    widget._allocate(Rect(0, 0, width, height))
    widget._map()
    return widget


def click(widget, x=1, y=0):
    if widget.winfo_width() == 0:
        laid_out(widget)
    widget._handle(MouseEvent(button=1, state="pressed", x=x, y=y))
    widget._handle(MouseEvent(button=1, state="released", x=x, y=y))


# ----------------------------------------------------------------- the group


def test_only_the_matching_button_is_on(group):
    variable, (small, medium, large) = group
    variable.set("medium")
    assert [b._indicator_state for b in (small, medium, large)] == ["off", "on", "off"]


def test_selecting_one_turns_the_others_off(group):
    """Nothing tells the others to turn off: they all read the same variable."""
    _, (small, medium, large) = group
    medium.select()
    large.select()
    assert [b._indicator_state for b in (small, medium, large)] == ["off", "off", "on"]


def test_a_group_can_start_with_nothing_chosen(group):
    _, buttons = group
    assert all(b._indicator_state == "off" for b in buttons)


def test_deselect_leaves_the_group_empty(group):
    variable, (small, _, _) = group
    small.select()
    small.deselect()
    assert variable.get() == ""
    assert small._indicator_state == "off"


def test_an_integer_value_matches_an_integer_variable(root):
    variable = IntVar(root, 2)
    buttons = [
        Radiobutton(root, name=f"r{n}", variable=variable, value=n) for n in (1, 2, 3)
    ]
    assert [b._indicator_state for b in buttons] == ["off", "on", "off"]


def test_a_string_variable_matches_an_integer_value(root):
    """Tcl has one type, so "2" and 2 name the same choice."""
    variable = StringVar(root, "2")
    button = Radiobutton(root, name="r", variable=variable, value=2)
    assert button._indicator_state == "on"


def test_buttons_without_a_variable_share_tks_default_group(root):
    """Tk's behaviour: no variable means the -variable selectedButton default."""
    first = Radiobutton(root, name="a", text="One", value="one")
    second = Radiobutton(root, name="b", text="Two", value="two")
    second.select()
    assert first._indicator_state == "off"
    assert second._indicator_state == "on"


def test_the_default_group_is_one_variable_the_application_owns(root):
    """Not one Variable object per button that happens to share a name.

    A Variable forgets its value when its last reference goes, so a group
    whose only owners were its own buttons would be at the mercy of which of
    them was collected last. The application holds it instead.
    """
    first = Radiobutton(root, name="a", text="One", value="one")
    second = Radiobutton(root, name="b", text="Two", value="two")
    shared = root.tk.shared_variables["selectedButton"]
    assert first._options["variable"] is shared
    assert second._options["variable"] is shared


def test_two_applications_keep_separate_default_groups():
    one, two = Misc(), Misc()
    Radiobutton(one, name="a", value="x").select()
    assert Radiobutton(two, name="a", value="x")._indicator_state == "off"


# ------------------------------------------------------------------ pressing


def test_a_click_selects_the_button(group):
    variable, (_, medium, _) = group
    click(medium)
    assert variable.get() == "medium"


def test_clicking_the_chosen_one_leaves_it_chosen(group):
    """A radiobutton cannot be turned off by clicking it; that is the point."""
    variable, (_, medium, _) = group
    medium.select()
    click(medium)
    assert variable.get() == "medium"
    assert medium._indicator_state == "on"


def test_clicking_the_chosen_one_still_runs_the_command(root):
    calls = []
    variable = StringVar(root, "a")
    button = Radiobutton(
        root, name="r", variable=variable, value="a", command=lambda: calls.append(1)
    )
    click(button)
    assert calls == [1]


def test_space_selects_the_focused_button(group):
    variable, (_, _, large) = group
    large._handle(KeyEvent(keysym="space"))
    assert variable.get() == "large"


def test_return_does_not_select_it(group):
    variable, (_, _, large) = group
    large._handle(KeyEvent(keysym="Return"))
    assert variable.get() == ""


def test_invoke_selects_and_runs_the_command(root):
    calls = []
    variable = StringVar(root, "")
    button = Radiobutton(
        root, name="r", variable=variable, value="a", command=lambda: calls.append(1)
    )
    assert button.invoke() is None
    assert variable.get() == "a"
    assert calls == [1]


def test_invoke_returns_what_the_command_returns(root):
    button = Radiobutton(root, name="r", value="a", command=lambda: "result")
    assert button.invoke() == "result"


def test_a_disabled_button_does_not_answer_a_click(root):
    variable = StringVar(root, "")
    button = Radiobutton(root, name="r", variable=variable, value="a", state="disabled")
    click(button)
    assert variable.get() == ""


def test_select_still_works_while_disabled(root):
    variable = StringVar(root, "")
    button = Radiobutton(root, name="r", variable=variable, value="a", state="disabled")
    button.select()
    assert variable.get() == "a"


def test_a_radiobutton_takes_the_focus(root):
    assert Radiobutton(root, name="r", text="One")._takefocus is True


# ----------------------------------------------------------------- geometry


def test_a_radiobutton_asks_for_room_for_its_indicator(root):
    plain = Radiobutton(root, name="a", text="Small", indicatoron=False)
    marked = Radiobutton(root, name="b", text="Small")
    assert marked.winfo_reqwidth() == plain.winfo_reqwidth() + 4


def test_the_text_sits_to_the_right_of_the_indicator(root):
    button = laid_out(Radiobutton(root, name="r", text="Small"), width=20)
    assert button._text_area().x >= 4
