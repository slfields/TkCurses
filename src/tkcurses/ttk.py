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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

import tkcurses
from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses._core.errors import TclError

if TYPE_CHECKING:
    from tkcurses import Event, Misc

__all__ = ["THEMES", "Style", "Theme"]


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
    _widget_options: ClassVar[dict[str, Any]] = {"style": ""}

    def winfo_class(self) -> str:
        """The themed class name - ``TButton``, not ``Button``.

        This is what puts the widget's bindings and its default style under
        the ttk name, and what keeps the classic widget's bindings off it.
        """
        return self._ttk_class

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
        given = {**(cnf or {}), **kw}
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

    _ttk_class = "TProgressbar"

    _widget_options: ClassVar[dict[str, Any]] = {
        "orient": "horizontal",
        "mode": "determinate",
        "maximum": 100.0,
        "value": 0.0,
        "length": 20,
        "variable": None,
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
        given = {**(cnf or {}), **kw}
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
            if not self.winfo_exists():
                return
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
        """Cancel the timer before going, so it cannot fire into a dead widget."""
        if self._timer is not None:
            with contextlib.suppress(Exception):
                self.after_cancel(self._timer)
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
