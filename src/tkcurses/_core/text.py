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

"""Laying text out in cells: wrapping, alignment and measurement.

A label decides how big it needs to be from the text it holds, and where each
line sits from ``justify`` and ``anchor``. None of that needs a terminal, so it
is here rather than in the widget - it can be exercised directly, and the
awkward cases (a word longer than the line, a wrap width of zero, trailing
blank lines) are worth exercising.

Wrapping is by word, falling back to breaking mid-word only when a single word
cannot fit. That is what Tk does, and the alternative - refusing to break and
letting the word overflow - puts characters outside the widget, which in a
character grid means on top of a neighbour.
"""

from __future__ import annotations

from tkcurses._core.cells import cells, clip_cells

__all__ = ["align_offset", "measure", "wrap", "wrap_spans"]

#: Where each justification puts a short line within the available width.
_JUSTIFY_FRACTIONS: dict[str, float] = {
    "left": 0.0,
    "center": 0.5,
    "right": 1.0,
}


def wrap(text: str, width: int = 0) -> list[str]:
    """Break ``text`` into display lines.

    Explicit newlines always break a line. ``width`` of zero or less means no
    wrapping at all, which is what a label without a ``wraplength`` does.

    An empty string is one empty line rather than no lines: a label holding
    nothing still occupies a row, as it does in Tk.
    """
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if width <= 0:
            lines.append(paragraph)
            continue
        lines.extend(_wrap_paragraph(paragraph, width))
    return lines or [""]


def _wrap_paragraph(paragraph: str, width: int) -> list[str]:
    """Wrap one newline-free run of text to ``width`` cells."""
    words = paragraph.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        for piece in _fit(word, width):
            if not current:
                current = piece
            elif cells(current) + 1 + cells(piece) <= width:
                current = f"{current} {piece}"
            else:
                lines.append(current)
                current = piece
    lines.append(current)
    return lines


def _fit(word: str, width: int) -> list[str]:
    """Split a word that cannot fit on a line of its own.

    Returned whole when it fits, so the common case allocates nothing.
    """
    if cells(word) <= width:
        return [word]
    pieces = []
    while word:
        # At least one character, so a wide one in a width of one still
        # moves on rather than looping for ever.
        piece = clip_cells(word, width) or word[0]
        pieces.append(piece)
        word = word[len(piece) :]
    return pieces


def measure(lines: list[str]) -> tuple[int, int]:
    """The cells a block of text occupies, as ``(width, height)``."""
    return max((cells(line) for line in lines), default=0), len(lines)


def align_offset(line_width: int, available: int, justify: str = "left") -> int:
    """Where a line starts within ``available`` cells.

    Never negative: a line wider than the space it is given starts at the left
    edge and is clipped by whoever draws it, rather than starting off-screen.

    Raises:
        ValueError: If ``justify`` is not one tkinter defines.
    """
    try:
        fraction = _JUSTIFY_FRACTIONS[justify.strip().lower()]
    except KeyError:
        raise ValueError(f"unknown justify: {justify!r}") from None
    return max(0, int((available - line_width) * fraction))


def word_break(line: str, start: int, end: int) -> int:
    """Where a row of ``line`` from ``start`` ends, when ``end`` is the first
    character that does not fit: past the spaces there, which hang beyond
    the edge as Tk's do, or after the last space that fits, or at ``end``
    in the middle of a word too long for any row."""
    if line[end] == " ":
        while end < len(line) and line[end] == " ":
            end += 1
        return end
    cut = line.rfind(" ", start, end)
    return cut + 1 if cut > start else end


def wrap_spans(line: str, width: int, mode: str = "char") -> list[tuple[int, int]]:
    """Where one line breaks on screen, as ``(start, end)`` character offsets.

    Offsets rather than strings, because a Text has to turn a screen position
    back into a position in its buffer, and a list of wrapped strings cannot
    answer that - the breaks have thrown the offsets away. :func:`wrap` is
    still the right thing for a Label, which only ever needs to draw.

    ``mode`` is Tk's ``wrap`` option: ``none`` leaves the line whole and lets
    the widget scroll sideways, ``char`` breaks wherever the width runs out,
    and ``word`` breaks at the last space that fits, keeping that space at the
    end of the line it broke - which is what stops a wrapped paragraph
    starting every line with a space. Spaces after a word that reaches the
    edge stay on its row too, however many, past the edge where nothing
    draws them: measured on Tk 9.0.2, ``16 a's + "   bbb"`` in 16 columns is
    one row to the third space and ``bbb`` on the next. TkCurses-5co5.

    Always at least one span, so an empty line still occupies a row.
    """
    if width <= 0 or mode == "none" or not line:
        return [(0, len(line))]
    spans: list[tuple[int, int]] = []
    start = 0
    while start < len(line):
        end = min(start + width, len(line))
        if mode == "word" and end < len(line):
            end = word_break(line, start, end)
        spans.append((start, end))
        start = end
    return spans
