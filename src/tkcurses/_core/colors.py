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

"""Translate tkinter colour names into curses colours and pairs.

tkinter accepts X11 colour names and ``#rrggbb`` strings. A terminal offers
eight colours, optionally doubled by the bold and dim attributes, so every
colour has to be approximated. Two mechanisms do that:

* The names listed in ARCHITECTURE.md "Extended X11 Color Approximations" have
  fixed mappings, given there.
* Everything else - hex strings and names not in the table - is matched to the
  nearest entry of the 16-colour palette by weighted RGB distance.

Nearest-match replaces the threshold cascade the specification sketched, which
left gaps: ``#ff8000`` matched none of its dominant-channel rules and fell
through to dim white, turning orange grey.
"""

from __future__ import annotations

import contextlib
import curses
import os
from dataclasses import dataclass
from enum import IntEnum
from functools import lru_cache
from typing import TYPE_CHECKING

from tkcurses._core.dispatcher import CursesDispatcher

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "ColorDepth",
    "ColorManager",
    "ResolvedColor",
    "detect_depth",
    "palette_rgb",
    "parse_color",
    "rgb_for",
    "rgb_of",
    "truecolor_hinted",
]


class ColorDepth(IntEnum):
    """How much colour a terminal has, which is not one thing.

    Terminfo answers this, and the numbers are its own: ``tigetnum("colors")``
    gives -1 where there is no colour at all, then 8, 16, 256, and 16777216
    for a terminal that takes a colour number as an RGB triple. The names here
    are ordered, so ``depth >= ColorDepth.EXTENDED`` asks the useful question.
    """

    #: No colour. Bold, reverse and underline are all there is.
    NONE = 0
    #: The original eight. A bright *foreground* is reachable with A_BOLD; a
    #: bright background is not reachable at all, which is why every bright
    #: colour in this library is a duplicate of its dark form below this tier.
    BASIC = 8
    #: The eight and their bright forms as real colours, 8 to 15. From here
    #: up, a bright background is a colour rather than an attribute.
    BRIGHT = 16
    #: The xterm cube: 16 named, a 6x6x6 cube, and 24 greys.
    EXTENDED = 256
    #: Colour numbers are 0xRRGGBB. ncurses does this for a terminal whose
    #: terminfo carries the RGB flag, and nothing special is needed to use it.
    DIRECT = 1 << 24


#: Values of COLORTERM that mean 24-bit colour. The convention exists because
#: terminfo under-reports: this very terminal is xterm-256color and does
#: truecolor, and xterm-direct is a TERM almost nobody sets.
TRUECOLOR_ENV = frozenset({"truecolor", "24bit"})


def detect_depth(colors: int | None = None, direct: bool = False) -> ColorDepth:
    """Work out what a terminal can do, from what terminfo says about it.

    Args:
        colors: ``tigetnum("colors")``, or None to ask terminfo now.
        direct: ``tigetflag("RGB")``, which marks a terminal whose colour
            numbers are RGB triples.

    Returns:
        The nearest tier at or below what the terminal reported. An
        unrecognised number rounds *down* - 88-colour rxvt comes back as 16 -
        because asking for a colour the terminal has not got puts the wrong
        colour on the screen, while asking for one fewer costs only accuracy.

    ``COLORTERM`` is deliberately not consulted here. It is the convention by
    which a truecolor terminal admits to being one when terminfo does not,
    but what it promises is that *escape sequences* will be understood - not
    that ncurses is in direct mode. Acting on it here would send colour
    numbers of 0xRRGGBB to a terminal whose curses expects 0 to 255. See
    :func:`truecolor_hinted` and TkCurses-b2b.
    """
    if colors is None:
        colors = _terminfo_number("colors")
    if direct or colors >= ColorDepth.DIRECT:
        return ColorDepth.DIRECT
    depth = ColorDepth.NONE
    for tier in (ColorDepth.BASIC, ColorDepth.BRIGHT, ColorDepth.EXTENDED):
        if colors >= tier:
            depth = tier
    return depth


