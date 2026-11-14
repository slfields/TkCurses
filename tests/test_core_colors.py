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
    _BRIGHT_PALETTE,
    ColorDepth,
    ColorManager,
    ResolvedColor,
    _resolve_rgb,
    detect_depth,
    din99d,
    palette_rgb,
    parse_color,
    rgb_for,
    rgb_of,
    rgb_of_number,
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
    assert parse_color("RED") == parse_color("red")


@pytest.mark.parametrize(
    ("spec", "known"),
    [
        # Every verdict measured on Tk 9.0.2, which this table follows: a
        # space only where the name starts a word, one at a time, never at
        # either end and never before a number.
        ("SteelBlue", True),
        ("steel blue", True),
        ("STEELBLUE", True),
        ("light goldenrod yellow", True),
        ("Light Goldenrod Yellow", True),
        ("lightgoldenrodyellow", True),
        ("navy blue", True),
        ("gray0", True),
        ("grey100", True),
        ("s teelblue", False),
        ("steel  blue", False),
        (" steelblue", False),
        ("steelblue ", False),
        ("  RED  ", False),
        ("gray 50", False),
        ("gr ay50", False),
        ("gray101", False),
        ("darkyellow", False),
    ],
)
def test_a_name_is_read_by_tks_rule(spec, known):
    if known:
        parse_color(spec)
    else:
        with pytest.raises(ValueError, match="unknown colour name"):
            parse_color(spec)


def test_tks_whole_table_is_known():
    """665 names, the X11 set with Tk's changes: gray is the web's 128, and
    there are aqua, crimson, indigo and the rest Tk added."""
    from tkcurses._core import x11colors

    assert len(x11colors.NAMES) == 665
    assert all(x11colors.lookup(name) == name for name in x11colors.NAMES)
    assert x11colors.NAMES["gray"] == (128, 128, 128)
    assert x11colors.NAMES["green"] == (0, 128, 0)
    assert x11colors.NAMES["crimson"] == (220, 20, 60)
    for number in range(101):
        assert x11colors.lookup(f"gray{number}") is not None
        assert x11colors.lookup(f"Grey{number}") is not None


def test_a_name_beyond_the_palette_reports_tks_rgb():
    """What a picture's get() or winfo_rgb() reports for a name the
    approximations do not cover is the colour Tk gives it."""
    assert rgb_of("SteelBlue") == (70, 130, 180)
    assert rgb_of("light goldenrod yellow") == (250, 250, 210)
    assert rgb_of("no such colour") is None


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
    """The specification's threshold cascade turned #ff8000 into dim white.

    Orange now resolves to bright RED at eight colours, where it used to
    resolve to yellow. That is the perceptual answer and not a regression:
    measured in DIN99d, orange is 50.96 from bright red and 85.31 from
    yellow, so red is 1.67 times nearer. The old weighted-RGB metric chose
    yellow because it counted green four times over, and orange's green
    channel sits half way to yellow's - an artefact of the weights rather
    than a statement about colour.

    What this test is really guarding is in its name, and it still holds:
    the answer must be a colour, not a grey.
    """
    resolved = parse_color("#ff8000")
    assert resolved.color == curses.COLOR_RED
    assert resolved.attr & curses.A_BOLD, "orange is nearer BRIGHT red than red"
    assert resolved.color not in (curses.COLOR_BLACK, curses.COLOR_WHITE)


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
def manager(request, monkeypatch):
    """A ColorManager over a stubbed curses, so no terminal is needed.

    Eight colours unless the test asks for more, since that is what a
    terminal that has never been interrogated is assumed to have. Indirect
    parametrisation sets ``curses.COLORS`` to something else.
    """
    allocated: list[tuple[int, int, int]] = []
    colors = getattr(request, "param", 8)

    monkeypatch.setattr(curses, "start_color", lambda: None)
    monkeypatch.setattr(curses, "has_colors", lambda: True)
    monkeypatch.setattr(curses, "use_default_colors", lambda: None)
    monkeypatch.setattr(
        curses, "init_pair", lambda n, fg, bg: allocated.append((n, fg, bg))
    )
    # color_pair() likewise needs initscr(); the shift mirrors what curses does.
    monkeypatch.setattr(curses, "color_pair", lambda n: n << 8)
    # COLOR_PAIRS and COLORS only exist once start_color() has run.
    monkeypatch.setattr(curses, "COLOR_PAIRS", 8, raising=False)
    monkeypatch.setattr(curses, "COLORS", colors, raising=False)

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
    """An over-colourful application must still render.

    This used to assert that an exhausted allocator answers 0, and 0 is the
    pair holding the TERMINAL's default colours - so running out did not
    degrade, it repainted whatever came next in the default foreground and
    background. On a picture that is the difference between a slightly
    wrong colour and an unrelated one.

    It answers with the nearest pair it has already allocated now, so the
    guarantee is the stronger one: every cell still gets a colour, and the
    colour is close to the one asked for.
    """
    manager.start()
    for fg in range(8):
        for bg in range(8):
            manager.pair_number(fg, bg)
    assert manager.exhausted
    fallback = manager.pair_number(6, 7)
    assert fallback != 0, "an exhausted allocator must not answer with the default pair"
    assert fallback in manager._pairs.values()


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


