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

import atexit
import codecs
import contextlib
import curses
import os
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tkcurses._core.cells import char_cells
from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses._core.geometry import Rect, Size

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

__all__ = ["Cell", "CursesScreen", "ScreenBuffer", "TerminalCursor"]

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


def _cell_entries(text: str, skip: int, available: int) -> list[str]:
    """``text`` as it fills cells: one entry a cell, from ``skip`` cells in.

    A wide character's second cell is ``""``; a combining mark is added to
    the character it follows; a wide character cut by the left or the right
    edge is a blank, its visible half.
    """
    out: list[str] = []
    used = 0  # cells of text passed, skipped ones included
    lead: int | None = None  # where the last character shown is
    for character in text:
        size = char_cells(character)
        if size == 0:
            if lead is not None:
                out[lead] += character
            continue
        if len(out) >= available:
            break
        if used + size <= skip:
            used += size
            lead = None
            continue
        if used < skip or len(out) + size > available:
            out.append(BLANK)  # straddles an edge: the half that shows
            used += size
            lead = None
            continue
        lead = len(out)
        out.append(character)
        out.extend([""] * (size - 1))
        used += size
    return out


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

        Laid out in cells, as a terminal does: a wide character fills its
        cell and the next, which holds ``""``; a combining mark joins the
        character before it; and a wide character cut by either edge leaves
        a blank. Writing over the first half of a wide character blanks its
        second, as curses does, rather than leave half a character showing.
        """
        if not (0 <= row < self._height) or not text:
            return 0
        start = max(0, col)
        skip = start - col
        available = self._width - start
        # Guard before slicing: a negative end index silently yields a prefix
        # rather than nothing, which would then be written out of bounds.
        if available <= 0:
            return 0
        if text.isascii():
            if skip >= len(text):
                return 0
            entries: list[str] = list(text[skip : skip + available])
        else:
            entries = _cell_entries(text, skip, available)
            if not entries:
                return 0
        line = self._cells[row]
        end = start + len(entries)
        changed_lo: int | None = None
        changed_hi = start

        def put(column: int, char: str) -> None:
            nonlocal changed_lo, changed_hi
            if line[column].set(char, fg, bg, attr):
                changed_lo = column if changed_lo is None else min(changed_lo, column)
                changed_hi = max(changed_hi, column)

        # Only the second half is blanked. Measured against ncurses through
        # the test harness: "z" written on the second cell of an ideograph
        # leaves the ideograph in the first, and written on its first cell
        # blanks the second.
        for offset, char in enumerate(entries):
            put(start + offset, char)
        if end < self._width and line[end].char == "":
            put(end, BLANK)
        if changed_lo is not None:
            self._mark(row, changed_lo, changed_hi)
        return len(entries)

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


@dataclass(frozen=True)
class CursorStyle:
    """What a widget asks of the terminal's cursor, beyond where it goes.

    Built from Tk's insertion-cursor options - see
    ``BaseWidget._cursor_style`` for how - and sent to the terminal as the two
    requests terminals widely understand. A terminal that does not understand
    one ignores it, and the cursor keeps the shape it had.

    Attributes:
        shape: The DECSCUSR shape, ``ESC [ n SP q``: 1 a blinking block,
            2 a steady block, 5 a blinking bar, 6 a steady bar. None leaves
            the terminal's own shape alone.
        colour: ``#rrggbb`` for OSC 12, or None to leave the terminal's.
    """

    shape: int | None = None
    colour: str | None = None


#: Asks nothing of the terminal: its own cursor, as the person set it up.
TERMINALS_OWN = CursorStyle()


class TerminalCursor:
    """The terminal's own cursor, put where typing goes, or hidden.

    Entry and Text used to paint their insertion point as a reversed cell -
    the same attribute as a selection, and never blinking - so a person could
    not tell the cursor from the selected text beside it (found running UAT
    43, TkCurses-lw2). Tk draws a distinct, blinking insertion bar. The
    terminal already has one: this shows it at the focused widget's insert
    point and hides it everywhere else, so it blinks and takes whatever
    shape the person's terminal is set to. The author's choice, over painting
    a better imitation.

    ``place`` runs right before every ``doupdate``: curses puts the cursor
    wherever its virtual cursor is at that moment, so it is set last. The
    cursor is shown and hidden only on a change, not every frame.

    **A program may ask for a shape and a colour** (TkCurses-gm66.2), through
    Tk's ``-blockcursor``, ``-insertwidth``, ``-insertofftime`` and
    ``-insertbackground``. ``style`` answers what the focused widget asks, and
    the request is sent only when it changes. The person's own cursor comes
    back when the focus moves to a widget that asks nothing, and at exit -
    :meth:`restore`, which :meth:`CursesScreen.stop` runs - because a cursor
    shape outlives the program that set it.

    Args:
        source: Answers the screen cell, ``(row, column)``, the cursor belongs
            in, or None when nothing focused takes typing.
        style: Answers what the focused widget asks of the cursor's look.
        write: Sends bytes straight to the terminal. Standard output, which
            is where curses draws, unless a test says otherwise.
    """

    def __init__(
        self,
        source: Callable[[], tuple[int, int] | None],
        style: Callable[[], CursorStyle] | None = None,
        write: Callable[[bytes], None] | None = None,
    ) -> None:
        self._source = source
        self._style = style
        self._write = write or _write_to_terminal
        self._shown: bool | None = None
        #: What the terminal has been asked for, so a frame sends nothing new.
        self._applied = TERMINALS_OWN

    def place(self) -> None:
        """Move the cursor to where it belongs, or hide it. Curses thread only."""
        try:
            cell = self._source()
        except Exception:
            # A widget half torn down mid-frame is not worth the frame.
            cell = None
        if cell is None:
            if self._shown is not False:
                with contextlib.suppress(curses.error):
                    curses.curs_set(0)
                self._shown = False
            return
        self._ask(self._wanted())
        with contextlib.suppress(curses.error):
            curses.setsyx(*cell)
        if self._shown is not True:
            with contextlib.suppress(curses.error):
                curses.curs_set(1)
            self._shown = True

    def restore(self) -> None:
        """Give the person back the cursor they had, if anything was asked."""
        self._ask(TERMINALS_OWN)

    def _wanted(self) -> CursorStyle:
        if self._style is None:
            return TERMINALS_OWN
        try:
            return self._style()
        except Exception:
            # As for the cell: never lose a frame to a widget mid-teardown.
            return TERMINALS_OWN

    def _ask(self, style: CursorStyle) -> None:
        """Send what differs from what the terminal was last asked for.

        ``ESC [ 0 SP q`` and OSC 112 are the resets: the shape and the colour
        the person's terminal is configured with, not a guess at them.
        """
        applied, self._applied = self._applied, style
        sequences = b""
        if style.shape != applied.shape:
            sequences += b"\x1b[%d q" % (style.shape or 0)
        if style.colour != applied.colour:
            if style.colour is None:
                sequences += b"\x1b]112\x07"
            else:
                sequences += b"\x1b]12;" + style.colour.encode("ascii") + b"\x07"
        if sequences:
            self._write(sequences)


def _write_to_terminal(data: bytes) -> None:
    """Write past curses to where it draws. Losing a cursor shape loses nothing."""
    with contextlib.suppress(OSError, ValueError):
        os.write(sys.stdout.fileno(), data)


class CursesScreen:
    """Owns the curses screen and paints a :class:`ScreenBuffer` onto it.

    The terminal is a process-wide resource: if it is left in raw mode the
    user's shell is unusable afterwards, so teardown runs even when the
    application fails.
    """

    def __init__(self, *, dispatcher: CursesDispatcher | None = None) -> None:
        self._dispatcher = dispatcher or CursesDispatcher.get()
        #: Placed before every flush when set; see :class:`TerminalCursor`.
        self.cursor: TerminalCursor | None = None
        self._stdscr: Any = None
        self._buffer: ScreenBuffer | None = None
        #: Maps a cell's colours and attributes onto a curses attribute.
        #: The colour manager replaces this once one exists; until then only
        #: attributes are honoured, which keeps this module free of any
        #: dependency on colour handling.
        self.attribute_resolver: Callable[[str, str, int], int] = _attributes_only
        #: A :meth:`str.translate` table applied to every character on its
        #: way to the terminal, or None. ``[display] unicode_borders`` off
        #: sets it to :data:`~tkcurses._core.attributes.ASCII_GLYPHS`.
        self.glyphs: dict[int, str] | None = None

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
        """Initialise curses and return the buffer sized to the terminal.

        **Registers an exit hook that gives the terminal back.** From here
        on the terminal is in cbreak mode, on the alternate screen, with the
        cursor hidden - and a process that leaves without undoing those
        hands the user a shell that needs ``reset``.

        It is not enough to undo them in ``destroy()``, because a program is
        not obliged to call it. tkinter's own documented way to leave a main
        loop is ``quit()``, after which a great many programs simply fall off
        the end of the file: measured, that left every one of those modes
        set. An interrupt did too. The hook catches all of them, and
        :meth:`stop` unregisters it so an orderly shutdown is not undone
        twice.
        """
        if self._stdscr is not None:
            raise RuntimeError("screen is already started")
        stdscr = curses.initscr()
        self._stdscr = stdscr
        atexit.register(self.stop)
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

    @property
    def addressable(self) -> bool:
        """True if the terminal can move its cursor to a given cell.

        Everything here is drawn by moving the cursor to a cell and writing
        there, so a terminal without ``cup`` - ``TERM=dumb`` - can start
        curses and run a main loop while showing nothing at all. Asked of
        terminfo once curses has read it.
        """
        try:
            return curses.tigetstr("cup") is not None
        except curses.error:
            return False

    @property
    def utf8(self) -> bool:
        """True if curses encodes text as UTF-8, which is the locale's choice.

        Anything else cannot carry an accented letter or a box-drawing
        line: measured under ``LC_ALL=C``, ``café`` is drawn as ``caf�`` and
        an Entry's border as ``^``.
        """
        try:
            return codecs.lookup(self.stdscr.encoding).name == "utf-8"
        except LookupError:
            return False

    def stop(self) -> None:
        """Restore the terminal. Safe to call more than once."""
        atexit.unregister(self.stop)
        if self._stdscr is None:
            return
        stdscr, self._stdscr = self._stdscr, None
        self._buffer = None
        with contextlib.suppress(curses.error):
            stdscr.keypad(False)
        if self.cursor is not None:
            self.cursor.restore()
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
        glyphs = self.glyphs
        for region in buffer.get_dirty():
            for row in range(region.top, region.bottom + 1):
                for col in range(region.left, region.right + 1):
                    cell = buffer.cell(row, col)
                    if cell.char == "":
                        # A wide character's second cell, which drawing the
                        # character before it has already filled.
                        continue
                    attr = self.attribute_resolver(cell.fg, cell.bg, cell.attr)
                    char = cell.char if glyphs is None else cell.char.translate(glyphs)
                    # A letter and the combining marks on it are one cell
                    # and several characters, which addch refuses.
                    single = len(char) == 1
                    if row == last_row and col == last_col:
                        # Writing the last cell scrolls the screen and raises;
                        # insch puts the character there without advancing.
                        # ASCII only: insch takes a chtype, and anything past
                        # a byte - a half block from a background image
                        # filling the screen - raises OverflowError rather
                        # than curses.error, which nothing here catches.
                        with contextlib.suppress(curses.error):
                            if single and char.isascii():
                                stdscr.insch(row, col, char, attr)
                            else:
                                stdscr.insstr(row, col, char, attr)
                    else:
                        with contextlib.suppress(curses.error):
                            if single:
                                stdscr.addch(row, col, char, attr)
                            else:
                                stdscr.addstr(row, col, char, attr)
                    painted += 1
        stdscr.noutrefresh()
        if self.cursor is not None:
            self.cursor.place()
        curses.doupdate()
        return painted
