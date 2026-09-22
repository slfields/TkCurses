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

"""Painting cells past curses, for pictures that curses cannot hold.

**Why this exists, and why it is not a shortcut.** Curses paints a *pair* -
a registered (foreground, background) combination - and there are 255 of
them, because :func:`curses.color_pair` packs the number into eight bits of
the attribute. ncurses itself will make 65536 and has ``init_extended_pair``
to name them; Python's binding does not expose it. Measured on a real
terminal: ``init_pair(300, ...)`` succeeds, ``color_pair(300) >> 8`` is 44,
and a cell painted with it shows pair 44's colours.

A photograph wants far more combinations than that. mickey.gif at 106x33
cells asks for 991. Fitting it to 255 costs most of its colour: measured
against a Lanczos reference, TkCurses drew it with 14 colours scoring 35.06
where chafa drew it with 1778 scoring 11.78. **The ceiling is the single
largest thing between this library and a dedicated image renderer**, and no
amount of choosing colours better addresses it, because the scarce thing is
combinations rather than colours.

chafa has no pair table because it writes its own escape sequences. So does
this.

**What it costs.** Curses no longer knows what is on those cells. Its model
and the screen diverge, which is the risk `TkCurses-gyo` and `TkCurses-by3`
ran into for mouse modes and resizing. The arrangement that keeps it honest:

- The cells are written into the curses window as well, in the nearest pair
  curses can manage. If direct painting never happens, or happens onto a
  terminal that ignores it, what shows is the ordinary rendering rather than
  a hole.
- The overlay is emitted *after* ``doupdate``, so curses has finished and
  cannot paint over it within the frame.
- It is re-emitted every frame it is wanted, because curses will repaint
  those cells whenever anything near them changes and will not say so.

**Semicolons, not colons.** ``ESC[38;2;r;g;b m``. ncurses emits the
colon-separated form from the ``xterm-direct`` terminfo - ``ESC[38:2::r:g:b
m``, with an empty colour-space field - and many terminals cannot parse it,
which is `TkCurses-bvu.7`: blocks.gif rendered correctly at 8, 16 and 256
colours and wrongly at truecolor, while chafa was fine on the same terminal.
Writing the sequence ourselves is also what fixes that.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Callable, Iterable

#: A cell to paint: glyph, and the two colours it needs as RGB triples. A
#: background of None means the cell keeps whatever is behind it, which
#: cannot be expressed in one SGR write - so those cells are left to curses.
Cell = tuple[str, tuple[int, int, int], tuple[int, int, int]]


class DirectPainter:
    """Collects cells during a frame and writes them after curses is done."""

    def __init__(self, stream: int = 1) -> None:
        self._stream = stream
        #: Cells by whoever contributed them. **Kept apart on purpose**: one
        #: shared dictionary meant a second picture wiped the first, because
        #: each widget clears before it draws, and a picture whose widget
        #: stopped drawing - a collected image - left its cells behind for
        #: ever.
        self._cells: dict[int, dict[tuple[int, int], Cell]] = {}
        self._enabled = False
        self._index_of: Callable[[tuple[int, int, int]], int] | None = None
        #: What was last written, so an unchanged picture over an unchanged
        #: frame costs nothing. A full-screen photograph is tens of
        #: kilobytes; writing it again every tick is most of the cost of
        #: having it.
        self._written: bytes | None = None

    @property
    def enabled(self) -> bool:
        """True when cells are being written past curses at all."""
        return self._enabled

    @property
    def form(self) -> str:
        """Which colour form is written: ``truecolor``, ``palette``, ``off``.

        Both escape the pair ceiling; they differ in what they can say. A
        palette terminal gets ``ESC[38;5;N``, so its own theme decides what
        the number looks like; direct colour gets the exact RGB.
        """
        if not self._enabled:
            return "off"
        return "palette" if self._index_of is not None else "truecolor"

    def enable(
        self,
        enabled: bool = True,
        index_of: Callable[[tuple[int, int, int]], int] | None = None,
    ) -> None:
        """Turn painting on, and say in which of the two forms.

        ``index_of`` given means the terminal has a palette rather than
        direct colour, and cells are written as ``ESC[38;5;N m`` against it.
        **That case matters as much as truecolor**: a 256-colour terminal
        also has no pair ceiling when the sequences are written by hand, and
        going through curses there costs just as much. Measured on mickey at
        106x33, 14 colours through the pair table against 88 for a renderer
        writing its own.

        ``index_of`` omitted means direct colour, ``ESC[38;2;r;g;b m``.
        """
        self._enabled = enabled
        self._index_of = index_of

    def clear(self, owner: object | None = None) -> None:
        """Forget ``owner``'s cells, or everything when none is named.

        A widget calls this before it draws, so what it contributed last
        time does not survive it drawing something smaller - or nothing at
        all, which is what a collected image leaves behind.
        """
        if owner is None:
            self._cells.clear()
        else:
            self._cells.pop(id(owner), None)

    @property
    def pending(self) -> int:
        """How many cells are waiting to be painted."""
        return sum(len(cells) for cells in self._cells.values())

    def add(
        self,
        owner: object,
        row: int,
        column: int,
        glyph: str,
        fore: tuple[int, int, int],
        back: tuple[int, int, int],
    ) -> None:
        """Note one cell of ``owner``'s, in absolute screen coordinates."""
        if self._enabled:
            self._cells.setdefault(id(owner), {})[(row, column)] = (
                glyph,
                fore,
                back,
            )

    def render(self) -> bytes:
        """The escape sequences for everything collected, or empty.

        Colours are written only where they change, and each run of adjacent
        cells is written after a single cursor move. A photograph is mostly
        runs of one colour, so this is the difference between a few kilobytes
        a frame and a hundred.
        """
        merged: dict[tuple[int, int], Cell] = {}
        for cells in self._cells.values():
            merged.update(cells)
        if not merged:
            return b""
        out: list[str] = []
        fore: tuple[int, int, int] | None = None
        back: tuple[int, int, int] | None = None
        previous: tuple[int, int] | None = None
        for (row, column), (glyph, want_fore, want_back) in sorted(merged.items()):
            if previous != (row, column - 1):
                # Not continuing a run, so say where we are. One-based.
                out.append(f"\x1b[{row + 1};{column + 1}H")
            if want_fore != fore:
                out.append(self._sgr(38, want_fore))
                fore = want_fore
            if want_back != back:
                out.append(self._sgr(48, want_back))
                back = want_back
            out.append(glyph)
            previous = (row, column)
        # Left as curses found it, or the next thing it writes inherits the
        # picture's colours.
        out.append("\x1b[0m")
        return "".join(out).encode("utf-8", "replace")

    def _sgr(self, role: int, colour: tuple[int, int, int]) -> str:
        """One colour as a select-graphic-rendition, in whichever form."""
        if self._index_of is not None:
            return f"\x1b[{role};5;{self._index_of(colour)}m"
        return f"\x1b[{role};2;{colour[0]};{colour[1]};{colour[2]}m"

    def paint(self, repainted: bool = True) -> int:
        """Write the collected cells to the terminal. Returns bytes written.

        Called after ``doupdate``, on the thread that owns the terminal.

        Args:
            repainted: True if curses put anything on the screen this frame.
                When it did not, and the cells have not changed either, what
                is on the terminal is still ours and writing it again is
                pure cost - tens of kilobytes a tick for a full-screen
                picture, which is most of the expense of painting this way.

        The gap this leaves, stated rather than hidden: a panel moving over
        the picture and away again repaints those cells from the window
        underneath without any cell of ours changing, and without the screen
        buffer being touched. The picture is then curses' approximation
        until the next redraw. Panels move rarely and a redraw follows
        almost at once, so the trade is worth it - but it is a trade.
        """
        data = self.render()
        if not data:
            self._written = None
            return 0
        if not repainted and data == self._written:
            return 0
        # **Written in a loop, because os.write is allowed to write less than
        # it is given** and a terminal is exactly where that happens: a pty
        # has a fixed buffer, and one frame of a full-screen picture is tens
        # of kilobytes. Ignoring the count left the first part of the picture
        # in exact colour and the rest in whatever curses had put there,
        # which measured as MORE distinct colours and a worse picture - the
        # shape of failure that looks like a quality problem and is not.
        written = 0
        while written < len(data):
            try:
                sent = os.write(self._stream, data[written:])
            except BlockingIOError:
                continue
            except OSError:
                # A closed terminal is not worth failing a frame over; the
                # curses rendering underneath is still correct.
                break
            if sent <= 0:
                break
            written += sent
        self._written = data if written == len(data) else None
        return written

    def extend(
        self,
        owner: object,
        cells: Iterable[
            tuple[int, int, str, tuple[int, int, int], tuple[int, int, int]]
        ],
    ) -> None:
        """Note several of ``owner``'s cells at once."""
        for row, column, glyph, fore, back in cells:
            self.add(owner, row, column, glyph, fore, back)
