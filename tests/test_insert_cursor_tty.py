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

"""What Tk's insertion-cursor options send to a real terminal, and that the
person's own cursor comes back at exit. TkCurses-gm66.2.

Read from the bytes the program writes, ``term.received``: the emulator under
the harness keeps no cursor shape or colour to look at.
"""

from __future__ import annotations

import re

import pytest

pytestmark = pytest.mark.tty

#: DECSCUSR, ``ESC [ n SP q``: any cursor-shape request at all.
SHAPE = re.compile(rb"\x1b\[(\d) q")


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
{body}
root.after(1500, root.quit)
root.mainloop()
root.destroy()
"""


def test_a_block_cursor_is_asked_for_and_given_back(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "t = tkcurses.Text(root, width=20, height=3, blockcursor=True,\n"
            "                  insertbackground='#ff8000')\n"
            "t.place(x=1, y=1)\n"
            "t.focus_set()"
        ),
        workdir=tmp_path,
    )
    assert term.wait_for_exit(timeout=10) == 0
    out = term.received
    assert [m.group(1) for m in SHAPE.finditer(out)] == [b"1", b"0"], out
    asked = out.index(b"\x1b]12;#ff8000\x07")
    assert out.index(b"\x1b]112\x07") > asked, "the colour is given back at exit"


def test_tks_defaults_leave_the_cursor_alone(terminal, tmp_path):
    """The person's own cursor, untouched - the author's choice in UAT 43."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("e = tkcurses.Entry(root, width=10)\ne.place(x=1, y=1)\ne.focus_set()"),
        workdir=tmp_path,
    )
    assert term.wait_for_exit(timeout=10) == 0
    assert not SHAPE.search(term.received)
    assert b"\x1b]12;" not in term.received
    assert b"\x1b]112" not in term.received


def test_the_focus_leaving_gives_the_cursor_back(terminal, tmp_path):
    """A steady bar on one entry, the terminal's own on the next."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "a = tkcurses.Entry(root, width=10, insertofftime=0)\n"
            "a.place(x=1, y=1)\n"
            "b = tkcurses.Entry(root, width=10)\n"
            "b.place(x=1, y=4)\n"
            "a.focus_set()\n"
            "root.after(500, b.focus_set)"
        ),
        workdir=tmp_path,
    )
    assert term.wait_for_exit(timeout=10) == 0
    assert [m.group(1) for m in SHAPE.finditer(term.received)] == [b"6", b"0"]
