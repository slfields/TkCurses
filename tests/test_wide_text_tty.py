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

"""Wide text in the widgets that lay out rows and columns of their own.

A CJK ideograph takes two cells. Each of these measured its text with
``len()`` and so allotted one: a Listbox lost its border, a Scale wrote its
value over its label, a Menu cut its accelerators, a Notebook's tab was too
narrow for its label. TkCurses-r9k2.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

WIDE = "日本語"  # three ideographs, six cells
BAR = "│"


def program(body: str) -> str:
    return f"""
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
WIDE = {WIDE!r}
{body}
root.after(4000, root.quit)
root.mainloop()
"""


def _run(terminal, tmp_path, body, cols=36, rows=10):
    term = terminal(cols=cols, rows=rows)
    term.run_source(program(body), workdir=tmp_path)
    return term


def test_a_listbox_cuts_wide_text_at_its_border(terminal, tmp_path):
    term = _run(
        terminal,
        tmp_path,
        "box = tkcurses.Listbox(root, height=2, width=8)\n"
        "box.insert(0, WIDE + '|end', 'ab')\n"
        "box.place(x=1, y=1)",
    )
    term.wait_for(
        lambda t: (
            BAR + " " + WIDE + " " + BAR in t.display[2]
            and BAR + " ab     " + BAR in t.display[3]
        ),
        message="both rows inside the border",
    )


def test_a_listbox_scrolled_into_a_wide_character_leaves_a_blank(terminal, tmp_path):
    term = _run(
        terminal,
        tmp_path,
        "box = tkcurses.Listbox(root, height=1, width=8)\n"
        "box.insert(0, WIDE * 3)\n"
        "box.place(x=1, y=1)\n"
        "box.xview_scroll(1, 'units')",
    )
    term.wait_for(
        # A blank for the first ideograph's second half, two more, and no
        # room for the next in the one cell left.
        lambda t: BAR + "  " + WIDE[1:] + "  " + BAR in t.display[2],
        message="the first ideograph's second half a blank",
    )


def test_a_scale_keeps_its_value_clear_of_a_wide_label(terminal, tmp_path):
    term = _run(
        terminal,
        tmp_path,
        "tkcurses.Scale(root, label=WIDE, orient='horizontal', length=16)"
        ".place(x=1, y=1)",
    )
    term.wait_for(
        lambda t: WIDE + " 0" in t.display[1], message="the label, then the value"
    )


def test_a_menus_accelerators_line_up_after_a_wide_label(terminal, tmp_path):
    term = _run(
        terminal,
        tmp_path,
        "menu = tkcurses.Menu(root, tearoff=0)\n"
        "menu.add_command(label=WIDE, accelerator='Ctrl+X')\n"
        "menu.add_command(label='ab', accelerator='F1')\n"
        "root.after(100, lambda: menu.post(2, 2))",
    )
    term.wait_for(
        lambda t: (
            any(" " + WIDE + "  Ctrl+X " + BAR in row for row in t.display)
            and any(" ab" + " " * 10 + "F1 " + BAR in row for row in t.display)
        ),
        message="both accelerators flush right",
    )


def test_a_menubar_spaces_its_labels_by_their_cells(terminal, tmp_path):
    term = _run(
        terminal,
        tmp_path,
        "bar = tkcurses.Menu(root)\n"
        "sub = tkcurses.Menu(bar)\n"
        "bar.add_cascade(label=WIDE, menu=sub)\n"
        "bar.add_cascade(label='Edit', menu=sub)\n"
        "root.config(menu=bar)",
    )
    term.wait_for(
        lambda t: " " + WIDE + "  Edit " in t.display[0], message="both labels"
    )


def test_a_notebook_tab_is_as_wide_as_its_label(terminal, tmp_path):
    term = _run(
        terminal,
        tmp_path,
        "book = ttk.Notebook(root)\n"
        "book.add(tkcurses.Frame(book), text=WIDE)\n"
        "book.add(tkcurses.Frame(book), text='next')\n"
        "book.place(x=1, y=1, width=30, height=5)",
    )
    term.wait_for(
        lambda t: BAR + " " + WIDE + " " + BAR + BAR + " next " + BAR in t.display[2],
        message="two tabs, each closed round its label",
    )


def test_a_treeview_cuts_wide_text_at_its_column(terminal, tmp_path):
    term = _run(
        terminal,
        tmp_path,
        "tree = ttk.Treeview(root, height=2, columns=('a', 'b'))\n"
        "tree.column('#0', width=10, stretch=False)\n"
        "tree.column('a', width=5, stretch=False)\n"
        "tree.column('b', width=2, stretch=False)\n"
        "tree.heading('a', text=WIDE)\n"
        "tree.heading('b', text='B')\n"
        "tree.insert('', 'end', text=WIDE + WIDE, values=('xyz', 'q'))\n"
        "tree.place(x=1, y=1, width=21, height=6)",
    )
    # Ten cells of tree column: the marker cell and four ideographs, the
    # fifth left out; a space; five of the next column; a space; two more.
    # The heading's third ideograph would run into the B's column.
    term.wait_for(
        lambda t: (
            " " + WIDE + WIDE[0] + "  xyz   q " + BAR in t.display[3]
            and WIDE[:2] + "  B " + BAR in t.display[2]
        ),
        message="each cell and heading inside its own column",
    )


def test_a_treeview_scrolled_into_a_wide_character_leaves_a_blank(terminal, tmp_path):
    term = _run(
        terminal,
        tmp_path,
        "tree = ttk.Treeview(root, height=1, show='tree')\n"
        "tree.column('#0', width=20, stretch=False)\n"
        "tree.insert('', 'end', text=WIDE * 3)\n"
        "tree.place(x=1, y=1, width=12, height=3)\n"
        "root.after(50, lambda: tree.xview_scroll(2, 'units'))",
    )
    # Two cells scrolled off: the marker and the first ideograph's first
    # half, whose second half is a blank; then four ideographs, and a blank
    # where the fifth has one cell of the two it needs.
    term.wait_for(
        lambda t: BAR + " " + WIDE[1:] + WIDE[:2] + " " + BAR in t.display[2],
        message="a blank where the first ideograph was cut",
    )


def test_canvas_text_is_centred_on_its_cells(terminal, tmp_path):
    """Six cells centred on column 7 start at 4, not at 7 less half of
    three characters: four blanks either side, inside the border."""
    term = _run(
        terminal,
        tmp_path,
        "canvas = tkcurses.Canvas(root, width=14, height=2)\n"
        "canvas.create_text(7, 1, text=WIDE)\n"
        "canvas.place(x=1, y=1)",
    )
    term.wait_for(
        lambda t: BAR + " " * 4 + WIDE + " " * 4 + BAR in t.display[2],
        message="the text centred",
    )


def test_canvas_text_cut_by_the_edge_draws_no_half_ideograph(terminal, tmp_path):
    term = _run(
        terminal,
        tmp_path,
        "canvas = tkcurses.Canvas(root, width=5, height=2)\n"
        "canvas.create_text(0, 0, text=WIDE + 'x', anchor='nw')\n"
        "canvas.place(x=1, y=1)",
    )
    term.wait_for(
        lambda t: BAR + WIDE[:2] + " " + BAR in t.display[2],
        message="two ideographs and a blank, then the border",
    )


def test_a_labelframe_is_wide_enough_for_a_wide_caption(terminal, tmp_path):
    term = _run(
        terminal,
        tmp_path,
        "tkcurses.LabelFrame(root, text=WIDE + 'x', height=3).place(x=1, y=1)",
    )
    term.wait_for(
        lambda t: " " + WIDE + "x ╕" in t.display[1], message="the whole caption"
    )


def test_a_menu_underlines_the_letter_after_wide_ones(terminal, tmp_path):
    """underline counts characters: the a after three ideographs is the one
    marked, wherever the menu is posted."""
    term = _run(
        terminal,
        tmp_path,
        "menu = tkcurses.Menu(root, tearoff=0)\n"
        "menu.add_command(label=WIDE + 'a', underline=3)\n"
        "root.after(100, lambda: menu.post(2, 2))",
    )

    def marked(t):
        return [
            t.char_at(row, column).data
            for row in range(len(t.display))
            for column in range(36)
            if t.char_at(row, column).underscore
        ]

    # And the label still whole: the mark written a cell too far left lands
    # on an ideograph and breaks it.
    term.wait_for(
        lambda t: marked(t) == ["a"] and any(WIDE + "a" in row for row in t.display),
        message="only the a underlined, under itself",
    )


@pytest.mark.parametrize(
    "widget",
    [
        "box = tkcurses.Listbox(root, height=2, width=10, justify='right')\n"
        "box.insert(0, WIDE, 'ab')\n"
        "box.place(x=1, y=1)",
        "canvas = tkcurses.Canvas(root, width=10, height=4)\n"
        "canvas.create_text(0, 0, text=WIDE + '\\nab', anchor='nw', justify='right')\n"
        "canvas.place(x=1, y=1)",
    ],
    ids=["listbox", "canvas"],
)
def test_right_justified_short_text_lines_up_with_wide_text(terminal, tmp_path, widget):
    """``ab`` ends in the same cell as the six of ideographs above it. Both
    rows begin in plain cells, so string positions are columns up to the
    text."""
    term = _run(terminal, tmp_path, widget)

    def end(line, text):
        at = line.find(text)
        return None if at < 0 else at + (2 * len(text) if text == WIDE else len(text))

    term.wait_for(
        lambda t: (
            end(t.display[2], WIDE) is not None
            and end(t.display[2], WIDE) == end(t.display[3], "ab")
        ),
        message="the two rows flush right",
    )