# --------------------------------------------- resolving against each tier


def test_the_eight_colour_tier_is_what_it_always_was():
    """Every colour rule written before there were tiers has to survive, so
    BASIC is the default and nothing about it moves."""
    assert parse_color("red", ColorDepth.BASIC) == ResolvedColor(curses.COLOR_RED)
    assert parse_color("lime", ColorDepth.BASIC) == ResolvedColor(
        curses.COLOR_GREEN, curses.A_BOLD
    )
    assert parse_color("red") == parse_color("red", ColorDepth.BASIC)


def test_brightness_becomes_a_colour_once_there_are_sixteen():
    """And stops being an attribute, which is the whole point: A_BOLD never
    touched a background, so a bright background was unreachable."""
    bright = parse_color("lime", ColorDepth.BRIGHT)
    assert bright == ResolvedColor(10)
    assert bright.attr == curses.A_NORMAL


@pytest.mark.parametrize("depth", [ColorDepth.BRIGHT, ColorDepth.EXTENDED])
def test_no_colour_above_the_eight_carries_a_brightness_attribute(depth):
    for name in ("lime", "gray", "darkgray", "fuchsia", "brown", "navy"):
        assert parse_color(name, depth).attr == curses.A_NORMAL, name


def test_a_name_renders_as_the_same_colour_at_every_tier():
    """`red` is #cd0000 on all of them - a better terminal gets closer to
    what was asked for, it does not change what was asked for."""
    for depth in ColorDepth:
        if depth is ColorDepth.NONE:
            continue
        assert palette_rgb(parse_color("red", depth), depth) == (205, 0, 0)


def test_256_colours_reach_the_cube_rather_than_rounding_to_anything():
    """#ff8000 is orange, and only 256 colours has an orange to offer.

    Eight colours has to round it to a hue that is not orange - bright red,
    which is the nearest thing perceptually. 256 has cube entry 208, which
    really is orange, and the point of the test is that the extended path
    reaches it rather than settling for the same rounding.
    """
    assert parse_color("#ff8000", ColorDepth.BASIC).color == curses.COLOR_RED
    resolved = parse_color("#ff8000", ColorDepth.EXTENDED)
    assert resolved.color == 208
    assert palette_rgb(resolved, ColorDepth.EXTENDED) == (255, 135, 0)


def test_direct_colour_is_not_approximated_at_all():
    resolved = parse_color("#ff8000", ColorDepth.DIRECT)
    assert resolved.color == 0xFF8000
    assert palette_rgb(resolved, ColorDepth.DIRECT) == (255, 128, 0)


def test_a_monochrome_terminal_keeps_the_attributes_and_loses_the_colour():
    """Bold and dim are all it has to tell one thing from another with."""
    assert parse_color("lime", ColorDepth.NONE) == ResolvedColor(-1, curses.A_BOLD)
    assert parse_color("gray", ColorDepth.NONE) == ResolvedColor(-1, curses.A_DIM)
    assert parse_color("red", ColorDepth.NONE).color == -1


@given(red=st.integers(0, 255), green=st.integers(0, 255), blue=st.integers(0, 255))
def test_every_hex_colour_resolves_at_every_tier(red, green, blue):
    spec = f"#{red:02x}{green:02x}{blue:02x}"
    assert 0 <= parse_color(spec, ColorDepth.BRIGHT).color <= 15
    assert 0 <= parse_color(spec, ColorDepth.EXTENDED).color <= 255
    assert parse_color(spec, ColorDepth.DIRECT).color == (red << 16 | green << 8 | blue)


# ------------------------------------------------- the manager's own tier


