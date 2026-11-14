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
import math
import os
from dataclasses import dataclass
from enum import IntEnum
from functools import lru_cache
from typing import TYPE_CHECKING

from tkcurses._core import x11colors
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


@lru_cache(maxsize=65536)
def rgb_of(spec: str) -> tuple[int, int, int] | None:
    """The RGB a colour specification actually renders as, or None.

    **Cached, and it has to be.** A picture asks this twice per cell, every
    time it is drawn - a 58x36 window is 4,176 calls a repaint - and each
    one parsed the hex again. That alone was most of the cost of drawing an
    image once the cells were being written past curses as well.

    ``rgb_for`` answers only for ``#rgb`` forms, because that is all the
    resolver needs. This one also answers for the names, by resolving the
    name and reporting the RGB the terminal palette really shows for it - so
    ``PhotoImage.get`` can return a triple the way Tk's does without
    pretending a terminal has more colours than it has.
    """
    direct = rgb_for(spec)
    if direct is not None:
        return direct
    name = x11colors.lookup(spec)
    if name is None:
        return None
    resolved = _NAMED.get(name.lower())
    if resolved is None:
        return x11colors.NAMES[name]
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
#: The entries of :data:`_PALETTE_RGB` that need no attribute to be shown.
#:
#: A background can only ever be one of these. Curses will not brighten a
#: background - A_BOLD applies to the foreground alone - so resolving a
#: background against the full table picks a colour on the strength of
#: brightness it will never get. Measured, the mid grey (130, 131, 128) at
#: the centre of a gradient resolved to black plus A_BOLD, meaning grey 127,
#: and arrived as (0, 0, 0): the single WORST of the eight, when yellow,
#: cyan, magenta and white were all nearer.
_PLAIN_PALETTE: tuple[tuple[tuple[int, int, int], ResolvedColor], ...] = tuple(
    entry for entry in _PALETTE_RGB if not entry[1].attr
)

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


def to_linear(value: int) -> float:
    """One sRGB channel, 0-255, as linear light.

    sRGB is not linear in light - it carries roughly a 2.2 gamma - so the
    mean of two channel *bytes* is not the byte of the mean *brightness*.
    Anything averaging colour together has to come through here first and go
    back through :func:`from_linear` afterwards.

    The standard sRGB transfer function, IEC 61966-2-1. Noticed while reading
    chafa (https://hpjansson.org/chafa/, LGPL-3.0-or-later), which linearises
    before it does arithmetic on a colour; implemented here from the
    published function rather than from chafa's code. See ``TkCurses-e9l``.
    """
    v = value / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def from_linear(value: float) -> int:
    """Linear light back to one sRGB channel, 0-255. Inverse of the above."""
    v = 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)
    v = v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
    return round(v * 255)


#: sRGB byte to linear light, worked out once. :meth:`PhotoImage._average`
#: runs this over every pixel of a photograph, so it must not be a pow().
_LINEAR: tuple[float, ...] = tuple(to_linear(v) for v in range(256))


def linear_of(value: int) -> float:
    """:data:`_LINEAR` by index, clamped, for callers with untrusted bytes."""
    return _LINEAR[0 if value < 0 else (255 if value > 255 else value)]


