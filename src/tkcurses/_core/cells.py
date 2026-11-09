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

"""How many terminal cells a piece of text takes.

Not one per character. A terminal gives a wide character - CJK, a fullwidth
letter, most emoji - two cells, and a combining mark or a zero-width
character none: it joins the cell before it. Measured in the test harness's
terminal (pyte, which follows wcwidth as real terminals do):
``Label(text="A日本語B")`` drew ``A日本`` when five cells were allotted for
five code points, and ``x😀y`` lost the ``y``.

The widths follow the rules of Markus Kuhn's ``wcwidth`` (and the ``wcwidth``
package's refinements of them, which are what terminal emulators use),
computed from the Unicode Character Database that ships with Python rather
than a table of our own:

- **0** for nonspacing, enclosing and spacing combining marks (``Mn``,
  ``Me``, ``Mc``), for format characters (``Cf``) other than the soft hyphen
  and the prepended concatenation marks, for zero width space, and for the
  Hangul medial and final jamo (U+1160-U+11FF) and the Hangul filler, which
  join the syllable before them;
- **2** for East Asian Wide and Fullwidth characters (``W``, ``F``) and the
  regional indicator symbols that pair into flags;
- **1** for everything else.

A control character is not measured here: the widgets replace each with a
printable stand-in before anything is drawn.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "EMBEDDED",
    "cells",
    "char_cells",
    "clip_cells",
    "is_embedded",
    "pad_cells",
    "skip_cells",
]

#: The last private-use plane, which a Text reserves for what it embeds: an
#: embedded window or image stands in its text as one of these characters,
#: so that it takes one index as Tk's does, and this table says how many
#: cells it is wide. Characters from that plane are never text in a Text.
EMBEDDED_FIRST = "\U00100000"
EMBEDDED_LAST = "\U0010fffd"
#: Each embedded character in use, and what says how wide it is now.
EMBEDDED: dict[str, Callable[[], int]] = {}


def is_embedded(character: str) -> bool:
    """Whether a character is one of those reserved for embedding."""
    return EMBEDDED_FIRST <= character <= EMBEDDED_LAST


#: Format characters that DO take a cell: the soft hyphen, drawn as a hyphen,
#: and the Arabic and Syriac prepended concatenation marks, drawn as a sign.
_FORMAT_WITH_WIDTH = frozenset(
    "\u00ad\u0600\u0601\u0602\u0603\u0604\u0605\u06dd\u070f\u0890\u0891\u08e2"
    "\U000110bd\U000110cd"
)


def char_cells(character: str) -> int:
    """The cells one character takes on a terminal: 0, 1 or 2 - or, for a
    character a Text embeds, as many as the window or image is wide."""
    if character < "\u0300":
        # Latin, the common case, without asking the database.
        return 1
    if character >= EMBEDDED_FIRST:
        # Before the cache: an embedded window's width changes with it.
        width = EMBEDDED.get(character)
        if width is not None:
            return width()
        if character <= EMBEDDED_LAST:
            return 0  # one whose window or image has gone
    return _char_cells(character)


@lru_cache(maxsize=4096)
def _char_cells(character: str) -> int:
    """:func:`char_cells` for a character the Unicode database decides."""
    category = unicodedata.category(character)
    if category in ("Mn", "Me", "Mc"):
        return 0
    if category == "Cf":
        return 1 if character in _FORMAT_WITH_WIDTH else 0
    if "\u1160" <= character <= "\u11ff" or character == "\u3164":
        return 0
    if "\U0001f1e6" <= character <= "\U0001f1ff":
        return 2
    return 2 if unicodedata.east_asian_width(character) in ("W", "F") else 1


def cells(text: str) -> int:
    """The cells ``text`` takes on one row."""
    if text.isascii():
        return len(text)
    return sum(char_cells(character) for character in text)


def clip_cells(text: str, width: int) -> str:
    """The longest start of ``text`` that fits in ``width`` cells.

    A wide character that would straddle the edge is left out rather than
    cut in half, and a combining mark stays with the character it follows.
    """
    if width <= 0:
        return ""
    if text.isascii():
        return text[:width]
    used = 0
    for index, character in enumerate(text):
        used += char_cells(character)
        if used > width:
            return text[:index]
    return text


def pad_cells(text: str, width: int) -> str:
    """``text`` cut or padded with spaces to exactly ``width`` cells.

    ``str.ljust`` in cells: a wide character that would straddle the end is
    replaced by the space it leaves.
    """
    text = clip_cells(text, width)
    return text + " " * (max(0, width) - cells(text))


def skip_cells(text: str, count: int) -> tuple[str, int]:
    """``text`` less the characters in its first ``count`` cells.

    Returns what is left and how many cells further right it starts than
    ``count`` says, which is 1 when a wide character straddled the cut: its
    half that would have been shown is a blank cell, not half a character.
    """
    if count <= 0:
        return text, 0
    if text.isascii():
        return text[count:], 0
    used = 0
    for index, character in enumerate(text):
        if used >= count and char_cells(character) > 0:
            return text[index:], used - count
        used += char_cells(character)
    return "", max(0, used - count)
