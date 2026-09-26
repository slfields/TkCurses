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


"""A widget hanging off the screen shows the part that fits, and no more.

curses wraps a write that runs past the right edge onto the next row rather
than dropping it, so every widget that puts content on a window has to clip
for itself. ``_write_line`` is the one place that does it - and it was
reached by two of the forty-odd writes in the library, which is
TkCurses-4jd.5.

Measured before it was fixed, on a 40-column screen with each widget
starting at column 28 and 24 wide: a Text wrapped its line onto the row
below and lost the row's left border, a Scale's trough wrapped, and a
Canvas's pixels wrapped. A Listbox did not - it already went through
``_write_line``, which is what the other widgets look like now.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

OFF_THE_EDGE = """
import tkcurses

root = tkcurses.Tk()

text = tkcurses.Text(root, name='tx')
text.place(x=28, y=0, width=24, height=4)
text.insert('end', 'A' * 24)

box = tkcurses.Listbox(root, name='lb')
box.place(x=28, y=5, width=24, height=4)
box.insert('end', 'C' * 24, 'D' * 24)

scale = tkcurses.Scale(root, name='sc', orient='horizontal', showvalue=False)
scale.place(x=28, y=10, width=24, height=3)

canvas = tkcurses.Canvas(root, name='c')
canvas.place(x=28, y=14, width=24, height=4)
canvas.create_rectangle(0, 0, 40, 6, fill='white', outline='')

root.update_layout()
root.tk.screen.refresh()
root.after(6000, root.quit)
root.mainloop()
"""

#: The screen is 40 wide and every widget starts here, so twelve columns of
#: each are on screen and the rest is not.
EDGE = 28


@pytest.fixture
def clipped(terminal, tmp_path):
    term = terminal(cols=40, rows=20)
    term.run_source(OFF_THE_EDGE, workdir=tmp_path)
    term.wait_for(lambda t: any("A" in row for row in t.display), message="the text")
    term.wait_for_idle()
    return term


def nothing_left_of(term, column):
    """True if no row has anything drawn before ``column``.

    Everything on this screen starts at ``EDGE``, so a mark to the left of
    it can only have arrived by wrapping off the right-hand side.
    """
    return all(not row[:column].strip() for row in term.display)


def test_nothing_wraps_around_to_the_next_row(clipped):
    assert nothing_left_of(clipped, EDGE), clipped.describe()


def test_a_text_keeps_its_border_on_every_row(clipped):
    """The give-away when a line wrapped: the row below started with the
    wrapped text instead of the widget's left border.

    The Text's own four rows only - the scale below it draws no border at
    all, which is what it should do and not what this is about.
    """
    for row in clipped.display[0:4]:
        assert row[EDGE] in "┌│└", clipped.describe()


def test_the_scale_draws_one_row_of_trough(clipped):
    """It wrapped onto a second row before, which for a one-row trough is
    the whole of it drawn twice."""
    troughs = [row for row in clipped.display if "░" in row]
    assert len(troughs) == 1, clipped.describe()


def test_the_canvas_fills_only_the_cells_it_has(clipped):
    filled = [row for row in clipped.display if "█" in row]
    assert filled, clipped.describe()
    for row in filled:
        assert not row[:EDGE].strip(), clipped.describe()


# A control character breaks the same assumption from the other side: not a
# write running past the edge, but a write whose characters are not the
# width the caller counted on. TkCurses-wy7 covers real tab stops; this is
# about the display never disagreeing with the widget's own arithmetic.

CONTROL_CHARACTERS = """
import tkcurses

root = tkcurses.Tk()

text = tkcurses.Text(root, name='tx', wrap='none')
text.place(x=0, y=0, width=24, height=3)
text.insert('1.0', '\\tAB')

tkcurses.Label(root, name='lb', text='A\\tB').place(x=0, y=4)

entry = tkcurses.Entry(root, name='en', width=20)
entry.place(x=0, y=6, width=20)
entry.insert(0, 'C\\tD')

root.update_layout()

def report():
    # After a frame, not before: the widgets have not drawn themselves at
    # the point this file is read, so asking now would compare a bbox
    # against a blank screen.
    buffer = root.tk.screen.buffer
    buffer.write(9, 0, 'bbox=%s' % (text.bbox('1.1'),))
    root.tk.screen.refresh()

root.after(200, report)
root.after(4000, root.quit)
root.mainloop()
"""


@pytest.fixture
def controls(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(CONTROL_CHARACTERS, workdir=tmp_path)
    term.wait_for(lambda t: any("AB" in row for row in t.display), message="the text")
    term.wait_for_text("bbox=")
    term.wait_for_idle()
    return term


def test_a_tab_is_drawn_where_the_widget_says_it_is(controls):
    """The fault the user hit: report one column, draw in another.

    A tab handed straight to curses is expanded to a tab stop, so the A
    after it landed at column 10 while bbox said column 4 - and clicking
    the A selected a different character from the one under the pointer.
    """
    box = next(row for row in controls.display if "bbox=" in row)
    x = int(box.split("(")[1].split(",")[0])
    row = controls.display[1]
    assert row[x] == "A", f"bbox says column {x}, found {row[x]!r} in {row.rstrip()!r}"


def test_a_label_does_not_lose_what_follows_a_tab(controls):
    """It lost the B entirely: the tab pushed it past the label's width."""
    assert "A B" in controls.display[4]


def test_an_entry_does_not_push_text_across_the_box(controls):
    """C<tab>D put the D seven columns in, inside a twenty-column box."""
    row = next(row for row in controls.display if "C" in row and "D" in row)
    assert "C D" in row, row.rstrip()
