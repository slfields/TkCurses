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

"""Tests for the Spinbox widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Entry, Misc, Spinbox, StringVar, TclError
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


def laid_out(widget, width=14, height=1):
    widget._allocate(Rect(0, 0, width, height))
    widget._map()
    return widget


SIZES = ("small", "medium", "large")


# ------------------------------------------------------------- starting out


def test_a_values_spinbox_starts_on_the_first_value(root):
    assert Spinbox(root, name="s", values=SIZES).get() == "small"


def test_a_numeric_spinbox_starts_at_from(root):
    assert Spinbox(root, name="s", from_=2, to=8).get() == "2"


def test_a_textvariable_wins_over_the_starting_value(root):
    """An empty spinbox is filled in; one that already has contents is not."""
    variable = StringVar(root, "medium")
    assert (
        Spinbox(root, name="s", values=SIZES, textvariable=variable).get() == "medium"
    )


# ------------------------------------------------------------------ stepping


def test_the_arrows_walk_the_values(root):
    spin = Spinbox(root, name="s", values=SIZES)
    spin.invoke("buttonup")
    assert spin.get() == "medium"
    spin.invoke("buttonup")
    assert spin.get() == "large"
    spin.invoke("buttondown")
    assert spin.get() == "medium"


def test_the_values_stop_at_the_ends(root):
    spin = Spinbox(root, name="s", values=SIZES)
    for _ in range(5):
        spin.invoke("buttonup")
    assert spin.get() == "large"
    for _ in range(5):
        spin.invoke("buttondown")
    assert spin.get() == "small"


def test_the_values_wrap_when_asked_to(root):
    spin = Spinbox(root, name="s", values=SIZES, wrap=True)
    spin.invoke("buttondown")
    assert spin.get() == "large"
    spin.invoke("buttonup")
    assert spin.get() == "small"


def test_values_given_as_a_string_are_split(root):
    """A Tcl list arriving through the option database is one string."""
    spin = Spinbox(root, name="s", values="small medium large")
    spin.invoke("buttonup")
    assert spin.get() == "medium"


def test_contents_outside_the_values_step_to_an_end(root):
    """Either arrow has to be a way out of a value that is not on the list."""
    spin = Spinbox(root, name="s", values=SIZES)
    spin.delete(0, "end")
    spin.insert(0, "enormous")
    spin.invoke("buttonup")
    assert spin.get() == "small"
    spin.delete(0, "end")
    spin.insert(0, "enormous")
    spin.invoke("buttondown")
    assert spin.get() == "large"


def test_the_arrows_count_by_the_increment(root):
    spin = Spinbox(root, name="s", from_=0, to=10, increment=2)
    spin.invoke("buttonup")
    assert spin.get() == "2"


def test_a_number_stops_at_the_end_of_its_range(root):
    spin = Spinbox(root, name="s", from_=0, to=3)
    for _ in range(6):
        spin.invoke("buttonup")
    assert spin.get() == "3"


def test_a_number_wraps_when_asked_to(root):
    spin = Spinbox(root, name="s", from_=0, to=3, wrap=True)
    spin.invoke("buttondown")
    assert spin.get() == "3"
    spin.invoke("buttonup")
    assert spin.get() == "0"


def test_a_descending_range_counts_down(root):
    spin = Spinbox(root, name="s", from_=10, to=0)
    spin.invoke("buttonup")
    assert spin.get() == "9"


def test_a_fractional_increment_keeps_its_decimals(root):
    spin = Spinbox(root, name="s", from_=0, to=1, increment=0.25)
    spin.invoke("buttonup")
    assert spin.get() == "0.25"


def test_a_whole_increment_shows_no_decimal_point(root):
    spin = Spinbox(root, name="s", from_=0, to=5, increment=1)
    spin.invoke("buttonup")
    assert spin.get() == "1"


def test_a_format_is_honoured(root):
    spin = Spinbox(root, name="s", from_=0, to=5, format="%0.2f")
    spin.invoke("buttonup")
    assert spin.get() == "1.00"


def test_rubbish_typed_in_steps_back_onto_the_scale(root):
    spin = Spinbox(root, name="s", from_=4, to=9)
    spin.delete(0, "end")
    spin.insert(0, "hello")
    spin.invoke("buttonup")
    assert spin.get() == "4"


def test_a_range_of_no_width_does_not_move(root):
    """Tk's default from_ and to are both zero, and the arrows do nothing."""
    spin = Spinbox(root, name="s")
    spin.invoke("buttonup")
    assert spin.get() == "0"


def test_an_unknown_element_is_refused(root):
    with pytest.raises(TclError, match="buttondown or buttonup"):
        Spinbox(root, name="s", values=SIZES).invoke("middle")


# ------------------------------------------------------------------ command


def test_the_command_runs_on_every_step(root):
    calls = []
    spin = Spinbox(root, name="s", values=SIZES, command=lambda: calls.append(1))
    spin.invoke("buttonup")
    spin.invoke("buttondown")
    assert calls == [1, 1]


