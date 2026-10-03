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

"""Where each character of a line sits, once tabs stop being one cell wide.

Everywhere else in this library a character is a cell and an offset is a
column. A tab breaks that: it advances to the next tab stop, so it occupies
a *range* of columns and the mapping from offset to column stops being the
identity. A left margin breaks it too, by moving where the line begins.

This module is that mapping, and its inverse. They must stay exact inverses
of each other: :meth:`Text.bbox` resolves an index to a cell and
``_index_at_cell`` resolves a cell back to an index, and if the two disagree
then clicking a character selects a different one from the one drawn under
the pointer.

Everything here was measured against real tkinter (Tk 9.0) with a monospace
font, so the pixel numbers read directly as columns.

**Stops are absolute, from the left edge of the widget.** Not from where the
line's text starts. With stops at 10 and 20 and an eight-column indent, the
indented line put its first character at 8 and the text after its first tab
at 10 - exactly where the unindented line put its own. That is what makes
columns line up down the page whatever the indent, and measuring stops from
the text start would destroy it.

**Extrapolation repeats the last interval.** Stops at 4 and 10 continue 16,
22. A single stop at 10 continues 20, 30, 40 - with nothing to subtract from,
the interval is the stop itself.

**A tab owns every column it spans.** ``ab<TAB>cd`` with a stop at 10 draws
the tab from column 2 to column 9 and ``c`` at 10; a click anywhere in 2..9
answers with the tab's own index. So the inverse maps a whole run back to one
character.

**All four of Tk's alignments are here.** Left, right and centre measure the
run between one tab and the next; ``numeric`` reads it, looking for a decimal
point. Each needs to see ahead to the next tab or the end of the line, which is
why they live with the ``-tabs`` option rather than with the stops -
TkCurses-wy7.2, and TkCurses-eq2 for numeric, whose three rules were measured
off a real widget because the manual states all three more loosely than Tk
implements them. See :func:`_numeric_offset`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tkcurses._core.errors import TclError

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "ALIGNMENTS",
    "DEFAULT_EVERY",
    "TabStops",
    "char_at",
    "column_of",
    "columns_of",
    "parse_tabs",
    "render",
]

#: Tk's default when ``-tabs`` is unset or empty: "every eight (average size)
#: characters". In a proportional font that is an approximation; in a
#: character grid it is exactly eight cells, so the grid is the more faithful
#: of the two.
DEFAULT_EVERY = 8

#: The two values Tk's ``-tabstyle`` takes.
TABULAR = "tabular"
WORDPROCESSOR = "wordprocessor"

#: The alignments a stop may carry. ``numeric`` is the only one that reads the
#: text rather than measuring it - see :func:`_numeric_offset`.
ALIGNMENTS = ("left", "right", "center", "numeric")


@dataclass(frozen=True)
class TabStops:
    """The columns a tab may advance to, counted from the widget's left edge.

    ``columns`` are the explicit stops. When there are none, stops fall every
    :attr:`every` columns, which is Tk's default.
    """

    columns: tuple[int, ...] = ()
    alignments: tuple[str, ...] = ()
    every: int = DEFAULT_EVERY

    def align(self, n: int) -> str:
        """How text is placed against the ``n``-th stop.

        Extrapolates the last one, because Tk extrapolates "using the
        spacing **and alignment** from the last tab stop in the list".
        """
        if not self.alignments:
            return "left"
        if n < len(self.alignments):
            return self.alignments[n]
        return self.alignments[-1]

    def index_after(self, column: int) -> int:
        """Which stop :meth:`after` would choose - wordprocessor needs the
        number as well as the column, to read the alignment off it."""
        n = 0
        while self.nth(n) <= column:
            n += 1
        return n

    def nth(self, n: int) -> int:
        """The ``n``-th stop, counting from zero, extrapolating past the list.

        Tk: "If the list of tab stops does not have enough elements to cover
        all of the tabs in a text line, then Tk extrapolates new tab stops
        using the spacing and alignment from the last tab stop in the list."

        Measured: 4 and 10 continue 16 and 22, so the spacing is the last
        interval. A lone stop at 10 continues 20, 30, 40 - there is no
        previous stop to subtract, and the stop itself is the interval.
        """
        if not self.columns:
            return (n + 1) * self.every
        if n < len(self.columns):
            return self.columns[n]
        if len(self.columns) >= 2:
            interval = self.columns[-1] - self.columns[-2]
        else:
            interval = self.columns[-1]
        return self.columns[-1] + (n - len(self.columns) + 1) * interval

    def after(self, column: int) -> int:
        """The first stop strictly past ``column`` - what wordprocessor uses.

        Strictly: a tab sitting exactly on a stop moves to the next one, or
        it would take no space at all.
        """
        n = 0
        while True:
            stop = self.nth(n)
            if stop > column:
                return stop
            n += 1


def parse_tabs(spec: Any, to_cells: Callable[[Any], float]) -> TabStops:
    """Read Tk's ``-tabs`` value into stops.

    The value is a flat list of distances, each optionally followed by an
    alignment word: ``2c left 4c 6c center`` is three stops, the first two
    left and the third centred. A string is split on whitespace, which is
    how Tcl would have seen it.

    ``to_cells`` converts one screen distance, and is the widget's
    :meth:`~tkcurses.Misc.winfo_fpixels` - a bare number is already cells
    here, and ``2c`` / ``1i`` / ``10p`` / ``3m`` convert at ten cells to the
    inch, which is the rule this project already uses for padx, pady and
    place coordinates.

    Raises:
        TclError: For an unknown alignment, for a stop that is not positive,
            or for stops that do not increase - all of which Tk rejects too.
    """
    items: list[Any]
    if spec is None or spec == "":
        return TabStops()
    if isinstance(spec, str):
        items = spec.split()
    elif isinstance(spec, (list, tuple)):
        items = list(spec)
    else:
        items = [spec]

    columns: list[int] = []
    alignments: list[str] = []
    for item in items:
        word = str(item).strip().lower()
        if word in ALIGNMENTS:
            if not columns:
                raise TclError(f"tab alignment {word!r} with no stop before it")
            alignments[-1] = word
            continue
        cells = round(to_cells(item))
        if cells <= 0:
            raise TclError(f"tab stop {item!r} is not positive")
        if columns and cells <= columns[-1]:
            raise TclError(
                f"tab stops must increase: {item!r} does not follow {columns[-1]}"
            )
        columns.append(cells)
        alignments.append("left")
    return TabStops(tuple(columns), tuple(alignments))


def columns_of(
    text: str,
    *,
    start: int = 0,
    stops: TabStops | None = None,
    style: str = TABULAR,
) -> list[int]:
    """The column each character of ``text`` begins at.

    ``start`` is the column the line begins in - the left margin. It is a
    column from the widget's edge, not zero, because the stops are measured
    from there too.

    The returned list has one entry per character. Where the next character
    begins is the end of this one, which is what makes a tab's span readable:
    it runs from its own column to the column of whatever follows.
    """
    return _walk(text, start, stops, style)[0]


def _walk(
    text: str, start: int, stops: TabStops | None, style: str
) -> tuple[list[int], int]:
    """Lay the line out once, returning each column and where the line ends.

    The end comes back with the columns rather than being worked out again
    afterwards, because only the walk knows where a TRAILING tab stopped -
    there is no following character to read it off.
    """
    stops = stops if stops is not None else TabStops()
    out: list[int] = []
    column = start
    tab = 0
    for index, character in enumerate(text):
        out.append(column)
        if character != "\t":
            column += 1
            continue
        number = stops.index_after(column) if style == WORDPROCESSOR else tab
        target = _aligned(stops, number, _run_after(text, index), column)
        # "If the tab character's x coordinate falls to the right of the
        # n'th tab stop, then a gap of a single space will be inserted as a
        # fallback" - measured: text ending at column 8 with a stop at 4 put
        # the next character at 9, not back at 4 and not at the following
        # stop. The same clamp catches a right- or centre-aligned run too
        # long to fit before its stop.
        column = target if target > column else column + 1
        tab += 1
    return out, column


def _run_after(text: str, index: int) -> str:
    """The characters that follow a tab, up to the next tab or the line end.

    What the alignments are measured against: Tk places the run between one tab
    and the next, not the whole rest of the line. ``numeric`` needs the text and
    not merely its length, which is why this answers a string.
    """
    following = text.find("\t", index + 1)
    stop = len(text) if following < 0 else following
    return text[index + 1 : stop]


#: What Tk accepts as a decimal point. The comma is not a guess: measured, the
#: run ``a,b`` - no digit anywhere in it - puts its comma on the stop, so the
#: comma is a separator in its own right rather than something only recognised
#: between digits.
_DECIMAL_POINTS = ".,"


def _numeric_offset(run: str) -> int:
    """How many columns before its stop a numeric-aligned run begins.

    Tk's manual states three rules: the decimal point goes on the stop, else the
    "least significant digit of the number" goes just left of it, else the text
    is right-justified. All three are measured here rather than taken from that
    wording, because all three are more specific than it says - read off a real
    Text widget with ``bbox()`` against a stop at column 20:

    ======================  =============================================
    run                     where it lands
    ======================  =============================================
    ``1.5``                 ``.`` on the stop
    ``1.5.2``               the **last** ``.`` on the stop, not the first
    ``a,b``                 the ``,`` on the stop, with no digits at all
    ``1.2,3``               the ``,`` - whichever separator comes last
    ``ab12cd34``            ``12`` ends just left of the stop, not ``34``
    ``abc``                 right-justified, ending just left of the stop
    ======================  =============================================

    So: the last ``.`` or ``,`` rather than "the decimal point"; the first run of
    digits rather than "the number"; and the comma counts even with no digit
    near it. The manual's third rule is the only one it describes exactly.
    """
    separators = [i for i, ch in enumerate(run) if ch in _DECIMAL_POINTS]
    if separators:
        return separators[-1]
    digits = [i for i, ch in enumerate(run) if ch.isdigit()]
    if digits:
        # The FIRST run of digits, so ab12cd34 aligns on 12. Walk from the
        # first digit until the digits stop.
        last = digits[0]
        while last + 1 < len(run) and run[last + 1].isdigit():
            last += 1
        return last + 1
    return len(run)


def _aligned(stops: TabStops, number: int, run: str, column: int) -> int:
    """Where the text after a tab begins, for that stop's alignment.

    Measured against Tk with a stop at 20 and the run ``word``: left put it
    at 20, right at 16 - the stop less its length - and centre at 18.

    Centre ROUNDS UP, which is not the obvious formula and is why it was
    measured: a run of three against a stop at 10 began at 8, not 9.

    ``numeric`` is the one that reads the run rather than counting it; see
    :func:`_numeric_offset`. It degrades into right alignment for a run with
    neither a separator nor a digit, which is Tk's own third rule and not a
    convenience - ``_numeric_offset`` returns the run's length there, and
    ``stop - len(run)`` is exactly what ``right`` computes.
    """
    stop = stops.nth(number)
    alignment = stops.align(number)
    length = len(run)
    if alignment == "right":
        return stop - length
    if alignment == "center":
        return stop - (length + 1) // 2
    if alignment == "numeric":
        return stop - _numeric_offset(run)
    del column
    return stop


def render(
    text: str,
    *,
    start: int = 0,
    stops: TabStops | None = None,
    style: str = TABULAR,
) -> str:
    """The line as it is drawn, tabs replaced by the blanks they span.

    Returned from column ``start`` onwards, so the caller writes it at the
    margin rather than at column zero.

    A tab is never drawn as a character: it is the gap between where it
    begins and where the next character does. Handing a raw tab to curses is
    what made every widget disagree with its own arithmetic - see
    ``_one_cell_each`` and TkCurses-zrm - and this is the other half of that
    fix, putting the blanks where the layout says they are rather than where
    the terminal guesses.
    """
    laid, end = _walk(text, start, stops, style)
    out = [" "] * (end - start)
    for index, character in enumerate(text):
        if character != "\t":
            out[laid[index] - start] = character
    return "".join(out)


def column_of(
    text: str,
    index: int,
    *,
    start: int = 0,
    stops: TabStops | None = None,
    style: str = TABULAR,
) -> int:
    """The column character ``index`` begins at.

    An index one past the end answers with the column the line ends in,
    which is where an insert cursor at the end of a line belongs.
    """
    laid, end = _walk(text, start, stops, style)
    if index < len(laid):
        return laid[max(0, index)]
    return end


def char_at(
    text: str,
    column: int,
    *,
    start: int = 0,
    stops: TabStops | None = None,
    style: str = TABULAR,
) -> int:
    """The index of the character occupying ``column``.

    The exact inverse of :func:`column_of` for every column a character
    covers. A column inside a tab's span answers with the tab, because that
    is what Tk does: with a stop at 10, ``ab<TAB>cd`` answered every click
    from column 2 to column 9 with the tab's own index.

    A column before the line starts answers 0, and one past its end answers
    the length, so a click in the empty space either side lands somewhere
    sensible rather than out of range.
    """
    laid, end = _walk(text, start, stops, style)
    if not laid or column < laid[0]:
        return 0
    for index in range(len(laid) - 1):
        if laid[index] <= column < laid[index + 1]:
            return index
    if column < end:
        return len(laid) - 1
    return len(laid)
