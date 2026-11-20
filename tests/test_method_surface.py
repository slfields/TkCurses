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

"""Every widget's METHODS, against the real tkinter beside it.

The option surface has had this since TkCurses-ale -
``tests/test_ttk_option_surface.py`` - and it is how ``-exportselection``,
``-placeholder`` and the Progressbar label options were all caught. Methods had
nothing. A missing method was invisible to the suite, and that is not a
hypothetical: ARCHITECTURE.md marked the whole ``ttk.Treeview`` identify family
as implemented while ``hasattr`` was False for every one of the six, and the
document was the only place anyone would have looked. TkCurses-hv9.

So this file does two things with one comparison.

**One: our classes against tkinter's.** A method tkinter has and we lack breaks
programs - ``spin.set(5)`` is how every ttk program assigns a spinbox value and
it raised AttributeError here. Those live in :data:`GAPS`, each against the
issue that will close it, 184 of them when the list was first taken.

**Two: the same comparison pointed at ARCHITECTURE.md.** Its API tables carry
621 claims of implementation and nothing had ever checked one. 51 were false.

THREE TRAPS, each of which produced a wrong number before it was understood.

*bbox is grid_bbox.* Measured: ``tkinter.Misc.bbox is tkinter.Misc.grid_bbox``
is True and ``__name__`` is ``'grid_bbox'``. A naive sweep reports 38 widgets
"missing bbox" when it is one inherited geometry method counted 38 times. This
is why :data:`GAPS` is keyed by the class that DEFINES a method rather than by
the widget that inherits it - the entry appears once, where tkinter puts it.
``tk.Spinbox.bbox`` and ``ttk.Entry.bbox`` are a different method entirely, the
box of one character, and are listed separately under those classes.

*identify means two things.* ``ttk.Widget.identify(x, y)`` answers a style
ELEMENT name; the domain form - 'slider', 'sash', 'buttonup' - is the CLASSIC
Scale, Scrollbar, Spinbox and PanedWindow's. A sweep that conflates them reports
17 false gaps, and it hid something worse: the ttk versions of those four
answered the classic form, wrongly, and passed this check because the method
existed. A method being present says nothing about its answers. Both were
settled in TkCurses-d5u.

*tk.Entry and ttk.Entry are both named "Entry".* Grouping by
``__qualname__.split('.')[0]`` merges them, and it did: the first run of this
comparison attributed ``validate`` to ``tk.Entry``, which has no such method -
it is ``ttk.Entry``'s. Every key here is module-qualified for that reason.

WHY THE BASE CLASSES ARE EXCLUDED, rather than quietly passing. ``tk.Misc``,
``tk.Wm``, the three geometry-manager mixins and ``ttk.Widget`` are not
instantiated by programs, and our ``ttk.Widget`` is deliberately a mixin that
does not extend ``Misc`` - so comparing it to ttk's reports 170 "missing"
methods that every real themed widget of ours has. See
:func:`test_the_excluded_classes_are_only_the_ones_programs_never_instantiate`,
which pins the exclusion list so it cannot grow to hide a real gap.

WHY NO WIDGET IS INSTANTIATED: methods are class attributes, so ``hasattr`` on
the class answers the question. The option surface has to build a widget to ask
``configure()``; this does not, which makes it immune to the fixture problem
recorded in ``test_ttk_option_surface.py`` - no display, no root, nothing to
skip for.

VERSION SKEW IS REAL, AND IT BROKE THIS FILE ON THREE OF THE FIVE PYTHONS.
tkinter's own method surface grew in 3.13: the ``busy_*`` family,
``info_patchlevel``, ``after_info``, ``PhotoImage.copy_replace``. CI ran
3.10-3.14, so on the older runners **tkinter has less**, and eighteen entries
in :data:`GAPS` name methods that tkinter does not have there either.

The direction that matters - we lack something tkinter has - is computed
against the running interpreter and was always correct. It was the guards
*about the table* that went wrong: nothing of ours can resolve an owner for a
method that does not exist, so those eighteen entries covered no class and
looked like dead weight. 3.10, 3.11 and 3.12 failed; 3.13 and 3.14 passed.
See :func:`_some_compared_class_has`, which excuses exactly that case rather
than skipping the check on three runners out of five.

**Verify a fix here against an older tkinter, not against this one.** Deleting
the 3.13 additions from ``tkinter.Misc`` and ``tkinter.PhotoImage`` in a probe
reproduces the condition, and the version-gated test has to be deselected to
match what a real 3.11 or 3.12 runs - the probe can strip the library but cannot lower
``sys.version_info``.
"""

