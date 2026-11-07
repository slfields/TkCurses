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

"""The compatibility matrix: every class and method of tkinter's, and
whether TkCurses has it.

Generated when the documentation is built, from tkinter itself and from
the library, so it cannot drift as a table kept by hand does. A method is
**supported** when TkCurses has it; **partial** when its docstring has a
``Differences from tkinter:`` section, whose first sentence says why, or
when only some of the widgets that inherit it have it; **missing** when it
is not there. Each method is listed once, under the tkinter class that
defines it - ``Misc``'s under ``Misc``, not under every widget.

A method is looked for where a program calls it: on TkCurses's
counterparts of the tkinter classes that inherit the class defining it -
the widgets, for ``Misc``, ``Grid`` or ``XView`` - or on the class itself
when nothing inherits it.

The page is written into the source tree when the build starts
(``docs/reference/compatibility.md``, ignored by git) and read like any
other page.
"""

from __future__ import annotations

import importlib
import inspect
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "reference" / "compatibility.md"

SUPPORTED, PARTIAL, MISSING = "supported", "partial", "missing"

#: tkinter's base classes no program makes an instance of.
ABSTRACT = frozenset({"BaseWidget", "Widget"})

#: A reST literal, ``like this``, as the Markdown page writes it.
LITERAL = re.compile(r"``(.+?)``")
#: A reST role, :meth:`Misc.after` or :class:`~tkcurses.Text`.
ROLE = re.compile(r":[a-z]+:`~?([^`]+)`")


@dataclass
class Row:
    name: str
    status: str
    why: str = ""


@dataclass
class Table:
    """One tkinter class, or a module's functions."""

    title: str
    status: str
    why: str = ""
    rows: list[Row] = field(default_factory=list)


@dataclass
class Module:
    ours: str
    theirs: str
    tables: list[Table] = field(default_factory=list)


def _surface() -> Any:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import docsurface

    return docsurface


def first_sentence(text: str) -> str:
    """The first sentence of a docstring section, as one plain line."""
    flat = " ".join(text.split())
    flat = ROLE.sub(lambda m: m.group(1).rsplit(".", 1)[-1], flat)
    flat = LITERAL.sub(r"\1", flat)
    match = re.match(r"(.+?[.!?])(\s|$)", flat)
    return match.group(1) if match else flat


def difference(obj: Any) -> str | None:
    """The first sentence of ``obj``'s Differences section, if it has one."""
    doc = inspect.getdoc(obj) or ""
    found = _surface().section(doc, _surface().DIFFERENCES_MARKER)
    return first_sentence(found) if found and found.strip() else None


def _public(cls: type) -> list[str]:
    return sorted(
        name
        for name, value in vars(cls).items()
        if not name.startswith("_") and (callable(value) or isinstance(value, property))
    )


def _classes(module: Any) -> list[type]:
    names = getattr(module, "__all__", None) or dir(module)
    found: list[type] = []
    for name in names:
        obj = getattr(module, name, None)
        if (
            inspect.isclass(obj)
            and obj.__module__ == module.__name__
            and not name.startswith("_")
            # ttk exports Labelframe and PanedWindow under a second name too.
            and obj not in found
        ):
            found.append(obj)
    return found


def _functions(module: Any) -> list[str]:
    names = getattr(module, "__all__", None) or dir(module)
    return sorted(
        name
        for name in names
        if not name.startswith("_")
        and inspect.isfunction(getattr(module, name, None))
        and getattr(module, name).__module__ == module.__name__
    )


def _holders(cls: type, theirs: Any, ours: Any) -> list[type]:
    """What answers for tkinter's ``cls`` here: TkCurses's counterparts of
    the tkinter classes that inherit it, which are what a program calls -
    ``Label().grid_columnconfigure``, not ``Grid.grid_columnconfigure`` -
    or, for a class nothing inherits, the class of that name."""
    heirs = [
        mine
        for heir in _classes(theirs)
        if heir is not cls and issubclass(heir, cls)
        for mine in [getattr(ours, heir.__name__, None)]
        if inspect.isclass(mine)
    ]
    if heirs:
        return heirs
    own = getattr(ours, cls.__name__, None)
    return [own] if inspect.isclass(own) else []