def truecolor_hinted(colorterm: str | None = None) -> bool:
    """True if ``COLORTERM`` says the terminal understands 24-bit colour.

    Separate from :func:`detect_depth` because it is a promise about escape
    sequences rather than about curses. A terminal can be
    ``TERM=xterm-256color`` with ``COLORTERM=truecolor`` - as the one this was
    written on is - which means terminfo reports 256, curses can only be
    asked for 256, and exact colour is reachable only by writing past curses
    entirely.
    """
    if colorterm is None:
        colorterm = os.environ.get("COLORTERM", "")
    return colorterm.strip().lower() in TRUECOLOR_ENV


def _terminfo_number(capability: str) -> int:
    """One numeric terminfo capability, or -1 if it cannot be read."""
    with contextlib.suppress(curses.error, ValueError, TypeError):
        return int(curses.tigetnum(capability))
    return -1


def _terminfo_flag(capability: str) -> bool:
    """One boolean terminfo capability, false if it cannot be read."""
    with contextlib.suppress(curses.error, ValueError, TypeError):
        return curses.tigetflag(capability) > 0
    return False


@dataclass(frozen=True, slots=True)
class ResolvedColor:
    """A terminal colour and the attribute that selects its bright/dim form."""

    color: int
    attr: int = curses.A_NORMAL


# --------------------------------------------------------------------------
# Palettes
# --------------------------------------------------------------------------

#: The eight base colours by name.
_BASE: dict[str, int] = {
    "black": curses.COLOR_BLACK,
    "red": curses.COLOR_RED,
    "green": curses.COLOR_GREEN,
    "yellow": curses.COLOR_YELLOW,
    "blue": curses.COLOR_BLUE,
    "magenta": curses.COLOR_MAGENTA,
    "cyan": curses.COLOR_CYAN,
    "white": curses.COLOR_WHITE,
}

#: Named approximations, exactly as ARCHITECTURE.md specifies them.
_NAMED: dict[str, ResolvedColor] = {
    **{name: ResolvedColor(value) for name, value in _BASE.items()},
    "gray": ResolvedColor(curses.COLOR_WHITE, curses.A_DIM),
    "grey": ResolvedColor(curses.COLOR_WHITE, curses.A_DIM),
    "lightgray": ResolvedColor(curses.COLOR_WHITE),
    "lightgrey": ResolvedColor(curses.COLOR_WHITE),
    "darkgray": ResolvedColor(curses.COLOR_BLACK, curses.A_BOLD),
    "darkgrey": ResolvedColor(curses.COLOR_BLACK, curses.A_BOLD),
    "orange": ResolvedColor(curses.COLOR_YELLOW),
    "pink": ResolvedColor(curses.COLOR_MAGENTA),
    "purple": ResolvedColor(curses.COLOR_MAGENTA),
    "violet": ResolvedColor(curses.COLOR_MAGENTA),
    "brown": ResolvedColor(curses.COLOR_YELLOW, curses.A_DIM),
    "navy": ResolvedColor(curses.COLOR_BLUE, curses.A_DIM),
    "lime": ResolvedColor(curses.COLOR_GREEN, curses.A_BOLD),
    "aqua": ResolvedColor(curses.COLOR_CYAN),
    "turquoise": ResolvedColor(curses.COLOR_CYAN),
    "maroon": ResolvedColor(curses.COLOR_RED, curses.A_DIM),
    "olive": ResolvedColor(curses.COLOR_YELLOW, curses.A_DIM),
    "teal": ResolvedColor(curses.COLOR_CYAN, curses.A_DIM),
    "silver": ResolvedColor(curses.COLOR_WHITE),
    "fuchsia": ResolvedColor(curses.COLOR_MAGENTA, curses.A_BOLD),
}