# ----------------------------------------------------------------- variable


def test_stepping_writes_the_textvariable(root):
    variable = StringVar(root, "")
    spin = Spinbox(root, name="s", values=SIZES, textvariable=variable)
    spin.invoke("buttonup")
    assert variable.get() == "medium"


def test_writing_the_variable_moves_the_spinbox(root):
    variable = StringVar(root, "small")
    spin = Spinbox(root, name="s", values=SIZES, textvariable=variable)
    variable.set("large")
    assert spin.get() == "large"


# -------------------------------------------------------------------- state


def test_a_readonly_spinbox_still_steps(root):
    """The state that makes a spinbox a chooser: arrows yes, typing no."""
    spin = Spinbox(root, name="s", values=SIZES, state="readonly")
    spin.invoke("buttonup")
    assert spin.get() == "medium"
    spin._handle(KeyEvent(keysym="x", char="x"))
    assert spin.get() == "medium"


def test_a_disabled_spinbox_does_not_step(root):
    spin = Spinbox(root, name="s", values=SIZES, state="disabled")
    spin.invoke("buttonup")
    assert spin.get() == "small"


def test_a_validator_can_refuse_a_step(root):
    spin = Spinbox(
        root,
        name="s",
        values=SIZES,
        validate="key",
        validatecommand=lambda proposed: proposed != "medium",
    )
    spin.invoke("buttonup")
    assert spin.get() == "small"


# ----------------------------------------------------------------- keyboard


def test_up_and_down_step(root):
    spin = Spinbox(root, name="s", values=SIZES)
    spin._handle(KeyEvent(keysym="Up"))
    assert spin.get() == "medium"
    spin._handle(KeyEvent(keysym="Down"))
    assert spin.get() == "small"


def test_typing_still_reaches_the_field(root):
    spin = Spinbox(root, name="s", from_=0, to=9)
    spin.delete(0, "end")
    spin._handle(KeyEvent(keysym="7", char="7"))
    assert spin.get() == "7"


def test_the_entry_editing_keys_still_work(root):
    spin = Spinbox(root, name="s", values=SIZES)
    spin._handle(KeyEvent(keysym="End"))
    spin._handle(KeyEvent(keysym="BackSpace"))
    assert spin.get() == "smal"


def test_a_spinbox_takes_the_focus(root):
    assert Spinbox(root, name="s")._takefocus is True


# -------------------------------------------------------------------- mouse


def test_clicking_the_up_arrow_steps_up(root):
    spin = laid_out(Spinbox(root, name="s", values=SIZES, width=10))
    column = spin._arrow_columns()[0]
    spin._handle(MouseEvent(button=1, state="pressed", x=column, y=0))
    spin._handle(MouseEvent(button=1, state="released", x=column, y=0))
    assert spin.get() == "medium"


def test_clicking_the_down_arrow_steps_down(root):
    spin = laid_out(Spinbox(root, name="s", values=SIZES, width=10, wrap=True))
    column = spin._arrow_columns()[1]
    spin._handle(MouseEvent(button=1, state="pressed", x=column, y=0))
    spin._handle(MouseEvent(button=1, state="released", x=column, y=0))
    assert spin.get() == "large"


def test_clicking_the_field_places_the_cursor_instead(root):
    spin = laid_out(Spinbox(root, name="s", values=SIZES, width=10))
    # One row tall, so there is no room for a border and none is drawn:
    # the text starts at column 0 and column 2 is the third character.
    spin._handle(MouseEvent(button=1, state="pressed", x=2, y=0))
    assert spin.get() == "small"
    assert spin.index("insert") == 2


def test_identify_names_the_three_parts(root):
    spin = laid_out(Spinbox(root, name="s", values=SIZES, width=10))
    up, down = spin._arrow_columns()
    assert spin.identify(up, 0) == "buttonup"
    assert spin.identify(down, 0) == "buttondown"
    assert spin.identify(0, 0) == "entry"
    assert spin.identify(99, 0) == "none"


def test_identify_takes_coordinates_within_the_widget(root):
    spin = Spinbox(root, name="s", values=SIZES, width=10)
    spin._allocate(Rect(7, 5, 14, 1))
    spin._map()
    assert spin.identify(0, 0) == "entry"
    assert spin.identify(*[spin._arrow_columns()[0], 0]) == "buttonup"


# ----------------------------------------------------------------- geometry


def test_a_spinbox_asks_for_room_for_its_arrows(root):
    """Everything an Entry of the same width asks for, plus the two arrows."""
    entry = Entry(root, name="a", width=10)
    spin = Spinbox(root, name="b", width=10)
    assert spin._requested.width == entry._requested.width + Spinbox._ARROW_WIDTH


def test_the_text_area_stops_before_the_arrows(root):
    spin = laid_out(Spinbox(root, name="s", width=10), width=12)
    entry = laid_out(Entry(root, name="e", width=10), width=12)
    assert spin._text_area().width == entry._text_area().width - Spinbox._ARROW_WIDTH
