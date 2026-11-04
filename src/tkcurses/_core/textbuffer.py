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

**Peers share one store.** Tk lets several Text widgets show one body of text
(``peer create``), each over its own range of whole lines (``-startline``,
``-endline``), with indices that count from ``1.0`` in each. So the string,
the marks, the tags and the undo stack live in a :class:`_Store`, and a
:class:`TextBuffer` is one widget's *view* of it: its window of lines,
renumbered. The view keeps Tk's three private things - the ``insert`` and
``current`` marks and the ``sel`` tag - in the store under names of its own, so
every edit moves them with everything else, and its window's two edges are
marks too, so the window grows and shrinks with edits as Tk's does.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tkcurses._core.errors import TclError

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["Index", "TextBuffer", "TextIndexError"]

#: What counts as part of a word for ``wordstart`` and ``wordend``. Tk's rule:
#: letters, digits and underscores are word characters and everything else is
#: a single-character word of its own.
_WORD = re.compile(r"\w")

#: ``+3 chars``, ``-2 lines``, and the compact ``+3c`` / ``-2l`` Tk also takes.
#: The pieces of a modifier list: a sign, or a run of anything else up to
#: the next space or sign. ``+1c`` is the two pieces ``+`` and ``1c``.
_MODIFIER_PIECE = re.compile(r"[+-]|[^\s+-]+")
#: Where the base index ends, once the whole string is not a mark's name.
_BASE_END = re.compile(r"[\s+-]")
#: A count's units, each with the letter its abbreviations start with.
#: ``indices`` counts what ``chars`` does here: a buffer holds no embedded
#: windows or images to tell them apart.
_UNITS = {"chars": "chars", "indices": "chars", "lines": "lines"}
#: The word modifiers. Tk takes any abbreviation of five letters or more, so
#: ``lines`` is ``linestart`` - and is never a unit here, where it follows no
#: count.
_EDGES = ("linestart", "lineend", "wordstart", "wordend")

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


class TextIndexError(TclError):
    """An index string that means nothing.

    A ``TclError``, as tkinter's is: a program catching that around an index
    used to crash on a ValueError instead. TkCurses-g7nf.
    """


class _NoTaggedCharacters(TextIndexError):
    """``tag.first`` for a tag that exists and covers nothing - the one bad
    index Tk names for what it is rather than quoting."""


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


#: What each view keeps to itself, as Tk's manual says of peers: "each peer
#: has its own insert and current mark positions" and "the sel tag exists
#: separately and independently in each peer". Everything else is shared.
_PRIVATE_MARKS = ("insert", "current")
_PRIVATE_TAGS = ("sel",)

#: Separates a private name from the view it belongs to, in the store. A NUL
#: cannot appear in a mark or tag name a program gives, so no collision.
_OWN = "\0"


