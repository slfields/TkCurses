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

"""What a Text's embedded windows and images look like in a real terminal."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
text = tkcurses.Text(root, width=36, height=6)
text.insert("1.0", "Press  to go on.\\n" + "\\n".join(f"line {{n}}" for n in range(2, 12)))
said = tkcurses.Label(root, text="", borderwidth=0)
text.pack()
said.pack()
text.focus_set()
{body}
root.after(5000, root.quit)
root.mainloop()
"""


def row_of(term, text: str) -> int:
    """The first screen row showing ``text``, or -1."""
    return next((r for r, line in enumerate(term.display) if text in line), -1)


def below(term, text: str, offset: int) -> str:
    """The screen row ``offset`` rows under the first one showing ``text``."""
    row = row_of(term, text)
    return "" if row < 0 else term.display[row + offset]


BUTTON = (
    "button = tkcurses.Button(text, text='OK',"
    " command=lambda: said.configure(text='pressed'))\n"
    "text.window_create('1.6', window=button)\n"
)


def test_a_button_sits_in_its_line_and_is_clicked(terminal, tmp_path):
    """The line grows to the button's three rows, the text sits in the
    middle of them, the rest of the line follows the button, and a click
    reaches it."""
    term = terminal(cols=40, rows=12)
    term.run_source(program(BUTTON), workdir=tmp_path)
    term.wait_for(
        lambda t: (
            "┌──────┐" in below(t, "│Press │  OK  │ to go on.", -1)
            and "└──────┘" in below(t, "│Press │  OK  │ to go on.", 1)
            and "line 2" in below(t, "│Press │  OK  │ to go on.", 2)
        ),
        message="the button inside line 1, line 2 below it",
    )
    row = row_of(term, "│Press │  OK")
    term.click(term.display[row].index("OK"), row)
    term.wait_for_text("pressed")


def test_typing_after_it_and_deleting_it(terminal, tmp_path):
    """The cursor steps over the button as one index; deleting that index
    takes the button off the screen and the line back to one row."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            BUTTON + "text.mark_set('insert', '1.7')\n"
            "root.bind('<F4>', lambda e: text.delete('1.6'))\n"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: row_of(t, "│Press │  OK") >= 0, message="the button")
    term.send(b"X")
    term.wait_for(
        lambda t: row_of(t, "│Press │  OK  │X to go on.") >= 0,
        message="X after the button",
    )
    term.send_keys("<F4>")
    term.wait_for(
        lambda t: "line 2" in below(t, "│Press X to go on.", 1) and row_of(t, "OK") < 0,
        message="the button gone and the line one row again",
    )


def test_scrolling_moves_the_button_and_takes_it_away(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            BUTTON + "root.bind('<F2>', lambda e: text.see('end'))\n"
            "root.bind('<F3>', lambda e: text.see('1.0'))\n"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: row_of(t, "│Press │  OK") >= 0, message="the button")
    term.send_keys("<F2>")
    term.wait_for(
        lambda t: row_of(t, "line 11") >= 0 and row_of(t, "OK") < 0,
        message="line 11 at the bottom and the button gone",
    )
    term.send_keys("<F3>")
    term.wait_for(
        lambda t: "┌──────┐" in below(t, "│Press │  OK  │ to go on.", -1),
        message="the button back",
    )


def test_an_image_draws_in_its_cells(terminal, tmp_path):
    """Four pixels wide is four cells; four high is two rows, which the line
    grows to hold, and the text after it follows."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "dot = tkcurses.PhotoImage(width=4, height=4)\n"
            "dot.put('orange', to=(0, 0, 4, 4))\n"
            "text.image_create('2.4', image=dot)\n"
        ),
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: (
            "│    ████" in below(t, "│line████ 2", 1)
            and "line 3" in below(t, "│line████ 2", 2)
        ),
        message="the image in line 2, two rows tall",
    )