from __future__ import annotations

import functools
import inspect
import re
import sys
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("tkinter", reason="the comparison needs real tkinter")

import tkinter
import tkinter.ttk

import tkcurses
import tkcurses.curses
import tkcurses.panel
import tkcurses.ttk

#: Classes no program instantiates: tkinter's own mixins and base classes.
#:
#: Excluded rather than listed as gaps because the comparison is meaningless for
#: them. The load-bearing one is ``ttk.Widget``: ours is a mixin that does not
#: extend ``Misc``, by design, so ttk's ``Widget`` appears to have 170 methods
#: we lack - every one of which our real themed widgets DO have, from the other
#: side of their inheritance. Measured, 2026-10-03.
NOT_INSTANTIATED = frozenset(
    {"Misc", "Widget", "BaseWidget", "Pack", "Place", "Grid", "Wm", "XView", "YView"}
)


#: Methods real tkinter has that we do not, each against the issue that owns it.
#:
#: KEYED BY THE CLASS THAT DEFINES THE METHOD, module-qualified - and resolved
#: through each widget's own MRO, never by name alone. That is not tidiness, it
#: is the only sound key, and three separate wrong numbers came out of getting
#: it wrong:
#:
#: * Keyed by the widget that INHERITS a method, ``tk.Misc.busy_hold`` would be
#:   42 entries saying one thing. The first run of this measurement reported
#:   1518 "missing methods" that way - absurd enough to be worth keeping as a
#:   warning.
#: * Keyed by method NAME, two unrelated methods merge. Measured across the
#:   widget set, 54 names have more than one defining class: ``bbox`` has
#:   seven, ``identify`` eight, ``get`` thirteen. ``tk.Spinbox.bbox`` (the box
#:   of one character) and ``tk.Misc.bbox`` (which IS ``grid_bbox``) are
#:   different methods that a name-keyed table cannot tell apart.
#: * Keyed by a method's defining class looked up GLOBALLY rather than per
#:   widget, ``ttk.Spinbox.set`` files itself under ``tk.Scale``, because Scale
#:   is simply the first class in the sweep that happens to define a ``set``.
#:
#: So an entry here covers exactly those of our classes whose real counterpart
#: resolves that method to that class, and nothing else. See
#: :func:`_covered_by`.
#:
#: 150 entries over 20 defining classes on 2026-10-03, the day the list was
#: first taken, with 34 more in :data:`PARTIAL_GAPS`. Filed as:
#:
#:   TkCurses-019  xview_moveto / xview_scroll / yview_* - the scroll protocol
#:   TkCurses-elb  ttk.Spinbox.set
#:   TkCurses-52q  ttk.Entry.validate and bbox
#:   TkCurses-67u  the ttk.Treeview tag API
#:   TkCurses-d5u  the themed-element identify
#:   TkCurses-6lh  scan_mark / scan_dragto
#:   TkCurses-k1i  the tk.Wm icon, group and aspect family
#:   TkCurses-0ap  tk.Misc busy, visual and screen introspection
#:   TkCurses-zmf  the geometry-manager method aliases (bbox, anchor, size,
#:                 location) - one assignment each in tkinter, and note that
#:                 whoever closes it should assert IDENTITY, since tkinter's
#:                 own ``Misc.bbox is Misc.grid_bbox``
#:   TkCurses-xy2  tk.PanedWindow proxy and sash
#:   TkCurses-5kg  Listbox.itemconfigure and the Spinbox selection family
#:   TkCurses-5rt  five single-method gaps
#:   TkCurses-aj1.16.1  the Canvas item types that were already owned
#:
#: It shrank by four on 2026-10-03 (TkCurses-67u): the ttk.Treeview tag API -
#: tag_configure, tag_bind, tag_has - and set_children. This list's first
#: shrink, and it was this test that demanded it: the four were implemented,
#: test_every_listed_gap_is_still_missing failed naming all four, and the
#: entries came out. That is the whole arrangement working as intended.
#:
#: And by one more the same day (TkCurses-elb): ttk.Spinbox.set.
#: PARTIAL_GAPS lost every scroll-protocol entry to TkCurses-019.
#:
#: And by four on 2026-11-01 (TkCurses-5rt): PhotoImage.copy_replace,
#: Scrollbar.activate, Tk.loadtk and readprofile, Variable.trace. The fifth
#: it named, Menu.xposition, had gone with TkCurses-aj1.13.1.
#:
#: A gap not listed here is a test failure, which is the point: this list may
#: shrink and must never silently grow.
#:
#: On 2026-11-13 it lost TkCurses-zmf's aliases, TkCurses-k1i's Wm hints and
#: all of TkCurses-0ap: the busy family, the screen and visual questions,
#: atoms, send, register, info_patchlevel and the palette; and with
#: Listbox.scan_mark and scan_dragto, the last of TkCurses-6lh.
GAPS: dict[str, dict[str, str]] = {
    "tk.Canvas": {},
    "tk.Listbox": {},
    "tk.Misc": {},
    "tk.PanedWindow": {},
    "tk.Wm": {},
}

