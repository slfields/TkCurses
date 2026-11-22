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

"""Treemap on a real terminal: what the screen actually shows.

Every test waits for each cell it asserts on, in one predicate, so a frame
caught half drawn is waited out rather than asserted on.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

# Each program ends itself, so a failing test cannot leave one behind.
PROGRAM = """
import tkcurses as tk
from tkcurses.treemap import Treemap

root = tk.Tk()
tree = Treemap(root)
tree.pack(fill="both", expand=True)
tree.insert("", "end", "web", text="web")
for name, size in (("nginx", 330), ("apache", 170), ("php", 50)):
    tree.insert("web", "end", name, text=name, value=size)
tree.insert("", "end", "db", text="db")
for name, size in (("postgres", 140), ("mysql", 60)):
    tree.insert("db", "end", name, text=name, value=size)
tree.insert("", "end", "cache", text="cache", value=100)
{body}
root.after(8000, root.destroy)
root.mainloop()
"""


def run(terminal, body="", *, term="xterm-256color"):
    screen = terminal(cols=50, rows=12, env={"TERM": term})
    screen.run_source(PROGRAM.format(body=body))
    return screen


def test_tiles_are_drawn_in_colour_with_labels_and_shades(terminal):
    term = run(terminal)

    def drawn(t):
        return (
            t.row(0).startswith("web 64.71%")
            and t.text_at(1, 0, 5) == "nginx"
            and t.text_at(2, 0, 6) == "38.82%"
            and t.row(11) == "total 850"
            and t.char_at(0, 0).bg == "green"
            and t.char_at(0, 0).bold
            and t.char_at(1, 0).bg == "green"
            and t.char_at(1, 0).fg == "black"
            # apache, beside nginx, in a shade of green: not green itself.
            and t.text_at(1, 19, 6) == "apache"
            and t.char_at(1, 19).bg not in ("green", "default")
        )

    term.wait_for(drawn, message="the services drawn in colour")


def test_eight_colours_outline_each_groups_children(terminal):
    term = run(terminal, term="xterm")

    def drawn(t):
        return (
            t.row(0).startswith("web 64.71%")
            and t.text_at(1, 0, 3) == "┌──"
            and t.text_at(2, 0, 6) == "│nginx"
            and t.char_at(1, 0).bg == "green"
            and t.char_at(2, 1).bg == "green"
            and t.char_at(2, 1).fg == "black"
        )

    term.wait_for(drawn, message="web's children outlined in green")


def test_a_change_to_an_item_is_drawn(terminal):
    term = run(
        terminal,
        "root.after(300, lambda: tree.item('cache', value=1000))",
    )

    def grown(t):
        # cache is an item, not a group: no header, its value under it.
        return (
            t.row(11) == "total 1750"
            and t.text_at(0, 0, 6) == "cache "
            and t.text_at(1, 0, 6) == "57.14%"
        )

    term.wait_for(grown, message="cache grown to the largest")
