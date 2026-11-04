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

"""Event bindings: sequence parsing and the binding table.

A tkinter binding is a string such as ``<Control-Key-a>`` or ``<Double-Button-1>``
paired with a callback. Two jobs follow from that, and they are separated here.

:func:`parse_sequence` turns the string into an :class:`EventPattern`. It is
pure text handling with no terminal and no widgets behind it, which is why it
lives in ``_core`` next to the keysym table it draws on rather than in the
widget layer that calls it.

:class:`BindingTable` stores callbacks against those patterns, keyed by *tag*.
Tk resolves an event by walking a widget's ``bindtags`` — its own path, its
class, its toplevel, then ``all`` — and the table knows nothing about which
tags a widget has; it is handed the list and walks it. That keeps the rule
about what a widget's tags *are* in the widget layer where it can be
overridden by ``bindtags()``.

Virtual events (``<<Paste>>``) are a separate mapping, :class:`VirtualEvents`,
because they are a name-to-sequences relation rather than a callback registry.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tkcurses._core.events import (
    MOD_ALT,
    MOD_BUTTON1,
    MOD_BUTTON2,
    MOD_BUTTON3,
    MOD_BUTTON4,
    MOD_BUTTON5,
    MOD_BUTTONS,
    MOD_CTRL,
    MOD_META,
    MOD_SHIFT,
    Event,
    KeyEvent,
    MouseEvent,
    ResizeEvent,
    canonical_keysym,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping

__all__ = [
    "BREAK",
    "MOD_ANY",
    "Binding",
    "BindingTable",
    "EventPattern",
    "VirtualEvents",
    "parse_sequence",
    "pattern_for_event",
]

#: Returned by a callback to stop the event propagating to further bindings.
BREAK = "break"

#: The ``Any`` modifier, which makes a pattern ignore modifier state. It sits
#: clear of every ``MOD_*`` bit in :mod:`tkcurses._core.events` rather than
#: alongside them: those describe a key or button that was really held, this
#: one describes how to match, and no input event ever carries it.
MOD_ANY = 0x8000

#: Modifier names accepted in a sequence, including the aliases tkinter takes
#: from macOS and X11 so that code written for either binds the same thing.
_MODIFIERS: dict[str, int] = {
    # B1 to B5: a mouse button held down. <B1-Motion> is Tk's drag idiom.
    "B1": MOD_BUTTON1,
    "B2": MOD_BUTTON2,
    "B3": MOD_BUTTON3,
    "B4": MOD_BUTTON4,
    "B5": MOD_BUTTON5,
    "Button1": MOD_BUTTON1,
    "Button2": MOD_BUTTON2,
    "Button3": MOD_BUTTON3,
    "Button4": MOD_BUTTON4,
    "Button5": MOD_BUTTON5,
    "Control": MOD_CTRL,
    "Ctrl": MOD_CTRL,
    "Shift": MOD_SHIFT,
    "Alt": MOD_ALT,
    "Option": MOD_ALT,
    "Meta": MOD_META,
    "M": MOD_META,
    "Command": MOD_META,
    "Cmd": MOD_META,
    "Any": MOD_ANY,
}

#: Click-count prefixes. Tk calls these modifiers; they are tracked separately
#: because they count repetitions rather than name a held key.
_REPEATS: dict[str, int] = {
    "Double": 2,
    "Triple": 3,
    "Quadruple": 4,
}

#: Event types, mapped to the canonical spelling. The aliases are Tk's own:
#: ``Key`` and ``KeyPress`` name one event, as do ``Button`` and
#: ``ButtonPress``.
_TYPES: dict[str, str] = {
    "Key": "Key",
    "KeyPress": "Key",
    "KeyRelease": "KeyRelease",
    "Button": "Button",
    "ButtonPress": "Button",
    "ButtonRelease": "ButtonRelease",
    "Motion": "Motion",
    "MouseWheel": "MouseWheel",
    "Enter": "Enter",
    "Leave": "Leave",
    "FocusIn": "FocusIn",
    "FocusOut": "FocusOut",
    "Configure": "Configure",
    "Destroy": "Destroy",
    "Map": "Map",
    "Unmap": "Unmap",
    "Expose": "Expose",
    "Visibility": "Visibility",
    "Activate": "Activate",
    "Deactivate": "Deactivate",
}

#: Virtual event name, e.g. ``<<Paste>>``.
_VIRTUAL_RE = re.compile(r"^<<([^<>]+)>>$")

#: A single bracketed event, e.g. ``<Control-Key-a>``.
_PHYSICAL_RE = re.compile(r"^<([^<>]*)>$")

#: Mouse states that are reported as a press, with the click count each
#: implies. A bare click is a press as far as bindings are concerned; the
#: release arrives as its own event.
_MOUSE_PRESS_STATES: dict[str, int] = {
    "pressed": 1,
    "clicked": 1,
    "double": 2,
    "triple": 3,
}


@dataclass(frozen=True)
class EventPattern:
    """What a binding matches, or what an event is.

    The same type serves both sides of the comparison: a sequence parses into
    one, an incoming event converts into one, and :meth:`matches` decides
    whether the first covers the second.

    Attributes:
        type: Canonical event type, or ``"Virtual"`` for ``<<Name>>``.
        detail: Keysym for a key, button number for a button, virtual event
            name for a virtual. Empty means "any", so ``<Key>`` matches every
            key press.
        modifiers: Bitwise OR of the ``MOD_*`` flags, possibly including
            :data:`MOD_ANY`.
        repeat: Click count: 1 for a single click, 2 for ``<Double-...>``.
    """

    type: str
    detail: str = ""
    modifiers: int = 0
    repeat: int = 1

    @property
    def is_virtual(self) -> bool:
        """True for a ``<<Name>>`` pattern."""
        return self.type == "Virtual"

    def matches(self, event: EventPattern) -> bool:
        """True if a binding on this pattern should fire for ``event``.

        Asymmetries all the way down, which is what makes this a one-way test
        rather than equality. An empty ``detail`` is a wildcard, so ``<Key>``
        catches every key. A pattern fires for a click count of AT LEAST its
        own: a single-click pattern on a double or triple click, and
        ``<Double-Button-1>`` on a triple - Tk's ``patPtr->count <= count``,
        and its manual: "<Double-Button-1> will match each button press but
        the first". This required the count exactly until TkCurses-jfm, so a
        third click fired nothing bound to a double.

        And the modifiers need only be a **subset** of the event's, which is
        Tk's rule and not an obvious one: ``<Key>`` fires for a key held with
        Shift, and ``<Button-1>`` fires for a shift-click. Requiring them to
        be equal - which this did - meant the obvious binding for "tell me
        about every key" silently stopped working the moment a modifier was
        held. Where several patterns match, :meth:`specificity` decides which
        of them actually runs.
        """
        if self.type != event.type:
            return False
        if self.detail and self.detail != event.detail:
            return False
        if self.repeat > event.repeat:
            return False
        if self.modifiers & MOD_ANY:
            return True
        wanted = self.modifiers & ~MOD_ANY
        return wanted & event.modifiers == wanted

    @property
    def specificity(self) -> tuple[int, int, int]:
        """How particular this pattern is, for choosing between matches.

        Ordered the way Tk orders them, checked against Tk 9.0.2: a named
        detail outranks any number of modifiers - ``<Key-A>`` beats
        ``<Shift-Key>`` - then a LONGER sequence outranks more modifiers, and
        only then do more modifiers win. ``Any`` is not counted: it waives
        the comparison rather than demanding anything, so a pattern using it
        is the least particular of all.

        The click count is the "longer sequence", as Tk's manual has it, and
        it used to rank below the modifiers here. Measured with synthetic
        clicks on a Frame: held Control, the second click of a double fires
        ``<Double-Button-1>`` over ``<Control-Button-1>``; held Shift, with no
        double-shift binding, ``<Double-Button-1>`` over ``<Shift-Button-1>``,
        and the third ``<Triple-Button-1>``. Ours fired the modified single
        click every time. TkCurses-mndh.
        """
        return _rank((self,))

    def __str__(self) -> str:
        """The canonical sequence string for this pattern."""
        if self.is_virtual:
            return f"<<{self.detail}>>"
        parts = [name for flag, name in _CANONICAL_MODIFIERS if self.modifiers & flag]
        parts.extend(name for name, count in _REPEATS.items() if count == self.repeat)
        parts.append(self.type)
        if self.detail:
            parts.append(self.detail)
        return "<" + "-".join(parts) + ">"


#: Tk's weight for a pattern's click count when ranking matches (IsBetterMatch
#: in tkBind.c): a double outweighs any number of singles, and so on up.
_COUNT_WEIGHT = (0, 1, 10**6, 10**12, 10**18)


def _rank(patterns: tuple[EventPattern, ...]) -> tuple[int, int, int]:
    """How particular a match is - Tk's ``IsBetterMatch``, read from tkBind.c.

    First, the click counts of the patterns that name a detail (a key or a
    button) - so ``<Key-A>`` beats ``<Shift-Key>``, a double beats a single,
    and ``<Control-x><Control-s>`` beats ``<Control-s>``. Then every
    pattern's count, weighted, so a longer sequence wins a tie. Then the
    modifiers of the last pattern, Tk's ``CompareModMasks``. ``Any`` is not a
    modifier here: it waives the comparison rather than demanding anything.
    """
    detailed = sum(pattern.repeat for pattern in patterns if pattern.detail)
    weighted = sum(_COUNT_WEIGHT[min(pattern.repeat, 4)] for pattern in patterns)
    modifiers = int(patterns[-1].modifiers & ~MOD_ANY).bit_count()
    return (detailed, weighted, modifiers)


@dataclass(frozen=True)
class PatternSequence:
    """Several events that must arrive in order: ``<Control-x><Control-s>``.

    It never matches one event by itself; :class:`BindingTable` follows it
    across events, as Tk does - see :meth:`BindingTable.dispatch`.
    """

    patterns: tuple[EventPattern, ...]

    @property
    def type(self) -> str:
        """The type of the event that completes it - its last pattern's."""
        return self.patterns[-1].type

    @property
    def is_virtual(self) -> bool:
        return False

    def matches(self, event: EventPattern) -> bool:
        """Never: a sequence is matched across events, not by one."""
        del event
        return False

    @property
    def specificity(self) -> tuple[int, int, int]:
        return _rank(self.patterns)

    def __str__(self) -> str:
        return "".join(str(pattern) for pattern in self.patterns)


