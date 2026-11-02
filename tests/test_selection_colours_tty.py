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

"""Selection colours on a real terminal. TkCurses-gm66.3.

A selection nobody coloured is reversed; one given ``selectbackground`` and
``selectforeground`` is drawn in them; a Text whose ``inactiveselectbackground``
is ``""`` shows no selection without the focus.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

#: Eight colours, so a colour name comes back as itself.
EIGHT = {"TERM": "xterm", "COLORTERM": ""}


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
{body}
root.after(1500, root.quit)
root.mainloop()
root.destroy()
"""


def coloured(cell):
    return cell.fg == "cyan" and cell.bg == "red" and not cell.reverse


@pytest.mark.parametrize(
    "make",
    [
        "e = tkcurses.Entry(root, width=10, {colours})\n"
        "e.place(x=1, y=1)\n"
        "e.insert(0, 'abcdef')\n"
        "e.selection_range(0, 3)",
        "e = tkcurses.Text(root, width=10, height=2, {colours})\n"
        "e.place(x=1, y=1)\n"
        "e.insert('1.0', 'abcdef')\n"
        "e.tag_add('sel', '1.0', '1.3')\n"
        "e.focus_set()",
    ],
    ids=["Entry", "Text"],
)
def test_a_selection_is_drawn_in_the_colours_given(terminal, tmp_path, make):
    term = terminal(cols=40, rows=8, env=EIGHT)
    colours = "selectbackground='red', selectforeground='cyan'"
    term.run_source(program(make.format(colours=colours)), workdir=tmp_path)
    for column in (2, 3, 4):
        term.wait_for_cell(2, column, coloured, message="the selected text")
    term.wait_for_cell(2, 5, lambda cell: cell.data == "d")
    assert not coloured(term.char_at(2, 5)), term.describe()


def test_a_listbox_selection_is_drawn_in_the_colours_given(terminal, tmp_path):
    term = terminal(cols=40, rows=8, env=EIGHT)
    term.run_source(
        program(
            "b = tkcurses.Listbox(root, width=10, height=3,\n"
            "                     selectbackground='red', selectforeground='cyan')\n"
            "b.place(x=1, y=1)\n"
            "b.insert('end', 'one', 'two')\n"
            "b.selection_set(1)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("two")
    row = term.find_text("two")[0]
    term.wait_for_cell(row, term.find_text("two")[1], coloured, message="'two'")
    one_row, one_column = term.find_text("one")
    term.wait_for_cell(one_row, one_column, lambda cell: not coloured(cell))


def test_an_uncoloured_selection_is_still_reversed(terminal, tmp_path):
    term = terminal(cols=40, rows=8, env=EIGHT)
    term.run_source(
        program(
            "e = tkcurses.Entry(root, width=10)\n"
            "e.place(x=1, y=1)\n"
            "e.insert(0, 'abcdef')\n"
            "e.selection_range(0, 3)"
        ),
        workdir=tmp_path,
    )
    for column in (2, 3, 4):
        term.wait_for_cell(2, column, lambda cell: cell.reverse)


def test_an_empty_inactive_colour_hides_an_unfocused_selection(terminal, tmp_path):
    """Two Texts with the same selection: the focused one shows it, the other,
    told ``inactiveselectbackground=""``, does not.

    ``exportselection`` off, or the second ``tag_add`` would take the PRIMARY
    selection and clear the first Text's, as in Tk.
    """
    term = terminal(cols=40, rows=10, env=EIGHT)
    term.run_source(
        program(
            "for row, name in ((1, 'focused'), (5, 'unfocused')):\n"
            "    t = tkcurses.Text(root, width=10, height=2, name=name,\n"
            "                      exportselection=False,\n"
            "                      inactiveselectbackground='')\n"
            "    t.place(x=1, y=row)\n"
            "    t.insert('1.0', 'abcdef')\n"
            "    t.tag_add('sel', '1.0', '1.3')\n"
            "root.nametowidget('focused').focus_set()"
        ),
        workdir=tmp_path,
    )
    for column in (2, 3, 4):
        term.wait_for_cell(2, column, lambda cell: cell.reverse)
        term.wait_for_cell(6, column, lambda cell: cell.data in "abc")
    hidden = [term.char_at(6, column).reverse for column in (2, 3, 4)]
    assert not any(hidden), term.describe()