def _row(name: str, holders: list[type], own: Any = None) -> Row:
    # Only the widgets a program makes count: BaseWidget and Widget are
    # never instantiated, so a method they lack is not missing from anything.
    concrete = [h for h in holders if h.__name__ not in ABSTRACT] or holders
    having = [h for h in concrete if hasattr(h, name)]
    if not having:
        return Row(name, MISSING)
    if len(having) < len(concrete):
        lacking = [h.__name__ for h in concrete if h not in having]
        present = [h.__name__ for h in having]
        if len(present) <= len(lacking):
            return Row(name, PARTIAL, f"Only on {', '.join(present)}.")
        return Row(name, PARTIAL, f"Not on {', '.join(lacking)}.")
    # TkCurses's own class of that name first: what Misc.configure says
    # about itself holds for every widget, though Tk overrides it.
    sources = ([own] if inspect.isclass(own) and hasattr(own, name) else []) + having
    for source in sources:
        why = difference(getattr(source, name))
        if why:
            return Row(name, PARTIAL, why)
    return Row(name, SUPPORTED)


def module_matrix(ours_name: str, theirs_name: str) -> Module:
    ours = importlib.import_module(ours_name)
    theirs = importlib.import_module(theirs_name)
    module = Module(ours_name, theirs_name)
    functions = _functions(theirs)
    if functions:
        table = Table("Functions", SUPPORTED)
        for name in functions:
            mine = getattr(ours, name, None)
            if mine is None:
                table.rows.append(Row(name, MISSING))
            else:
                why = difference(mine)
                table.rows.append(Row(name, PARTIAL if why else SUPPORTED, why or ""))
        module.tables.append(table)
    for cls in _classes(theirs):
        holders = _holders(cls, theirs, ours)
        if not holders:
            module.tables.append(Table(cls.__name__, MISSING))
            continue
        own = getattr(ours, cls.__name__, None)
        why = difference(own) if inspect.isclass(own) else None
        status = PARTIAL if why else SUPPORTED
        if not inspect.isclass(own):
            why = "Not a class here; its methods are on the widgets that use it."
        table = Table(cls.__name__, status, why or "")
        table.rows = [_row(name, holders, own) for name in _public(cls)]
        module.tables.append(table)
    return module


def matrix() -> list[Module]:
    return [module_matrix(ours, theirs) for ours, theirs in _surface().COUNTERPARTS]


# -- the page ------------------------------------------------------------------

MARK = {SUPPORTED: "✓ supported", PARTIAL: "◐ partial", MISSING: "✗ missing"}


def _count(rows: list[Row]) -> dict[str, int]:
    return {s: sum(r.status == s for r in rows) for s in (SUPPORTED, PARTIAL, MISSING)}


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def render(modules: list[Module]) -> str:
    version = ".".join(map(str, sys.version_info[:2]))
    lines = [
        "# Compatibility with tkinter",
        "",
        "Every class, method and function in tkinter's modules, and whether",
        "TkCurses has it. **Supported** means it is there and behaves as",
        "tkinter's does. **Partial** means it is there and differs in some way,",
        "and says how; the class's or method's own entry in the reference says",
        "more. **Missing** means calling it raises `AttributeError`.",
        "",
        "Each method is listed once, under the tkinter class that defines it:",
        "the methods every widget has are under `Misc`, and the geometry",
        "managers' under `Pack`, `Grid` and `Place`. TkCurses also has API",
        "tkinter does not, which is not listed here; the reference marks it",
        "*TkCurses extension*.",
        "",
        "This page is generated each time the documentation is built, from",
        f"the library and from the tkinter of Python {version}.",
        "",
        "## Summary",
        "",
        "| Module | Supported | Partial | Missing |",
        "|---|---|---|---|",
    ]
    for module in modules:
        rows = [r for t in module.tables for r in t.rows]
        rows += [Row(t.title, t.status) for t in module.tables if not t.rows]
        count = _count(rows)
        lines.append(
            f"| [`{module.theirs}`](#{module.theirs.replace('.', '-')}) | "
            f"{count[SUPPORTED]} | {count[PARTIAL]} | {count[MISSING]} |"
        )
    for module in modules:
        lines += [
            "",
            f"({module.theirs.replace('.', '-')})=",
            f"## `{module.theirs}`",
            "",
        ]
        lines.append(f"Provided by `{module.ours}`.")
        for table in module.tables:
            lines += ["", f"### {table.title}", ""]
            if table.status != SUPPORTED or table.why:
                lines += [f"{MARK[table.status]}. {table.why}".rstrip(), ""]
            if not table.rows:
                continue
            lines += ["| Name | Status | Notes |", "|---|---|---|"]
            for row in table.rows:
                lines.append(
                    f"| `{row.name}` | {MARK[row.status]} | {_cell(row.why)} |"
                )
    return "\n".join(lines) + "\n"


def write(_app: Any = None) -> None:
    text = render(matrix())
    if not PAGE.exists() or PAGE.read_text() != text:
        PAGE.write_text(text)


def setup(app: Any) -> dict[str, Any]:
    app.connect("builder-inited", write)
    return {"parallel_read_safe": True, "version": "1"}
