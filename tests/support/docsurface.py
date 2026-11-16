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

"""The documented surface of TkCurses, found by comparing it with tkinter.

``tests/test_docstrings.py`` holds the docstrings to the convention;
this module only finds what the convention applies to, and finds it from
tkinter itself rather than from a list kept here - a list is a second
place for the truth to live, and it goes stale silently.

The convention, which ``docs/reference/index.md`` explains to readers:

- Every class, method and function TkCurses provides has a docstring,
  written for someone using the library: no tracker IDs and no private
  names, which belong in comments and ARCHITECTURE.md. That holds for
  tkinter's API, for the extensions and for the ``#:`` comments that
  document module data.
- Where it behaves differently from tkinter, a ``Differences from
  tkinter:`` section says how. A ttk class that has a method only the
  classic widget has in tkinter must name it there.
- API that tkinter does not have carries a ``TkCurses extension:``
  section - on the module, for a module that is one as a whole. Module
  data counts when a reference page shows it with ``autodata``.
- Every widget has a ``Sample output:`` section: an example the
  documentation build runs, showing the screen it draws beside it
  (``docs/_ext/tkscreens.py``).
- Every option a classic widget takes is named in its docstring. One that
  changes the drawing - measured, ``visible_options.json`` - has a sample:
  a widget's own option in a ``Sample output (name):`` section of its
  docstring, and an option many widgets share (``COMMON_OPTIONS``) once,
  under its heading on ``docs/reference/options.md``.

The docstrings did not all keep it when it was written down, and the
breaches as they stood are in ``docstring_debt.json``. The test lets that
list shrink and never grow. Rewrite it, after fixing some, with::

    python3 tests/support/docsurface.py --write
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType

#: Each TkCurses module and the tkinter module it stands in for.
COUNTERPARTS = (
    ("tkcurses", "tkinter"),
    ("tkcurses.ttk", "tkinter.ttk"),
    ("tkcurses.messagebox", "tkinter.messagebox"),
    ("tkcurses.filedialog", "tkinter.filedialog"),
    ("tkcurses.simpledialog", "tkinter.simpledialog"),
    ("tkcurses.colorchooser", "tkinter.colorchooser"),
    ("tkcurses.commondialog", "tkinter.commondialog"),
    ("tkcurses.dialog", "tkinter.dialog"),
    ("tkcurses.scrolledtext", "tkinter.scrolledtext"),
    ("tkcurses.dnd", "tkinter.dnd"),
    ("tkcurses.font", "tkinter.font"),
)

#: Modules that are TkCurses extensions as a whole. Their own docstring
#: carries the marker, and their members need not repeat it.
EXTENSION_MODULES = ("tkcurses.curses", "tkcurses.panel", "tkcurses.constants")

#: tkinter's API grew after Python 3.11, the oldest TkCurses supports, so
#: the tkinter a test runs against may be missing methods TkCurses provides
#: to match a newer one. They are tkinter's API all the same, not
#: extensions. The test checks each against the tkinter that has it, so an
#: entry cannot be wrong; one missing is found as an unmarked extension on
#: the oldest Python CI runs.
LATER_TKINTER = {
    ("Misc", "after_info"): (3, 13),
    ("Misc", "busy"): (3, 13),
    ("Misc", "busy_cget"): (3, 13),
    ("Misc", "busy_config"): (3, 13),
    ("Misc", "busy_configure"): (3, 13),
    ("Misc", "busy_current"): (3, 13),
    ("Misc", "busy_forget"): (3, 13),
    ("Misc", "busy_hold"): (3, 13),
    ("Misc", "busy_status"): (3, 13),
    ("Misc", "tk_busy"): (3, 13),
    ("Misc", "tk_busy_cget"): (3, 13),
    ("Misc", "tk_busy_config"): (3, 13),
    ("Misc", "tk_busy_configure"): (3, 13),
    ("Misc", "tk_busy_current"): (3, 13),
    ("Misc", "tk_busy_forget"): (3, 13),
    ("Misc", "tk_busy_hold"): (3, 13),
    ("Misc", "tk_busy_status"): (3, 13),
    ("PhotoImage", "copy_replace"): (3, 13),
    ("PhotoImage", "data"): (3, 13),
    ("PhotoImage", "read"): (3, 13),
}

EXTENSION_MARKER = "TkCurses extension:"
#: An example the documentation build runs and shows the screen of
#: (docs/_ext/tkscreens.py). Every widget has one - decided with the user,
#: TkCurses-imii.16.
SAMPLE_MARKER = "Sample output:"
DIFFERENCES_MARKER = "Differences from tkinter:"

DEBT = Path(__file__).with_name("docstring_debt.json")

#: What each widget's options do to its drawing, measured by
#: ``record_visible_options.py``. Themed widgets are under ``ttk.Button``.
VISIBLE = Path(__file__).with_name("visible_options.json")

#: The options Tk's own themed widgets have, recorded from Tk by
#: ``record_tk_ttk_options.py``. A themed widget is documented with these,
#: not with every option it accepts: it inherits the classic widget's too,
#: and those are not part of its interface (TkCurses-jo7l).
TK_TTK_OPTIONS = Path(__file__).with_name("tk_ttk_options.json")

#: Where the options many widgets share are described, once each, as Tk's
#: own options(n) manual does - decided with the user, TkCurses-imii.5.
OPTIONS_PAGE = Path(__file__).parents[2] / "docs" / "reference" / "options.md"
REFERENCE = OPTIONS_PAGE.parent

#: Tk's standard options (options(n)), and the three every widget has with a
#: meaning of its own - width, height and state - which the options page
#: describes once with each widget's unit.
COMMON_OPTIONS = frozenset(
    {
        "activebackground",
        "activeborderwidth",
        "activeforeground",
        "anchor",
        "background",
        "bitmap",
        "borderwidth",
        "compound",
        "cursor",
        "disabledforeground",
        "exportselection",
        "font",
        "foreground",
        "highlightbackground",
        "highlightcolor",
        "highlightthickness",
        "image",
        "insertbackground",
        "insertborderwidth",
        "insertofftime",
        "insertontime",
        "insertwidth",
        "jump",
        "justify",
        "orient",
        "padx",
        "pady",
        "placeholder",
        "placeholderforeground",
        "relief",
        "repeatdelay",
        "repeatinterval",
        "selectbackground",
        "selectborderwidth",
        "selectforeground",
        "setgrid",
        "takefocus",
        "text",
        "textvariable",
        "troughcolor",
        "underline",
        "wraplength",
        "xscrollcommand",
        "yscrollcommand",
        "width",
        "height",
        "state",
    }
)

#: The options most themed widgets share, described once on the options
#: page as ttk_widget(n) describes them, beside the standard ones.
THEMED_OPTIONS = frozenset({"class", "style", "padding"})

#: A sample for an option, or several: ``Sample output (relief):``,
#: ``Sample output (from, to):``.
NAMED_SAMPLE = re.compile(r"^\s*Sample output \((\w+(?:, \w+)*)\):\s*$", re.M)

#: A tracker ID - maintainer history, not something a reader can follow.
TRACKER_ID = re.compile(r"TkCurses-[a-z0-9]+(?:\.\d+)*")

#: A private name: ``_draw``, ``self._rect``, ``tkcurses._core``. A reader
#: cannot use one, and the reference does not show them. Reached through a
#: dot counts too; the first version did not, and missed all of those.
PRIVATE_NAME = re.compile(r"(?<!\w)_(?!tkinter\b)[a-z]\w*")


@dataclass(frozen=True)
class Item:
    """One documented object: what it is called in the reference, and it."""

    key: str
    obj: Any


def _module(name: str) -> ModuleType:
    return importlib.import_module(name)


def _public_names(module: ModuleType) -> list[str]:
    names = getattr(module, "__all__", None)
    if names is None:
        names = [n for n in dir(module) if not n.startswith("_")]
    return list(names)


def _key(obj: Any) -> str:
    raw = inspect.unwrap(getattr(obj, "__func__", obj))
    module = getattr(raw, "__module__", None) or "?"
    return f"{module}.{getattr(raw, '__qualname__', repr(raw))}"


def _documentable(obj: Any) -> bool:
    return inspect.isclass(obj) or inspect.isroutine(obj) or isinstance(obj, property)


def _tkinter_has(cls: type, name: str) -> bool:
    """Whether tkinter's class has the method, in any Python TkCurses
    supports - not only the one running."""
    return hasattr(cls, name) or any(
        (klass.__name__, name) in LATER_TKINTER for klass in cls.__mro__
    )


def class_counterparts() -> dict[type, list[type]]:
    """Each TkCurses class, and the tkinter classes it stands in for."""
    found: dict[type, list[type]] = {}
    for ours_name, theirs_name in COUNTERPARTS:
        ours, theirs = _module(ours_name), _module(theirs_name)
        for name in _public_names(theirs):
            theirs_obj = getattr(theirs, name, None)
            ours_obj = getattr(ours, name, None)
            if inspect.isclass(theirs_obj) and inspect.isclass(ours_obj):
                found.setdefault(ours_obj, []).append(theirs_obj)
    return found


def tkinter_surface() -> Iterator[Item]:
    """Every class, method and function of tkinter's that TkCurses provides,
    once each, under the name of the object that answers it."""
    seen: set[str] = set()

    def emit(obj: Any) -> Iterator[Item]:
        key = _key(obj)
        if key not in seen:
            seen.add(key)
            yield Item(key, obj)

    for ours_cls, theirs_list in class_counterparts().items():
        yield from emit(ours_cls)
        for theirs_cls in theirs_list:
            for name in dir(theirs_cls):
                if name.startswith("_") or not hasattr(ours_cls, name):
                    continue
                attr = getattr(ours_cls, name)
                if callable(attr):
                    yield from emit(attr)
    for ours_name, theirs_name in COUNTERPARTS:
        ours, theirs = _module(ours_name), _module(theirs_name)
        for name in _public_names(theirs):
            ours_obj = getattr(ours, name, None)
            if inspect.isroutine(ours_obj):
                yield from emit(ours_obj)


def extensions() -> Iterator[Item]:
    """API beyond tkinter's, outside the modules that are extensions whole.

    A method counts when tkinter has no such method on any class this
    class stands in for, nor on any class it inherits from - inheriting a
    method another tkinter class has is a difference, not an extension
    (see :func:`borrowed_methods`). A name that is only another name for a
    standard object, as ``TkCursesError`` is for ``TclError``, is not one.
    """
    counterparts = class_counterparts()
    seen: set[str] = set()
    for ours_cls in counterparts:
        for name in dir(ours_cls):
            if name.startswith("_"):
                continue
            static = inspect.getattr_static(ours_cls, name, None)
            attr = getattr(ours_cls, name, None)
            if not (callable(attr) or isinstance(static, property)):
                continue
            if any(
                _tkinter_has(theirs, name)
                for klass in ours_cls.__mro__
                for theirs in counterparts.get(klass, [])
            ):
                continue
            owner = next(k for k in ours_cls.__mro__ if name in vars(k))
            key = f"{owner.__module__}.{owner.__qualname__}.{name}"
            if key not in seen:
                seen.add(key)
                yield Item(key, static if isinstance(static, property) else attr)
    standard = {id(o) for o in counterparts} | {
        id(o) for c in counterparts.values() for o in c
    }
    for ours_name, theirs_name in COUNTERPARTS:
        ours, theirs = _module(ours_name), _module(theirs_name)
        for name in _public_names(ours):
            obj = getattr(ours, name, None)
            if hasattr(theirs, name) or not _documentable(obj) or id(obj) in standard:
                continue
            if inspect.ismodule(obj):
                continue
            key = f"{ours_name}.{name}"
            if key not in seen:
                seen.add(key)
                yield Item(key, obj)


def extension_module_members() -> Iterator[Item]:
    """The classes, methods and functions of the modules that are
    extensions whole. They need no marker of their own, and are held to
    the rest of the convention like anything else."""
    for name in EXTENSION_MODULES:
        module = _module(name)
        for attr in _public_names(module):
            obj = getattr(module, attr, None)
            if not _documentable(obj) or getattr(obj, "__module__", None) != name:
                continue
            yield Item(_key(obj), obj)
            if inspect.isclass(obj):
                for key, value in vars(obj).items():
                    if key.startswith("_"):
                        continue
                    if inspect.isfunction(value) or isinstance(value, property):
                        yield Item(f"{name}.{obj.__qualname__}.{key}", value)


def data_docs(source: str) -> dict[str, str]:
    """Module data and its documentation: each public name assigned at the
    top of ``source`` under a run of ``#:`` comment lines, as autodoc
    reads them."""
    lines = source.splitlines()
    found = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        else:
            continue
        if not isinstance(target, ast.Name):
            continue
        # Private names are not data a reader is shown; dunders such as
        # ``__version__`` are public API despite the underscore.
        dunder = target.id.startswith("__") and target.id.endswith("__")
        if target.id.startswith("_") and not dunder:
            continue
        comment: list[str] = []
        row = node.lineno - 2
        while row >= 0 and lines[row].lstrip().startswith("#:"):
            comment.insert(0, lines[row].lstrip()[2:].removeprefix(" "))
            row -= 1
        if comment:
            found[target.id] = "\n".join(comment)
    return found


def documented_data() -> Iterator[tuple[str, str]]:
    """Every documented piece of module data, as its key and its text."""
    modules = [ours for ours, _ in COUNTERPARTS] + list(EXTENSION_MODULES)
    for name in dict.fromkeys(modules):
        source = inspect.getsource(_module(name))
        for attr, doc in data_docs(source).items():
            yield f"{name}.{attr}", doc


def reference_data() -> set[str]:
    """The module data a reference page shows, by ``autodata``."""
    shown: set[str] = set()
    for page in REFERENCE.rglob("*.md"):
        shown.update(re.findall(r"^\.\. autodata:: (\S+)", page.read_text(), re.M))
    return shown


def borrowed_methods() -> dict[type, list[str]]:
    """Methods a class has that tkinter's own version of it lacks, because
    it inherits them from another class tkinter does have them on - a
    ttk.Checkbutton's ``select``, which only the classic one has in tkinter.
    Each belongs in its class's "Differences from tkinter" section."""
    counterparts = class_counterparts()
    found: dict[type, list[str]] = {}
    for ours_cls, theirs_list in counterparts.items():
        for theirs_cls in theirs_list:
            for name in sorted(dir(ours_cls)):
                if name.startswith("_") or hasattr(theirs_cls, name):
                    continue
                attr = getattr(ours_cls, name, None)
                if not callable(attr):
                    continue
                if any(
                    hasattr(other, name)
                    for klass in ours_cls.__mro__
                    for other in counterparts.get(klass, [])
                ):
                    found.setdefault(ours_cls, [])
                    if name not in found[ours_cls]:
                        found[ours_cls].append(name)
    return found