#: Modifier flags in the order Tk writes them, used to render a pattern back
#: into a sequence string. ``Any`` is deliberately absent: it is a matching
#: instruction, and reproducing it would make two different patterns print the
#: same.
_CANONICAL_MODIFIERS: tuple[tuple[int, str], ...] = (
    (MOD_CTRL, "Control"),
    (MOD_ALT, "Alt"),
    (MOD_SHIFT, "Shift"),
    (MOD_META, "Meta"),
    (MOD_BUTTON1, "B1"),
    (MOD_BUTTON2, "B2"),
    (MOD_BUTTON3, "B3"),
    (MOD_BUTTON4, "B4"),
    (MOD_BUTTON5, "B5"),
)


def parse_sequence(sequence: str) -> EventPattern | PatternSequence:
    """Parse a tkinter binding sequence.

    One event gives an :class:`EventPattern`: the bracketed form
    (``<Control-Key-a>``, ``<Double-Button-1>``, ``<<Paste>>``) or a bare
    character, which stands for a key press - ``"a"`` means ``<Key-a>``.
    Several give a :class:`PatternSequence`: ``<Control-x><Control-s>``, or
    ``"ab"``, which is ``<Key-a><Key-b>`` as it is in Tk. TkCurses-jfm.

    Raises:
        ValueError: If the sequence is malformed or names something unknown,
            or puts a virtual event in a sequence of several.
    """
    if not sequence:
        raise ValueError("binding sequence is empty")
    patterns = [_parse_event(sequence, token) for token in _tokens(sequence)]
    if len(patterns) == 1:
        return patterns[0]
    if any(pattern.is_virtual for pattern in patterns):
        raise ValueError(
            f"cannot parse binding sequence {sequence!r}: a virtual event "
            "cannot be part of a sequence of several"
        )
    return PatternSequence(tuple(patterns))