def test_the_manager_reads_its_tier_from_curses(manager):
    manager.start()
    assert manager.depth is ColorDepth.BASIC


@pytest.mark.parametrize(
    ("manager", "expected"),
    [(8, ColorDepth.BASIC), (16, ColorDepth.BRIGHT), (256, ColorDepth.EXTENDED)],
    indirect=["manager"],
)
def test_the_manager_follows_whatever_curses_reports(manager, expected):
    manager.start()
    assert manager.depth is expected


def test_the_tier_is_none_before_the_manager_starts(manager):
    assert manager.depth is ColorDepth.NONE


def test_reset_forgets_the_tier_too(manager):
    manager.start()
    manager.reset()
    assert manager.depth is ColorDepth.NONE


@pytest.mark.parametrize("manager", [16], indirect=True)
def test_the_manager_allocates_the_bright_colour_number(manager):
    """Rather than green-with-bold, which would have painted the background
    plain green and the caller would never know why."""
    manager.start()
    attribute = manager.attribute_for("black", "lime")
    assert not attribute & curses.A_BOLD
    assert manager.allocated_pairs == [(1, curses.COLOR_BLACK, 10)]


# ------------------------------------------------------ the attribute cache


def test_the_same_request_answers_the_same_attribute(manager):
    """A screen paints one cell at a time and asks here for each: measured,
    a canvas of 500 items asked 22,500 times for about thirty distinct
    answers, and each answer re-searched the palette. TkCurses-g9w.
    """
    manager.start()
    first = manager.attribute_for("white", "black")
    assert manager.attribute_for("white", "black") == first


def test_reset_forgets_the_cached_attributes(manager):
    """The pairs go with a screen being torn down, so the attributes built
    from them cannot outlive it."""
    manager.start()
    manager.attribute_for("white", "black")
    assert manager._attributes

    manager.reset()

    assert not manager._attributes


def test_different_requests_get_different_answers(manager):
    """The obvious way a cache goes wrong: one key for everything."""
    manager.start()
    one = manager.attribute_for("white", "black")
    two = manager.attribute_for("red", "black")
    three = manager.attribute_for("white", "blue")

    assert len({one, two, three}) == 3


# --------------------------------------------------------------- the budget


def test_capacity_is_what_an_attribute_can_name_not_what_curses_offers(manager):
    """COLOR_PAIRS is the wrong number, and using it paints the wrong colours.

    The stub reports 8 pairs, which is below the 255 an attribute can name,
    so the smaller of the two has to win. The fixture's A_COLOR is the real
    curses one.
    """
    manager.start()
    assert manager.capacity == 7, "8 pairs reported, minus pair 0"


@pytest.mark.parametrize("manager", [256], indirect=True)
def test_capacity_stops_at_the_eight_bits_a_pair_number_gets(manager, monkeypatch):
    """A terminal offering 65536 pairs still only gets 255 usable ones."""
    monkeypatch.setattr(curses, "COLOR_PAIRS", 65536, raising=False)
    manager.start()
    assert manager.capacity == 255


def test_remaining_counts_down_as_pairs_are_taken(manager):
    manager.start()
    start = manager.remaining
    manager.pair_number(curses.COLOR_RED, curses.COLOR_BLACK)
    manager.pair_number(curses.COLOR_BLUE, curses.COLOR_BLACK)
    assert manager.remaining == start - 2


def test_remaining_never_goes_below_zero(manager):
    manager.start()
    for fg in range(8):
        for bg in range(8):
            manager.pair_number(fg, bg)
    assert manager.exhausted
    assert manager.remaining == 0


def test_a_terminal_without_colour_has_no_capacity(monkeypatch):
    monkeypatch.setattr(curses, "start_color", lambda: None)
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    instance = ColorManager(
        dispatcher=CursesDispatcher(owner_thread_id=threading.get_ident())
    )
    instance.start()
    assert instance.capacity == 0
    assert instance.remaining == 0


# -------------------------------------------------------------- the renewal


def _exhaust(manager):
    for fg in range(8):
        for bg in range(8):
            manager.pair_number(fg, bg)
    assert manager.exhausted


def test_a_table_with_room_left_is_not_renewed(manager):
    manager.start()
    manager.pair_number(curses.COLOR_RED, curses.COLOR_BLACK)
    assert manager.renew_if_exhausted() is False
    assert manager.allocated == 1, "nothing was thrown away"


