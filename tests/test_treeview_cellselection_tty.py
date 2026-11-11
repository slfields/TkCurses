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

"""Selected cells on a real terminal: how they look, and the gestures."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def program(body: str) -> str:
    return f"""
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
tree = ttk.Treeview(root, columns=("a", "b"), height=3, selecttype="cell")
for column in ("#0", "a", "b"):
    tree.column(column, width=6, stretch=False)
for number in (1, 2, 3):
    tree.insert("", "end", iid=f"I{{number}}", text=f"row{{number}}",
                values=(f"a{{number}}", f"b{{number}}"))
tree.place(x=0, y=0, width=24, height=6)
said = tkcurses.Label(root, text="")
said.place(x=0, y=7)
def show(event=None):
    said.configure(text=" ".join(f"{{i}}{{c}}" for i, c in tree.cellselection()) or "none")
tree.bind("<<TreeviewSelect>>", show, add=True)
{body}
root.after(8000, root.quit)
root.mainloop()
"""


def test_a_selected_cell_is_reversed_and_its_row_is_not(terminal, tmp_path):
    term = terminal(cols=30, rows=10)
    term.run_source(
        program("tree.cellselection_set(('I2', 'b'))\nshow()\n"), workdir=tmp_path
    )
    term.wait_for_text("I2b")
    where = term.find_text("b2")
    assert where is not None
    row, column = where
    a2 = (row, term.find_text("a2")[1])
    # One wait naming every cell asserted on: TkCurses-txk.
    term.wait_for(
        lambda t: (
            t.char_at(row, column).reverse
            and t.char_at(row, column).data == "b"
            and not t.char_at(*a2).reverse
            and not t.char_at(row - 1, column).reverse
        ),
        message="b2 reversed, a2 and b1 not",
    )


def test_a_click_a_control_click_and_an_arrow_choose_cells(terminal, tmp_path):
    term = terminal(cols=30, rows=10)
    term.run_source(program("show()\n"), workdir=tmp_path)
    term.wait_for_text("none")
    row, column = term.find_text("a1")
    term.click(column, row)
    term.wait_for_text("I1a ")
    b3 = term.find_text("b3")
    term.click(b3[1], b3[0], ctrl=True)
    term.wait_for_text("I1a I3b")
    # The keyboard is still on row 1 - a Control-click does not move it - and
    # the column comes from the anchor, which the Control-click moved to b.
    term.send_keys("<Down>")
    term.wait_for_text("I2b")
