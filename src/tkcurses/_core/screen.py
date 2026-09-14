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

"""The character grid and the curses screen that renders it.

Two things live here, deliberately separated:

:class:`ScreenBuffer` is the model — a grid of :class:`Cell` objects with dirty
tracking. It imports no curses, so the whole of it can be exercised without a
terminal, and widgets can be checked against what they *meant* to draw.

:class:`CursesScreen` is the device — it owns ``initscr``/``endwin`` and paints
the buffer's dirty regions onto the real terminal, routing every curses call
through :class:`~tkcurses._core.dispatcher.CursesDispatcher`.

Keeping them apart means a layout bug is diagnosable from the buffer alone,
without a pty in the loop.
"""

from __future__ import annotations

import contextlib
import curses
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses._core.geometry import Rect, Size

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

__all__ = ["Cell", "CursesScreen", "ScreenBuffer"]

#: What an empty cell holds.
BLANK = " "


def _attributes_only(fg: str, bg: str, attr: int) -> int:
    """Default attribute resolver: ignore colour, honour attributes."""
    del fg, bg
    return attr


@dataclass(slots=True)
class Cell:
    """One character position on the screen."""

    char: str = BLANK
    fg: str = "white"
    bg: str = "black"
    attr: int = curses.A_NORMAL
    dirty: bool = False

    def set(self, char: str, fg: str, bg: str, attr: int) -> bool:
        """Update this cell, returning True if anything actually changed.

        Returning the change lets the buffer mark only cells that differ, so
        redrawing an identical frame costs nothing.
        """
        if (self.char, self.fg, self.bg, self.attr) == (char, fg, bg, attr):
            return False
        self.char = char
        self.fg = fg
        self.bg = bg
        self.attr = attr
        self.dirty = True
        return True


