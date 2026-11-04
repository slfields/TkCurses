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
#
# Portions follow logic in the Tcl and Tk library scripts, each named beside
# the code that follows it. Tcl and Tk are copyright the Regents of the
# University of California, Sun Microsystems, Inc., Scriptics Corporation,
# ActiveState Corporation, Apple Inc. and other parties, and are used under
# the Tcl/Tk licence; see THIRD_PARTY_NOTICES.md.

"""Themed widgets, and the style database they draw from.

ttk is not a second set of widgets that happen to look different. It is the
same widgets with their appearance lifted out into a database that can be
changed from one place, and a state model - disabled, active, focus, pressed
- that the appearance is resolved against. This module is that database;
the widgets that consume it follow.

Every rule below was measured against real ttk on Tk 9.0 rather than
remembered, because two of them are not what they look like.

**A style name inherits through its dots.** ``Danger.TButton`` falls back to
``TButton`` for anything it does not set itself, and the walk goes all the
way: ``A.B.C.TDeep`` finds ``TDeep``. A widget with no ``style`` option of
its own uses its class name, which is why ``TButton`` is where a button
looks.

**Resolution is two passes, not one.** Every style in the chain is checked
for a matching ``map`` entry *first*, and only then does the chain get walked
again for a ``configure`` value. So a base style's ``map`` beats a derived
style's ``configure`` - measured, and the opposite of what an interleaved
walk would do.

**Map entries match in the order they were given**, first full match winning,
rather than most-specific-first. ``[("disabled", "focus", "both"),
("disabled", "plain")]`` answers ``both`` when both states are set and
``plain`` when only ``disabled`` is - because the first entry did not match,
not because the second was more specific.

A state spec is every element of an entry but the last, each one a state name
or a negated ``!name``; the last element is the value. An entry matches when
every element of its spec does.

**The themes are not tkinter's.** Real ttk offers ``clam``, ``alt``,
``default`` and ``classic``, which are about pixels: bevels, shading,
gradients. None of that means anything on a character grid, and what does
vary here is which glyphs a border is drawn with. So the themes are the six
in ARCHITECTURE.md - ``default``, ``ascii``, ``dos``, ``rounded``, ``double``
and ``minimal`` - and :meth:`Style.theme_names` answers with those. That is a
deliberate departure, recorded rather than hidden; ``default`` is in both
lists, so ``theme_use("default")`` means the same thing either way.
"""

from __future__ import annotations

import contextlib
import curses
import functools
import math
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, ClassVar, cast

import tkcurses
from tkcurses._core.attributes import BorderStyle, with_colors
from tkcurses._core.bindings import parse_sequence
from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses._core.errors import TclError
from tkcurses._core.geometry import BORDER_WIDTH, Insets, Point, Rect
from tkcurses._core.pack import parse_anchor
from tkcurses._core.text import align_offset, measure, wrap

if TYPE_CHECKING:
    from collections.abc import Callable

    from tkcurses import Event, Misc
    from tkcurses._core.paned import PaneOptions

__all__ = [
    "THEMES",
    "Combobox",
    "Progressbar",
    "Scale",
    "Separator",
    "Sizegrip",
    "Style",
    "Theme",
    "Treeview",
]


@dataclass(frozen=True)
class Glyphs:
    """The characters a theme draws a box with.

    Nine, in the order a border is assembled: four corners, two rails, and
    the three tee pieces a table or a notebook needs where lines meet.
    """

    top_left: str
    top_right: str
    bottom_left: str
    bottom_right: str
    horizontal: str
    vertical: str
    tee_down: str = "┬"
    tee_up: str = "┴"
    cross: str = "┼"


#: The themes, and what each one draws with. These replace tkinter's
#: clam/alt/default/classic, which describe bevels and shading that a
#: character grid has no way to show. See the module docstring.
THEMES: dict[str, Glyphs] = {
    "default": Glyphs("┌", "┐", "└", "┘", "─", "│"),
    "ascii": Glyphs("+", "+", "+", "+", "-", "|", "+", "+", "+"),
    "dos": Glyphs("╔", "╗", "╚", "╝", "═", "║", "╦", "╩", "╬"),
    "rounded": Glyphs("╭", "╮", "╰", "╯", "─", "│"),
    "double": Glyphs("╔", "╗", "╚", "╝", "═", "║", "╦", "╩", "╬"),
    "minimal": Glyphs(" ", " ", " ", " ", " ", " ", " ", " ", " "),
}

#: What :meth:`Style.lookup` answers with when nothing matches and the caller
#: named no default. tkinter answers with the empty string, and callers test
#: it for truth.
MISSING = ""


@dataclass
class Theme:
    """One theme's style database.

    Attributes:
        name: What ``theme_use`` is called with.
        glyphs: The characters a box is drawn with under this theme.
        settings: Per style name, the options ``configure`` recorded.
        states: Per style name and option, the ``map`` entries in the order
            they were given - order decides which one wins.
    """

    name: str
    glyphs: Glyphs
    settings: dict[str, dict[str, Any]] = field(default_factory=dict)
    states: dict[str, dict[str, list[tuple[tuple[str, ...], Any]]]] = field(
        default_factory=dict
    )

    def copy(self, name: str, glyphs: Glyphs | None = None) -> Theme:
        """A theme starting as a duplicate of this one.

        How ``theme_create(name, parent=...)`` is served: the child is a copy
        taken once, not a live view of its parent. tkinter's themes behave
        the same way, and a live view would mean a second dimension in every
        lookup for something nothing asks for.
        """
        return Theme(
            name=name,
            glyphs=glyphs or self.glyphs,
            settings={style: dict(options) for style, options in self.settings.items()},
            states={
                style: {option: list(entries) for option, entries in options.items()}
                for style, options in self.states.items()
            },
        )


def parse_padding(value: Any) -> Insets:
    """ttk's ``-padding`` as per-edge insets.

    One to four screen distances, in Tk's order - left, top, right, bottom -
    with right defaulting to left and bottom to top. Accepts the forms tkinter
    does: a number, a string of numbers, or a sequence of either.

    Anything unparseable is no padding rather than an error, because the option
    is also read back and compared, and a widget that refused to render because
    of a malformed pad would be worse than one that ignored it. Tk itself
    raises; matching that is TkCurses-avy's own follow-up if it ever matters.
    """
    if value is None or value == "":
        return Insets()
    pieces: Any
    if isinstance(value, (int, float)):
        pieces = [value]
    elif isinstance(value, str):
        pieces = value.split()
    else:
        pieces = value
    # One guard around every form, not only the sequence one. The first version
    # of this guarded the sequence branch and let a malformed STRING raise,
    # while its own docstring promised otherwise - a docstring describing
    # behaviour the code did not have, which is the same fault TkCurses-avy is
    # about.
    try:
        parts = [int(float(piece)) for piece in pieces]
    except (TypeError, ValueError):
        return Insets()
    if not parts or any(part < 0 for part in parts):
        return Insets()
    left = parts[0]
    top = parts[1] if len(parts) > 1 else left
    right = parts[2] if len(parts) > 2 else left
    bottom = parts[3] if len(parts) > 3 else top
    return Insets(left, top, right, bottom)


def style_chain(style: str) -> list[str]:
    """A style name and everything it inherits from, most specific first.

    ``Danger.TButton`` is ``["Danger.TButton", "TButton"]``. The walk strips
    one leading component at a time and goes all the way down, so
    ``A.B.C.TDeep`` ends at ``TDeep``.
    """
    parts = style.split(".")
    return [".".join(parts[index:]) for index in range(len(parts))]


def state_matches(spec: tuple[str, ...], states: frozenset[str]) -> bool:
    """Whether a map entry's state spec is satisfied.

    Every element has to match: a bare name means the state is set, and a
    ``!name`` means it is not. An empty spec matches anything, which is how
    a map entry with no states acts as a default.
    """
    for element in spec:
        if element.startswith("!"):
            if element[1:] in states:
                return False
        elif element not in states:
            return False
    return True