def _tokens(sequence: str) -> list[str]:
    """Split a sequence into its events: ``<...>``, ``<<...>>``, or one char."""
    tokens: list[str] = []
    at = 0
    while at < len(sequence):
        if sequence.startswith("<<", at):
            end = sequence.find(">>", at + 2)
            if end < 0:
                raise ValueError(f"cannot parse binding sequence {sequence!r}")
            tokens.append(sequence[at : end + 2])
            at = end + 2
        elif sequence[at] == "<":
            end = sequence.find(">", at + 1)
            if end < 0:
                raise ValueError(
                    f"cannot parse binding sequence {sequence!r}: no closing '>'"
                )
            tokens.append(sequence[at : end + 1])
            at = end + 1
        else:
            tokens.append(sequence[at])
            at += 1
    return tokens


def _parse_event(sequence: str, token: str) -> EventPattern:
    """One event of a sequence."""
    virtual = _VIRTUAL_RE.match(token)
    if virtual:
        return EventPattern(type="Virtual", detail=virtual.group(1))
    if not token.startswith("<"):
        return EventPattern(type="Key", detail=_bare_keysym(token))
    physical = _PHYSICAL_RE.match(token)
    if physical is None:
        raise ValueError(f"cannot parse binding sequence {sequence!r}")
    return _parse_fields(sequence, _split_fields(physical.group(1)))


