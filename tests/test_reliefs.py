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

"""Tk's extra reliefs, element borders and slider length. TkCurses-gm66.5.

A relief is a box style here, and most of these belong to parts one cell
deep - a slider, an arrow, a menu entry - with no edge to draw one on. Those
show only the relief Tk's own bindings put on a part while it is held,
``sunken``, drawn dim as a sunken border is. ``overrelief`` and ``offrelief``
are whole-widget reliefs and draw as boxes.

pyte has no dim, so what is drawn is read from a window that records the
attribute of every cell, rather than from a terminal.
"""

from __future__ import annotations

import curses
from types import SimpleNamespace

import pytest

import tkcurses
from tkcurses import Misc, TclError, ttk
from tkcurses._core.attributes import style_for_relief
from tkcurses._core.geometry import Rect
from tkcurses._core.input import MouseEvent

#: The options this issue adds, with the default each reads back. Tk's own,
#: measured on 9.0.2, except ``sliderlength``: Tk's is 30 pixels, and here
#: one cell, the handle as it was drawn before.
DEFAULTS = {
    ("Button", "overrelief"): "",
    ("Checkbutton", "offrelief"): "raised",
    ("Checkbutton", "overrelief"): "",
    ("Radiobutton", "offrelief"): "raised",
    ("Radiobutton", "overrelief"): "",
    ("Menu", "activeborderwidth"): 1,
    ("Menu", "activerelief"): "raised",
    ("Scale", "sliderlength"): 1,
    ("Scale", "sliderrelief"): "raised",
    ("Scrollbar", "activerelief"): "raised",
    ("Scrollbar", "elementborderwidth"): "",
    ("Spinbox", "buttoncursor"): "",
    ("Spinbox", "buttondownrelief"): "raised",
    ("Spinbox", "buttonuprelief"): "raised",
}

RELIEF_OPTIONS = [
    (name, option)
    for (name, option), default in DEFAULTS.items()
    if option.endswith("relief") and option != "overrelief"
]


class Window:
    """A curses window that keeps every cell written, with its attribute."""

    def __init__(self, rows, columns):
        self.size = (rows, columns)
        self.cells = {}

    def getmaxyx(self):
        return self.size

    def bkgd(self, *args):
        pass

    def erase(self):
        self.cells = {}

    def addstr(self, row, column, text, attribute=0):
        for offset, character in enumerate(text):
            self.cells[(row, column + offset)] = (character, attribute)

    insstr = addstr


@pytest.fixture
def root():
    return Misc()


def shown(widget, width, height=1):
    """Lay ``widget`` out at the top left and draw it into a :class:`Window`."""
    widget._allocate(Rect(0, 0, width, height))
    widget._panel = SimpleNamespace(window=Window(height, width))
    widget.tk.screen = SimpleNamespace()
    widget._redraw()
    return widget._panel.window


def dim(window, row, column):
    return bool(window.cells[(row, column)][1] & curses.A_DIM)


def text(window, row, width):
    return "".join(window.cells.get((row, c), (" ", 0))[0] for c in range(width))


# ---------------------------------------------------------------- the options


@pytest.mark.parametrize(("name", "option"), list(DEFAULTS))
def test_each_is_taken_with_tks_default(root, name, option):
    assert getattr(tkcurses, name)(root).cget(option) == DEFAULTS[(name, option)]


@pytest.mark.parametrize(("name", "option"), RELIEF_OPTIONS)
def test_a_relief_is_taken_by_a_unique_prefix(root, name, option):
    widget = getattr(tkcurses, name)(root, **{option: "gr"})
    assert widget.cget(option) == "groove"


@pytest.mark.parametrize(("name", "option"), RELIEF_OPTIONS)
def test_a_relief_is_refused_as_tk_refuses_it(root, name, option):
    widget = getattr(tkcurses, name)(root)
    choices = "must be flat, groove, raised, ridge, solid, or sunken"
    with pytest.raises(TclError, match=f'bad relief "RAISED": {choices}'):
        widget.configure(**{option: "RAISED"})
    with pytest.raises(TclError, match=f'ambiguous relief "s": {choices}'):
        widget.configure(**{option: "s"})
    with pytest.raises(TclError, match=f'ambiguous relief "": {choices}'):
        widget.configure(**{option: ""})
    assert widget.cget(option) == DEFAULTS[(name, option)]