@lru_cache(maxsize=65536)
def din99d(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """An sRGB triple in the DIN99d uniform colour space.

    **Why this exists: plain RGB distance is not what "nearest" means to an
    eye.** A uniform space is one where the straight-line distance between
    two colours is proportional to how different they look, which is exactly
    the question :func:`_nearest` is asking and cannot answer in RGB.

    Measured against the weighted-RGB distance this replaced, scored over
    every distinct colour in each picture:

        picture        depth       differs    old    din99d
        mickey.gif     8 colours       16%   76.38    68.72
        mickey.gif     256             53%   33.40    27.53
        earth.gif      8 colours        2%  106.09   103.63
        earth.gif      256             56%   27.40    23.23
        gradient.png   8 colours       64%  119.60    65.68
        gradient.png   16 colours      64%   70.38    47.93

    Better on every picture at every depth, and the smooth gradient - where
    the old weights disagreed with the eye about two thirds of the time - is
    45% better at eight colours. That picture was reported as looking
    significantly worse than another renderer's, which is what prompted this.

    sRGB is linearised first (see :func:`to_linear`), converted to CIE XYZ
    under a D65 white point, to CIE L*a*b*, and then through the DIN99d
    correction. Implemented from the published formula; the constants are the
    standard's. Noticed while reading chafa
    (https://hpjansson.org/chafa/, LGPL-3.0-or-later), which matches colours
    the same way - not taken from its code. See ``TkCurses-e9l``.

    Cached, and it must stay cached: this has a cube root, a logarithm and an
    ``atan2`` in it, and the palettes alone are 256 conversions.
    """
    red, green, blue = (to_linear(channel) for channel in rgb)
    x = 0.4124564 * red + 0.3575761 * green + 0.1804375 * blue
    y = 0.2126729 * red + 0.7151522 * green + 0.0721750 * blue
    z = 0.0193339 * red + 0.1191920 * green + 0.9503041 * blue
    # The DIN99d tristimulus correction, applied before L*a*b*.
    x = 1.12 * x - 0.12 * z

    def f(value: float) -> float:
        return (
            value ** (1 / 3)
            if value > 216 / 24389
            else ((24389 / 27) * value + 16) / 116
        )

    # D65, which is what sRGB is defined against.
    fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
    lightness = 116 * fy - 16
    a_star = 500 * (fx - fy)
    b_star = 200 * (fy - fz)

    # A 50-degree rotation, then a 1.14 stretch of the b axis, which is what
    # makes the space uniform where plain L*a*b* is not.
    cos50, sin50 = 0.6427876096865393, 0.766044443118978
    e = cos50 * a_star + sin50 * b_star
    g = 1.14 * (cos50 * b_star - sin50 * a_star)
    chroma = 22.5 * math.log1p(0.06 * math.hypot(e, g))
    hue = math.atan2(g, e) + math.radians(50)
    return (
        325.22 * math.log1p(0.0036 * lightness) * 2.5,
        chroma * math.cos(hue) * 2.5 + 128.0,
        chroma * math.sin(hue) * 2.5 + 128.0,
    )


def _din99d_palette(
    palette: tuple[tuple[tuple[int, int, int], ResolvedColor], ...],
) -> tuple[tuple[tuple[float, float, float], ResolvedColor], ...]:
    """``palette`` with every entry converted once, and kept.

    Keyed by identity of the palette tuple rather than its contents: these
    are module-level constants, there are four of them, and hashing 256
    triples on every lookup would cost more than the search it feeds.
    """
    converted = _DIN99D_PALETTES.get(id(palette))
    if converted is None:
        converted = tuple((din99d(rgb), resolved) for rgb, resolved in palette)
        _DIN99D_PALETTES[id(palette)] = converted
    return converted


#: Converted palettes by ``id()``. See :func:`_din99d_palette`.
_DIN99D_PALETTES: dict[
    int, tuple[tuple[tuple[float, float, float], ResolvedColor], ...]
] = {}


def _below_the_palette(
    first: tuple[int, int, int],
    second: tuple[int, int, int],
    shown_first: tuple[int, int, int],
    shown_second: tuple[int, int, int],
) -> bool:
    """True when a palette cannot honestly tell these two colours apart.

    The two halves of a cell are compared against how far each of them had
    to move to reach the palette. If they are closer to *each other* than to
    their own approximations, the difference between them is finer than
    anything the palette can express - so drawing them differently invents a
    difference the picture does not have.

    There is no threshold here on purpose. The question is asked relative to
    the error already being accepted, which scales by itself: at eight
    colours almost everything smooth is below the palette, and at 256 almost
    nothing is.
    """
    apart = sum(
        (a - b) ** 2 for a, b in zip(din99d(first), din99d(second), strict=True)
    )
    moved = max(
        sum(
            (a - b) ** 2
            for a, b in zip(din99d(first), din99d(shown_first), strict=True)
        ),
        sum(
            (a - b) ** 2
            for a, b in zip(din99d(second), din99d(shown_second), strict=True)
        ),
    )
    return apart < moved


def _nearest(
    rgb: tuple[int, int, int],
    palette: tuple[tuple[tuple[int, int, int], ResolvedColor], ...] | None = None,
) -> ResolvedColor:
    """Closest palette entry by perceptual distance.

    Measured in DIN99d - see :func:`din99d` - where a straight line is
    proportional to how different two colours look. This used to be a
    weighted RGB distance, green counted most and blue least, which is a
    guess at luminance and cannot account for the eye's sensitivity varying
    across the space. On a smooth gradient the two disagreed about two
    thirds of the time, and the perceptual answer was 45% closer.
    """
    want = din99d(rgb)
    best: ResolvedColor | None = None
    closest = 0.0
    # Strictly less than, in palette order, so the lowest colour number wins
    # a tie - black is both colour 0 and colour 16.
    for point, resolved in _din99d_palette(palette or _PALETTE_RGB):
        measure = (
            (want[0] - point[0]) ** 2
            + (want[1] - point[1]) ** 2
            + (want[2] - point[2]) ** 2
        )
        if best is None or measure < closest:
            closest, best = measure, resolved
    assert best is not None
    return best


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


@lru_cache(maxsize=65536)
def _nearest_extended(rgb: tuple[int, int, int]) -> ResolvedColor:
    """The nearest of the 256, by perceptual distance.

    **This walks all 256, and that is not a regression to be optimised away
    again.** It used to make forty-one comparisons instead of two hundred and
    fifty-six by *solving* the 6x6x6 cube one channel at a time rather than
    searching it. That shortcut is only sound for a separable metric - one
    where the best red can be chosen without knowing the green - and a
    perceptual distance is not separable. Keeping it would have made the
    search fast and the answer wrong.

    Paid for by caching instead, at two levels: the palette is converted once
    (:func:`_din99d_palette`) and each distinct colour is resolved once
    (here). Measured, dithering a 53x33 image made 981 *distinct* lookups,
    so the cache is what carries this, not the scan.
    """
    return _nearest(rgb, _EXTENDED_PALETTE)


def _resolve_rgb(
    rgb: tuple[int, int, int],
    depth: ColorDepth,
    *,
    background: bool = False,
) -> ResolvedColor:
    """An RGB triple as this tier expresses it.

    Only :data:`ColorDepth.DIRECT` can say exactly what was asked for; every
    other tier approximates against the palette it has.

    Args:
        background: True when this colour will be used as a background. At
            :data:`ColorDepth.BASIC` that is a smaller palette - see
            :data:`_PLAIN_PALETTE` - because brightness there is an
            attribute, and no attribute has ever brightened a background.
            Above BASIC brightness is a colour number, so it makes no
            difference and is ignored.
    """
    if depth is ColorDepth.DIRECT:
        return ResolvedColor(direct_color(rgb))
    if depth is ColorDepth.EXTENDED:
        return _nearest_extended(rgb)
    if background and depth is ColorDepth.BASIC:
        return _nearest(rgb, _PLAIN_PALETTE)
    return _nearest(rgb, _PALETTES.get(depth, _PALETTE_RGB))


@lru_cache(maxsize=4096)
def parse_color(
    spec: str,
    depth: ColorDepth = ColorDepth.BASIC,
    *,
    background: bool = False,
) -> ResolvedColor:
    """Resolve a tkinter colour specification to a terminal colour.

    Args:
        spec: A name, or ``#rgb`` in any of the four widths tkinter takes.
        depth: What the terminal can show. The default is the eight, which is
            what a terminal reports when it has never been asked.
        background: True when the answer will be used as a background. It
            changes nothing above :data:`ColorDepth.BASIC`; at BASIC it
            confines the answer to colours that need no attribute, because
            the attribute would be dropped and the colour chosen on its
            strength is then the wrong one.

    Raises:
        ValueError: If ``spec`` is empty, a malformed hex string, or a name
            Tk does not know - :mod:`tkcurses._core.x11colors` holds them
            all, and the rule for spaces within one.

    At :data:`ColorDepth.BASIC` the named table is used as it always was, with
    brightness expressed as an attribute. Above it, brightness is a colour
    number and the attribute goes away - which is what makes a bright
    *background* possible at all, since no attribute has ever brightened one.
    """
    if not spec or not spec.strip():
        raise ValueError("colour specification must not be empty")
    text = spec.strip().lower().replace(" ", "")
    name = None if text.startswith("#") else x11colors.lookup(spec)
    if name is not None:
        text = name.lower()
    if depth is ColorDepth.NONE:
        # No colour, but the attributes still work and are the only thing a
        # monochrome terminal has to tell one thing from another with, so the
        # eight-colour resolution is kept and only its colour thrown away.
        return ResolvedColor(-1, parse_color(spec, ColorDepth.BASIC).attr)
    if name is not None and text in _NAMED:
        named = _NAMED[text]
        if depth is ColorDepth.BASIC:
            if background and named.attr:
                # `gray` is white plus A_DIM and `lime` is green plus A_BOLD.
                # Behind text neither attribute arrives, so the name has to be
                # matched by the colour it renders as, against what a
                # background can hold.
                return _nearest(palette_rgb(named), _PLAIN_PALETTE)
            return named
        # Above the eight, a name is resolved through the colour it renders
        # as, so `red` stays #cd0000 whatever the tier - and its brightness
        # becomes a colour number rather than an attribute.
        return _resolve_rgb(palette_rgb(named), depth, background=background)
    if text.startswith("#"):
        rgb = rgb_for(text)
        if rgb is None:
            raise ValueError(f"malformed hex colour: {spec!r}")
        return _resolve_rgb(rgb, depth, background=background)
    if name is None:
        raise ValueError(f"unknown colour name: {spec!r}")
    return _resolve_rgb(x11colors.NAMES[name], depth, background=background)


#: Marks a cached attribute as :meth:`ColorManager.fallback_attribute_for`'s,
#: where the attributes argument goes: no real attribute is negative.
_FALLBACK = -1


class ColorManager:
    """Allocates curses colour pairs on demand.

    Curses requires every foreground/background combination to be registered
    as a numbered pair before use, and the number available is finite. Pairs
    are therefore allocated lazily and reused; once the terminal's supply is
    exhausted, further combinations fall back to the default pair rather than
    raising, so an over-colourful application degrades instead of failing.
    """

    def __init__(
        self,
        *,
        dispatcher: CursesDispatcher | None = None,
        ceiling: ColorDepth | None = None,
    ) -> None:
        self._dispatcher = dispatcher or CursesDispatcher.get()
        #: The most colour to use whatever the terminal reports - the
        #: ``[display] color_mode`` setting. Only ever a limit: curses refuses
        #: a colour number past the ``COLORS`` it started with.
        self._ceiling = ceiling
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
        #: Set by a renewal, cleared by the first frame that starts with
        #: pairs still to spare. If a renewal is followed straight away by
        #: another exhaustion, this screen genuinely wants more pairs than
        #: the terminal has and renewing again would only repaint everything
        #: for nothing - see :meth:`renew_if_exhausted`.
        self._renewed = False
        self._futile = False
        self._depth = ColorDepth.NONE
        #: Moves whenever the pair table is emptied, so a palette chosen to
        #: fit what was left in it can tell that it should be chosen again.
        self.generation = 0
        self._wanted = False

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
            if self._ceiling is not None:
                self._depth = min(self._depth, self._ceiling)
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
        self._renewed = False
        self._futile = False
        self._wanted = False
        self._depth = ColorDepth.NONE
        self.generation += 1

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

    @property
    def capacity(self) -> int:
        """How many pairs can exist at once, at most.

        Not :data:`curses.COLOR_PAIRS`, which is how many the terminal will
        *create* - 65536 on a modern ncurses. A pair is useless unless an
        attribute can name it, and :func:`curses.color_pair` packs the number
        into the eight bits of ``A_COLOR``, so 255 is the real ceiling. Pair 0
        is reserved for the terminal's own default colours and is not counted.

        Zero before :meth:`start`, and on a terminal without colour.
        """
        return max(self._max_pairs - 1, 0)

    @property
    def remaining(self) -> int:
        """How many more distinct ``(fg, bg)`` combinations will fit.

        What anything sizing its own palette has to ask - an image cannot
        assume it has the whole table, because widgets and text have already
        taken some of it. See :class:`~tkcurses._core.images.PhotoImage`.
        """
        # The clamp cannot currently fire, and is kept deliberately:
        # ``pair_number`` is the only thing that adds to ``_pairs`` and stops
        # at ``_max_pairs``, so the subtraction is non-negative by
        # construction. A mutation sweep will report removing it as an
        # equivalent mutant - it is, today, and the guard is here so that a
        # second way of allocating would report zero rather than a negative
        # budget that every caller would read as "plenty".
        return max(self.capacity - len(self._pairs), 0)

    def index_of(self, rgb: tuple[int, int, int]) -> int:
        """The palette number this colour resolves to, at this depth.

        For :class:`~tkcurses._core.direct.DirectPainter`, which writes
        ``ESC[38;5;N`` itself and so needs the number rather than a pair.
        Cached by :func:`parse_color` and :func:`_nearest_extended` behind
        it, so a repeated colour costs a dictionary lookup.
        """
        return _resolve_rgb(rgb, self._depth).color

    # ------------------------------------------------------------- renewal

    def renew_if_exhausted(self) -> bool:
        """Throw an exhausted pair table away, and say whether that happened.

        Called once at the start of a frame. Returns True if the caller must
        repaint everything, because every pair number it might have painted
        with is about to mean something else.

        Pairs are allocated lazily and were never given back, so the table was
        append-only for the life of the screen: measured on xterm-256color,
        one demo image took 238 of the 255 and the *second* one exhausted it,
        after which every new colour fell back to the nearest pair the first
        image happened to leave behind. An image viewer showed its first
        picture correctly and every later one in the wrong palette.

        Throwing the table away is safe, and cheaply so, because
        :class:`~tkcurses._core.screen.ScreenBuffer` stores a cell's colours
        as *names*, not as pair numbers: nothing on screen holds a number
        across a frame, and the repaint that follows re-asks for every cell.
        So the rebuilt table contains exactly the colours still visible, and
        the ones belonging to a picture that has gone are simply not asked
        for again.

        The attribute cache goes with it. That cache is keyed by colours but
        *holds whole attributes*, pair numbers included, so keeping it would
        hand out a recycled number under its old meaning - the one trap in
        an otherwise mechanical change.
        """
        if self._wanted:
            # Asked for, not run into: a new picture that would otherwise be
            # fitted into what an old one left behind. Asked once per
            # picture, so it is not counted towards giving up.
            self._wanted = False
            self._empty()
            return True
        if not self._exhausted:
            # A frame began with pairs still to spare, so the last renewal
            # did its job and the next one is allowed to try again.
            self._renewed = False
            return False
        if self._futile:
            return False
        if self._renewed:
            # Renewed, and exhausted again before a single frame could start
            # with room left. This screen wants more pairs than the terminal
            # has, so renewing merely repaints everything every frame to no
            # purpose. Degrade to nearest-pair instead, which is at least
            # stable to look at.
            self._futile = True
            return False
        self._empty()
        self._renewed = True
        return True

    def _empty(self) -> None:
        """Forget every pair, keeping the terminal's colour support."""
        self._pairs.clear()
        self._attributes.clear()
        self._next = 1
        self._exhausted = False
        self.generation += 1

    def ask_for_renewal(self) -> None:
        """Have the next frame empty the table and repaint, as running out
        does.

        For a picture about to be fitted into the pairs left: those may be
        held by a picture no longer shown, and only emptying the table
        finds out which colours are still wanted.
        """
        self._wanted = True

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

    def _agree(
        self,
        fg: str,
        bg: str,
        foreground: ResolvedColor,
        background: ResolvedColor,
    ) -> tuple[ResolvedColor, ResolvedColor]:
        """Stop the halves of one cell being resolved against two palettes.

        **Eight colours is the only tier where a cell's two halves do not get
        the same choices**, and left alone that difference manufactures
        stripes out of smooth pictures. A foreground may be bright, because
        A_BOLD reaches it; a background may not. So the very same colour gets
        two different answers depending on which half of the cell it lands
        in. Measured on big.png, two pixels six levels apart in green:

            #1e5c80  as a foreground -> black + A_BOLD, meaning grey 127
            #1e5c80  as a background -> blue

        A gradient drawn that way comes out banded in hard horizontal stripes
        of grey over blue, which is what a person reported seeing. The
        per-pixel error was not what was wrong - grey over blue scores better
        than either alone - the *incoherence* was.

        So when the two halves are closer to each other than to their own
        approximations - see :func:`_below_the_palette` - both are answered
        from the background's palette. They then agree, the cell is one flat
        colour, and a smooth region stays smooth. A cell whose halves really
        do differ keeps its bright foreground.
        """
        first, second = rgb_of(fg), rgb_of(bg)
        if first is None or second is None:
            return foreground, background
        shown_fg = rgb_of_number(foreground.color, self._depth)
        shown_bg = rgb_of_number(background.color, self._depth)
        if shown_fg is None or shown_bg is None:
            return foreground, background
        if foreground.attr & curses.A_BOLD and shown_fg is not None:
            # What the foreground will really show, which is the brightened
            # form - otherwise this compares against a colour nobody sees.
            brightened = rgb_of_number(foreground.color + 8, ColorDepth.BRIGHT)
            if brightened is not None:
                shown_fg = brightened
        if not _below_the_palette(first, second, shown_fg, shown_bg):
            return foreground, background
        agreed = parse_color(fg, self._depth, background=True)
        return agreed, agreed

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
        # Resolved as a background, which at eight colours is a different and
        # smaller palette: brightness there is an attribute and an attribute
        # never reaches a background, so asking for the nearest colour
        # overall picks one that cannot be shown. See _PLAIN_PALETTE.
        background = parse_color(bg, self._depth, background=True)
        if self._depth is ColorDepth.BASIC and fg != bg:
            foreground, background = self._agree(fg, bg, foreground, background)
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

    def fallback_attribute_for(self, fg: str, bg: str) -> int:
        """An attribute for ``fg`` on ``bg`` in the eight basic colours.

        For the cells written under a picture that is drawn past curses:
        they show only on a terminal that ignores those writes, and asking
        for every combination a photograph holds fills the pair table that
        everything else is drawn from. Eight colours make at most 64 pairs,
        and resolving one costs a dictionary lookup once seen.
        """
        key = (fg, bg, _FALLBACK)
        cached = self._attributes.get(key)
        if cached is not None:
            return cached
        depth = min(self._depth, ColorDepth.BASIC)
        foreground = parse_color(fg, depth)
        background = parse_color(bg, depth, background=True)
        combined = foreground.attr
        pair = self.pair_number(foreground.color, background.color)
        if pair:
            combined |= curses.color_pair(pair)
        self._attributes[key] = combined
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