#: RGB values the standard 16-colour terminal palette actually renders, used
#: for nearest-match. The bright half is reached with A_BOLD.
_PALETTE_RGB: tuple[tuple[tuple[int, int, int], ResolvedColor], ...] = (
    ((0, 0, 0), ResolvedColor(curses.COLOR_BLACK)),
    ((205, 0, 0), ResolvedColor(curses.COLOR_RED)),
    ((0, 205, 0), ResolvedColor(curses.COLOR_GREEN)),
    ((205, 205, 0), ResolvedColor(curses.COLOR_YELLOW)),
    ((0, 0, 238), ResolvedColor(curses.COLOR_BLUE)),
    ((205, 0, 205), ResolvedColor(curses.COLOR_MAGENTA)),
    ((0, 205, 205), ResolvedColor(curses.COLOR_CYAN)),
    ((229, 229, 229), ResolvedColor(curses.COLOR_WHITE)),
    ((127, 127, 127), ResolvedColor(curses.COLOR_BLACK, curses.A_BOLD)),
    ((255, 0, 0), ResolvedColor(curses.COLOR_RED, curses.A_BOLD)),
    ((0, 255, 0), ResolvedColor(curses.COLOR_GREEN, curses.A_BOLD)),
    ((255, 255, 0), ResolvedColor(curses.COLOR_YELLOW, curses.A_BOLD)),
    ((92, 92, 255), ResolvedColor(curses.COLOR_BLUE, curses.A_BOLD)),
    ((255, 0, 255), ResolvedColor(curses.COLOR_MAGENTA, curses.A_BOLD)),
    ((0, 255, 255), ResolvedColor(curses.COLOR_CYAN, curses.A_BOLD)),
    ((255, 255, 255), ResolvedColor(curses.COLOR_WHITE, curses.A_BOLD)),
)


def rgb_for(spec: str) -> tuple[int, int, int] | None:
    """Parse a ``#rgb``-style colour, returning None if it is not one.

    tkinter accepts four widths of hex specification, from ``#rgb`` to
    ``#rrrrggggbbbb``; each is scaled to eight bits per channel.
    """
    if not spec.startswith("#"):
        return None
    digits = spec[1:]
    if len(digits) not in (3, 6, 9, 12) or not all(
        c in "0123456789abcdefABCDEF" for c in digits
    ):
        return None
    per = len(digits) // 3
    parts = [digits[i * per : (i + 1) * per] for i in range(3)]
    scale = 16**per - 1
    red, green, blue = (round(int(part, 16) * 255 / scale) for part in parts)
    return red, green, blue


def rgb_of(spec: str) -> tuple[int, int, int] | None:
    """The RGB a colour specification actually renders as, or None.

    ``rgb_for`` answers only for ``#rgb`` forms, because that is all the
    resolver needs. This one also answers for the names, by resolving the
    name and reporting the RGB the terminal palette really shows for it - so
    ``PhotoImage.get`` can return a triple the way Tk's does without
    pretending a terminal has more colours than it has.
    """
    direct = rgb_for(spec)
    if direct is not None:
        return direct
    resolved = _NAMED.get(spec.lower())
    if resolved is None:
        return None
    for rgb, candidate in _PALETTE_RGB:
        if candidate == resolved:
            return rgb
    return None


