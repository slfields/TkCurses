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

import tkinter
import tkinter.constants
import tkinter.ttk

import pytest

import tkcurses
import tkcurses.constants
import tkcurses.ttk


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


# --------------------------------------------------------------- ttk
#
# The same comparison for tkinter.ttk, which nothing made: its __all__ had
# nine names while the module had twenty-three of tkinter.ttk's twenty-five,
# so ``from tkcurses.ttk import *`` gave a program written for tkinter.ttk a
# NameError on Button, Entry, Frame, Notebook... TkCurses-2q6o.9.


def tkinter_ttk_names() -> list[str]:
    return sorted(tkinter.ttk.__all__)


def test_the_fixture_finds_ttks_names():
    assert len(tkinter_ttk_names()) > 20


@pytest.mark.parametrize("name", tkinter_ttk_names())
def test_every_tkinter_ttk_name_is_exported_by_a_star_import(name):
    assert hasattr(tkcurses.ttk, name), f"tkcurses.ttk has no {name}"
    assert name in tkcurses.ttk.__all__, f"{name} is bound but not in __all__"


def test_everything_in_ttks_all_exists():
    """A name in __all__ that is not bound breaks the star-import outright."""
    missing = [n for n in tkcurses.ttk.__all__ if not hasattr(tkcurses.ttk, n)]
    assert not missing


def test_a_star_import_gives_a_working_button():
    scope: dict[str, object] = {}
    exec("from tkcurses.ttk import *", scope)
    assert scope["Button"] is tkcurses.ttk.Button
    assert scope["Notebook"] is tkcurses.ttk.Notebook


@pytest.mark.parametrize(
    "values",
    [
        {"a": ("1", "2", "x")},
        {"a": ()},
        {"a": ["7", 8]},
        {"a": "1 2"},
        {"a": 5, "b": ""},
        {"a": (3.5, "b")},
    ],
)
def test_tclobjs_to_py_does_to_python_values_what_tkinters_does(values):
    """Nothing here is a Tcl object, so this is all of tkinter's conversion
    that can apply - checked against tkinter.ttk's own function."""
    assert tkcurses.ttk.tclobjs_to_py(dict(values)) == tkinter.ttk.tclobjs_to_py(
        dict(values)
    )


def test_setup_master_returns_a_master_it_is_given():
    sentinel = object()
    assert tkcurses.ttk.setup_master(sentinel) is sentinel  # type: ignore[arg-type]


def test_setup_master_without_a_root_refuses_rather_than_creating_one(monkeypatch):
    monkeypatch.setattr(tkcurses, "_default_root", None)
    with pytest.raises(tkcurses.TclError, match="No root window"):
        tkcurses.ttk.setup_master()


def test_setup_master_without_a_master_is_the_default_root(monkeypatch):
    root = object()
    monkeypatch.setattr(tkcurses, "_default_root", root)
    monkeypatch.setattr(tkcurses, "_support_default_root", True)
    assert tkcurses.ttk.setup_master() is root


# ------------------------------------------------- module-level names
#
# tkinter.__all__ itself, apart from the two that are Tcl's machinery: Tcl()
# is an interpreter without Tk and CallWrapper wraps Python callables for
# one, and there is no interpreter here for either to talk to.
# TkCurses-2q6o.10.

NOT_PROVIDED = {"Tcl", "CallWrapper"}


def tkinter_module_names() -> list[str]:
    return sorted(set(tkinter.__all__) - NOT_PROVIDED)


def test_the_fixture_finds_tkinters_names():
    assert len(tkinter_module_names()) > 120
    assert set(tkinter.__all__) >= NOT_PROVIDED, "an exclusion tkinter dropped"


@pytest.mark.parametrize("name", tkinter_module_names())
def test_every_tkinter_name_is_exported_by_a_star_import(name):
    assert hasattr(tkcurses, name), f"tkcurses has no {name}"
    assert name in tkcurses.__all__, f"{name} is bound but not in __all__"


