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

"""What a background image looks like on a real terminal."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

FULL = "█"


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
art = tkcurses.PhotoImage(master=root, width=2, height=2)
art.put('red', to=(0, 0, 2, 2))
{body}
root.after(5000, root.quit)
root.mainloop()
"""


FRAME = (
    "frame = tkcurses.Frame(root, width=10, height=5, relief='solid', bd=1,"
    " backgroundimage=art, tile=True)\n"
    "frame.place(x=2, y=1)\n"
)


def red(cell) -> bool:
    return cell.data == FULL and cell.fg == "red"


def test_a_tiled_image_fills_the_inside_of_the_border(terminal, tmp_path):
    term = terminal(cols=30, rows=10)
    term.run_source(program(FRAME), workdir=tmp_path)
    # The frame covers columns 2-11 and rows 1-5; inside its border, 3-10
    # and 2-4.
    inside = [(row, column) for row in range(2, 5) for column in range(3, 11)]
    border = [(1, column) for column in range(2, 12)]
    border += [(row, 2) for row in range(1, 6)]
    # One wait naming every cell asserted on: TkCurses-txk.
    term.wait_for(
        lambda t: (
            all(red(t.char_at(*cell)) for cell in inside)
            and t.char_at(1, 2).data == "┌"
        ),
        message="the inside tiled, and the border drawn",
    )
    assert not any(red(term.char_at(*cell)) for cell in border)


def test_a_child_is_drawn_over_it(terminal, tmp_path):
    term = terminal(cols=30, rows=10)
    term.run_source(
        program(FRAME + "tkcurses.Label(frame, text='hi', bd=0).place(x=1, y=1)\n"),
        workdir=tmp_path,
    )
    term.wait_for_cell(3, 4, lambda cell: cell.data == "h", message="the label")
    term.wait_for_cell(3, 6, red, message="the image beside it")
    term.wait_for_cell(3, 5, lambda cell: cell.data == "i")


def test_it_follows_its_image_and_goes_when_the_image_does(terminal, tmp_path):
    term = terminal(cols=30, rows=10)
    term.run_source(
        program(
            FRAME + "def blue():\n"
            "    art.put('blue', to=(0, 0, 2, 2))\n"
            "def gone():\n"
            "    global art\n"
            "    tkcurses.Label(root, text='gone').place(x=15, y=8)\n"
            "    del art\n"
            "root.after(300, blue)\n"
            "root.after(600, gone)\n"
        ),
        workdir=tmp_path,
    )
    term.wait_for_cell(3, 5, red, message="red first")
    term.wait_for_cell(3, 5, lambda cell: cell.fg == "blue", message="then blue")
    term.wait_for_text("gone")
    term.wait_for_cell(3, 5, lambda cell: cell.data == " ", message="then nothing")


def test_the_root_paints_it_behind_everything(terminal, tmp_path):
    term = terminal(cols=20, rows=6)
    term.run_source(
        program(
            "root.configure(backgroundimage=art, tile=True)\n"
            "tkcurses.Label(root, text='over', bd=0).place(x=0, y=0)\n"
        ),
        workdir=tmp_path,
    )
    term.wait_for_cell(5, 19, red, message="the far corner")
    term.wait_for_cell(0, 0, lambda cell: cell.data == "o", message="the label")
    term.wait_for_cell(0, 4, red, message="beside the label")