def test_an_exhausted_table_is_renewed_and_asks_for_a_repaint(manager):
    manager.start()
    _exhaust(manager)
    assert manager.renew_if_exhausted() is True
    assert manager.allocated == 0
    assert not manager.exhausted
    assert manager.remaining == manager.capacity


def test_emptying_the_table_moves_the_generation(manager):
    """What a picture's fitted palette is keyed on: chosen for the pairs
    that were left, it is wrong once they all are again."""
    manager.start()
    before = manager.generation
    manager.pair_number(curses.COLOR_RED, curses.COLOR_BLACK)
    manager.renew_if_exhausted()
    assert manager.generation == before, "a table with room left is kept"
    _exhaust(manager)
    manager.renew_if_exhausted()
    assert manager.generation == before + 1
    manager.reset()
    assert manager.generation == before + 2


def test_a_renewal_asked_for_empties_the_table_once(manager):
    """For a new picture, which must not be fitted into what an old one
    left. Not counted towards giving up: a table that then runs dry is
    still renewed, as one that ran dry on its own would be."""
    manager.start()
    manager.pair_number(curses.COLOR_RED, curses.COLOR_BLACK)
    before = manager.generation
    manager.ask_for_renewal()
    assert manager.renew_if_exhausted() is True
    assert manager.allocated == 0
    assert manager.generation == before + 1
    assert manager.renew_if_exhausted() is False, "asked once, done once"
    _exhaust(manager)
    assert manager.renew_if_exhausted() is True


@pytest.mark.parametrize("manager", [256], indirect=True)
def test_the_layer_under_a_direct_picture_stays_in_eight_colours(manager, monkeypatch):
    """At most 64 pairs whatever the picture holds, so the table is left
    for everything else on screen."""
    monkeypatch.setattr(curses, "COLOR_PAIRS", 256, raising=False)
    manager.start()
    shades = [
        f"#{n:02x}{(n * 7) % 256:02x}{(n * 13) % 256:02x}" for n in range(0, 256, 9)
    ]
    for fore in shades:
        for back in shades:
            manager.fallback_attribute_for(fore, back)
    assert not manager.exhausted
    assert 1 < manager.allocated <= 64
    assert all(fg < 8 and bg < 8 for _, fg, bg in manager.allocated_pairs)
    assert manager.fallback_attribute_for(shades[3], shades[5]) == (
        manager.fallback_attribute_for(shades[3], shades[5])
    )


def test_renewal_drops_the_attribute_cache_too(manager):
    """The one trap: that cache is keyed by colours but holds pair NUMBERS.

    Keeping it across a renewal hands out a recycled number under its old
    meaning, which is worse than running out - the colours would be not
    merely approximate but someone else's.
    """
    manager.start()
    before = manager.attribute_for("red", "black")
    _exhaust(manager)
    manager.renew_if_exhausted()
    assert manager._attributes == {}, "a cache of stale pair numbers was kept"
    # Resolved again rather than remembered, and the proof is that it had to
    # allocate: a renewed table starts empty, so answering at all means a
    # fresh pair was taken rather than the cached attribute handed back.
    assert manager.allocated == 0
    after = manager.attribute_for("red", "black")
    assert manager.allocated == 1
    assert after == before, "same colours, so the same pair number comes back"


def test_a_screen_that_really_wants_too_many_pairs_stops_renewing(manager):
    """Renewing every frame would repaint everything every frame, for nothing.

    A screen genuinely needing more than the terminal has will exhaust the
    table again the moment it is rebuilt. Renewing then is not a recovery,
    it is a repaint loop, so the second attempt latches off and the manager
    goes back to handing out its nearest pair - which at least holds still.
    """
    manager.start()
    _exhaust(manager)
    assert manager.renew_if_exhausted() is True
    _exhaust(manager)  # the rebuild filled up again straight away
    assert manager.renew_if_exhausted() is False, "no second renewal"
    assert manager.exhausted, "and it stays exhausted, rather than pretending"
    _exhaust(manager)
    assert manager.renew_if_exhausted() is False, "latched, not merely skipped"