def _bare_keysym(char: str) -> str:
    """The keysym a bare one-character sequence stands for.

    Only the space bar needs translating: Tk names it ``space`` because a
    literal space cannot survive the sequence syntax.
    """
    return "space" if char == " " else char


def _split_fields(body: str) -> list[str]:
    """Split the inside of ``<...>`` on ``-``, keeping a trailing ``-`` whole.

    ``<Control-->`` binds Control and the minus key, so the final separator
    cannot be treated as one: splitting naively yields an empty last field
    instead of the detail.
    """
    if not body.endswith("-"):
        return body.split("-")
    # Drop the detail, then the separator that introduced it, so that
    # "Control--" leaves "Control" rather than an empty trailing field.
    prefix = body[:-1].removesuffix("-")
    return [*prefix.split("-"), "-"] if prefix else ["-"]


def _parse_fields(sequence: str, fields: list[str]) -> EventPattern:
    """Build a pattern from the ``-`` separated fields of a sequence."""
    modifiers = 0
    repeat = 1
    event_type = ""
    detail = ""

    for index, field_text in enumerate(fields):
        if not field_text:
            raise ValueError(f"cannot parse binding sequence {sequence!r}: empty field")
        if field_text in _MODIFIERS and not event_type:
            modifiers |= _MODIFIERS[field_text]
        elif field_text in _REPEATS and not event_type:
            repeat = _REPEATS[field_text]
        elif field_text in _TYPES and not event_type:
            event_type = _TYPES[field_text]
        elif index == len(fields) - 1:
            # <Key-period> and <Key-.> are the same binding: X11's names for
            # the punctuation keys are what tkinter documentation uses, and
            # without resolving them here such a binding could never fire,
            # because the event carries the character.
            detail = canonical_keysym(field_text)
        else:
            raise ValueError(
                f"cannot parse binding sequence {sequence!r}: {field_text!r} is "
                "neither a modifier nor an event type, and only the last field "
                "may be a detail"
            )

    if not event_type:
        # <Control-c> and <F1> name no type; Tk reads them as key presses.
        # A button needs its type spelled out, since "1" alone is the keysym.
        if not detail:
            raise ValueError(
                f"cannot parse binding sequence {sequence!r}: no event type"
            )
        event_type = "Key"
    return EventPattern(
        type=event_type, detail=detail, modifiers=modifiers, repeat=repeat
    )


def _same_event(pattern: EventPattern, event: EventPattern) -> bool:
    """The type and the detail match - what makes Tk count a pattern as met."""
    return pattern.type == event.type and (
        not pattern.detail or pattern.detail == event.detail
    )


def _modifiers_fit(pattern: EventPattern, event: EventPattern) -> bool:
    if pattern.modifiers & MOD_ANY:
        return True
    wanted = pattern.modifiers & ~MOD_ANY
    return wanted & event.modifiers == wanted


def pattern_for_event(event: Event) -> EventPattern:
    """Convert an input event into the pattern that bindings match against.

    Raises:
        TypeError: If the event is of a kind with no binding representation.
    """
    if isinstance(event, KeyEvent):
        return EventPattern(type="Key", detail=event.keysym, modifiers=event.modifiers)
    if isinstance(event, MouseEvent):
        return _mouse_pattern(event)
    if isinstance(event, ResizeEvent):
        return EventPattern(type="Configure")
    raise TypeError(f"no binding pattern for event of type {type(event).__name__}")


def _mouse_pattern(event: MouseEvent) -> EventPattern:
    """The pattern for a mouse event.

    Wheel movement is reported by curses as buttons 4 and 5, which is also how
    X11 reports it, so it stays a ``Button`` event; ``<MouseWheel>`` matches it
    too, for code written against the Windows and macOS spelling.
    """
    if event.state in _MOUSE_PRESS_STATES:
        return EventPattern(
            type="Button",
            detail=str(event.button),
            modifiers=event.modifiers,
            repeat=_MOUSE_PRESS_STATES[event.state],
        )
    if event.state == "released":
        # The button being released is still held as far as the modifier is
        # concerned, which is what makes <B1-ButtonRelease-1> - the pattern
        # dnd builds to catch the end of a drag - match anything at all.
        return EventPattern(
            type="ButtonRelease",
            detail=str(event.button),
            modifiers=event.modifiers | MOD_BUTTONS.get(event.button, 0),
        )
    modifiers = event.modifiers
    if event.state == "drag":
        modifiers |= MOD_BUTTONS.get(event.button, 0)
    return EventPattern(type="Motion", modifiers=modifiers)


