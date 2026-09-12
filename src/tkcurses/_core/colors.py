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
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tkcurses._core.dispatcher import CursesDispatcher

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["ColorManager", "ResolvedColor", "palette_rgb", "parse_color", "rgb_for"]


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


def palette_rgb(resolved: ResolvedColor) -> tuple[int, int, int]:
    """The RGB a terminal actually renders for a resolved colour.

    The inverse of nearest-match, and necessarily lossy: several names
    collapse onto one palette entry, so this reports what will be seen rather
    than what was asked for. ``winfo_rgb`` needs it, since tkinter answers
    that question with real channel values.
    """
    for rgb, entry in _PALETTE_RGB:
        if entry == resolved:
            return rgb
    # A_DIM has no palette entry of its own: it darkens the base colour, so
    # report the base at half intensity rather than claiming no match.
    base = ResolvedColor(resolved.color)
    for rgb, entry in _PALETTE_RGB:
        if entry == base:
            return tuple(value // 2 for value in rgb)  # type: ignore[return-value]
    return (0, 0, 0)


def _nearest(rgb: tuple[int, int, int]) -> ResolvedColor:
    """Closest palette entry by weighted RGB distance.

    Green is weighted most and blue least, roughly matching how much each
    contributes to perceived brightness, so approximations stay recognisable.
    """
    red, green, blue = rgb

    def distance(entry: tuple[tuple[int, int, int], ResolvedColor]) -> int:
        (pr, pg, pb), _ = entry
        return 2 * (red - pr) ** 2 + 4 * (green - pg) ** 2 + 3 * (blue - pb) ** 2

    return min(_PALETTE_RGB, key=distance)[1]


def parse_color(spec: str) -> ResolvedColor:
    """Resolve a tkinter colour specification to a terminal colour.

    Raises:
        ValueError: If ``spec`` is empty or a malformed hex string. An unknown
            *name* is approximated rather than rejected, since terminals cannot
            reproduce most X11 names exactly anyway.
    """
    if not spec or not spec.strip():
        raise ValueError("colour specification must not be empty")
    text = spec.strip().lower().replace(" ", "")
    if text in _NAMED:
        return _NAMED[text]
    if text.startswith("#"):
        rgb = rgb_for(text)
        if rgb is None:
            raise ValueError(f"malformed hex colour: {spec!r}")
        return _nearest(rgb)
    known = _X11_RGB.get(text)
    if known is not None:
        return _nearest(known)
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
        self._next = 1  # pair 0 is reserved for the terminal's default
        self._started = False
        self._has_colors = False
        self._max_pairs = 0
        self._exhausted = False

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
            # start_color() defines COLOR_PAIRS; read it defensively so a
            # curses build that omits it degrades rather than raising.
            self._max_pairs = getattr(curses, "COLOR_PAIRS", 0)
        return self._has_colors

    def reset(self) -> None:
        """Forget every allocated pair, for a screen being torn down."""
        self._pairs.clear()
        self._next = 1
        self._started = False
        self._has_colors = False
        self._exhausted = False

    @property
    def has_colors(self) -> bool:
        """True if the terminal reported colour support."""
        return self._has_colors

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
            return 0
        try:
            self._dispatcher.call(curses.init_pair, self._next, fg, bg)
        except curses.error:
            # Some terminals report more pairs than they will actually create.
            self._exhausted = True
            return 0
        self._pairs[key] = self._next
        self._next += 1
        return self._pairs[key]

    def attribute_for(self, fg: str, bg: str, attr: int = curses.A_NORMAL) -> int:
        """Combine colours and attributes into one curses attribute value.

        This is the resolver :class:`~tkcurses._core.screen.CursesScreen`
        applies to every cell it paints.
        """
        foreground = parse_color(fg)
        background = parse_color(bg)
        # A background cannot be bright or dim in curses, so only the
        # foreground's brightness attribute survives.
        combined = attr | foreground.attr
        pair = self.pair_number(foreground.color, background.color)
        if pair:
            combined |= curses.color_pair(pair)
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
