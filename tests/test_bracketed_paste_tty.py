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

"""Bracketed paste against a real terminal: the mode asked for and given
back, a marked paste read as one piece, and a suspend that hands both the
paste and the mouse motion modes back to the shell. TkCurses-tcbj.22.
"""

from __future__ import annotations

import shlex
import shutil
import sys

import pytest

pytestmark = pytest.mark.tty

ON = b"\x1b[?2004h"
OFF = b"\x1b[?2004l"

PROGRAM = """
import os, signal
import tkcurses as tk
root = tk.Tk()
text = tk.Text(root, width=30, height=3)
text.pack()
text.focus_set()
shown = tk.Label(root, text="ready")
shown.pack()
def report(event):
    shown["text"] = "got=%r" % text.get("1.0", "end-1c")
    return "break"
def suspend(event):
    os.kill(os.getpid(), signal.SIGTSTP)
    root.after(200, lambda: shown.configure(text="back"))
    return "break"
text.bind("<F5>", report)
text.bind("<F6>", suspend)
text.bind("<F7>", lambda e: root.quit())
root.after(15000, root.quit)
root.mainloop()
root.destroy()
"""


def start(terminal, tmp_path, **env):
    term = terminal(cols=50, rows=8, env=env)
    term.run_source(PROGRAM, workdir=tmp_path)
    term.wait_for_text("ready")
    return term


def test_a_marked_paste_arrives_as_its_text(terminal, tmp_path):
    term = start(terminal, tmp_path)
    # After ncurses has set the screen up, and asked once: ncurses never
    # turns this mode off, unlike the mouse's, so it needs no second asking.
    assert term.received.rindex(ON) > term.received.index(b"\x1b[?1049h")
    term.send(b"\x1b[200~one\rtwo\x1b[201~")
    term.send_keys("<F5>")
    term.wait_for_text("got='one\\ntwo'")


def test_the_mode_is_given_back_on_the_way_out(terminal, tmp_path):
    term = start(terminal, tmp_path)
    term.send_keys("<F7>")
    assert term.wait_for_exit() == 0
    assert term.received.rindex(OFF) > term.received.rindex(ON)


def test_the_setting_turns_it_off(terminal, tmp_path):
    term = start(terminal, tmp_path, TKCURSES_INPUT_BRACKETED_PASTE="0")
    term.send_keys("<F7>")
    assert term.wait_for_exit() == 0
    assert ON not in term.received
    assert OFF not in term.received


def test_a_suspend_gives_the_modes_back_and_resuming_takes_them_again(
    terminal, tmp_path
):
    """The program signals itself: a pty's own Control-Z reaches no one, as
    the harness's child is in an orphaned process group. For the same
    reason the stop itself is discarded, so the program comes straight
    back, which is what lets the resume be seen."""
    term = start(terminal, tmp_path)
    before = len(term.received)
    term.send_keys("<F6>")
    term.wait_for_text("back")
    sent = term.received[before:]
    leave = sent.index(b"\x1b[?1049l")  # curses leaving the screen
    assert sent.index(b"\x1b[?1002l") < leave
    assert sent.index(OFF) < leave
    assert sent.index(b"\x1b[?1002h") > leave
    assert sent.index(ON) > sent.index(b"\x1b[?1049h")
    # And it still reads pastes.
    term.send(b"\x1b[200~after\x1b[201~")
    term.send_keys("<F5>")
    term.wait_for_text("got='after'")


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_control_z_under_a_shell_stops_and_fg_brings_it_back(terminal, tmp_path):
    """A real suspend, from the key, under a shell with job control - the
    one place the stop is not discarded."""
    program = tmp_path / "app.py"
    program.write_text(PROGRAM)
    term = terminal(cols=60, rows=10)
    term.run(["bash", "-c", "exec bash --norc --noprofile -i 2>&1"])
    term.wait_for_text("$")
    command = f"{shlex.quote(sys.executable)} {shlex.quote(str(program))}"
    term.send(f"{command}\r".encode())
    term.wait_for_text("ready")
    before = len(term.received)
    term.send(b"\x1a")
    term.wait_for_text("Stopped")
    handed_back = term.received[before:]
    assert b"\x1b[?1002l" in handed_back
    assert OFF in handed_back
    before = len(term.received)
    term.send(b"fg\r")
    # Not "ready", which never left this emulator's screen: the modes, which
    # the program sends last on its way back, once the tty is its own again.
    term.wait_for(lambda t: ON in t.received[before:])
    term.send(b"\x1b[200~after\x1b[201~")
    term.send_keys("<F5>")
    term.wait_for_text("got='after'")
    taken_again = term.received[before:]
    assert b"\x1b[?1002h" in taken_again
    assert ON in taken_again


FALLBACK = """
import tkcurses as tk
root = tk.Tk()
keys = []
shown = tk.Label(root, text="ready")
shown.pack()
button = tk.Button(root, text="OK", command=lambda: keys.append("INVOKED"))
button.pack()
button.focus_set()
button.bind("<Key>", lambda e: keys.append(e.keysym))
button.bind("<Return>", lambda e: keys.append("RETURN"))
button.bind("<F5>", lambda e: shown.configure(text="keys=[" + ",".join(keys) + "]"))
root.after(15000, root.quit)
root.mainloop()
"""


def test_a_widget_that_takes_no_paste_gets_its_keys_without_controls(
    terminal, tmp_path
):
    """A focused button bound to Return, as a dialog's default is: the line
    break in a paste must not press it, nor the Escape close anything."""
    term = terminal(cols=50, rows=8)
    term.run_source(FALLBACK, workdir=tmp_path)
    term.wait_for_text("ready")
    term.send(b"\x1b[200~a\rb\x1b\tc\x1b[201~")
    term.send_keys("<F5>")
    term.wait_for_text("keys=[a,b,c]")


def test_a_paste_goes_to_the_focus_as_one_edit_in_an_entry(terminal, tmp_path):
    source = PROGRAM.replace(
        "text = tk.Text(root, width=30, height=3)", "text = tk.Entry(root, width=30)"
    ).replace('text.get("1.0", "end-1c")', "text.get()")
    term = terminal(cols=50, rows=8)
    term.run_source(source, workdir=tmp_path)
    term.wait_for_text("ready")
    term.send(b"\x1b[200~one\rtwo\x1b[201~")
    term.send_keys("<F5>")
    term.wait_for_text("got='one two'")