def test_everything_in_tkcurses_all_exists():
    missing = [n for n in tkcurses.__all__ if not hasattr(tkcurses, n)]
    assert not missing


@pytest.mark.parametrize("name", ["READABLE", "WRITABLE", "EXCEPTION"])
def test_the_file_handler_masks_are_tkinters(name):
    assert getattr(tkcurses, name) == getattr(tkinter, name)


def test_the_versions_are_the_tk_this_is_measured_against():
    """Floats, as tkinter's are, so a ``TkVersion >= 8.6`` check passes."""
    assert tkcurses.TkVersion == 9.0
    assert tkcurses.TclVersion == 9.0
    assert isinstance(tkcurses.TkVersion, float)


def test_getint_and_getdouble_are_the_builtins_tkinters_are():
    assert tkcurses.getint is tkinter.getint is int
    assert tkcurses.getdouble is tkinter.getdouble is float


@pytest.fixture
def default_root(monkeypatch):
    root = tkcurses.Misc()
    monkeypatch.setattr(tkcurses, "_default_root", root)
    monkeypatch.setattr(tkcurses, "_support_default_root", True)
    return root


@pytest.mark.parametrize(
    ("text", "expected"), [("yes", True), ("off", False), ("1", True), ("FALSE", False)]
)
def test_getboolean_parses_as_tcl_does(default_root, text, expected):
    assert tkcurses.getboolean(text) is expected


def test_getboolean_refuses_with_the_error_tkinters_function_raises(default_root):
    """The method raises TclError; tkinter's function turns it into this."""
    with pytest.raises(ValueError, match=r"^invalid literal for getboolean\(\)$"):
        tkcurses.getboolean("maybe")


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("getboolean", ("1",)),
        ("mainloop", ()),
        ("image_names", ()),
        ("image_types", ()),
    ],
)
def test_the_functions_need_a_root_as_tkinters_do(monkeypatch, name, args):
    monkeypatch.setattr(tkcurses, "_default_root", None)
    with pytest.raises(tkcurses.TclError, match="No root window"):
        getattr(tkcurses, name)(*args)


def test_image_names_and_types_are_the_default_roots(default_root):
    image = tkcurses.PhotoImage(master=default_root, width=1, height=1)
    assert tkcurses.image_names() == default_root.image_names()
    assert str(image) in tkcurses.image_names()
    assert tkcurses.image_types() == ("photo", "bitmap")


def test_mainloop_runs_the_default_roots_loop(monkeypatch):
    class Root:
        def mainloop(self, n=0):
            ran.append(n)

    ran: list[int] = []
    monkeypatch.setattr(tkcurses, "_default_root", Root())
    tkcurses.mainloop()
    tkcurses.mainloop(3)
    assert ran == [0, 3]


# ------------------------------------------------------------ EventType


def test_eventtype_has_tkinters_members_and_values():
    theirs = {
        name: member.value for name, member in tkinter.EventType.__members__.items()
    }
    ours = {
        name: member.value for name, member in tkcurses.EventType.__members__.items()
    }
    assert ours == theirs


@pytest.mark.parametrize("member", list(tkinter.EventType))
def test_eventtype_reads_as_tkinters_does(member):
    """str() and format() are the number, and it equals its own string."""
    ours = tkcurses.EventType[member.name]
    assert str(ours) == str(member)
    assert f"{ours}" == f"{member}"
    assert ours == member.value
    assert repr(ours) == repr(member)


def generated(widget, sequence, **kw):
    seen = []
    widget.bind(sequence, seen.append)
    widget.event_generate(sequence, **kw)
    (event,) = seen
    return event


