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

"""Tests for tkcurses._core.colors."""

from __future__ import annotations

import curses
import threading

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses._core.colors import (
    ColorDepth,
    ColorManager,
    ResolvedColor,
    detect_depth,
    parse_color,
    rgb_for,
    truecolor_hinted,
)
from tkcurses._core.dispatcher import CursesDispatcher

# ------------------------------------------------------------ named colours


@pytest.mark.parametrize(
    ("name", "color"),
    [
        ("black", curses.COLOR_BLACK),
        ("red", curses.COLOR_RED),
        ("green", curses.COLOR_GREEN),
        ("yellow", curses.COLOR_YELLOW),
        ("blue", curses.COLOR_BLUE),
        ("magenta", curses.COLOR_MAGENTA),
        ("cyan", curses.COLOR_CYAN),
        ("white", curses.COLOR_WHITE),
    ],
)
def test_base_colours(name, color):
    assert parse_color(name) == ResolvedColor(color, curses.A_NORMAL)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # Exactly the table in ARCHITECTURE.md.
        ("gray", ResolvedColor(curses.COLOR_WHITE, curses.A_DIM)),
        ("grey", ResolvedColor(curses.COLOR_WHITE, curses.A_DIM)),
        ("lightgray", ResolvedColor(curses.COLOR_WHITE)),
        ("darkgray", ResolvedColor(curses.COLOR_BLACK, curses.A_BOLD)),
        ("orange", ResolvedColor(curses.COLOR_YELLOW)),
        ("pink", ResolvedColor(curses.COLOR_MAGENTA)),
        ("purple", ResolvedColor(curses.COLOR_MAGENTA)),
        ("violet", ResolvedColor(curses.COLOR_MAGENTA)),
        ("brown", ResolvedColor(curses.COLOR_YELLOW, curses.A_DIM)),
        ("navy", ResolvedColor(curses.COLOR_BLUE, curses.A_DIM)),
        ("lime", ResolvedColor(curses.COLOR_GREEN, curses.A_BOLD)),
        ("aqua", ResolvedColor(curses.COLOR_CYAN)),
        ("turquoise", ResolvedColor(curses.COLOR_CYAN)),
        ("maroon", ResolvedColor(curses.COLOR_RED, curses.A_DIM)),
        ("olive", ResolvedColor(curses.COLOR_YELLOW, curses.A_DIM)),
        ("teal", ResolvedColor(curses.COLOR_CYAN, curses.A_DIM)),
        ("silver", ResolvedColor(curses.COLOR_WHITE)),
        ("fuchsia", ResolvedColor(curses.COLOR_MAGENTA, curses.A_BOLD)),
    ],
)
def test_specified_approximations(name, expected):
    assert parse_color(name) == expected


def test_names_are_case_and_space_insensitive():
    """tkinter accepts 'Light Gray' as readily as 'lightgray'."""
    assert parse_color("LightGray") == parse_color("lightgray")
    assert parse_color("Light Gray") == parse_color("lightgray")
    assert parse_color("  RED  ") == parse_color("red")


def test_unknown_name_is_rejected():
    with pytest.raises(ValueError, match="unknown colour name"):
        parse_color("chartreuse-ish")


def test_empty_specification_is_rejected():
    with pytest.raises(ValueError, match="must not be empty"):
        parse_color("")
    with pytest.raises(ValueError, match="must not be empty"):
        parse_color("   ")


# -------------------------------------------------------------------- hex


@pytest.mark.parametrize(
    ("spec", "rgb"),
    [
        ("#000000", (0, 0, 0)),
        ("#ffffff", (255, 255, 255)),
        ("#ff8000", (255, 128, 0)),
        ("#f80", (255, 136, 0)),  # #rgb widens each digit
        ("#000", (0, 0, 0)),
        ("#fff", (255, 255, 255)),
        ("#ffff00000000", (255, 0, 0)),  # 16-bit per channel
    ],
)
def test_hex_parsing(spec, rgb):
    assert rgb_for(spec) == rgb


@pytest.mark.parametrize("spec", ["red", "#12345", "#gggggg", "#", "#1234567", ""])
def test_non_hex_specifications_return_none(spec):
    assert rgb_for(spec) is None


