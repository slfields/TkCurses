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

"""A single line of editable text: cursor, selection, and what is visible.

Everything an Entry does to its contents happens here, away from curses and
from widget options, because it is the part with the awkward cases: deleting a
selection that runs backwards, a cursor left pointing past the end of shortened
text, scrolling so the cursor stays visible in a field narrower than the text.

Positions are indices *between* characters, as they are in Tk. A field holding
``abc`` has four of them, 0 to 3, and the cursor sits at one: index 0 is before
``a`` and index 3 is after ``c``. Thinking of them as characters rather than
gaps is what makes off-by-one errors in editing code.
"""

from __future__ import annotations

import contextlib
import unicodedata
from typing import TYPE_CHECKING

from tkcurses._core.cells import cells
from tkcurses._core.wipeable import SecretBuffer

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from tkcurses._core.words import Characters

__all__ = ["TextField", "is_word_char", "run_end", "run_start"]


# --------------------------------------------------------------- words
#
# What a double-click selects, in Entry and Text alike: the run of characters
# of one kind around the pointer, where the kinds are word characters and
# everything else - so a run of spaces or punctuation is a "word" too, and
# double-clicking the ", " in "hello, world" selects both. Tk gets this from
# Tcl's tcl_wordBreakBefore and tcl_wordBreakAfter, whose regular expressions
# are built on Tcl's \w; read from the running interpreter, Tk 9.0.2, and the
# selections measured character by character (TkCurses-svtr).


def is_word_char(char: str) -> bool:
    """True for a character Tcl's ``\\w`` matches.

    A letter, a decimal digit or connector punctuation (the underscore, and
    ``‿`` with it). Not Python's ``str.isalnum``, which also takes ``²`` and
    ``½`` - numbers, but not decimal digits - while missing ``‿``. Checked
    against Tcl 9.0.2's regexp for every code point there is, with no
    difference, under Python 3.14's Unicode 16 tables.
    """
    category = unicodedata.category(char)
    return category[0] == "L" or category in ("Nd", "Pc")


def run_start(text: Characters, index: int) -> int:
    """Where the run holding the character at ``index`` begins.

    Tk's ``tk::wordBreakBefore``, floored at 0 as its callers floor it. Past
    the end it answers for the last character, as Tcl's string range clamps.
    """
    if not text or index < 0:
        return 0
    index = min(index, len(text) - 1)
    kind = is_word_char(text[index])
    while index > 0 and is_word_char(text[index - 1]) == kind:
        index -= 1
    return index


def run_end(text: Characters, index: int) -> int:
    """Where the run holding the character at ``index`` ends, exclusive.

    Tk's ``tk::wordBreakAfter``, with "no break after it" read as the end of
    the text, as its callers read it.
    """
    index = max(index, 0)
    if index >= len(text):
        return len(text)
    kind = is_word_char(text[index])
    while index < len(text) and is_word_char(text[index]) == kind:
        index += 1
    return index


