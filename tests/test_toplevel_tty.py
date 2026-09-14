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

"""Tests for what a Toplevel puts on a real terminal."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def program(body: str) -> str:
    """A root with a toplevel, then the loop."""
    return f"""
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
{body}
root.after(4000, root.quit)
root.mainloop()
"""


def test_a_toplevel_draws_a_border(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("win = tkcurses.Toplevel(root, width=20, height=6)"),
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: any("┌" in line and "┐" in line for line in t.display),
        message="a bordered window",
    )


def test_a_borderless_toplevel_draws_none(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "win = tkcurses.Toplevel(root, width=20, height=6, borderwidth=0)\n"
            'buffer.write(0, 0, "no border")\n'
            "root.tk.screen.refresh()"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("no border")
    term.wait_for_idle()
    assert not any("┌" in line for line in term.display)


def test_the_border_sits_where_the_window_was_placed(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("win = tkcurses.Toplevel(root, width=20, height=6)"),
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: any("┌" in line for line in t.display), message="the border"
    )
    top = next(i for i, line in enumerate(term.display) if "┌" in line)
    # Centred on a 40x12 terminal: (12 - 6) // 2 == 3.
    assert top == 3
    assert term.display[top].index("┌") == (40 - 20) // 2


def test_a_toplevel_covers_what_is_behind_it(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            'buffer.write(5, 0, "' + "X" * 40 + '")\n'
            "root.tk.screen.refresh()\n"
            "win = tkcurses.Toplevel(root, width=20, height=6)"
        ),
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: any("┌" in line for line in t.display), message="the border"
    )
    term.wait_for_idle()
    # Row 5 crosses the window: the X's survive only outside it.
    assert term.display[5].count("X") < 40


def test_raising_a_toplevel_brings_it_in_front(terminal, tmp_path):
    term = terminal(cols=40, rows=14)
    term.run_source(
        program(
            "first = tkcurses.Toplevel(root, name='a', width=24, height=8)\n"
            "second = tkcurses.Toplevel(root, name='b', width=16, height=4)\n"
            "def raise_first():\n"
            "    first.tkraise()\n"
            '    buffer.write(0, 0, "raised")\n'
            "    root.tk.screen.refresh()\n"
            "root.after(150, raise_first)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("raised")
    term.wait_for_idle()
    # The smaller window is centred inside the larger one; once the larger is
    # raised, the smaller one's corners are covered.
    assert sum(line.count("┌") for line in term.display) == 1


def test_destroying_a_toplevel_uncovers_the_root(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "win = tkcurses.Toplevel(root, width=20, height=6)\n"
            "def close():\n"
            "    win.destroy()\n"
            '    buffer.write(0, 0, "closed")\n'
            "    root.tk.screen.refresh()\n"
            "root.after(150, close)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("closed")
    term.wait_for_idle()
    assert not any("┌" in line for line in term.display)


def test_a_key_reaches_a_binding_on_a_toplevel(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "win = tkcurses.Toplevel(root, width=24, height=6)\n"
            "def typed(event):\n"
            '    buffer.write(0, 0, "window got %s" % event.keysym)\n'
            "    root.tk.screen.refresh()\n"
            'win.bind("<Key-z>", typed)\n'
            "win.focus_set()\n"
            'buffer.write(11, 0, "ready")\n'
            "root.tk.screen.refresh()"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send(b"z")
    term.wait_for_text("window got z")