@pytest.mark.parametrize("spec", ["#12345", "#gggggg", "#"])
def test_malformed_hex_is_rejected(spec):
    with pytest.raises(ValueError, match="malformed hex colour"):
        parse_color(spec)


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("#ff0000", ResolvedColor(curses.COLOR_RED, curses.A_BOLD)),
        ("#00ff00", ResolvedColor(curses.COLOR_GREEN, curses.A_BOLD)),
        ("#0000ff", ResolvedColor(curses.COLOR_BLUE)),
        ("#ffffff", ResolvedColor(curses.COLOR_WHITE, curses.A_BOLD)),
        ("#000000", ResolvedColor(curses.COLOR_BLACK)),
        ("#cd0000", ResolvedColor(curses.COLOR_RED)),
    ],
)
def test_hex_matches_the_expected_palette_entry(spec, expected):
    assert parse_color(spec) == expected


def test_orange_hex_does_not_degrade_to_grey():
    """The specification's threshold cascade turned #ff8000 into dim white."""
    assert parse_color("#ff8000").color == curses.COLOR_YELLOW


def test_mid_grey_becomes_bright_black():
    """The 16-colour palette renders grey as bright black, not dim white."""
    assert parse_color("#808080") == ResolvedColor(curses.COLOR_BLACK, curses.A_BOLD)


def test_extra_x11_names_are_approximated():
    assert parse_color("gold").color == curses.COLOR_YELLOW
    assert parse_color("lightpink").color in (
        curses.COLOR_MAGENTA,
        curses.COLOR_WHITE,
        curses.COLOR_RED,
    )


@given(red=st.integers(0, 255), green=st.integers(0, 255), blue=st.integers(0, 255))
def test_every_hex_colour_resolves(red, green, blue):
    """No colour a tkinter application can name may fail to render."""
    resolved = parse_color(f"#{red:02x}{green:02x}{blue:02x}")
    assert 0 <= resolved.color <= 7
    assert resolved.attr in (curses.A_NORMAL, curses.A_BOLD, curses.A_DIM)


# ----------------------------------------------------------- ColorManager


@pytest.fixture
def manager(monkeypatch):
    """A ColorManager over a stubbed curses, so no terminal is needed."""
    allocated: list[tuple[int, int, int]] = []

    monkeypatch.setattr(curses, "start_color", lambda: None)
    monkeypatch.setattr(curses, "has_colors", lambda: True)
    monkeypatch.setattr(curses, "use_default_colors", lambda: None)
    monkeypatch.setattr(
        curses, "init_pair", lambda n, fg, bg: allocated.append((n, fg, bg))
    )
    # color_pair() likewise needs initscr(); the shift mirrors what curses does.
    monkeypatch.setattr(curses, "color_pair", lambda n: n << 8)
    # COLOR_PAIRS only exists once start_color() has run.
    monkeypatch.setattr(curses, "COLOR_PAIRS", 8, raising=False)

    instance = ColorManager(
        dispatcher=CursesDispatcher(owner_thread_id=threading.get_ident())
    )
    instance.allocated_pairs = allocated  # type: ignore[attr-defined]
    return instance


def test_start_reports_colour_support(manager):
    assert manager.start() is True
    assert manager.has_colors


def test_start_is_idempotent(manager):
    assert manager.start() == manager.start()


def test_pairs_are_allocated_once_and_reused(manager):
    manager.start()
    first = manager.pair_number(curses.COLOR_RED, curses.COLOR_BLACK)
    second = manager.pair_number(curses.COLOR_RED, curses.COLOR_BLACK)
    assert first == second
    assert manager.allocated == 1
    assert len(manager.allocated_pairs) == 1


def test_distinct_combinations_get_distinct_pairs(manager):
    manager.start()
    red = manager.pair_number(curses.COLOR_RED, curses.COLOR_BLACK)
    blue = manager.pair_number(curses.COLOR_BLUE, curses.COLOR_BLACK)
    assert red != blue
    assert manager.allocated == 2


def test_pair_zero_is_never_allocated(manager):
    """Pair 0 carries the terminal's default colours and is reserved."""
    manager.start()
    numbers = {manager.pair_number(fg, curses.COLOR_BLACK) for fg in range(0, 6)}
    assert 0 not in numbers


def test_running_out_of_pairs_degrades_instead_of_failing(manager):
    """An over-colourful application must still render."""
    manager.start()
    for fg in range(8):
        for bg in range(8):
            manager.pair_number(fg, bg)
    assert manager.exhausted
    assert manager.pair_number(6, 7) == 0  # falls back to the default pair


def test_a_terminal_without_colour_is_not_an_error(monkeypatch):
    monkeypatch.setattr(curses, "start_color", lambda: None)
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    instance = ColorManager(
        dispatcher=CursesDispatcher(owner_thread_id=threading.get_ident())
    )
    assert instance.start() is False
    assert instance.pair_number(curses.COLOR_RED, curses.COLOR_BLACK) == 0
    assert instance.attribute_for("red", "black", curses.A_BOLD) == curses.A_BOLD