#: The six methods some of our classes have and others do not, by OUR class.
#:
#: Keyed differently from :data:`GAPS` for a measured reason. Both of these are
#: defined once in tkinter, on a mixin, and inherited widely:
#:
#:   tk.XView.xview         our Canvas, Entry, Text and Treeview had it;
#:                          our Listbox did not (until TkCurses-019)
#:   ttk.Widget.identify    our Scale, Scrollbar and PanedWindow answered
#:                          (the classic domain form); the rest had nothing
#:                          (until TkCurses-d5u)
#:
#: So a single entry under the defining class would be false as stated - it
#: would say the method is missing from everything that inherits it, and the
#: staleness check would rightly reject it. Six names were in this position,
#: all of them the scroll protocol (TkCurses-019) and identify (TkCurses-d5u),
#: which is not a coincidence: those are exactly the two issues whose subject
#: is a method implemented on some widgets and not others. The scroll
#: protocol's five came out with TkCurses-019, which put them on public
#: XView / YView mixins as tkinter does, and identify with TkCurses-d5u, which
#: put it on ttk.Widget. Empty now, and kept for the next method in that
#: position.
PARTIAL_GAPS: dict[str, dict[str, str]] = {}


def _qualified(cls: type) -> str:
    """``tk.Entry`` or ``ttk.Entry`` - never the bare name.

    The two are different classes with different methods, and merging them
    under one label is how ``validate`` was first attributed to ``tk.Entry``,
    which has no such method. It is ``ttk.Entry``'s.
    """
    return ("ttk." if cls.__module__.endswith("ttk") else "tk.") + cls.__name__


@functools.cache
def _methods(cls: type) -> dict[str, type]:
    """Public methods of ``cls``, each mapped to the class that DEFINES it.

    Cached because the checks below ask the same question of the same class
    hundreds of times - 184 gap entries against 42 class pairs - and walking
    ``dir()`` plus the MRO each time took the file from under a second to ten.

    ``getattr_static`` rather than ``getattr`` so a descriptor is inspected
    rather than invoked. Properties are dropped: they are state, not API
    surface, and ``configure``/``cget`` already cover options.
    """
    found: dict[str, type] = {}
    for name in dir(cls):
        if name.startswith("_"):
            continue
        try:
            value = inspect.getattr_static(cls, name)
        except AttributeError:  # pragma: no cover - a descriptor that refuses
            continue
        if isinstance(value, property):
            continue
        if not callable(value) and not isinstance(value, (staticmethod, classmethod)):
            continue
        found[name] = next((c for c in cls.__mro__ if name in vars(c)), cls)
    return found


