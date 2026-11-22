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

"""Checking a chart widget's option values.

Each function takes a value as a program may give it - a number, its
string, a Tcl-style word - and returns it checked, or raises
``ValueError`` with Tk's wording, which the widget turns into
``TclError``. Colours are checked against the library's colour names,
the one thing here that is not self-contained.
"""

from __future__ import annotations

import math
from typing import Any

from tkcurses._core.colors import parse_color

__all__ = ["choice", "color", "count", "flag", "items", "number", "optional_count"]


def count(value: Any, name: str, *, minimum: int = 1) -> int:
    """An integer option, given as an int or its decimal string."""
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ValueError(f"{name} must be an integer, not {value!r}")
    try:
        number = int(value)
    except ValueError:
        raise ValueError(f"{name} must be an integer, not {value!r}") from None
    if number < minimum:
        raise ValueError(f"{name} must be at least {minimum}, not {number}")
    return number


def number(value: Any, name: str) -> float:
    """A number option, given as a number or its string."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number, not {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number, not {value!r}") from None
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number, not {value!r}")
    return number


def optional_count(value: Any, name: str, *, minimum: int) -> int | None:
    """An integer option that may be left unset, as None or ''."""
    if value is None or value == "":
        return None
    return count(value, name, minimum=minimum)


def choice(value: Any, name: str, allowed: tuple[str, ...]) -> str:
    text = str(value)
    if text not in allowed:
        # Tcl's punctuation: "a or b" for two, "a, b, or c" for more.
        listed = ", ".join(allowed[:-1]) + ("," if len(allowed) > 2 else "")
        raise ValueError(f'bad {name} "{text}": must be {listed} or {allowed[-1]}')
    return text


def color(value: Any) -> str:
    """A colour, refused here rather than when a bar is first drawn in it:
    an unknown name used to raise on every repaint and leave the whole
    window blank. Known or not does not depend on the terminal's depth."""
    text = str(value)
    try:
        parse_color(text)
    except ValueError:
        raise ValueError(f'unknown color name "{text}"') from None
    return text


def flag(value: Any) -> bool:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("1", "true", "yes", "on"):
            return True
        if lowered in ("0", "false", "no", "off", ""):
            return False
        raise ValueError(f"expected a boolean, not {value!r}")
    return bool(value)


def items(value: Any) -> tuple[Any, ...]:
    """A list option: a sequence, or empty for None or ''."""
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return tuple(value.split())
    try:
        return tuple(value)
    except TypeError:
        # One word is a list of one, as Tcl reads it: colors=5 is the
        # colour "5", refused as a colour, not a TypeError.
        return (value,)
