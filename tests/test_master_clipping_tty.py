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


"""A widget shows only inside its master, and only the part that is there.

X clips every window by its parent's, so in Tk a label placed 6 wide in a
5-wide pane shows 5 cells and whatever is beside the pane stays visible. A
widget here was clipped to the screen and never to its master, and drew over
its container's siblings - seen in UAT 40, where a shrunken ttk.Panedwindow
pane's label covered the sash. TkCurses-wbov.

Measured on the same screens before the fix: the frame's child ran on to
``12345|789`` past the frame's right edge, a child placed at ``x=-2`` drew
``abcdefg`` from two cells left of the frame, and a label placed at ``x=-3``
on the root showed ``ABCDE`` - its first five cells, where Tk shows its last
five. The screen's left and top edges had never shifted the drawing either.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

CLIPPED = """
import tkcurses

root = tkcurses.Tk()
tkcurses.Label(root, text='ABCDEFGH').place(x=-3, y=0)

frame = tkcurses.Frame(root, width=5, height=4)
frame.place(x=10, y=2)
tkcurses.Label(frame, text='123456789').place(x=0, y=0)
tkcurses.Label(frame, text='abcdefg').place(x=-2, y=1)
inner = tkcurses.Frame(frame, width=20, height=1)
inner.place(x=0, y=2)
tkcurses.Label(inner, text='nested-past-both').place(x=-1, y=0)

tkcurses.Label(root, text='after').place(x=16, y=2)

root.update_layout()
root.tk.screen.refresh()
root.after(6000, root.quit)
root.mainloop()
"""


@pytest.fixture
def clipped(terminal, tmp_path):
    term = terminal(cols=30, rows=8)
    term.run_source(CLIPPED, workdir=tmp_path)
    term.wait_for(
        lambda t: (
            t.text_at(0, 0, 5) == "DEFGH"
            and t.text_at(2, 10, 11) == "12345 after"
            and t.text_at(3, 8, 9) == "  cdefg  "
            and t.text_at(4, 8, 9) == "  ested  "
        ),
        message="every clipped label",
    )
    return term


def test_a_child_shows_no_further_right_than_its_master(clipped):
    """The frame is columns 10-14; ``123456789`` stops at its edge and the
    gap and the label beside the frame are left alone."""
    assert clipped.text_at(2, 10, 11) == "12345 after", clipped.describe()


def test_a_child_placed_left_of_its_master_shows_its_right_hand_part(clipped):
    """``x=-2`` puts ``ab`` outside the frame: nothing is drawn there, and
    the frame's first cell holds the child's third, ``c``."""
    assert clipped.text_at(3, 8, 9) == "  cdefg  ", clipped.describe()


def test_a_grandchild_is_clipped_by_every_ancestor(clipped):
    """``inner`` is 20 wide inside the 5-wide frame, and its label starts
    one cell before it: the frame's edges bound both."""
    assert clipped.text_at(4, 8, 9) == "  ested  ", clipped.describe()


def test_the_screens_left_edge_shifts_the_drawing_too(clipped):
    """A widget placed at ``x=-3`` shows the cells from its fourth on."""
    assert clipped.text_at(0, 0, 6) == "DEFGH ", clipped.describe()


BORDERED = """
import tkcurses

root = tkcurses.Tk()
top = tkcurses.Toplevel(root)
top.geometry('12x5+2+1')
tkcurses.Label(top, text='WIDEWIDEWIDEWIDE').place(x=3, y=1)
tkcurses.Label(top, text='under').place(x=0, y=3)

root.update_layout()
root.tk.screen.refresh()
root.after(6000, root.quit)
root.mainloop()
"""


