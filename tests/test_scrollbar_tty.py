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

"""What a Scrollbar looks like beside the thing it scrolls."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


PAIR = """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
frame = tkcurses.Frame(root, relief='solid')
frame.pack(fill='both', expand=True)
lb = tkcurses.Listbox(frame, width=16, height=5)
lb.pack(side='left', fill='both')
bar = tkcurses.Scrollbar(frame, command=lb.yview)
bar.pack(side='left', fill='y')
lb.configure(yscrollcommand=bar.set)
lb.insert('end', *['row %d' % n for n in range(20)])
root.update_layout()
root.tk.screen.refresh()
buffer.write(11, 0, 'ready')
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


def test_a_scrollbar_draws_arrows_and_a_thumb(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(PAIR, workdir=tmp_path)
    # "ready" is written to the buffer; the widgets' panels are composited by
    # the loop afterwards, so waiting for content rather than for the marker.
    term.wait_for_text("row 0")
    term.wait_for_idle()
    screen = "\n".join(term.display)
    assert "▲" in screen
    assert "▼" in screen
    assert "█" in screen
    assert "░" in screen


def test_scrolling_the_list_moves_the_thumb(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(PAIR, workdir=tmp_path)
    term.wait_for_text("row 0")

    def thumb_rows():
        return [i for i, line in enumerate(term.display) if "█" in line]

    term.wait_for_idle()
    before = thumb_rows()
    assert before, "the thumb should be drawn to begin with"
    term.click(4, 2)
    # Control-End rather than a run of Downs: a few rows of twenty move the
    # thumb by less than a cell, so the assertion would depend on the
    # arithmetic rounding the right way. Not End, which scrolls a listbox
    # sideways in Tk.
    term.send_keys("<Control-End>")
    term.wait_for(lambda t: thumb_rows() != before, message="the thumb to move")


def test_clicking_the_scrollbar_scrolls_the_list(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(PAIR, workdir=tmp_path)
    term.wait_for_text("row 0")
    term.wait_for_idle()
    arrow_row = next(i for i, line in enumerate(term.display) if "▼" in line)
    arrow_col = term.display[arrow_row].index("▼")
    for _ in range(3):
        term.click(arrow_col, arrow_row)
    term.wait_for(
        lambda t: "row 0" not in "\n".join(t.display), message="the list to scroll"
    )


def thumb_rows(term):
    return [i for i, line in enumerate(term.display) if "█" in line]


def test_dragging_the_thumb_scrolls_the_list(terminal, tmp_path):
    """What most people reach for first, and what the scrollbar could not do
    until now: pick the thumb up and pull it down."""
    term = terminal(cols=40, rows=12)
    term.run_source(PAIR, workdir=tmp_path)
    term.wait_for_text("row 0")
    term.wait_for_idle()

    rows = thumb_rows(term)
    column = term.display[rows[0]].index("█")
    term.send_mouse(column, rows[0], action="press")
    term._drain(0.05)
    for row in range(rows[-1] + 1, len(term.display) - 2):
        term.send_mouse(column, row, action="move")
        term._drain(0.03)
    term.send_mouse(column, len(term.display) - 3, action="release")

    term.wait_for(
        lambda t: "row 0" not in "\n".join(t.display),
        message="the list to scroll under the drag",
    )
    assert thumb_rows(term)[0] > rows[0], term.describe()


def test_the_thumb_follows_the_pointer_rather_than_jumping_to_it(terminal, tmp_path):
    """Pressing the thumb and letting go without moving scrolls nothing.

    This is Tk's behaviour, measured: a press on the slider only remembers
    where the drag began. The version before this one called moveto on the
    press, so grabbing the thumb anywhere but its top row moved the view
    before the hand did.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(PAIR, workdir=tmp_path)
    term.wait_for_text("row 0")
    term.wait_for_idle()

    rows = thumb_rows(term)
    column = term.display[rows[0]].index("█")
    before = "\n".join(term.display)
    term.click(column, rows[-1])
    term.wait_for_idle()
    assert "\n".join(term.display) == before, term.describe()


EXTENT = """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
vertical = tkcurses.Scrollbar(root, orient='vertical')
vertical.place(x=1, y=1, width=1, height=9)
vertical.set(0.2, 0.6)
horizontal = tkcurses.Scrollbar(root, orient='horizontal')
horizontal.place(x=4, y=1, width=11, height=1)
horizontal.set(0.0, 0.4)
root.update_layout()
root.tk.screen.refresh()
buffer.write(12, 0, 'ready')
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


def test_a_scrollbar_paints_every_cell_it_was_given(terminal, tmp_path):
    """No dead cells inside a scrollbar, measured on screen rather than inferred.

    This is the test that would have caught the fault a person found in UAT 40:
    a bar nine rows tall drew seven glyphs and left two rows that still took
    clicks and still painted background. A restyle made it visible as blue
    running past the last glyph.

    It reads the TERMINAL, deliberately. The obvious unit check - that a widget
    drawing no border keeps its whole allocation as content - passes with that
    bug present, because the fault was in the scrollbar's own `_length` and not
    in `_content_rect`. Measured both ways round before writing this: an
    invariant over the content area is cover without protection here.
    """
    term = terminal(cols=20, rows=14)
    term.run_source(EXTENT, workdir=tmp_path)
    term.wait_for_text("ready")
    term.wait_for_idle()

    # Found rather than assumed: the bar is placed at 1,1 inside the root, and
    # reading row 0 column 0 was reading the root's own border. Locating it by
    # its arrow keeps the test honest if the placement changes.
    column = next(
        x
        for x in range(term.cols)
        if any(term.char_at(y, x).data == "\u25b2" for y in range(term.rows))
    )
    top = next(y for y in range(term.rows) if term.char_at(y, column).data == "\u25b2")
    down = [term.char_at(top + offset, column).data for offset in range(9)]
    assert " " not in down, (
        f"a 9-row scrollbar left dead cells: {down!r} - every row of it should "
        f"carry an arrow, a trough cell or the thumb.\n{term.describe()}"
    )

    row = next(
        y
        for y in range(term.rows)
        if any(term.char_at(y, x).data == "\u25c4" for x in range(term.cols))
    )
    left = next(x for x in range(term.cols) if term.char_at(row, x).data == "\u25c4")
    across = [term.char_at(row, left + offset).data for offset in range(11)]
    assert " " not in across, (
        f"an 11-column scrollbar left dead cells: {across!r}\n{term.describe()}"
    )