class TextField:
    """The contents of a one-line editor, and where the user is in it.

    Every operation keeps three things consistent: the cursor stays within the
    text, the selection stays within the text or is dropped, and neither is
    left describing a string that has changed underneath it.
    """

    def __init__(self, text: str = "") -> None:
        # A str, or for a hidden field a SecretBuffer: see hide().
        self._text: str | SecretBuffer = text
        #: Cells per character while hidden, when every one is drawn as the
        #: same mask character and the text itself is never measured.
        self._hidden_cells = 1
        self._cursor = len(text)
        # Tk's anchor is always somewhere: 0 until something sets it, and it
        # outlives the selection - selection_clear, a plain arrow and a delete
        # of the whole selection all leave it. TkCurses-bfy.
        self._anchor = 0
        self._selection: tuple[int, int] | None = None
        self._view = 0
        #: The cells a run of the text takes on screen. Indices count
        #: characters; columns count cells, and a CJK ideograph takes two
        #: and a combining mark none. An entry with ``show`` set replaces
        #: this, because what it draws is the mask, not the text.
        self.measure: Callable[[str], int] = cells

    # --------------------------------------------------------------- state

    @property
    def text(self) -> str:
        """The whole contents.

        For a hidden field this builds a ``str``, which cannot be wiped:
        what needs only the length or one character uses :attr:`length`
        and :meth:`char`.
        """
        if isinstance(self._text, SecretBuffer):
            return self._text.to_str()
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        """Replace the contents, keeping the cursor somewhere sensible.

        A cursor past the end of the new text would otherwise insert into a
        position that does not exist - which is what happens when a
        textvariable is set from elsewhere while the field is being edited.

        **The selection is clamped, not dropped.** Measured against Tk 9.0.2,
        for ``tk.Entry`` and ``ttk.Entry`` through a textvariable and for
        ``ttk.Spinbox.set``: a selection of 1-4 over ``"hello"`` reads 1-2 once
        the text is ``"ab"``, and one that started at or past the new end is
        gone. This dropped it outright until TkCurses-elb.

        **The anchor is not clamped**, which this said it was until
        TkCurses-bfy. Anchor at 6, the text set to ``"abc"``, six characters
        inserted at 3, then ``selection to 0``: Tk reads 0-9, which only an
        anchor still at 6 - moved to 12 by the insert - produces. Everything
        that reads the anchor clamps what it selects, so one past the end is
        harmless until an edit moves it back into range.
        """
        if isinstance(self._text, SecretBuffer):
            self._text.clear()
            self._text.insert(0, value)
        else:
            self._text = value
        self._cursor = min(self._cursor, len(value))
        if self._selection is not None:
            self._set_selection(*self._selection)
        self._clamp_view()

    @property
    def length(self) -> int:
        """How many characters there are."""
        return len(self._text)

    def char(self, index: int) -> str:
        """The one character at ``index``."""
        return self._text[index]

    @property
    def characters(self) -> Characters:
        """The contents, for reading one character at a time."""
        return self._text

    # ---------------------------------------------------------- hiding

    @property
    def hidden(self) -> bool:
        """True while the contents are held in wipeable memory."""
        return isinstance(self._text, SecretBuffer)

    def hide(self, cells_each: int = 1) -> None:
        """Hold the contents in wipeable memory, each drawn ``cells_each`` wide.

        Text already in the field was a ``str``, and that copy stays where
        it was: a field hidden from the start never makes one.
        """
        self._hidden_cells = cells_each
        if isinstance(self._text, str):
            self._text = SecretBuffer(self._text)

    def reveal(self) -> None:
        """Back to a ``str``, wiping the memory the contents were in."""
        if isinstance(self._text, SecretBuffer):
            buffer = self._text
            self._text = buffer.to_str()
            buffer.close()

    @contextlib.contextmanager
    def secret(self) -> Iterator[memoryview]:
        """The contents as UTF-8 in wipeable memory, wiped when done."""
        if isinstance(self._text, SecretBuffer):
            with self._text.utf8() as view:
                yield view
            return
        buffer = SecretBuffer(self._text)
        try:
            with buffer.utf8() as view:
                yield view
        finally:
            buffer.close()

    def close(self) -> None:
        """Wipe hidden contents and leave the field empty."""
        if isinstance(self._text, SecretBuffer):
            self._text.close()
            self._text = ""
        self._cursor = self._anchor = self._view = 0
        self._selection = None

    def _span(self, first: int, last: int) -> int:
        """The cells ``first`` up to ``last`` take on screen."""
        if isinstance(self._text, SecretBuffer):
            return self._hidden_cells * max(0, last - first)
        return self.measure(self._text[first:last])

    @property
    def cursor(self) -> int:
        """Where the next insertion goes."""
        return self._cursor

    @property
    def view(self) -> int:
        """Index of the first character shown, once the field has scrolled."""
        return self._view

    def clamp(self, index: int) -> int:
        """Hold an index within the text: below 0 is 0, past the end is the end.

        **A negative index is 0, as in Tk** - measured on 9.0.2, ``index(-1)``
        and ``index(-99)`` both answer 0 and ``delete(-2)`` removes the first
        character. This counted negatives from the end, a Python-slice habit,
        until TkCurses-11m, and every cursor motion goes through it: Left at
        the start of a field computed index -1 and jumped to the far end.
        """
        return max(0, min(len(self._text), index))

    # ------------------------------------------------------------- editing

    def insert(self, index: int, string: str) -> None:
        """Insert ``string`` at ``index``.

        The cursor follows text inserted before it, so typing at the start of
        a field does not leave the cursor behind what was just typed.

        **The selection, its anchor and the view move with the text**, as in
        Tk - measured on 9.0.2, a selection of 2-5 reads 4-7 after two
        characters go in at 0, and 2-7 after they go in at 3. Text inserted
        exactly at either end of the selection lands *outside* it. The view
        moves only for text inserted strictly before it, so the characters on
        screen stay on screen. Until TkCurses-61v any insert dropped the
        selection.
        """
        index = self.clamp(index)
        added = len(string)
        if isinstance(self._text, SecretBuffer):
            self._text.insert(index, string)
        else:
            self._text = self._text[:index] + string + self._text[index:]
        if self._cursor >= index:
            self._cursor += added
        if self._selection is not None:
            first, last = self._selection
            # The anchor is tested against the OLD first: an anchor sitting on
            # the insertion point moves only when the selection starts there.
            if self._anchor > index or first >= index:
                self._anchor += added
            self._selection = (
                first + added if first >= index else first,
                last + added if last > index else last,
            )
        elif self._anchor > index:
            self._anchor += added
        if self._view > index:
            self._view += added

    def delete(self, first: int, last: int | None = None) -> None:
        """Delete from ``first`` up to but not including ``last``.

        With no ``last`` this removes one character, matching Tk. A range
        given backwards is taken the right way round rather than ignored,
        because a selection dragged leftwards produces exactly that.

        Every position past the deleted run - the cursor, both ends of the
        selection, its anchor and the view - moves back by its length, and
        one inside the run moves to its start. A selection left empty is
        dropped. Measured against Tk 9.0.2; TkCurses-61v.
        """
        first = self.clamp(first)
        last = first + 1 if last is None else self.clamp(last)
        if last < first:
            first, last = last, first
        if first == last:
            return
        if isinstance(self._text, SecretBuffer):
            self._text.delete(first, last)
        else:
            self._text = self._text[:first] + self._text[last:]

        def moved(position: int) -> int:
            if position >= last:
                return position - (last - first)
            return min(position, first)

        self._cursor = moved(self._cursor)
        if self._selection is not None:
            start, stop = moved(self._selection[0]), moved(self._selection[1])
            self._selection = (start, stop) if start < stop else None
        self._anchor = moved(self._anchor)
        self._view = moved(self._view)

    def delete_selection(self) -> bool:
        """Delete the selected text. True if there was any."""
        if self._selection is None:
            return False
        first, last = self._selection
        self.delete(first, last)
        return True

    # -------------------------------------------------------------- cursor

    def move_to(self, index: int, *, extend: bool = False) -> None:
        """Put the cursor at ``index``, as an arrow key does.

        ``extend`` drags the selection with it, which is what a shifted arrow
        key does; without it the selection is dropped, which is what a plain
        one does - and the anchor is kept, as Tk keeps it.

        Extending is Tk's ``tk::EntryKeySelect``: with nothing selected the
        selection starts at the cursor, whatever anchor an edit left behind
        (measured: type over a selection, then Shift-Right selects one
        character); with a selection it is *adjusted* (:meth:`select_adjust`),
        so Shift-Right on 2-4 with the cursor at 5 reads 2-6.
        """
        index = self.clamp(index)
        if extend:
            if self._selection is None:
                self._anchor = self._cursor
                self.select_to(index)
            else:
                self.select_adjust(index)
        else:
            self._selection = None
        self._cursor = index

    def place_cursor(self, index: int) -> None:
        """Put the cursor at ``index`` and leave the selection alone.

        What Tk's ``icursor`` does - measured on ``tk.Entry`` and
        ``ttk.Entry``, a selection of 1-3 survives ``icursor(0)``. Distinct
        from :meth:`move_to`, which is a keystroke and drops it.
        """
        self._cursor = self.clamp(index)

    def move_by(self, distance: int, *, extend: bool = False) -> None:
        """Move the cursor along by ``distance`` characters."""
        self.move_to(self._cursor + distance, extend=extend)

    # ----------------------------------------------------------- selection

    @property
    def selection(self) -> tuple[int, int] | None:
        """The selected range as ``(first, last)``, or None."""
        return self._selection

    def select_range(self, first: int, last: int) -> None:
        """Select from ``first`` to ``last`` - Tk's ``selection range``.

        Measured on Tk 9.0.2: it does not move the anchor (range 2-6, then
        ``selection to 8`` reads 0-8), and a range given backwards, or empty,
        clears the selection rather than being turned round. TkCurses-bfy.
        """
        first, last = self.clamp(first), self.clamp(last)
        self._selection = (first, last) if first < last else None

    def select_from(self, index: int) -> None:
        """Set the anchor and nothing else - Tk's ``selection from``.

        The selection, if any, stays as it is, and so does the cursor
        (measured). It is the next :meth:`select_to` that uses it.
        """
        self._anchor = self.clamp(index)

    def select_to(self, index: int) -> None:
        """Select from the anchor to ``index`` - Tk's ``selection to``.

        The cursor does not move (measured: it stays put through every
        ``selection to``). Selecting onto the anchor itself leaves no
        selection here, where Tk reports an empty one as present - a
        ``sel.first`` equal to ``sel.last`` - which is not worth copying.
        """
        self._set_selection(self._anchor, index)

    def select_adjust(self, index: int) -> None:
        """Move the nearer end of the selection to ``index``.

        Tk's ``selection adjust``, which is not ``selection to``: the far end
        becomes the anchor, the choice made around the midpoint with Tk's own
        rounding. Measured on 2-6: ``adjust 3`` reads 3-6, ``adjust 5`` 2-5,
        ``adjust 8`` 2-8, ``adjust 1`` 1-6, and ``adjust 4`` - the exact
        middle - keeps whatever anchor there was. With nothing selected it is
        :meth:`select_to`.
        """
        index = self.clamp(index)
        if self._selection is not None:
            first, last = self._selection
            if index < (first + last) // 2:
                self._anchor = last
            elif index > (first + last + 1) // 2:
                self._anchor = first
        self.select_to(index)

    def select_clear(self) -> None:
        """Drop the selection, leaving the cursor and the anchor where they are."""
        self._selection = None

    def select_all(self) -> None:
        """Select everything and leave the cursor at the end."""
        self.select_range(0, len(self._text))
        self._cursor = len(self._text)

    def selected_text(self) -> str:
        """The selected text, empty if there is no selection."""
        if self._selection is None:
            return ""
        first, last = self._selection
        return self.text[first:last]

    def _set_selection(self, first: int, last: int) -> None:
        """Record a selection, normalised and dropped if it is empty."""
        first, last = self.clamp(first), self.clamp(last)
        if first > last:
            first, last = last, first
        self._selection = None if first == last else (first, last)

    # ---------------------------------------------------------------- view

    def visible(self, width: int) -> str:
        """The characters on screen in a field ``width`` cells wide.

        A wide character that would straddle the right edge is left out.
        """
        used = 0
        text = self.text
        for index in range(self._view, len(text)):
            used += self.measure(text[index])
            if used > width:
                return text[self._view : index]
        return text[self._view :]

    def scroll_into_view(self, width: int) -> None:
        """Move the window so the cursor is on screen.

        Tk's ``see insert``, which its entry *bindings* do after a keystroke
        or a click - and only they. A program calling ``insert``, ``icursor``
        or ``xview`` leaves the view where it is, so this is not called after
        every change (TkCurses-i8s). The window only moves as far as it must,
        so a cursor in the middle of a long line does not recentre the text
        every keystroke.
        """
        if width <= 0:
            self._view = 0
            return
        if self._cursor < self._view:
            self._view = self._cursor
        else:
            # The cursor's own cell must fit too: the character it is on,
            # two cells for a wide one, or one past the end.
            cursor = self._cursor
            own = self._span(cursor, cursor + 1) if cursor < len(self._text) else 1
            used = self._span(self._view, cursor) + max(1, own)
            while used > width and self._view < cursor:
                used -= self._span(self._view, self._view + 1)
                self._view += 1
            self._skip_marks(cursor)
        self._clamp_view()

    def set_view(self, index: int, width: int) -> None:
        """Scroll so ``index`` is the first character shown - Tk's ``xview``.

        The cursor is not touched: in Tk the view and the insertion cursor are
        independent, and scrolling an entry moves neither the cursor nor the
        selection (measured on 9.0.2; this moved the cursor until
        TkCurses-i8s). Held to ``len - width`` at most, as Tk holds it, so a
        scroll to the end shows the last ``width`` characters and no blank -
        the last ``width`` cells, with wide characters in the text.
        """
        self._view = max(0, min(index, self._last_view(width)))
        self._skip_marks(len(self._text))

    def fit_view(self, width: int) -> None:
        """Pull the window back if the text no longer reaches its right edge.

        Tk does this when it draws: delete the tail of a long entry and the
        view slides left until the text fills the field again. One cell more
        is allowed while the cursor is at the very end, which Tk does not
        need - its cursor is a line between characters, ours occupies a cell,
        and without it a cursor typed to the end of a full field would be
        drawn off the edge.
        """
        if self._cursor == len(self._text):
            width -= 1
        self._view = max(0, min(self._view, self._last_view(width)))

    def _last_view(self, width: int) -> int:
        """The furthest the view may scroll: the last ``width`` cells in view."""
        start = len(self._text)
        used = 0
        while start > 0:
            used += self._span(start - 1, start)
            if used > width:
                break
            start -= 1
        return start

    def _skip_marks(self, limit: int) -> None:
        """Keep the view off a combining mark, which has no cell of its own,
        moving it no further right than ``limit``."""
        while self._view < limit and self._span(self._view, self._view + 1) == 0:
            self._view += 1

    def _clamp_view(self) -> None:
        """Keep the window inside the text."""
        self._view = max(0, min(self._view, len(self._text)))

    def column_of(self, index: int) -> int:
        """Where an index appears on screen, relative to the visible window.

        In cells: negative for an index scrolled off to the left.
        """
        index = self.clamp(index)
        if index >= self._view:
            return self._span(self._view, index)
        return -self._span(index, self._view)

    def index_at(self, column: int) -> int:
        """The index a screen column corresponds to, for a mouse click.

        The character whose cells include ``column`` - either half of a wide
        one names it - or the end, past the last.
        """
        start = self._span(0, self._view)
        return self.index_at_cell(start + max(0, column))

    def index_at_cell(self, cell: int) -> int:
        """The character whose cells include ``cell``, counted from the start.

        Not from the view, as :meth:`index_at` counts: what a scrollbar's
        fraction of the whole text lands on.
        """
        used = 0
        for index in range(len(self._text)):
            used += self._span(index, index + 1)
            if cell < used:
                return index
        return len(self._text)

    def cell_of(self, index: int) -> int:
        """How many cells precede ``index``, counted from the start."""
        return self._span(0, self.clamp(index))