@pytest.mark.parametrize("name", ["Button", "Checkbutton", "Radiobutton"])
def test_overrelief_may_be_empty_and_says_so_when_refusing(root, name):
    widget = getattr(tkcurses, name)(root, overrelief="su")
    assert widget.cget("overrelief") == "sunken"
    widget.configure(overrelief="")
    assert widget.cget("overrelief") == ""
    with pytest.raises(
        TclError,
        match='bad relief "bogus": must be flat, groove, raised, ridge, solid,'
        ' sunken, or ""',
    ):
        widget.configure(overrelief="bogus")


@pytest.mark.parametrize(
    ("name", "option"), [("Scale", "sliderlength"), ("Menu", "activeborderwidth")]
)
def test_a_length_keeps_its_sign_as_tk_does(root, name, option):
    widget = getattr(tkcurses, name)(root, **{option: -5})
    assert widget.cget(option) == -5
    widget.configure(**{option: " 4 "})
    assert widget.cget(option) == 4
    with pytest.raises(TclError, match='expected screen distance but got "x"'):
        widget.configure(**{option: "x"})


def test_a_negative_element_border_reads_back_empty(root):
    bar = tkcurses.Scrollbar(root, elementborderwidth=-3)
    assert bar.cget("elementborderwidth") == ""
    bar.configure(elementborderwidth=2)
    assert bar.cget("elementborderwidth") == 2


def test_buttoncursor_is_kept_as_given(root):
    spinbox = tkcurses.Spinbox(root, buttoncursor="hand2")
    assert spinbox.cget("buttoncursor") == "hand2"


# ------------------------------------------------------------------ overrelief


@pytest.mark.parametrize("name", ["Button", "Checkbutton", "Radiobutton"])
def test_the_pointer_arriving_puts_on_the_overrelief(root, name):
    """``tk::ButtonEnter``: active, and the relief swapped for the over one."""
    widget = getattr(tkcurses, name)(root, relief="flat", overrelief="raised")
    widget.event_generate("<Enter>")
    assert widget.cget("relief") == "raised"
    assert widget.cget("state") == "active"
    widget.event_generate("<Leave>")
    assert widget.cget("relief") == "flat"
    assert widget.cget("state") == "normal"


def test_without_an_overrelief_the_relief_stays(root):
    button = tkcurses.Button(root, relief="groove")
    button.event_generate("<Enter>")
    assert button.cget("relief") == "groove"
    assert button.cget("state") == "active"
    button.event_generate("<Leave>")
    assert button.cget("relief") == "groove"


def test_a_relief_changed_while_over_it_is_kept(root):
    """``tk::ButtonLeave`` restores only the relief it put there."""
    button = tkcurses.Button(root, relief="flat", overrelief="raised")
    button.event_generate("<Enter>")
    button.configure(relief="ridge")
    button.event_generate("<Leave>")
    assert button.cget("relief") == "ridge"


def test_a_disabled_button_does_not_answer_the_pointer(root):
    button = tkcurses.Button(root, relief="flat", overrelief="raised", state="disabled")
    button.event_generate("<Enter>")
    assert button.cget("relief") == "flat"
    button.event_generate("<Leave>")
    assert button.cget("state") == "disabled"


def test_a_held_button_keeps_its_relief_on_the_way_back_in(root):
    """Tk sinks it there; a press here is markers, not a relief."""
    button = tkcurses.Button(root, relief="flat", overrelief="raised")
    button._pressed = True
    button.event_generate("<Enter>")
    assert button.cget("relief") == "flat"


def test_the_overrelief_is_drawn_as_the_box(root):
    button = tkcurses.Button(root, text="Go", overrelief="ridge")
    button.event_generate("<Enter>")
    window = shown(button, 10, 3)
    assert window.cells[(0, 0)][0] == style_for_relief("ridge").top_left


def test_a_ttk_button_has_no_overrelief_binding(root):
    """ttk's buttons follow ttk's procedures, which have no overrelief."""
    button = ttk.Button(root, relief="flat", overrelief="raised")
    button.event_generate("<Enter>")
    assert button.cget("relief") == "flat"


# ------------------------------------------------------------------ offrelief


