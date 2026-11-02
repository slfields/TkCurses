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

"""Tk's colours for a widget's states and parts. TkCurses-gm66.4.

Active, disabled and readonly states; the indicator, trough and spin-button
colours. Every one defaults to ``""`` here, where Tk's are real colours, and
draws what was drawn before: an active widget reversed, a disabled one dimmed.
A colour a program gives is drawn instead (``BaseWidget._in_state``).
"""

from __future__ import annotations

import curses

import pytest

import tkcurses
from tkcurses import Misc, TclError
from tkcurses._core.colors import ColorDepth

#: The options Tk 9.0.2 takes that this issue adds, per widget.
OPTIONS = {
    "Button": "activebackground activeforeground disabledforeground",
    "Checkbutton": "activebackground activeforeground disabledforeground selectcolor",
    "Entry": "disabledbackground disabledforeground readonlybackground",
    "Label": "activebackground activeforeground disabledforeground",
    "Listbox": "disabledforeground",
    "Menu": "activebackground activeforeground disabledforeground selectcolor",
    "Menubutton": "activebackground activeforeground disabledforeground",
    "Radiobutton": "activebackground activeforeground disabledforeground selectcolor",
    "Scale": "activebackground troughcolor",
    "Scrollbar": "activebackground troughcolor",
    "Spinbox": (
        "activebackground buttonbackground disabledbackground disabledforeground"
        " readonlybackground"
    ),
}

CASES = [(name, option) for name, names in OPTIONS.items() for option in names.split()]


class _Pairs:
    """Stands in for the colour manager: a pair number per ``(fg, bg)``."""

    depth = ColorDepth.BASIC  # winfo_rgb asks, to check a colour name

    def __init__(self):
        self.pairs: list[tuple[str, str]] = []

    def attribute_for(self, fg, bg, attr=0):
        if (fg, bg) not in self.pairs:
            self.pairs.append((fg, bg))
        return (self.pairs.index((fg, bg)) + 1) << 8

    def of(self, attribute):
        """The ``(fg, bg)`` an attribute's pair stands for."""
        number = (attribute & curses.A_COLOR) >> 8
        return self.pairs[number - 1] if number else None


@pytest.fixture
def root():
    return Misc()


@pytest.fixture
def colours(root):
    root.tk.colors = _Pairs()
    return root.tk.colors


def make(root, name, **kw):
    return getattr(tkcurses, name)(root, **kw)


# ------------------------------------------------------------- the options


@pytest.mark.parametrize(("name", "option"), CASES)
def test_each_is_taken_and_starts_as_the_terminals_own(root, name, option):
    assert make(root, name).cget(option) == ""


@pytest.mark.parametrize(("name", "option"), CASES)
def test_each_is_a_colour(root, name, option):
    widget = make(root, name, **{option: "red"})
    assert widget.cget(option) == "red"
    with pytest.raises(TclError, match='unknown color name "nocolour"'):
        widget.configure(**{option: "nocolour"})


def test_a_message_has_none_of_them(root):
    """Tk's Message has no state colours; it shares the drawing code."""
    with pytest.raises(TclError, match='unknown option "-activebackground"'):
        tkcurses.Message(root, activebackground="red")


# ------------------------------------------------------- labels and buttons


@pytest.mark.parametrize("name", ["Label", "Button", "Menubutton", "Checkbutton"])
def test_an_uncoloured_active_widget_is_reversed(root, colours, name):
    widget = make(root, name, state="active")
    assert widget._text_attribute() & curses.A_REVERSE
    assert colours.of(widget._background_attribute()) == ("white", "black")


@pytest.mark.parametrize("name", ["Label", "Button", "Menubutton", "Checkbutton"])
def test_an_active_widget_takes_its_active_colours(root, colours, name):
    widget = make(
        root, name, state="active", activebackground="red", activeforeground="yellow"
    )
    assert not widget._text_attribute() & curses.A_REVERSE
    assert colours.of(widget._background_attribute()) == ("yellow", "red")


def test_one_active_colour_keeps_the_widgets_for_the_other(root, colours):
    button = tkcurses.Button(
        root, state="active", activebackground="red", foreground="green"
    )
    assert colours.of(button._background_attribute()) == ("green", "red")


def test_a_button_held_down_is_active(root, colours):
    """Tk presses only an active button, so its colours show through a press."""
    button = tkcurses.Button(root, activebackground="red")
    assert colours.of(button._background_attribute()) == ("white", "black")
    button._pressed = True
    assert colours.of(button._background_attribute()) == ("white", "red")