def test_start_color_failure_is_survived(monkeypatch):
    def refuse():
        raise curses.error("no colour here")

    monkeypatch.setattr(curses, "start_color", refuse)
    instance = ColorManager(
        dispatcher=CursesDispatcher(owner_thread_id=threading.get_ident())
    )
    assert instance.start() is False


def test_init_pair_failure_degrades(manager, monkeypatch):
    """Some terminals claim more pairs than they will actually create."""
    manager.start()

    def refuse(n, fg, bg):
        raise curses.error("refused")

    monkeypatch.setattr(curses, "init_pair", refuse)
    assert manager.pair_number(curses.COLOR_RED, curses.COLOR_BLUE) == 0
    assert manager.exhausted


def test_attribute_combines_colour_and_attributes(manager):
    manager.start()
    attr = manager.attribute_for("lime", "black", curses.A_UNDERLINE)
    assert attr & curses.A_UNDERLINE, "requested attribute is kept"
    assert attr & curses.A_BOLD, "lime is bright green, so bold is added"


def test_dim_named_colours_contribute_their_attribute(manager):
    manager.start()
    assert manager.attribute_for("gray", "black") & curses.A_DIM


def test_reset_forgets_allocations(manager):
    manager.start()
    manager.pair_number(curses.COLOR_RED, curses.COLOR_BLACK)
    manager.reset()
    assert manager.allocated == 0
    assert not manager.has_colors


def test_preallocate_counts_new_pairs(manager):
    manager.start()
    created = manager.preallocate([("red", "black"), ("blue", "black")])
    assert created == 2
    # Asking again allocates nothing further.
    assert manager.preallocate([("red", "black")]) == 0


# ----------------------------------------------------------- colour depth


@pytest.mark.parametrize(
    ("terminal", "colors", "direct", "expected"),
    [
        # Measured with tigetnum("colors") and tigetflag("RGB"), one process
        # per terminal - setupterm does not re-read on a second call in the
        # same process, so a loop reports the first terminal's answers for
        # all of them.
        ("vt100", -1, False, ColorDepth.NONE),
        ("dumb", -1, False, ColorDepth.NONE),
        ("xterm", 8, False, ColorDepth.BASIC),
        ("linux", 8, False, ColorDepth.BASIC),
        ("xterm-16color", 16, False, ColorDepth.BRIGHT),
        ("xterm-256color", 256, False, ColorDepth.EXTENDED),
        ("screen-256color", 256, False, ColorDepth.EXTENDED),
        ("xterm-direct", 16777216, True, ColorDepth.DIRECT),
    ],
)
def test_the_tier_comes_from_terminfo(terminal, colors, direct, expected):
    assert detect_depth(colors, direct) is expected


def test_an_unknown_count_rounds_down():
    """88-colour rxvt is the real case. Asking for a colour the terminal has
    not got puts the wrong colour on the screen; asking for one fewer costs
    only accuracy."""
    assert detect_depth(88, False) is ColorDepth.BRIGHT
    assert detect_depth(7, False) is ColorDepth.NONE
    assert detect_depth(255, False) is ColorDepth.BRIGHT


def test_the_rgb_flag_is_enough_on_its_own():
    """Whatever the count says beside it."""
    assert detect_depth(256, True) is ColorDepth.DIRECT


def test_the_tiers_are_ordered_so_they_can_be_compared():
    assert ColorDepth.NONE < ColorDepth.BASIC < ColorDepth.BRIGHT
    assert ColorDepth.BRIGHT < ColorDepth.EXTENDED < ColorDepth.DIRECT


# ------------------------------------------------------- the COLORTERM hint


@pytest.mark.parametrize("value", ["truecolor", "24bit", "TrueColor", " truecolor "])
def test_colorterm_says_a_terminal_understands_24_bit(value):
    assert truecolor_hinted(value) is True


@pytest.mark.parametrize("value", ["", "yes", "256color", "8bit"])
def test_anything_else_says_nothing(value):
    assert truecolor_hinted(value) is False


def test_the_hint_does_not_change_the_tier():
    """It is a promise about escape sequences, not about curses.

    A terminal can be xterm-256color with COLORTERM=truecolor - the one this
    was written on is - which means terminfo reports 256, curses can only be
    asked for 256, and acting on the hint here would send colour numbers of
    0xRRGGBB to a curses that expects 0 to 255.
    """
    assert detect_depth(256, False) is ColorDepth.EXTENDED
    assert truecolor_hinted("truecolor") is True