def test_a_frame_with_room_to_spare_re_arms_renewal(manager):
    """The latch is for a screen that stays too colourful, not one that was.

    Reaching a frame with pairs left means the last renewal did its job, so
    the next time the table fills it is allowed to be rebuilt again. Without
    this, one crowded frame would disable renewal for the life of the screen.
    """
    manager.start()
    _exhaust(manager)
    assert manager.renew_if_exhausted() is True
    # A quiet frame: the rebuilt table has room, so renewal re-arms.
    manager.pair_number(curses.COLOR_RED, curses.COLOR_BLACK)
    assert manager.renew_if_exhausted() is False
    _exhaust(manager)
    assert manager.renew_if_exhausted() is True, "re-armed by the quiet frame"


def test_reset_clears_the_renewal_latch(manager):
    manager.start()
    _exhaust(manager)
    manager.renew_if_exhausted()
    _exhaust(manager)
    manager.renew_if_exhausted()  # latches
    manager.reset()
    manager.start()
    _exhaust(manager)
    assert manager.renew_if_exhausted() is True


# ------------------------------- a background cannot carry an attribute


def test_a_background_is_not_chosen_on_brightness_it_cannot_have(manager):
    """The reported bug: a mid grey behind text arrived as pure black.

    At eight colours brightness is an attribute, and ``attribute_for`` drops
    the background's - curses will not brighten a background. What was
    missed is that the background's COLOUR was picked on the strength of
    that attribute. (130, 131, 128) resolved to black plus A_BOLD, meaning
    grey 127, and landed as (0, 0, 0): the worst of the eight, when yellow,
    cyan, magenta and white were all nearer.
    """
    grey = "#828380"
    as_foreground = parse_color(grey, ColorDepth.BASIC)
    as_background = parse_color(grey, ColorDepth.BASIC, background=True)

    assert as_foreground.attr, "a foreground may still carry its brightness"
    assert not as_background.attr, (
        "a background was given an attribute that will be thrown away, so the "
        "colour underneath it was chosen for a brightness it never gets"
    )
    assert as_background.color != curses.COLOR_BLACK, (
        "plain black is the FURTHEST of the eight from a mid grey; it was only "
        "ever chosen because A_BOLD was assumed to brighten it"
    )


def test_the_background_palette_is_the_colours_that_need_no_attribute(manager):
    """Every one of the eight is reachable as a background; none needs bold."""
    reached = set()
    for spec in (
        "#000000",
        "#cc0000",
        "#00cc00",
        "#cccc00",
        "#0000ee",
        "#cc00cc",
        "#00cccc",
        "#e5e5e5",
    ):
        resolved = parse_color(spec, ColorDepth.BASIC, background=True)
        assert not resolved.attr
        reached.add(resolved.color)
    assert reached == set(range(8))


def test_a_named_colour_behind_text_drops_to_what_it_can_show(manager):
    """`gray` is white plus A_DIM, and A_DIM does not reach a background."""
    behind = parse_color("gray", ColorDepth.BASIC, background=True)
    assert not behind.attr
    assert behind.color in range(8)


@pytest.mark.parametrize("manager", [16], indirect=True)
def test_above_eight_colours_a_background_is_resolved_as_before(manager):
    """Brightness is a colour number there, so nothing needs to change."""
    for spec in ("#828380", "#ff0000", "gray", "lime"):
        assert parse_color(spec, ColorDepth.BRIGHT) == parse_color(
            spec, ColorDepth.BRIGHT, background=True
        )


def test_a_cell_of_mid_grey_is_not_painted_black_on_black(manager):
    """End of the chain, and the shape the bug actually took on screen.

    Both halves of the cell want the same mid grey. Before the fix the
    foreground got bold-black (grey 127) and the background plain black, so
    the lower half of every such cell was a black stripe.
    """
    manager.start()
    grey = "#828380"
    attribute = manager.attribute_for(grey, grey)
    pair = (attribute & curses.A_COLOR) >> 8
    fg, bg = next(key for key, value in manager._pairs.items() if value == pair)
    assert not (fg == curses.COLOR_BLACK and bg == curses.COLOR_BLACK), (
        "a mid grey cell resolved to black on black, which shows nothing at all"
    )


# ------------------------------------------- perceptual colour resolution