class _Store:
    """The text, its marks and tags, and the undo stack: what peers share.

    Offsets here are into the whole string. Nothing outside this module
    touches it; a :class:`TextBuffer` translates to and from its own window.
    """

    def __init__(self, text: str) -> None:
        self.text = text if text.endswith("\n") else text + "\n"
        #: Bumped on every change to :attr:`text`, which is what each view's
        #: cached split is checked against.
        self.version = 0
        self.marks: dict[str, tuple[int, str]] = {}
        self.tags: dict[str, list[tuple[int, int]]] = {}
        #: Applied edits, newest last, in groups that undo together. A
        #: separator closes the open group; see :meth:`TextBuffer.edit_separator`.
        self.done: list[list[_Edit]] = []
        #: Groups taken back by an undo, newest last. Any new edit clears it -
        #: measured against Tk, where a fresh edit after an undo leaves
        #: "nothing to redo".
        self.undone: list[list[_Edit]] = []
        #: True while undoing or redoing, so the reversal is not itself
        #: recorded. Without this the stack never empties: each undo pushes
        #: its own inverse and the next one puts the edit straight back.
        self.replaying = False
        #: True when the next recorded edit should start a new group.
        self.separate = True
        #: Whether edits are recorded at all - the widgets' ``-undo``, shared:
        #: measured on Tk 9.0.2, whichever peer set it last decides.
        self.undo_enabled = False
        #: How many groups the stack keeps, oldest dropped first - ``-maxundo``.
        #: 0 or below keeps them all, as Tk's does.
        self.max_undo = 0
        #: Every view over this store, oldest first, so a change made through
        #: one can reach the others. A view leaves by :meth:`TextBuffer.detach`.
        self.views: list[TextBuffer] = []
        #: Whatever the widgets over this store share that is not text - tag
        #: styles and the modified flag. This module never reads it.
        self.shared: dict[str, Any] = {}

    # -------------------------------------------------------------- edits

    def insert(self, at: int, text: str) -> None:
        self.record(_Edit(at, text, inserted=True))
        self.text = self.text[:at] + text + self.text[at:]
        self.version += 1
        self.shift(at, len(text))

    def delete(self, start: int, stop: int) -> None:
        self.record(_Edit(start, self.text[start:stop], inserted=False))
        self.text = self.text[:start] + self.text[stop:]
        self.version += 1
        self.shift(stop, -(stop - start), floor=start)

    def shift(self, at: int, distance: int, *, floor: int | None = None) -> None:
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

        self.marks = {
            name: (moved(offset, gravity=gravity), gravity)
            for name, (offset, gravity) in self.marks.items()
        }
        for name, ranges in self.tags.items():
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
            self.tags[name] = _merge(pair for pair in shifted if pair[0] < pair[1])

    # ------------------------------------------------------------------ undo

    def record(self, edit: _Edit) -> None:
        """Note an edit that is about to be applied.

        Called from :meth:`insert` and :meth:`delete`, which is every path
        that changes the text - typing, backspace, deleting a selection and
        a program calling ``insert()`` all arrive at one of those two, from
        whichever peer. There is no other way in, so nothing can quietly
        escape the stack.
        """
        if not self.undo_enabled or self.replaying:
            return
        # Measured against Tk: an edit made after an undo drops what was
        # undone, leaving "nothing to redo". The alternative - keeping it -
        # would let redo reapply an edit to text it no longer fits.
        self.undone.clear()
        if self.separate or not self.done:
            self.done.append([])
            self.separate = False
            self.trim_undo()
        self.done[-1].append(edit)

    def trim_undo(self) -> None:
        if self.max_undo > 0 and len(self.done) > self.max_undo:
            del self.done[: len(self.done) - self.max_undo]

    def replay(self, edits: Iterable[_Edit], *, forward: bool) -> None:
        """Replay edits, or reverse them, without recording what that does."""
        self.replaying = True
        try:
            for edit in edits:
                putting_in = edit.inserted if forward else not edit.inserted
                if putting_in:
                    self.insert(edit.at, edit.text)
                else:
                    self.delete(edit.at, edit.at + len(edit.text))
        finally:
            self.replaying = False