@pytest.mark.parametrize(
    ("sequence", "expected"),
    [
        ("<Key>", "KeyPress"),
        ("<KeyPress-a>", "KeyPress"),
        ("<Button-1>", "ButtonPress"),
        ("<ButtonRelease-1>", "ButtonRelease"),
        ("<Motion>", "Motion"),
        ("<Configure>", "Configure"),
        ("<FocusIn>", "FocusIn"),
        ("<<Custom>>", "VirtualEvent"),
    ],
)
def test_a_generated_events_type_is_tkinters(sequence, expected):
    """Measured with tkinter on Tk 9.0.2: event_generate of each of these
    hands the binding an EventType - KeyPress for <Key>, VirtualEvent for
    <<Custom>> - so ``event.type == EventType.KeyPress`` holds."""
    frame = tkcurses.Frame(tkcurses.Misc())
    event = (
        generated(frame, sequence, keysym="a")
        if "Key" in sequence
        else (generated(frame, sequence))
    )
    assert event.type is tkcurses.EventType[expected]
    assert event.type == tkinter.EventType[expected]


def test_a_keys_repr_names_its_type_as_tkinters_does():
    frame = tkcurses.Frame(tkcurses.Misc())
    assert repr(generated(frame, "<Key>", keysym="a")).startswith("<KeyPress event ")


@pytest.mark.parametrize(
    ("core", "expected"),
    [
        ("key", "KeyPress"),
        ("pressed", "ButtonPress"),
        ("double", "ButtonPress"),
        ("released", "ButtonRelease"),
        ("drag", "Motion"),
        ("resize", "Configure"),
    ],
)
def test_real_input_has_tkinters_types(core, expected):
    """What the terminal reports, not only what event_generate makes."""
    from tkcurses._core.events import KeyEvent, MouseEvent, ResizeEvent

    widget = tkcurses.Frame(tkcurses.Misc())
    if core == "key":
        raw = KeyEvent(keysym="a", char="a")
    elif core == "resize":
        raw = ResizeEvent(width=3, height=4)
    else:
        raw = MouseEvent(state=core, button=1)
    assert tkcurses.Event._from_core(raw, widget).type is tkcurses.EventType[expected]


# ------------------------------------------------- TkCurses' own version

#: Every shape setuptools-scm writes, in the order PEP 440 sorts them.
VERSIONS_IN_ORDER = [
    ("0+unknown", (0, 0, 0, "alpha", 0)),
    ("0.2.9", (0, 2, 9, "final", 0)),
    ("0.3.0rc1.dev3+g1a2b3c4", (0, 3, 0, "candidate", 0)),
    ("0.3.0rc1", (0, 3, 0, "candidate", 1)),
    ("0.3.0rc2.dev2+ge7c8fdbfd.d20261105", (0, 3, 0, "candidate", 1)),
    ("0.3.0rc2", (0, 3, 0, "candidate", 2)),
    ("0.3.0", (0, 3, 0, "final", 0)),
    ("0.3.1.dev5+g1a2b3c4", (0, 3, 1, "alpha", 0)),
    ("0.3.1a1", (0, 3, 1, "alpha", 1)),
    ("0.3.1b2", (0, 3, 1, "beta", 2)),
    ("0.3.1", (0, 3, 1, "final", 0)),
    ("0.4", (0, 4, 0, "final", 0)),
    ("1.0.0.post1", (1, 0, 0, "final", 0)),
]


@pytest.mark.parametrize(("version", "expected"), VERSIONS_IN_ORDER)
def test_a_version_reads_as_its_parts(version, expected):
    assert tuple(tkcurses._version_info(version)) == expected


def test_versions_compare_in_release_order():
    """Each compares no lower than the one before: the order a program
    checking ``version_info >= (0, 3)`` relies on."""
    infos = [tkcurses._version_info(version) for version, _ in VERSIONS_IN_ORDER]
    assert infos == sorted(infos)


def test_the_installed_version_is_described_both_ways():
    info = tkcurses.version_info
    assert info == tkcurses._version_info(tkcurses.__version__)
    assert info._fields == ("major", "minor", "micro", "releaselevel", "serial")
    assert info._fields == tkcurses.Misc().info_patchlevel()._fields
    assert info >= (0, 3)
    assert "version_info" in tkcurses.__all__
