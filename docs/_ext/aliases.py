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

"""One entry per method in the API reference, however many names it has.

tkinter gives many methods two names - ``wm_title`` and ``title``,
``pack_configure`` and ``pack`` - and autodoc documents each name in full,
so the reference showed the window manager's methods twice and ran each
sample twice. A method is documented once, under the name it was defined
with, and that entry says what else it is called.
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any


def _owner(func: Any) -> type | None:
    """The class a function was defined in, from its qualified name."""
    qualname = getattr(func, "__qualname__", "")
    if "." not in qualname or "<locals>" in qualname:
        return None
    try:
        obj: Any = importlib.import_module(func.__module__)
    except ImportError:
        return None
    for part in qualname.split(".")[:-1]:
        obj = getattr(obj, part, None)
    return obj if inspect.isclass(obj) else None


def other_names(func: Any) -> list[str]:
    """The other names ``func`` has on the class that defined it."""
    cls = _owner(func)
    if cls is None:
        return []
    return [
        name
        for name, value in vars(cls).items()
        if value is func and name != func.__name__ and not name.startswith("_")
    ]


def is_alias(name: str, obj: Any) -> bool:
    """Whether ``name`` is a second name for a method documented under its
    own: true only when the class that defined it also has it by that one."""
    if not inspect.isfunction(obj) or name == obj.__name__:
        return False
    cls = _owner(obj)
    return (
        cls is not None
        and vars(cls).get(obj.__name__) is obj
        and vars(cls).get(name) is obj
    )


def _skip(
    _app: Any, _what: str, name: str, obj: Any, _skip: bool, _options: Any
) -> bool | None:
    # None leaves the decision to autodoc and the other handlers.
    return True if is_alias(name, obj) else None


def _note(
    _app: Any, what: str, _name: str, obj: Any, _options: Any, lines: list[str]
) -> None:
    if what not in ("method", "function"):
        return
    names = other_names(obj)
    if names:
        listed = " and ".join(f"``{n}``" for n in sorted(names))
        lines.extend(["", f"Also called {listed}."])


def setup(app: Any) -> dict[str, Any]:
    app.setup_extension("sphinx.ext.autodoc")
    app.connect("autodoc-skip-member", _skip)
    # After napoleon, so the note follows the docstring's own sections.
    app.connect("autodoc-process-docstring", _note, priority=600)
    return {"parallel_read_safe": True, "version": "1"}
