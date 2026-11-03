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

"""Reliefs on a real terminal. TkCurses-gm66.5.

What pyte can see: the box a whole-widget relief draws, and how long a
handle is. A sunken part is dim, which pyte does not record; that is read in
``test_reliefs.py`` instead.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
{body}
root.after(1500, root.quit)
root.mainloop()
root.destroy()
"""


def run(terminal, tmp_path, body, cols=40, rows=10):
    term = terminal(cols=cols, rows=rows)
    term.run_source(program(body), workdir=tmp_path)
    return term


def glyph(character):
    return lambda cell: cell.data == character


def test_an_indicatorless_button_shows_offrelief_then_sinks(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "v = tkcurses.IntVar(value=0)\n"
        "tkcurses.Checkbutton(root, text='Bold', variable=v, indicatoron=False,\n"
        "                     borderwidth=1, offrelief='ridge').place(x=0, y=0)\n"
        "root.after(300, lambda: v.set(1))",
    )
    # Off: the ridge box, double lines; on: sunken, single ones.
    term.wait_for_cell(0, 0, glyph("╔"), message="the off relief")
    term.wait_for_cell(0, 0, glyph("┌"), message="sunken once on")
    term.wait_for_cell(1, 1, glyph("B"))


def test_the_overrelief_is_put_on_when_the_pointer_arrives(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "b = tkcurses.Button(root, text='Go', overrelief='ridge')\n"
        "b.place(x=0, y=0)\n"
        "root.after(300, lambda: b.event_generate('<Enter>'))\n"
        "root.after(600, lambda: b.event_generate('<Leave>'))",
    )
    term.wait_for_cell(0, 0, glyph("┌"), message="raised to begin with")
    term.wait_for_cell(0, 0, glyph("╔"), message="the over relief")
    term.wait_for_cell(0, 0, glyph("┌"), message="raised again after leaving")


def test_a_handle_is_as_long_as_sliderlength(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "s = tkcurses.Scale(root, orient='horizontal', from_=0, to=10,\n"
        "                   showvalue=False, length=12, sliderlength=3,\n"
        "                   highlightthickness=0)\n"
        "s.set(10)\n"
        "s.place(x=0, y=0)",
    )
    for column in (10, 11, 12):
        term.wait_for_cell(0, column, glyph("█"), message=f"handle at {column}")
    term.wait_for_cell(0, 9, glyph("░"), message="trough before the handle")
