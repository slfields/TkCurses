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

"""Auto-repeat on a real terminal: a mouse button held down. TkCurses-gm66.6.

The terminal reports a press and, much later, a release, with nothing
between them; everything that repeats is the application's own timer.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
{body}
root.after(4000, root.quit)
root.mainloop()
root.destroy()
"""


def at_least(row, start, width, smallest):
    """A predicate: the number in ``width`` cells of ``row`` is ``smallest`` or
    more. Read whole, so a busy machine that samples past one value still
    sees a larger one."""

    def check(term):
        text = term.display[row][start : start + width].strip()
        return text.isdigit() and int(text) >= smallest

    return check


def find(term, glyph):
    row = next(i for i, line in enumerate(term.display) if glyph in line)
    return term.display[row].index(glyph), row


def test_holding_a_spinbox_arrow_counts_up(terminal, tmp_path):
    term = terminal(cols=30, rows=6)
    term.run_source(
        program(
            "tkcurses.Spinbox(root, from_=0, to=99, width=10, relief='flat',\n"
            "                 repeatdelay=200, repeatinterval=50).place(x=0, y=0)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("▲")
    column, row = find(term, "▲")
    term.send_mouse(column, row, action="press")
    # Past the delay and several intervals: well beyond one step.
    term.wait_for(at_least(row, 0, 8, 5), message="the arrow held")
    term.send_mouse(column, row, action="release")


def test_holding_a_scales_trough_steps_it_along(terminal, tmp_path):
    term = terminal(cols=40, rows=6)
    term.run_source(
        program(
            "v = tkcurses.IntVar(root, 0)\n"
            "tkcurses.Scale(root, orient='horizontal', from_=0, to=10,\n"
            "               length=20, variable=v, showvalue=False,\n"
            "               highlightthickness=0, repeatdelay=200,\n"
            "               repeatinterval=50).place(x=0, y=0)\n"
            "tkcurses.Label(root, textvariable=v, width=4).place(x=0, y=3)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("█░")
    column, row = find(term, "█")
    term.send_mouse(column + 15, row, action="press")
    term.wait_for(at_least(3, 0, 4, 5), message="the trough held")
    term.send_mouse(column + 15, row, action="release")


def test_holding_a_repeating_button_invokes_it_again(terminal, tmp_path):
    term = terminal(cols=40, rows=6)
    term.run_source(
        program(
            "n = tkcurses.IntVar(root, 0)\n"
            "tkcurses.Button(root, text='More', repeatdelay=200, repeatinterval=50,\n"
            "                command=lambda: n.set(n.get() + 1)).place(x=0, y=0)\n"
            "tkcurses.Label(root, textvariable=n, width=4).place(x=0, y=4)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("More")
    column, row = find(term, "More")
    term.send_mouse(column, row, action="press")
    term.wait_for(at_least(4, 0, 4, 5), message="the button held")
    term.send_mouse(column, row, action="release")
