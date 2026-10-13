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


"""The system clipboard, end to end: the startup question, and a copy leaving.

The harness answers the terminal's half - "do you have OSC 52?" - as kitty
would (osc52=True) or as the author's VTE terminal was measured to (False).
The desktop is taken away (no WAYLAND_DISPLAY or DISPLAY), so nothing here can
reach the developer's real clipboard. TkCurses-hpr.
"""

from __future__ import annotations

import base64

import pytest

pytestmark = pytest.mark.tty

#: Copies "hello" once the loop is running, says so, and leaves.
COPIES = """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer


def copy():
    root.clipboard_clear()
    root.clipboard_append("hello")
    buffer.write(0, 0, "copied")
    root.tk.screen.refresh()
    root.after(200, root.quit)


root.after(100, copy)
root.mainloop()
root.destroy()
"""

NO_DESKTOP = {"WAYLAND_DISPLAY": "", "DISPLAY": "", "SSH_CONNECTION": ""}
OSC52_HELLO = b"\x1b]52;c;" + base64.b64encode(b"hello") + b"\x07"


def test_a_terminal_with_osc52_is_asked_and_gets_the_copy(terminal, tmp_path):
    term = terminal(
        cols=30,
        rows=6,
        osc52=True,
        env={**NO_DESKTOP, "TKCURSES_CLIPBOARD_SYSTEM": "auto"},
    )
    term.run_source(COPIES, workdir=tmp_path)
    term.wait_for(lambda t: OSC52_HELLO in t.received, message="OSC 52 'hello'")
    assert term.wait_for_exit(timeout=10) == 0
    assert b"\x1bP+q4d73\x1b\\" in term.received, "the terminal was asked first"
    assert "stayed inside" not in term.stderr


def test_a_terminal_without_it_is_not_sent_it_and_the_person_is_told(
    terminal, tmp_path
):
    """VTE's case, as measured, on a machine with no clipboard tool: the copy
    stays inside, and the notice says why once the screen is given back."""
    term = terminal(
        cols=30,
        rows=6,
        osc52=False,
        env={**NO_DESKTOP, "TKCURSES_CLIPBOARD_SYSTEM": "auto"},
    )
    term.run_source(COPIES, workdir=tmp_path)
    term.wait_for_text("copied")
    assert term.wait_for_exit(timeout=10) == 0
    assert b"\x1b]52;" not in term.received
    assert "stayed inside this program" in term.stderr
    assert "no OSC 52" in term.stderr


def test_off_asks_the_terminal_nothing_and_says_nothing(terminal, tmp_path):
    term = terminal(cols=30, rows=6, osc52=True, env={**NO_DESKTOP})
    term.run_source(COPIES, workdir=tmp_path)
    term.wait_for_text("copied")
    assert term.wait_for_exit(timeout=10) == 0
    assert b"\x1bP+q" not in term.received
    assert b"\x1b]52;" not in term.received
    assert "stayed inside" not in term.stderr