def _pairs() -> list[tuple[str, type, type]]:
    """Every class of ours that mirrors one of tkinter's, by name.

    Discovered rather than listed, so a widget added to the library is compared
    the day it lands instead of the day somebody remembers to extend a tuple.
    """
    pairs: list[tuple[str, type, type]] = []
    for prefix, ours_module, their_module in (
        ("tk", tkcurses, tkinter),
        ("ttk", tkcurses.ttk, tkinter.ttk),
    ):
        for name in dir(ours_module):
            if name in NOT_INSTANTIATED or name.startswith("_"):
                continue
            ours = getattr(ours_module, name)
            theirs = getattr(their_module, name, None)
            if inspect.isclass(ours) and inspect.isclass(theirs):
                pairs.append((f"{prefix}.{name}", ours, theirs))
    return pairs


PAIRS = _pairs()
LABELS = [label for label, _, _ in PAIRS]


def _covered_by(owner: str, method: str) -> list[tuple[str, type]]:
    """Our classes that a single :data:`GAPS` entry speaks for.

    A class is covered when its real counterpart resolves ``method`` to
    ``owner`` - not merely when ``owner`` appears somewhere in its ancestry.
    The difference is the whole soundness of the table: ``tk.Canvas`` inherits
    from ``tk.Misc``, so an MRO-membership test would let the ``tk.Misc.bbox``
    entry excuse Canvas's own missing ``bbox`` - a different method, with its
    own issue.
    """
    covered = []
    for label, ours, theirs in PAIRS:
        defines = _methods(theirs).get(method)
        if defines is not None and _qualified(defines) == owner:
            covered.append((label, ours))
    return covered


def _is_owned(label: str, name: str, owner: str) -> bool:
    """Whether some issue already owns this class lacking this method."""
    return name in GAPS.get(owner, {}) or name in PARTIAL_GAPS.get(label, {})


def test_the_comparison_found_some_classes_to_compare() -> None:
    """The guard that stops every other test here passing vacuously.

    :func:`_pairs` discovers by name. A rename in either library, or an import
    that quietly fails, would leave it empty and every parametrised test below
    would then pass by having nothing to check.
    """
    assert len(PAIRS) > 40, f"only found {len(PAIRS)} class pairs: {LABELS}"
    assert "tk.Entry" in LABELS
    assert "ttk.Treeview" in LABELS


@pytest.mark.parametrize("label", LABELS)
def test_no_widget_lacks_a_method_its_tkinter_counterpart_has(label: str) -> None:
    """The direction that breaks programs.

    ``spin.set(5)`` is how every ttk program assigns a spinbox value, and it
    raised AttributeError here until TkCurses-elb was filed.

    Computed against the running interpreter's tkinter, so it is correct on
    every Python CI runs regardless of which methods that version added.
    """
    ours, theirs = next((o, t) for lab, o, t in PAIRS if lab == label)
    unexplained = [
        f"{name} (tkinter defines it on {_qualified(owner)})"
        for name, owner in _methods(theirs).items()
        if not hasattr(ours, name) and not _is_owned(label, name, _qualified(owner))
    ]
    assert not unexplained, (
        f"{label} lacks methods real tkinter has and nothing owns: "
        f"{sorted(unexplained)}. Implement them, or list them against an "
        f"issue - in GAPS under the class that DEFINES each one when every "
        f"widget inheriting it lacks it, in PARTIAL_GAPS under {label} when "
        f"some of our widgets have it already."
    )


@pytest.mark.parametrize("label", LABELS)
def test_a_method_we_do_have_is_actually_callable(label: str) -> None:
    """Present under the right name is not the same as usable.

    The option surface learned this the expensive way: ``ttk.Combobox``
    DECLARED ``-exportselection`` and nothing acted on it, so the comparison
    passed for Combobox while the option did nothing (TkCurses-163). A name
    bound to a non-callable would hide here the same way.
    """
    ours, theirs = next((o, t) for lab, o, t in PAIRS if lab == label)
    broken = [
        name
        for name in _methods(theirs)
        if hasattr(ours, name)
        and not callable(getattr(ours, name))
        and not isinstance(
            inspect.getattr_static(ours, name, None),
            (property, staticmethod, classmethod),
        )
    ]
    assert not broken, f"{label}: present but not callable: {broken}"


