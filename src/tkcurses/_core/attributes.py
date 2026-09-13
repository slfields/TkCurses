"""Text attributes and the border styles that stand in for tkinter reliefs.

Two related translations live here. The first turns attribute names and widget
states into curses attribute masks. The second turns tkinter's ``relief``
values into box-drawing characters: a terminal cannot shade a bevel, so a
raised border is distinguished from a sunken one by line style instead, which
is the closest a character grid gets to the same distinction.
"""

from __future__ import annotations

import curses
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "ATTRIBUTES",
    "BorderStyle",
    "attribute_names",
    "for_state",
    "from_font",
    "parse_attributes",
    "style_for_relief",
    "with_colors",
    "without",
]

#: Attribute names accepted anywhere a style is given, and their curses masks.
ATTRIBUTES: dict[str, int] = {
    "normal": curses.A_NORMAL,
    "bold": curses.A_BOLD,
    "dim": curses.A_DIM,
    "reverse": curses.A_REVERSE,
    "standout": curses.A_STANDOUT,
    "underline": curses.A_UNDERLINE,
    "blink": curses.A_BLINK,
    "italic": curses.A_ITALIC,
    "invisible": curses.A_INVIS,
}

#: How a widget's state shows without colour.
_STATE_ATTRIBUTES: dict[str, int] = {
    # tkinter's "normal" state; nothing is added.
    "normal": curses.A_NORMAL,
    # The widget under the pointer or holding focus stands out.
    "active": curses.A_REVERSE,
    # A terminal has no greying, so dim is the nearest equivalent.
    "disabled": curses.A_DIM,
}


def parse_attributes(spec: str | Iterable[str] | int) -> int:
    """Build a curses attribute mask from names, a space-separated string, or a mask.

    Raises:
        ValueError: If a name is not one of :data:`ATTRIBUTES`.
    """
    if isinstance(spec, int):
        return spec
    names = spec.split() if isinstance(spec, str) else list(spec)
    mask = curses.A_NORMAL
    for name in names:
        key = name.strip().lower()
        if not key:
            continue
        if key not in ATTRIBUTES:
            raise ValueError(f"unknown text attribute: {name!r}")
        mask |= ATTRIBUTES[key]
    return mask


def attribute_names(mask: int) -> tuple[str, ...]:
    """Names of the attributes set in ``mask``, for display and debugging."""
    return tuple(
        name for name, value in ATTRIBUTES.items() if value and mask & value == value
    )


def without(mask: int, *attributes: int) -> int:
    """Return ``mask`` with ``attributes`` cleared."""
    for attribute in attributes:
        mask &= ~attribute
    return mask


def with_colors(base: int, pair: int) -> int:
    """Return ``base`` wearing ``pair``'s colours instead of its own.

    Colour is a packed *field* in a curses attribute - ``A_COLOR`` is
    ``0xff00``, holding the pair's number - and not a flag. OR-ing a second
    pair onto an attribute that already carries one therefore produces the
    number of neither: pair 2 and pair 5 together are pair 7, and the cell
    comes out in some third colour entirely. Anything layering colour over
    an attribute that may already have some has to replace the field rather
    than add to it.
    """
    return (base & ~curses.A_COLOR) | pair


def for_state(state: str, base: int = curses.A_NORMAL) -> int:
    """Combine ``base`` with the attribute representing a widget ``state``.

    Raises:
        ValueError: If ``state`` is not one tkinter defines.
    """
    key = state.strip().lower()
    if key not in _STATE_ATTRIBUTES:
        raise ValueError(f"unknown widget state: {state!r}")
    return base | _STATE_ATTRIBUTES[key]


def from_font(
    *, bold: bool = False, italic: bool = False, underline: bool = False
) -> int:
    """Map font styling onto attributes.

    All fonts are monospace in a terminal, so weight and slant are the only
    parts of a font specification that can be rendered at all.
    """
    mask = curses.A_NORMAL
    if bold:
        mask |= curses.A_BOLD
    if italic:
        mask |= curses.A_ITALIC
    if underline:
        mask |= curses.A_UNDERLINE
    return mask


@dataclass(frozen=True, slots=True)
class BorderStyle:
    """The characters used to draw one style of box.

    Attributes are named for their position, following curses' ACS names so
    the mapping between the two stays obvious.
    """

    top_left: str
    top_right: str
    bottom_left: str
    bottom_right: str
    horizontal: str
    vertical: str
    #: Attribute applied to the border, used where line style alone is not
    #: enough to tell two reliefs apart.
    attr: int = curses.A_NORMAL

    def top(self, width: int) -> str:
        """The top edge of a box ``width`` cells wide."""
        return self._edge(self.top_left, self.top_right, width)

    def bottom(self, width: int) -> str:
        """The bottom edge of a box ``width`` cells wide."""
        return self._edge(self.bottom_left, self.bottom_right, width)

    def _edge(self, left: str, right: str, width: int) -> str:
        if width <= 0:
            return ""
        if width == 1:
            return left
        return left + self.horizontal * (width - 2) + right


#: Box styles standing in for tkinter's reliefs. A terminal cannot shade an
#: edge, so the reliefs are distinguished by line weight and style: solid and
#: ridge use heavier or doubled lines, groove and sunken lighter ones.
_RELIEF_STYLES: dict[str, BorderStyle] = {
    "flat": BorderStyle(" ", " ", " ", " ", " ", " "),
    "raised": BorderStyle("┌", "┐", "└", "┘", "─", "│", curses.A_BOLD),
    "sunken": BorderStyle("┌", "┐", "└", "┘", "─", "│", curses.A_DIM),
    "solid": BorderStyle("┌", "┐", "└", "┘", "─", "│"),
    "ridge": BorderStyle("╔", "╗", "╚", "╝", "═", "║"),
    "groove": BorderStyle("╒", "╕", "╘", "╛", "═", "│"),
}


def style_for_relief(relief: str) -> BorderStyle:
    """Return the box style standing in for a tkinter ``relief``.

    Raises:
        ValueError: If ``relief`` is not one tkinter defines.
    """
    key = relief.strip().lower()
    if key not in _RELIEF_STYLES:
        raise ValueError(f"unknown relief: {relief!r}")
    return _RELIEF_STYLES[key]
