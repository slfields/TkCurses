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

"""Colour chooser rules that need no terminal."""

from __future__ import annotations

import pytest

from tkcurses import Misc, TclError
from tkcurses.colorchooser import PALETTE, Chooser, _hex, askcolor


def chooser(**options):
    picker = Chooser(Misc(), **options)
    picker._fixoptions()
    return picker


# ---------------------------------------------------------------- palette


def test_the_palette_is_the_sixteen_a_terminal_has():
    """Eight colours and their bright forms. Not sixteen million: a mixer
    would be offering precision the terminal cannot deliver."""
    assert len(PALETTE) == 16


def test_every_swatch_is_a_colour_string():
    assert all(len(color) == 7 and color.startswith("#") for color in PALETTE)


def test_the_palette_has_no_duplicates():
    """Two swatches the same would be two ways to say one thing."""
    assert len(set(PALETTE)) == len(PALETTE)


@pytest.mark.parametrize(
    ("rgb", "text"),
    [((0, 0, 0), "#000000"), ((255, 255, 255), "#ffffff"), ((205, 0, 205), "#cd00cd")],
)
def test_a_triplet_becomes_the_hex_tkinter_speaks(rgb, text):
    assert _hex(rgb) == text


# ---------------------------------------------------------------- options


def test_an_rgb_triplet_initialcolor_becomes_a_colour_string():
    """tkinter accepts either and converts, so code passing a triplet works."""
    assert chooser(initialcolor=(255, 0, 0)).options["initialcolor"] == "#ff0000"


def test_a_string_initialcolor_is_left_as_it_is():
    assert chooser(initialcolor="red").options["initialcolor"] == "red"


def test_no_initialcolor_is_fine():
    assert "initialcolor" not in chooser().options


# ----------------------------------------------------------------- result


def test_cancelling_gives_a_pair_of_nones():
    """Not None. Callers write `rgb, name = askcolor()` and would trip."""
    assert chooser()._fixresult(Misc(), None) == (None, None)


def test_an_empty_answer_is_a_cancellation_too():
    assert chooser()._fixresult(Misc(), "") == (None, None)


def test_a_chosen_colour_comes_back_as_a_triplet_and_a_string():
    rgb, text = chooser()._fixresult(Misc(), "#ff0000")
    assert rgb == (255, 0, 0)
    assert text == "#ff0000"


def test_a_name_answers_with_the_colour_the_terminal_will_show():
    """Not the one the name means elsewhere.

    ``red`` is #ff0000 in X11 and #cd0000 on a terminal, and it is the
    second that anything drawn in it will be - so reporting the first back
    would hide the approximation until somebody wondered why their orange
    looked like mustard.
    """
    rgb, text = chooser()._fixresult(Misc(), "red")
    assert text == "#cd0000"
    assert text == _hex(rgb)
    assert text in PALETTE


def test_a_hex_colour_is_its_own_answer():
    """The caller has already said exactly what it meant; the approximation
    happens when it is drawn, not when it is named. winfo_rgb agrees."""
    rgb, text = chooser()._fixresult(Misc(), "#005f5f")
    assert text == "#005f5f"
    assert rgb == (0, 0x5F, 0x5F)


# ----------------------------------------------------------------- no root


def test_asking_without_a_root_says_so():
    with pytest.raises(TclError, match="No root window"):
        askcolor()