def test_a_disabled_widget_is_dimmed_unless_given_a_colour(root, colours):
    label = tkcurses.Label(root, state="disabled")
    assert label._text_attribute() & curses.A_DIM
    label.configure(disabledforeground="grey")
    assert not label._text_attribute() & curses.A_DIM
    assert colours.of(label._background_attribute()) == ("grey", "black")


def test_the_active_colours_do_not_colour_another_state(root, colours):
    label = tkcurses.Label(root, activebackground="red", disabledforeground="grey")
    assert colours.of(label._background_attribute()) == ("white", "black")


def test_a_terminal_without_colour_keeps_the_old_look(root):
    root.tk.colors = None
    button = tkcurses.Button(root, state="active", activebackground="red")
    assert button._text_attribute() & curses.A_REVERSE


# --------------------------------------------------- check and radio buttons


@pytest.mark.parametrize("name", ["Checkbutton", "Radiobutton"])
def test_selectcolor_is_the_indicators_background(root, colours, name):
    widget = make(root, name, selectcolor="blue")
    attribute = widget._background_attribute() | widget._text_attribute()
    assert colours.of(widget._coloured(attribute, "", "blue")) == ("white", "blue")
    # And the button around it keeps its own.
    assert colours.of(widget._background_attribute()) == ("white", "black")


def test_an_indicatorless_button_that_is_on_takes_selectcolor(root, colours):
    """Tk's manual: "used as the background for the entire widget, in place
    of background or activeBackground, whenever the widget is selected"."""
    box = tkcurses.Checkbutton(root, indicatoron=False, selectcolor="blue")
    assert colours.of(box._background_attribute()) == ("white", "black")
    box.select()
    assert colours.of(box._background_attribute()) == ("white", "blue")
    assert not box._text_attribute() & curses.A_REVERSE


def test_an_indicatorless_button_without_selectcolor_is_reversed_when_on(root, colours):
    box = tkcurses.Checkbutton(root, indicatoron=False)
    box.select()
    assert box._text_attribute() & curses.A_REVERSE


# --------------------------------------------------------- Entry and Spinbox


@pytest.mark.parametrize("name", ["Entry", "Spinbox"])
def test_a_disabled_entry_takes_its_disabled_colours(root, colours, name):
    entry = make(
        root,
        name,
        state="disabled",
        disabledbackground="blue",
        disabledforeground="grey",
    )
    attribute = entry._in_state(entry._background_attribute())
    assert colours.of(attribute) == ("grey", "blue")
    assert not attribute & curses.A_DIM


def test_a_disabled_entry_without_them_is_dimmed(root, colours):
    entry = tkcurses.Entry(root, state="disabled")
    assert entry._in_state(entry._background_attribute()) & curses.A_DIM


def test_a_readonly_entry_takes_readonlybackground(root, colours):
    entry = tkcurses.Entry(root, readonlybackground="blue")
    assert colours.of(entry._in_state(0)) is None
    entry.configure(state="readonly")
    assert colours.of(entry._in_state(0)) == ("white", "blue")


def test_the_disabled_colours_are_not_the_readonly_ones(root, colours):
    entry = tkcurses.Entry(root, state="readonly", disabledbackground="blue")
    assert colours.of(entry._in_state(0)) is None


# ------------------------------------------------------------------ Listbox


def test_a_disabled_listbox_takes_disabledforeground(root, colours):
    box = tkcurses.Listbox(root, state="disabled", disabledforeground="grey")
    attribute = box._in_state(box._background_attribute())
    assert colours.of(attribute) == ("grey", "black")
    assert not attribute & curses.A_DIM


# ----------------------------------------------------------- Scrollbar, Scale


def test_a_scrollbars_trough_and_active_part_take_their_colours(root, colours):
    bar = tkcurses.Scrollbar(root, troughcolor="blue", activebackground="red")
    assert colours.of(bar._part_attribute("trough", 0)) == ("white", "blue")
    assert colours.of(bar._part_attribute("slider", 0)) is None
    bar.activate("slider")
    assert colours.of(bar._part_attribute("slider", 0)) == ("white", "red")
    assert colours.of(bar._part_attribute("arrow1", 0)) is None


def test_a_scales_handle_is_active_while_dragged_or_in_state(root, colours):
    scale = tkcurses.Scale(root, activebackground="red")
    assert not scale._active_handle()
    scale._dragging = True
    assert scale._active_handle()
    scale._dragging = False
    scale.configure(state="active")
    assert scale._active_handle() and scale._handle_coloured()