class TextBuffer:
    """One widget's view of the text, and everything that points into it.

    Every operation leaves four things consistent: the final newline is still
    there, marks still name positions that exist, tag ranges are still sorted
    and non-overlapping, and nothing describes text that an edit has removed.

    Made on its own, a buffer has a store of its own and sees all of it. Made
    by :meth:`peer`, it shares the store with the buffer it came from.
    """

    _keys = itertools.count(1)

    def __init__(self, text: str = "", *, store: _Store | None = None) -> None:
        self._store = store if store is not None else _Store(text)
        self._store.views.append(self)
        self._key = f"{_OWN}{next(TextBuffer._keys)}"
        #: The window's edges, as marks of this view's, or None for no limit.
        self._edges: tuple[str | None, str | None] = (None, None)
        #: The split of :attr:`_text`, and what it was split from.
        self._lines: list[str] | None = None
        self._starts: list[int] | None = None
        self._cached: tuple[int, int, int] | None = None
        self._cached_text = ""
        #: Whatever this view belongs to - the widget - for the others to reach.
        self.owner: Any = None

    def peer(self) -> TextBuffer:
        """A new view of the same store, over all of it until told otherwise."""
        return TextBuffer(store=self._store)

    def peers(self) -> list[TextBuffer]:
        """The other views of this store, oldest first."""
        return [view for view in self._store.views if view is not self]

    def detach(self) -> None:
        """Leave the store, taking this view's own marks, tag and edges.

        The text stays for the others: measured on Tk 9.0.2, destroying the
        widget a peer was made from leaves the peer as it was.
        """
        store = self._store
        if self in store.views:
            store.views.remove(self)
        for table in (store.marks, store.tags):
            for key in [key for key in table if key.endswith(self._key)]:
                del table[key]
        self.owner = None

    @property
    def shared(self) -> dict[str, Any]:
        """What the widgets over this store share beyond the text."""
        return self._store.shared

    # ----------------------------------------------------------- the window

    def _edge_offset(self, which: int) -> int | None:
        name = self._edges[which]
        if name is None:
            return None
        entry = self._store.marks.get(name)
        return None if entry is None else entry[0]

    def _window(self) -> tuple[int, int]:
        """Where this view's text begins and ends in the store.

        Both edges are snapped back to the start of their line, so the
        window is always whole lines, as Tk's manual says it is: an edit
        that leaves an edge part way along a line - deleting from the middle
        of the line before it - cannot cut a line in two.
        """
        text = self._store.text
        lo = self._edge_offset(0)
        hi = self._edge_offset(1)
        lo = 0 if lo is None else text.rfind("\n", 0, lo) + 1
        hi = len(text) if hi is None or hi >= len(text) else text.rfind("\n", 0, hi) + 1
        return lo, max(lo, hi)

    def window_lines(self) -> tuple[int | None, int | None]:
        """The window as Tk's ``-startline`` and ``-endline``: the store's
        first line shown and the first line after, or None for no limit."""
        text = self._store.text
        lo, hi = self._window()
        start = None if self._edges[0] is None else text.count("\n", 0, lo) + 1
        end = None if self._edges[1] is None else text.count("\n", 0, hi) + 1
        return start, end

    def set_window(self, start: int | None, end: int | None) -> None:
        """Show the store's lines ``start`` up to but not including ``end``.

        None is no limit. A line past the store's last is its end.

        Both edges have left gravity, so text another peer inserts exactly at
        the start edge lands inside the window and text inserted exactly at
        the end edge lands after it. Measured on Tk 9.0.2 over lines 3 to 6
        of ten: a line inserted at 3.0 appears in the peer and moves its
        ``-endline`` to 7, and one inserted at 6.0 does not appear at all.
        """
        names = (f"{_OWN}start{self._key}", f"{_OWN}end{self._key}")
        edges: list[str | None] = []
        for name, line in zip(names, (start, end), strict=True):
            self._store.marks.pop(name, None)
            if line is None:
                edges.append(None)
                continue
            self._store.marks[name] = (self._store_offset_of_line(line), "left")
            edges.append(name)
        self._edges = (edges[0], edges[1])
        self._cached = None
        # Moved, not only hidden: measured on Tk 9.0.2, a peer's insert held
        # at 1.0 by a window below it is still at 1.0 when the window moves
        # back over where it was.
        for name in _PRIVATE_MARKS:
            key = self._mark_key(name)
            if key in self._store.marks:
                offset, gravity = self._store.marks[key]
                self._store.marks[key] = (self._held(name, offset), gravity)

    def _store_offset_of_line(self, line: int) -> int:
        text = self._store.text
        at = 0
        for _ in range(line - 1):
            found = text.find("\n", at)
            if found < 0:
                return len(text)
            at = found + 1
        return at

    def store_line_count(self) -> int:
        """How many lines the whole store holds, whatever this view shows."""
        return self._store.text.count("\n")

    @property
    def _text(self) -> str:
        """This view's text: whole lines, ending with a newline.

        A window with no lines in it - ``-startline`` equal to ``-endline``,
        or every line deleted through another peer - is the manual's "empty
        shell" and holds nothing at all, not even the final newline: measured
        on Tk 9.0.2, its ``end`` is ``1.0`` and ``get 1.0 end`` is empty. It
        takes no text either.
        """
        lo, hi = self._window()
        key = (self._store.version, lo, hi)
        if key != self._cached:
            self._cached = key
            self._cached_text = self._store.text[lo:hi]
            self._lines = None
            self._starts = None
        return self._cached_text

    @property
    def _shell(self) -> bool:
        lo, hi = self._window()
        return lo == hi

    def _local(self, offset: int) -> int | None:
        """A store offset as this view's, or None when it is outside."""
        lo, hi = self._window()
        if not lo <= offset <= hi:
            return None
        return offset - lo

    def _mark_offset(self, name: str) -> int | None:
        """Where a mark is in this view, or None if it is not here.

        A shared mark outside the window is not here - measured on Tk 9.0.2,
        naming one is ``bad text index``. This view's own ``insert`` and
        ``current`` always are; see :meth:`_held`.
        """
        key = self._mark_key(name)
        entry = self._store.marks.get(key)
        if entry is None or self._visible(key) != name:
            return None
        if name in _PRIVATE_MARKS:
            return self._held(name, entry[0]) - self._window()[0]
        return self._local(entry[0])

    def _held(self, name: str, offset: int) -> int:
        """A store offset pulled into the window, for this view's own marks.

        Measured on Tk 9.0.2: when the window moves above a peer's ``insert``
        it is held at the end of the window's last line, not after its
        newline, and when the window moves below it, at ``1.0``. That is
        ``insert``'s rule everywhere - ``mark set insert end`` puts it before
        the final newline - while ``current`` may sit at ``end``.
        """
        lo, hi = self._window()
        return max(lo, min(offset, hi - 1 if name == "insert" else hi))

    def _global(self, offset: int) -> int:
        return self._window()[0] + offset

    # ------------------------------------------------------ private names

    def _mark_key(self, name: str) -> str:
        return name + self._key if name in _PRIVATE_MARKS else name

    def _tag_key(self, name: str) -> str:
        return name + self._key if name in _PRIVATE_TAGS else name

    def _visible(self, key: str) -> str | None:
        """The name a store key goes by in this view, or None if it is
        another view's, or one of this view's edges."""
        if _OWN not in key:
            return key
        name, _, owner = key.partition(_OWN)
        return name if _OWN + owner == self._key else None

    def _local_ranges(self, name: str) -> list[tuple[int, int]]:
        """A tag's ranges cut to the window, in this view's offsets.

        Measured on Tk 9.0.2: ``tag ranges`` in a peer leaves out what lies
        outside its lines, and cuts a range that crosses its edge.
        """
        lo, hi = self._window()
        out = []
        for start, stop in self._store.tags.get(self._tag_key(name), []):
            start, stop = max(start, lo), min(stop, hi)
            if start < stop:
                out.append((start - lo, stop - lo))
        return out

    # --------------------------------------------------------------- shape

    @property
    def text(self) -> str:
        """Everything this view shows, final newline included."""
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
        text = self._text
        if self._lines is None:
            self._lines = text.split("\n")[:-1]
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
        try:
            if not text:
                raise TextIndexError(text)
            # The whole string is tried as a mark first, as Tk does: a mark
            # may be called my-mark, and then "my-mark +1c" is no index at
            # all, because the base stops at the first space or sign.
            local = self._mark_offset(text)
            if local is not None:
                return self.clamp(self.index_of(local))
            cut = _BASE_END.search(text)
            base = text if cut is None else text[: cut.start()]
            index = self._resolve_base(base)
            rest = "" if cut is None else text[cut.start() :]
            for modifier in self._modifiers(rest):
                index = self._apply_modifier(index, modifier)
        except _NoTaggedCharacters:
            raise
        except TextIndexError:
            # Measured on Tk 9.0.2: whatever part is wrong - the mark, a
            # modifier's count or its unit - the message quotes the index
            # whole, as it was given.
            raise TextIndexError(f'bad text index "{spec}"') from None
        return self.clamp(index)

    @staticmethod
    def _modifiers(text: str) -> list[tuple[str, int]]:
        """The modifiers after the base, in order, each as a unit and a count.

        Measured on Tk 9.0.2, which applies them left to right:
        ``3.0 lineend +1c`` is the start of line 4 and ``3.2 +1c lineend`` the
        end of line 3. Spaces are optional around a sign and between a count
        and its unit, and a unit may be cut short - ``+1c``, ``- 2 ch``, ``+ 1
        l``. A count may name ``any`` before its unit, which changes nothing
        here; ``display`` is refused, since the buffer knows nothing of how
        the lines wrap. Raises :class:`TextIndexError` for anything else.
        """
        pieces = _MODIFIER_PIECE.findall(text)
        found: list[tuple[str, int]] = []
        while pieces:
            piece = pieces.pop(0)
            if piece in "+-":
                if not pieces:
                    raise TextIndexError(text)
                digits = re.match(r"\d+", pieces[0])
                if digits is None:
                    raise TextIndexError(text)
                count = int(digits.group())
                unit = pieces.pop(0)[digits.end() :] or (
                    pieces.pop(0) if pieces else ""
                )
                if unit and "any".startswith(unit):
                    unit = pieces.pop(0) if pieces else ""
                name = next(
                    (name for name in _UNITS if unit and name.startswith(unit)), None
                )
                if name is None:
                    raise TextIndexError(text)
                found.append((_UNITS[name], count if piece == "+" else -count))
                continue
            if "any".startswith(piece) and pieces:
                piece = pieces.pop(0)
            edge = next(
                (edge for edge in _EDGES if len(piece) >= 5 and edge.startswith(piece)),
                None,
            )
            if edge is None:
                raise TextIndexError(text)
            found.append((edge, 0))
        return found

    def _resolve_base(self, base: str) -> Index:
        """The starting point, before any modifier is applied."""
        if base == "end":
            return self.end()
        local = self._mark_offset(base)
        if local is not None:
            return self.index_of(local)
        if "." in base:
            line, _, char = base.partition(".")
            if line.isdigit() and char == "end":
                number = int(line)
                return Index(number, self.line_length(number))
            if line.isdigit() and char.isdigit():
                return Index(int(line), int(char))
            name, _, which = base.rpartition(".")
            if which in ("first", "last") and self._tag_key(name) in self._store.tags:
                ranges = self._local_ranges(name)
                if not ranges:
                    raise _NoTaggedCharacters(
                        f'text doesn\'t contain any characters tagged with "{name}"'
                    )
                edge = ranges[0][0] if which == "first" else ranges[-1][1]
                return self.index_of(edge)
        raise TextIndexError(f'bad text index "{base}"')

    def _apply_modifier(self, index: Index, modifier: tuple[str, int]) -> Index:
        """Move an index by one modifier."""
        kind, count = modifier
        if kind == "linestart":
            return Index(index.line, 0)
        if kind == "lineend":
            return Index(index.line, self.line_length(index.line))
        if kind in ("wordstart", "wordend"):
            return self._word_edge(index, start=kind == "wordstart")
        if kind == "chars":
            return self.index_of(self.offset_of(index) + count)
        line = index.line + count
        return Index(line, min(index.char, self.line_length(line)))

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
        raise TextIndexError(
            f'bad comparison operator "{op}": must be <, <=, ==, >=, >, or !='
        )

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
        nothing can go after it. An empty shell takes nothing.
        """
        if not text or self._shell:
            return self.index(index)
        at = min(self.offset_of(self.index(index)), len(self._text) - 1)
        self._store.insert(self._global(at), text)
        return self.index_of(at + len(text))

    def delete(self, first: Index | str, last: Index | str | None = None) -> None:
        """Delete from ``first`` up to but not including ``last``.

        With no ``last`` this removes one character, matching Tk. A range
        given backwards is taken the right way round, because a selection
        dragged upwards produces exactly that. The final newline is never
        removed, whatever range is asked for - in a peer, the newline ending
        its last line, which is why one cannot empty itself: measured on Tk
        9.0.2, deleting all of a peer's lines leaves it one empty line.
        """
        start = self.offset_of(self.index(first))
        stop = start + 1 if last is None else self.offset_of(self.index(last))
        if stop < start:
            start, stop = stop, start
        # An empty shell has no newline to keep, and this makes both -1.
        stop = min(stop, len(self._text) - 1)
        start = min(start, stop)
        if start == stop:
            return
        self._store.delete(self._global(start), self._global(stop))

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

    @property
    def undo_enabled(self) -> bool:
        """Whether edits are recorded - shared by every peer."""
        return self._store.undo_enabled

    @undo_enabled.setter
    def undo_enabled(self, value: bool) -> None:
        self._store.undo_enabled = value

    @property
    def max_undo(self) -> int:
        """How many groups the stack keeps - shared by every peer."""
        return self._store.max_undo

    @max_undo.setter
    def max_undo(self, value: int) -> None:
        self._store.max_undo = value

    def trim_undo(self) -> None:
        """Drop the oldest groups past :attr:`max_undo`.

        Measured on Tk 9.0.2: with ``-maxundo 2``, four separated edits undo
        two at a time and no more; and lowering it to 2 over five groups
        leaves two to undo. A group counts once however many edits it holds.
        """
        self._store.trim_undo()

    def edit_separator(self) -> None:
        """End the current group, so the next edit begins a new one."""
        self._store.separate = True

    def edit_reset(self) -> None:
        """Forget everything on both stacks."""
        self._store.done.clear()
        self._store.undone.clear()
        self._store.separate = True

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
        return len(self._store.done)

    @property
    def can_undo(self) -> bool:
        """Whether there is a group to take back."""
        return bool(self._store.done)

    @property
    def can_redo(self) -> bool:
        """Whether there is a group to put back."""
        return bool(self._store.undone)

    def edit_undo(self) -> bool:
        """Take back the newest group. False when there is nothing to take.

        The group is reversed newest edit first, which is the only order
        that works: the offsets in each record describe the text as it was
        when that edit was applied, so an earlier one cannot be undone until
        the later ones are gone. It is the store's stack, so it takes back
        an edit made through any peer, outside this view's lines or not.

        **Text comes back; tags do not.** A tag whose whole range was
        deleted is gone for good, because only the characters are recorded.
        That is not a shortcut - Tk does exactly the same, measured: tag a
        range, delete across it, undo, and ``tag_ranges`` is still empty
        while the text is back. Marks do return, because they are moved by
        the store's shift rather than stored.
        """
        store = self._store
        if not store.done:
            return False
        group = store.done.pop()
        store.replay(reversed(group), forward=False)
        store.undone.append(group)
        store.separate = True
        return True

    def edit_redo(self) -> bool:
        """Put back the newest undone group. False when there is none."""
        store = self._store
        if not store.undone:
            return False
        group = store.undone.pop()
        store.replay(group, forward=True)
        store.done.append(group)
        store.separate = True
        return True

    # ----------------------------------------------------------------- marks

    def mark_set(self, name: str, index: Index | str) -> None:
        """Put a mark at an index, creating it if it is new."""
        key = self._mark_key(name)
        gravity = self._store.marks.get(key, (0, "right"))[1]
        offset = self._global(self.offset_of(self.index(index)))
        self._store.marks[key] = (offset, gravity)

    def mark_unset(self, *names: str) -> None:
        """Remove marks. Unknown names are ignored, as in Tk."""
        for name in names:
            self._store.marks.pop(self._mark_key(name), None)

    def mark_names(self) -> tuple[str, ...]:
        """Every mark, in the order they were first set.

        Measured on Tk 9.0.2: a peer lists every shared mark, those outside
        its lines too, though naming one of those as an index is an error.
        Its own marks come first, as they do in the widget it was made from.
        """
        names = [self._visible(key) for key in self._store.marks]
        own = [name for name in _PRIVATE_MARKS if name in names]
        rest = [name for name in names if name is not None and name not in own]
        return (*own, *rest)

    def mark_index(self, name: str) -> Index | None:
        """Where a mark is, or None if there is no such mark in this view."""
        local = self._mark_offset(name)
        return None if local is None else self.index_of(local)

    def mark_gravity(self, name: str, gravity: str | None = None) -> str:
        """Read or set which side of an insertion a mark ends up on.

        Raises:
            TextIndexError: If the mark does not exist, or the gravity is
                neither ``left`` nor ``right``.
        """
        key = self._mark_key(name)
        if key not in self._store.marks:
            raise TextIndexError(f'there is no mark named "{name}"')
        offset, current = self._store.marks[key]
        if gravity is None:
            return current
        if gravity not in _GRAVITIES:
            raise TextIndexError(f'bad mark gravity "{gravity}": must be left or right')
        self._store.marks[key] = (offset, gravity)
        return gravity

    def _local_marks(self) -> list[tuple[int, str]]:
        """This view's marks inside its window, at its own offsets."""
        out = []
        for key, (offset, _) in self._store.marks.items():
            name = self._visible(key)
            local = self._local(offset)
            if name is not None and local is not None:
                out.append((local, name))
        return out

    def mark_next(self, index: Index | str) -> str | None:
        """The first mark at or after an index, or None."""
        at = self.offset_of(self.index(index))
        after = [(offset, name) for offset, name in self._local_marks() if offset > at]
        return min(after)[1] if after else None

    def mark_previous(self, index: Index | str) -> str | None:
        """The last mark before an index, or None."""
        at = self.offset_of(self.index(index))
        before = [(offset, name) for offset, name in self._local_marks() if offset < at]
        return max(before)[1] if before else None

    # ------------------------------------------------------------------ tags

    def tag_add(
        self, name: str, first: Index | str, last: Index | str | None = None
    ) -> None:
        """Tag a range, merging it with any the tag already covers."""
        key = self._tag_key(name)
        start = self.offset_of(self.index(first))
        stop = start + 1 if last is None else self.offset_of(self.index(last))
        if stop < start:
            start, stop = stop, start
        if start == stop:
            self._store.tags.setdefault(key, [])
            return
        span = (self._global(start), self._global(stop))
        self._store.tags[key] = _merge([*self._store.tags.get(key, []), span])

    def tag_remove(
        self, name: str, first: Index | str, last: Index | str | None = None
    ) -> None:
        """Untag a range, splitting any range it falls inside."""
        key = self._tag_key(name)
        ranges = self._store.tags.get(key)
        if not ranges:
            return
        start = self.offset_of(self.index(first))
        stop = start + 1 if last is None else self.offset_of(self.index(last))
        if stop < start:
            start, stop = stop, start
        start, stop = self._global(start), self._global(stop)
        kept: list[tuple[int, int]] = []
        for existing_start, existing_stop in ranges:
            if existing_stop <= start or existing_start >= stop:
                kept.append((existing_start, existing_stop))
                continue
            if existing_start < start:
                kept.append((existing_start, start))
            if existing_stop > stop:
                kept.append((stop, existing_stop))
        self._store.tags[key] = _merge(kept)

    def tag_delete(self, *names: str) -> None:
        """Forget tags entirely, ranges and all."""
        for name in names:
            self._store.tags.pop(self._tag_key(name), None)

    def tag_names(self, index: Index | str | None = None) -> tuple[str, ...]:
        """Every tag, or only those covering one index."""
        names = [
            name
            for name in (self._visible(key) for key in self._store.tags)
            if name is not None
        ]
        if index is None:
            return tuple(names)
        at = self.offset_of(self.index(index))
        return tuple(
            name
            for name in names
            if any(start <= at < stop for start, stop in self._local_ranges(name))
        )

    def tag_ranges(self, name: str) -> list[Index]:
        """Every range of a tag, as a flat list of start and end indices.

        Flat because that is the shape Tk returns, and code that walks it in
        pairs is written against that shape.
        """
        return [
            self.index_of(offset)
            for start, stop in self._local_ranges(name)
            for offset in (start, stop)
        ]

    def tag_nextrange(
        self, name: str, first: Index | str, last: Index | str | None = None
    ) -> tuple[Index, Index] | None:
        """The first range of a tag at or after an index."""
        at = self.offset_of(self.index(first))
        limit = len(self._text) if last is None else self.offset_of(self.index(last))
        for start, stop in self._local_ranges(name):
            if stop > at and start < limit:
                return (self.index_of(max(start, at)), self.index_of(stop))
        return None

    def tag_prevrange(
        self, name: str, first: Index | str, last: Index | str | None = None
    ) -> tuple[Index, Index] | None:
        """The last range of a tag before an index."""
        at = self.offset_of(self.index(first))
        limit = 0 if last is None else self.offset_of(self.index(last))
        for start, stop in reversed(self._local_ranges(name)):
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
