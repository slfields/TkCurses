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

"""A Treeview's column and heading anchors on a real terminal.

What Tk 9.0.2 was seen to draw: headings centred unless told otherwise; a
column's values where its anchor puts them; in the tree column the indent
and marker at the left and the text placed after them; and text too wide
starting at the left, cut at the right, whatever the anchor.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

PROGRAM = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
tree = ttk.Treeview(root, columns=("r", "w"), height=3)
tree.column("#0", width=12, anchor="e", stretch=False)
tree.column("r", width=8, anchor="e", stretch=False)
tree.column("w", width=8, stretch=False)
tree.heading("#0", text="Who")
tree.heading("r", text="Right", anchor="e")
tree.heading("w", text="Mid")
top = tree.insert("", "end", text="top", values=("ab", "abcdefghijk"), open=True)
tree.insert(top, "end", text="kid", values=("x", "y"))
tree.place(x=0, y=0, width=34, height=6)
root.after(8000, root.quit)
root.mainloop()
"""

# Inside the border: the tree column is cells 1-12, r is 14-21, w is 23-30.
HEADING, TOP, KID = 1, 2, 3


def test_cells_and_headings_sit_where_their_anchors_put_them(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    term.run_source(PROGRAM, workdir=tmp_path)
    # One wait naming every row asserted on: TkCurses-txk.
    term.wait_for(
        lambda t: (
            "Who" in t.row(HEADING) and "kid" in t.row(KID) and "ab" in t.row(TOP)
        ),
        message="the tree drawn",
    )
    heading, top, kid = term.row(HEADING), term.row(TOP), term.row(KID)
    # "Who" centred in twelve cells; "Mid" centred in eight; "Right" at the right.
    assert heading[1:13] == "    Who     ", term.describe()
    assert heading[23:31] == "  Mid   ", term.describe()
    assert heading[14:22] == "   Right", term.describe()
    # Under anchor e, a parent and its child end together whatever their depth.
    assert top[1:13].endswith("top") and kid[1:13].endswith("kid"), term.describe()
    assert top[1] == "▾", term.describe()
    assert top[14:22] == "      ab", term.describe()
    # Too wide: its beginning shows, cut at the right.
    assert top[23:31] == "abcdefgh", term.describe()
