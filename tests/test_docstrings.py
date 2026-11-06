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

"""The docstrings keep the API reference's convention (TkCurses-imii.3).

The reference is autodoc on the docstrings, so a docstring is a page a
user reads. What it must say is in ``tests/support/docsurface.py``; what
it applies to is found from tkinter itself, so a method added to match
tkinter is held to it without anyone listing it.

The breaches that were there when the convention was written down are
recorded, and these tests let that record shrink and never grow: a new
breach fails, and so does a fixed one still listed, so the fix cannot
quietly come undone later.
"""

from __future__ import annotations

import inspect
import json
import sys

import pytest

from tests.support import docsurface

RULES = (
    "undocumented",
    "tracker_ids",
    "private_names",
    "unmarked_extensions",
    "unlisted_borrowed",
)


@pytest.fixture(scope="module")
def found() -> dict[str, set[str]]:
    return docsurface.violations()


@pytest.fixture(scope="module")
def debt() -> dict[str, set[str]]:
    recorded = json.loads(docsurface.DEBT.read_text())
    return {rule: set(recorded.get(rule, [])) for rule in RULES}


@pytest.mark.parametrize("rule", RULES)
def test_no_new_breaches(rule, found, debt):
    new = sorted(found[rule] - debt[rule])
    assert not new, (
        f"{rule}: these break the docstring convention "
        f"(tests/support/docsurface.py says what it is): {new}"
    )


@pytest.mark.parametrize("rule", RULES)
def test_a_fixed_breach_leaves_the_record(rule, found, debt):
    fixed = sorted(debt[rule] - found[rule])
    assert not fixed, (
        f"{rule}: these keep the convention now, so take them out of "
        f"docstring_debt.json - python3 tests/support/docsurface.py --write: {fixed}"
    )


def test_the_surface_is_tkinters():
    """The comparison finds what it should, so an empty result means the
    docstrings are right rather than that it looked at nothing."""
    keys = {item.key for item in docsurface.tkinter_surface()}
    assert len(keys) > 500
    for expected in (
        "tkcurses.Button",
        "tkcurses.Misc.after",
        "tkcurses.ttk.Treeview.insert",
        "tkcurses.messagebox.showinfo",
    ):
        assert expected in keys, expected


def test_extensions_are_found():
    keys = {item.key for item in docsurface.extensions()}
    assert "tkcurses.Misc.winfo_colordepth" in keys
    assert "tkcurses.ttk.Theme" in keys
    # Another name for a standard class is not an extension.
    assert "tkcurses.TkCursesError" not in keys
    # Nor is a method another tkinter class has; that is a difference.
    assert not any(key.endswith(".select") for key in keys)


@pytest.mark.parametrize(("where", "added"), sorted(docsurface.LATER_TKINTER.items()))
def test_a_later_tkinter_method_is_tkinters(where, added):
    """Each name the oldest Pythons' tkinter lacks is on the newer one's."""
    import tkinter

    if sys.version_info < added:
        pytest.skip(f"tkinter has it from Python {added[0]}.{added[1]}")
    cls, name = where
    assert hasattr(getattr(tkinter, cls), name)


def test_borrowed_methods_are_found():
    import tkcurses.ttk

    borrowed = docsurface.borrowed_methods()
    assert "select" in borrowed[tkcurses.ttk.Checkbutton]


@pytest.mark.parametrize(
    ("doc", "expected"),
    [
        ("Summary.\n\nDifferences from tkinter:\n    Cells.\n", "    Cells."),
        (
            "Summary.\n\nDifferences from tkinter:\n    A.\n    B.\nArgs:\n",
            "    A.\n    B.",
        ),
        ("Summary. Differences from tkinter: inline.\n", None),
    ],
)
def test_a_section_is_a_napoleon_section(doc, expected):
    assert docsurface.section(inspect.cleandoc(doc), "Differences from tkinter:") == (
        expected
    )