def border(widget):
    return widget._border_style()


@pytest.mark.parametrize("name", ["Checkbutton", "Radiobutton"])
def test_an_indicatorless_button_is_drawn_in_offrelief_while_off(root, name):
    """``TkpDisplayButton``: the relief option is not what is drawn."""
    widget = getattr(tkcurses, name)(
        root, indicatoron=False, relief="flat", offrelief="ridge", borderwidth=1
    )
    if name == "Radiobutton":
        widget.configure(value="mine")
    widget.deselect()
    assert border(widget) == style_for_relief("ridge")


@pytest.mark.parametrize("name", ["Checkbutton", "Radiobutton"])
def test_an_indicatorless_button_is_sunken_while_on(root, name):
    widget = getattr(tkcurses, name)(
        root, indicatoron=False, offrelief="ridge", borderwidth=1
    )
    widget.select()
    assert border(widget) == style_for_relief("sunken")


def test_the_pointer_over_an_indicatorless_button_shows_its_relief(root):
    """The manual's toolbar button: flat, raised under the pointer."""
    check = tkcurses.Checkbutton(
        root, indicatoron=False, offrelief="flat", overrelief="raised", borderwidth=1
    )
    assert border(check) == style_for_relief("flat")
    check.event_generate("<Enter>")
    assert border(check) == style_for_relief("raised")
    check.event_generate("<Leave>")
    assert border(check) == style_for_relief("flat")


def test_with_an_indicator_the_relief_is_its_own(root):
    check = tkcurses.Checkbutton(root, relief="groove", offrelief="ridge")
    assert border(check) == style_for_relief("groove")


def test_offrelief_does_not_change_the_size(root):
    """A box is three rows here: off and on must not resize the button."""
    check = tkcurses.Checkbutton(root, text="B", indicatoron=False)
    before = check.winfo_reqheight()
    check.select()
    check._apply_requested_size()
    assert check.winfo_reqheight() == before


# ----------------------------------------------------------------- the slider


def scale(root, **kw):
    return tkcurses.Scale(
        root, orient="horizontal", from_=0, to=10, showvalue=False, **kw
    )


def handle(window, width=14):
    return [c for c in range(width) if window.cells.get((0, c), ("",))[0] == "█"]


def test_a_handle_is_sliderlength_cells_long(root):
    widget = scale(root, sliderlength=3)
    widget.set(5)
    assert handle(shown(widget, 14)) == [5, 6, 7]


def test_a_long_handle_still_reaches_both_ends(root):
    widget = scale(root, sliderlength=3)
    window = shown(widget, 14)
    assert handle(window) == [1, 2, 3]
    widget.set(10)
    assert handle(window) == [10, 11, 12]


def test_the_whole_handle_is_the_slider(root):
    widget = scale(root, sliderlength=3)
    widget.set(5)
    shown(widget, 14)
    assert [widget.identify(c, 0) for c in range(4, 9)] == [
        "trough1",
        "slider",
        "slider",
        "slider",
        "trough2",
    ]
    assert widget.coords() == (6, 0)


@pytest.mark.parametrize("length", [2, 3, 4, 7])
def test_each_place_the_handle_stands_is_the_value_drawn_there(root, length):
    """What a drag to a cell sets is a value whose handle is at that cell.

    Not the other way round: a long handle has fewer places than the scale
    has values, so two values can share one. And not for a one-cell handle
    here, whose twelve places outnumber eleven values, as they always have.
    """
    widget = scale(root, sliderlength=length)
    shown(widget, 14)
    lead = (length - 1) // 2
    for start in range(12 - length + 1):
        middle = start + lead
        assert widget._offset_for(widget._value_at(middle)) == middle


@pytest.mark.parametrize("length", [1, 2, 3, 4, 7])
def test_the_ends_are_the_scales_ends(root, length):
    widget = scale(root, sliderlength=length)
    shown(widget, 14)
    lead = (length - 1) // 2
    assert widget._value_at(lead) == 0
    assert widget._value_at(12 - length + lead) == 10


def test_one_cell_is_the_handle_as_it_was(root):
    widget = scale(root)
    widget.set(5)
    assert handle(shown(widget, 14)) == [7]