class Style:
    """The style database, as ``ttk.Style``.

    Every instance in one application talks to the same database, which is
    what makes ``ttk.Style().configure(...)`` in one place change widgets
    made in another. tkinter gets that by talking to the interpreter; here
    the database lives on the :class:`~tkcurses._core.application.Application`
    the widgets already share.
    """

    def __init__(self, master: Misc | None = None) -> None:
        """
        Args:
            master: Any widget of the application whose styles these are.
                Defaults to the implicit root, as tkinter's does.
        """
        import tkcurses

        if master is None:
            master = tkcurses._get_default_root("create a style")
        self.master = master
        self.tk = master.tk
        #: Set while a batch of settings is being applied, so the repaint
        #: happens once at the end rather than after every line of it.
        self._deferred = False
        if self.tk.themes is None:
            self.tk.themes = {
                name: Theme(name=name, glyphs=glyphs) for name, glyphs in THEMES.items()
            }
            self.tk.theme_in_use = "default"

    # ------------------------------------------------------------ the theme

    @property
    def _theme(self) -> Theme:
        """The theme in use, which is what every lookup resolves against."""
        assert self.tk.themes is not None
        return self.tk.themes[self.tk.theme_in_use]

    def theme_names(self) -> tuple[str, ...]:
        """Every theme there is.

        Not tkinter's clam/alt/default/classic - see the module docstring for
        why a terminal's themes are glyph sets instead.
        """
        assert self.tk.themes is not None
        return tuple(self.tk.themes)

    def theme_use(self, themename: str | None = None) -> str:
        """Switch themes, or report the one in use.

        Raises:
            TclError: If there is no such theme, as tkinter does rather than
                leaving an application drawing with nothing.
        """
        if themename is None:
            return self.tk.theme_in_use
        assert self.tk.themes is not None
        if themename not in self.tk.themes:
            raise TclError(f"no such theme: {themename!r}")
        self.tk.theme_in_use = themename
        self._restyle()
        return themename

    def _restyle(self) -> None:
        """Repaint every widget, because the database changed underneath them.

        A widget resolves its appearance when it paints, so changing a style
        changes nothing anyone can see until something happens to repaint.
        Real ttk restyles on the spot, and a style that only took effect on
        the next keypress would be one nobody could demonstrate - which is
        exactly what the acceptance asks a person to do.

        Every entry point that changes the database calls this: theme_use,
        configure and map. :meth:`theme_settings` defers it so that a batch
        of twenty settings repaints once rather than twenty times.
        """
        if self._deferred:
            return
        root = self.master
        while root.master is not None:
            root = root.master
        for widget in root._subtree():
            redraw = getattr(widget, "_redraw", None)
            if callable(redraw):
                with contextlib.suppress(Exception):
                    redraw()

    def theme_create(
        self,
        themename: str,
        parent: str | None = None,
        settings: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Add a theme, optionally starting from another.

        Args:
            themename: What to call it.
            parent: A theme to copy first. Without one the new theme starts
                empty, drawing with the default glyphs.
            settings: Applied after the copy, in ``theme_settings`` form.

        Raises:
            TclError: If the name is taken, or the parent does not exist.
        """
        assert self.tk.themes is not None
        if themename in self.tk.themes:
            raise TclError(f"theme {themename!r} already exists")
        if parent is None:
            theme = Theme(name=themename, glyphs=THEMES["default"])
        else:
            if parent not in self.tk.themes:
                raise TclError(f"no such theme: {parent!r}")
            theme = self.tk.themes[parent].copy(themename)
        self.tk.themes[themename] = theme
        if settings:
            self.theme_settings(themename, settings)

    def theme_settings(
        self, themename: str, settings: dict[str, dict[str, Any]]
    ) -> None:
        """Apply a batch of configure and map settings to one theme.

        Args:
            themename: The theme to change.
            settings: Style name to a dictionary that may hold
                ``configure`` and ``map`` keys, as tkinter's takes.

        Raises:
            TclError: If there is no such theme.
        """
        assert self.tk.themes is not None
        if themename not in self.tk.themes:
            raise TclError(f"no such theme: {themename!r}")
        was, self.tk.theme_in_use = self.tk.theme_in_use, themename
        self._deferred = True
        try:
            for style, spec in settings.items():
                if "configure" in spec:
                    self.configure(style, **spec["configure"])
                if "map" in spec:
                    self.map(style, **spec["map"])
        finally:
            self.tk.theme_in_use = was
            self._deferred = False
        self._restyle()

    def glyphs(self) -> Glyphs:
        """The characters the theme in use draws boxes with.

        Not tkinter API. It is how a widget asks what a border looks like
        now, which on a terminal is the whole of what a theme changes.
        """
        return self._theme.glyphs

    # ------------------------------------------------------------- settings

    def configure(self, style: str, query_opt: str | None = None, **kw: Any) -> Any:
        """Set options on a style, or read them back.

        With keywords, sets them. With ``query_opt``, returns that one. With
        neither, returns everything this style sets itself - its own entries
        only, not what it inherits.
        """
        if kw and not tkcurses._given(None, kw):
            return None  # every option None, which tkinter drops
        kw = tkcurses._given(None, kw)
        options = self._theme.settings.setdefault(style, {})
        if kw:
            options.update(kw)
            self._restyle()
            return None
        if query_opt is not None:
            return options.get(query_opt, MISSING)
        return dict(options)

    def map(self, style: str, query_opt: str | None = None, **kw: Any) -> Any:
        """Set per-state values on a style, or read them back.

        Each keyword takes a list of entries, every entry being one or more
        state names followed by the value: ``[("disabled", "grey")]`` or
        ``[("disabled", "focus", "grey")]``. **Order decides**, first match
        winning, so put the specific entries first.
        """
        if kw and not tkcurses._given(None, kw):
            return None  # every option None, which tkinter drops
        kw = tkcurses._given(None, kw)
        options = self._theme.states.setdefault(style, {})
        if kw:
            for option, entries in kw.items():
                options[option] = [
                    (tuple(str(part) for part in entry[:-1]), entry[-1])
                    for entry in entries
                ]
            self._restyle()
            return None
        if query_opt is not None:
            return [(*spec, value) for spec, value in options.get(query_opt, ())]
        return {
            option: [(*spec, value) for spec, value in entries]
            for option, entries in options.items()
        }

    def lookup(
        self,
        style: str,
        option: str,
        state: list[str] | tuple[str, ...] | None = None,
        default: Any = None,
    ) -> Any:
        """What ``option`` comes to for ``style`` in this state.

        Two passes over the inheritance chain, and the order is the thing
        that is easy to get wrong: **every style in the chain is checked for
        a matching map entry before any of them is checked for a configure
        value.** So a base style's map beats a derived style's configure.
        Measured against Tk 9.0, where it does exactly that.
        """
        states = frozenset(state or ())
        chain = style_chain(style)
        theme = self._theme
        for name in chain:
            for spec, value in theme.states.get(name, {}).get(option, ()):
                if state_matches(spec, states):
                    return value
        for name in chain:
            options = theme.settings.get(name, {})
            if option in options:
                return options[option]
        return MISSING if default is None else default

    # ------------------------------------------------------------- elements

    def element_names(self) -> tuple[str, ...]:
        """The drawable pieces a theme has.

        A terminal's are the parts of a box, because that is all a theme
        changes here. tkinter's are the pieces of a widget's layout, which
        is a thing this has no equivalent of - see :meth:`layout`.
        """
        return tuple(Glyphs.__dataclass_fields__)

    def element_options(self, elementname: str) -> tuple[str, ...]:
        """What an element takes. Each of ours takes one character.

        Raises:
            TclError: If there is no such element.
        """
        if elementname not in Glyphs.__dataclass_fields__:
            raise TclError(f"no such element: {elementname!r}")
        return ("character",)

    def layout(self, style: str, layoutspec: Any = None) -> Any:
        """Not available, and not a gap that can be filled.

        tkinter's layout rearranges the elements a widget is assembled from -
        which side the indicator sits on, how padding nests. A widget here is
        characters in a grid and has no such assembly to describe.

        Raises:
            TclError: Always, naming the reason rather than failing oddly.
        """
        del style, layoutspec
        raise TclError(
            "ttk.Style.layout is not available: a terminal widget has no "
            "element geometry to rearrange"
        )

    def element_create(self, elementname: str, etype: str, *args: Any) -> None:
        """Not available, for the same reason as :meth:`layout`.

        Raises:
            TclError: Always.
        """
        del elementname, etype, args
        raise TclError(
            "ttk.Style.element_create is not available: elements here are "
            "the characters a box is drawn with, not widget pieces"
        )


#: The states ttk defines, and the only ones a widget will accept. Measured
#: against Tk 9.0, which refuses anything else with "Invalid state name".
STATES: frozenset[str] = frozenset(
    {
        "active",
        "alternate",
        "background",
        "disabled",
        "focus",
        "hover",
        "invalid",
        "pressed",
        "readonly",
        "selected",
    }
)


def _state_option_flags(value: str) -> list[str]:
    """The state spec a ``-state`` value stands for: clear ``active``,
    ``disabled`` and ``readonly``, then set the one named, if any."""
    names = [f"!{flag}" for flag in ("active", "disabled", "readonly")]
    if value in ("active", "disabled", "readonly"):
        names.remove(f"!{value}")
        names.append(value)
    return names


class Widget:
    """What every themed widget adds to an ordinary one.

    A mixin rather than a base of its own, combined with whichever tkcurses
    widget already draws the thing: ``class Button(Widget, tkcurses.Button)``.
    That reuses the drawing and the behaviour, and adds the two things ttk is
    actually about - a set of state flags, and an appearance resolved from the
    style database against them.

    **A themed widget does not inherit the classic widget's bindings**, and
    that is deliberate rather than an oversight. Measured against Tk 9.0:
    ``ttk.Button`` has bindtags ``('.!button2', 'TButton', '.', 'all')`` -
    ``Button`` is not among them. Binding tags name one class, so a widget
    reporting ``TButton`` gets what is bound to ``TButton`` and nothing that
    was bound to ``Button``. Each themed widget therefore installs its own
    class bindings under its own name, exactly as ttk does.
    """

    #: What :meth:`winfo_class` answers, and so which tag the widget's class
    #: bindings and its default style are found under. Every subclass sets it.
    _ttk_class: str = "TWidget"

    #: The one option ttk adds to every widget. Option specs are merged down
    #: the MRO, so naming it here gives it to every themed widget without
    #: each of them repeating it. Empty by default, which is what tkinter
    #: answers too - an unset style means "use my class name", resolved in
    #: :meth:`_style_name` rather than stored.
    _widget_options: ClassVar[dict[str, Any]] = {"style": "", "class": ""}

    #: **No themed widget has an option synonym.** Measured on Tcl/Tk 9.0.2:
    #: ``ttk.Label`` has ``background`` and refuses ``bg``; ``ttk.Entry`` has
    #: ``validatecommand`` and refuses ``vcmd``. Tk's synonyms live in the
    #: classic widgets' option tables and ttk's elements do not carry them.
    #:
    #: This has to be declared, not inherited: every themed widget is built on
    #: a classic one, so without emptying the set here ``ttk.Entry(vcmd=...)``
    #: would be accepted - a divergence created by fixing the classic side.
    #: The most derived declaration wins and this mixin comes first in every
    #: themed MRO. TkCurses-oe5.
    _option_synonyms: ClassVar[dict[str, str]] = {}

    #: ttk keeps ``-class`` read-only its own way, below, and a themed widget
    #: has no window-system options to fix: the classic widgets' rule,
    #: TkCurses-gm66.7, does not reach one.
    _creation_only: ClassVar[frozenset[str]] = frozenset()

    def winfo_class(self) -> str:
        """The themed class name - ``TButton``, not ``Button``.

        This is what puts the widget's bindings and its default style under
        the ttk name, and what keeps the classic widget's bindings off it.

        ``-class`` OVERRIDES it, which is what that option is for. Measured
        against Tk 9.0: ``ttk.Label(class_="Custom").winfo_class()`` answers
        ``"Custom"``, so the style and the class bindings both resolve
        against the given name instead of ``TLabel``. It defaults to empty,
        and an empty one means "use my own class".
        """
        given = getattr(self, "_options", {}).get("class", "")
        return str(given) if given else self._ttk_class

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, refusing to change ``-class`` after construction.

        Tk makes ``-class`` read-only: measured, configuring it afterwards
        raises "attempt to change read-only option". It has to be, because
        the widget's bindings were installed under the name it had when it
        was built, and letting it move would leave them behind.
        """
        given = tkcurses._given(cnf, kw)
        current = getattr(self, "_options", {}).get("class", "")
        if "class" in given and given["class"] != current:
            raise TclError("attempt to change read-only option")
        result = super().configure(cnf, **kw)  # type: ignore[misc]
        if "state" in given and "state" in getattr(self, "_options", {}):
            self._state_from_option(str(given["state"]))
        return result

    def _state_from_option(self, value: str) -> None:
        """Set the state flags a ``-state`` value stands for, as ttk does.

        Measured on Tk 9.0.2, on every themed widget that has the option
        (Entry, Combobox, Spinbox, Button, Checkbutton, Radiobutton, Label,
        Scale, Menubutton): it clears ``active``, ``disabled`` and
        ``readonly`` and sets the one named - ``normal`` sets none - and
        leaves every other flag alone. Ours stored the option and left the
        flags as they were, so ``ttk.Combobox(state="readonly")``, the usual
        pick-from-a-list combobox, still took typing. The other direction is
        not tied: ``state(["disabled"])`` leaves ``cget("state")`` alone, in
        Tk too. TkCurses-fgke.
        """
        self.state(_state_option_flags(value))

    def _initial_options(self, given: dict[str, Any]) -> dict[str, Any]:
        """The classic options, and the flags a ``state=`` given at birth means.

        Construction does not pass through :meth:`configure`, so without this
        ``ttk.Combobox(state="readonly")`` set the option and not the flag.
        Applied to the flags directly: nothing can be redrawn yet.
        """
        options: dict[str, Any] = super()._initial_options(given)  # type: ignore[misc]
        if "state" in given and "state" in options:
            flags = self._state_flags
            for name in _state_option_flags(str(given["state"])):
                flags.discard(name[1:]) if name.startswith("!") else flags.add(name)
        return options

    config = configure

    # ---------------------------------------------------------- the states

    @property
    def _state_flags(self) -> set[str]:
        """The flags this widget currently has set."""
        flags: set[str] | None = getattr(self, "_ttk_states", None)
        if flags is None:
            flags = set()
            self._ttk_states = flags
        return flags

    def state(
        self, statespec: list[str] | tuple[str, ...] | None = None
    ) -> tuple[str, ...]:
        """Set or read the widget's state flags.

        Args:
            statespec: Flags to change, each a name or a negated ``!name``.
                Omit it to read the flags currently set.

        Returns:
            Reading: the flags set, sorted. Setting: **the previous value of
            the flags this call actually changed**, in the order given, as a
            spec that would undo it - so ``old = w.state(["disabled"])``
            followed later by ``w.state(old)`` puts it back. Measured against
            Tk 9.0: setting ``disabled`` on an enabled widget answers
            ``("!disabled",)``, and setting it again answers ``()`` because
            nothing changed.

        Raises:
            TclError: On a flag ttk does not define, as Tk does rather than
                storing a state nothing will ever look at.
        """
        flags = self._state_flags
        if statespec is None:
            return tuple(sorted(flags))
        changed: list[str] = []
        for entry in statespec:
            negated = entry.startswith("!")
            name = entry[1:] if negated else entry
            if name not in STATES:
                raise TclError(f"Invalid state name {name}")
            was_set = name in flags
            if negated == was_set:
                changed.append(name if was_set else f"!{name}")
                flags.discard(name) if negated else flags.add(name)
        if changed:
            # Tk repaints a themed widget whenever its state changes - a
            # state is how it looks. Without this, validate() set "invalid"
            # and the field showed it only at the next keystroke, and
            # state(["disabled"]) showed nothing at all. TkCurses-b9q.
            redraw = getattr(self, "_redraw", None)
            if redraw is not None:
                redraw()
        return tuple(changed)

    def instate(
        self,
        statespec: list[str] | tuple[str, ...],
        callback: Any = None,
        *args: Any,
        **kw: Any,
    ) -> Any:
        """Whether the widget is in a state, optionally running something if so.

        Returns:
            Without a callback, True or False. With one: **whatever the
            callback returned** if the spec matched, and False if it did not.
            Measured against Tk 9.0, where a matching call returned the
            callback's own ``None`` rather than True.
        """
        matched = state_matches(tuple(statespec), frozenset(self._state_flags))
        if callback is None:
            return matched
        return callback(*args, **kw) if matched else False

    # ----------------------------------------------------------- the style

    def _style_name(self) -> str:
        """The style this widget draws from.

        Its own ``style`` option when it has one, and otherwise its class
        name - which is why configuring ``TButton`` reaches every button that
        was not given a style of its own.
        """
        options = getattr(self, "_options", {})
        return str(options.get("style") or "") or self.winfo_class()

    def _content_padding(self) -> Insets:
        """The classic padding, plus ttk's ``-padding``.

        TkCurses-avy: five widgets declared this option and none of them did
        anything with it, so code written for ttk that padded a frame got no
        error and no padding - the layout quietly wrong with nothing to point
        at. It is added to ``padx``/``pady`` rather than replacing them,
        because a themed widget still answers to both and a caller who set
        each meant each.

        The side order is MEASURED, not recalled, because it is the kind of
        thing that is easy to have backwards. Real ttk 9.0, a 200x120 frame
        with a child filling it:

            padding="5"         child at 5,5    sized 190x110
            padding="2 8"       child at 2,8    sized 196x104
            padding="2 8 20"    child at 2,8    sized 178x104
            padding="2 8 20 30" child at 2,8    sized 178x82

        which is LEFT, TOP, RIGHT, BOTTOM, with right defaulting to left and
        bottom defaulting to top.
        """
        base = super()._content_padding()  # type: ignore[misc]
        extra = parse_padding(getattr(self, "_options", {}).get("padding"))
        return Insets(
            base.left + extra.left,
            base.top + extra.top,
            base.right + extra.right,
            base.bottom + extra.bottom,
        )

    def _background_attribute(self) -> int:
        """Colours resolved against the style database, not only the options.

        The classic method reads ``self._options`` and nothing else, so
        ``Style.configure("TButton", background="blue")`` reached none of the
        widgets built on ordinary ones - every one of them paints with this.
        Redirecting it to :meth:`_themed_attribute` is what makes a restyle
        visible, and that method keeps the right precedence: a widget handed
        ``foreground=`` directly still wins, because a caller who named a
        colour meant it.

        The companion to :meth:`_border_style`. That one fixed WHICH characters
        a themed widget draws (TkCurses-5vu); this one fixes what colour they
        are drawn in. Both were reported by a person using UAT 40 - Ctrl-T for
        the characters, Ctrl-R for the colours - and neither was caught by a
        test, because the tests compared option surfaces and the scenario's own
        status label.
        """
        return self._themed_attribute()

    def _border_style(self) -> BorderStyle:
        """The box this widget draws, taken from the theme.

        A themed widget's appearance belongs to the theme, so the glyphs come
        from the theme's set rather than from the relief's. The relief still
        decides the WEIGHT - its attribute, bold for raised and dim for sunken
        - because that is a distinction a theme's glyph set does not carry, and
        ``flat`` still draws nothing at all: a theme must not put a box around
        a widget that asked for none.

        This is TkCurses-5vu. Nine widgets built on ordinary ones - Frame,
        Labelframe, Button, Checkbutton, Radiobutton, Menubutton, Entry,
        Spinbox and Scrollbar - inherited the classic drawing and a theme
        change reached none of them. Found by a person pressing Ctrl-T in UAT
        40 and seeing only the label change, after an automated test asserted
        that same label and so never looked at a widget.

        One override rather than nine, because every one of them paints through
        ``_Drawable._draw_border``.
        """
        options = getattr(self, "_options", {})
        relief = str(options.get("relief", "") or tkcurses.FLAT)
        base: BorderStyle = super()._border_style()  # type: ignore[misc]
        if relief == tkcurses.FLAT:
            return base
        glyphs = Style(self).glyphs()  # type: ignore[arg-type]
        return BorderStyle(
            glyphs.top_left,
            glyphs.top_right,
            glyphs.bottom_left,
            glyphs.bottom_right,
            glyphs.horizontal,
            glyphs.vertical,
            base.attr,
        )

    def _themed_attribute(self) -> int:
        """The curses attribute this widget should draw with.

        The style database first, the widget's own options second. That
        order is what makes a themed widget themed: configuring
        ``TProgressbar`` reaches every bar that did not ask for a colour of
        its own, and a ``map`` entry reaches it only while it is in that
        state. A widget given ``foreground=`` directly still wins, because a
        caller who named a colour meant it.
        """
        colors = self.tk.colors  # type: ignore[attr-defined]
        if colors is None:
            return curses.A_NORMAL
        options = getattr(self, "_options", {})
        foreground = options.get("foreground") or self._styled("foreground")
        background = options.get("background") or self._styled("background")
        return int(
            colors.attribute_for(str(foreground or "white"), str(background or "black"))
        )

    def _styled(self, option: str, default: Any = None) -> Any:
        """One option, resolved from the style database for this state.

        The single call a themed widget makes when it wants to know what it
        looks like. Everything interesting - the inheritance through dotted
        names, maps beating configures - happens in :meth:`Style.lookup`.
        """
        return Style(self).lookup(  # type: ignore[arg-type]
            self._style_name(), option, sorted(self._state_flags), default
        )

    # ------------------------------------------------------------- identify
    #
    # ttk.Widget.identify answers the name of the style ELEMENT at a point -
    # "label", "Combobox.downarrow", "trough" - which is not the domain answer
    # the classic Scale, Scrollbar and Spinbox give ("trough1", "arrow1",
    # "buttonup"). Measured on Tk 9.0.2 for every themed widget, and read
    # against its default-theme layout: elements are nested rectangles, an
    # outer one (border, field) holding padding holding the content. The
    # names here are the DEFAULT theme's, transcribed rather than derived:
    # what comes back is the registered element, which is why it is "label"
    # for Button.label but "Checkbutton.indicator" for the indicator, and
    # the one place the built-in themes disagree (clam's Combobox answers
    # "Combobox.field" and a bare "downarrow"). TkCurses-d5u.
    #
    # Answered from the geometry as DRAWN, so a part drawn no cells wide is
    # never answered: there is no separate focus ring here, so "focus" never
    # comes back, and a flat border takes no cells.

    #: The outermost element of the ring model, and the innermost.
    _outer_element: ClassVar[str] = "border"
    _inner_element: ClassVar[str] = "label"

    #: For a widget whose layout is one element: the answer everywhere on it.
    _only_element: ClassVar[str | None] = None

    def identify(self, x: int, y: int) -> Any:
        """The name of the style element at ``(x, y)``, ``""`` outside them all.

        ``x`` and ``y`` are cells within this widget, as an event reports them.
        """
        rect = self._rect  # type: ignore[attr-defined]
        if not (0 <= x < rect.width and 0 <= y < rect.height):
            return ""
        if self._only_element is not None:
            return self._only_element
        return self._element_at(x, y)

    def _element_at(self, x: int, y: int) -> Any:
        """The ring model: the outer element's border, padding, the content."""
        host: Any = self
        if _within(self._element_area(), x, y):
            return self._inner_element
        rect = host._rect
        on_edge = x in (0, rect.width - 1) or y in (0, rect.height - 1)
        if host._border_drawn and on_edge:
            return self._outer_element
        return "padding"

    def _element_area(self) -> Rect:
        """Where the content element is: what the text is drawn into."""
        host: Any = self
        return cast("Rect", host._text_area())


def _within(area: Rect, x: int, y: int) -> bool:
    """Whether a cell falls inside a rectangle."""
    return area.x <= x < area.x + area.width and area.y <= y < area.y + area.height


def _indicator_element(widget: Any, name: str, x: int, y: int) -> Any:
    """A check or radio button's indicator, or the ring model around it."""
    place = widget._indicator_place()
    if place is not None:
        column, row = place
        if y == row and column <= x < column + widget._INDICATOR_WIDTH:
            return f"{name}.indicator"
    return Widget._element_at(widget, x, y)


def _menubutton_element(widget: Any, x: int, y: int) -> Any:
    """A menubutton's arrow, or the ring model around it."""
    if widget._indicator_cell() == (x, y):
        return "Menubutton.indicator"
    return Widget._element_at(widget, x, y)


#: How far :meth:`Progressbar.step` moves when nobody says. Tk's default.
STEP = 1.0

#: Milliseconds between automatic steps under :meth:`Progressbar.start`.
START_INTERVAL = 50

#: What a determinate bar is drawn with: the part done, then the part left.
FILLED = "█"
TROUGH = "░"

#: The grip, drawn into the bottom-right corner.
GRIP = "◢"

#: The smallest a window may be dragged to. Below this a window has no room
#: for its own border and the grip becomes impossible to find again.
MINIMUM_SIZE = 3


class Separator(Widget, tkcurses.Frame):
    """A line, and nothing else. ``ttk.Separator``.

    Drawn with the theme's rail characters, so it matches the borders around
    it: ``─`` under the default theme, ``-`` under ascii, ``═`` under double.
    """

    _ttk_class = "TSeparator"

    #: Measured: the one element its layout has.
    _only_element = "separator"

    _widget_options: ClassVar[dict[str, Any]] = {
        "orient": "horizontal",
        "foreground": "",
        "background": "",
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``orient``, ``style``, and the standard options.
        """
        kw.setdefault("relief", "flat")
        super().__init__(master, cnf, name=name, **kw)
        self._apply_requested_size()

    @property
    def _vertical(self) -> bool:
        """True if this separator runs up and down."""
        return str(self._options["orient"]) != "horizontal"

    def _apply_requested_size(self) -> None:
        """One cell thick, and as long as whatever it is packed beside."""
        if self._vertical:
            self._request_size(1, 2)
        else:
            self._request_size(2, 1)

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, re-measuring and repainting as the change requires."""
        given = tkcurses._given(cnf, kw)
        result = super().configure(cnf, **kw)
        if given:
            if "orient" in given:
                self._apply_requested_size()
                self._invalidate_layout()
            self._redraw()
        return result

    config = configure

    def _redraw(self) -> None:
        """Draw the line, in the theme's characters."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        glyphs = Style(self).glyphs()
        attribute = self._themed_attribute()
        dispatcher = CursesDispatcher.get()
        with contextlib.suppress(curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._vertical:
                for row in range(self._rect.height):
                    self._write_line(
                        dispatcher, window, row, 0, glyphs.vertical, attribute
                    )
            else:
                self._write_line(
                    dispatcher,
                    window,
                    0,
                    0,
                    glyphs.horizontal * self._rect.width,
                    attribute,
                )


class Sizegrip(Widget, tkcurses.Frame):
    """The corner grip, as ``ttk.Sizegrip``. Drag it to resize the window.

    Which window matters, and getting that wrong is what this was at first.
    A grip resizes **the toplevel it is in** - ``winfo_toplevel()`` - exactly
    as Tk's does. This library has its own windows: a ``Toplevel`` has a
    geometry, sits in a z-ordered stack, and redraws when it changes size, so
    dragging its corner is a real operation and not a pretence.

    The exception is the root window, whose size *is* the terminal's. Nothing
    an application draws can change that, so a grip on the root is a mark
    and nothing more. That is a statement about one window rather than about
    terminals, which is the distinction the first version of this missed.

    ``wm_resizable`` is honoured per axis, as Tk honours it: a window locked
    in one direction grows only in the other.
    """

    _ttk_class = "TSizegrip"

    #: Measured over the whole of Tk's.
    _only_element = "sizegrip"

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``style``, and the standard options.
        """
        #: Where a drag started, and how big the window was then.
        self._drag: tuple[int, int, int, int] | None = None
        kw.setdefault("relief", "flat")
        super().__init__(master, cnf, name=name, **kw)
        self._request_size(1, 1)
        self._install_class_bindings()

    def _install_class_bindings(self) -> None:
        """The three Tk binds, under this widget's own class name.

        A themed widget inherits none of the classic widget's bindings, so
        each one installs its own - see :class:`Widget`.
        """
        if self._ttk_class in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(self._ttk_class)
        bind = self.bind_class
        bind(self._ttk_class, "<Button-1>", _sizegrip_press)
        bind(self._ttk_class, "<B1-Motion>", _sizegrip_drag)
        bind(self._ttk_class, "<ButtonRelease-1>", _sizegrip_release)

    def _resizable_window(self) -> Misc | None:
        """The window this grip would resize, or None if there is not one.

        None for a grip on the root, whose size is the terminal's, and for a
        window locked against resizing in both directions.
        """
        window = self.winfo_toplevel()
        if window.master is None:
            return None
        resizable = getattr(window, "wm_resizable", None)
        if callable(resizable) and not any(resizable()):
            return None
        return window

    def _redraw(self) -> None:
        """Draw the grip in the bottom-right cell this widget has."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        attribute = self._themed_attribute()
        dispatcher = CursesDispatcher.get()
        with contextlib.suppress(curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            self._write_line(
                dispatcher,
                window,
                max(0, self._rect.height - 1),
                max(0, self._rect.width - 1),
                GRIP,
                attribute,
            )


def _sizegrip_press(event: Event) -> None:
    """Remember where the drag began and how big the window was.

    The distance travelled is what resizes, not the position arrived at, so
    wherever in the grip the press landed stays under the pointer - the same
    rule the scrollbar thumb follows.
    """
    grip = event.widget
    if grip.instate(["disabled"]):
        return
    window = grip._resizable_window()
    if window is None:
        return
    grip._drag = (
        event.x_root,
        event.y_root,
        window.winfo_width(),
        window.winfo_height(),
    )


def _sizegrip_drag(event: Event) -> None:
    """Resize the window by however far the grip has been dragged."""
    grip = event.widget
    origin = grip._drag
    if origin is None:
        return
    window = grip._resizable_window()
    if window is None:
        return
    press_x, press_y, width, height = origin
    wide, tall = window.wm_resizable()
    new_width = max(MINIMUM_SIZE, width + (event.x_root - press_x)) if wide else width
    new_height = (
        max(MINIMUM_SIZE, height + (event.y_root - press_y)) if tall else height
    )
    window.geometry(f"{new_width}x{new_height}+{window.winfo_x()}+{window.winfo_y()}")
    window.update_layout()


def _sizegrip_release(event: Event) -> None:
    """Forget the drag, leaving the window the size it was let go at."""
    event.widget._drag = None


class Progressbar(Widget, tkcurses.Frame):
    """A bar showing how far along something is. ``ttk.Progressbar``.

    Three behaviours here are not what they look like, and all three were
    measured against Tk 9.0 rather than assumed:

    **step() wraps in determinate mode and does not in indeterminate.**
    Determinate is ``(value + amount) % maximum`` - stepping 30 from 90 with
    a maximum of 100 lands on 20. Indeterminate just accumulates: 30, 60, 90,
    120, 270, without bound. The bar still has somewhere to draw, because the
    indeterminate *display* is the value taken modulo a there-and-back cycle.

    **Setting value directly does not wrap.** ``configure(value=150)`` on a
    bar whose maximum is 100 leaves it at 150. Only ``step`` wraps.

    **stop() resets value to zero**, as well as cancelling the timer. It is
    not a pause.
    """

    _value_checks: ClassVar[dict[str, Callable[[Any, Any], Any]]] = {
        "length": tkcurses._signed_distance
    }

    _ttk_class = "TProgressbar"

    def _element_at(self, x: int, y: int) -> Any:
        """``pbar`` over the filled cells, ``trough`` everywhere else."""
        span = self._rect.height if self._vertical else self._rect.width
        along, across = (y, x) if self._vertical else (x, y)
        if self._vertical:
            along = span - 1 - along  # it fills up from the bottom
        start, count = self._filled_cells(span)
        if across == 0 and start <= along < start + count:
            return "pbar"
        return "trough"

    _widget_options: ClassVar[dict[str, Any]] = {
        "orient": "horizontal",
        "mode": "determinate",
        "maximum": 100.0,
        "value": 0.0,
        "length": 20,
        "variable": None,
        "foreground": "",
        "background": "",
        # Tk 9.0's label over the bar - TkCurses-xe9.1. The defaults are
        # measured: anchor is "w" and justify "left", not "center" as a bar
        # showing "40%" in the middle might suggest.
        "text": "",
        "anchor": "w",
        "font": "",
        "justify": "left",
        "wraplength": 0,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``orient``, ``mode``, ``maximum``, ``value``, ``length``,
                ``style``, and the standard options.
        """
        self._timer: str | None = None
        kw.setdefault("relief", "flat")
        super().__init__(master, cnf, name=name, **kw)
        self._apply_requested_size()

    @property
    def _vertical(self) -> bool:
        """True if this bar fills from the bottom up."""
        return str(self._options["orient"]) != "horizontal"

    @property
    def _indeterminate(self) -> bool:
        """True in the mode that sweeps rather than fills."""
        return str(self._options["mode"]) == "indeterminate"

    def _apply_requested_size(self) -> None:
        """As long as ``length``, and one cell thick."""
        length = max(1, int(self._options["length"]))
        if self._vertical:
            self._request_size(1, length)
        else:
            self._request_size(length, 1)

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, re-measuring and repainting as the change requires."""
        given = tkcurses._given(cnf, kw)
        result = super().configure(cnf, **kw)
        if given:
            if {"length", "orient"} & set(given):
                self._apply_requested_size()
                self._invalidate_layout()
            self._redraw()
        return result

    config = configure

    # -------------------------------------------------------------- moving

    def step(self, amount: float | None = None) -> None:
        """Move the bar on.

        Args:
            amount: How far, defaulting to 1.0 as Tk's does.

        Determinate wraps at ``maximum``; indeterminate accumulates without
        bound and is drawn modulo its sweep. Both measured.
        """
        step = STEP if amount is None else float(amount)
        value = float(self._options["value"]) + step
        maximum = float(self._options["maximum"])
        if not self._indeterminate and maximum > 0:
            value %= maximum
        self.configure(value=value)

    def start(self, interval: int | None = None) -> None:
        """Step automatically until :meth:`stop`.

        Args:
            interval: Milliseconds between steps, defaulting to 50 as Tk's
                does. Starting an already-running bar does nothing, rather
                than stacking a second timer onto the first.
        """
        if self._timer is not None:
            return
        delay = START_INTERVAL if interval is None else int(interval)

        def tick() -> None:
            self._timer = None
            self.step()
            self._timer = self.after(delay, tick)

        self._timer = self.after(delay, tick)

    def stop(self) -> None:
        """Stop stepping and go back to zero.

        Not a pause: Tk's stop resets the value, and this does too.
        """
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None
        self.configure(value=0.0)

    def destroy(self) -> None:
        """Forget the timer handle. Misc.destroy cancels the timer itself.

        This used to cancel by hand, and the tick below used to begin with a
        winfo_exists() guard, because a callback scheduled on a widget went
        on firing after the widget was destroyed. That was TkCurses-khq, and
        it was the framework's fault rather than this widget's: every widget
        that schedules anything needed the same pair, and only this one had
        it. destroy() now drops a widget's pending callbacks, as Tk does.
        """
        self._timer = None
        super().destroy()

    # ------------------------------------------------------------ painting

    def _filled_cells(self, span: int) -> tuple[int, int]:
        """Which cells of a trough ``span`` long are filled, as ``(start, count)``.

        Determinate fills from the near end. Indeterminate is a block that
        sweeps out and back: the value is taken modulo twice the maximum, and
        the second half of that cycle is the first half reflected, which is
        what makes it bounce rather than jump back to the start.
        """
        maximum = float(self._options["maximum"]) or 1.0
        value = float(self._options["value"])
        if not self._indeterminate:
            filled = round(span * min(max(value / maximum, 0.0), 1.0))
            return (0, filled)
        block = max(1, span // 4)
        travel = max(1, span - block)
        cycle = value % (2 * maximum)
        position = cycle if cycle <= maximum else (2 * maximum) - cycle
        return (round(travel * position / maximum), block)

    def _redraw(self) -> None:
        """Paint the trough, then the filled part of it."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        span = self._rect.height if self._vertical else self._rect.width
        if span <= 0:
            return
        attribute = self._themed_attribute()
        start, count = self._filled_cells(span)
        cells = [TROUGH] * span
        for offset in range(start, min(start + count, span)):
            cells[offset] = FILLED
        if self._vertical:
            # Up from the bottom, which is the way a column fills.
            cells.reverse()
        dispatcher = CursesDispatcher.get()
        with contextlib.suppress(curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._vertical:
                for row, cell in enumerate(cells):
                    self._write_line(dispatcher, window, row, 0, cell, attribute)
            else:
                self._write_line(dispatcher, window, 0, 0, "".join(cells), attribute)
            self._draw_label(dispatcher, window, attribute)

    def _label_lines(self) -> list[str]:
        """The label's text, wrapped if ``wraplength`` asks for it.

        ``wraplength`` is in cells here, as every screen distance in this
        library is. Zero means no wrapping, which is :func:`wrap`'s own rule.
        """
        label = str(self._options["text"])
        if not label:
            return []
        return wrap(label, max(0, int(self._options["wraplength"])))

    def _draw_label(
        self, dispatcher: CursesDispatcher, window: Any, attribute: int
    ) -> None:
        """Draw ``text`` over the bar, where the anchor puts it.

        **Over the bar, not beside it**, and that is the one place this departs
        from Tk - because a cell cannot hold a block glyph and a letter at once.
        Measured on Tk 9.0.2: giving a horizontal bar any text grows it from 6
        pixels tall to 21, the height of the font, and the bar is drawn inside
        that band with the label on top. A terminal row is already one line
        tall, so the band and the overlay are the same thing here; what a
        person sees - the label on the bar - matches.

        The same measurement answers two questions the option list does not.
        **A longer label does not widen the bar**: a label far wider than
        ``length`` left the requested width at ``length``, so it is clipped
        rather than stretching the widget. And **a vertical bar ignores its
        text entirely** - the requested size was identical with and without it
        - so this draws nothing in that case rather than inventing a sideways
        label.
        """
        lines = self._label_lines()
        if not lines or self._vertical or self._rect.is_empty:
            return
        justify = str(self._options["justify"])
        across, down = parse_anchor(str(self._options["anchor"]))
        _, height = measure(lines)
        top = int((self._rect.height - height) * down)
        for offset, line in enumerate(lines):
            row = top + offset
            if not 0 <= row < self._rect.height:
                continue
            # The anchor decides where the BLOCK sits, justify where each line
            # sits within it - the same two-step Label uses, so a one-line
            # label is positioned by the anchor alone.
            column = int((self._rect.width - len(line)) * across)
            column += align_offset(
                len(line), max(0, self._rect.width - column), justify
            )
            # Not clipped here: _write_line clips to the window and documents
            # why it must - curses wraps an over-wide write onto the next row
            # rather than dropping it. A second clip looked like it mattered and
            # could not be mutated into failing, which is how it was spotted.
            self._write_line(dispatcher, window, row, max(0, column), line, attribute)


#: The mark at the right-hand end of a combobox, where ttk draws a downarrow.
ARROW = "▾"

#: How many rows of the list the dropdown shows when nothing says otherwise.
#: Tk's default, measured.
DROPDOWN_HEIGHT = 10

#: What current() answers when the text is not one of the values. Measured
#: against Tk 9.0.2, which gives -1 rather than 0 or None.
NOT_IN_LIST = -1


class _EntryCommands(tkcurses.Entry):
    """What all three ttk entries share and the classic Entry does not:
    ``validate`` and ``bbox``, and ttk's own validation rules.

    In tkinter both are defined once on ``ttk.Entry``, and ``ttk.Combobox``
    and ``ttk.Spinbox`` inherit them. Here those three subclass different
    classic widgets, so the two methods live in this one class, between
    ``Widget`` and the classic base. TkCurses-52q.
    """

    if TYPE_CHECKING:
        # Supplied by Widget, which comes before this in every subclass.
        def state(
            self, statespec: list[str] | tuple[str, ...] | None = None
        ) -> tuple[str, ...]: ...

    def validate(self) -> bool:
        """Revalidate now, whatever ``validate`` says, and set ``invalid``.

        Measured on Tk 9.0.2, which disagrees with the classic paths more
        than the manual's one sentence suggests:

        * **It runs under every mode, ``none`` included**, with the current
          text, and returns the verdict. Without a ``validatecommand`` it is
          True.
        * **The ``invalid`` state follows the answer**: set on a refusal,
          cleared on an approval, even one that was set by hand. Ordinary key
          validation, by contrast, never touches the state.
        * **A refusal runs the ``invalidcommand``**, as a refused edit or focus
          change does.
        * **A validator that raises makes this raise** ``TclError`` - tkinter
          hands Tcl nothing, and Tk cannot read that as a boolean - and turns
          validation off; the state is left alone.
        * **A validator that edits the entry**: its edit stays, this answers
          False with no ``invalidcommand``, ``invalid`` is set - and
          validation stays ON. The classic Entry turns it off; ttk does not.
        """
        verdict = self._ask_validator(self._field.text, can_raise=True)
        self.state(["!invalid" if verdict else "invalid"])
        return verdict

    # The ttk side of the classic Entry's validation hooks. Measured on Tk
    # 9.0.2, every condition against a validator that approves, refuses,
    # raises and edits the entry; ttk departs from the classic Entry in four
    # of those cells and in the invalid state. TkCurses-4ag.

    def _nested_edit(self) -> None:
        """An edit from inside a callback lands, and validation stays on.

        The edit being validated is still dropped - a key insert of ``X``
        whose validator appends ``!`` leaves ``hello!`` - but where the
        classic Entry then reads ``validate`` as ``none``, ttk keeps the mode.
        """

    def _validator_raised(self, *, can_raise: bool) -> None:
        """ttk hands the error to whoever asked: ``insert`` and ``delete``
        raise ``TclError``, and so does :meth:`validate`. A focus change has
        no caller and stays silent; validation is turned off either way."""
        if can_raise:
            raise TclError('expected boolean value but got "None"')

    def _validate_forced(self) -> None:
        """Nothing: ttk does not validate a ``textvariable`` write at all.

        Measured on all three ttk entries: with ``validate="all"`` the
        validator is not called when the variable is set, where the classic
        Entry calls it with ``%V`` = ``forced``.
        """

    def _validate_focus(self, condition: str) -> bool | None:
        """As the classic Entry, and the ``invalid`` state follows the answer.

        An approval clears it, even one set by hand; a refusal - or a
        validator that edits the entry - sets it. A validator that raised has
        turned validation off and leaves the state alone. Key validation
        never touches the state; only this and :meth:`validate` do.
        """
        verdict = super()._validate_focus(condition)
        if verdict is not None and str(self._options["validate"]) != "none":
            self.state(["!invalid" if verdict else "invalid"])
        return verdict

    def bbox(self, index: Any) -> tuple[int, int, int, int]:
        """The box of the character at ``index`` - see
        :meth:`tkcurses.Entry._char_bbox`."""
        return self._char_bbox(index)


class Combobox(Widget, _EntryCommands):
    """An entry with a list of values to choose from. ``ttk.Combobox``.

    Three behaviours were measured against Tk 9.0.2 rather than assumed, and
    the first is the one most likely to be got wrong.

    **Neither set() nor current() fires ``<<ComboboxSelected>>``.** Measured
    with a binding installed and ``update()`` pumped: the event never
    arrives. It fires when a person picks from the dropdown, and at no other
    time. It is a *gesture*, not a value change - so an application that
    watches it to learn the value has changed will miss every programmatic
    change, in Tk exactly as here.

    **current() answers -1 when the text is not one of the values**, not 0
    and not None; and ``set()`` to a listed value moves it to that index,
    while ``set()`` to anything else leaves it -1. Reconfiguring ``values``
    keeps the index if the current text is still in the new list.

    **The dropdown is a window of its own.** In Tk it is an
    ``overrideredirect`` toplevel of class ``ComboboxPopdown`` holding a
    listbox whose height is the combobox's ``height``. It is the same here,
    which makes it the case ARCHITECTURE.md's "Window Management" section
    describes: no decoration, so the widget places it rather than handing it
    to anything else.
    """

    _value_checks: ClassVar[dict[str, Callable[[Any, Any], Any]]] = {
        "width": tkcurses._tcl_integer
    }

    _ttk_class = "TCombobox"

    _outer_element = "field"
    _inner_element = "textarea"

    def _element_at(self, x: int, y: int) -> Any:
        """The arrow's column is ``Combobox.downarrow``, the rest an entry's."""
        area = tkcurses.Entry._text_area(self)
        arrow = area.x + area.width - 1
        if area.width and x == arrow and area.y <= y < area.y + area.height:
            return "Combobox.downarrow"
        return super()._element_at(x, y)

    # exportselection is NOT repeated here. It was declared on this class alone
    # and nothing honoured it - an option accepted and silently ignored, which
    # the option-surface test cannot see because it compares names rather than
    # behaviour. It now lives on tkcurses.Entry, which this inherits, so there
    # is one declaration and one default. TkCurses-163.
    _widget_options: ClassVar[dict[str, Any]] = {
        "values": (),
        "height": DROPDOWN_HEIGHT,
        "postcommand": None,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``values``, ``height``, ``postcommand``, ``style``, plus
                everything an Entry takes.
        """
        self._popdown: tkcurses.Toplevel | None = None
        self._listbox: tkcurses.Listbox | None = None
        super().__init__(master, cnf, name=name, **kw)
        self._install_class_bindings()

    # ------------------------------------------------------------- bindings

    def _install_class_bindings(self) -> None:
        """Register the gestures a combobox answers, under its own class name.

        ``TCombobox``, not ``Entry``: binding tags name one class, so these
        do not displace Entry's editing keys - the widget carries both tags
        and gets both sets.
        """
        if self._ttk_class in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(self._ttk_class)
        bind = self.bind_class
        # Entry's editing keys, again, under this class. Binding tags name
        # one class rather than a chain, so a widget reporting TCombobox
        # matches nothing bound to Entry - measured, a combobox took every
        # keystroke and did nothing with it, the text never changing. The
        # same trap Spinbox meets with Entry and OptionMenu with Menubutton;
        # this is its fifth appearance, and the first in a widget written
        # after it was written down.
        # This widget's own first: bindings on one tag run in the order they
        # were registered, and Down and Escape mean something here that they
        # do not mean in a plain field.
        # Tk's ttk::combobox::Press: on an editable combobox's text these are
        # an entry's clicks, and anywhere else - the arrow, the border, or a
        # read-only combobox - they open the list. TkCurses-fgke.
        bind(self._ttk_class, "<Button-1>", lambda e: _combobox_press(e, ""))
        bind(self._ttk_class, "<Double-Button-1>", lambda e: _combobox_press(e, "2"))
        bind(self._ttk_class, "<Triple-Button-1>", lambda e: _combobox_press(e, "3"))
        for extend in tkcurses._EXTEND_MODIFIERS:
            bind(
                self._ttk_class,
                f"<{extend}-Button-1>",
                lambda e: _combobox_press(e, "s"),
            )
        # Tk's Drag acts only after a press in the text; the entry's drag
        # handler already does nothing unless such a press began one.
        bind(self._ttk_class, "<Motion>", tkcurses._entry_drag)
        bind(self._ttk_class, "<ButtonRelease-1>", tkcurses._entry_release)
        bind(self._ttk_class, "<Key-Down>", _combobox_open)
        bind(self._ttk_class, "<Key-Escape>", _combobox_escape)
        bind(self._ttk_class, "<Any-Key>", tkcurses._entry_key)
        bind(self._ttk_class, "<FocusIn>", tkcurses._entry_focus_in)
        bind(self._ttk_class, "<FocusOut>", tkcurses._entry_focus_out)
        tkcurses._bind_entry_clipboard(bind, self._ttk_class)
        tkcurses._bind_entry_navigation(bind, self._ttk_class, themed=True)

    # ---------------------------------------------------------------- state

    @property
    def _editable(self) -> bool:
        """True while the field takes typing.

        ttk keeps this in its state flags rather than in a ``state`` option,
        so ``readonly`` and ``disabled`` are asked of the flags. A readonly
        combobox still opens - it is the *typing* that is refused, not the
        widget.
        """
        return not (self.instate(["readonly"]) or self.instate(["disabled"]))

    # --------------------------------------------------------------- values

    @property
    def _values(self) -> tuple[str, ...]:
        """The values, as the tuple ``cget`` hands back."""
        return tuple(str(value) for value in self._options["values"])

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, keeping the dropdown and the arrow in step."""
        given = tkcurses._given(cnf, kw)
        result = super().configure(cnf, **kw)
        if given and "values" in given and self._listbox is not None:
            self._fill_list()
        return result

    config = configure

    def cget(self, key: str) -> Any:
        """One option's value; ``values`` comes back a tuple, as Tk's does."""
        if key == "values":
            return self._values
        return super().cget(key)

    __getitem__ = cget

    def set(self, value: str) -> None:
        """Replace the text. Does not fire ``<<ComboboxSelected>>``.

        Unvalidated and ungated by state, as Tk's is - see
        :meth:`Entry._set_value`. This was ``delete`` then ``insert`` until
        TkCurses-elb, so a refusing validatecommand was asked twice and kept
        the old text, and a disabled combobox could not be set at all.
        """
        self._set_value(value)

    def current(self, newindex: int | None = None) -> int | None:
        """Get or set which of ``values`` is showing.

        Args:
            newindex: The index to select, or None to read the current one.

        Returns:
            Reading: the index of the text within ``values``, or ``-1`` when
            it is not one of them. Setting: None.

        Raises:
            TclError: On an index outside ``values``, as Tk does.
        """
        values = self._values
        if newindex is None:
            try:
                return values.index(self.get())
            except ValueError:
                return NOT_IN_LIST
        try:
            value = values[int(newindex)]
        except (IndexError, ValueError):
            raise TclError(f'index "{newindex}" out of range') from None
        self.set(value)
        return None

    # ------------------------------------------------------------- dropdown

    @property
    def _open(self) -> bool:
        """True while the dropdown is showing."""
        return self._popdown is not None and self._popdown.winfo_exists()

    def _post(self) -> None:
        """Show the dropdown under the combobox, or over it if there is no room.

        ``postcommand`` runs first, as Tk's does, so an application can fill
        ``values`` at the moment of opening.
        """
        if self._open or self.instate(["disabled"]):
            return
        command = self._options["postcommand"]
        if callable(command):
            command()
        values = self._values
        if not values:
            return

        # Two rows more than the values need, for the border around them.
        rows = max(1, min(int(self._options["height"]), len(values))) + 2 * BORDER_WIDTH
        width = max(1, self._rect.width)
        window = tkcurses.Toplevel(self, name="popdown", width=width, height=rows)
        # No decoration, so nothing else can place it - the same case as any
        # borderless window. See ARCHITECTURE.md, "Window Management".
        window.overrideredirect(True)
        below = self.winfo_rooty() + self._rect.height
        screen_height = self.winfo_screenheight()
        top = below if below + rows <= screen_height else self.winfo_rooty() - rows
        window.geometry(f"{width}x{rows}+{self.winfo_rootx()}+{max(0, top)}")

        # Bordered, as Tk's popdown is: a list of values floating over the
        # application with nothing around it reads as text that has landed on
        # the screen rather than as a thing to choose from.
        # Not exported, as combobox.tcl makes it: choosing from the list
        # must not take PRIMARY from the entry.
        listbox = tkcurses.Listbox(
            window, name="list", relief="solid", exportselection=False
        )
        listbox.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self._popdown, self._listbox = window, listbox
        self._fill_list()
        # A click anywhere else closes without choosing, which includes a
        # second click on the combobox itself. The dropdown holds the grab,
        # so every click outside it is routed here rather than to whatever
        # was under the pointer - and a click inside stays with the listbox,
        # because the grab keeps events that are already within its own
        # subtree.
        window.bind("<Button-1>", lambda _event: self._unpost())
        listbox.bind("<Button-1>", lambda event: self._pick_from(event), add="+")
        listbox.bind("<Key-Return>", lambda _event: self._pick())
        listbox.bind("<Key-Escape>", lambda _event: self._unpost())
        window.grab_set()
        listbox.focus_set()
        self._layout()
        # After the layout pass, which creates the panels of anything that
        # needed one: a dropdown made before it is otherwise left under
        # whatever the pass touched next, and shows a single row with the
        # widget below drawn over the rest. tkraise carries its subtree.
        window.tkraise()

    def _fill_list(self) -> None:
        """Put the values in the list, with the current one active."""
        listbox = self._listbox
        if listbox is None or not listbox.winfo_exists():
            return
        listbox.delete(0, "end")
        values = self._values
        if values:
            listbox.insert("end", *values)
        index = self.current()
        if index is not None and index >= 0:
            listbox.selection_clear(0, "end")
            listbox.selection_set(index)
            listbox.activate(index)
            listbox.see(index)

    def _unpost(self) -> None:
        """Take the dropdown down and give the keyboard back."""
        window = self._popdown
        self._popdown = self._listbox = None
        if window is not None and window.winfo_exists():
            window.grab_release()
            window.destroy()
        if self.winfo_exists():
            self.focus_set()
            self._layout()

    def _layout(self) -> None:
        """Re-run layout, which a window appearing or going needs."""
        root = self.winfo_toplevel()
        with contextlib.suppress(Exception):
            root.update_layout()

    def _pick_from(self, event: Event) -> None:
        """Choose whatever row was clicked."""
        listbox = self._listbox
        if listbox is None:
            return
        listbox.selection_clear(0, "end")
        listbox.selection_set(listbox.nearest(event.y))
        self._pick()

    def _pick(self) -> None:
        """Take the highlighted value, close, and say so.

        The one place ``<<ComboboxSelected>>`` is fired, because a pick is
        the only thing that fires it in Tk.
        """
        listbox = self._listbox
        if listbox is None:
            return
        chosen = listbox.curselection()
        if chosen:
            # Tk's SelectEntry, word for word: current, select all, cursor to
            # the end. The last two used to happen by accident, as a side
            # effect of set() being delete-then-insert.
            self.set(self._values[chosen[0]])
            self.selection_range(0, "end")
            self.icursor("end")
        self._unpost()
        self.event_generate("<<ComboboxSelected>>")

    def destroy(self) -> None:
        """Take the dropdown down with the widget, rather than leaving it up."""
        self._unpost()
        super().destroy()

    # ------------------------------------------------------------- painting

    def _text_area(self) -> Rect:
        """The field, less the cell the arrow is drawn in."""
        area = super()._text_area()
        return Rect(area.x, area.y, max(0, area.width - 1), area.height)

    def _redraw(self) -> None:
        """Paint the field, then the arrow that says there is a list."""
        super()._redraw()
        window = self._window
        if window is None or self.tk.screen is None:
            return
        area = super()._text_area()
        if area.is_empty:
            return
        dispatcher = CursesDispatcher.get()
        with contextlib.suppress(curses.error):
            self._write_line(
                dispatcher,
                window,
                area.y,
                area.x + area.width - 1,
                ARROW,
                self._themed_attribute(),
            )


def _combobox_press(event: Event, mode: str) -> Any:
    """Select in the text, or open the list - ``ttk::combobox::Press``.

    Read from Tk 9.0.2: a press counts as the ENTRY's when the combobox is
    not read-only and the press is on its ``textarea`` element, and is then
    ttk's entry press, word select, line select or shift-press by ``mode``
    ("", "2", "3", "s"). Anywhere else it opens the list. Until this, every
    click opened it, so the text of an editable combobox could not be
    clicked into or selected with the mouse at all. TkCurses-fgke.
    """
    combobox = event.widget
    if not isinstance(combobox, Combobox) or combobox.instate(["disabled"]):
        return "break"
    entry_press = not combobox.instate(["readonly"]) and str(
        combobox.identify(event.x, event.y)
    ).endswith("textarea")
    if not entry_press:
        return _combobox_click(event)
    combobox.focus_set()
    {
        "": tkcurses._entry_click,
        "2": tkcurses._entry_double,
        "3": tkcurses._entry_triple,
        "s": tkcurses._entry_shift_click,
    }[mode](event)
    return "break"


def _combobox_click(event: Event) -> Any:
    """Open the list, or close it if it is already open."""
    combobox = event.widget
    if not isinstance(combobox, Combobox):
        return None
    if combobox._open:
        combobox._unpost()
    else:
        combobox._post()
    return "break"


def _combobox_open(event: Event) -> Any:
    """Down opens the list, as it does in Tk."""
    combobox = event.widget
    if isinstance(combobox, Combobox) and not combobox._open:
        combobox._post()
        return "break"
    return None


def _combobox_escape(event: Event) -> Any:
    """Escape closes the list and leaves the value alone."""
    combobox = event.widget
    if isinstance(combobox, Combobox) and combobox._open:
        combobox._unpost()
        return "break"
    return None


#: Rows the tab strip occupies: the tops of the tab boxes, their labels, and
#: the page frame's top edge that the selected tab opens into.
#:
#: Three rather than one, deliberately. The tabs were drawn into the frame's
#: top border once, which cost a single row and read as a row of words on a
#: line. Tk draws raised boxes standing on the page frame, with the selected
#: one open at the bottom so the tab and its page are visibly one space -
#: that shape is what makes a notebook recognisable, and it is worth the two
#: rows.
STRIP_HEIGHT = 3

#: Cells of padding either side of a tab's label, inside its box.
TAB_PADDING = 1

#: The page frame starts one column in, leaving its own top-left corner
#: clear of the first tab.
TAB_INSET = 1

#: What separates one tab from the next in the strip, and what brackets the
#: selected one. Drawn with the theme's own vertical rule.
TAB_GAP = " "


@dataclass
class _Tab:
    """One page of a notebook, and what the strip says about it.

    Attributes:
        child: The widget the page shows.
        options: Its tab options - text, state, padding and the rest.
        hidden: Whether ``hide`` has taken it out of the strip. It stays in
            ``tabs()`` either way, which is what Tk does.
    """

    child: tkcurses.Widget
    options: dict[str, Any]
    hidden: bool = False


class Notebook(Widget, tkcurses.Frame):
    """Pages behind a row of tabs. ``ttk.Notebook``.

    Measured against Tk 9.0.2, and the first of these is worth holding
    beside the Combobox:

    **``<<NotebookTabChanged>>`` fires on a programmatic ``select()``**,
    where ``<<ComboboxSelected>>`` fires only on a gesture. They are not one
    convention, and guessing from the other gets it wrong either way. It
    fires on a *change*: selecting the tab already selected fires nothing.

    **``hide`` is not ``forget``.** A hidden tab stays in ``tabs()`` and in
    ``index("end")`` - it stops being shown, not being managed - and
    ``add``-ing its child again un-hides it in place rather than appending a
    second copy. ``forget`` is the one that removes.

    On a character grid the strip is a single row of labels drawn with the
    theme's glyphs, and only the selected child occupies the space below it.
    ``image``, ``compound`` and ``underline`` are accepted and ignored, as
    everywhere else in this cycle: they describe pixels.
    """

    _ttk_class = "TNotebook"

    def _element_at(self, x: int, y: int) -> Any:
        """Over a tab ``tab``, ``padding`` or ``label``; ``""`` anywhere else.

        Measured on Tk: a tab is ``tab`` holding ``padding`` holding
        ``label``, and the tab row past the last tab and the page under it
        both answer ``""``. Here the tab's box is ``tab``, its label text
        ``label`` and the spaces either side ``padding``. Not a tab index -
        that is :meth:`index` with ``"@x,y"``.
        """
        if y > 1:
            return ""
        for index, first, last in self._tab_spans():
            if not first <= x <= last:
                continue
            if y == 0 or x in (first, last):
                return "tab"
            label = str(self._tabs[index].options["text"])
            start = first + 1 + TAB_PADDING
            return "label" if start <= x < start + len(label) else "padding"
        return ""

    _widget_options: ClassVar[dict[str, Any]] = {
        "height": 0,
        "width": 0,
        "padding": "",
    }

    #: What ``tab()`` answers for, with the defaults Tk gives.
    _tab_options: ClassVar[dict[str, Any]] = {
        "text": "",
        "state": "normal",
        "sticky": "nsew",
        "padding": 0,
        "image": "",
        "compound": "",
        "underline": "",
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``height``, ``width``, ``padding``, ``style``, and the
                standard options.
        """
        self._tabs: list[_Tab] = []
        # The selected TAB, not its index. Measured on Tk 9.0.2: forgetting
        # a tab before the selected one leaves the same page selected and
        # shifts its index down, so an index held across a mutation names
        # the wrong page - or none.
        self._selected: _Tab | None = None
        # Bordered: Tk frames the page area and sits the tabs on its edge, and
        # a notebook with nothing drawn around it is a row of words above some
        # text - there is no way to see where a page ends.
        kw.setdefault("relief", "solid")
        super().__init__(master, cnf, name=name, **kw)
        self._install_class_bindings()

    def _install_class_bindings(self) -> None:
        """Clicking a tab selects it; Left and Right walk the strip."""
        if self._ttk_class in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(self._ttk_class)
        bind = self.bind_class
        bind(self._ttk_class, "<Button-1>", _notebook_click)
        bind(self._ttk_class, "<Key-Left>", _notebook_previous)
        bind(self._ttk_class, "<Key-Right>", _notebook_next)
        bind(self._ttk_class, "<Control-Key-Tab>", _notebook_next)

    # ---------------------------------------------------------------- tabs

    def add(self, child: tkcurses.Widget, **kw: Any) -> None:
        """Append a page, or un-hide one that is already here.

        Args:
            child: The widget to show on the page.
            **kw: Tab options - ``text``, ``state``, ``sticky`` and the rest.

        Adding a child that is already a tab un-hides it in place rather than
        appending a second copy, which is what Tk does.
        """
        kw = tkcurses._given(None, kw)
        existing = self._find(child)
        if existing is not None:
            existing.hidden = False
            existing.options.update(self._checked_tab(kw))
        else:
            self._tabs.append(
                _Tab(child, {**self._tab_options, **self._checked_tab(kw)})
            )
        self._settle()

    def insert(self, where: Any, child: tkcurses.Widget, **kw: Any) -> None:
        """Put a page at ``where`` rather than at the end."""
        kw = tkcurses._given(None, kw)
        position = self._position(where, allow_end=True)
        existing = self._find(child)
        if existing is not None:
            self._tabs.remove(existing)
            existing.hidden = False
            existing.options.update(self._checked_tab(kw))
            tab = existing
        else:
            tab = _Tab(child, {**self._tab_options, **self._checked_tab(kw)})
        self._tabs.insert(min(position, len(self._tabs)), tab)
        self._settle()

    def forget(self, where: Any) -> None:  # type: ignore[override]
        """Remove a page altogether. Unlike :meth:`hide`, it leaves ``tabs()``.

        The name collides with the geometry managers' ``forget``, which takes
        no argument. Tk has the same collision and resolves it the same way:
        on a notebook, ``forget`` is about tabs.
        """
        tab = self._tabs.pop(self._position(where))
        tab.child._unmap()
        self._settle()

    def hide(self, where: Any) -> None:
        """Stop showing a page, keeping it in ``tabs()``.

        Not ``forget``: the tab is still managed, still counted by
        ``index("end")``, and ``add``-ing its child again brings it back in
        place. Hiding the selected tab moves the selection on.
        """
        tab = self._tabs[self._position(where)]
        tab.hidden = True
        tab.child._unmap()
        self._settle()

    def tabs(self) -> tuple[str, ...]:
        """Every page's widget path, hidden ones included, as Tk does."""
        return tuple(str(tab.child) for tab in self._tabs)

    def tab(self, where: Any, option: str | None = None, **kw: Any) -> Any:
        """Read or set one page's tab options.

        Args:
            where: An index, the child widget, or ``"current"``.
            option: One option to read, or None for all of them.
            **kw: Options to set.

        Returns:
            The option's value, or every option as a dict, or None when
            setting.
        """
        if kw and not tkcurses._given(None, kw):
            return None  # every option None, which tkinter drops
        kw = tkcurses._given(None, kw)
        tab = self._tabs[self._position(where)]
        if kw:
            tab.options.update(self._checked_tab(kw))
            self._settle()
            return None
        if option is not None:
            return tab.options[option.lstrip("-")]
        return dict(tab.options)

    # ----------------------------------------------------------- selection

    def select(self, where: Any = None) -> Any:
        """Show a page, or say which one is showing.

        Args:
            where: An index or the child widget; omit it to read.

        Returns:
            Reading: the selected child's path, or ``""`` when there is
            none. Setting: None.

        Selecting the page that is already selected does nothing at all -
        measured, Tk fires no event for it.
        """
        if where is None:
            if self._current is None:
                return ""
            return str(self._tabs[self._current].child)
        position = self._position(where)
        if position == self._current:
            return None
        self._selected = self._tabs[position]
        self._settle()
        self.event_generate("<<NotebookTabChanged>>")
        return None

    def index(self, where: Any) -> int:
        """The position of a page, the count for ``"end"``."""
        if str(where) == "end":
            return len(self._tabs)
        return self._position(where)

    def enable_traversal(self) -> None:
        """Accepted for compatibility; the keys are always bound here.

        Tk binds traversal to the toplevel only when asked, because the keys
        it uses are shared. Nothing else here wants Left and Right on a
        notebook, so they are on from the start and this has nothing to do.
        """

    # ------------------------------------------------------------ internals

    def _find(self, child: tkcurses.Widget) -> _Tab | None:
        """The tab holding ``child``, if it is one of them."""
        for tab in self._tabs:
            if tab.child is child:
                return tab
        return None

    def _position(self, where: Any, *, allow_end: bool = False) -> int:
        """Resolve an index, a child widget or ``"current"`` to a position."""
        if isinstance(where, tkcurses.Widget):
            tab = self._find(where)
            if tab is None:
                raise TclError(f'managed window "{where}" not a tab')
            return self._tabs.index(tab)
        text = str(where)
        if text == "current":
            if self._current is None:
                raise TclError("no tab is selected")
            return self._current
        if text == "end" and allow_end:
            return len(self._tabs)
        try:
            position = int(text)
        except ValueError:
            raise TclError(f'bad notebook index "{where}"') from None
        limit = len(self._tabs) if allow_end else len(self._tabs) - 1
        if not 0 <= position <= max(0, limit):
            raise TclError(f'Managed window index "{where}" out of bounds')
        return position

    def _checked_tab(self, given: dict[str, Any]) -> dict[str, Any]:
        """Reject a tab option Tk does not have, as Tk does."""
        cleaned = {}
        for key, value in given.items():
            name = key.lstrip("-")
            if name not in self._tab_options:
                raise TclError(f'unknown option "-{name}"')
            cleaned[name] = value
        return cleaned

    @property
    def _current(self) -> int | None:
        """Where the selected tab sits now, or None if there is none."""
        if self._selected is None or self._selected not in self._tabs:
            return None
        return self._tabs.index(self._selected)

    @property
    def _shown(self) -> list[int]:
        """The positions of the tabs the strip shows."""
        return [index for index, tab in enumerate(self._tabs) if not tab.hidden]

    def _settle(self) -> None:
        """Keep the selection legal, place the pages, and repaint the strip."""
        shown = self._shown
        if not shown:
            self._selected = None
        elif self._current is None or self._current not in shown:
            self._selected = self._tabs[shown[0]]
        current = self._current
        for index, tab in enumerate(self._tabs):
            if index == current:
                # Relative, with the border taken off as a negative offset.
                # Not arithmetic on self._rect: _settle runs before the
                # notebook has been laid out, so the width read there is
                # zero and the page is placed zero cells wide - which is
                # what ate the right and bottom border. The layout engine
                # resolves relwidth at the moment it knows the answer.
                edge = BORDER_WIDTH if self._bordered else 0
                tab.child.place(
                    x=edge,
                    y=STRIP_HEIGHT,
                    relwidth=1.0,
                    width=-2 * edge,
                    relheight=1.0,
                    height=-(STRIP_HEIGHT + edge),
                )
            else:
                # Both: place_forget takes it out of the layout, _unmap takes
                # it off the screen. Leaving the layout does not hide a
                # window - measured, the previous page's contents stayed
                # drawn over the new one.
                tab.child.place_forget()
                tab.child._unmap()
        self._invalidate_layout()
        # The pages are this widget's children, so they belong above its own
        # panel - and a page shown, hidden and shown again comes back at
        # whatever place in the stack it was rebuilt at, which is below the
        # notebook. The symptom is a tab whose contents are there and
        # invisible: the notebook's blank background is drawn over them.
        stack = self.tk.panels
        if stack is not None:
            self._restack_descendants(stack)
        self._redraw()

    def _tab_spans(self) -> list[tuple[int, int, int]]:
        """Each shown tab as ``(index, first column, last column)``.

        Inset by one, so that the page frame's own top-left corner has a
        column to itself and the first tab does not sit on top of it.
        """
        spans = []
        column = TAB_INSET
        for index in self._shown:
            label = str(self._tabs[index].options["text"])
            width = len(label) + 2 * TAB_PADDING + 2
            spans.append((index, column, column + width - 1))
            column += width
        return spans

    def _strip_rows(self) -> list[str]:
        """The three rows of the strip, as they are drawn.

        A tab is a box standing on the page frame. The selected one is
        **open at the bottom**, so that it and the page it shows are one
        space rather than two things near each other - which is how Tk draws
        it, and the only mark that does not depend on colour. A notebook has
        to be readable on a terminal with none.
        """
        glyphs = Style(self).glyphs()
        width = max(0, self._rect.width)
        tops = [" "] * width
        labels = [" "] * width
        frame = ["─"] * width

        for index, first, last in self._tab_spans():
            if last >= width:
                break
            label = str(self._tabs[index].options["text"])
            tops[first] = glyphs.top_left
            tops[last] = glyphs.top_right
            for column in range(first + 1, last):
                tops[column] = glyphs.horizontal
            labels[first] = glyphs.vertical
            labels[last] = glyphs.vertical
            for offset, character in enumerate(f"{' ' * TAB_PADDING}{label}"):
                if first + 1 + offset < last:
                    labels[first + 1 + offset] = character
            if index == self._current:
                # Open at the bottom: the tab runs into its page.
                frame[first] = glyphs.bottom_right
                frame[last] = glyphs.bottom_left
                for column in range(first + 1, last):
                    frame[column] = " "
            else:
                frame[first] = glyphs.tee_up
                frame[last] = glyphs.tee_up

        if width:
            frame[0] = glyphs.top_left
            frame[width - 1] = glyphs.top_right
        return ["".join(tops), "".join(labels), "".join(frame)]

    def _strip(self) -> str:
        """The label row on its own. Kept for the tests that read one row."""
        return self._strip_rows()[1]

    def _tab_at(self, column: int) -> int | None:
        """Which tab covers a column of the strip, if any."""
        for index, first, last in self._tab_spans():
            if first <= column <= last:
                return index
        return None

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, re-placing the pages as the size changes."""
        given = tkcurses._given(cnf, kw)
        result = super().configure(cnf, **kw)
        if given:
            self._settle()
        return result

    config = configure

    def _redraw(self) -> None:
        """Paint the tab strip. The pages draw themselves."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        attribute = self._themed_attribute()
        dispatcher = CursesDispatcher.get()
        with contextlib.suppress(curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._border_drawn:
                self._draw_border(
                    dispatcher, window, self._rect.width, self._rect.height, attribute
                )
            if self._rect.width > 0:
                # The frame's own top edge is the third of these, so the
                # border drawn above is overwritten there on purpose.
                for row, text in enumerate(self._strip_rows()):
                    self._write_line(dispatcher, window, row, 0, text, attribute)


def _notebook_click(event: Event) -> Any:
    """Select whichever tab the strip was clicked on."""
    notebook = event.widget
    # Anywhere in the strip, which is three rows now: the box tops, the
    # labels, and the frame edge the selected tab opens into. It used to be
    # one row, and the test for it was still `event.y != 0`, so a click on a
    # tab's own label did nothing.
    if not isinstance(notebook, Notebook) or not 0 <= event.y < STRIP_HEIGHT:
        return None
    index = notebook._tab_at(event.x)
    if index is not None:
        notebook.select(index)
        return "break"
    return None


def _notebook_step(notebook: Notebook, step: int) -> Any:
    """Move the selection along the shown tabs, wrapping as Tk's does."""
    shown = notebook._shown
    if not shown or notebook._current is None:
        return None
    place = shown.index(notebook._current)
    notebook.select(shown[(place + step) % len(shown)])
    return "break"


def _notebook_next(event: Event) -> Any:
    """Right, or Control-Tab: the next tab."""
    notebook = event.widget
    return _notebook_step(notebook, 1) if isinstance(notebook, Notebook) else None


def _notebook_previous(event: Event) -> Any:
    """Left: the previous tab."""
    notebook = event.widget
    return _notebook_step(notebook, -1) if isinstance(notebook, Notebook) else None


#: The tree column, which holds the item text rather than a value.
TREE_COLUMN = "#0"

#: What marks a branch that can be opened, and one that is open. Two cells
#: of every indented row, so that a row's depth reads at a glance.
CLOSED_MARKER = "▸"
OPEN_MARKER = "▾"

#: Cells of indentation per level of depth.
INDENT = 2

#: How many rows a treeview asks for when nothing says. Tk's default.
TREE_HEIGHT = 10

#: How wide a data column is when nothing says. Tk's default is 200 pixels;
#: on a character grid that is a cell count, and twenty is about the same
#: share of a default window.
COLUMN_WIDTH = 20


def _as_tags(value: Any) -> tuple[str, ...]:
    """Normalise a ``tags`` value to a tuple, as Tk reports it.

    A bare string is one tag, not a sequence of characters: measured,
    ``tags="single"`` reads back from real ttk as ``('single',)``.
    """
    if not value:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(tag) for tag in value)


@dataclass
class _Item:
    """One row of a treeview.

    Attributes:
        iid: Its identifier, generated or given.
        parent: The iid of its parent, or ``""`` at the top level.
        options: text, values, open, tags - what ``item()`` reads and writes.
        children: The iids below it, in order.
        detached: True once ``detach`` has taken it out of the tree. It still
            exists, which is what separates detach from delete.
    """

    iid: str
    parent: str
    options: dict[str, Any]
    children: list[str] = field(default_factory=list)
    detached: bool = False


def _as_words(value: Any) -> list[str]:
    """A list-valued option as its words: ``"a b"`` and ``("a", "b")`` alike.

    Tk reads ``-columns`` and ``-displaycolumns`` as Tcl lists, so a string is
    split on whitespace rather than taken as a sequence of characters, which is
    what iterating it would do.
    """
    if isinstance(value, str):
        return value.split()
    return [str(word) for word in value]


def _tcl_integer(value: Any) -> int:
    """``value`` read as Tcl reads an integer option, or Tk's refusal."""
    try:
        return int(str(value).strip())
    except ValueError:
        raise TclError(f'expected integer but got "{value}"') from None


def _displayed(columns: Any, displaycolumns: Any) -> list[str]:
    """The data columns ``displaycolumns`` draws, by name, in its order.

    Measured on Tk 9.0.2. ``#all`` alone is every column in data order; any
    other entry is a column's name or its index in ``-columns``, and the same
    column may be listed twice and is drawn twice. ``()`` draws none. Display
    identifiers are refused, ``#all`` among others too, and ``#0`` with them:

    * ``Invalid column index "zz"`` - not a column, nor an integer
    * ``Column index "5" out of bounds`` - an integer past the columns, or
      below zero
    """
    names = _as_words(columns)
    words = _as_words(displaycolumns)
    if words == ["#all"]:
        return names
    shown = []
    for word in words:
        if word in names:
            shown.append(word)
            continue
        # Tcl's integers, not Python's: "1_0" and "1.0" are not column indices.
        digits = word.lstrip("+-")
        if not (digits.isascii() and digits.isdigit()):
            raise TclError(f'Invalid column index "{word}"')
        index = int(word)
        if not 0 <= index < len(names):
            raise TclError(f'Column index "{word}" out of bounds')
        shown.append(names[index])
    return shown


class Treeview(Widget, tkcurses.Frame, tkcurses.XView, tkcurses.YView):
    """A hierarchy of rows, with columns. ``ttk.Treeview``.

    **It reports ``Treeview``, not ``TTreeview``.** Measured: it is the one
    themed widget without the T, and since binding tags name one class, a
    widget reporting the wrong name gets no class bindings at all. That trap
    has bitten five times in this library; this is the widget where the
    spelling itself is the trap.

    **The event rules are per widget, not per library.** Three widgets in
    this cycle answer differently, and none can be guessed from another:

    =========================  =============================================
    ``<<ComboboxSelected>>``   never on ``set()`` - a gesture only
    ``<<NotebookTabChanged>>`` on ``select()``, but only on a real change
    ``<<TreeviewSelect>>``     on ``selection_set()`` **every time**, a
                               no-op selection included
    ``<<TreeviewOpen>>``       never on ``item(open=True)`` - a gesture only
    =========================  =============================================

    **``detach`` is not ``delete``.** A detached item leaves the tree and
    ``exists()`` still answers True for it; ``move`` puts it back. Only
    ``delete`` makes it stop existing.

    On a character grid a row is one line, indented by its depth, with a
    marker on a branch that can be opened. Column widths are cells rather
    than pixels; ``image``, ``imageanchor`` and ``height`` describe pixels
    and are accepted and ignored.
    """

    _value_checks: ClassVar[dict[str, Callable[[Any, Any], Any]]] = {
        "height": tkcurses._signed_distance
    }

    _ttk_class = "Treeview"

    _widget_options: ClassVar[dict[str, Any]] = {
        # Tk 9.0's alternating row tint - TkCurses-xe9.4. A boolean,
        # default 0; Tk rejects anything else with
        # 'expected boolean value but got "..."'.
        "striped": 0,
        # Tk 9.0's frozen leading rows - TkCurses-xe9.6. A count of displayed
        # rows, default 0; see _check_titles for what Tk refuses.
        "titleitems": 0,
        # And the frozen leading columns, counted with #0 - see _frozen_width.
        "titlecolumns": 0,
        # Real ttk.Treeview has -padding and ours did not. Measured widget by
        # widget rather than assumed: ttk carries it on Label, Notebook,
        # Treeview and LabeledScale, and NOT on Separator, Sizegrip,
        # Progressbar, Combobox or Scale - so it is added to the two that
        # lacked it and to nothing else.
        "padding": "",
        "columns": (),
        "displaycolumns": ("#all",),
        "show": ("tree", "headings"),
        "height": TREE_HEIGHT,
        "selectmode": "extended",
        # A tree is something you walk with the arrows, so it takes the
        # keyboard. Frame's default is False, and inheriting it left the
        # widget unreachable by Tab.
        "takefocus": True,
        # Without these a tree cannot be attached to a scrollbar, which is how
        # a tree is used in almost every program that has one:
        #
        #     tree = ttk.Treeview(root, yscrollcommand=bar.set)
        #     bar = ttk.Scrollbar(root, command=tree.yview)
        #
        # The first line raised "unknown option" until TkCurses-ale. They are
        # not Tk 9.0 additions, they are the ordinary scroll callbacks, and
        # this is built on Frame which has none.
        "yscrollcommand": None,
        "xscrollcommand": None,
    }

    #: What ``item()`` answers for, with Tk's defaults.
    _item_options: ClassVar[dict[str, Any]] = {
        "text": "",
        "values": (),
        "open": 0,
        "tags": "",
        "image": "",
    }

    #: What ``tag_configure()`` answers for, with Tk's defaults.
    #:
    #: Seven, measured against Tcl/Tk 9.0.2 - not the two the issue that asked
    #: for this named. ``stripedbackground`` is the one that matters: the
    #: manual calls it *"the cell or item background color for alternate
    #: lines, if -striped is true"*, which makes striping a TAG feature rather
    #: than a widget one. TkCurses-xe9.4 read the style for it because there
    #: was no tag machinery to read instead; :meth:`_stripe_attribute` is
    #: where the two meet.
    _tag_options: ClassVar[dict[str, Any]] = {
        "background": "",
        "foreground": "",
        "font": "",
        "image": "",
        "imageanchor": "",
        "padding": "",
        "stripedbackground": "",
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``columns``, ``show``, ``height``, ``selectmode``,
                ``style``, and the standard options.
        """
        self._items: dict[str, _Item] = {}
        self._roots: list[str] = []
        # Insertion-ordered on purpose: Tk breaks ties between tags by
        # creation order, earliest first, so this dict IS the priority list.
        self._tags: dict[str, dict[str, Any]] = {}
        self._tag_bindings: dict[str, dict[str, Any]] = {}
        # One widget binding per sequence any tag binds, however many tags
        # bind it: the dispatcher reads _tag_bindings when the event arrives.
        self._tag_dispatch: dict[str, Any] = {}
        self._selection: list[str] = []
        self._focus = ""
        self._headings: dict[str, dict[str, Any]] = {}
        self._columns: dict[str, dict[str, Any]] = {}
        self._counter = 0
        self._top = 0
        #: Cells the columns are scrolled left by. TkCurses-xe9.6.
        self._left = 0
        kw.setdefault("relief", "sunken")
        self._check_titles(tkcurses._given(cnf, kw))
        self._check_display(tkcurses._given(cnf, kw))
        super().__init__(master, cnf, name=name, **kw)
        self._install_class_bindings()

    def _install_class_bindings(self) -> None:
        """Clicking a row selects it; clicking a marker opens the branch."""
        if self._ttk_class in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(self._ttk_class)
        bind = self.bind_class
        bind(self._ttk_class, "<Button-1>", _treeview_click)
        bind(self._ttk_class, "<Key-Down>", _treeview_down)
        bind(self._ttk_class, "<Key-Up>", _treeview_up)
        bind(self._ttk_class, "<Key-Right>", _treeview_expand)
        bind(self._ttk_class, "<Key-Left>", _treeview_collapse)
        # Tk binds <MouseWheel> and these three forms of it. Modifiers match
        # exactly, so each needs its own binding. TkCurses-94fn.
        for modifiers, axis, units in _TREEVIEW_WHEEL:
            for button, sign in ((4, -1), (5, 1)):
                bind(
                    self._ttk_class,
                    f"<{modifiers}Button-{button}>",
                    functools.partial(_treeview_wheel, axis, sign * units),
                )

    # -------------------------------------------------------------- the tree

    def insert(
        self,
        parent: str = "",
        index: Any = "end",
        *,
        iid: str | None = None,
        **kw: Any,
    ) -> str:
        """Add a row and return its identifier.

        Args:
            parent: The iid to add under, or ``""`` for the top level.
            index: Where among the siblings, or ``"end"``.
            iid: An identifier to use; one is generated when omitted.
            **kw: ``text``, ``values``, ``open``, ``tags``.

        Raises:
            TclError: If ``iid`` is already in use, or ``parent`` is not.
        """
        kw = tkcurses._given(None, kw)
        if parent and parent not in self._items:
            raise TclError(f"Item {parent} not found")
        if iid is None:
            self._counter += 1
            iid = f"I{self._counter:03d}"
            while iid in self._items:
                self._counter += 1
                iid = f"I{self._counter:03d}"
        elif iid in self._items:
            raise TclError(f"Item {iid} already exists")
        item = _Item(iid, parent, {**self._item_options, **self._checked_item(kw)})
        self._items[iid] = item
        self._place_in(parent, iid, index)
        self._redraw()
        return iid

    def _place_in(self, parent: str, iid: str, index: Any) -> None:
        """Put ``iid`` among ``parent``'s children at ``index``."""
        siblings = self._children_of(parent)
        position = len(siblings) if str(index) == "end" else int(index)
        siblings.insert(max(0, min(position, len(siblings))), iid)

    def _children_of(self, parent: str) -> list[str]:
        """The mutable child list of ``parent``, or of the top level."""
        if not parent:
            return self._roots
        return self._items[parent].children

    def delete(self, *items: str) -> None:
        """Remove rows and everything under them, for good."""
        for iid in items:
            self._delete_one(iid)
        self._redraw()

    def _delete_one(self, iid: str) -> None:
        """Remove one row and its descendants from the tree and the index."""
        item = self._items.get(iid)
        if item is None:
            return
        for child in list(item.children):
            self._delete_one(child)
        with contextlib.suppress(ValueError):
            self._children_of(item.parent).remove(iid)
        self._items.pop(iid, None)
        if iid in self._selection:
            self._selection.remove(iid)
        if self._focus == iid:
            self._focus = ""

    def detach(self, *items: str) -> None:
        """Take rows out of the tree, keeping them in existence.

        Not ``delete``: ``exists()`` still answers True afterwards, and
        ``move`` puts the row back. Measured against Tk, which is the same.

        **A detached row reports no parent.** Measured, ``parent()`` answers
        ``""`` in Tk once a row is detached, which is indistinguishable from a
        row at the top level - Tk's own quirk, and ``detached`` is what tells
        the two apart. This kept the old parent until TkCurses-67u, which made
        the difference reachable: ``set_children`` detaches whatever it omits,
        so a program could see a row that was no longer among its parent's
        children while still naming that parent.
        """
        for iid in items:
            item = self._items.get(iid)
            if item is None:
                continue
            with contextlib.suppress(ValueError):
                self._children_of(item.parent).remove(iid)
            item.parent = ""
            item.detached = True
        self._redraw()

    def move(self, item: str, parent: str, index: Any) -> None:
        """Re-parent a row, or put a detached one back."""
        entry = self._items[item]
        if not entry.detached:
            with contextlib.suppress(ValueError):
                self._children_of(entry.parent).remove(item)
        entry.detached = False
        entry.parent = parent
        self._place_in(parent, item, index)
        self._redraw()

    reattach = move

    # ------------------------------------------------------------- reading

    def get_children(self, item: str = "") -> tuple[str, ...]:
        """The rows directly under ``item``, in order."""
        return tuple(self._children_of(item))

    def parent(self, item: str) -> str:
        """The iid above ``item``, or ``""`` at the top level."""
        return self._items[item].parent

    def index(self, item: str) -> int:
        """Where ``item`` sits among its siblings.

        **Zero for a detached row**, which is what Tk answers - measured. A
        detached row is in nobody's children list, and asking the list where
        it was raised a bare ``ValueError`` out of ``list.index``: not a
        :class:`TclError`, so not something a caller could catch by name, and
        not a number either. ``detach`` could always reach it; TkCurses-67u
        made it ordinary, because ``set_children`` detaches what it omits.
        """
        entry = self._items[item]
        siblings = self._children_of(entry.parent)
        return siblings.index(item) if item in siblings else 0

    def exists(self, item: str) -> bool:
        """Whether ``item`` is a row of this tree, detached or not."""
        return item in self._items

    def next(self, item: str) -> str:
        """The sibling after ``item``, or ``""`` if it is the last."""
        return self._sibling(item, 1)

    def prev(self, item: str) -> str:
        """The sibling before ``item``, or ``""`` if it is the first."""
        return self._sibling(item, -1)

    def _sibling(self, item: str, step: int) -> str:
        """One sibling along, or ``""`` at the end.

        A detached row has no siblings to step between - it is in nobody's
        children list - so it answers ``""`` rather than raising out of
        ``list.index``. See :meth:`index`.
        """
        entry = self._items[item]
        siblings = self._children_of(entry.parent)
        if item not in siblings:
            return ""
        position = siblings.index(item) + step
        if 0 <= position < len(siblings):
            return siblings[position]
        return ""

    # ------------------------------------------------------------- options

    def item(self, item: str, option: str | None = None, **kw: Any) -> Any:
        """Read or set one row's options."""
        if kw and not tkcurses._given(None, kw):
            return None  # every option None, which tkinter drops
        kw = tkcurses._given(None, kw)
        entry = self._items[item]
        if kw:
            entry.options.update(self._checked_item(kw))
            self._redraw()
            return None
        if option is not None:
            return entry.options[option.lstrip("-")]
        return dict(entry.options)

    def set(self, item: str, column: str | None = None, value: Any = None) -> Any:
        """Read or write one cell of a row."""
        entry = self._items[item]
        names = self._column_names()
        values = list(entry.options["values"])
        if column is None:
            return dict(zip(names, values, strict=False))
        # Measured on Tk 9.0.2: "#1" is the first DISPLAYED column, as
        # everywhere else, and "#0" is refused - the tree column has no value.
        if str(column) == TREE_COLUMN:
            raise TclError("Display column #0 cannot be set")
        position = names.index(self._column_for(column))
        if value is None:
            return values[position] if position < len(values) else ""
        while len(values) <= position:
            values.append("")
        values[position] = value
        entry.options["values"] = tuple(values)
        self._redraw()
        return None

    def heading(self, column: str, option: str | None = None, **kw: Any) -> Any:
        """Read or set a column's heading."""
        if kw and not tkcurses._given(None, kw):
            return None  # every option None, which tkinter drops
        kw = tkcurses._given(None, kw)
        name = self._column_for(column)
        heading = self._headings.setdefault(
            name, {"text": "", "image": "", "anchor": "center", "command": ""}
        )
        if kw:
            heading.update(kw)
            self._redraw()
            return None
        if option is not None:
            return heading[option.lstrip("-")]
        return dict(heading)

    def column(self, column: str, option: str | None = None, **kw: Any) -> Any:
        """Read or set a column's geometry.

        ``width`` and ``minwidth`` are cells here rather than pixels, which
        is the only sense they have on a character grid.
        """
        if kw and not tkcurses._given(None, kw):
            return None  # every option None, which tkinter drops
        kw = tkcurses._given(None, kw)
        name = self._column_for(column)
        entry = self._columns_entry(name)
        if kw:
            if "width" in kw:
                # Every column's drawn width becomes its own width first, which
                # is what Tk's -width already is: setting one column after a
                # stretch leaves the others where they were drawn and shares
                # out only what this change frees or takes (measured, 213/193/
                # 192 then a=60 -> 257/104/237). Without it, reading each
                # width and writing it back moved the columns. TkCurses-a01.
                for span_name, start, end in self._column_spans():
                    self._columns_entry(span_name)["width"] = end - start
            entry.update(kw)
            self._redraw()
            return None
        # Tk answers with the width the column is DRAWN at, stretched - a
        # 600-pixel tree's 80-wide column reads back 213. TkCurses-a01.
        shown = {
            span_name: end - start for span_name, start, end in self._column_spans()
        }
        answer = dict(entry)
        if name in shown:
            answer["width"] = shown[name]
        if option is not None:
            return answer[option.lstrip("-")]
        return answer

    def _columns_entry(self, name: str) -> dict[str, Any]:
        """One column's stored options, made with Tk's defaults on first use."""
        return self._columns.setdefault(
            name,
            {
                "width": COLUMN_WIDTH,
                "minwidth": 1,
                "stretch": 1,
                "anchor": "w",
                "id": name,
            },
        )

    def _column_names(self) -> list[str]:
        """The data columns, in order, without the tree column.

        Data order, which is what a row's ``values`` are indexed by. The order
        they are DRAWN in is :meth:`_displayed_names`.
        """
        return _as_words(self._options["columns"])

    def _displayed_names(self) -> list[str]:
        """The data columns as drawn: ``-displaycolumns``, resolved to names."""
        return _displayed(self._options["columns"], self._options["displaycolumns"])

    def _checked_item(self, given: dict[str, Any]) -> dict[str, Any]:
        """Reject an item option Tk does not have."""
        cleaned = {}
        for key, value in given.items():
            name = key.lstrip("-")
            if name not in self._item_options:
                raise TclError(f'unknown option "-{name}"')
            if name == "values":
                cleaned[name] = tuple(value)
            elif name == "tags":
                cleaned[name] = _as_tags(value)
            else:
                cleaned[name] = value
        return cleaned

    # ---------------------------------------------------------------- tags

    def tag_configure(self, tagname: str, option: str | None = None, **kw: Any) -> Any:
        """Query or set the options of one tag.

        Three forms, all measured against real ttk:

        * ``tag_configure("warn")`` - every option, with ``""`` for each one
          never set.
        * ``tag_configure("warn", "background")`` - that option's value, or
          ``""``.
        * ``tag_configure("warn", background="red")`` - sets, returns None.

        **Naming a tag here creates it**, which is not a detail: Tk decides
        priority between tags by CREATION ORDER, so the order these calls
        happen in is what decides who wins. See :meth:`_tag_value`.
        """
        if kw and not tkcurses._given(None, kw):
            return None  # every option None, which tkinter drops
        kw = tkcurses._given(None, kw)
        options = self._tags.setdefault(tagname, dict(self._tag_options))
        if kw:
            for key, value in kw.items():
                name = key.lstrip("-")
                if name not in self._tag_options:
                    raise TclError(f'unknown option "-{name}"')
                options[name] = value
            self._redraw()
            return None
        if option is not None:
            return options[option.lstrip("-")]
        return dict(options)

    def tag_has(self, tagname: str, item: str | None = None) -> Any:
        """Which rows carry a tag, or whether one does.

        ``tag_has("warn")`` answers the tuple of rows carrying it - ``()`` for
        a tag nothing carries, which is not an error. ``tag_has("warn", iid)``
        answers a bool. Measured; the two return types from one method are
        Tk's, not a convenience.
        """
        if item is not None:
            return tagname in self._item_tags(item)
        return tuple(iid for iid in self._items if tagname in self._item_tags(iid))

    def tag_bind(
        self, tagname: str, sequence: str | None = None, callback: Any = None
    ) -> None:
        """Bind an event for every row carrying a tag.

        Returns None in all three forms, which is what tkinter does - measured,
        including the form that looks like a query. So there is nothing here to
        read the bindings back with, and nothing in tkinter to match if there
        were; the form without a callback is a query and changes nothing.

        **The binding goes on the widget, and the dispatcher picks the row.**
        A tag is not a window, so there is nothing for the binding table to
        hang a tag binding on. One ordinary ``bind`` per sequence is installed
        instead - ``add="+"``, so it joins rather than displaces whatever the
        program bound itself - and :func:`_treeview_tag_event` decides which
        row the event belongs to and runs that row's tags. Which row depends
        on the event type; see :data:`_POINTER_TAG_EVENTS`.
        """
        if sequence is None or callback is None:
            return None
        self._tag_bindings.setdefault(tagname, {})[sequence] = callback
        if sequence not in self._tag_dispatch:
            self._tag_dispatch[sequence] = self.bind(
                sequence, functools.partial(_treeview_tag_event, sequence), add="+"
            )
        return None

    def _deliver_tags(self, item: str, sequence: str, event: Event) -> None:
        """Run what one row's tags bind for one event.

        **In the order of the row's own ``tags`` list**, which is NOT the
        order :meth:`_tag_value` walks. The two orders are different on
        purpose and ``man ttk_treeview`` gives both: a tag OPTION is resolved
        by creation order, *"tags created first receive higher priority"*,
        while a tag BINDING is run *"for each of the item's tags option ...
        in order as per bindtags(n)"*. So colour comes from the oldest tag
        and callbacks run in the order the row names them.

        Every matching binding runs, and a return value stops nothing - the
        same as ``Canvas._deliver``, whose item bindings this mirrors.
        """
        for tag in self._item_tags(item):
            callback = self._tag_bindings.get(tag, {}).get(sequence)
            if callback is not None:
                callback(event)

    def _item_tags(self, item: str) -> tuple[str, ...]:
        """The tags on one row, always a tuple.

        ``tags="single"`` is a bare string to Tk and a one-tuple out of it -
        measured, ``item(iid, "tags")`` answers ``('single',)`` there and
        answered ``'single'`` here. Worth more than tidiness: iterating the
        string would have asked whether each CHARACTER was a tag.
        """
        entry = self._items.get(item)
        if entry is None:
            return ()
        return _as_tags(entry.options.get("tags", ""))

    def _tag_value(self, item: str, option: str) -> Any:
        """One tag option for a row, resolved the way Tk resolves it.

        **Earliest-created tag wins**, and it is worth saying why that is not
        what anyone would guess. ``man ttk_treeview``, TAG OPTIONS: *"tag
        priority is decided by the creation order: tags created first receive
        higher priority."* Not the last tag configured, and NOT the order of
        the row's own ``tags`` list - so this walks the tag registry, which is
        insertion-ordered, and never the row's tags.

        ``item(iid, "image")`` and the rest of the row's own options beat any
        tag, per the same paragraph. That is why the drawing code asks the row
        first and only falls back to here.

        Cell tags would come before item tags; this library has no cell
        selection yet, so there are none - TkCurses-xe9.5.
        """
        carried = set(self._item_tags(item))
        if not carried:
            return ""
        for name, options in self._tags.items():
            if name in carried and options.get(option):
                return options[option]
        return ""

    def set_children(self, item: str, *newchildren: str) -> None:
        """Replace a row's children with exactly these, in this order.

        **This reparents, and the name hides it.** Measured against Tk:

        * What it omits is DETACHED, not deleted. ``exists()`` still answers
          True for a dropped row, and ``move`` puts it back.
        * A row that belonged to another parent is MOVED here, and whatever it
          displaces is detached in turn.
        * A cycle is refused: Tk raises ``Cannot insert I001 as descendant of
          I002``, naming the row and then the parent it was offered to, and
          so does this.

        Raises:
            TclError: If a row would become its own descendant.
        """
        for iid in newchildren:
            if iid not in self._items:
                raise TclError(f"Item {iid} not found")
            if item and self._is_descendant_or_self(item, iid):
                raise TclError(f"Cannot insert {iid} as descendant of {item}")
        for dropped in list(self._children_of(item)):
            if dropped not in newchildren:
                self.detach(dropped)
        for iid in newchildren:
            entry = self._items[iid]
            if not entry.detached:
                with contextlib.suppress(ValueError):
                    self._children_of(entry.parent).remove(iid)
            entry.detached = False
            entry.parent = item
        self._children_of(item)[:] = list(newchildren)
        self._redraw()

    def _is_descendant_or_self(self, item: str, ancestor: str) -> bool:
        """Whether ``item`` is ``ancestor`` or sits below it."""
        walked = item
        while walked:
            if walked == ancestor:
                return True
            entry = self._items.get(walked)
            if entry is None:
                return False
            walked = entry.parent
        return False

    # ----------------------------------------------------------- selection

    def selection(self) -> tuple[str, ...]:
        """The selected rows, in order."""
        return tuple(self._selection)

    def selection_set(self, *items: str) -> None:
        """Select exactly these rows.

        Fires ``<<TreeviewSelect>>`` **every time**, even when the selection
        does not change - measured against Tk, and the opposite of the
        notebook, which fires only on a change.
        """
        self._selection = [iid for iid in items if iid in self._items]
        self._redraw()
        self.event_generate("<<TreeviewSelect>>")

    def selection_add(self, *items: str) -> None:
        """Add rows to the selection."""
        self.selection_set(*self._selection, *items)

    def selection_remove(self, *items: str) -> None:
        """Take rows out of the selection."""
        self.selection_set(*[iid for iid in self._selection if iid not in items])

    def selection_toggle(self, *items: str) -> None:
        """Select the unselected and unselect the selected."""
        kept = [iid for iid in self._selection if iid not in items]
        added = [iid for iid in items if iid not in self._selection]
        self.selection_set(*kept, *added)

    def focus(self, item: str | None = None) -> Any:
        """Get or set the row the keyboard is on.

        Shadows ``Misc.focus`` deliberately: on a treeview, ``focus`` is
        about rows. Tk has the same collision and resolves it the same way.
        """
        if item is None:
            return self._focus
        self._focus = item
        self._redraw()
        return None

    def see(self, item: str) -> None:
        """Scroll ``item`` into view, opening whatever hides it."""
        entry = self._items.get(item)
        if entry is None:
            return
        parent = entry.parent
        while parent:
            self._items[parent].options["open"] = 1
            parent = self._items[parent].parent
        _titles, rows = self._split_rows()
        # A title row is always in view, so seeing one moves nothing -
        # measured on Tk 9.0.2.
        if item in rows:
            position = rows.index(item)
            height = max(1, self._rows_window())
            self._top = max(min(self._top, position), position - height + 1)
        self._clamp_view()
        self._redraw()

    # -------------------------------------------------------------- scrolling

    def yview(self, *args: Any) -> Any:
        """Report or move the vertical view, as a scrollbar expects.

        Called with nothing it answers the pair of fractions a scrollbar wants.
        Called by a scrollbar it takes Tk's own arguments - ``("moveto",
        fraction)`` or ``("scroll", count, "units"|"pages")`` - which is what
        lets any scrollbar drive any widget without either knowing what the
        other is. The same contract tkcurses.Listbox and tkcurses.Text already
        implement; this copies it rather than inventing a second one.
        """
        if not args:
            return self._view_fractions()
        rows = len(self._split_rows()[1])
        if args[0] == "moveto":
            # Rounded, halves up, as Tk does; this truncated. TkCurses-md5.
            self._top = math.floor(float(args[1]) * rows + 0.5)
        elif args[0] == "scroll":
            count = int(args[1])
            step = max(1, self._rows_window()) if args[2] == "pages" else 1
            self._top += count * step
        else:  # a bare index, as Tk also accepts
            self._top = int(args[0])
        self._clamp_view()
        self._redraw()
        return None

    def xview(self, *args: Any) -> Any:
        """Report or move the horizontal view, as a scrollbar expects.

        The same contract as :meth:`yview`, in cells: ``("moveto", fraction)``,
        ``("scroll", count, "units"|"pages")`` or a bare offset. Measured on
        Tk 9.0.2, where the unit is a pixel: one unit moves one, one page moves
        the width of the part that scrolls, and ``xview(50)`` puts offset 50 at
        the left edge. Columns that fit the tree - the usual case, since they
        stretch to fill it - leave nothing to scroll, and the view stays
        ``(0.0, 1.0)``.

        Until TkCurses-xe9.6 a tree here never scrolled sideways, and columns
        wider than it were clipped where they could not be reached.
        """
        if not args:
            return self._x_fractions()
        extent = self._scrolled_width()
        if args[0] == "moveto":
            self._left = math.floor(float(args[1]) * extent + 0.5)
        elif args[0] == "scroll":
            count = int(args[1])
            step = max(1, self._scroll_window()) if args[2] == "pages" else 1
            self._left += count * step
        else:
            self._left = int(args[0])
        self._clamp_view()
        self._redraw()
        return None

    def _frozen_width(self) -> int:
        """Cells at the left that do not scroll sideways: ``-titlecolumns``.

        Measured on Tk 9.0.2, the count includes ``#0`` **even when the tree
        column is hidden**: with ``show="headings"``, 1 freezes nothing and 2
        freezes the first data column. The columns are the first in DISPLAY
        order, so read here from the spans as drawn rather than from
        ``-columns``: measured, ``displaycolumns=("c", "a", "b")`` with 2
        frozen freezes ``#0`` and ``c``. A count past the last column freezes
        them all, and then nothing scrolls.

        The cell that joins the last frozen column to the next is frozen with
        it, as it belongs to that column for a click (see
        :meth:`identify_column`).
        """
        count = int(self._options["titlecolumns"])
        spans = self._column_spans()
        drawn = [name for name, _start, _end in spans if name != TREE_COLUMN]
        frozen = set([TREE_COLUMN, *drawn][:count])
        width = 0
        for index, (name, _start, end) in enumerate(spans):
            if name not in frozen:
                break
            width = end + (1 if index + 1 < len(spans) else 0)
        return width

    def _scrolled_width(self) -> int:
        """Cells of columns that scroll sideways: all but the frozen ones.

        None at all before the tree has been laid out. Measured on Tk 9.0.2:
        a tree never shown answers ``(0.0, 1.0)`` and ignores ``moveto`` and
        ``scroll``, rather than reporting every column as out of view.
        """
        if self._rows_area().width <= 0:
            return 0
        spans = self._column_spans()
        total = spans[-1][2] if spans else 0
        return max(0, total - self._frozen_width())

    def _scroll_window(self) -> int:
        """Cells of the rows area that the scrolling columns are seen through."""
        return max(0, self._rows_area().width - self._frozen_width())

    def _x_fractions(self) -> tuple[float, float]:
        """Where the view is across the columns that scroll, as Tk reports it.

        Measured on Tk 9.0.2: the fractions are of the scrolling part only,
        so frozen columns change them - 100-pixel columns in a 298-pixel tree
        report ``(0.0, 0.596)``, and ``(0.0, 0.327)`` once two are frozen.
        """
        extent = self._scrolled_width()
        if extent <= 0:
            return (0.0, 1.0)
        return (
            self._left / extent,
            min(1.0, (self._left + self._scroll_window()) / extent),
        )

    def _content_x(self, offset: int) -> int:
        """The column-span position seen ``offset`` cells into the rows area."""
        frozen = self._frozen_width()
        return offset if offset < frozen else offset + self._left

    def _view_x(self, position: int, frozen: bool) -> int:
        """Where column-span ``position`` is drawn, in cells into the rows area.

        A scrolling column can come out left of the frozen ones, or of the
        tree itself; Tk's bbox answers such positions unclipped, measured
        (``-101`` for a column scrolled a column's width past the edge).
        """
        return position if frozen else position - self._left

    def _in_view(self, line: str, width: int) -> str:
        """The part of a whole row of columns that the view shows."""
        frozen = self._frozen_width()
        line = line.ljust(frozen)
        return (line[:frozen] + line[frozen + self._left :])[:width]

    def _view_fractions(self) -> tuple[float, float]:
        """Where the visible rows are, as two fractions of the rows that scroll.

        Measured on Tk 9.0.2: title rows are not counted, so 20 rows with 3
        frozen and 5 more in view report ``(0.0, 5/17)``.
        """
        rows = len(self._split_rows()[1])
        if rows <= 0:
            return (0.0, 1.0)
        height = max(1, self._rows_window())
        return (self._top / rows, min(1.0, (self._top + height) / rows))

    def _split_rows(self) -> tuple[list[str], list[str]]:
        """The displayed rows as ``(title rows, rows that scroll)``.

        ``-titleitems`` counts DISPLAYED rows in display order, measured on
        Tk 9.0.2: with two frozen and an open first branch, the branch and
        its first child stay put; closed, the branch and the next top-level
        row do. A count past the end freezes them all.
        """
        rows = self._visible()
        count = min(int(self._options["titleitems"]), len(rows))
        return rows[:count], rows[count:]

    def _drawn_titles(self) -> list[str]:
        """The title rows that fit, which is all of them unless the tree is short."""
        return self._split_rows()[0][: self._content_height()]

    def _rows_window(self) -> int:
        """How many rows that scroll the tree has room for, under its titles."""
        return max(0, self._content_height() - len(self._drawn_titles()))

    def _clamp_view(self) -> None:
        """Keep the visible rows inside the tree, and the columns too."""
        height = max(1, self._rows_window())
        rows = len(self._split_rows()[1])
        self._top = max(0, min(self._top, max(0, rows - height)))
        across = self._scrolled_width() - self._scroll_window()
        self._left = max(0, min(self._left, max(0, across)))

    def _publish_view(self) -> None:
        """Tell the scrollbars where the view is, if any are listening."""
        vertical = self._options["yscrollcommand"]
        if vertical is not None:
            first, last = self._view_fractions()
            vertical(first, last)
        horizontal = self._options["xscrollcommand"]
        if horizontal is not None:
            first, last = self._x_fractions()
            horizontal(first, last)

    # ------------------------------------------------------------ painting

    def _visible(self) -> list[str]:
        """Every row that is drawn, top to bottom.

        A row is here only if every branch above it is open, which is what
        makes a closed branch hide a subtree rather than merely mark it.
        """
        rows: list[str] = []

        def walk(iids: list[str]) -> None:
            for iid in iids:
                item = self._items[iid]
                if item.detached:
                    continue
                rows.append(iid)
                if item.options["open"]:
                    walk(item.children)

        walk(self._roots)
        return rows

    def _depth(self, iid: str) -> int:
        """How many branches ``iid`` sits under."""
        depth = 0
        parent = self._items[iid].parent
        while parent:
            depth += 1
            parent = self._items[parent].parent
        return depth

    def _rows_area(self) -> Rect:
        """Where the rows go, **in this widget's own cells**.

        Not ``_content_rect``, which is in screen cells: mixing the two puts
        everything at the widget's position *again*, so a treeview at row 3
        drew its heading at row 7 and its last row on top of its own bottom
        border. It only shows when the widget is not at the origin, which is
        why the unit tests were happy and the first scenario was not.
        """
        edge = BORDER_WIDTH if self._border_drawn else 0
        padx, pady = int(self._options["padx"]), int(self._options["pady"])
        return Rect(
            edge + padx,
            edge + pady,
            max(0, self._rect.width - 2 * (edge + padx)),
            max(0, self._rect.height - 2 * (edge + pady)),
        )

    def _content_height(self) -> int:
        """How many rows the widget can draw, headings taken off."""
        area = self._rows_area()
        return max(0, area.height - (1 if self._shows_headings else 0))

    def _shown(self) -> tuple[str, ...]:
        """What ``-show`` asks for, whether given as words or as a sequence.

        ``tuple("tree")`` is ``("t", "r", "e", "e")``, so reading the option
        directly made ``show="tree"`` ask for neither the tree column nor the
        headings and draw an empty box. Measured on real ttk, which parses the
        string into words: ``show="tree"`` reads back as ``("tree",)`` and
        ``show="tree headings"`` as both. Found by writing a scrollbar test that
        used the natural string form (TkCurses-ale).
        """
        value = self._options["show"]
        if isinstance(value, str):
            return tuple(value.split())
        return tuple(value)

    @property
    def _shows_headings(self) -> bool:
        """Whether a heading row is drawn."""
        return "headings" in self._shown()

    @property
    def _shows_tree(self) -> bool:
        """Whether the tree column is drawn."""
        return "tree" in self._shown()

    def _column_spans(self) -> list[tuple[str, int, int]]:
        """Where each column sits, in cells from the left of the rows area.

        ``[(name, start, end)]`` left to right, ``end`` exclusive, the tree
        column ``#0`` first when ``show`` includes it.

        **The one source of truth for the horizontal layout.** It was implicit
        before this: :meth:`_row_text` and :meth:`_heading_text` each padded
        every column to its width and joined with a space, so a column's
        position was ``sum(widths before it) + one space each`` - computed
        twice, written down nowhere, and impossible for
        :meth:`identify_column` to ask about. Both now compose from this, so a
        click and a repaint cannot disagree about where a column is.

        Absolute, with no scroll offset: these are positions along the whole
        row of columns. What the view shows of them is :meth:`_in_view`,
        :meth:`_content_x` and :meth:`_view_x`, which every painter and every
        identify answer goes through - TkCurses-xe9.6, which is when the tree
        began scrolling sideways and the offset had to be applied somewhere.
        """
        spans: list[tuple[str, int, int]] = []
        position = 0
        names = ([TREE_COLUMN] if self._shows_tree else []) + self._displayed_names()
        widths = self._stretched_widths(names)
        for name, width in zip(names, widths, strict=True):
            spans.append((name, position, position + width))
            # Plus the single space that joins one column to the next, which is
            # what " ".join puts there.
            position += width + 1
        return spans

    def _stretched_widths(self, names: list[str]) -> list[int]:
        """Each shown column's width once ``-stretch`` has filled the rows area.

        A column's ``-width`` is where it starts. Measured on Tk 9.0.2, a tree
        600 pixels wide whose three columns ask for 80, 60 and 60 draws them
        213, 193 and 192 - **the surplus is shared out evenly**, not in
        proportion to width (100/50/50 gets the same +133/+133/+132), with the
        odd units going to the leftmost. A column with ``stretch=0`` takes no
        share and the others split it; with none stretchable nothing grows; a
        hidden ``#0`` takes none either. Until TkCurses-a01 ``stretch`` was
        stored and never read, and the space past the last column was blank.

        **A resize keeps no state, where Tk's does.** Tk carries a running
        slack total between layouts, so its answer can depend on history: a
        tree created narrower than its columns does not shrink them at all,
        while one that has been wider shrinks below its configured widths,
        down to ``-minwidth``. Here a column never draws narrower than its
        ``-width``, and what does not fit is clipped. Every first layout and
        every grow-and-shrink-back Tk was measured doing comes out the same;
        ARCHITECTURE.md has the cases that do not. Setting a width is the one
        place state is kept, as in Tk - see :meth:`column`.
        """
        widths = [max(0, int(self._columns_entry(name)["width"])) for name in names]
        # The joining spaces take room too: n columns, n - 1 of them.
        surplus = self._rows_area().width - (sum(widths) + max(0, len(names) - 1))
        growing = [
            i
            for i, name in enumerate(names)
            if self.getboolean(self._columns_entry(name)["stretch"])
        ]
        if surplus <= 0 or not growing:
            return widths
        share, odd = divmod(surplus, len(growing))
        for rank, i in enumerate(growing):
            widths[i] += share + (1 if rank < odd else 0)
        return widths

    def _cell_text(self, iid: str, name: str) -> str:
        """What one cell of one row holds, before it is padded."""
        item = self._items[iid]
        if name == TREE_COLUMN:
            marker = " "
            if item.children:
                marker = OPEN_MARKER if item.options["open"] else CLOSED_MARKER
            return (
                " " * (INDENT * self._depth(iid)) + marker + str(item.options["text"])
            )
        values = tuple(item.options["values"])
        index = self._column_names().index(name)
        return str(values[index]) if index < len(values) else ""

    def _row_text(self, iid: str, width: int) -> str:
        """One row as it is drawn: the marker, the text, then the columns.

        Each cell is padded to its own span, which is what keeps the data
        columns under their own headings - otherwise a row would start its
        values wherever its text happened to end.
        """
        pieces = [
            self._cell_text(iid, name).ljust(end - start)
            for name, start, end in self._column_spans()
        ]
        return self._in_view(" ".join(pieces), width)

    def _heading_text(self, width: int) -> str:
        """The heading row, drawn above the rows when ``show`` asks for it."""
        pieces = [
            str(self.heading(name, "text")).ljust(end - start)
            for name, start, end in self._column_spans()
        ]
        return self._in_view(" ".join(pieces), width)

    def identify_column(self, x: int) -> str:
        """The display column identifier at ``x``, or ``""`` outside them all.

        ``"#0"`` for the tree column, then ``"#1"`` for the first data column
        and so on - Tk's display identifiers, not our internal names, measured:
        ``identify_column`` on a tree with columns ``("a","b")`` answers
        ``"#1"`` and ``"#2"``, never ``"a"``.

        Two edges differ from Tk and both are measured and recorded:

        * The single cell that JOINS one column to the next belongs to the
          column on its left. Tk's columns abut, so it has no such cell; the
          gap is an artefact of drawing a character grid, and leaving it
          answering ``""`` would make one cell in every gap unclickable.
        * Past the last column this answers ``""``. Tk's columns stretch to
          the widget's edge, and so do ours since TkCurses-a01 - the spans
          grew and this followed with no change here - so that only happens
          now when no column is stretchable, or the columns overflow.
        """
        area = self._rows_area()
        if not 0 <= x - area.x < area.width:
            return ""
        offset = self._content_x(x - area.x)
        spans = self._column_spans()
        # No "past the last column" test here: the walk below falls through to
        # "" for any offset beyond the final span, so adding one could not be
        # mutated into failing - it was in the first version and came out
        # again for exactly that reason. The negative and empty cases DO need
        # saying: a negative offset would match the first span's upper bound.
        if offset < 0 or not spans:
            return ""
        for index, (name, _start, end) in enumerate(spans):
            if offset < end + (1 if index + 1 < len(spans) else 0):
                return (
                    TREE_COLUMN
                    if name == TREE_COLUMN
                    else f"#{index + (0 if self._shows_tree else 1)}"
                )
        return ""

    def identify_row(self, y: int) -> str:
        """The item at ``y``, or ``""`` where there is none.

        ``""`` for the heading row as well as past the last item - measured:
        ``identify_row`` over the heading answers empty while
        ``identify_region`` answers ``"heading"``, so the two are independent.
        """
        return self._row_at(y) or ""

    def identify_region(self, x: int, y: int) -> str:
        """Which part of the tree is at ``(x, y)``.

        One of ``"heading"``, ``"tree"``, ``"cell"`` or ``"nothing"``.

        **Never ``"separator"``**, and that is decided rather than overlooked.
        Tk documents separator as the space between two column headings, for
        dragging a column's width; this widget draws no separators and offers
        no such drag, so returning it would name something that is not there.
        A caller testing for it will simply never match. TkCurses-p9h.
        """
        area = self._rows_area()
        if not area.contains_point(Point(x, y)):
            return "nothing"
        if self._shows_headings and y == area.y:
            return "heading"
        if self._row_at(y) is None:
            return "nothing"
        column = self.identify_column(x)
        if not column:
            return "nothing"
        return "tree" if column == TREE_COLUMN else "cell"

    def identify_element(self, x: int, y: int) -> str:
        """The style element at ``(x, y)`` - always ``""`` here.

        Tk answers the name of a themed element: ``padding``, ``text``,
        ``image``. Those names come from Tk's element tree, which this library
        does not have - its themes are glyph sets, not layouts of named
        elements - and Tk documents no fixed set of return values either, so
        nothing portable can be written against them.

        Present and empty rather than absent, because ``identify`` dispatches
        to it and a caller asking politely deserves an answer rather than an
        AttributeError. TkCurses-p9h.
        """
        del x, y
        return ""

    def identify(self, component: str, x: int, y: int) -> Any:  # type: ignore[override]
        """Tk's dispatcher: ``identify(component, x, y)``.

        ``region``, ``item``, ``column``, ``cell`` and ``element``, plus
        ``row`` as Tk's own obsolescent synonym for ``item``.

        ``cell`` is here deliberately even though **tkinter has no wrapper for
        it**: Tk documents it, it answers the ``(item, column)`` pair that cell
        work actually wants, and composing ``identify_row`` with
        ``identify_column`` by hand - which is all a tkinter program can do -
        is the sort of thing a compatibility layer should spare its callers.

        Raises:
            TclError: For a component Tk does not define, with Tk's wording.
        """
        if component in ("item", "row"):
            return self.identify_row(y)
        if component == "column":
            return self.identify_column(x)
        if component == "region":
            return self.identify_region(x, y)
        if component == "element":
            return self.identify_element(x, y)
        if component == "cell":
            item = self.identify_row(y)
            column = self.identify_column(x)
            return (item, column) if item and column else ""
        raise TclError(
            f'bad command "{component}": must be '
            "region, item, column, row, cell or element"
        )

    def bbox(
        self, item: str, column: str | None = None
    ) -> tuple[int, int, int, int] | str:
        """Where an item is drawn, as ``(x, y, width, height)`` in this widget.

        ``""`` when the item is not visible - scrolled out of view, or a
        descendant of a closed item - which is Tk's documented answer and was
        measured: ``bbox`` of a child under a closed parent is empty, and the
        same child answers a rectangle once the parent is opened.

        With ``column``, the rectangle of that cell within the row. The column
        may be named or given as a display identifier: Tk accepts
        ``bbox(item, "#0")`` as well as ``bbox(item, "size")``, measured.

        Raises:
            TclError: If the item does not exist. Measured - Tk raises
                ``Item nosuch not found`` rather than answering empty, which
                is the opposite of how it treats an invisible one.
        """
        if item not in self._items:
            raise TclError(f"Item {item} not found")
        titles = self._drawn_titles()
        rows = self._split_rows()[1]
        if item in titles:
            position = titles.index(item)
        elif item in rows:
            position = len(titles) + rows.index(item) - self._top
            if position < len(titles):
                return ""
        else:
            return ""
        area = self._rows_area()
        height = self._content_height()
        if position >= height:
            return ""
        row = area.y + position + (1 if self._shows_headings else 0)
        if column is None:
            return (area.x, row, area.width, 1)
        name = self._column_for(column)
        frozen = self._frozen_width()
        for candidate, start, end in self._column_spans():
            if candidate == name:
                x = self._view_x(start, start < frozen)
                return (area.x + x, row, end - start, 1)
        return ""

    def _column_for(self, column: str) -> str:
        """The internal column name for a name or a display identifier.

        ``"#0"`` is the tree column; ``"#1"`` onwards are the data columns in
        DISPLAY order, so under ``displaycolumns=("c", "a")`` ``"#1"`` is
        ``c``. Tk accepts either spelling wherever a column is named, and
        ``bbox(item, "#0")`` was measured answering the tree column's
        rectangle.

        Raises:
            TclError: For ``"#n"`` past the displayed columns. Measured on Tk
                9.0.2, ``column``, ``heading`` and ``set`` all answer
                ``Column #9 out of range``.
        """
        text = str(column)
        if not text.startswith("#"):
            return text
        if text == TREE_COLUMN:
            return TREE_COLUMN
        try:
            index = int(text[1:]) - 1
        except ValueError:
            return text
        names = self._displayed_names()
        if not 0 <= index < len(names):
            raise TclError(f"Column {text} out of range")
        return names[index]

    def _row_at(self, y: int) -> str | None:
        """Which row a click landed on, if any."""
        area = self._rows_area()
        offset = y - area.y - (1 if self._shows_headings else 0)
        # Every title, not just those drawn: measured on Tk 9.0.2, identify
        # keeps counting rows below the bottom of the tree, titles included
        # when they overflow it.
        titles, rows = self._split_rows()
        if 0 <= offset < len(titles):
            return titles[offset]
        position = self._top + offset - len(titles)
        if offset >= 0 and position < len(rows):
            return rows[position]
        return None

    def _marker_column(self, iid: str) -> int:
        """Where the open/closed marker of ``iid`` is drawn, or -1 if hidden.

        The marker is in the tree column, so it scrolls with it: a click at
        the place it would be with the view at the left must not open a
        branch whose marker is not there. -1 is never a click's column.
        """
        area = self._rows_area()
        position = INDENT * self._depth(iid)
        # #0 is the first column, so it is frozen whole or not at all: a
        # marker never scrolls under the frozen ones, only off the edge.
        x = self._view_x(position, position < self._frozen_width())
        if x < 0 or x >= area.width:
            return -1
        return area.x + x

    def _redraw(self) -> None:
        """Paint the headings and whichever rows are in view."""
        # Every change that repaints also clamps the view and tells the
        # scrollbar where it is. Done here rather than in insert, delete, move,
        # open and close separately, because driving the widget showed both
        # halves going wrong: thirty rows could go in while the bar still read
        # (0.0, 1.0) - a full-size thumb on a tree showing a sixth of itself -
        # and deleting twenty rows left _top past the end, so the tree reported
        # a first fraction of 1.5. A repaint must not draw from a stale view
        # either, so the clamp belongs here with it.
        self._clamp_view()
        self._publish_view()
        window = self._window
        if window is None or self.tk.screen is None:
            return
        area = self._rows_area()
        if area.is_empty:
            return
        attribute = self._themed_attribute()
        left = area.x
        top = area.y
        dispatcher = CursesDispatcher.get()
        with contextlib.suppress(curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._border_drawn:
                self._draw_border(
                    dispatcher, window, self._rect.width, self._rect.height, attribute
                )
            row = top
            if self._shows_headings:
                self._write_line(
                    dispatcher,
                    window,
                    row,
                    left,
                    self._heading_text(area.width),
                    attribute | curses.A_BOLD,
                )
                row += 1
            rows = (
                self._drawn_titles()
                + self._split_rows()[1][self._top : self._top + self._rows_window()]
            )
            for offset, iid in enumerate(rows):
                self._write_line(
                    dispatcher,
                    window,
                    row,
                    left,
                    self._row_text(iid, area.width).ljust(area.width),
                    self._row_attribute(iid, offset, attribute),
                )
                row += 1

    def _check_titles(self, given: dict[str, Any]) -> None:
        """Refuse a ``titleitems`` or ``titlecolumns`` Tk would refuse.

        Measured on Tk 9.0.2: not an integer is ``expected integer but got
        "x"``, and a negative count is ``"-1" is out of range``. A count past
        the number of rows is kept as given and freezes them all.
        """
        if "titleitems" in given:
            count = _tcl_integer(given["titleitems"])
            if count < 0:
                raise TclError(f'"{count}" is out of range')
        # The same check, and Tk's message names a COLUMN: "#-1".
        if "titlecolumns" in given:
            count = _tcl_integer(given["titlecolumns"])
            if count < 0:
                raise TclError(f'"#{count}" is out of range')

    def _check_display(self, given: dict[str, Any]) -> None:
        """Refuse a ``columns`` and ``displaycolumns`` pair Tk would refuse.

        Either may change alone, so the pair is checked as it would stand:
        dropping a displayed column from ``-columns`` is refused as surely as
        naming one that does not exist. Tk 9.0.2 refuses that case too, but
        only after applying half of it - ``-columns`` reads back unchanged
        while ``set(item)`` already answers with the new columns. Here nothing
        changes. Measured; ARCHITECTURE.md has it.
        """
        if "columns" not in given and "displaycolumns" not in given:
            return
        current = getattr(self, "_options", self._widget_options)
        _displayed(
            given.get("columns", current["columns"]),
            given.get("displaycolumns", current["displaycolumns"]),
        )

    def _striped(self) -> bool:
        """Whether alternate rows are tinted.

        The value is parsed the way Tcl reads a boolean, and
        :meth:`configure` rejects anything else when it is set - Tk raises
        ``expected boolean value but got "nonsense"`` at configure time, and so
        does this. Most boolean options in this library are not validated at
        all (``exportselection="nonsense"`` is accepted and stored); that wider
        gap is TkCurses-861 rather than something to fix one option at a time,
        but there is no reason for a new option to join it.
        """
        return self.getboolean(self._options["striped"])

    def _row_attribute(self, iid: str, offset: int, attribute: int) -> int:
        """How one row is drawn: selected, striped, or plain.

        **Selection wins.** A selected row is drawn reversed and never tinted,
        because reverse-and-dim together is whatever the terminal decides and
        the selection is the more important of the two signals. The same
        reasoning as the focused entry border dropping A_DIM before adding
        A_BOLD.

        The stripe falls on odd rows of what is ON SCREEN, so the banding stays
        put as the tree scrolls rather than crawling. Tk hands its row element
        a ``-rownumber`` and lets the theme decide; which parity it picks, and
        whether it counts displayed or absolute rows, could not be measured
        without eyes on a GUI and is recorded as open on TkCurses-xe9.4.
        """
        if iid in self._selection:
            return attribute | curses.A_REVERSE
        if self._striped() and offset % 2:
            return self._stripe_attribute(attribute, iid)
        return self._tag_attribute(attribute, iid)

    def _tag_attribute(self, attribute: int, iid: str) -> int:
        """``attribute`` recoloured by whichever tag wins for this row.

        Only the two options a terminal can honour. ``font``, ``image``,
        ``imageanchor`` and ``padding`` are accepted and stored by
        :meth:`tag_configure` - a program that sets them keeps working - and
        there is nothing here to do with them: one cell is one cell.
        """
        background = self._tag_value(iid, "background")
        foreground = self._tag_value(iid, "foreground")
        if not background and not foreground:
            return attribute
        return self._recoloured(attribute, foreground, background)

    def _recoloured(self, attribute: int, foreground: Any, background: Any) -> int:
        """``attribute`` with whichever of the two colours was given.

        Falls back to the widget's own foreground and background for the half
        that was not, so a tag setting only one colour does not blank the
        other.
        """
        colors = self.tk.colors
        if colors is None:
            return attribute
        fallback_fg = str(self._options["foreground"] or "white")
        fallback_bg = str(self._options["background"] or "black")
        # REPLACE the colour field, never OR into it: the row's attribute
        # already carries the widget's own pair, and two pair numbers OR'd
        # are a third pair - a cyan tag drew red. TkCurses-mur.
        return with_colors(
            attribute,
            colors.attribute_for(
                str(foreground or fallback_fg), str(background or fallback_bg)
            ),
        )

    def _stripe_attribute(self, attribute: int, iid: str = "") -> int:
        """The tint for a striped row.

        **The winning tag's ``stripedbackground`` first**, because that is
        where Tk puts the option: the manual describes it as a tag option,
        *"the background color for alternate lines, if -striped is true"*.
        TkCurses-xe9.4 built the stripe before any tag machinery existed and
        could only read the style, which is the half of the feature Tk reaches
        when no tag answers.

        Then ``Treeview``'s ``stripedbackground`` from the style - measured,
        ``style.lookup("Treeview", "stripedbackground")`` answers ``#e8e8e8``
        against a white background.

        Otherwise **dim**, and that fallback is the point rather than a
        shortcut. This library's themes are glyph sets, not colour palettes, so
        nothing sets ``stripedbackground`` by default - and honouring only the
        style would make ``striped=1`` do nothing at all on a default theme,
        which is an option that appears to work. Dim is the terminal's own
        banding, legible at any colour depth.
        """
        colour = self._tag_value(iid, "stripedbackground") if iid else ""
        if not colour:
            colour = Style(self).lookup(self._style_name(), "stripedbackground")
        colors = self.tk.colors
        if colour and colors is not None:
            return colors.attribute_for(
                str(
                    self._tag_value(iid, "foreground")
                    or self._options["foreground"]
                    or "white"
                ),
                str(colour),
            )
        if iid:
            attribute = self._tag_attribute(attribute, iid)
        return attribute | curses.A_DIM

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, repainting as the change requires.

        ``striped`` is checked HERE rather than when the row is drawn, because
        Tk raises at configure time and because the alternative hides the
        error: this method's first version left the parse to the drawing code,
        so ``striped="nonsense"`` was stored happily and would have raised at
        the next repaint - or never, on a widget nothing had mapped yet. The
        docstring claimed it raised; running it showed it did not.
        """
        given = tkcurses._given(cnf, kw)
        self._check_titles(given)
        self._check_display(given)
        result = super().configure(cnf, **kw)
        if given:
            self._redraw()
        return result

    config = configure


#: Event types whose tag bindings go to the row under the pointer. Everything
#: else goes to the row with the keyboard.
#:
#: ``man ttk_treeview``, under ``tag bind``: *"<KeyPress>, <KeyRelease>, and
#: virtual events are sent to the focus item. <ButtonPress>, <ButtonRelease>,
#: and <Motion> events are sent to the item under the mouse pointer. No other
#: event types are supported."*
#:
#: Spelled in the canonical types :func:`parse_sequence` answers with, not the
#: names a program writes: ``<ButtonPress-1>`` and ``<Button-1>`` are the same
#: event and both parse to ``Button``.
_POINTER_TAG_EVENTS = frozenset({"Button", "ButtonRelease", "Motion"})


def _treeview_tag_event(sequence: str, event: Event) -> None:
    """Deliver one event to the tag bindings of the row it belongs to.

    Installed on the widget by :meth:`Treeview.tag_bind`, once per sequence.
    A pointer event belongs to the row under the pointer and anything else to
    the focus row - :data:`_POINTER_TAG_EVENTS`. Neither is guaranteed to
    exist: a click can land below the last row and a tree can have no focus
    row, and then there is nothing to deliver to.
    """
    tree = event.widget
    if not isinstance(tree, Treeview):
        return
    if parse_sequence(sequence).type in _POINTER_TAG_EVENTS:
        item = tree._row_at(event.y)
    else:
        item = tree.focus() or None
    if item:
        tree._deliver_tags(item, sequence, event)


def _treeview_click(event: Event) -> Any:
    """Select the row clicked, or open the branch if the marker was hit."""
    tree = event.widget
    if not isinstance(tree, Treeview):
        return None
    iid = tree._row_at(event.y)
    if iid is None:
        return None
    if tree._items[iid].children and event.x == tree._marker_column(iid):
        _treeview_toggle(tree, iid)
        return "break"
    # focus_set as well as focus(iid): Treeview.focus is the ROW the keyboard
    # is on, shadowing Misc.focus, so setting it does nothing about which
    # widget receives keys. Without this the arrows never arrive and the tree
    # looks like it simply ignores them - reported from UAT 34.
    tree.focus_set()
    tree.focus(iid)
    tree.selection_set(iid)
    return "break"


def _treeview_toggle(tree: Treeview, iid: str) -> None:
    """Open a closed branch or close an open one, and say which."""
    item = tree._items[iid]
    opening = not item.options["open"]
    item.options["open"] = 1 if opening else 0
    tree._redraw()
    tree.event_generate("<<TreeviewOpen>>" if opening else "<<TreeviewClose>>")


def _treeview_step(tree: Treeview, step: int) -> Any:
    """Move the selection one visible row."""
    rows = tree._visible()
    if not rows:
        return None
    current = tree.focus()
    place = rows.index(current) + step if current in rows else 0
    if not 0 <= place < len(rows):
        return "break"
    tree.focus(rows[place])
    tree.selection_set(rows[place])
    tree.see(rows[place])
    return "break"


#: The wheel as Tk 9.0.2 binds it on a Treeview: ``tk::MouseWheel`` with a
#: factor of -40, or -12 with Alt, for X11's 120 a notch. Measured, a notch
#: moves 3 rows, or 10 with Alt; with Shift the same counts move it sideways,
#: in pixels there and cells here.
_TREEVIEW_WHEEL = (
    ("", "y", 3),
    ("Alt-", "y", 10),
    ("Shift-", "x", 3),
    ("Shift-Alt-", "x", 10),
)


def _treeview_wheel(axis: str, units: int, event: Event) -> None:
    """Scroll the tree, leaving the selection and the focus item where they are.

    Sideways is only as good as the terminal: many keep Shift-wheel for their
    own scrollback and never report it.
    """
    view = event.widget.xview if axis == "x" else event.widget.yview
    view("scroll", units, "units")


def _treeview_down(event: Event) -> Any:
    """Down: the next row that is showing."""
    tree = event.widget
    return _treeview_step(tree, 1) if isinstance(tree, Treeview) else None


def _treeview_up(event: Event) -> Any:
    """Up: the previous row that is showing."""
    tree = event.widget
    return _treeview_step(tree, -1) if isinstance(tree, Treeview) else None


def _treeview_expand(event: Event) -> Any:
    """Right opens the branch the keyboard is on."""
    tree = event.widget
    if not isinstance(tree, Treeview):
        return None
    iid = tree.focus()
    if iid and tree._items[iid].children and not tree._items[iid].options["open"]:
        _treeview_toggle(tree, iid)
    return "break"


def _treeview_collapse(event: Event) -> Any:
    """Left closes the branch the keyboard is on."""
    tree = event.widget
    if not isinstance(tree, Treeview):
        return None
    iid = tree.focus()
    if iid and tree._items[iid].options["open"]:
        _treeview_toggle(tree, iid)
    return "break"


#: Where the label sits relative to the scale, and the default. Tk takes
#: this as a constructor argument rather than a widget option.
LABEL_ABOVE = "top"
LABEL_BELOW = "bottom"


class LabeledScale(Widget, tkcurses.Frame):
    """A scale with its value written beside it. ``ttk.LabeledScale``.

    **It is a composite, not a widget class.** Measured: ``winfo_class()``
    answers ``TFrame``, because that is what it is - a frame holding a
    ``.label`` and a ``.scale``, both reachable and both ordinary widgets.
    Nothing is bound to a class called ``TLabeledScale``, here or in Tk.

    **Constructing it overwrites the variable you pass.** Measured against
    Tk 9.0.2, and it is in tkinter's own source as ``self._variable.set(
    from_)``: a variable holding 5, handed to a scale running from 2, comes
    back holding 2. Surprising enough to be worth stating, and copied rather
    than corrected - a program written against tkinter would see the same
    thing there, and a library that quietly disagreed would be the harder
    one to reason about.

    ``compound`` decides which side the label goes, ``"top"`` by default, and
    is a constructor argument rather than an option, again as Tk has it.

    Its halves are a :class:`Label` and a :class:`Scale` - the themed ones,
    so they draw from the style database and report ``TLabel`` and
    ``TScale``, as Tk's do.
    """

    _ttk_class = "TFrame"

    #: It is a Frame, whose layout is that one element.
    _only_element = "border"

    #: ttk.LabeledScale carries -padding; ours did not. See Treeview for why
    #: this list is per widget rather than given to everything themed.
    _widget_options: ClassVar[dict[str, Any]] = {"padding": ""}

    def __init__(
        self,
        master: Misc | None = None,
        variable: tkcurses.Variable | None = None,
        from_: float = 0,
        to: float = 10,
        *,
        name: str | None = None,
        compound: str = LABEL_ABOVE,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            variable: The value to share. One is made when omitted - and
                whichever it is, it is set to ``from_``.
            from_: The low end of the range.
            to: The high end.
            name: Path component, generated when omitted.
            compound: ``"top"`` to put the label above the scale,
                ``"bottom"`` to put it below.
            **kw: The standard frame options.
        """
        kw.setdefault("relief", "flat")
        super().__init__(master, name=name, **kw)
        self._variable = variable if variable is not None else tkcurses.IntVar(self)
        # Tk does this, and it is the reason a variable handed in does not
        # keep its value. See the class docstring.
        self._variable.set(from_)
        self._compound = compound

        self.label = Label(self, name="label", text=str(from_), anchor="w")
        # ttk's Scale is horizontal by default and shows no number of its
        # own, which is what this composite wants: its label is the value,
        # and two copies of the same number is not what the widget is for.
        # The classic Scale defaults to VERTICAL - measured on Tk 9.0.2 -
        # and a composite built on that one drew nothing at all on a single
        # row until it was told otherwise.
        self.scale = Scale(
            self,
            name="scale",
            variable=self._variable,
            from_=from_,
            to=to,
            relief="flat",
        )
        label_row, scale_row = (0, 1) if compound == LABEL_ABOVE else (1, 0)
        self.label.place(x=0, y=label_row, relwidth=1.0, height=1)
        self.scale.place(x=0, y=scale_row, relwidth=1.0, height=1)
        self._request_size((int(to) and len(str(to))) or 1, 2)
        self._variable.trace_add("write", lambda *_: self._follow())
        self._follow()

    @property
    def value(self) -> Any:
        """The number the scale is on. Settable, and the label follows."""
        return self._variable.get()

    @value.setter
    def value(self, value: Any) -> None:
        self._variable.set(value)

    def _follow(self) -> None:
        """Put the variable's value in the label.

        Both halves are bound to the same variable, so moving the scale
        writes it and this writes the label - which is the whole of what
        the widget adds over a scale on its own.
        """
        if self.label.winfo_exists():
            self.label.configure(text=str(self._variable.get()))

    def destroy(self) -> None:
        """Drop the trace before going, so it cannot fire into a dead label."""
        with contextlib.suppress(Exception):
            self._variable.trace_remove("write", self._variable.trace_info()[-1][1])
        super().destroy()


class OptionMenu(Widget, tkcurses.OptionMenu):
    """A menubutton whose menu is built from a list. ``ttk.OptionMenu``.

    **It reports ``TMenubutton``.** Measured: like ``LabeledScale`` being a
    ``TFrame``, this is a menubutton with a constructor that fills its menu
    rather than a widget class of its own. Fourth naming case in this cycle,
    after ``Treeview`` without its T and ``TFrame`` for the labeled scale -
    the T-prefix is a convention with exceptions, not a rule, and each one
    matters because a widget reporting the wrong class gets no bindings.

    It differs from the classic ``OptionMenu`` in three measured ways, all
    of them in the constructor rather than the behaviour:

    * The first value is ``default`` and **may be None**, which leaves the
      button blank while the menu still holds every value. The classic one
      refuses to be built with nothing to show.
    * ``set_menu(default, *values)`` takes the default first and
      positionally, where the classic takes it as a keyword.
    * Built with no values at all it is accepted, not refused.
    """

    _ttk_class = "TMenubutton"

    def _element_at(self, x: int, y: int) -> Any:
        """As a Menubutton: the arrow is ``Menubutton.indicator``."""
        return _menubutton_element(self, x, y)

    def __init__(
        self,
        master: Misc | None,
        variable: tkcurses.Variable,
        default: Any = None,
        *values: Any,
        command: Callable[[Any], Any] | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget.
            variable: The variable the choice is written to, and the one the
                button's text follows.
            default: What to start on, or None to start blank. Not added to
                the menu unless it is also among ``values``.
            *values: The choices.
            command: Called with the chosen value, after the variable is set.
            **kw: Anything else a menubutton takes.
        """
        kw.setdefault("indicatoron", True)
        kw.setdefault("textvariable", variable)
        # Straight to Menubutton: the classic OptionMenu's constructor
        # refuses to be built with nothing to show, and this one must accept
        # exactly that.
        tkcurses.Menubutton.__init__(self, master, **kw)
        self._variable = variable
        self._command = command
        self._options["menu"] = tkcurses.Menu(self, name="menu")
        self.set_menu(default, *values)
        self._install_class_bindings()

    def set_menu(self, default: Any = None, *values: Any) -> None:  # type: ignore[override]
        """Replace the choices, and what is showing.

        Args:
            default: What the button shows now, or None to leave it blank.
            *values: The entries to offer.

        The default is positional and first, which is ttk's shape. The
        classic widget takes it as a keyword instead, and the two are not
        interchangeable - a call written for one silently means something
        else to the other.
        """
        menu = self._options["menu"]
        menu.delete(0, "end")
        for value in values:
            menu.add_radiobutton(
                label=str(value),
                variable=self._variable,
                value=value,
                command=None if self._command is None else _chosen(self, value),
            )
        self._variable.set("" if default is None else default)


def _chosen(widget: OptionMenu, value: Any) -> Callable[[], None]:
    """The callback one menu entry runs: tell the application what was picked."""

    def run() -> None:
        if widget._command is not None:
            widget._command(value)

    return run


class Label(Widget, tkcurses.Label):
    """Text drawn from the style database. ``ttk.Label``.

    A themed Label over the classic one. Nothing is bound to ``TLabel`` - a
    label answers no gestures - so the class-binding trap that catches the
    interactive widgets does not arise here.
    """

    #: ttk's label family keeps ``width`` unchecked - ``width="abc"`` reads
    #: back ``abc`` on Tk 9.0.2 - so drawing reads it with a fallback.
    _value_checks: ClassVar[dict[str, Callable[[Any, Any], Any]]] = {
        "width": tkcurses._unchecked,
        "wraplength": tkcurses._distance_or_empty,
    }

    _ttk_class = "TLabel"

    _widget_options: ClassVar[dict[str, Any]] = {
        "padding": "",
        "compound": "",
    }


class Scale(Widget, tkcurses.Scale):
    """A value chosen by sliding, drawn from the style database. ``ttk.Scale``.

    Three measured differences from the classic ``Scale``, all of them worth
    knowing because code written against one behaves differently under the
    other:

    * **It is horizontal by default.** The classic one is vertical. A
      composite built on the wrong default draws nothing at all on a single
      row, which is how this was first noticed.
    * **It has a ``value`` option**, which the classic takes only through
      ``set()``.
    * **It leaves a variable alone.** Handed a variable holding 7, it shows
      7 - where ``LabeledScale`` overwrites it with ``from_``, as tkinter's
      own source does.

    It shows no number of its own: ttk's scale is the slider and nothing
    else, and anything wanting a number beside it uses ``LabeledScale``.
    """

    _ttk_class = "TScale"

    def _element_at(self, x: int, y: int) -> Any:
        """``slider`` and ``trough``, where the classic scale says trough1/2.

        Tk's ttk.Scale answers ``trough`` on both sides of the slider, and
        nowhere on the widget answers ``""``; the cells the classic one calls
        ``""`` on the trough's own line are its caps, part of the trough.
        """
        part = tkcurses.Scale.identify(self, x, y)
        if part == "slider":
            return "slider"
        if part:
            return "trough"
        origin_x, origin_y = self._trough_origin()
        return "trough" if (x == origin_x if self._vertical else y == origin_y) else ""

    _widget_options: ClassVar[dict[str, Any]] = {
        "orient": "horizontal",
        "value": None,
        "showvalue": False,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``orient``, ``from_``, ``to``, ``value``, ``variable``,
                ``command``, ``style``, and the standard options.
        """
        value = kw.pop("value", None)
        super().__init__(master, cnf, name=name, **kw)
        if value is not None:
            self.set(float(value))


class Frame(Widget, tkcurses.Frame):
    """A container with a themed border. ``ttk.Frame``.

    The least behaviour of any themed widget: a region, a border taken from
    the style, and children laid out in it. Nothing is bound to ``TFrame``.

    ``padding`` is accepted and **not yet honoured** - see the note on
    :class:`Labelframe`.
    """

    _ttk_class = "TFrame"

    #: A Frame's layout is that one element.
    _only_element = "border"

    _widget_options: ClassVar[dict[str, Any]] = {
        "padding": "",
    }


class Labelframe(Widget, tkcurses.LabelFrame):
    """A frame with a caption in its border. ``ttk.Labelframe``.

    Spelled both ways, as in tkinter: ``Labelframe`` is the class and
    ``LabelFrame`` is a second name for the same one. Measured against ttk
    9.0, where ``ttk.LabelFrame is ttk.Labelframe`` is True - they are one
    class, not two implementations, so this is an assignment rather than a
    subclass and the two can never drift apart.

    ``underline`` is a ttk addition the classic widget does not have;
    ``labelanchor``, ``text`` and ``labelwidget`` come from the classic one.

    **``padding`` is accepted and does nothing yet.** It is declared because
    the option surface is compared against real ttk's and a missing option is
    a test failure, and it is inert because no themed widget here honours it -
    ``Notebook``, ``Treeview`` and ``LabeledScale`` declare it the same way.
    Saying so rather than leaving it to be discovered: ``TkCurses-avy``.
    """

    _ttk_class = "TLabelframe"

    def _element_at(self, x: int, y: int) -> Any:
        """``border``, except over the caption, which answers ``""`` in Tk."""
        place = self._caption_place()
        if place is not None:
            row, column, text = place
            if y == row and column <= x < column + len(text):
                return ""
        return "border"

    _widget_options: ClassVar[dict[str, Any]] = {
        "padding": "",
        "underline": "",
    }


#: ttk's other spelling. One class, two names, exactly as tkinter has it.
LabelFrame = Labelframe


class Panedwindow(Widget, tkcurses.PanedWindow):
    """Panes with draggable sashes between them. ``ttk.Panedwindow``.

    The one themed widget whose tkinter counterpart is also built on the
    classic one - measured, ``ttk.Panedwindow.__mro__`` begins
    ``Panedwindow, Widget, PanedWindow`` - so the shape here is the shape
    real ttk uses, rather than a convenience.

    It drops sixteen of the classic widget's options, all of them about
    drawing the sash by hand: ``sashwidth``, ``sashrelief``, ``sashpad``,
    ``sashcursor``, ``showhandle``, ``handlepad``, ``handlesize``, the
    ``proxy*`` three, ``opaqueresize``, and the colours. Under ttk a sash is
    the theme's business. They are still accepted here, because every themed
    widget in this module is deliberately wider than ttk rather than
    narrower - see ``test_a_themed_widget_is_wider_than_ttk_on_purpose``.

    It adds two methods the classic widget has no counterpart for,
    :meth:`pane` and :meth:`sashpos`, and one pane option, ``weight``.

    **``weight`` is stored and reported, and does not yet change the
    layout.** ttk gives surplus space to panes in proportion to their
    weights, with ``weight=0`` meaning "do not resize"; the layout underneath
    spreads surplus evenly across every pane instead, which is what the
    classic widget documents and what its tests assert. Honouring weight
    means a weighted distribution that the two widgets cannot share, so it is
    its own piece of work rather than something smuggled in here:
    ``TkCurses-2v2``. Until then ``pane(index)`` answers what was set, so
    code that round-trips a weight sees what it wrote.
    """

    _value_checks: ClassVar[dict[str, Callable[[Any, Any], Any]]] = {
        "height": tkcurses._tcl_integer,
        "width": tkcurses._tcl_integer,
    }

    _ttk_class = "TPanedwindow"

    def _element_at(self, x: int, y: int) -> Any:
        """A sash's index over a sash, ``""`` anywhere else.

        Measured: Tk's ttk.Panedwindow answers the bare index, ``0``, where
        the classic one answers ``(0, "sash")``.
        """
        found = tkcurses.PanedWindow.identify(self, x, y)
        return found[0] if found else ""

    _widget_options: ClassVar[dict[str, Any]] = {
        "height": 0,
        "width": 0,
    }

    #: What a pane's weight is when nobody sets one. ttk's default.
    DEFAULT_WEIGHT = 0

    def _pane_options(self, given: dict[str, Any], child: Any) -> PaneOptions:
        """The classic pane options, plus ttk's ``weight``.

        The weight is carried by the layout's own PaneOptions rather than in a
        dict beside it, so there is ONE place a pane's weight lives - the
        thing that reads it when dividing space is the same thing :meth:`pane`
        reports from. An earlier version kept a dict keyed by widget path and
        the layout could not see it, which is how the option came to be
        recorded and ignored (TkCurses-2v2).

        A weight not given is kept, as the classic options are: measured, ttk
        moves a pane ``insert`` names again and leaves its weight alone.
        """
        given = dict(given)
        weight = given.pop("weight", None)
        options = super()._pane_options(given, child)
        if weight is not None:
            return replace(options, weight=int(weight))
        if options.weight is None:
            return replace(options, weight=self.DEFAULT_WEIGHT)
        return options

    def _pane_at(self, index: Any) -> Any:
        """The pane named by a position, a widget path, or a widget itself.

        All three are things ttk accepts where a pane is wanted, and the one
        that comes back from ``panes()`` is the path.
        """
        slaves = self._paned.slaves()
        if isinstance(index, int):
            if not -len(slaves) <= index < len(slaves):
                raise TclError(f"pane index out of range: {index}")
            return slaves[index]
        wanted = str(index)
        for child in slaves:
            if child._w == wanted:
                return child
        raise TclError(f'not managed by this window: "{index}"')

    def add(self, child: Any, **kw: Any) -> None:
        """Add a pane at the end.

        Args:
            child: The widget to put in it.
            **kw: ``weight``, plus the pane options the classic widget takes.

        Raises:
            TclError: If ``child`` is a pane here already. Measured: ttk refuses
                it with ``<path> already added``, where the classic widget
                treats a second ``add`` as a ``paneconfigure``.
        """
        if self._paned.options_for(child) is not None:
            raise TclError(f"{child} already added")
        kw = tkcurses._given(None, kw)
        super().add(child, **kw)

    def insert(self, index: Any, child: tkcurses.Widget, **kw: Any) -> None:
        """Add a pane at a position.

        The first argument is named ``index`` and tkinter's ttk names it
        ``pos``. Positionally they are the same; a caller writing
        ``insert(pos=0, ...)`` would differ. It follows the classic widget
        here because overriding with a different name is a typing error - the
        base promises a parameter called ``index`` and callers may use it -
        and the two spellings cannot both be right. Same shape as
        ``TkCurses-y5q``, where we report ``from_`` and tkinter reports
        ``from``.

        Args:
            index: Index to insert before, or ``"end"``.
            child: The widget to put in it.
            **kw: ``weight``, plus the pane options the classic widget takes.
        """
        kw = tkcurses._given(None, kw)
        super().insert(index, child, **kw)

    def forget(self, child: tkcurses.Widget | None = None) -> None:
        """Remove a pane, and with it the weight the layout held for it."""
        super().forget(child)

    def pane(self, index: Any, option: str | None = None, **kw: Any) -> Any:
        """Read or set one pane's options.

        Args:
            index: Which pane, by position or by widget.
            option: One option to read, by name - ``pane(child, "weight")``.
                It was refused here with a TypeError until TkCurses-kopw.
            **kw: Options to set; omit them to read instead.

        Returns:
            Reading: a dict of the pane's ttk options. Measured against ttk
            9.0, that is ``{'weight': N}`` and nothing else. With ``option``,
            that one value.

        Raises:
            TclError: For an ``option`` a ttk pane does not have. Measured on
                Tk 9.0.2, that is every name but ``weight`` - ``minsize``
                included - as ``unknown option "-minsize"``, and the name is
                taken as given: ``"-weight"`` is ``unknown option "--weight"``.
        """
        if option is not None:
            current = self.pane(index)
            if option not in current:
                raise TclError(f'unknown option "-{option}"')
            return current[option]
        if kw and not tkcurses._given(None, kw):
            return None  # every option None, which tkinter drops
        kw = tkcurses._given(None, kw)
        child = self._pane_at(index)
        options = self._paned.options_for(child)
        if options is None:  # pragma: no cover - _pane_at already refused it
            raise TclError(f'not managed by this window: "{index}"')
        if not kw:
            weight = options.weight
            return {"weight": self.DEFAULT_WEIGHT if weight is None else weight}
        self.paneconfigure(child, **kw)
        return None

    def sashpos(self, index: int, newpos: int | None = None) -> int:
        """Read or move a sash, as one number.

        Args:
            index: Which sash, counting from zero.
            newpos: Where to put it, in cells from this widget's left or top
                edge. Omit it to read the position instead.

        Returns:
            Where the sash is - after the move, when one was asked for.

        The classic widget has no such method: it offers ``sash_coord`` and
        ``sash_place``, which are two-dimensional because a classic paned
        window will tell you both coordinates. A ttk one takes and gives the
        single number along its own orientation, so this is not a rename.
        """
        if newpos is not None:
            area = self._content_area()
            if self._paned.vertical:
                self.sash_place(index, area.x, area.y + int(newpos))
            else:
                self.sash_place(index, area.x + int(newpos), area.y)
        x, y = self.sash_coord(index)
        area = self._content_area()
        return (y - area.y) if self._paned.vertical else (x - area.x)


#: ttk's other spelling, as with Labelframe.
PanedWindow = Panedwindow


class Button(Widget, tkcurses.Button):
    """A button drawn from the style database. ``ttk.Button``.

    Measured against Tk 9.0, its bindtags are
    ``('.!button', 'TButton', '.', 'all')`` - ``Button`` is not among them, so
    none of the classic button's class bindings reach it and it installs its
    own. The classic widget's ``_install_class_bindings`` binds under
    ``winfo_class()``, which answers ``TButton`` here, so inheriting it is
    enough: the six binds land on the themed tag. It did not always - see the
    commit that stopped it hardcoding the name.
    """

    _value_checks: ClassVar[dict[str, Callable[[Any, Any], Any]]] = {
        "width": tkcurses._unchecked
    }

    _ttk_class = "TButton"

    _widget_options: ClassVar[dict[str, Any]] = {
        "padding": "",
    }


class Checkbutton(Widget, tkcurses.Checkbutton):
    """A box that remembers whether it is ticked. ``ttk.Checkbutton``.

    ``onvalue`` and ``offvalue`` are ``1`` and ``0``, the same as the classic
    widget's - measured, rather than assumed either way, because the issue
    that asked for this widget suspected ttk of differing and it does not.

    Bindings come from ``_ChoiceWidget``, which already binds under
    ``winfo_class()``: the space bar and not Return, so that Return still
    reaches a dialog's default button from wherever the focus is.
    """

    _value_checks: ClassVar[dict[str, Callable[[Any, Any], Any]]] = {
        "width": tkcurses._unchecked
    }

    _ttk_class = "TCheckbutton"

    _outer_element = "padding"

    def _element_at(self, x: int, y: int) -> Any:
        """``Checkbutton.indicator`` over the box, else the ring model."""
        return _indicator_element(self, "Checkbutton", x, y)

    _widget_options: ClassVar[dict[str, Any]] = {
        "padding": "",
    }


class Radiobutton(Widget, tkcurses.Radiobutton):
    """One of a set, where choosing it unchooses the others.
    ``ttk.Radiobutton``.

    Its default variable is ``selectedButton``, shared by every radiobutton
    that is not given one - the same name the classic widget defaults to.
    Measured: ttk reports it fully qualified as ``::selectedButton`` and the
    classic one as ``selectedButton``, which is the same global under Tcl's
    namespace rules rather than a difference.
    """

    _value_checks: ClassVar[dict[str, Callable[[Any, Any], Any]]] = {
        "width": tkcurses._unchecked
    }

    _ttk_class = "TRadiobutton"

    _outer_element = "padding"

    def _element_at(self, x: int, y: int) -> Any:
        """``Radiobutton.indicator`` over the button, else the ring model."""
        return _indicator_element(self, "Radiobutton", x, y)

    @property
    def _indicator_state(self) -> str:
        """On or off, never the classic widget's third state.

        Measured on Tk 9.0.2: a ttk radiobutton over an empty variable has
        no ``alternate`` state, where the classic one draws its third.
        """
        state = super()._indicator_state
        return "off" if state == "tristate" else state

    _widget_options: ClassVar[dict[str, Any]] = {
        "padding": "",
    }


class Menubutton(Widget, tkcurses.Menubutton):
    """A button that opens a menu. ``ttk.Menubutton``.

    ``direction`` defaults to ``below``, as ttk's does.
    """

    _value_checks: ClassVar[dict[str, Callable[[Any, Any], Any]]] = {
        "width": tkcurses._unchecked
    }

    _ttk_class = "TMenubutton"

    def _element_at(self, x: int, y: int) -> Any:
        """The arrow is ``Menubutton.indicator``, the rest the ring model."""
        return _menubutton_element(self, x, y)

    _widget_options: ClassVar[dict[str, Any]] = {
        "padding": "",
    }


class Entry(Widget, _EntryCommands):
    """A one-line text field drawn from the style. ``ttk.Entry``.

    ``validate``, ``validatecommand`` and ``invalidcommand`` come from the
    classic widget, with ttk's own rules where they differ - no validation of
    a ``textvariable`` write, errors handed to the caller, validation left on
    after a callback edits the entry, and the ``invalid`` state. Those, and
    ``validate()`` and ``bbox()``, are in :class:`_EntryCommands`.

    ttk drops the long list of classic colour and insertion-cursor options -
    ``bd``, ``bg``, ``disabledbackground``, ``insertwidth`` and the rest. They
    are still accepted, as everywhere in this module: wider than ttk on
    purpose.
    """

    _value_checks: ClassVar[dict[str, Callable[[Any, Any], Any]]] = {
        "width": tkcurses._tcl_integer
    }

    _ttk_class = "TEntry"

    _outer_element = "field"
    _inner_element = "textarea"

    _widget_options: ClassVar[dict[str, Any]] = {}


class Spinbox(Widget, _EntryCommands, tkcurses.Spinbox):
    """An entry with a value you can step. ``ttk.Spinbox``.

    **ttk's Spinbox is an Entry, not the classic Spinbox**, which is what the
    issue behind this widget warned to check. Measured on Tk 9.0,
    ``ttk.Spinbox.__mro__`` begins ``Spinbox, Entry, Widget, Entry`` - it is
    built on ``ttk.Entry``, and against the classic Spinbox it adds ``show``
    while dropping twenty-eight options, nearly all of them about painting the
    little buttons ttk draws from the theme instead.

    Here the classic Spinbox already subclasses the classic Entry, so the same
    relationship holds underneath and ``show`` comes with it. The two
    hierarchies agree; only the painting options differ, and those we keep.
    """

    _value_checks: ClassVar[dict[str, Callable[[Any, Any], Any]]] = {
        "width": tkcurses._tcl_integer
    }

    _ttk_class = "TSpinbox"

    _outer_element = "field"
    _inner_element = "textarea"

    def _element_at(self, x: int, y: int) -> Any:
        """The arrows are ``Spinbox.uparrow`` and ``Spinbox.downarrow``.

        The classic Spinbox calls them ``buttonup`` and ``buttondown``.
        """
        part = tkcurses.Spinbox.identify(self, x, y)
        if part == "buttonup":
            return "Spinbox.uparrow"
        if part == "buttondown":
            return "Spinbox.downarrow"
        return super()._element_at(x, y)

    _widget_options: ClassVar[dict[str, Any]] = {}

    def set(self, value: Any) -> None:
        """Make ``value`` the spinbox's text.

        Taken as given: not checked against ``from_``/``to`` or ``values``,
        not validated, and not refused by ``readonly`` or ``disabled`` -
        measured, ``set(99)`` on a 0-10 spinbox reads back ``"99"`` in Tk.
        See :meth:`Entry._set_value` for the rest of what Tk does here.
        """
        self._set_value(value)


class Scrollbar(Widget, tkcurses.Scrollbar):
    """A themed scrollbar. ``ttk.Scrollbar``.

    The simplest of the three: ttk adds only ``class`` and ``style``, both from
    the mixin, and drops the seven classic appearance options -
    ``activebackground``, ``activerelief``, ``background`` and the rest - which
    a theme decides instead.
    """

    _ttk_class = "TScrollbar"

    def activate(self, index: str | None = None) -> str | None:  # noqa: ARG002
        """Refused, as Tk refuses it: ``ttk::scrollbar`` has no ``activate``.

        tkinter's ttk.Scrollbar inherits the method from the classic one and
        Tk rejects the command, measured on 9.0.2 with and without an
        element. A theme draws the active state from ``state()`` instead.
        """
        raise TclError(
            'bad command "activate": must be cget, configure, delta, fraction, '
            "get, identify, instate, set, state, or style"
        )

    def _element_at(self, x: int, y: int) -> Any:
        """ttk's names for the classic scrollbar's parts.

        ``arrow1``/``arrow2`` are ``leftarrow``/``rightarrow`` or
        ``uparrow``/``downarrow`` by orientation, ``slider`` is ``thumb``,
        and both troughs are ``trough`` - measured on Tk's horizontal and
        vertical ttk.Scrollbar.
        """
        part = tkcurses.Scrollbar.identify(self, x, y)
        if part == "arrow1":
            return "uparrow" if self._vertical else "leftarrow"
        if part == "arrow2":
            return "downarrow" if self._vertical else "rightarrow"
        return "thumb" if part == "slider" else "trough"

    _widget_options: ClassVar[dict[str, Any]] = {}