def test_every_listed_gap_is_still_missing() -> None:
    """So the list shrinks when something is implemented, rather than going stale.

    The same idea as ``xfail(strict=True)``: a gap that has quietly been closed
    should say so, not sit in a list implying work remains.
    """
    closed = [
        f"GAPS[{owner!r}][{method!r}] (present on {label})"
        for owner, methods in GAPS.items()
        for method in methods
        for label, ours in _covered_by(owner, method)
        if hasattr(ours, method)
    ]
    closed += [
        f"PARTIAL_GAPS[{label!r}][{method!r}]"
        for label, methods in PARTIAL_GAPS.items()
        for method in methods
        if hasattr(next(o for lab, o, _ in PAIRS if lab == label), method)
    ]
    assert not closed, (
        f"listed as a gap but implemented now - remove the entries: {sorted(closed)}"
    )


def _some_compared_class_has(method: str) -> bool:
    """Whether this method name exists anywhere in the surface being compared.

    THE VERSION TRAP. tkinter's own method surface grew in 3.13 - the
    ``busy_*`` family, ``info_patchlevel``, ``PhotoImage.copy_replace`` - so on
    3.11 and 3.12 eighteen entries in :data:`GAPS` name methods tkinter does not have
    there. Nothing of ours can resolve an owner for a method that does not
    exist, so :func:`_covered_by` comes back empty and the entry looks dead
    when it is merely ahead of the interpreter.

    Asked through :func:`_methods`, deliberately, rather than through
    ``hasattr`` on the owner class. Both would excuse the eighteen; this one is
    answered by the same lens every other check in this file uses, so it cannot
    disagree with :func:`_covered_by` about what a class has. If tkinter lacks
    the method, no compared class has it and the entry is excused; if tkinter
    has it, some compared class resolves it and the entry is covered. Either
    way a version-added name cannot be reported, while a name every widget
    resolves elsewhere - ``tk.Misc.destroy``, shadowed by ``tk.BaseWidget`` -
    still is.
    """
    return any(method in _methods(theirs) for _, _, theirs in PAIRS)


def test_every_listed_gap_speaks_for_at_least_one_of_our_classes() -> None:
    """An entry covering nothing is dead weight that reads as outstanding work.

    It happens when a widget is renamed or dropped, or when an entry is filed
    under a defining class no widget of ours resolves to: the entry stays,
    nothing checks it, and the list grows a row that can never shrink.

    It also catches the reverse of the mistake :data:`PARTIAL_GAPS` exists for.
    A method listed in :data:`GAPS` that some of our classes DO implement is
    not covered by this check - :func:`test_every_listed_gap_is_still_missing`
    catches that one - but a method listed under a class nothing inherits from
    would otherwise be invisible.

    Version-added methods are excused rather than skipped - see
    :func:`_some_compared_class_has`. Skipping below 3.13 would retire a real
    guard on three runners out of five.
    """
    silent = [
        f"GAPS[{owner!r}][{method!r}]"
        for owner, methods in GAPS.items()
        for method in methods
        if _some_compared_class_has(method) and not _covered_by(owner, method)
    ]
    silent += [
        f"PARTIAL_GAPS[{label!r}]" for label in PARTIAL_GAPS if label not in LABELS
    ]
    assert not silent, f"gap entries that speak for no class of ours: {silent}"


@pytest.mark.skipif(
    sys.version_info < (3, 13),
    reason="tkinter's own method surface grew in 3.13 (the busy_* family, "
    "after_info, PhotoImage.copy_replace), so on an older runner a name absent "
    "from tkinter is not evidence the entry is stale; this check runs where "
    "the surface is widest",
)
def test_every_listed_gap_names_a_method_tkinter_actually_has() -> None:
    """Catches an invented entry, which no other direction can.

    A gap listed for a method that exists nowhere would never fail the
    comparison: nothing reports it missing, because tkinter does not have it
    either. ARCHITECTURE.md carried exactly that - ``Text.search_all``, marked
    "direct implementation", present in neither library.
    """
    invented = []
    for table in (GAPS, PARTIAL_GAPS):
        for owner, methods in table.items():
            module = tkinter.ttk if owner.startswith("ttk.") else tkinter
            real = getattr(module, owner.split(".", 1)[1], None)
            if real is None:
                invented.append(f"{owner} (no such class in tkinter)")
                continue
            invented.extend(
                f"{owner}.{method}" for method in methods if not hasattr(real, method)
            )
    assert not invented, f"listed as a gap but tkinter has no such method: {invented}"


