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
    from collections.abc import Callable, Iterable, Iterator

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
#: above the ``MOD_*`` bits in :mod:`tkcurses._core.events` rather than
#: alongside them: those describe a key that was actually pressed, this one
#: describes how to match, and no input event ever carries it.
MOD_ANY = 0x100

#: Modifier names accepted in a sequence, including the aliases tkinter takes
#: from macOS and X11 so that code written for either binds the same thing.
_MODIFIERS: dict[str, int] = {
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
        catches every key. A single-click pattern also fires on a double or
        triple click, matching Tk.

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
        if self.repeat > 1 and self.repeat != event.repeat:
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
        ``<Shift-Key>`` - and among patterns with the same detail, more
        modifiers wins. ``Any`` is not counted: it waives the comparison
        rather than demanding anything, so a pattern using it is the least
        particular of all.
        """
        modifiers = self.modifiers & ~MOD_ANY
        return (int(bool(self.detail)), int(modifiers).bit_count(), self.repeat)

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


#: Modifier flags in the order Tk writes them, used to render a pattern back
#: into a sequence string. ``Any`` is deliberately absent: it is a matching
#: instruction, and reproducing it would make two different patterns print the
#: same.
_CANONICAL_MODIFIERS: tuple[tuple[int, str], ...] = (
    (MOD_CTRL, "Control"),
    (MOD_ALT, "Alt"),
    (MOD_SHIFT, "Shift"),
    (MOD_META, "Meta"),
)


def parse_sequence(sequence: str) -> EventPattern:
    """Parse a tkinter binding sequence into an :class:`EventPattern`.

    Accepts the bracketed form (``<Control-Key-a>``, ``<Double-Button-1>``,
    ``<<Paste>>``) and the bare form, where a single character stands for a
    key press: ``"a"`` means ``<Key-a>``.

    Raises:
        ValueError: If the sequence is malformed, names something unknown, or
            chains several events (``<Control-x><Control-s>``), which has no
            implementation here yet.
    """
    if not sequence:
        raise ValueError("binding sequence is empty")

    virtual = _VIRTUAL_RE.match(sequence)
    if virtual:
        return EventPattern(type="Virtual", detail=virtual.group(1))

    if not sequence.startswith("<"):
        if len(sequence) != 1:
            raise ValueError(
                f"cannot parse binding sequence {sequence!r}: a bare sequence "
                "must be a single character; bracket it as <Key-...> otherwise"
            )
        return EventPattern(type="Key", detail=_bare_keysym(sequence))

    physical = _PHYSICAL_RE.match(sequence)
    if physical is None:
        raise ValueError(
            f"cannot parse binding sequence {sequence!r}: multi-event sequences "
            "such as <Control-x><Control-s> are not supported"
        )
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
        return EventPattern(
            type="ButtonRelease",
            detail=str(event.button),
            modifiers=event.modifiers,
        )
    return EventPattern(type="Motion", modifiers=event.modifiers)


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
    pattern: EventPattern

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
        self._tags: dict[str, dict[EventPattern, list[Binding]]] = {}
        # Maps a funcid back to where it lives, so unbind() by id does not
        # have to scan every tag.
        self._located: dict[str, tuple[str, EventPattern]] = {}
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
        return {
            pattern.detail
            for patterns in self._tags.values()
            for pattern, bindings in patterns.items()
            if bindings
            and pattern.type == type
            and pattern.detail
            and pattern.modifiers & ~MOD_ANY == modifiers
        }

    def bind(
        self,
        tag: str,
        pattern: EventPattern,
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
        self, tag: str, pattern: EventPattern | None = None, funcid: str | None = None
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

    def bindings(self, tag: str, pattern: EventPattern | None = None) -> list[Binding]:
        """Bindings on ``tag``, or only those on ``pattern`` if given.

        Exact pattern lookup, not matching: this answers "what is bound here",
        which is what ``bind()`` reports back, rather than "what would fire".
        """
        patterns = self._tags.get(tag, {})
        if pattern is not None:
            return list(patterns.get(pattern, []))
        return [binding for bindings in patterns.values() for binding in bindings]

    def sequences(self, tag: str) -> list[str]:
        """Canonical sequence strings currently bound on ``tag``."""
        return [str(pattern) for pattern in self._tags.get(tag, {})]

    def tags(self) -> list[str]:
        """Tags that currently hold at least one binding."""
        return list(self._tags)

    def matching(self, tag: str, patterns: Iterable[EventPattern]) -> Iterator[Binding]:
        """Bindings on ``tag`` for the most particular pattern that fires.

        One pattern per tag, not every pattern that matches. With ``<Key>``
        and ``<Shift-Key>`` both bound on a widget, a shifted key runs the
        second and not the first - Tk chooses the most specific match within
        a tag and then moves on to the next tag, so a widget binding and a
        class binding both still get their turn.

        Yields in registration order within that pattern, so handlers added
        with ``add=True`` run in the order they were added.
        """
        registered = self._tags.get(tag)
        if not registered:
            return
        wanted = list(patterns)
        # Grouped by event type, because a physical event and the virtual
        # event it triggers are two different events and Tk delivers both.
        # Specificity chooses between patterns for the *same* event, so
        # <Key> and <Shift-Key> compete while <Key> and <<Paste>> do not.
        best: dict[str, tuple[int, int, int]] = {}
        chosen: dict[str, list[Binding]] = {}
        for pattern, bindings in list(registered.items()):
            if not any(pattern.matches(candidate) for candidate in wanted):
                continue
            kind, rank = pattern.type, pattern.specificity
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
        self, tags: Iterable[str], event: Any, patterns: Iterable[EventPattern]
    ) -> bool:
        """Run every binding on ``tags`` that matches, in tag order.

        Returns True if a callback returned ``"break"``, which stops the event
        there: remaining callbacks and remaining tags are skipped, and the
        caller should treat the event as handled.
        """
        wanted = list(patterns)
        for tag in tags:
            for binding in list(self.matching(tag, wanted)):
                if binding.func(event) == BREAK:
                    return True
        return False

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


class VirtualEvents:
    """Virtual event names and the physical sequences that raise them.

    Tk ships defaults such as ``<<Copy>>`` and ``<<Paste>>``; those are
    supplied by the widget layer rather than hardcoded here, so a platform or
    a configuration file can choose different keys without editing this class.
    """

    def __init__(self) -> None:
        self._events: dict[str, list[EventPattern]] = {}

    def add(self, virtual: str, *patterns: EventPattern) -> None:
        """Make ``patterns`` raise ``virtual``, keeping any already added."""
        name = self._name(virtual)
        registered = self._events.setdefault(name, [])
        for pattern in patterns:
            if pattern not in registered:
                registered.append(pattern)

    def delete(self, virtual: str, *patterns: EventPattern) -> None:
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

    def info(self, virtual: str) -> tuple[EventPattern, ...]:
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

    @staticmethod
    def _name(virtual: str) -> str:
        """Strip the ``<<>>`` brackets, accepting a name given either way."""
        match = _VIRTUAL_RE.match(virtual)
        if match:
            return match.group(1)
        if virtual.startswith("<") or virtual.endswith(">"):
            raise ValueError(f"{virtual!r} is not a virtual event name")
        return virtual
