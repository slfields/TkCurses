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

__all__ = ["TextField"]


class TextField:
    """The contents of a one-line editor, and where the user is in it.

    Every operation keeps three things consistent: the cursor stays within the
    text, the selection stays within the text or is dropped, and neither is
    left describing a string that has changed underneath it.
    """

    def __init__(self, text: str = "") -> None:
        self._text = text
        self._cursor = len(text)
        self._anchor: int | None = None
        self._selection: tuple[int, int] | None = None
        self._view = 0

    # --------------------------------------------------------------- state

    @property
    def text(self) -> str:
        """The whole contents."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        """Replace the contents, keeping the cursor somewhere sensible.

        A cursor past the end of the new text would otherwise insert into a
        position that does not exist - which is what happens when a
        textvariable is set from elsewhere while the field is being edited.

        **The selection is clamped, not dropped**, and so is its anchor.
        Measured against Tk 9.0.2, for ``tk.Entry`` and ``ttk.Entry`` through
        a textvariable and for ``ttk.Spinbox.set``: a selection of 1-4 over
        ``"hello"`` reads 1-2 once the text is ``"ab"``, and one that started
        at or past the new end is gone. This dropped it outright until
        TkCurses-elb.
        """
        self._text = value
        self._cursor = min(self._cursor, len(value))
        if self._selection is not None:
            self._set_selection(*self._selection)
        self._anchor = (
            None if self._selection is None else self.clamp(self._anchor or 0)
        )
        self._clamp_view()

    @property
    def cursor(self) -> int:
        """Where the next insertion goes."""
        return self._cursor

    @property
    def view(self) -> int:
        """Index of the first character shown, once the field has scrolled."""
        return self._view

    def clamp(self, index: int) -> int:
        """Hold an index within the text, counting from the end if negative."""
        if index < 0:
            index = len(self._text) + index
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
        self._text = self._text[:index] + string + self._text[index:]
        if self._cursor >= index:
            self._cursor += added
        if self._selection is not None:
            first, last = self._selection
            # The anchor is tested against the OLD first: an anchor sitting on
            # the insertion point moves only when the selection starts there.
            if self._anchor is not None and (self._anchor > index or first >= index):
                self._anchor += added
            self._selection = (
                first + added if first >= index else first,
                last + added if last > index else last,
            )
        elif self._anchor is not None and self._anchor > index:
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
        self._text = self._text[:first] + self._text[last:]

        def moved(position: int) -> int:
            if position >= last:
                return position - (last - first)
            return min(position, first)

        self._cursor = moved(self._cursor)
        if self._selection is not None:
            start, stop = moved(self._selection[0]), moved(self._selection[1])
            self._selection = (start, stop) if start < stop else None
        if self._anchor is not None:
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
        """Put the cursor at ``index``.

        ``extend`` drags the selection with it, which is what a shifted arrow
        key does; without it the selection is dropped, which is what a plain
        one does.
        """
        index = self.clamp(index)
        if extend:
            # With nothing selected the drag starts here, whatever anchor an
            # edit left behind - what Tk's Shift-arrow bindings do (measured:
            # type over a selection, then Shift-Right selects one character).
            if self._anchor is None or self._selection is None:
                self._anchor = self._cursor
            self._cursor = index
            self._set_selection(self._anchor, index)
        else:
            self._cursor = index
            self._selection = None
            self._anchor = None

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
        """Select from ``first`` to ``last``."""
        self._anchor = self.clamp(first)
        self._set_selection(first, last)

    def select_clear(self) -> None:
        """Drop the selection, leaving the cursor where it is."""
        self._selection = None
        self._anchor = None

    def select_all(self) -> None:
        """Select everything and leave the cursor at the end."""
        self.select_range(0, len(self._text))
        self._cursor = len(self._text)

    def selected_text(self) -> str:
        """The selected text, empty if there is no selection."""
        if self._selection is None:
            return ""
        first, last = self._selection
        return self._text[first:last]

    def _set_selection(self, first: int, last: int) -> None:
        """Record a selection, normalised and dropped if it is empty."""
        first, last = self.clamp(first), self.clamp(last)
        if first > last:
            first, last = last, first
        self._selection = None if first == last else (first, last)

    # ---------------------------------------------------------------- view

    def visible(self, width: int) -> str:
        """The characters on screen in a field ``width`` cells wide."""
        if width <= 0:
            return ""
        return self._text[self._view : self._view + width]

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
        elif self._cursor > self._view + width - 1:
            self._view = self._cursor - width + 1
        self._clamp_view()

    def set_view(self, index: int, width: int) -> None:
        """Scroll so ``index`` is the first character shown - Tk's ``xview``.

        The cursor is not touched: in Tk the view and the insertion cursor are
        independent, and scrolling an entry moves neither the cursor nor the
        selection (measured on 9.0.2; this moved the cursor until
        TkCurses-i8s). Held to ``len - width`` at most, as Tk holds it, so a
        scroll to the end shows the last ``width`` characters and no blank.
        """
        self._view = max(0, min(index, len(self._text) - max(0, width)))

    def fit_view(self, width: int) -> None:
        """Pull the window back if the text no longer reaches its right edge.

        Tk does this when it draws: delete the tail of a long entry and the
        view slides left until the text fills the field again. One cell more
        is allowed while the cursor is at the very end, which Tk does not
        need - its cursor is a line between characters, ours occupies a cell,
        and without it a cursor typed to the end of a full field would be
        drawn off the edge.
        """
        limit = len(self._text) - max(0, width)
        if self._cursor == len(self._text):
            limit += 1
        self._view = max(0, min(self._view, limit))

    def _clamp_view(self) -> None:
        """Keep the window inside the text."""
        self._view = max(0, min(self._view, len(self._text)))

    def column_of(self, index: int) -> int:
        """Where an index appears on screen, relative to the visible window."""
        return self.clamp(index) - self._view

    def index_at(self, column: int) -> int:
        """The index a screen column corresponds to, for a mouse click."""
        return self.clamp(self._view + max(0, column))