def palette_rgb(
    resolved: ResolvedColor, depth: ColorDepth = ColorDepth.BASIC
) -> tuple[int, int, int]:
    """The RGB a terminal actually renders for a resolved colour.

    The inverse of nearest-match, and necessarily lossy: several names
    collapse onto one palette entry, so this reports what will be seen rather
    than what was asked for. ``winfo_rgb`` needs it, since tkinter answers
    that question with real channel values.

    Which entry a number stands for depends on the tier, so the tier has to
    be given: colour 9 is bright red on a terminal that has sixteen, and is
    nothing at all on one that has eight.
    """
    if depth is ColorDepth.DIRECT:
        return rgb_of_direct(resolved.color)
    palette = _PALETTES.get(depth, _PALETTE_RGB)
    for rgb, entry in palette:
        if entry == resolved:
            return rgb
    # A_DIM has no palette entry of its own: it darkens the base colour, so
    # report the base at half intensity rather than claiming no match.
    base = ResolvedColor(resolved.color)
    for rgb, entry in palette:
        if entry == base:
            return tuple(value // 2 for value in rgb)  # type: ignore[return-value]
    return (0, 0, 0)


#: The six levels each channel takes in xterm's 6x6x6 cube. Not evenly
#: spaced: the gap from 0 to 95 is wider than the rest, which is xterm's
#: choice and has to be matched or every dark colour lands a step out.
CUBE_LEVELS: tuple[int, ...] = (0, 95, 135, 175, 215, 255)

#: Where the cube starts in the 256-colour palette, and where the greys do.
CUBE_START = 16
GREY_START = 232
GREY_COUNT = 24


def _extended_palette() -> tuple[tuple[tuple[int, int, int], ResolvedColor], ...]:
    """The xterm 256: sixteen named, a 6x6x6 cube, then twenty-four greys.

    Built rather than listed. A table of 256 triples is 256 chances to mistype
    one, and the arithmetic is xterm's own and short.
    """
    entries: list[tuple[tuple[int, int, int], ResolvedColor]] = [
        (rgb, ResolvedColor(number)) for number, (rgb, _) in enumerate(_PALETTE_RGB)
    ]
    for index in range(216):
        red = CUBE_LEVELS[index // 36]
        green = CUBE_LEVELS[(index // 6) % 6]
        blue = CUBE_LEVELS[index % 6]
        entries.append(((red, green, blue), ResolvedColor(CUBE_START + index)))
    for index in range(GREY_COUNT):
        level = 8 + index * 10
        entries.append(((level, level, level), ResolvedColor(GREY_START + index)))
    return tuple(entries)


#: The sixteen as real colour numbers, for a terminal that has 8 to 15 rather
#: than reaching them through A_BOLD.
_BRIGHT_PALETTE: tuple[tuple[tuple[int, int, int], ResolvedColor], ...] = tuple(
    (rgb, ResolvedColor(number)) for number, (rgb, _) in enumerate(_PALETTE_RGB)
)

_EXTENDED_PALETTE = _extended_palette()

#: Which palette each tier approximates against. DIRECT has none: a colour
#: number *is* the colour there, so nothing is approximated at all.
_PALETTES: dict[ColorDepth, tuple[tuple[tuple[int, int, int], ResolvedColor], ...]] = {
    ColorDepth.BASIC: _PALETTE_RGB,
    ColorDepth.BRIGHT: _BRIGHT_PALETTE,
    ColorDepth.EXTENDED: _EXTENDED_PALETTE,
}


@lru_cache(maxsize=8)
def _by_number(depth: ColorDepth) -> dict[int, tuple[int, int, int]]:
    """A palette indexed by colour number, for looking one up backwards.

    Built once per depth. Scanning the 256 entries each time is fine when a
    caller asks about a handful of colours and hopeless when it asks about
    one per pixel, which is what dithering does.
    """
    palette = _PALETTES.get(depth)
    if palette is None:
        return {}
    # First occurrence wins, which is what the linear scan this replaces
    # did. _PALETTE_RGB lists a colour number twice - once plain and once
    # bright, the bright one reached with A_BOLD - so a plain dict
    # comprehension answers (255, 0, 0) for red where the scan answered
    # (205, 0, 0), and every colour in the basic palette shifts.
    found: dict[int, tuple[int, int, int]] = {}
    for rgb, resolved in palette:
        found.setdefault(resolved.color, rgb)
    return found


def rgb_of_number(number: int, depth: ColorDepth) -> tuple[int, int, int] | None:
    """What a colour *number* shows as, which is the reverse of parse_color.

    Needed wherever two resolved colours have to be compared rather than
    just used: choosing the nearest already-allocated pair when the pair
    table is full, and measuring the error a pixel accumulates when it is
    moved to the nearest colour the terminal has.
    """
    if number < 0:
        return None
    if depth >= ColorDepth.DIRECT:
        return rgb_of_direct(number)
    return _by_number(depth).get(number)


def direct_color(rgb: tuple[int, int, int]) -> int:
    """The colour number ncurses uses for an RGB triple in direct mode."""
    red, green, blue = rgb
    return (red << 16) | (green << 8) | blue


def rgb_of_direct(number: int) -> tuple[int, int, int]:
    """The RGB behind a direct-mode colour number."""
    return ((number >> 16) & 0xFF, (number >> 8) & 0xFF, number & 0xFF)


def _nearest(
    rgb: tuple[int, int, int],
    palette: tuple[tuple[tuple[int, int, int], ResolvedColor], ...] | None = None,
) -> ResolvedColor:
    """Closest palette entry by weighted RGB distance.

    Green is weighted most and blue least, roughly matching how much each
    contributes to perceived brightness, so approximations stay recognisable.
    """
    red, green, blue = rgb

    def distance(entry: tuple[tuple[int, int, int], ResolvedColor]) -> int:
        (pr, pg, pb), _ = entry
        return 2 * (red - pr) ** 2 + 4 * (green - pg) ** 2 + 3 * (blue - pb) ** 2

    return min(palette or _PALETTE_RGB, key=distance)[1]


@lru_cache(maxsize=1)
def _extended_index() -> tuple[
    tuple[tuple[tuple[int, int, int], ResolvedColor], ...],
    tuple[tuple[tuple[int, int, int], ResolvedColor], ...],
]:
    """The 256 palette split into the part that can be solved and the rest.

    The cube is a product grid - every combination of six levels on each
    channel - and the distance below is *separable*: a weighted sum of
    per-channel squares. Minimising each channel on its own therefore gives
    the nearest cube entry exactly, with no search. What is left is the 16
    named colours and the 24 greys, forty entries to check by hand.
    """
    named = tuple(_EXTENDED_PALETTE[:CUBE_START])
    greys = tuple(_EXTENDED_PALETTE[GREY_START:])
    return named, greys


def _nearest_level(channel: int) -> int:
    """Which of the cube's six levels one channel is nearest to."""
    best = 0
    closest = abs(CUBE_LEVELS[0] - channel)
    for index in range(1, len(CUBE_LEVELS)):
        measure = abs(CUBE_LEVELS[index] - channel)
        if measure < closest:
            closest, best = measure, index
    return best


def _nearest_extended(rgb: tuple[int, int, int]) -> ResolvedColor:
    """The nearest of the 256, without walking all of them.

    Measured: dithering a 53x33 image made 981 distinct lookups and 251,136
    distance comparisons, which was over half the time it took. This makes
    forty-one comparisons instead of two hundred and fifty-six, and gives
    the same answer - the cube part is solved rather than searched.
    """
    red, green, blue = rgb
    named, greys = _extended_index()

    # In palette order, and strictly less than, because that is how a scan
    # of all 256 breaks a tie: the lowest colour number wins. Black is both
    # colour 0 and colour 16, and checking the cube first quietly answered
    # 16 - which is the same colour and a different number, and enough to
    # make this disagree with the scan it replaces on 209 of 20,000 random
    # colours.
    best: ResolvedColor | None = None
    closest = 0
    for (pr, pg, pb), resolved in named:
        measure = 2 * (red - pr) ** 2 + 4 * (green - pg) ** 2 + 3 * (blue - pb) ** 2
        if best is None or measure < closest:
            closest, best = measure, resolved

    levels = [_nearest_level(channel) for channel in (red, green, blue)]
    cube_rgb = (
        CUBE_LEVELS[levels[0]],
        CUBE_LEVELS[levels[1]],
        CUBE_LEVELS[levels[2]],
    )
    measure = (
        2 * (red - cube_rgb[0]) ** 2
        + 4 * (green - cube_rgb[1]) ** 2
        + 3 * (blue - cube_rgb[2]) ** 2
    )
    if measure < closest:
        closest = measure
        best = ResolvedColor(CUBE_START + levels[0] * 36 + levels[1] * 6 + levels[2])

    for (pr, pg, pb), resolved in greys:
        measure = 2 * (red - pr) ** 2 + 4 * (green - pg) ** 2 + 3 * (blue - pb) ** 2
        if measure < closest:
            closest, best = measure, resolved
    assert best is not None
    return best


def _resolve_rgb(rgb: tuple[int, int, int], depth: ColorDepth) -> ResolvedColor:
    """An RGB triple as this tier expresses it.

    Only :data:`ColorDepth.DIRECT` can say exactly what was asked for; every
    other tier approximates against the palette it has.
    """
    if depth is ColorDepth.DIRECT:
        return ResolvedColor(direct_color(rgb))
    if depth is ColorDepth.EXTENDED:
        return _nearest_extended(rgb)
    return _nearest(rgb, _PALETTES.get(depth, _PALETTE_RGB))


@lru_cache(maxsize=4096)
def parse_color(spec: str, depth: ColorDepth = ColorDepth.BASIC) -> ResolvedColor:
    """Resolve a tkinter colour specification to a terminal colour.

    Args:
        spec: A name, or ``#rgb`` in any of the four widths tkinter takes.
        depth: What the terminal can show. The default is the eight, which is
            what a terminal reports when it has never been asked.

    Raises:
        ValueError: If ``spec`` is empty or a malformed hex string. An unknown
            *name* is approximated rather than rejected, since terminals cannot
            reproduce most X11 names exactly anyway.

    At :data:`ColorDepth.BASIC` the named table is used as it always was, with
    brightness expressed as an attribute. Above it, brightness is a colour
    number and the attribute goes away - which is what makes a bright
    *background* possible at all, since no attribute has ever brightened one.
    """
    if not spec or not spec.strip():
        raise ValueError("colour specification must not be empty")
    text = spec.strip().lower().replace(" ", "")
    if depth is ColorDepth.NONE:
        # No colour, but the attributes still work and are the only thing a
        # monochrome terminal has to tell one thing from another with, so the
        # eight-colour resolution is kept and only its colour thrown away.
        return ResolvedColor(-1, parse_color(spec, ColorDepth.BASIC).attr)
    if text in _NAMED:
        named = _NAMED[text]
        if depth is ColorDepth.BASIC:
            return named
        # Above the eight, a name is resolved through the colour it renders
        # as, so `red` stays #cd0000 whatever the tier - and its brightness
        # becomes a colour number rather than an attribute.
        return _resolve_rgb(palette_rgb(named), depth)
    if text.startswith("#"):
        rgb = rgb_for(text)
        if rgb is None:
            raise ValueError(f"malformed hex colour: {spec!r}")
        return _resolve_rgb(rgb, depth)
    known = _X11_RGB.get(text)
    if known is not None:
        return _resolve_rgb(known, depth)
    raise ValueError(f"unknown colour name: {spec!r}")


#: A few further X11 names common in tkinter code, matched by RGB rather than
#: listed individually, so they degrade sensibly instead of raising.
_X11_RGB: dict[str, tuple[int, int, int]] = {
    "darkblue": (0, 0, 139),
    "darkgreen": (0, 100, 0),
    "darkred": (139, 0, 0),
    "darkcyan": (0, 139, 139),
    "darkmagenta": (139, 0, 139),
    "darkyellow": (139, 139, 0),
    "lightblue": (173, 216, 230),
    "lightgreen": (144, 238, 144),
    "lightyellow": (255, 255, 224),
    "lightcyan": (224, 255, 255),
    "lightpink": (255, 182, 193),
    "gold": (255, 215, 0),
    "beige": (245, 245, 220),
    "tan": (210, 180, 140),
    "salmon": (250, 128, 114),
    "coral": (255, 127, 80),
    "khaki": (240, 230, 140),
    "indigo": (75, 0, 130),
    "ivory": (255, 255, 240),
    "snow": (255, 250, 250),
}


class ColorManager:
    """Allocates curses colour pairs on demand.

    Curses requires every foreground/background combination to be registered
    as a numbered pair before use, and the number available is finite. Pairs
    are therefore allocated lazily and reused; once the terminal's supply is
    exhausted, further combinations fall back to the default pair rather than
    raising, so an over-colourful application degrades instead of failing.
    """

    def __init__(self, *, dispatcher: CursesDispatcher | None = None) -> None:
        self._dispatcher = dispatcher or CursesDispatcher.get()
        self._pairs: dict[tuple[int, int], int] = {}
        #: Whole resolved attributes, keyed by what was asked for. A screen
        #: paints one cell at a time and asks here for each - measured, a
        #: canvas of 500 items asked 22,500 times for about thirty distinct
        #: answers. Cleared by :meth:`reset` and whenever the depth is
        #: decided, which are the only things that change an answer.
        self._attributes: dict[tuple[str, str, int], int] = {}
        self._next = 1  # pair 0 is reserved for the terminal's default
        self._started = False
        self._has_colors = False
        self._max_pairs = 0
        self._exhausted = False
        self._depth = ColorDepth.NONE

    # ---------------------------------------------------------- lifecycle

    def start(self) -> bool:
        """Initialise colour support. Returns True if the terminal has it.

        A terminal without colour is not an error: everything still renders,
        using attributes alone.
        """
        if self._started:
            return self._has_colors
        self._started = True
        try:
            self._dispatcher.call(curses.start_color)
        except curses.error:
            self._has_colors = False
            return False
        self._has_colors = bool(self._dispatcher.call(curses.has_colors))
        if self._has_colors:
            # Let pair 0 keep the terminal's own default colours, so an
            # unstyled widget looks native rather than forced to white on black.
            with contextlib.suppress(curses.error):
                self._dispatcher.call(curses.use_default_colors)
            # Two different numbers, and using the wrong one silently ruins
            # the screen. COLOR_PAIRS is how many pairs the terminal will
            # CREATE - 65536 on a modern ncurses. A_COLOR is how many an
            # attribute can NAME, and curses.color_pair() packs the number
            # into that field: eight bits, so 256.
            #
            # Past 255 the number wraps instead of failing. Measured on
            # xterm-256color: color_pair(256) is 0, which is the terminal's
            # default colours; color_pair(257) is pair 1; color_pair(300) is
            # pair 44. Cells come out painted in some other pair's colours
            # entirely, and nothing reports a thing - allocation succeeded,
            # init_pair succeeded, exhausted stayed False.
            #
            # That is what "the image is way off at 256 colours and fine at
            # 8" turns out to be: eight colours never needs more than a few
            # dozen pairs, and an image at 256 runs through them.
            reported = getattr(curses, "COLOR_PAIRS", 0)
            encodable = (curses.A_COLOR >> 8) + 1
            self._max_pairs = min(reported, encodable) if reported else encodable
            # start_color() sets COLORS to what the running ncurses will
            # accept, which is the number that matters here. Terminfo is the
            # same number in every case measured, but this one cannot be out
            # of step with the library actually being called.
            self._depth = detect_depth(getattr(curses, "COLORS", 0))
            # The depth decides what every colour resolves to, so answers
            # worked out before it was known are not answers any more.
            self._attributes.clear()
        return self._has_colors

    def reset(self) -> None:
        """Forget every allocated pair, for a screen being torn down."""
        self._pairs.clear()
        self._attributes.clear()
        self._next = 1
        self._started = False
        self._has_colors = False
        self._exhausted = False
        self._depth = ColorDepth.NONE

    @property
    def has_colors(self) -> bool:
        """True if the terminal reported colour support."""
        return self._has_colors

    @property
    def depth(self) -> ColorDepth:
        """How many colours this terminal has, once :meth:`start` has run.

        :data:`ColorDepth.NONE` before then, and on a terminal that has no
        colour at all - the two are the same as far as painting goes.
        """
        return self._depth

    @property
    def allocated(self) -> int:
        """Number of distinct pairs allocated so far."""
        return len(self._pairs)

    @property
    def exhausted(self) -> bool:
        """True once the terminal's supply of pairs has run out."""
        return self._exhausted

    # --------------------------------------------------------- allocation

    def pair_number(self, fg: int, bg: int) -> int:
        """Return a curses pair number for ``fg`` on ``bg``, allocating if new."""
        if not self._has_colors:
            return 0
        key = (fg, bg)
        existing = self._pairs.get(key)
        if existing is not None:
            return existing
        if self._max_pairs and self._next >= self._max_pairs:
            self._exhausted = True
            return self._nearest_pair(fg, bg)
        try:
            self._dispatcher.call(curses.init_pair, self._next, fg, bg)
        except curses.error:
            # Some terminals report more pairs than they will actually create.
            self._exhausted = True
            return self._nearest_pair(fg, bg)
        self._pairs[key] = self._next
        self._next += 1
        return self._pairs[key]

    def _nearest_pair(self, fg: int, bg: int) -> int:
        """The closest pair already allocated, for when there are no more.

        Returning 0 instead - which is what this did - paints the cell in
        the terminal's default colours, so running out of pairs turned parts
        of a picture into whatever the background happens to be. An
        approximate colour is a far better answer than an unrelated one, and
        it is a real answer rather than a failure, so it can be cached.
        """
        if not self._pairs:
            return 0
        want_fg = self._rgb_of_number(fg)
        want_bg = self._rgb_of_number(bg)
        if want_fg is None or want_bg is None:
            return next(iter(self._pairs.values()))

        def distance(key: tuple[int, int]) -> int:
            have_fg = self._rgb_of_number(key[0])
            have_bg = self._rgb_of_number(key[1])
            if have_fg is None or have_bg is None:
                return 1 << 30
            return sum(
                (a - b) ** 2 for a, b in zip(want_fg, have_fg, strict=True)
            ) + sum((a - b) ** 2 for a, b in zip(want_bg, have_bg, strict=True))

        return self._pairs[min(self._pairs, key=distance)]

    def _rgb_of_number(self, number: int) -> tuple[int, int, int] | None:
        """What a colour number actually shows as, at this manager's depth."""
        return rgb_of_number(number, self._depth)

    def attribute_for(self, fg: str, bg: str, attr: int = curses.A_NORMAL) -> int:
        """Combine colours and attributes into one curses attribute value.

        This is the resolver :class:`~tkcurses._core.screen.CursesScreen`
        applies to every cell it paints.
        """
        cached = self._attributes.get((fg, bg, attr))
        if cached is not None:
            return cached
        if attr & curses.A_COLOR:
            # The caller already chose a colour pair, which is what a curses
            # program does - tkcurses.curses hands the pair straight through
            # in the attribute. Allocating a second one and OR-ing it in
            # would leave neither: A_COLOR is a packed field, not a flag.
            return attr
        foreground = parse_color(fg, self._depth)
        background = parse_color(bg, self._depth)
        # A background cannot be bright or dim in curses, so only the
        # foreground's brightness attribute survives.
        combined = attr | foreground.attr
        pair = self.pair_number(foreground.color, background.color)
        if pair:
            combined |= curses.color_pair(pair)
        # Cached either way now. This used to refuse to cache once the
        # allocator was exhausted, because an exhausted allocator answered
        # 0 - a failure, and caching a failure makes it permanent. It
        # answers with the nearest pair it already has instead, which is a
        # real and stable answer and worth keeping.
        self._attributes[(fg, bg, attr)] = combined
        return combined

    def preallocate(self, combinations: Iterable[tuple[str, str]]) -> int:
        """Allocate pairs for known combinations up front. Returns how many.

        Useful for a theme, where allocating during the first paint would
        otherwise cost a pair lookup per cell.
        """
        count = 0
        for fg, bg in combinations:
            before = self.allocated
            self.attribute_for(fg, bg)
            count += self.allocated - before
        return count