def widget_options(cls: type) -> set[str]:
    """Every option the widget takes: those it declares, less any a classic
    widget keeps from its base class and refuses, as LabelFrame does Frame's
    ``backgroundimage``. A themed widget's are all of them: its rules compare
    them with Tk's names separately."""
    options: dict[str, Any] = {}
    for klass in reversed(cls.__mro__):
        options.update(vars(klass).get("_widget_options", {}) or {})
    public = getattr(cls, "_public_options", None)
    if public is None or cls.__module__ == "tkcurses.ttk":
        return set(options)
    return set(options) & set(public())


def options_page_samples() -> set[str]:
    """The options the options page has a sample for: each is a heading
    ``### name`` with a ``{tkcurses-sample}`` block before the next one."""
    if not OPTIONS_PAGE.exists():
        return set()
    sampled = set()
    for block in re.split(r"^### ", OPTIONS_PAGE.read_text(), flags=re.M)[1:]:
        names = block.split("\n", 1)[0].replace("`", "").split(",")
        if "```{tkcurses-sample}" in block:
            sampled.update(name.strip() for name in names)
    return sampled


def _check_options(found: dict[str, set[str]]) -> None:
    """Every option of every widget is measured, described in its class's
    docstring, and - where it changes the drawing - sampled. A themed
    widget's options are the ones Tk's has; one TkCurses lacks is measured
    as ``missing`` and has to be described all the same."""
    import tkcurses
    from tkcurses import ttk

    measured = json.loads(VISIBLE.read_text())
    tk_ttk = json.loads(TK_TTK_OPTIONS.read_text())
    on_page = options_page_samples()
    for name, options in measured.items():
        themed = name.startswith("ttk.")
        cls = getattr(ttk, name[4:]) if themed else getattr(tkcurses, name)
        shared = COMMON_OPTIONS | THEMED_OPTIONS if themed else COMMON_OPTIONS
        key = class_key(cls)
        doc = inspect.getdoc(cls) or ""
        named = {
            name for names in NAMED_SAMPLE.findall(doc) for name in names.split(", ")
        }
        actual = set(tk_ttk[name[4:]]) if themed else widget_options(cls)
        for option in sorted(actual ^ set(options)):
            found["unmeasured_options"].add(f"{key}:{option}")
        for option, entry in options.items():
            if not re.search(rf"\b{re.escape(option)}\b", doc):
                found["undescribed_options"].add(f"{key}:{option}")
            # Unsettled is an option whose screens would not hold still
            # long enough to compare: assume it shows.
            if entry["kind"] not in ("visible", "unsettled"):
                continue
            sampled = option in on_page if option in shared else option in named
            if not sampled:
                found["unsampled_options"].add(f"{key}:{option}")