class ScreenBuffer:
    """A grid of cells with per-row dirty tracking.

    Writes are clipped to the grid rather than raising: widgets routinely
    compute a position partly outside their parent, and clipping at the buffer
    keeps every caller from repeating the same bounds check.
    """

    def __init__(self, width: int, height: int) -> None:
        if width < 0 or height < 0:
            raise ValueError(f"negative buffer size: {width}x{height}")
        self._width = width
        self._height = height
        self._cells: list[list[Cell]] = [
            [Cell() for _ in range(width)] for _ in range(height)
        ]
        # Per row, the inclusive column span that changed, or None if clean.
        self._spans: list[tuple[int, int] | None] = [None] * height

    # ----------------------------------------------------------- geometry

    @property
    def width(self) -> int:
        """Columns in the grid."""
        return self._width

    @property
    def height(self) -> int:
        """Rows in the grid."""
        return self._height

    @property
    def size(self) -> Size:
        """Grid dimensions."""
        return Size(self._width, self._height)

    @property
    def bounds(self) -> Rect:
        """The grid as a rectangle at the origin."""
        return Rect(0, 0, self._width, self._height)

    def contains(self, row: int, col: int) -> bool:
        """True if ``(row, col)`` is inside the grid."""
        return 0 <= row < self._height and 0 <= col < self._width

    def cell(self, row: int, col: int) -> Cell:
        """Return the cell at ``(row, col)``.

        Raises:
            IndexError: If the position lies outside the grid. Reads are
                strict where writes are clipped: a read out of bounds is a
                bug in the caller, not a widget hanging off its parent.
        """
        if not self.contains(row, col):
            raise IndexError(f"({row}, {col}) outside {self._width}x{self._height}")
        return self._cells[row][col]

    def rows(self) -> Iterator[list[Cell]]:
        """Iterate over the rows of the grid."""
        yield from self._cells

    # ------------------------------------------------------------- writes

    def write(
        self,
        row: int,
        col: int,
        text: str,
        *,
        fg: str = "white",
        bg: str = "black",
        attr: int = curses.A_NORMAL,
    ) -> int:
        """Write ``text`` starting at ``(row, col)``. Returns cells written.

        Text running past the right edge is truncated, and a negative column
        starts the visible portion at the left edge, so a partly off-screen
        widget draws its visible part instead of failing.
        """
        if not (0 <= row < self._height) or not text:
            return 0
        start = max(0, col)
        skip = start - col
        if skip >= len(text):
            return 0
        available = self._width - start
        # Guard before slicing: a negative end index silently yields a prefix
        # rather than nothing, which would then be written out of bounds.
        if available <= 0:
            return 0
        visible = text[skip : skip + available]
        changed_lo: int | None = None
        changed_hi = start
        for offset, char in enumerate(visible):
            if self._cells[row][start + offset].set(char, fg, bg, attr):
                if changed_lo is None:
                    changed_lo = start + offset
                changed_hi = start + offset
        if changed_lo is not None:
            self._mark(row, changed_lo, changed_hi)
        return len(visible)

    def fill(
        self,
        rect: Rect,
        char: str = BLANK,
        *,
        fg: str = "white",
        bg: str = "black",
        attr: int = curses.A_NORMAL,
    ) -> None:
        """Fill ``rect`` with ``char``, clipped to the grid."""
        if not char:
            raise ValueError("fill character must not be empty")
        area = rect.intersection(self.bounds)
        if area.is_empty:
            return
        run = char[0] * area.width
        for row in range(area.top, area.bottom + 1):
            self.write(row, area.left, run, fg=fg, bg=bg, attr=attr)

    def clear(self) -> None:
        """Reset every cell to blank, marking the whole grid dirty."""
        self.fill(self.bounds)

    def resize(self, width: int, height: int) -> None:
        """Resize the grid, keeping the cells that still fit.

        Content is preserved so a terminal resize does not blank the display
        before the widgets have had a chance to lay out again.
        """
        if width < 0 or height < 0:
            raise ValueError(f"negative buffer size: {width}x{height}")
        if (width, height) == (self._width, self._height):
            return
        grid: list[list[Cell]] = []
        for row in range(height):
            existing = self._cells[row][:width] if row < self._height else []
            existing.extend(Cell() for _ in range(width - len(existing)))
            grid.append(existing)
        self._cells = grid
        self._width = width
        self._height = height
        # Everything must be repainted: curses discarded the old screen.
        self._spans = [None] * height
        for row in range(height):
            if width:
                self._mark(row, 0, width - 1)
                for cell in self._cells[row]:
                    cell.dirty = True

    # -------------------------------------------------------------- dirty

    def _mark(self, row: int, lo: int, hi: int) -> None:
        """Widen row ``row``'s dirty span to include columns ``lo``..``hi``."""
        span = self._spans[row]
        if span is None:
            self._spans[row] = (lo, hi)
        else:
            self._spans[row] = (min(span[0], lo), max(span[1], hi))

    @property
    def is_dirty(self) -> bool:
        """True if anything needs repainting."""
        return any(span is not None for span in self._spans)

    def get_dirty(self) -> list[Rect]:
        """Rectangles covering everything changed since the last clear.

        Rows that changed over the same columns are merged into one rectangle,
        so a full-screen repaint is a single region rather than one per row.
        """
        regions: list[Rect] = []
        start_row: int | None = None
        current: tuple[int, int] | None = None
        for row, span in enumerate([*self._spans, None]):
            if span == current:
                continue
            if current is not None and start_row is not None:
                lo, hi = current
                regions.append(Rect(lo, start_row, hi - lo + 1, row - start_row))
            current = span
            start_row = row if span is not None else None
        return regions

    def touch_all(self) -> None:
        """Mark every cell dirty, so the next refresh repaints the lot.

        Needed whenever something other than this buffer has written to the
        terminal, because the buffer's idea of what is on screen is then
        wrong everywhere and painting only what it thinks changed leaves the
        damage in place. A traceback written to the same terminal does
        exactly that.
        """
        for row in range(self._height):
            for cell in self._cells[row]:
                cell.dirty = True
            self._spans[row] = (0, self._width - 1)

    def clear_dirty(self) -> None:
        """Mark everything clean, after the dirty regions have been painted."""
        for row in range(self._height):
            if self._spans[row] is None:
                continue
            for cell in self._cells[row]:
                cell.dirty = False
            self._spans[row] = None

    # --------------------------------------------------------- inspection

    def text_at(self, row: int, col: int = 0, length: int | None = None) -> str:
        """Characters on ``row``, for assertions and debugging."""
        cells = self._cells[row][col : None if length is None else col + length]
        return "".join(cell.char for cell in cells)

    @property
    def lines(self) -> list[str]:
        """The buffer rendered as plain text, one string per row."""
        return ["".join(cell.char for cell in row) for row in self._cells]

    def __repr__(self) -> str:
        return f"<ScreenBuffer {self._width}x{self._height} dirty={self.is_dirty}>"


