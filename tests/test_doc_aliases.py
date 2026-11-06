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

"""The API reference documents a method once, however many names it has:
docs/_ext/aliases.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("sphinx")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "_ext"))

import aliases  # noqa: E402

import tkcurses  # noqa: E402


def test_a_second_name_is_skipped():
    assert aliases.is_alias("title", tkcurses.Wm.wm_title)


def test_the_name_it_was_defined_with_is_kept():
    assert not aliases.is_alias("wm_title", tkcurses.Wm.wm_title)


class Lender:
    def lend(self) -> None:
        """Defined here."""


class Borrower:
    borrowed = Lender.lend


def test_a_name_another_class_gives_it_is_not_skipped():
    """Only a second name on the class that defined the method is skipped:
    a class that borrows it under its own name has no other entry for it."""
    assert not aliases.is_alias("borrowed", Lender.lend)


def test_the_kept_entry_names_the_others():
    lines = ["Get or set the title."]
    aliases._note(None, "method", "x", tkcurses.Wm.wm_title, None, lines)
    assert lines[-1] == "Also called ``title``."


def test_a_method_with_one_name_gets_no_note():
    lines = ["Delete."]
    aliases._note(None, "method", "x", tkcurses.Text.delete, None, lines)
    assert lines == ["Delete."]


def test_every_alias_of_one_method_is_named():
    """pack_propagate is also propagate and grid_propagate, as in tkinter."""
    assert sorted(aliases.other_names(tkcurses.Misc.pack_propagate)) == [
        "grid_propagate",
        "propagate",
    ]


def test_autodoc_is_told_to_skip_the_second_name_only():
    assert aliases._skip(None, "class", "title", tkcurses.Wm.wm_title, False, None)
    assert (
        aliases._skip(None, "class", "wm_title", tkcurses.Wm.wm_title, False, None)
        is None
    )