@dataclass
class _Promoted:
    """A sequence partway through, as tkBind.c keeps it: a "promoted" entry.

    It sits at the level of how many of its events have matched, belongs to
    one binding tag and one window, and is ``expired`` when the event it was
    waiting for came and went, ``keep`` when it must survive this event's
    clean-up - as a fresh promotion always does.
    """

    tag: str
    sequence: PatternSequence
    window: object
    expired: bool = False
    keep: bool = True


def _is_key(type_: str) -> bool:
    return type_ in ("Key", "KeyRelease")


def _is_button(type_: str) -> bool:
    return type_ in ("Button", "ButtonRelease")


@dataclass
class Binding:
    """One registered callback.

    Attributes:
        funcid: Handle returned by ``bind()``, used to remove just this one.
        func: The callback, invoked with the event.
        pattern: What it matches.
    """

    funcid: str
    func: Callable[[Any], Any]
    pattern: EventPattern | PatternSequence

    @property
    def sequence(self) -> str:
        """The canonical sequence string this binding was made for."""
        return str(self.pattern)


class BindingTable:
    """Callbacks registered against event patterns, grouped by binding tag.

    A tag is any string: a widget path, a class name such as ``Button``, or
    ``all``. What tags exist and in what order they are consulted is the
    caller's business; this table only stores and dispatches.
    """

    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        """
        Args:
            on_change: Called after anything is bound or unbound. The one
                thing outside this table that depends on *what* is bound
                rather than on what fires is the terminal: a key it would
                otherwise turn into a signal has to be claimed back while a
                binding wants it.
        """
        self._tags: dict[str, dict[EventPattern | PatternSequence, list[Binding]]] = {}
        # Maps a funcid back to where it lives, so unbind() by id does not
        # have to scan every tag.
        self._located: dict[str, tuple[str, EventPattern | PatternSequence]] = {}
        #: Sequences partway through, by how many of their events have
        #: matched less one: level 0 holds those one event in. Tk's promArr.
        self._levels: list[list[_Promoted]] = []
        self._ids = itertools.count(1)
        self._on_change = on_change

    def _changed(self) -> None:
        """Tell whoever is listening that the set of bindings has moved."""
        if self._on_change is not None:
            self._on_change()

    def details_bound_with(self, modifiers: int, type: str = "Key") -> set[str]:
        """Details bound on ``type`` events that ask for exactly ``modifiers``.

        Args:
            modifiers: The modifier set a pattern must require, ``MOD_ANY``
                aside. ``<Control-c>`` asks for Control and matches here;
                ``<Key-c>`` asks for nothing and does not.
            type: Event type to look at.

        Returns:
            Every such pattern's detail, across every tag. Answers "is
            anything, anywhere, waiting for this key" - which is the
            question, since a binding on any widget is reason enough to stop
            the terminal eating the key.
        """
        # Every event of a sequence counts: <Control-c><Control-c> needs the
        # terminal to deliver Control-C as much as <Control-c> does.
        return {
            pattern.detail
            for patterns in self._tags.values()
            for bound, bindings in patterns.items()
            if bindings
            for pattern in (
                bound.patterns if isinstance(bound, PatternSequence) else (bound,)
            )
            if pattern.type == type
            and pattern.detail
            and pattern.modifiers & ~MOD_ANY == modifiers
        }

    def bind(
        self,
        tag: str,
        pattern: EventPattern | PatternSequence,
        func: Callable[[Any], Any],
        add: bool = False,
    ) -> str:
        """Register ``func`` for ``pattern`` under ``tag`` and return its id.

        Without ``add`` the new callback replaces everything already bound to
        that exact pattern on that tag, which is Tk's default and the reason
        rebinding in a loop does not accumulate handlers.
        """
        patterns = self._tags.setdefault(tag, {})
        existing = patterns.get(pattern)
        if existing is None or not add:
            if existing is not None:
                self._forget_ids(existing)
            existing = []
            patterns[pattern] = existing
        binding = Binding(f"bind#{next(self._ids)}", func, pattern)
        existing.append(binding)
        self._located[binding.funcid] = (tag, pattern)
        self._changed()
        return binding.funcid

    def unbind(
        self,
        tag: str,
        pattern: EventPattern | PatternSequence | None = None,
        funcid: str | None = None,
    ) -> None:
        """Remove bindings from ``tag``.

        With a ``funcid`` only that callback goes; with only a ``pattern``
        every callback on it goes; with neither the tag is cleared. Removing
        something that is not there is not an error, so teardown paths need no
        guard.
        """
        if funcid is not None:
            self._unbind_id(funcid)
            self._changed()
            return
        if pattern is None:
            for bindings in self._tags.pop(tag, {}).values():
                self._forget_ids(bindings)
            self._changed()
            return
        patterns = self._tags.get(tag)
        if patterns is None:
            return
        self._forget_ids(patterns.pop(pattern, []))
        if not patterns:
            del self._tags[tag]
        self._changed()

    def bindings(
        self, tag: str, pattern: EventPattern | PatternSequence | None = None
    ) -> list[Binding]:
        """Bindings on ``tag``, or only those on ``pattern`` if given.

        Exact pattern lookup, not matching: this answers "what is bound here",
        which is what ``bind()`` reports back, rather than "what would fire".
        """
        patterns = self._tags.get(tag, {})
        if pattern is not None:
            return list(patterns.get(pattern, []))
        return [binding for bindings in patterns.values() for binding in bindings]

    def sequences(self, tag: str) -> tuple[str, ...]:
        """Canonical sequence strings currently bound on ``tag``.

        A tuple, because this is what ``bind()`` with no callback hands back
        and tkinter's answers with one - measured on Tk 9.0.2, ``()`` and
        ``('a',)``. A list is the kind of difference that breaks real code
        quietly: ``widget.bind() + ('x',)`` raises rather than misbehaving
        somewhere later.
        """
        return tuple(str(pattern) for pattern in self._tags.get(tag, {}))

    def tags(self) -> list[str]:
        """Tags that currently hold at least one binding."""
        return list(self._tags)

    def matching(
        self,
        tag: str,
        patterns: Iterable[EventPattern],
        completed: Iterable[PatternSequence] = (),
        raised: Mapping[str, Raised] | None = None,
    ) -> Iterator[Binding]:
        """Bindings on ``tag`` for the most particular pattern that fires.

        One pattern per tag, not every pattern that matches. With ``<Key>``
        and ``<Shift-Key>`` both bound on a widget, a shifted key runs the
        second and not the first - Tk chooses the most specific match within
        a tag and then moves on to the next tag, so a widget binding and a
        class binding both still get their turn.

        Yields in registration order within that pattern, so handlers added
        with ``add=True`` run in the order they were added.

        ``completed`` are the sequences on this tag that this event finished;
        they compete with the single patterns by the same ranking, so a
        finished ``<Control-x><Control-s>`` runs instead of ``<Control-s>``.

        ``raised`` are the virtual events a physical event raised, by name.
        Each competes with the physical bindings for the one slot, ranked as
        the physical pattern that raised it; a tie goes to the physical
        binding, then to the virtual event defined first. Measured on Tk
        9.0.2 - ``<Up>`` beats ``<<PrevLine>>``, ``<<PrevLine>>`` beats
        ``<Key>``, Shift-Up runs ``<<SelectPrevLine>>`` and not
        ``<<PrevLine>>``. They used to be treated as two events, and both
        ran. TkCurses-hkul.
        """
        registered = self._tags.get(tag)
        if not registered:
            return
        wanted = list(patterns)
        finished = set(completed)
        raised = raised or {}
        # Grouped by event type, so that a raised virtual event competes in
        # the group of the physical event that raised it.
        best: dict[str, tuple[tuple[int, int, int], int, int]] = {}
        chosen: dict[str, list[Binding]] = {}
        for pattern, bindings in list(registered.items()):
            if isinstance(pattern, PatternSequence):
                if pattern not in finished:
                    continue
            elif not any(pattern.matches(candidate) for candidate in wanted):
                continue
            via = None
            if isinstance(pattern, EventPattern) and pattern.is_virtual:
                via = raised.get(pattern.detail or "")
            if via is None:
                kind, rank = pattern.type, (pattern.specificity, 1, 0)
            else:
                kind, rank = via.type, (via.specificity, 0, -via.order)
            if kind not in best or rank > best[kind]:
                best[kind], chosen[kind] = rank, list(bindings)
            elif rank == best[kind]:
                # Two different patterns, equally particular, both matching:
                # rare, and no reason to prefer whichever was registered
                # first, so both run.
                chosen[kind].extend(bindings)
        for kind in chosen:
            yield from chosen[kind]

    def dispatch(
        self,
        tags: Iterable[str],
        event: Any,
        patterns: Iterable[EventPattern],
        raised: Mapping[str, Raised] | None = None,
    ) -> bool:
        """Run every binding on ``tags`` that matches, in tag order.

        ``raised`` is passed to :meth:`matching`: what the physical event
        among ``patterns`` raised, from :meth:`VirtualEvents.raised_ranks`.

        Returns True if a callback returned ``"break"``, which stops the event
        there: remaining callbacks and remaining tags are skipped, and the
        caller should treat the event as handled.
        """
        wanted = list(patterns)
        tags = list(tags)
        completed = self._advance(tags, wanted, getattr(event, "widget", None))
        for tag in tags:
            found = self.matching(tag, wanted, completed.get(tag, ()), raised)
            for binding in list(found):
                if binding.func(event) == BREAK:
                    return True
        return False

    # ------------------------------------------------------------- sequences
    #
    # Multi-event sequences, followed across events the way tkBind.c follows
    # them (Tk_BindEvent, MatchPatterns), READ from Tk 9.0.2's source and
    # MEASURED against both wish8.6 and wish9.0, which agree (TkCurses-jfm):
    #
    # * an event that matches a sequence's first pattern PROMOTES it to level
    #   0, bound to the event's window; each later event that matches the next
    #   pattern promotes it a level, and the last one fires it.
    # * a waiting sequence is DROPPED by an event of the type it waits for
    #   with another key or button, or the wrong modifiers; by a Key event
    #   while it waits for a Button, or the other way round; and by any event
    #   in another window - so a sequence never spans two widgets.
    # * every other event leaves it waiting: motion, focus, a release. There
    #   is NO timeout - Ctrl-x, a pause of any length, Ctrl-s still fires.
    # * the quirk, from how the lists are kept: an event is tried as a fresh
    #   start while the entry it is dropping is still on level 0, and a
    #   sequence already listed there is not promoted again. So for <a><b>,
    #   "a a b" does NOT fire and "a a a b" does; for <a><b><c>, "a b a b c"
    #   does, its drop happening on another level. Measured, both Tks.
    #
    # Not reproduced, because curses never delivers them: a lone modifier key
    # press, which Tk ignores in a sequence, and a key release.

    def _advance(
        self, tags: list[str], wanted: list[EventPattern], window: object
    ) -> dict[str, list[PatternSequence]]:
        """Move every sequence along for one event; return those it finished."""
        physical = next((p for p in wanted if not p.is_virtual), None)
        if physical is None or not (self._levels or self._has_sequences()):
            return {}
        completed: dict[str, list[PatternSequence]] = {}
        # Waiting sequences first, the highest level first, as Tk does.
        for level in range(len(self._levels) - 1, -1, -1):
            for entry in self._levels[level]:
                if entry.tag not in tags or entry.window is not window:
                    continue
                nxt = entry.sequence.patterns[level + 1]
                entry.keep = False
                if not _same_event(nxt, physical):
                    continue
                entry.expired = True
                if not _modifiers_fit(nxt, physical):
                    continue
                if level + 2 == len(entry.sequence.patterns):
                    if nxt.repeat <= physical.repeat:
                        completed.setdefault(entry.tag, []).append(entry.sequence)
                    else:
                        entry.expired, entry.keep = False, True
                else:
                    self._promote(level + 1, entry.tag, entry.sequence, window)
        # Then fresh starts: a sequence whose first pattern this event is.
        for tag in tags:
            for bound in list(self._tags.get(tag, {})):
                if not isinstance(bound, PatternSequence):
                    continue
                first = bound.patterns[0]
                if first.matches(physical):
                    self._promote(0, tag, bound, window)
        self._clean_up(physical, window)
        return completed

    def _has_sequences(self) -> bool:
        return any(
            isinstance(bound, PatternSequence)
            for patterns in self._tags.values()
            for bound in patterns
        )

    def _promote(
        self, level: int, tag: str, sequence: PatternSequence, window: object
    ) -> None:
        """List a sequence at ``level`` unless it is already listed there.

        Already listed is checked against EVERY entry at that level, stale
        ones included - which is where the "a a b" quirk comes from.
        """
        while len(self._levels) <= level:
            self._levels.append([])
        listed = self._levels[level]
        if any(e.tag == tag and e.sequence == sequence for e in listed):
            return
        listed.append(_Promoted(tag, sequence, window))

    def _clean_up(self, physical: EventPattern, window: object) -> None:
        """Drop what this event ended, keeping what it just promoted."""
        for level, listed in enumerate(self._levels):
            kept: list[_Promoted] = []
            for entry in listed:
                if entry.keep:
                    entry.keep = False
                    kept.append(entry)
                    continue
                nxt = entry.sequence.patterns[level + 1]
                if (
                    entry.expired
                    or entry.window is not window
                    or (
                        nxt.detail
                        and physical.detail
                        and nxt.type == physical.type
                        and nxt.detail != physical.detail
                    )
                    or (_is_button(nxt.type) and _is_key(physical.type))
                    or (_is_key(nxt.type) and _is_button(physical.type))
                ):
                    continue
                kept.append(entry)
            listed[:] = kept
        while self._levels and not self._levels[-1]:
            self._levels.pop()

    def _unbind_id(self, funcid: str) -> None:
        """Remove one callback by its handle."""
        located = self._located.pop(funcid, None)
        if located is None:
            return
        tag, pattern = located
        patterns = self._tags.get(tag)
        if patterns is None:
            return
        bindings = patterns.get(pattern)
        if bindings is None:
            return
        patterns[pattern] = [b for b in bindings if b.funcid != funcid]
        if not patterns[pattern]:
            del patterns[pattern]
        if not patterns:
            del self._tags[tag]

    def _forget_ids(self, bindings: list[Binding]) -> None:
        """Drop the funcid index entries for bindings being discarded."""
        for binding in bindings:
            self._located.pop(binding.funcid, None)