def test_a_toplevels_border_is_not_drawn_over(terminal, tmp_path):
    """The border stands for the window manager's frame, which no window
    inside it can cover. Before, the label ran across it and on past the
    window. ``under`` at ``y=3`` is on the bottom border row, and does not
    show at all."""
    term = terminal(cols=30, rows=8)
    term.run_source(BORDERED, workdir=tmp_path)
    term.wait_for(
        lambda t: (
            t.text_at(3, 2, 13) == "│   WIDEWID│ "
            and t.text_at(5, 2, 12) == "└──────────┘"
        ),
        message="the label inside the border",
    )


SLIDING = """
import tkcurses

root = tkcurses.Tk()
frame = tkcurses.Frame(root, width=5, height=1)
frame.place(x=4, y=1)
label = tkcurses.Label(frame, text='0123456789')
label.place(x=-2, y=0)

root.update_layout()
root.tk.screen.refresh()
root.after(300, lambda: label.place(x=-4, y=0))
root.after(6000, root.quit)
root.mainloop()
"""


def test_a_child_sliding_under_its_master_is_redrawn(terminal, tmp_path):
    """Both positions cover all five of the frame's cells, so the child's
    window is the same size in the same place both times - only which part
    of the label is in it changes, and that alone has to repaint it."""
    term = terminal(cols=20, rows=4)
    term.run_source(SLIDING, workdir=tmp_path)
    term.wait_for(lambda t: t.text_at(1, 4, 5) == "23456", message="before")
    term.wait_for(lambda t: t.text_at(1, 4, 5) == "45678", message="after")


PANES = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
panes = ttk.Panedwindow(root, orient='horizontal')
panes.place(x=0, y=0, width=16, height=4)
for side in ('left', 'right'):
    pane = ttk.Frame(panes)
    tkcurses.Label(pane, text=side * 2, anchor='w').place(x=0, y=1, width=6)
    panes.add(pane, weight=1)

root.update_layout()
root.after(200, lambda: panes.sashpos(0, 4))
root.after(6000, root.quit)
root.mainloop()
"""


def test_a_shrunken_pane_leaves_the_sash_showing(terminal, tmp_path):
    """UAT 40's case: the left pane is 4 wide after the sash moves, and its
    6-wide label stops there instead of covering the sash's handle, which
    is drawn on that row."""
    term = terminal(cols=20, rows=6)
    term.run_source(PANES, workdir=tmp_path)
    term.wait_for(lambda t: t.text_at(1, 0, 4) == "left", message="the label")
    term.wait_for(
        lambda t: t.text_at(0, 4, 1) == "│" and t.text_at(1, 4, 1) == "┃",
        message="the sash in column 4, its handle on the label's row",
    )


CURSOR = """
import tkcurses

root = tkcurses.Tk()
frame = tkcurses.Frame(root, width=6, height=3)
frame.place(x=2, y=1)
entry = tkcurses.Entry(frame, width=12)
entry.place(x=0, y=0)
entry.insert(0, 'abcdefgh')
entry.icursor(2)
entry.focus_set()

root.update_layout()
root.after(6000, root.quit)
root.mainloop()
"""


def test_the_cursor_shows_where_the_widget_is_visible(terminal, tmp_path):
    term = terminal(cols=20, rows=4)
    term.run_source(CURSOR, workdir=tmp_path)
    term.wait_for(lambda t: t.cursor_cell() == (2, 5), message="the cursor at c")


def test_the_cursor_hides_in_a_part_of_the_widget_clipped_away(terminal, tmp_path):
    """The insert point moves to after ``h``, past the frame's last cell: in
    Tk it is in a part of the entry nobody can see, and so is the cursor.
    Seen first at ``c``, so that its going is the move and not the focus
    arriving late."""
    term = terminal(cols=20, rows=4)
    source = CURSOR.replace(
        "root.update_layout()",
        "root.update_layout()\nroot.after(400, lambda: entry.icursor('end'))",
    )
    term.run_source(source, workdir=tmp_path)
    term.wait_for(lambda t: t.cursor_cell() == (2, 5), message="the cursor at c")
    term.wait_for(lambda t: t.cursor_cell() is None, message="no cursor")