def test_the_excluded_classes_are_only_the_ones_programs_never_instantiate() -> None:
    """Pins :data:`NOT_INSTANTIATED` so it cannot grow to hide a real gap.

    Excluding a class removes it from every check above, which makes this the
    one list in the file that has to be argued for rather than extended. Each
    name is a tkinter mixin or abstract base: a program writes
    ``tkinter.Entry()``, never ``tkinter.Misc()`` or ``tkinter.XView()``.
    """
    for name in NOT_INSTANTIATED:
        real = getattr(tkinter, name, None) or getattr(tkinter.ttk, name)
        assert inspect.isclass(real), name
    # Nothing a program builds may be in here. Toplevel is the near miss worth
    # naming: it IS a Wm, and it is compared.
    for instantiated in ("Entry", "Frame", "Toplevel", "Tk", "Canvas", "Treeview"):
        assert instantiated not in NOT_INSTANTIATED
    assert "Widget" in NOT_INSTANTIATED, (
        "our ttk.Widget is a mixin that does not extend Misc, by design; "
        "comparing it to ttk's Widget reports 170 methods that every real "
        "themed widget of ours has from the other side of its inheritance"
    )


# --------------------------------------------------------------------------
# The same comparison, pointed at ARCHITECTURE.md.
#
# Its API tables carry over six hundred claims of implementation and nothing
# had ever checked one of them. 51 were false - including the whole ttk.Treeview
# identify family, marked "adapted implementation" while hasattr was False for
# all six. The document was the only place anyone would have looked, which is
# how that gap survived. TkCurses-hv9.
# --------------------------------------------------------------------------

ARCHITECTURE = Path(__file__).resolve().parent.parent / "ARCHITECTURE.md"

#: The document's own legend. The first three each assert the thing exists.
CLAIMS_IT_EXISTS = frozenset({"✓", "○", "◐"})

_HEADING = re.compile(r"^#{2,3} +(.*?)\s*$")
_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*([^|]*?)\s*\|")


class _Subject:
    """What a table's rows are claims about, and the names it can answer to.

    A set of names rather than an object, because a module's table mixes
    module-level functions with the methods of a class inside it - the
    ``simpledialog`` table lists both ``askinteger`` and ``body`` - and a claim
    there means "this name is part of that module's API", not "this exact
    object has that attribute".
    """

    def __init__(self, description: str, names: frozenset[str]) -> None:
        self.description = description
        self.names = names

    def has(self, name: str) -> bool:
        return name in self.names


def _of_class(cls: type) -> _Subject:
    return _Subject(cls.__qualname__, frozenset(dir(cls)))


def _of_module(module: Any) -> _Subject:
    """A module's own names, plus those of every public class in it."""
    names = set(dir(module))
    for attribute in vars(module).values():
        if inspect.isclass(attribute) and attribute.__module__ == module.__name__:
            names |= set(dir(attribute))
    return _Subject(module.__name__, frozenset(names))


#: Headings whose table is not about the class the heading names.
#:
#: Every one of these was a false positive until it was mapped, and together
#: they were 39 of an apparent 87 - my parser's fault, not the document's.
#: ``Geometry Managers`` tables ``pack()`` and ``grid()``, which live on widgets
#: and not on ``Misc``: measured, ``tkcurses.Misc.pack`` is False while
#: ``tkcurses.Frame.pack`` is True, so resolving that heading to ``Misc``
#: invents 13 false claims. The module headings table the methods of classes
#: INSIDE the module, which invented another 26.
_TABLES_ABOUT: dict[str, str] = {
    "Geometry Managers": "tkcurses.Frame",
    "Window Methods": "tkcurses.curses.Window",
    "Module Functions": "tkcurses.curses",
    "Panel Methods": "tkcurses.panel.Panel",
    "Panel Module": "tkcurses.panel",
    "commondialog.Dialog": "tkcurses.commondialog",
    "filedialog Module": "tkcurses.filedialog",
    "simpledialog Module": "tkcurses.simpledialog",
    "messagebox Module": "tkcurses.messagebox",
    "colorchooser Module": "tkcurses.colorchooser",
    "font Module": "tkcurses.font",
    "scrolledtext Module": "tkcurses.scrolledtext",
    "dnd Module": "tkcurses.dnd",
}