def widget_classes() -> list[type]:
    """The widgets tkinter has, as TkCurses provides them: everything that
    draws, and so everything that has a sample to show."""
    import tkcurses

    return [
        cls
        for cls in class_counterparts()
        if issubclass(cls, tkcurses.Widget) and cls is not tkcurses.Widget
    ]


def class_key(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def section(doc: str, marker: str) -> str | None:
    """The text of the section headed ``marker``, or None if there is none.

    Napoleon's shape: the header on its own line, then the body indented
    under it, up to the next line at the header's indentation or less.
    """
    lines = doc.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == marker:
            indent = len(line) - len(line.lstrip())
            body = []
            for following in lines[index + 1 :]:
                if (
                    following.strip()
                    and len(following) - len(following.lstrip()) <= indent
                ):
                    break
                body.append(following)
            return "\n".join(body)
    return None


def violations() -> dict[str, set[str]]:
    """Every breach of the convention, by rule."""
    found: dict[str, set[str]] = {
        "undocumented": set(),
        "tracker_ids": set(),
        "private_names": set(),
        "unmarked_extensions": set(),
        "unlisted_borrowed": set(),
        "no_sample": set(),
        "unmeasured_options": set(),
        "unsampled_options": set(),
        "undescribed_options": set(),
    }
    texts = [
        (item.key, inspect.getdoc(item.obj) or "")
        for item in (*tkinter_surface(), *extensions(), *extension_module_members())
    ]
    for key, doc in texts:
        if not doc.strip():
            found["undocumented"].add(key)
    for key, doc in [*texts, *documented_data()]:
        if TRACKER_ID.search(doc):
            found["tracker_ids"].add(key)
        if PRIVATE_NAME.search(doc):
            found["private_names"].add(key)
    for item in extensions():
        doc = inspect.getdoc(item.obj) or ""
        if section(doc, EXTENSION_MARKER) is None:
            found["unmarked_extensions"].add(item.key)
    counterpart = dict(COUNTERPARTS)
    data = dict(documented_data())
    for key in reference_data():
        module, attr = key.rsplit(".", 1)
        if module in EXTENSION_MODULES or module not in counterpart:
            continue
        if hasattr(_module(counterpart[module]), attr):
            continue
        if section(data.get(key, ""), EXTENSION_MARKER) is None:
            found["unmarked_extensions"].add(key)
    for name in EXTENSION_MODULES:
        doc = inspect.getdoc(_module(name)) or ""
        if section(doc, EXTENSION_MARKER) is None:
            found["unmarked_extensions"].add(name)
    for cls in widget_classes():
        if section(inspect.getdoc(cls) or "", SAMPLE_MARKER) is None:
            found["no_sample"].add(class_key(cls))
    _check_options(found)
    for cls, names in borrowed_methods().items():
        listed = section(inspect.getdoc(cls) or "", DIFFERENCES_MARKER) or ""
        for name in names:
            if not re.search(rf"\b{re.escape(name)}\b", listed):
                found["unlisted_borrowed"].add(f"{class_key(cls)}.{name}")
    return found


def write_debt() -> None:
    found = violations()
    DEBT.write_text(
        json.dumps({rule: sorted(keys) for rule, keys in found.items()}, indent=2)
        + "\n"
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        write_debt()
    for rule, keys in violations().items():
        print(f"{rule}: {len(keys)}")
        for key in sorted(keys):
            print(f"    {key}")
