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
from tkcurses._core.colors import ColorDepth, parse_color
from tkcurses.colorchooser import (
    BAR_LEVELS,
    BAR_WIDTH,
    CHANNELS,
    Chooser,
    _hex,
    _nearest_step,
    askcolor,
)


def chooser(**options):
    picker = Chooser(Misc(), **options)
    picker._fixoptions()
    return picker


# ------------------------------------------------------------------- bars


def test_there_are_three_channels_in_tk_s_order():
    assert CHANNELS == ("Red", "Green", "Blue")


def test_every_tier_has_a_set_of_levels():
    assert set(BAR_LEVELS) == set(ColorDepth)


def test_a_better_terminal_gets_more_steps():
    """Which is the whole reason the chooser waited for the colour tiers."""
    counts = [len(BAR_LEVELS[depth]) for depth in sorted(ColorDepth)]
    assert counts == sorted(counts)
    assert len(BAR_LEVELS[ColorDepth.BASIC]) == 2
    assert len(BAR_LEVELS[ColorDepth.EXTENDED]) == 6
    assert len(BAR_LEVELS[ColorDepth.DIRECT]) == 16


@pytest.mark.parametrize("depth", list(ColorDepth))
def test_every_level_is_a_channel_value(depth):
    levels = BAR_LEVELS[depth]
    assert all(0 <= level <= 255 for level in levels)
    assert list(levels) == sorted(levels), "a bar runs dark to light"
    assert len(set(levels)) == len(levels)


@pytest.mark.parametrize("depth", list(ColorDepth))
def test_a_bar_runs_from_nothing_to_everything(depth):
    """Tk's own bars stop at 240, so white cannot be reached from them at
    all. These end where the channel does."""
    assert BAR_LEVELS[depth][0] == 0
    assert BAR_LEVELS[depth][-1] == 255


def test_the_256_colour_levels_are_the_cube_s_own():
    """So every step lands exactly on a palette entry rather than near one."""
    assert BAR_LEVELS[ColorDepth.EXTENDED] == (0, 95, 135, 175, 215, 255)


def test_each_step_of_a_256_colour_bar_is_a_different_colour():
    """Measured against the resolver rather than assumed: this is what makes
    six the right count there and sixteen the wrong one."""
    resolved = {
        parse_color(_hex((level, 0, 0)), ColorDepth.EXTENDED)
        for level in BAR_LEVELS[ColorDepth.EXTENDED]
    }
    assert len(resolved) == 6


def test_sixteen_steps_on_an_eight_colour_terminal_are_mostly_repeats():
    """The bug this replaces, measured rather than argued.

    Tk's sixteen steps of red, resolved against eight colours, are three
    distinct results - and two of those differ only by A_BOLD, which does
    nothing at all to a background. So a bar drawn with them shows two
    appearances for sixteen steps. That is why the count has to follow the
    depth.
    """
    resolved = {
        parse_color(_hex((level, 0, 0)), ColorDepth.BASIC)
        for level in BAR_LEVELS[ColorDepth.DIRECT]
    }
    assert len(resolved) == 3
    assert len({entry.color for entry in resolved}) == 2, "as a background"


def test_a_bar_is_about_as_wide_whatever_it_holds():
    """Few steps means fat ones rather than a stubby bar."""
    for levels in BAR_LEVELS.values():
        cells = max(1, BAR_WIDTH // len(levels))
        assert 15 <= cells * len(levels) <= BAR_WIDTH


# ----------------------------------------------------------------- steps


def test_a_value_sits_on_the_step_nearest_it():
    levels = (0, 95, 135, 175, 215, 255)
    assert _nearest_step(levels, 0) == 0
    assert _nearest_step(levels, 255) == 5
    assert _nearest_step(levels, 128) == 2
    assert _nearest_step(levels, 100) == 1


def test_a_value_between_two_steps_picks_the_lower_one():
    """Only because min() keeps the first of an equal pair; what matters is
    that it picks one and does not fall off the end."""
    assert _nearest_step((0, 100, 200), 50) == 0


# --------------------------------------------------------------- the hex


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
