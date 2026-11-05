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

"""A widget that shrinks leaves nothing behind in the cells it gave up.

GitHub #43 reported ghost text, and a background colour left behind, where a
widget had been before it shrank - curses resizes a window without repainting
what the old one covered. ``BaseWidget._sync_window`` replaces the window on
any change of size for exactly that reason, and ARCHITECTURE.md's "Widget
Window Lifecycle" describes it. Nothing asserted it until these tests,
``TkCurses-016p``.

Each shrink is a key the test presses once the wide version is on screen,
not a timer: a timer can land before the first sample, and the wait for the
wide state then never succeeds (``TkCurses-cvi``). Each test then waits for
the whole final state it asserts on rather than for one cell of it.
"""

from __future__ import annotations

import pytest

from tests.test_frame_tty import program

pytestmark = pytest.mark.tty

COLS = 40


def blank(row: str) -> bool:
    return not row.strip()


def test_a_label_whose_text_shortens_leaves_no_old_text(terminal, tmp_path):
    term = terminal(cols=COLS, rows=8)
    term.run_source(
        program(
            "label = tkcurses.Label(root, text='Hello World long text')\n"
            "label.pack(anchor='nw')\n"
            "root.bind('<Key-s>', lambda e: label.configure(text='Hi'))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("Hello World long text")
    term.send(b"s")
    term.wait_for(
        lambda t: t.display[0] == "Hi".ljust(COLS),
        message="the label shortened to Hi, and nothing after it",
    )
    assert term.display[0] == "Hi".ljust(COLS)


def test_a_frame_placed_smaller_leaves_no_old_border(terminal, tmp_path):
    term = terminal(cols=COLS, rows=10)
    term.run_source(
        program(
            "frame = tkcurses.Frame(root, relief='solid', width=30, height=6)\n"
            "frame.place(x=1, y=1)\n"
            "root.bind('<Key-s>', lambda e: frame.place(x=1, y=1, width=8, height=3))"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: t.display[1][30] == "┐", message="the wide frame")
    term.send(b"s")
    expected = {
        1: " ┌──────┐".ljust(COLS),
        2: " │      │".ljust(COLS),
        3: " └──────┘".ljust(COLS),
    }

    def shrunk(t):
        rows = t.display
        return all(rows[r] == line for r, line in expected.items()) and all(
            blank(rows[r]) for r in range(4, 8)
        )

    term.wait_for(shrunk, message="only the small frame, and blank below it")
    for row, line in expected.items():
        assert term.display[row] == line
    for row in range(4, 8):
        assert blank(term.display[row]), f"row {row}: {term.display[row]!r}"


def test_a_shrinking_widget_gives_back_its_masters_background(terminal, tmp_path):
    """The colour half of #43: a red label inside a blue frame, cut from a
    long caption to "Ok", must leave blue where the red was."""
    term = terminal(cols=COLS, rows=8)
    term.run_source(
        program(
            "outer = tkcurses.Frame(root, bg='blue', width=36, height=6)\n"
            "outer.place(x=0, y=0)\n"
            "label = tkcurses.Label(outer, text='A much longer caption', bg='red')\n"
            "label.place(x=1, y=1)\n"
            "root.bind('<Key-s>', lambda e: label.configure(text='Ok'))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("A much longer caption")
    term.send(b"s")
    vacated = range(3, 1 + len("A much longer caption"))

    def shrunk(t):
        return (
            t.display[1][1:3] == "Ok"
            and all(t.display[1][c] == " " for c in vacated)
            and all(t.attrs_at(1, c)["bg"] == "blue" for c in vacated)
            and all(t.attrs_at(1, c)["bg"] == "red" for c in (1, 2))
        )

    term.wait_for(shrunk, message="Ok on red, and blue where the caption was")
    assert term.display[1][1:3] == "Ok"
    for col in vacated:
        assert term.display[1][col] == " ", f"column {col}"
        assert term.attrs_at(1, col)["bg"] == "blue", f"column {col}"
