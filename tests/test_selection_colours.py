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

"""Tk's selection colours: what they accept, and how a selection is drawn.

TkCurses-gm66.3. Every value rule and error message here was measured on Tk
9.0.2 with real tkinter. A selection nobody coloured is reversed, as it always
was; one given colours is drawn in them (``BaseWidget._selection_attribute``).
"""

from __future__ import annotations

import curses

import pytest

import tkcurses
from tkcurses import Misc, TclError
from tkcurses._core.colors import ColorDepth

SELECTING = ("Canvas", "Entry", "Listbox", "Spinbox", "Text")

#: Tk 9.0.2's defaults, except the colours: Tk's are #c3c3c3 and #000000,
#: ours are the terminal's own, "".
DEFAULTS = {"selectbackground": "", "selectborderwidth": 0, "selectforeground": ""}


class _Recorder:
    """Stands in for the colour manager, which needs a real terminal."""

    MARK = 1 << 20
    depth = ColorDepth.BASIC  # winfo_rgb asks, to check a colour name

    def __init__(self):
        self.calls = []

    def attribute_for(self, fg, bg, attr=0):
        self.calls.append((fg, bg))
        return self.MARK


@pytest.fixture
def root():
    return Misc()


@pytest.fixture
def colours(root):
    root.tk.colors = _Recorder()
    return root.tk.colors


# ------------------------------------------------------------- the options


@pytest.mark.parametrize("name", SELECTING)
def test_the_widgets_with_a_selection_take_them(root, name):
    widget = getattr(tkcurses, name)(root)
    expected = dict(DEFAULTS)
    if name == "Canvas":
        expected["selectborderwidth"] = 1  # Tk's, on a Canvas alone
    assert {key: widget.cget(key) for key in DEFAULTS} == expected


def test_only_text_has_an_inactive_selection_colour(root):
    assert tkcurses.Text(root).cget("inactiveselectbackground") == ""
    with pytest.raises(TclError, match='unknown option "-inactiveselectbackground"'):
        tkcurses.Entry(root, inactiveselectbackground="red")


@pytest.mark.parametrize("name", SELECTING)
@pytest.mark.parametrize("option", ["selectbackground", "selectforeground"])
def test_a_colour_that_is_not_one_is_refused(root, name, option):
    widget = getattr(tkcurses, name)(root)
    with pytest.raises(TclError, match='unknown color name "nocolour"'):
        widget.configure(**{option: "nocolour"})


def test_inactiveselectbackground_is_a_colour(root):
    with pytest.raises(TclError, match='unknown color name "nocolour"'):
        tkcurses.Text(root, inactiveselectbackground="nocolour")


@pytest.mark.parametrize(("given", "stored"), [(3, 3), ("2", 2), (-3, 0), ("-3", 0)])
def test_selectborderwidth_is_a_distance_that_stops_at_zero(root, given, stored):
    entry = tkcurses.Entry(root, selectborderwidth=given)
    assert entry.cget("selectborderwidth") == stored


@pytest.mark.parametrize("given", ["x", ""])
def test_selectborderwidth_refuses_what_is_not_a_distance(root, given):
    with pytest.raises(TclError, match=f'expected screen distance but got "{given}"'):
        tkcurses.Listbox(root, selectborderwidth=given)


# ------------------------------------------------ how the selection is drawn


@pytest.mark.parametrize("name", ["Entry", "Listbox"])
def test_an_uncoloured_selection_is_reversed(root, colours, name):
    widget = getattr(tkcurses, name)(root)
    assert widget._selection_attribute(0) == curses.A_REVERSE
    assert colours.calls == []


@pytest.mark.parametrize("name", ["Entry", "Listbox"])
def test_a_coloured_selection_is_drawn_in_its_colours(root, colours, name):
    widget = getattr(tkcurses, name)(
        root, selectbackground="red", selectforeground="yellow"
    )
    attribute = widget._selection_attribute(curses.A_BOLD)
    assert attribute == curses.A_BOLD | _Recorder.MARK
    assert colours.calls == [("yellow", "red")]


def test_one_colour_alone_keeps_the_widgets_for_the_other(root, colours):
    entry = tkcurses.Entry(root, selectbackground="red", foreground="green")
    entry._selection_attribute(0)
    assert colours.calls == [("green", "red")]


def test_a_terminal_without_colour_still_reverses(root):
    root.tk.colors = None
    entry = tkcurses.Entry(root, selectbackground="red")
    assert entry._selection_attribute(0) == curses.A_REVERSE


# ------------------------------------------------- Text: the sel tag follows


def test_text_select_colours_are_the_sel_tags(root):
    """Measured: configuring either changes what the other reads back."""
    text = tkcurses.Text(root, selectbackground="red")
    assert text.tag_cget("sel", "background") == "red"
    text.configure(selectforeground="blue")
    assert text.tag_cget("sel", "foreground") == "blue"
    text.tag_configure("sel", background="green", foreground="")
    assert text.cget("selectbackground") == "green"
    assert text.cget("selectforeground") == ""


def test_an_unconfigured_sel_tag_is_still_reversed(root, colours):
    text = tkcurses.Text(root)
    text.focus_set()
    assert text._tag_attribute("sel") == curses.A_REVERSE
    assert colours.calls == []


def test_a_coloured_sel_tag_is_drawn_in_its_colours(root, colours):
    text = tkcurses.Text(root, selectbackground="red", selectforeground="yellow")
    text.focus_set()
    assert text._tag_attribute("sel") == _Recorder.MARK
    assert colours.calls == [("yellow", "red")]


# ------------------------------------------ Text without the focus: inactive


def test_unfocused_the_selection_looks_as_it_does_focused(root, colours):
    """The default: Tk's inactive colour is the same grey as its active one."""
    text = tkcurses.Text(root)
    assert text.focus_get() is not text
    assert text._tag_attribute("sel") == curses.A_REVERSE


def test_unfocused_the_inactive_colour_takes_the_backgrounds_place(root, colours):
    text = tkcurses.Text(
        root,
        selectbackground="red",
        selectforeground="yellow",
        inactiveselectbackground="blue",
    )
    assert text._tag_attribute("sel") == _Recorder.MARK
    assert colours.calls == [("yellow", "blue")]
    colours.calls.clear()
    text.focus_set()
    text._tag_attribute("sel")
    assert colours.calls == [("yellow", "red")]


def test_an_empty_inactive_colour_hides_the_selection_without_the_focus(root):
    """Tk's manual: "If empty, then no selection is shown when the window
    does not have the focus." """
    text = tkcurses.Text(root, inactiveselectbackground="")
    assert text._tag_attribute("sel") is None
    text.focus_set()
    assert text._tag_attribute("sel") == curses.A_REVERSE


def test_the_default_given_back_does_not_hide_it(root):
    """``configure(x=cget(x))`` keeps the default, and the selection with it."""
    text = tkcurses.Text(root)
    text.configure(inactiveselectbackground=text.cget("inactiveselectbackground"))
    assert text._tag_attribute("sel") == curses.A_REVERSE


def test_the_option_database_can_hide_it(root):
    root.option_add("*Text.inactiveSelectBackground", "")
    text = tkcurses.Text(root)
    assert text._tag_attribute("sel") is None
