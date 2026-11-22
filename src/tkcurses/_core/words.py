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
#
# Portions follow logic in the Tcl and Tk library scripts, each named beside
# the code that follows it. Tcl and Tk are copyright the Regents of the
# University of California, Sun Microsystems, Inc., Scriptics Corporation,
# ActiveState Corporation, Apple Inc. and other parties, and are used under
# the Tcl/Tk licence; see THIRD_PARTY_NOTICES.md.

"""Where a word starts and ends, as Tk 9's keyboard bindings find it.

entry.tcl, ttk/entry.tcl, spinbox.tcl and text.tcl move by word through three
procedures, ``tk::endOfWord``, ``tk::startOfNextWord`` and
``tk::startOfPreviousWord``. tk.tcl defines them in Tcl, over ``word.tcl``'s
regular expressions, only when they do not already exist - and Tk 9.0.2,
built with ICU, makes them in C, so the Tcl ones never load. Measured on
Tk 9.0.2 over 417 strings (``tests/support/word_boundaries.json``), what they
answer is one step over ICU's word boundaries and sometimes a second:

- ``endOfWord``: the next boundary, and the one after it unless the first
  lands on white space;
- ``startOfNextWord``: the next boundary, and the one after it if the first
  lands on white space;
- ``startOfPreviousWord``: the boundary before, and the one before that if it
  lands on white space.

None of the three loops, so a space and a newline next to each other are two
stops. An answer at the end of the string is no answer at all: Tk returns
``""`` there, and its callers then go to ``end`` themselves.

The boundaries are Unicode's default word boundaries, UAX #29 ("Unicode Text
Segmentation", https://www.unicode.org/reports/tr29/), with the rules that
matter for text typed into a field: letters, digits and connectors such as
``_`` run together; a letter-joining mark - ``:``, ``.``, ``'`` - between two
letters, or a number-joining one - ``,``, ``.``, ``'`` - between two digits,
does not break; combining marks stay with what they follow; a run of plain
spaces is one piece; anything else is a piece by itself. ICU's dictionary
segmentation of Chinese, Japanese and Thai is not modelled: a run of those
counts as one word. TkCurses-wmaq.
"""

from __future__ import annotations

import unicodedata
from typing import Protocol

__all__ = ["Characters", "end_of_word", "start_of_next_word", "start_of_previous_word"]


class Characters(Protocol):
    """What reading a line by character needs: a ``str``, or a hidden
    field's contents, which never become one."""

    def __len__(self) -> int: ...

    def __getitem__(self, index: int, /) -> str: ...


#: Between letters, keeps them one word (UAX #29 MidLetter and MidNumLet).
_JOINS_LETTERS = frozenset(
    ":\u00b7\u0387\u05f4\u2027\ufe13\ufe55\uff1a.'\u2018\u2019\u2024\ufe52\uff07\uff0e"
)
#: Between digits, keeps them one number (UAX #29 MidNum and MidNumLet).
_JOINS_DIGITS = frozenset(
    ",;\u037e\u066c\ufe50\ufe54\uff0c\uff1b.'\u2018\u2019\u2024\ufe52\uff07\uff0e"
)
#: The line breaks, after which nothing attaches (UAX #29 WB3a).
_NEWLINES = frozenset("\n\r\x0b\x0c\x85\u2028\u2029")


def _kind(character: str) -> str:
    """The class a character falls in, for :func:`_boundaries`."""
    if character == " " or unicodedata.category(character) == "Zs":
        return "space"
    category = unicodedata.category(character)
    if category in ("Mn", "Me", "Mc", "Cf") and character != "\u200b":
        return "extend"
    if category == "Nd":
        return "digit"
    if category == "Pc":
        return "connector"
    if category[0] in "LN":
        return "letter"
    return "other"


def _boundaries(text: Characters) -> list[int]:
    """Every word boundary in ``text``, 0 and its length included."""
    kinds = [_kind(text[i]) for i in range(len(text))]
    found = [0]
    for i in range(1, len(text)):
        here, before = kinds[i], kinds[i - 1]
        if here == "extend" and text[i - 1] not in _NEWLINES:
            continue  # WB4: a combining mark goes with what it follows
        # Skip back over combining marks, as WB4 says to.
        j = i - 1
        while j > 0 and kinds[j] == "extend":
            j -= 1
        before = kinds[j]
        if before == here == "space":
            continue  # WB3d
        wordish = ("letter", "digit", "connector")
        if before in wordish and here in wordish:
            continue  # WB5, WB8, WB9, WB10, WB13a/b
        if _joins(text, kinds, j, i):
            continue  # WB6, WB12: "it's", "3.14" before the mark
        if j > 0 and _joins(text, kinds, _before(kinds, j), j):
            continue  # WB7, WB11: and after it
        found.append(i)
    if text:
        found.append(len(text))
    return found


def _before(kinds: list[str], index: int) -> int:
    """The character before ``index``, skipping combining marks."""
    index -= 1
    while index > 0 and kinds[index] == "extend":
        index -= 1
    return index


def _joins(text: Characters, kinds: list[str], left: int, mark: int) -> bool:
    """Whether ``text[mark]`` is a joining mark with the same kind of
    character on both sides of it - ``left`` before it and the next one
    after."""
    if mark >= len(text) or left < 0:
        return False
    after = mark + 1
    while after < len(text) and kinds[after] == "extend":
        after += 1
    if after >= len(text):
        return False
    pair = (kinds[left], kinds[after])
    character = text[mark]
    if pair == ("letter", "letter") and character in _JOINS_LETTERS:
        return True
    return pair == ("digit", "digit") and character in _JOINS_DIGITS


def _following(bounds: list[int], index: int) -> int | None:
    return next((b for b in bounds if b > index), None)


def _preceding(bounds: list[int], index: int) -> int | None:
    return next((b for b in reversed(bounds) if b < index), None)


def end_of_word(text: Characters, start: int) -> int | None:
    """``tk::endOfWord``: where the word at or after ``start`` ends."""
    bounds = _boundaries(text)
    found = _following(bounds, start)
    if found is not None and found < len(text) and not text[found].isspace():
        found = _following(bounds, found)
    return found if found is not None and found < len(text) else None


def start_of_next_word(text: Characters, start: int) -> int | None:
    """``tk::startOfNextWord``: where the word after ``start`` begins."""
    bounds = _boundaries(text)
    found = _following(bounds, start)
    if found is not None and found < len(text) and text[found].isspace():
        found = _following(bounds, found)
    return found if found is not None and found < len(text) else None


def start_of_previous_word(text: Characters, start: int) -> int | None:
    """``tk::startOfPreviousWord``: where the word before ``start`` begins."""
    bounds = _boundaries(text)
    found = _preceding(bounds, min(start, len(text) + 1))
    if found is not None and found < len(text) and text[found].isspace():
        found = _preceding(bounds, found) if found > 0 else found
    return found