class CursesScreen:
    """Owns the curses screen and paints a :class:`ScreenBuffer` onto it.

    The terminal is a process-wide resource: if it is left in raw mode the
    user's shell is unusable afterwards, so teardown runs even when the
    application fails.
    """

    def __init__(self, *, dispatcher: CursesDispatcher | None = None) -> None:
        self._dispatcher = dispatcher or CursesDispatcher.get()
        self._stdscr: Any = None
        self._buffer: ScreenBuffer | None = None
        #: Maps a cell's colours and attributes onto a curses attribute.
        #: The colour manager replaces this once one exists; until then only
        #: attributes are honoured, which keeps this module free of any
        #: dependency on colour handling.
        self.attribute_resolver: Callable[[str, str, int], int] = _attributes_only

    # ---------------------------------------------------------- lifecycle

    @property
    def started(self) -> bool:
        """True between :meth:`start` and :meth:`stop`."""
        return self._stdscr is not None

    @property
    def stdscr(self) -> Any:
        """The curses window, once started."""
        if self._stdscr is None:
            raise RuntimeError("screen is not started")
        return self._stdscr

    @property
    def buffer(self) -> ScreenBuffer:
        """The cell grid backing this screen."""
        if self._buffer is None:
            raise RuntimeError("screen is not started")
        return self._buffer

    def start(self) -> ScreenBuffer:
        """Initialise curses and return the buffer sized to the terminal."""
        if self._stdscr is not None:
            raise RuntimeError("screen is already started")
        stdscr = curses.initscr()
        self._stdscr = stdscr
        try:
            curses.noecho()
            curses.cbreak()
            stdscr.keypad(True)
            with contextlib.suppress(curses.error):
                curses.curs_set(0)
        except BaseException:
            # Never leave the terminal in raw mode because setup failed.
            self.stop()
            raise
        height, width = stdscr.getmaxyx()
        self._buffer = ScreenBuffer(width, height)
        return self._buffer

    def stop(self) -> None:
        """Restore the terminal. Safe to call more than once."""
        if self._stdscr is None:
            return
        stdscr, self._stdscr = self._stdscr, None
        self._buffer = None
        with contextlib.suppress(curses.error):
            stdscr.keypad(False)
        with contextlib.suppress(curses.error):
            curses.curs_set(1)
        with contextlib.suppress(curses.error):
            curses.nocbreak()
        with contextlib.suppress(curses.error):
            curses.echo()
        with contextlib.suppress(curses.error):
            curses.endwin()

    def __enter__(self) -> ScreenBuffer:
        return self.start()

    def __exit__(self, *exc_info: object) -> None:
        self.stop()

    # ------------------------------------------------------------ painting

    @property
    def size(self) -> Size:
        """Current terminal size in cells."""
        height, width = self.stdscr.getmaxyx()
        return Size(width, height)

    def handle_resize(self) -> Size:
        """Apply a terminal resize and return the new size.

        ``curses.update_lines_cols()`` does not refresh the dimensions on its
        own: ``COLS``, ``LINES`` and ``getmaxyx()`` all stay stale until
        ``resize_term()`` has been given the size the pty actually reports.
        """
        buffer = self.buffer
        size = os.get_terminal_size()
        self._dispatcher.call(self._resize_term, size.lines, size.columns)
        buffer.resize(size.columns, size.lines)
        # Not only the cells the buffer thinks changed: the screen is being
        # cleared underneath us, so everything has to be written again.
        buffer.touch_all()
        return Size(size.columns, size.lines)

    def _resize_term(self, lines: int, columns: int) -> None:
        """Resize curses and discard its record of the physical screen.

        A terminal that shrinks scrolls its own content up to keep the cursor
        on screen, and ``resize_term()`` leaves curses' copy of the physical
        screen exactly as it was. The two then disagree everywhere: curses
        believes a cell already holds the character about to be written
        there, writes nothing, and the scrolled fragment of the old layout
        stays on the terminal. Nothing can read the terminal back to settle
        it, so the only answer is to stop believing the copy - ``clearok()``
        makes the next update clear the screen and write every cell.

        Growing gets the same treatment: the rows and columns that appear
        have never been painted, and a terminal that scrolled on the way down
        does not scroll back on the way up.
        """
        stdscr = self.stdscr
        curses.resize_term(lines, columns)
        stdscr.clearok(True)

    def refresh(self) -> int:
        """Paint every dirty region and return the number of cells written.

        Only changed cells reach curses, so an unchanged frame costs one
        no-op refresh rather than a full repaint.
        """
        buffer = self.buffer
        if not buffer.is_dirty:
            return 0
        painted = self._dispatcher.call(self._paint, buffer)
        buffer.clear_dirty()
        return painted

    def repaint(self) -> int:
        """Repaint every cell, whatever the buffer thinks has changed.

        For putting the screen back after something else has written to the
        terminal underneath it.
        """
        if not self.started:
            return 0
        self.buffer.touch_all()
        return self.refresh()

    def _paint(self, buffer: ScreenBuffer) -> int:
        """Write the dirty cells to curses. Runs on the dispatcher's thread."""
        stdscr = self._stdscr
        painted = 0
        last_row = buffer.height - 1
        last_col = buffer.width - 1
        for region in buffer.get_dirty():
            for row in range(region.top, region.bottom + 1):
                for col in range(region.left, region.right + 1):
                    cell = buffer.cell(row, col)
                    attr = self.attribute_resolver(cell.fg, cell.bg, cell.attr)
                    if row == last_row and col == last_col:
                        # Writing the last cell scrolls the screen and raises;
                        # insch puts the character there without advancing.
                        with contextlib.suppress(curses.error):
                            stdscr.insch(row, col, cell.char, attr)
                    else:
                        with contextlib.suppress(curses.error):
                            stdscr.addch(row, col, cell.char, attr)
                    painted += 1
        stdscr.noutrefresh()
        curses.doupdate()
        return painted
