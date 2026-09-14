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

"""Named fonts on a device with one font.

The distinction these tests are mostly about is ``config`` against
``actual``: the first reports what was asked for and the second what the
terminal will really do, and a module that reported the request as the
result would be the worst kind of compatible - running, succeeding, and
doing nothing.
"""

from __future__ import annotations

import pytest

from tkcurses import Misc, TclError
from tkcurses.font import (
    BOLD,
    FAMILY,
    ITALIC,
    NORMAL,
    ROMAN,
    SIZE,
    Font,
    families,
    names,
    nametofont,
)


@pytest.fixture
def root():
    return Misc()


# --------------------------------------------------------------- creating


def test_a_font_gets_a_name_of_its_own(root):
    assert Font(root).name != Font(root).name


def test_a_named_font_keeps_the_name_it_was_given(root):
    assert str(Font(root, name="heading")) == "heading"


def test_a_font_is_registered_where_widgets_look(root):
    """A widget names a font in its option, so the name has to resolve."""
    heading = Font(root, name="heading", weight=BOLD)
    assert root.tk.fonts[str(heading)]["weight"] == BOLD


def test_two_fonts_cannot_share_a_name(root):
    first = Font(root, name="heading")
    with pytest.raises(TclError, match="already exists"):
        Font(root, name="heading")
    assert first.name == "heading"


def test_nametofont_finds_one_already_defined(root):
    original = Font(root, name="heading", weight=BOLD)
    assert nametofont("heading", root) == original


def test_nametofont_refuses_a_name_that_is_not_there(root):
    with pytest.raises(TclError, match="does not already exist"):
        nametofont("nosuchfont", root)


# ------------------------------------------------------- font descriptions


def test_a_tuple_description_is_family_size_and_styles(root):
    font = Font(root, font=("Times", 12, ITALIC, "underline"))
    assert font["family"] == "Times"
    assert font["size"] == 12
    assert font["slant"] == ITALIC
    assert font["underline"] == 1


def test_a_string_description_is_read_the_same_way(root):
    font = Font(root, font="Courier 14 bold")
    assert font["family"] == "Courier"
    assert font["size"] == 14
    assert font["weight"] == BOLD


def test_a_font_can_be_copied_from_another(root):
    original = Font(root, weight=BOLD, underline=1)
    copy = Font(root, font=original)
    assert copy["weight"] == BOLD
    assert copy["underline"] == 1
    assert copy.name != original.name, "a copy is a font of its own"


def test_copy_makes_a_distinct_font(root):
    original = Font(root, weight=BOLD)
    copy = original.copy()
    copy["weight"] = NORMAL
    assert original["weight"] == BOLD


# ---------------------------------------------------------------- options


def test_options_can_be_read_and_written_like_a_mapping(root):
    font = Font(root)
    font["weight"] = BOLD
    assert font["weight"] == BOLD


def test_config_with_no_arguments_reports_everything(root):
    assert set(Font(root).config()) == {
        "family",
        "size",
        "weight",
        "slant",
        "underline",
        "overstrike",
    }


def test_an_unknown_option_is_refused(root):
    font = Font(root)
    with pytest.raises(TclError, match="unknown option"):
        font.cget("colour")
    with pytest.raises(TclError, match="unknown option"):
        font.configure(colour="red")


# ----------------------------------------------------- asked for vs actual


def test_config_reports_what_was_asked_for(root):
    """Including the parts a terminal cannot honour: the request is kept."""
    font = Font(root, family="Courier", size=10)
    assert font.config() == {
        "family": "Courier",
        "size": 10,
        "weight": NORMAL,
        "slant": ROMAN,
        "underline": 0,
        "overstrike": 0,
    }


def test_actual_reports_what_the_terminal_will_do(root):
    """One typeface, one size, and only the styling it can draw."""
    font = Font(root, family="Courier", size=10, weight=BOLD, overstrike=1)
    assert font.actual() == {
        "family": FAMILY,
        "size": SIZE,
        "weight": BOLD,
        "slant": ROMAN,
        "underline": 0,
        # Curses has no strikeout, so nothing reports one.
        "overstrike": 0,
    }


def test_actual_can_be_asked_for_one_attribute(root):
    assert Font(root, family="Courier").actual("family") == FAMILY


def test_actual_refuses_an_attribute_a_font_has_not_got(root):
    with pytest.raises(TclError, match="unknown option"):
        Font(root).actual("colour")


# -------------------------------------------------------------- measuring


@pytest.mark.parametrize("text", ["", "a", "hello", "a longer line of text"])
def test_measuring_is_exact_because_a_cell_is_a_cell(root, text):
    """The whole difficulty of measuring a proportional font does not arise,
    so a widget laid out from this will fit."""
    assert Font(root).measure(text) == len(text)


def test_styling_does_not_change_the_width(root):
    """Bold text in a terminal occupies exactly the cells plain text does."""
    assert Font(root, weight=BOLD).measure("hello") == Font(root).measure("hello")


def test_the_metrics_are_one_cell(root):
    assert Font(root).metrics() == {
        "ascent": 1,
        "descent": 0,
        "linespace": 1,
        "fixed": 1,
    }


def test_one_metric_can_be_asked_for(root):
    assert Font(root).metrics("linespace") == 1


def test_several_metrics_come_back_as_a_mapping(root):
    assert Font(root).metrics("ascent", "descent") == {"ascent": 1, "descent": 0}


def test_an_unknown_metric_is_refused(root):
    with pytest.raises(TclError, match="unknown option"):
        Font(root).metrics("leading")


# ------------------------------------------------------------ the module


def test_there_is_one_family(root):
    """And saying so is the honest answer, not an empty tuple."""
    assert families(root) == (FAMILY,)


def test_names_lists_the_fonts_defined(root):
    one = Font(root, name="one")
    two = Font(root, name="two")
    assert set(names(root)) == {one.name, two.name}


def test_a_font_nobody_keeps_goes_away(root):
    """tkinter's trap, kept: a Font deletes itself when the last reference
    to it goes, so `Label(font=Font(...))` leaves the widget naming a font
    that no longer exists. Holding the Font is the caller's job there and
    here."""
    Font(root, name="unheld")
    assert "unheld" not in names(root)

    held = Font(root, name="held")
    assert "held" in names(root)
    assert held.name == "held"


def test_a_font_leaves_the_table_when_it_is_deleted(root):
    font = Font(root, name="temporary")
    assert "temporary" in names(root)
    font.__del__()
    assert "temporary" not in names(root)


def test_using_fonts_without_a_root_says_so():
    with pytest.raises(TclError, match="No root window"):
        Font()
    with pytest.raises(TclError, match="No root window"):
        names()
