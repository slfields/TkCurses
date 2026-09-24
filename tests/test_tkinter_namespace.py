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

"""What a star-import puts in scope, compared against tkinter itself.

**Compared against the real module, never against a list copied in here.**
A checklist of names is a second place for the truth to live, and it goes
stale silently - the point of these tests is that they cannot.

tkinter is imported by the TESTS only. The library does not import it, and
must not: ``tkcurses.constants`` defines its values rather than re-exporting
them precisely so that nothing drags in ``_tkinter`` at runtime.
"""

from __future__ import annotations

import tkinter.constants

import pytest

import tkcurses
import tkcurses.constants


def tkinter_constant_names() -> list[str]:
    return sorted(n for n in dir(tkinter.constants) if not n.startswith("_"))


def test_the_fixture_finds_the_constants():
    """A comparison against an empty set would pass and mean nothing."""
    assert len(tkinter_constant_names()) > 70


@pytest.mark.parametrize("name", tkinter_constant_names())
def test_every_tkinter_constant_is_in_scope(name):
    """The reported bug: `NameError: name 'RIGHT' is not defined`.

    A program written for tkinter does `from tkinter import *` and uses
    RIGHT, BOTH, NSEW and the rest without thinking about it. Every value
    behind those names already worked here; only the names were missing, so
    a program that would have run correctly stopped at import.
    """
    assert hasattr(tkcurses, name), (
        f"{name} is in tkinter's namespace and not in tkcurses's, so a "
        "star-import leaves it undefined"
    )


@pytest.mark.parametrize("name", tkinter_constant_names())
def test_every_tkinter_constant_has_the_same_value(name):
    """Same name and a different value would be worse than missing."""
    assert getattr(tkcurses, name) == getattr(tkinter.constants, name)


@pytest.mark.parametrize("name", tkinter_constant_names())
def test_the_constants_are_exported_by_a_star_import(name):
    """``__all__`` is what a star-import honours, not what is merely bound."""
    assert name in tkcurses.__all__, f"{name} is bound but not in __all__"


def test_no_curses_names_leak_into_the_tkinter_namespace():
    """The deliberate half of the decision.

    ``tkcurses.constants`` also carries curses names - A_BOLD, COLOR_RED,
    KEY_UP - which tkinter has no equivalent for. A star-import must not
    bind them: a program written against tkinter should not acquire names
    from us that tkinter would never have given it. They stay reachable as
    ``tkcurses.constants.A_BOLD``.
    """
    ours = {n for n in dir(tkcurses.constants) if not n.startswith("_")}
    theirs = set(tkinter_constant_names())
    curses_only = {n for n in ours - theirs if n.isupper()}
    assert curses_only, "the fixture expects curses extras to exist"
    leaked = sorted(curses_only & set(tkcurses.__all__))
    assert not leaked, f"curses-only names exported by a star-import: {leaked}"
    # And they are still reachable the explicit way.
    assert hasattr(tkcurses.constants, "A_BOLD")


def test_cascade_is_tkinters_meaning_not_the_menu_glyph():
    """Two different things wanted the same name, and tkinter's wins.

    ``_core.menus.CASCADE`` is the arrow drawn beside a submenu, '\\u25b8'.
    tkinter's CASCADE is the string 'cascade' naming an entry type. Exporting
    the wrong one would have drawn "File cascade" where the arrow belongs.
    """
    assert tkcurses.CASCADE == "cascade"

    from tkcurses._core.menus import CASCADE as glyph

    assert glyph == "▸"
    assert glyph != tkcurses.CASCADE