@pytest.mark.parametrize(("length", "cells"), [(-5, 1), (0, 1), (99, 12)])
def test_a_handle_stays_within_one_cell_and_the_trough(root, length, cells):
    widget = scale(root, sliderlength=length)
    assert len(handle(shown(widget, 14))) == cells


def test_a_handle_longer_than_the_trough_is_centred_on_it(root):
    """``coords`` names the handle's middle, which must be on the trough."""
    widget = scale(root, sliderlength=99)
    shown(widget, 14)
    assert widget.coords() == (1 + 5, 0)
    assert widget.identify(6, 0) == "slider"


def press(widget, x, y=0):
    widget._handle(MouseEvent(button=1, state="pressed", x=x, y=y))


def release(widget, x, y=0):
    widget._handle(MouseEvent(button=1, state="released", x=x, y=y))


@pytest.mark.parametrize(
    ("relief", "held"),
    [("raised", "sunken"), ("ridge", "groove"), ("flat", "flat"), ("solid", "solid")],
)
def test_a_held_slider_sinks_as_tk_sinks_it(root, relief, held):
    """``tk::ScaleButtonDown`` and ``tk::ScaleEndDrag``."""
    widget = scale(root, sliderrelief=relief)
    shown(widget, 14)
    press(widget, 1)  # the handle: a press on the trough steps instead
    assert widget.cget("sliderrelief") == held
    release(widget, 1)
    assert widget.cget("sliderrelief") == relief


def test_a_sunken_handle_is_dim_and_the_trough_is_not(root):
    widget = scale(root, sliderlength=2)
    window = shown(widget, 14)
    assert not dim(window, 0, 1)
    press(widget, 1)
    assert dim(window, 0, 1) and dim(window, 0, 2)
    assert not dim(window, 0, 3)
    release(widget, 1)
    assert not dim(window, 0, 1)


# ------------------------------------------------------------- the scrollbar


def test_a_pressed_scrollbar_sinks_its_active_element(root):
    """``tk::ScrollButtonDown`` and ``tk::ScrollButtonUp``."""
    bar = tkcurses.Scrollbar(root, activerelief="ridge", command=lambda *a: None)
    shown(bar, 1, 8)
    press(bar, 0, 0)
    assert bar.cget("activerelief") == "sunken"
    release(bar, 0, 0)
    assert bar.cget("activerelief") == "ridge"


def test_the_active_element_is_dim_while_sunken(root):
    bar = tkcurses.Scrollbar(root, activerelief="sunken")
    window = shown(bar, 1, 8)
    bar.activate("arrow1")
    assert dim(window, 0, 0)
    assert not dim(window, 7, 0)
    bar.configure(activerelief="raised")
    assert not dim(window, 0, 0)


def test_activate_redraws(root):
    bar = tkcurses.Scrollbar(root, activerelief="sunken")
    window = shown(bar, 1, 8)
    bar.activate("arrow2")
    assert dim(window, 7, 0)


# ------------------------------------------------------------ spinbox arrows


@pytest.mark.parametrize(
    ("up", "down", "dims"),
    [
        ("raised", "raised", (False, False)),
        ("sunken", "raised", (True, False)),
        ("ridge", "sunken", (False, True)),
    ],
)
def test_a_sunken_arrow_is_dim(root, up, down, dims):
    spinbox = tkcurses.Spinbox(
        root, buttonuprelief=up, buttondownrelief=down, relief="flat"
    )
    window = shown(spinbox, 8)
    assert text(window, 0, 8)[-2:] == "▲▼"
    assert (dim(window, 0, 6), dim(window, 0, 7)) == dims


# ---------------------------------------------------------------- menu entries


def test_the_active_entry_is_dim_while_its_relief_is_sunken(root):
    menu = tkcurses.Menu(root, activerelief="sunken")
    menu.add_command(label="One")
    menu.add_command(label="Two")
    menu.activate(0)
    window = shown(menu, 10, 4)
    row = next(r for r in range(4) if "One" in text(window, r, 10))
    other = next(r for r in range(4) if "Two" in text(window, r, 10))
    column = text(window, row, 10).index("O")
    assert dim(window, row, column)
    assert not dim(window, other, column)
    menu.configure(activerelief="raised")
    menu._redraw()
    assert not dim(window, row, column)