def test_din99d_agrees_with_published_lab_values():
    """The conversion is checked against the standard, not against itself.

    A colour space implemented from a formula is exactly the kind of code
    that can be confidently wrong, so the L*a*b* stage inside it is pinned to
    published sRGB D65 values. If these drift, the distance metric is
    measuring something that is not colour.
    """
    from tkcurses._core.colors import to_linear

    def lab(rgb):
        red, green, blue = (to_linear(c) for c in rgb)
        x = 0.4124564 * red + 0.3575761 * green + 0.1804375 * blue
        y = 0.2126729 * red + 0.7151522 * green + 0.0721750 * blue
        z = 0.0193339 * red + 0.1191920 * green + 0.9503041 * blue

        def f(v):
            return v ** (1 / 3) if v > 216 / 24389 else ((24389 / 27) * v + 16) / 116

        fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
        return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))

    for rgb, published in (
        ((255, 255, 255), (100.00, 0.00, 0.00)),
        ((255, 0, 0), (53.24, 80.09, 67.20)),
        ((0, 255, 0), (87.73, -86.18, 83.18)),
        ((0, 0, 255), (32.30, 79.19, -107.86)),
    ):
        assert lab(rgb) == pytest.approx(published, abs=0.05), rgb


def test_grey_carries_far_less_chroma_than_a_saturated_colour():
    """Greys sit near the neutral axis - near, not exactly on it.

    DIN99d applies a tristimulus correction (1.12x - 0.12z) before L*a*b*,
    which nudges neutrals slightly off axis by an amount that grows with
    lightness: white lands at about (118, 129) rather than (128, 128). That
    is the space behaving as specified, not an error, so what is asserted is
    the property that matters for matching - a grey is an order of magnitude
    less chromatic than a primary, and so will never be chosen for one.
    """

    def chroma(rgb):
        _, a, b = din99d(rgb)
        return ((a - 128.0) ** 2 + (b - 128.0) ** 2) ** 0.5

    for grey in (0, 64, 128, 192, 255):
        assert chroma((grey, grey, grey)) < 12.0, grey
    for primary in ((255, 0, 0), (0, 255, 0), (0, 0, 255)):
        assert chroma(primary) > 80.0, primary


def test_din99d_lightness_rises_with_brightness():
    levels = [din99d((v, v, v))[0] for v in (0, 64, 128, 192, 255)]
    assert levels == sorted(levels)
    assert levels[0] == pytest.approx(0.0, abs=0.01)


def test_orange_is_nearer_red_than_yellow_perceptually():
    """The measurement behind the behaviour change, stated on its own.

    This is the one resolution a person is most likely to be surprised by,
    so the reason is pinned rather than left in a commit message.
    """
    orange = din99d((255, 128, 0))

    def gap(rgb):
        pair = zip(orange, din99d(rgb), strict=True)
        return sum((a - b) ** 2 for a, b in pair) ** 0.5

    assert gap((255, 0, 0)) < gap((205, 205, 0)), "bright red is nearer than yellow"
    assert gap((255, 0, 0)) < gap((255, 255, 0)), "and nearer than bright yellow"


def test_perceptual_matching_beats_weighted_rgb_on_a_gradient():
    """Why this replaced the weighted-RGB distance at all.

    A smooth two-channel ramp is where the old weights did worst: they
    disagreed with the eye about two thirds of the time. Scored in the space
    the eye works in, over the ramp, the perceptual choice must win - and by
    a margin, not by a rounding error.
    """

    def gap(resolved, want):
        shown = rgb_of_number(resolved.color, ColorDepth.BRIGHT)
        pair = zip(want, din99d(shown), strict=True)
        return sum((a - b) ** 2 for a, b in pair) ** 0.5

    ours = theirs = 0.0
    for step in range(0, 256, 8):
        rgb = (step, 255 - step, 128)
        want = din99d(rgb)
        weighted = min(
            _BRIGHT_PALETTE,
            key=lambda e: (
                2 * (rgb[0] - e[0][0]) ** 2
                + 4 * (rgb[1] - e[0][1]) ** 2
                + 3 * (rgb[2] - e[0][2]) ** 2
            ),
        )[1]
        ours += gap(_resolve_rgb(rgb, ColorDepth.BRIGHT), want)
        theirs += gap(weighted, want)
    assert ours < theirs * 0.85, (
        f"perceptual {ours:.1f} against weighted-RGB {theirs:.1f}; the new "
        "metric is supposed to be clearly better on exactly this picture"
    )


# ------------------------------- the two halves of a cell must agree


def _halves(manager, upper, lower):
    """The (fg, bg) colour numbers a cell of these two colours comes out as."""
    attribute = manager.attribute_for(upper, lower)
    pair = (attribute & curses.A_COLOR) >> 8
    for key, value in manager._pairs.items():
        if value == pair:
            return key
    raise AssertionError("no pair was allocated")


