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

"""The compatibility matrix says what the library has, and is complete.

``docs/_ext/compat.py`` generates ``docs/reference/compatibility.md`` on
every documentation build, from tkinter and from the library. These hold
it to known answers - each one checked against the library directly - and
to listing everything tkinter has exactly once.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "docs" / "_ext"))

import compat

tkinter = pytest.importorskip("tkinter")


@pytest.fixture(scope="module")
def modules():
    return compat.matrix()


def row(modules, module, table, name):
    found = next(m for m in modules if m.theirs == module)
    rows = next(t for t in found.tables if t.title == table).rows
    return next(r for r in rows if r.name == name)


@pytest.mark.parametrize(
    ("module", "table", "name", "status"),
    [
        ("tkinter", "Misc", "after", compat.SUPPORTED),
        ("tkinter", "Misc", "winfo_rgb", compat.SUPPORTED),
        # A geometry manager's method is looked for on the widgets, where a
        # program calls it, not on TkCurses's own Grid class.
        ("tkinter", "Grid", "grid_columnconfigure", compat.SUPPORTED),
        # A documented difference makes a method partial.
        ("tkinter", "Text", "dump", compat.PARTIAL),
        ("tkinter", "Text", "tag_bind", compat.SUPPORTED),
        ("tkinter", "Text", "window_create", compat.PARTIAL),
        ("tkinter", "Text", "image_create", compat.SUPPORTED),
        ("tkinter", "Listbox", "itemconfigure", compat.SUPPORTED),
        ("tkinter", "Canvas", "create_image", compat.PARTIAL),
        ("tkinter", "Canvas", "create_window", compat.PARTIAL),
        ("tkinter", "Wm", "iconbitmap", compat.MISSING),
        ("tkinter", "Functions", "Tcl", compat.MISSING),
        ("tkinter", "Functions", "mainloop", compat.SUPPORTED),
        ("tkinter.messagebox", "Functions", "showinfo", compat.SUPPORTED),
    ],
)
def test_a_known_answer(modules, module, table, name, status):
    assert row(modules, module, table, name).status == status


def test_a_difference_is_partial_and_says_why(modules):
    found = row(modules, "tkinter", "Text", "dump")
    assert found.status == compat.PARTIAL
    assert found.why.startswith("Of several marks")
    assert "``" not in found.why and ":" not in found.why.split(" ")[0]


def test_a_method_on_some_widgets_says_which(modules):
    """Misc.bbox is grid_bbox's other name in tkinter; here bbox is only the
    widgets' own, so it is partial and names them."""
    found = row(modules, "tkinter", "Misc", "bbox")
    assert found.status == compat.PARTIAL
    assert found.why.startswith("Only on ")
    assert "Canvas" in found.why
    assert "BaseWidget" not in found.why


def test_the_abstract_bases_do_not_count():
    """No program makes a BaseWidget or a Widget: a method every real
    widget has is supported, and a list of where it is never names them."""

    class BaseWidget:
        pass

    class Widget:
        pass

    class Label:
        x = 1

    class Button:
        x = 1
        y = 1

    class Entry:
        y = 1

    assert compat._row("x", [BaseWidget, Widget, Label, Button]).status == (
        compat.SUPPORTED
    )
    partial = compat._row("y", [BaseWidget, Widget, Label, Button, Entry])
    assert partial.status == compat.PARTIAL
    assert partial.why == "Not on Label."


def test_a_missing_class_is_one_entry(modules):
    tables = next(m for m in modules if m.theirs == "tkinter").tables
    wrapper = next(t for t in tables if t.title == "CallWrapper")
    assert wrapper.status == compat.MISSING and wrapper.rows == []


def test_every_answer_is_what_the_library_has(modules):
    """A row is missing exactly when no widget answering for it has it."""
    ours = {m.theirs: __import__(m.ours, fromlist=["_"]) for m in modules}
    for module in modules:
        for table in module.tables:
            if table.title == "Functions":
                for r in table.rows:
                    has = hasattr(ours[module.theirs], r.name)
                    assert (r.status != compat.MISSING) == has, (module.theirs, r.name)
                continue
            theirs = __import__(module.theirs, fromlist=["_"])
            holders = compat._holders(
                getattr(theirs, table.title), theirs, ours[module.theirs]
            )
            real = [h for h in holders if h.__name__ not in compat.ABSTRACT]
            for r in table.rows:
                has = any(hasattr(h, r.name) for h in real or holders)
                assert (r.status != compat.MISSING) == has, (table.title, r.name)


def test_every_tkinter_class_and_method_is_listed_once(modules):
    for module in modules:
        theirs = __import__(module.theirs, fromlist=["_"])
        titles = [t.title for t in module.tables if t.title != "Functions"]
        assert len(titles) == len(set(titles))
        assert set(titles) == {c.__name__ for c in compat._classes(theirs)}
        for table in module.tables:
            if table.title == "Functions" or not table.rows:
                continue
            cls = getattr(theirs, table.title)
            names = [r.name for r in table.rows]
            assert names == sorted(set(names))
            assert set(names) == {
                n
                for n, v in vars(cls).items()
                if not n.startswith("_") and (callable(v) or isinstance(v, property))
            }


def test_the_page_has_every_module_and_a_row_per_method(modules):
    page = compat.render(modules)
    for module in modules:
        anchor = module.theirs.replace(".", "-")
        assert f"({anchor})=" in page and f"(#{anchor})" in page
    rows = sum(len(t.rows) for m in modules for t in m.tables)
    assert page.count("\n| `") == rows
    assert f"Python {sys.version_info[0]}.{sys.version_info[1]}" in page


@pytest.mark.parametrize(
    ("text", "first"),
    [
        (
            "Called with ``nothing``, it answers. Then more.",
            "Called with nothing, it answers.",
        ),
        ("See :meth:`~tkcurses.Misc.after` here.", "See after here."),
        ("  Wrapped\n    over lines.  ", "Wrapped over lines."),
    ],
)
def test_the_first_sentence_is_plain_text(text, first):
    assert compat.first_sentence(text) == first


def test_the_generated_page_is_not_tracked():
    """Written on every build: committing it would be a hand-kept copy."""
    ignore = (Path(__file__).parents[1] / ".gitignore").read_text()
    assert "docs/reference/compatibility.md" in ignore.splitlines()
    assert inspect.getsourcefile(compat).endswith("docs/_ext/compat.py")
