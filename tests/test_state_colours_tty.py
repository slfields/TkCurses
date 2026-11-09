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

"""State and part colours on a real terminal. TkCurses-gm66.4.

Each scene gives one widget a colour for a state or a part, and reads the
cells that should wear it - and one beside them that should not. Eight
colours, so a colour name comes back as itself (pyte calls yellow "brown").
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

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


def run(terminal, tmp_path, body, cols=40, rows=12):
    term = terminal(cols=cols, rows=rows, env=EIGHT)
    term.run_source(program(body), workdir=tmp_path)
    return term


def background(colour):
    return lambda cell: cell.bg == colour


def foreground(colour):
    return lambda cell: cell.fg == colour


def test_an_active_button_is_drawn_on_activebackground(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "tkcurses.Button(root, text='Go', state='active',\n"
        "                activebackground='red').place(x=0, y=0)\n"
        "tkcurses.Label(root, text='plain').place(x=20, y=0)",
    )
    # Edge to edge, border included, as Tk paints it - and not reversed.
    for column in (0, 3, 7):
        term.wait_for_cell(1, column, background("red"), message="the button")
    term.wait_for_cell(1, 3, lambda cell: cell.data == "G" and not cell.reverse)
    term.wait_for_cell(0, 20, lambda cell: cell.data == "p" and cell.bg != "red")


def test_a_checkbuttons_indicator_is_drawn_on_selectcolor(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "v = tkcurses.IntVar(value=1)\n"
        "tkcurses.Checkbutton(root, text='Tick', variable=v,\n"
        "                     selectcolor='blue').place(x=0, y=0)",
    )
    term.wait_for_cell(0, 1, lambda cell: cell.data == "x" and cell.bg == "blue")
    term.wait_for_cell(0, 4, lambda cell: cell.data == "T" and cell.bg != "blue")


def test_a_disabled_entry_takes_its_disabled_colours(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "e = tkcurses.Entry(root, width=8, disabledbackground='blue',\n"
        "                   disabledforeground='red')\n"
        "e.insert(0, 'off')\n"
        "e.configure(state='disabled')\n"
        "e.place(x=0, y=0)",
    )
    term.wait_for_cell(
        1,
        1,
        lambda cell: cell.data == "o" and (cell.fg, cell.bg) == ("red", "blue"),
    )


def test_a_disabled_listbox_takes_disabledforeground(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "b = tkcurses.Listbox(root, height=2, width=8, disabledforeground='red')\n"
        "b.insert('end', 'row')\n"
        "b.configure(state='disabled')\n"
        "b.place(x=0, y=0)",
    )
    term.wait_for_cell(1, 2, lambda cell: cell.data == "r" and cell.fg == "red")


def test_a_spinboxs_arrows_are_drawn_on_buttonbackground(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "s = tkcurses.Spinbox(root, width=8, from_=0, to=9,\n"
        "                     buttonbackground='magenta')\n"
        "s.place(x=0, y=0)",
    )
    for column in (9, 10):
        term.wait_for_cell(1, column, background("magenta"), message="an arrow")
    term.wait_for_cell(1, 1, lambda cell: cell.data == "0" and cell.bg != "magenta")


def test_a_scrollbars_trough_is_drawn_on_troughcolor(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "b = tkcurses.Scrollbar(root, orient='horizontal', troughcolor='cyan')\n"
        "b.place(x=0, y=0, width=12)\n"
        "b.set(0.0, 0.25)",
    )
    term.wait_for_cell(1, 9, lambda cell: cell.data == "░" and cell.bg == "cyan")
    # The thumb and the arrows keep the scrollbar's own.
    term.wait_for_cell(1, 2, lambda cell: cell.data == "█" and cell.bg != "cyan")
    term.wait_for_cell(1, 1, lambda cell: cell.data == "◄" and cell.bg != "cyan")


def test_an_active_scrollbar_part_is_drawn_on_activebackground(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "b = tkcurses.Scrollbar(root, orient='horizontal', activebackground='red')\n"
        "b.place(x=0, y=0, width=12)\n"
        "b.set(0.0, 0.25)\n"
        "b.activate('arrow2')",
    )
    term.wait_for_cell(1, 10, lambda cell: cell.data == "►" and cell.bg == "red")
    term.wait_for_cell(1, 1, lambda cell: cell.data == "◄" and cell.bg != "red")


def test_a_scales_trough_is_drawn_on_troughcolor(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "tkcurses.Scale(root, orient='horizontal', length=10, showvalue=False,\n"
        "               troughcolor='green').place(x=0, y=0)",
    )
    term.wait_for_cell(0, 4, lambda cell: cell.data == "░" and cell.bg == "green")
    term.wait_for_cell(0, 1, lambda cell: cell.data == "█" and cell.bg != "green")


def test_a_menu_draws_its_active_disabled_and_chosen_colours(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "v = tkcurses.IntVar(value=1)\n"
        "m = tkcurses.Menu(root, activebackground='red', activeforeground='cyan',\n"
        "                  disabledforeground='blue', selectcolor='green')\n"
        "m.add_command(label='Open')\n"
        "m.add_checkbutton(label='Wrap', variable=v)\n"
        "m.add_command(label='Gone', state='disabled')\n"
        "m.post(2, 1)\n"
        "m.activate(0)",
    )
    term.wait_for_cell(
        2,
        8,
        lambda cell: cell.data == "O" and (cell.fg, cell.bg) == ("cyan", "red"),
        message="the active entry",
    )
    term.wait_for_cell(3, 5, lambda cell: cell.data == "x" and cell.fg == "green")
    term.wait_for_cell(3, 8, lambda cell: cell.data == "W" and cell.fg != "green")
    term.wait_for_cell(4, 8, lambda cell: cell.data == "G" and cell.fg == "blue")


def test_uncoloured_states_look_as_they_did(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "tkcurses.Button(root, text='Go', state='active').place(x=0, y=0)",
    )
    term.wait_for_cell(1, 3, lambda cell: cell.data == "G" and cell.reverse)


def test_a_menu_entrys_own_colours_win_over_the_menus(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "v = tkcurses.IntVar(value=1)\n"
        "m = tkcurses.Menu(root, activebackground='red', selectcolor='green')\n"
        "m.add_command(label='Open', activebackground='blue')\n"
        "m.add_checkbutton(label='Wrap', variable=v, selectcolor='magenta')\n"
        "m.add_command(label='Save', background='cyan')\n"
        "m.add_separator(background='cyan')\n"
        "m.post(2, 1)\n"
        "m.activate(0)",
    )
    term.wait_for_cell(
        2, 8, lambda cell: cell.data == "O" and cell.bg == "blue", message="active"
    )
    term.wait_for_cell(3, 5, lambda cell: cell.data == "x" and cell.fg == "magenta")
    term.wait_for_cell(4, 8, lambda cell: cell.data == "S" and cell.bg == "cyan")
    term.wait_for_cell(5, 8, lambda cell: cell.data == "─" and cell.bg == "cyan")


def test_a_listbox_item_is_drawn_in_its_own_colours(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "b = tkcurses.Listbox(root, height=4, width=10, selectbackground='blue')\n"
        "b.insert('end', 'plain', 'red', 'chosen', 'mine')\n"
        "b.itemconfigure(1, background='red')\n"
        "b.itemconfigure(3, selectbackground='green')\n"
        "b.selection_set(2)\n"
        "b.selection_set(3)\n"
        "b.place(x=0, y=0)",
    )
    term.wait_for_cell(2, 2, lambda cell: cell.data == "r" and cell.bg == "red")
    term.wait_for_cell(1, 2, lambda cell: cell.data == "p" and cell.bg != "red")
    term.wait_for_cell(3, 2, lambda cell: cell.data == "c" and cell.bg == "blue")
    term.wait_for_cell(4, 2, lambda cell: cell.data == "m" and cell.bg == "green")