#: Headings with no API table under them: prose, a worked example, a constant
#: list. Listed so that a heading nobody has classified fails loudly in
#: :func:`test_every_heading_in_the_api_reference_is_accounted_for` rather than
#: having its rows silently skipped.
_NOT_A_TABLE = frozenset(
    {
        "Complete API Reference",
        "Legend",
        "Core Classes",
        "Widget Classes",
        "Variable Classes",
        "Image Classes",
        "TTK Widget Classes",
        "Dialog Modules",
        "Curses Compatibility Module",
        "Panel Module Overview",
        # BarGraph's design notes: it has no tkinter counterpart, and so
        # no table of tkinter methods to check.
        "BarGraph",
        "Its names, decided when it came in",
        "Pure modules, one widget module",
        "Drawing in eighths",
        "Colour",
        "Repainting",
        "Text is measured in cells",
        "How its options are measured",
        "Not yet",
        "The pixel",
        "What an option value is",
        "Image files",
        "Image colour and the pair ceiling",
        "compound",
        "Constants",
        "Running Both Halves",
    }
)


def _import(path: str) -> Any:
    """Resolve ``tkcurses.curses.Window`` to the object, importing as it walks."""
    import importlib

    parts = path.split(".")
    obj: Any = importlib.import_module(parts[0])
    for index, part in enumerate(parts[1:], start=1):
        try:
            obj = getattr(obj, part)
        except AttributeError:
            obj = importlib.import_module(".".join(parts[: index + 1]))
    return obj


def _subjects_of(heading: str) -> list[_Subject]:
    """Who a table's claims are about: empty when the heading is prose.

    A heading naming several classes - "StringVar, IntVar, DoubleVar,
    BooleanVar" - returns one subject each, so the claim must hold for all of
    them rather than for whichever happens to have the method.
    """
    if heading in _TABLES_ABOUT:
        found = _import(_TABLES_ABOUT[heading])
        return [_of_class(found) if inspect.isclass(found) else _of_module(found)]
    if heading in _NOT_A_TABLE:
        return []
    name = heading.removesuffix(" Class").removesuffix(" Base").strip()
    if name.startswith("ttk."):
        found = getattr(tkcurses.ttk, name[4:], None)
        return [_of_class(found)] if inspect.isclass(found) else []
    if "," in name:
        return [
            _of_class(getattr(tkcurses, part.strip()))
            for part in name.split(",")
            if isinstance(getattr(tkcurses, part.strip(), None), type)
        ]
    found = getattr(tkcurses, name, None)
    return [_of_class(found)] if inspect.isclass(found) else []


def _rows() -> list[tuple[str, _Subject, str, str, int]]:
    """Every API-table row: (heading, subject, name, symbol, line number).

    Rows whose first cell is not a name are skipped, and each skip is measured
    rather than guessed: ``file=`` is an option, and ``image["option"]`` is a
    subscript that splitting on ``(`` reads as a method called ``image`` -
    which it did, inventing a 52nd false claim that was the parser's fault.
    """
    text = ARCHITECTURE.read_text(encoding="utf-8").splitlines()
    start = next(
        index
        for index, line in enumerate(text)
        if line.startswith("## Complete API Reference")
    )
    rows: list[tuple[str, _Subject, str, str, int]] = []
    heading, subjects = "", []
    for number, line in enumerate(text[start:], start=start + 1):
        found = _HEADING.match(line)
        if found:
            heading = found.group(1)
            subjects = _subjects_of(heading)
            continue
        found = _ROW.match(line)
        if not found:
            continue
        signature, symbol = found.group(1).strip(), found.group(2).strip()
        if "[" in signature.split("(")[0]:  # image["option"], a subscript
            continue
        name = re.split(r"[( ]", signature)[0].lstrip("*")
        if not name.isidentifier():  # file=, **kw, a prose cell
            continue
        rows.extend((heading, subject, name, symbol, number) for subject in subjects)
    return rows