@dataclass(frozen=True)
class Raised:
    """A virtual event a physical one raised: the physical event's type, the
    specificity of the registered pattern that matched, and the order the
    virtual event was defined in."""

    type: str
    specificity: tuple[int, int, int]
    order: int


class VirtualEvents:
    """Virtual event names and the physical sequences that raise them.

    Tk ships defaults such as ``<<Copy>>`` and ``<<Paste>>``; those are
    supplied by the widget layer rather than hardcoded here, so a platform or
    a configuration file can choose different keys without editing this class.
    """

    def __init__(self) -> None:
        self._events: dict[str, list[EventPattern | PatternSequence]] = {}

    def add(self, virtual: str, *patterns: EventPattern | PatternSequence) -> None:
        """Make ``patterns`` raise ``virtual``, keeping any already added.

        A sequence of several events is accepted and kept, and reported by
        ``info``, and never raises anything - as in Tk 9.0.2, measured:
        ``event add <<Save>> <Control-x><Control-s>`` is listed and does not
        fire, "virtual events cannot promote" (tkBind.c). TkCurses-jfm.
        """
        name = self._name(virtual)
        registered = self._events.setdefault(name, [])
        for pattern in patterns:
            if pattern not in registered:
                registered.append(pattern)

    def delete(self, virtual: str, *patterns: EventPattern | PatternSequence) -> None:
        """Stop ``patterns`` raising ``virtual``; with none given, remove all."""
        name = self._name(virtual)
        if not patterns:
            self._events.pop(name, None)
            return
        registered = self._events.get(name)
        if registered is None:
            return
        self._events[name] = [p for p in registered if p not in patterns]
        if not self._events[name]:
            del self._events[name]

    def info(self, virtual: str) -> tuple[EventPattern | PatternSequence, ...]:
        """Physical patterns registered for ``virtual``."""
        return tuple(self._events.get(self._name(virtual), ()))

    def names(self) -> list[str]:
        """Every virtual event name defined, in ``<<Name>>`` form."""
        return [f"<<{name}>>" for name in self._events]

    def raised_by(self, pattern: EventPattern) -> list[EventPattern]:
        """Virtual patterns that ``pattern`` should also fire.

        A physical event raises its virtuals in addition to its own bindings,
        so a widget with both ``<Control-v>`` and ``<<Paste>>`` bound runs
        both, as it does under Tk.
        """
        return [
            EventPattern(type="Virtual", detail=name)
            for name, registered in self._events.items()
            if any(candidate.matches(pattern) for candidate in registered)
        ]

    def raised_ranks(self, pattern: EventPattern) -> dict[str, Raised]:
        """What ``pattern`` raises, each ranked for :meth:`BindingTable.matching`:
        as the most particular of its registered patterns that matched, and
        by when it was defined."""
        found: dict[str, Raised] = {}
        for order, (name, registered) in enumerate(self._events.items()):
            ranks = [
                candidate.specificity
                for candidate in registered
                if isinstance(candidate, EventPattern) and candidate.matches(pattern)
            ]
            if ranks:
                found[name] = Raised(pattern.type, max(ranks), order)
        return found

    @staticmethod
    def _name(virtual: str) -> str:
        """Strip the ``<<>>`` brackets, accepting a name given either way."""
        match = _VIRTUAL_RE.match(virtual)
        if match:
            return match.group(1)
        if virtual.startswith("<") or virtual.endswith(">"):
            raise ValueError(f"{virtual!r} is not a virtual event name")
        return virtual
