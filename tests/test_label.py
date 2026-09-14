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

"""Tests for the Label widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Label, Misc, StringVar, TclError
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


def size(widget):
    return widget.winfo_reqwidth(), widget.winfo_reqheight()


# -------------------------------------------------------------------- text


def test_a_label_is_as_big_as_its_text(root):
    assert size(Label(root, name="l", text="hello")) == (5, 1)


def test_an_empty_label_still_occupies_a_row(root):
    assert size(Label(root, name="l")) == (0, 1)


def test_a_multi_line_label_is_as_tall_as_its_lines(root):
    assert size(Label(root, name="l", text="one\ntwo\nthree")) == (5, 3)


def test_changing_the_text_re_measures(root):
    label = Label(root, name="l", text="hi")
    label.configure(text="a longer line")
    assert size(label) == (13, 1)


def test_an_explicit_width_overrides_the_text(root):
    assert size(Label(root, name="l", text="hello", width=20)) == (20, 1)


def test_an_explicit_height_overrides_the_line_count(root):
    assert size(Label(root, name="l", text="hello", height=4)) == (5, 4)


def test_padding_is_included_in_what_it_asks_for(root):
    assert size(Label(root, name="l", text="hello", padx=2, pady=1)) == (9, 3)


def test_a_border_is_included_in_what_it_asks_for(root):
    assert size(Label(root, name="l", text="hello", relief="solid")) == (7, 3)


# ------------------------------------------------------------------ wrapping


def test_wraplength_breaks_the_text(root):
    label = Label(root, name="l", text="one two three four", wraplength=9)
    assert size(label) == (7, 3)


def test_without_wraplength_the_text_is_one_line(root):
    label = Label(root, name="l", text="one two three four")
    assert size(label) == (18, 1)


def test_changing_wraplength_re_measures(root):
    label = Label(root, name="l", text="one two three four")
    label.configure(wraplength=9)
    assert size(label) == (7, 3)


# -------------------------------------------------------------- textvariable


def test_a_textvariable_supplies_the_text(root):
    var = StringVar(root, value="from the variable")
    assert size(Label(root, name="l", textvariable=var)) == (17, 1)


def test_setting_the_variable_updates_the_label(root):
    var = StringVar(root, value="short")
    label = Label(root, name="l", textvariable=var)
    var.set("a good deal longer")
    assert size(label) == (18, 1)


def test_a_variable_wins_over_text(root):
    var = StringVar(root, value="variable")
    label = Label(root, name="l", text="literal", textvariable=var)
    assert label._text() == "variable"


def test_replacing_the_variable_stops_following_the_old_one(root):
    first = StringVar(root, name="first", value="first")
    second = StringVar(root, name="second", value="second value")
    label = Label(root, name="l", textvariable=first)
    label.configure(textvariable=second)
    first.set("this should not be used at all")
    assert label._text() == "second value"
    assert size(label) == (12, 1)


def test_clearing_the_variable_falls_back_to_the_text(root):
    var = StringVar(root, value="variable")
    label = Label(root, name="l", text="literal", textvariable=var)
    label.configure(textvariable=None)
    assert label._text() == "literal"


# ------------------------------------------------------------------ options


def test_the_defaults_match_tkinter(root):
    label = Label(root, name="l")
    assert label.cget("anchor") == "center"
    assert label.cget("justify") == "center"
    assert label.cget("state") == "normal"
    assert label.cget("underline") == -1


def test_an_unknown_option_is_refused(root):
    with pytest.raises(TclError, match="unknown option"):
        Label(root, name="l", nonsense=1)


def test_a_label_is_a_widget_like_any_other(root):
    label = Label(root, name="l", text="hi")
    label.pack()
    root.update_layout()
    assert label.winfo_manager() == "pack"
    assert label.winfo_ismapped()


def test_redrawing_without_a_screen_is_silent(root):
    label = Label(root, name="l", text="hi", relief="solid")
    label._allocate(Rect(0, 0, 10, 3))
    label._map()
    label._redraw()


def test_the_text_area_excludes_the_border_and_padding(root):
    label = Label(root, name="l", text="hi", relief="solid", padx=2, pady=1)
    label._allocate(Rect(0, 0, 20, 8))
    area = label._text_area()
    assert (area.x, area.y) == (3, 2)
    assert (area.width, area.height) == (14, 4)
