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

"""The contents of a Text widget: lines, indices, marks and tags.

Everything a Text does to what it holds happens here, away from curses and
from widget options, because this is the part with the awkward cases -
deleting a range that runs backwards, a mark left pointing into text that has
gone, a tag whose range an edit has cut in half.

Three ideas from Tk are kept exactly, because code written against tkinter
depends on all three:

**Indices are positions between characters**, written ``line.char``. Lines
count from 1 and characters from 0, so ``1.0`` is the very beginning. As with
:class:`~tkcurses._core.editing.TextField`, thinking of an index as a
character rather than as a gap is what produces off-by-one errors.

**There is always a final newline.** A Text holding ``abc`` really holds
``abc\\n``, and no edit can remove that last character. It is why
``get("1.0", "end")`` comes back with a newline nobody typed, and why ``end``
is ``2.0`` rather than ``1.3``. Tk works this way and hiding it would make
every index this module returns disagree with tkinter's.

**Marks have gravity.** A mark is a position that survives editing, and when
text arrives exactly at one, its gravity says whether it ends up before the
new text or after it. The insert cursor has right gravity, which is what makes
typing push it along instead of leaving it behind.

Internally the whole buffer is one string and every position is an offset into
it. Lines are a view of that string, not the thing itself: an edit then shifts
marks and tag ranges by simple arithmetic rather than by walking a list of
lines and fixing up the ones after the change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["Index", "TextBuffer", "TextIndexError"]

#: What counts as part of a word for ``wordstart`` and ``wordend``. Tk's rule:
#: letters, digits and underscores are word characters and everything else is
#: a single-character word of its own.
_WORD = re.compile(r"\w")

#: ``+3 chars``, ``-2 lines``, and the compact ``+3c`` / ``-2l`` Tk also takes.
_COUNT = re.compile(r"^([+-])\s*(\d+)\s*([a-z]+)$")

_GRAVITIES = ("left", "right")


@dataclass(frozen=True)
class _Edit:
    """One applied change, holding enough to reverse itself.

    ``text`` is what moved: for an insertion the characters put in, for a
    deletion the characters taken out. Undoing an insertion deletes that
    span; undoing a deletion puts the text back at the same offset. Marks
    and tags are then moved by :meth:`TextBuffer._shift` on the way back
    exactly as they were on the way there, so nothing needs recording about
    them.
    """

    at: int
    text: str
    inserted: bool


class TextIndexError(ValueError):
    """An index string that means nothing."""


@dataclass(frozen=True, order=True)
class Index:
    """A position between two characters.

    Ordered, so two indices can be compared with ``<`` directly rather than
    through :meth:`TextBuffer.compare` - which is what makes the range
    arithmetic below readable.

    Attributes:
        line: Line number, counting from 1 as Tk does.
        char: Characters from the start of that line, counting from 0.
    """

    line: int
    char: int

    def __str__(self) -> str:
        """``line.char``, the form Tk prints and accepts."""
        return f"{self.line}.{self.char}"


class TextBuffer:
    """The text, and everything that points into it.

    Every operation leaves four things consistent: the final newline is still
    there, marks still name positions that exist, tag ranges are still sorted
    and non-overlapping, and nothing describes text that an edit has removed.
    """

    def __init__(self, text: str = "") -> None:
        self._text = text if text.endswith("\n") else text + "\n"
        #: The split of :attr:`_text`, or None when it needs doing again.
        #: Every assignment to ``_text`` clears it.
        self._lines: list[str] | None = None
        #: Line start offsets, rebuilt with :attr:`lines`.
        self._starts: list[int] | None = None
        self._marks: dict[str, tuple[int, str]] = {}
        self._tags: dict[str, list[tuple[int, int]]] = {}
        #: Applied edits, newest last, in groups that undo together. A
        #: separator closes the open group; see :meth:`edit_separator`.
        self._done: list[list[_Edit]] = []
        #: Groups taken back by :meth:`edit_undo`, newest last. Any new edit
        #: clears it - measured against Tk, where a fresh edit after an undo
        #: leaves "nothing to redo".
        self._undone: list[list[_Edit]] = []
        #: True while undoing or redoing, so the reversal is not itself
        #: recorded. Without this the stack never empties: each undo pushes
        #: its own inverse and the next one puts the edit straight back.
        self._replaying = False
        #: True when the next recorded edit should start a new group.
        self._separate = True
        #: Whether edits are recorded at all - the widget's ``-undo``.
        self.undo_enabled = False
        #: How many groups the undo stack keeps, oldest dropped first - the
        #: widget's ``-maxundo``. 0 or below keeps them all, as Tk's does.
        self.max_undo = 0

    # --------------------------------------------------------------- shape

    @property
    def text(self) -> str:
        """Everything, final newline included."""
        return self._text

    @property
    def lines(self) -> list[str]:
        """The lines, without their newlines.

        A buffer holding only its final newline has one empty line, not none:
        an empty Text still has a line 1 for the cursor to sit on.

        Split once and kept until the text changes. It was split on every
        access, and the callers are not occasional: ``offset_of`` walks this
        for each index it resolves, and a redraw resolves one per visible
        row. Measured on 5000 lines, a single repaint split the whole buffer
        528 times and ran 13 million len() calls, for 353ms - against 0.31ms
        for a Listbox of the same size. TkCurses-g9w.
        """
        if self._lines is None:
            self._lines = self._text.split("\n")[:-1]
            self._starts = None
        return self._lines

    def end(self) -> Index:
        """The index just past everything, which is Tk's ``end``."""
        return self.index_of(len(self._text))

    def line_count(self) -> int:
        """How many lines there are."""
        return self._text.count("\n")

    def line_length(self, line: int) -> int:
        """Characters on one line, not counting its newline."""
        lines = self.lines
        if not 1 <= line <= len(lines):
            return 0
        return len(lines[line - 1])

    # ------------------------------------------------------ offsets and indices

    @property
    def _line_starts(self) -> list[int]:
        """Where each line begins in the whole string, line 1 first.

        Built with the split and thrown away with it. Without it
        :meth:`offset_of` walks every line to reach one, and a redraw asks
        for one index per visible row - so a 5000-line buffer was walked 528
        times per repaint even once the split itself was cached.
        """
        if self._starts is None:
            starts, at = [], 0
            for line in self.lines:
                starts.append(at)
                at += len(line) + 1
            self._starts = starts
        return self._starts

    def offset_of(self, index: Index) -> int:
        """Where an index falls in the whole string, clamped to it."""
        index = self.clamp(index)
        starts = self._line_starts
        position = index.line - 1
        if 0 <= position < len(starts):
            return starts[position] + index.char
        return len(self._text)

    def index_of(self, offset: int) -> Index:
        """The index at a position in the whole string."""
        offset = max(0, min(offset, len(self._text)))
        before = self._text[:offset]
        line = before.count("\n") + 1
        char = offset - (before.rfind("\n") + 1)
        return Index(line, char)

    def clamp(self, index: Index) -> Index:
        """Pull an index inside the text.

        A line past the end becomes ``end``, and a character past the end of
        its line becomes that line's end rather than wrapping onto the next -
        which is what Tk does, and what keeps ``insert lineend`` meaningful
        on the last line.
        """
        lines = self.lines
        if index.line < 1:
            return Index(1, 0)
        if index.line > len(lines):
            return Index(len(lines) + 1, 0)
        return Index(index.line, max(0, min(index.char, len(lines[index.line - 1]))))

    # ----------------------------------------------------------- index strings

    def index(self, spec: Index | str) -> Index:
        """Resolve one of Tk's index strings.

        Understands ``line.char`` (with ``end`` for the character), ``end``,
        any mark name, ``tag.first`` and ``tag.last``, and the modifiers
        ``±N chars``, ``±N lines``, ``linestart``, ``lineend``, ``wordstart``
        and ``wordend``. ``@x,y`` is not resolved here: it means a position on
        screen, which only the widget knows about, so the widget turns it into
        an :class:`Index` first.

        Raises:
            TextIndexError: If the string names nothing.
        """
        if isinstance(spec, Index):
            return self.clamp(spec)
        text = str(spec).strip()
        if not text:
            raise TextIndexError('bad text index ""')
        base, modifiers = self._split_modifiers(text)
        index = self._resolve_base(base)
        for modifier in modifiers:
            index = self._apply_modifier(index, modifier)
        return self.clamp(index)

    @staticmethod
    def _split_modifiers(text: str) -> tuple[str, list[str]]:
        """Separate the base index from the modifiers that follow it.

        Tk allows ``insert+1c`` with no spaces as well as ``insert + 1 chars``,
        so the split looks for the signs rather than for whitespace, and the
        word modifiers are taken off the end first.
        """
        words = text.split()
        modifiers: list[str] = []
        while words and words[-1] in ("linestart", "lineend", "wordstart", "wordend"):
            modifiers.insert(0, words.pop())
        rest = " ".join(words)
        counts: list[str] = []
        while True:
            cut = max(rest.rfind("+"), rest.rfind("-"))
            # Not at position 0: a leading sign belongs to the base, and there
            # is no index string that legitimately starts with one.
            if cut <= 0:
                break
            counts.insert(0, rest[cut:].strip())
            rest = rest[:cut].strip()
        return rest, counts + modifiers

    def _resolve_base(self, base: str) -> Index:
        """The starting point, before any modifier is applied."""
        if base == "end":
            return self.end()
        if base in self._marks:
            return self.index_of(self._marks[base][0])
        if "." in base:
            line, _, char = base.partition(".")
            if line.isdigit() and char == "end":
                number = int(line)
                return Index(number, self.line_length(number))
            if line.isdigit() and char.isdigit():
                return Index(int(line), int(char))
            name, _, which = base.rpartition(".")
            if which in ("first", "last") and name in self._tags:
                ranges = self._tags[name]
                if not ranges:
                    raise TextIndexError(f"text doesn't contain any {name} tag")
                edge = ranges[0][0] if which == "first" else ranges[-1][1]
                return self.index_of(edge)
        raise TextIndexError(f'bad text index "{base}"')

    def _apply_modifier(self, index: Index, modifier: str) -> Index:
        """Move an index by one modifier."""
        if modifier == "linestart":
            return Index(index.line, 0)
        if modifier == "lineend":
            return Index(index.line, self.line_length(index.line))
        if modifier in ("wordstart", "wordend"):
            return self._word_edge(index, start=modifier == "wordstart")
        match = _COUNT.match(modifier.replace(" ", ""))
        if match is None:
            raise TextIndexError(f'bad text index modifier "{modifier}"')
        sign, digits, unit = match.groups()
        count = int(digits) * (1 if sign == "+" else -1)
        if "char".startswith(unit[:4]) or unit in ("c", "chars", "character"):
            return self.index_of(self.offset_of(index) + count)
        if unit in ("l", "line", "lines"):
            line = index.line + count
            return Index(line, min(index.char, self.line_length(line)))
        raise TextIndexError(f'bad text index modifier "{modifier}"')

    def _word_edge(self, index: Index, *, start: bool) -> Index:
        """The beginning or end of the word an index is in.

        Tk's rule: a run of word characters is a word, and anything else is a
        word one character long. The second half matters - without it,
        ``wordstart`` on a space would run backwards to the previous word.
        """
        line = index.line
        text = self.lines[line - 1] if 1 <= line <= len(self.lines) else ""
        char = max(0, min(index.char, len(text)))
        here = char if start else min(char, len(text) - 1)
        if here < 0 or here >= len(text) or not _WORD.match(text[here]):
            return Index(line, char if start else min(char + 1, len(text)))
        if start:
            while here > 0 and _WORD.match(text[here - 1]):
                here -= 1
            return Index(line, here)
        while here < len(text) and _WORD.match(text[here]):
            here += 1
        return Index(line, here)

    def compare(self, first: Index | str, op: str, last: Index | str) -> bool:
        """Compare two indices with one of Tk's six operators.

        Raises:
            TextIndexError: If the operator is not one of them.
        """
        a, b = self.index(first), self.index(last)
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
        raise TextIndexError(f'bad comparison operator "{op}"')

    # -------------------------------------------------------------- contents

    def get(self, first: Index | str, last: Index | str | None = None) -> str:
        """The text between two indices, or one character from ``first``."""
        start = self.offset_of(self.index(first))
        if last is None:
            return self._text[start : start + 1]
        stop = self.offset_of(self.index(last))
        if stop < start:
            start, stop = stop, start
        return self._text[start:stop]

    def insert(self, index: Index | str, text: str) -> Index:
        """Insert ``text``, returning the index just past what was inserted.

        Inserting at ``end`` puts the text *before* the final newline, since
        nothing can go after it.
        """
        if not text:
            return self.index(index)
        at = min(self.offset_of(self.index(index)), len(self._text) - 1)
        self._record(_Edit(at, text, inserted=True))
        self._text = self._text[:at] + text + self._text[at:]
        self._lines = None
        self._starts = None
        self._shift(at, len(text))
        return self.index_of(at + len(text))

    def delete(self, first: Index | str, last: Index | str | None = None) -> None:
        """Delete from ``first`` up to but not including ``last``.

        With no ``last`` this removes one character, matching Tk. A range
        given backwards is taken the right way round, because a selection
        dragged upwards produces exactly that. The final newline is never
        removed, whatever range is asked for.
        """
        start = self.offset_of(self.index(first))
        stop = start + 1 if last is None else self.offset_of(self.index(last))
        if stop < start:
            start, stop = stop, start
        stop = min(stop, len(self._text) - 1)
        start = min(start, stop)
        if start == stop:
            return
        self._record(_Edit(start, self._text[start:stop], inserted=False))
        self._text = self._text[:start] + self._text[stop:]
        self._lines = None
        self._starts = None
        self._shift(stop, -(stop - start), floor=start)

    def _shift(self, at: int, distance: int, *, floor: int | None = None) -> None:
        """Move every mark and tag edge after an edit.

        ``floor`` is where deleted text used to begin: anything that pointed
        inside the deleted range collapses to there rather than to wherever
        the arithmetic would otherwise put it.
        """

        def moved(offset: int, *, gravity: str = "right") -> int:
            if offset > at or (offset == at and gravity == "right" and distance > 0):
                return max(floor if floor is not None else 0, offset + distance)
            if floor is not None and offset > floor:
                return floor
            return offset

        self._marks = {
            name: (moved(offset, gravity=gravity), gravity)
            for name, (offset, gravity) in self._marks.items()
        }
        for name, ranges in self._tags.items():
            # A tag's two edges have OPPOSITE gravity, and that is what gives
            # Tk's rule for text inserted with no tags of its own: "the new
            # text will receive the tags of the characters both before and
            # after the insertion point; if a tag is present on only one of
            # these characters then it will not be applied" - the
            # INTERSECTION of the two sides.
            #
            # A start edge sitting exactly on the insertion moves right, so
            # the new text falls outside the tag. An end edge sitting there
            # stays, so the new text falls outside that one too. Text inside
            # a run has the start behind it and the end ahead of it, so it is
            # covered. Measured against Tk across five positions - inside a
            # run, both edges, between two different tags, and where one of
            # two tags continues - and the gravity rule reproduces all five.
            #
            # Both edges used right gravity before, which let a tag swallow
            # whatever was typed after it: an indented paragraph spread its
            # indent, a bold run made the next word bold. TkCurses-lx3.
            shifted = [
                (moved(start), moved(stop, gravity="left")) for start, stop in ranges
            ]
            self._tags[name] = _merge(pair for pair in shifted if pair[0] < pair[1])

    # ---------------------------------------------------------------- search

    def search(
        self,
        pattern: str,
        index: Index | str,
        stopindex: Index | str | None = None,
        *,
        backwards: bool = False,
        regexp: bool = False,
        nocase: bool = False,
    ) -> tuple[Index, int] | None:
        """Find ``pattern``, returning where it starts and how long it is.

        None when there is no match. The length is in characters and is
        what Tk's ``-count`` reports; for a regular expression the caller
        cannot work it out from the pattern, which is why it comes back
        here rather than being left to them.

        **Exact and regular-expression searches are two different
        searches**, not one with a flag, and this was measured against Tk
        rather than assumed:

        - An exact search runs over the whole buffer and **can match across
          a newline**: ``"abc\ndef"`` is found, with a count of 7.
        - A regular expression is matched **line by line**, so ``c.d``
          spanning a newline is not found at all, while ``c$`` and ``^d``
          match at the end and start of their own lines.

        Searching **wraps**: forwards runs to the end and round to the
        start, backwards the other way, stopping before the index it began
        at so a single match is never reported twice. ``stopindex`` is
        where to give up instead, which is how a caller asks for a search
        that does not wrap.

        An empty pattern matches at ``index`` with a count of 0, which is
        what Tk answers - not "no match", and not "everything".
        """
        start = self.offset_of(self.index(index))
        stop = None if stopindex is None else self.offset_of(self.index(stopindex))
        if not pattern:
            return self.index_of(start), 0
        found = self._search_span(
            pattern, start, stop, backwards=backwards, regexp=regexp, nocase=nocase
        )
        if found is None:
            return None
        at, length = found
        return self.index_of(at), length

    def _search_span(
        self,
        pattern: str,
        start: int,
        stop: int | None,
        *,
        backwards: bool,
        regexp: bool,
        nocase: bool,
    ) -> tuple[int, int] | None:
        """The offsets to look through, in order, and the first hit in them.

        Wrapping is expressed as two ranges rather than as arithmetic on a
        modulus: it is the same search run twice, and saying so keeps the
        two directions from needing different code.
        """
        size = len(self._text)
        if stop is not None:
            spans = [(stop, start)] if backwards else [(start, min(stop, size))]
        elif backwards:
            # Behind the cursor first, then round from the end back to it.
            spans = [(0, start), (start, size)]
        else:
            spans = [(start, size), (0, start)]
        for begin, end in spans:
            if begin >= end:
                continue
            hit = self._first_in(
                pattern, begin, end, backwards=backwards, regexp=regexp, nocase=nocase
            )
            if hit is not None:
                return hit
        return None

    def _first_in(
        self,
        pattern: str,
        begin: int,
        end: int,
        *,
        backwards: bool,
        regexp: bool,
        nocase: bool,
    ) -> tuple[int, int] | None:
        """The first match within one span, or the last one going backwards."""
        if regexp:
            return self._regexp_in(
                pattern, begin, end, backwards=backwards, nocase=nocase
            )
        haystack = self._text[begin:end]
        needle = pattern
        if nocase:
            haystack, needle = haystack.lower(), needle.lower()
        at = haystack.rfind(needle) if backwards else haystack.find(needle)
        if at < 0:
            return None
        return begin + at, len(pattern)

    def _regexp_in(
        self,
        pattern: str,
        begin: int,
        end: int,
        *,
        backwards: bool,
        nocase: bool,
    ) -> tuple[int, int] | None:
        """Match a regular expression line by line, as Tk does.

        Each line is matched on its own rather than the span as a whole,
        which is what makes ``^`` and ``$`` mean the edges of a line and
        what stops ``.`` reaching across a newline.
        """
        expression = re.compile(pattern, re.IGNORECASE if nocase else 0)
        best: tuple[int, int] | None = None
        for line_start, line in self._lines_between(begin, end):
            for match in expression.finditer(line):
                at = line_start + match.start()
                if not begin <= at < end:
                    continue
                hit = (at, match.end() - match.start())
                if not backwards:
                    return hit
                best = hit
        return best

    def _lines_between(self, begin: int, end: int) -> list[tuple[int, str]]:
        """Each line touching the span, as ``(offset of its start, text)``.

        Whole lines, deliberately: a pattern anchored with ``^`` has to see
        the real beginning of the line even when the span starts part way
        through it. Matches outside the span are filtered out afterwards.
        """
        starts = self._line_starts
        out = []
        for number, line in enumerate(self.lines):
            line_start = starts[number]
            if line_start >= end:
                break
            if line_start + len(line) < begin:
                continue
            out.append((line_start, line))
        return out

    # ------------------------------------------------------------------ undo

    def _record(self, edit: _Edit) -> None:
        """Note an edit that is about to be applied.

        Called from :meth:`insert` and :meth:`delete`, which is every path
        that changes the text - typing, backspace, deleting a selection and
        a program calling ``insert()`` all arrive at one of those two. There
        is no fourth way in, so nothing can quietly escape the stack.
        """
        if not self.undo_enabled or self._replaying:
            return
        # Measured against Tk: an edit made after an undo drops what was
        # undone, leaving "nothing to redo". The alternative - keeping it -
        # would let redo reapply an edit to text it no longer fits.
        self._undone.clear()
        if self._separate or not self._done:
            self._done.append([])
            self._separate = False
            self.trim_undo()
        self._done[-1].append(edit)

    def trim_undo(self) -> None:
        """Drop the oldest groups past :attr:`max_undo`.

        Measured on Tk 9.0.2: with ``-maxundo 2``, four separated edits undo
        two at a time and no more; and lowering it to 2 over five groups
        leaves two to undo. A group counts once however many edits it holds.
        """
        if self.max_undo > 0 and len(self._done) > self.max_undo:
            del self._done[: len(self._done) - self.max_undo]

    def edit_separator(self) -> None:
        """End the current group, so the next edit begins a new one."""
        self._separate = True

    def edit_reset(self) -> None:
        """Forget everything on both stacks."""
        self._done.clear()
        self._undone.clear()
        self._separate = True

    @property
    def undo_depth(self) -> int:
        """How many groups are waiting to be undone.

        Internal, with no counterpart in Tk: grouping is the part of undo
        that is invisible from outside and the part that is worth checking,
        since a stack that groups wrongly is correct edit by edit. The
        acceptance scenario shows this number so a person can watch a run
        of typing become one group rather than infer it from pressing
        Ctrl-Z and counting what comes back.
        """
        return len(self._done)

    @property
    def can_undo(self) -> bool:
        """Whether there is a group to take back."""
        return bool(self._done)

    @property
    def can_redo(self) -> bool:
        """Whether there is a group to put back."""
        return bool(self._undone)

    def edit_undo(self) -> bool:
        """Take back the newest group. False when there is nothing to take.

        The group is reversed newest edit first, which is the only order
        that works: the offsets in each record describe the text as it was
        when that edit was applied, so an earlier one cannot be undone until
        the later ones are gone.

        **Text comes back; tags do not.** A tag whose whole range was
        deleted is gone for good, because only the characters are recorded.
        That is not a shortcut - Tk does exactly the same, measured: tag a
        range, delete across it, undo, and ``tag_ranges`` is still empty
        while the text is back. Marks do return, because they are moved by
        :meth:`_shift` rather than stored.
        """
        if not self._done:
            return False
        group = self._done.pop()
        self._apply(reversed(group), forward=False)
        self._undone.append(group)
        self._separate = True
        return True

    def edit_redo(self) -> bool:
        """Put back the newest undone group. False when there is none."""
        if not self._undone:
            return False
        group = self._undone.pop()
        self._apply(group, forward=True)
        self._done.append(group)
        self._separate = True
        return True

    def _apply(self, edits: Iterable[_Edit], *, forward: bool) -> None:
        """Replay edits, or reverse them, without recording what that does."""
        self._replaying = True
        try:
            for edit in edits:
                putting_in = edit.inserted if forward else not edit.inserted
                if putting_in:
                    self.insert(self.index_of(edit.at), edit.text)
                else:
                    stop = self.index_of(edit.at + len(edit.text))
                    self.delete(self.index_of(edit.at), stop)
        finally:
            self._replaying = False

    # ----------------------------------------------------------------- marks

    def mark_set(self, name: str, index: Index | str) -> None:
        """Put a mark at an index, creating it if it is new."""
        gravity = self._marks.get(name, (0, "right"))[1]
        self._marks[name] = (self.offset_of(self.index(index)), gravity)

    def mark_unset(self, *names: str) -> None:
        """Remove marks. Unknown names are ignored, as in Tk."""
        for name in names:
            self._marks.pop(name, None)

    def mark_names(self) -> tuple[str, ...]:
        """Every mark, in the order they were first set."""
        return tuple(self._marks)

    def mark_index(self, name: str) -> Index | None:
        """Where a mark is, or None if there is no such mark."""
        entry = self._marks.get(name)
        return None if entry is None else self.index_of(entry[0])

    def mark_gravity(self, name: str, gravity: str | None = None) -> str:
        """Read or set which side of an insertion a mark ends up on.

        Raises:
            TextIndexError: If the mark does not exist, or the gravity is
                neither ``left`` nor ``right``.
        """
        if name not in self._marks:
            raise TextIndexError(f'there is no mark named "{name}"')
        offset, current = self._marks[name]
        if gravity is None:
            return current
        if gravity not in _GRAVITIES:
            raise TextIndexError(f'bad mark gravity "{gravity}"')
        self._marks[name] = (offset, gravity)
        return gravity

    def mark_next(self, index: Index | str) -> str | None:
        """The first mark at or after an index, or None."""
        at = self.offset_of(self.index(index))
        after = [
            (offset, name) for name, (offset, _) in self._marks.items() if offset > at
        ]
        return min(after)[1] if after else None

    def mark_previous(self, index: Index | str) -> str | None:
        """The last mark before an index, or None."""
        at = self.offset_of(self.index(index))
        before = [
            (offset, name) for name, (offset, _) in self._marks.items() if offset < at
        ]
        return max(before)[1] if before else None

    # ------------------------------------------------------------------ tags

    def tag_add(
        self, name: str, first: Index | str, last: Index | str | None = None
    ) -> None:
        """Tag a range, merging it with any the tag already covers."""
        start = self.offset_of(self.index(first))
        stop = start + 1 if last is None else self.offset_of(self.index(last))
        if stop < start:
            start, stop = stop, start
        if start == stop:
            self._tags.setdefault(name, [])
            return
        self._tags[name] = _merge([*self._tags.get(name, []), (start, stop)])

    def tag_remove(
        self, name: str, first: Index | str, last: Index | str | None = None
    ) -> None:
        """Untag a range, splitting any range it falls inside."""
        ranges = self._tags.get(name)
        if not ranges:
            return
        start = self.offset_of(self.index(first))
        stop = start + 1 if last is None else self.offset_of(self.index(last))
        if stop < start:
            start, stop = stop, start
        kept: list[tuple[int, int]] = []
        for existing_start, existing_stop in ranges:
            if existing_stop <= start or existing_start >= stop:
                kept.append((existing_start, existing_stop))
                continue
            if existing_start < start:
                kept.append((existing_start, start))
            if existing_stop > stop:
                kept.append((stop, existing_stop))
        self._tags[name] = _merge(kept)

    def tag_delete(self, *names: str) -> None:
        """Forget tags entirely, ranges and all."""
        for name in names:
            self._tags.pop(name, None)

    def tag_names(self, index: Index | str | None = None) -> tuple[str, ...]:
        """Every tag, or only those covering one index."""
        if index is None:
            return tuple(self._tags)
        at = self.offset_of(self.index(index))
        return tuple(
            name
            for name, ranges in self._tags.items()
            if any(start <= at < stop for start, stop in ranges)
        )

    def tag_ranges(self, name: str) -> list[Index]:
        """Every range of a tag, as a flat list of start and end indices.

        Flat because that is the shape Tk returns, and code that walks it in
        pairs is written against that shape.
        """
        return [
            self.index_of(offset)
            for start, stop in self._tags.get(name, [])
            for offset in (start, stop)
        ]

    def tag_nextrange(
        self, name: str, first: Index | str, last: Index | str | None = None
    ) -> tuple[Index, Index] | None:
        """The first range of a tag at or after an index."""
        at = self.offset_of(self.index(first))
        limit = len(self._text) if last is None else self.offset_of(self.index(last))
        for start, stop in self._tags.get(name, []):
            if stop > at and start < limit:
                return (self.index_of(max(start, at)), self.index_of(stop))
        return None

    def tag_prevrange(
        self, name: str, first: Index | str, last: Index | str | None = None
    ) -> tuple[Index, Index] | None:
        """The last range of a tag before an index."""
        at = self.offset_of(self.index(first))
        limit = 0 if last is None else self.offset_of(self.index(last))
        for start, stop in reversed(self._tags.get(name, [])):
            if start < at and stop > limit:
                return (self.index_of(start), self.index_of(min(stop, at)))
        return None


def _merge(ranges: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Sort ranges and join the ones that touch or overlap."""
    merged: list[tuple[int, int]] = []
    for start, stop in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], stop))
        else:
            merged.append((start, stop))
    return merged