def test_a_smooth_cell_does_not_come_out_striped(manager):
    """The reported bug: big.png banded in hard stripes at eight colours.

    Two pixels six levels apart in green. A foreground may be bright, a
    background may not, so the same colour resolved to bold black - grey 127
    - above and to blue below, and a smooth gradient came out as stripes of
    grey over blue. The per-pixel score was not what was wrong; the
    incoherence was.
    """
    manager.start()
    attribute = manager.attribute_for("#1e5c80", "#1e6280")
    fg, bg = _halves(manager, "#1e5c80", "#1e6280")
    assert fg == bg, (
        f"two colours six levels apart came out as {fg} over {bg}; the "
        "palette cannot express that difference, so it must not invent one"
    )
    # Agreeing on the colour NUMBER is not enough. A_BOLD brightens the
    # foreground alone, so bold-black over black is two different greys and
    # stripes exactly as before - the agreed colour has to be one a
    # background can show.
    assert not attribute & curses.A_BOLD, (
        "both halves share a colour number, but only the foreground is "
        "brightened, so the cell is still striped: grey over black"
    )


def test_a_cell_whose_halves_really_differ_keeps_both(manager):
    """The rule must not flatten an edge, which is most of a picture."""
    manager.start()
    fg, bg = _halves(manager, "#ffffff", "#000000")
    assert fg != bg, "white over black is a real edge and must survive"


def test_agreement_does_not_cost_a_bright_foreground_on_an_edge(manager):
    """Brightness is still available where the halves are far apart."""
    manager.start()
    attribute = manager.attribute_for("#ff0000", "#000000")
    assert attribute & curses.A_BOLD, (
        "bright red over black is a real edge; the foreground should still "
        "be allowed its brightness"
    )


@pytest.mark.parametrize("manager", [16], indirect=True)
def test_sixteen_colours_needs_no_agreement_rule(manager):
    """There is no asymmetry to correct once brightness is a colour number.

    Both halves already draw from the same sixteen, so two near-identical
    colours already resolve alike and nothing should be flattened.
    """
    manager.start()
    fg, bg = _halves(manager, "#1e5c80", "#1e6280")
    assert fg == bg
    far_fg, far_bg = _halves(manager, "#ffffff", "#000000")
    assert far_fg != far_bg


def test_agreement_judges_the_colour_the_foreground_will_really_show(manager):
    """A bold foreground is compared as the bright colour, not the dim one.

    The rule asks how far each half had to move to reach the palette. For a
    foreground that came out bold, the colour it will actually show is the
    brightened one - comparing against the unbrightened entry overstates the
    error, so the rule fires too eagerly and flattens cells that hold a real
    difference. Measured, 316 pairs change their answer on this alone; this
    is one of them.
    """
    manager.start()
    fg, bg = _halves(manager, "#0060b0", "#0090b0")
    assert fg != bg, (
        "these two are far enough apart to be drawn differently; they are "
        "only flattened if the bold foreground is judged as its dim form"
    )


def test_below_the_palette_scales_with_the_error_being_accepted():
    """No threshold: the question is asked against the error already taken.

    The same pair of colours is 'the same' when the palette is coarse and
    'different' when it is fine, which is the whole point - there is no
    constant in the rule to tune or to get wrong.
    """
    from tkcurses._core.colors import _below_the_palette

    near, also_near = (30, 92, 128), (30, 98, 128)
    # A coarse approximation: both land a long way off, so six levels of
    # green between them is beneath notice.
    assert _below_the_palette(near, also_near, (0, 0, 0), (0, 0, 238))
    # A fine one: both land almost exactly, so the difference is real.
    assert not _below_the_palette(near, also_near, near, also_near)


def test_rgb_of_is_cached_because_a_picture_asks_per_cell():
    """Counted, not timed, so a slow runner cannot make it flake.

    A picture asks this twice for every cell, every time it is drawn - a
    58x36 window is 4,176 calls a repaint - and each one parsed the hex
    again. Measured on the redraw-cost harness, caching took an image
    repaint from 10.10ms to 5.79ms, which is the difference between fitting
    the budget on a CI runner and not.
    """
    rgb_of.cache_clear()
    for _ in range(500):
        rgb_of("#123456")
        rgb_of("red")
    info = rgb_of.cache_info()
    assert info.misses == 2, (
        f"{info.misses} misses for two distinct colours asked 500 times "
        "each; the answer is being worked out again every call"
    )
    assert info.hits == 998