ROWS = _rows()


def test_the_architecture_audit_is_actually_reading_the_tables() -> None:
    """The guard, and the whole reason the audit below can be believed.

    An audit whose parser matches nothing passes perfectly. This one has had
    three parser faults already - a heading resolved to the wrong class, a
    module table read as a class, a subscript read as a method - and every one
    of them LOOKED like a finding. So pin the volume and some known headings:
    if the document is restructured, this fails and asks to be re-read rather
    than quietly checking less.
    """
    assert len(ROWS) > 550, f"only parsed {len(ROWS)} table rows"
    claims = [row for row in ROWS if row[3] in CLAIMS_IT_EXISTS]
    assert len(claims) > 500, f"only {len(claims)} rows claim an implementation"
    headings = {row[0] for row in ROWS}
    for expected in ("Misc Class", "ttk.Treeview", "Window Methods", "Canvas Class"):
        assert expected in headings, f"the {expected} table was not parsed"


def test_every_heading_in_the_api_reference_is_accounted_for() -> None:
    """A heading nobody classified has its rows skipped, and skipped is silent.

    This is the hole the audit would otherwise have: add a widget's table under
    a heading that does not resolve to a class, and none of its claims are
    checked - the exact shape of the failure the audit exists to catch.
    """
    text = ARCHITECTURE.read_text(encoding="utf-8").splitlines()
    start = next(
        index
        for index, line in enumerate(text)
        if line.startswith("## Complete API Reference")
    )
    unclassified = []
    for line in text[start:]:
        found = _HEADING.match(line)
        if (
            found
            and found.group(1) not in _NOT_A_TABLE
            and not _subjects_of(found.group(1))
        ):
            unclassified.append(found.group(1))
    assert not unclassified, (
        f"headings under the API reference that resolve to nothing, so their "
        f"claims go unchecked: {unclassified}. Map each one in _TABLES_ABOUT, "
        f"or declare it prose in _NOT_A_TABLE."
    )


def test_no_table_claims_something_we_have_not_implemented() -> None:
    """ARCHITECTURE.md said the Treeview identify family was done. It was not.

    Six rows marked "adapted implementation", ``hasattr`` False for all six.
    51 rows were false when this test was written - the same failure mode as
    the code graph that sat 165 commits stale while still being offered as the
    way to navigate the library.
    """
    false_claims = [
        f"{ARCHITECTURE.name}:{number} claims {symbol} for {subject.description}.{name}"
        for _, subject, name, symbol, number in ROWS
        if symbol in CLAIMS_IT_EXISTS and not subject.has(name)
    ]
    assert not false_claims, (
        f"ARCHITECTURE.md asserts {len(false_claims)} things that do not "
        f"exist:\n" + "\n".join(false_claims)
    )


@pytest.mark.parametrize(
    "name",
    [
        "anchor", "bbox", "columnconfigure", "config", "configure", "forget",
        "info", "location", "propagate", "rowconfigure", "size", "slaves",
    ],
)  # fmt: skip
def test_a_bare_name_reaches_the_method_tkinters_does(name):
    """tkinter gives the geometry managers' methods bare names - bbox for
    grid_bbox, slaves for pack_slaves - and which manager a widget's bare
    name reaches follows its method order. Every one reaches the same
    method here, on the classes that define them and on a widget."""
    for cls in ("Misc", "Pack", "Grid", "Place", "Widget"):
        theirs = getattr(getattr(tkinter, cls), name, None)
        ours = getattr(getattr(tkcurses, cls), name, None)
        assert (ours is None) == (theirs is None), (cls, name)
        if theirs is not None:
            # By what tkinter's reaches, looked up here: grid_propagate and
            # pack_propagate are one method in TkCurses, one flag to a
            # container.
            # Like tkinter's own, the query methods all live on Misc.
            target = getattr(
                getattr(tkcurses, cls),
                theirs.__name__,
                getattr(tkcurses.Misc, theirs.__name__, None),
            )
            assert ours.__qualname__ == target.__qualname__, (cls, name)
