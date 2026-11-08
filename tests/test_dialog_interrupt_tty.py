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

"""Ctrl-C in a dialog shown before mainloop cancels it, as Escape does.

It printed a KeyboardInterrupt traceback from the input wait: mainloop
takes Ctrl-C, and a dialog called at the top level of a program waits in
``wait_window`` before there is any mainloop.
"""

from __future__ import annotations

import re

import pytest

pytestmark = pytest.mark.tty

PROGRAM = """
import tkcurses as tk
from tkcurses import colorchooser, dialog, filedialog, messagebox, simpledialog

root = tk.Tk()
result = {call}
root.destroy()
print("result=%r;" % (result,))
"""

#: Each dialog the fault was measured in, and text it shows once it is up.
DIALOGS = {
    "messagebox": ('messagebox.askyesno("Q", "Proceed now?")', "Proceed now?"),
    "simpledialog": ('simpledialog.askinteger("Q", "How many?")', "How many?"),
    "filedialog": ('filedialog.askopenfilename(title="Open it")', "Open it"),
    "colorchooser": ('colorchooser.askcolor(title="Colour it")', "Colour it"),
    "dialog": (
        "dialog.Dialog(None, {'title': 'D', 'text': 'Choose one', 'bitmap': '',"
        " 'default': 0, 'strings': ('One', 'Two')}).num",
        "Choose one",
    ),
}


def _answer(terminal, tmp_path, call, shown, key):
    term = terminal(cols=60, rows=20)
    term.run_source(PROGRAM.format(call=call), workdir=tmp_path)
    term.wait_for_text(shown)
    term.send(key)
    term.wait_for_text(";")
    assert term.wait_for_exit(timeout=10) == 0, term.describe()
    assert "Traceback" not in term.stderr, term.stderr
    # Up to the marker: the dialog's border can still be on the row.
    found = re.search(r"result=(.*?);", "\n".join(term.display))
    assert found, term.describe()
    return found.group(1)


@pytest.mark.parametrize("name", sorted(DIALOGS))
def test_ctrl_c_in_a_dialog_before_mainloop_cancels_it_as_escape_does(
    terminal, tmp_path, name
):
    call, shown = DIALOGS[name]
    escaped = _answer(terminal, tmp_path / "escape", call, shown, b"\x1b")
    interrupted = _answer(terminal, tmp_path / "ctrl-c", call, shown, b"\x03")
    assert interrupted == escaped


# Inside mainloop. Ctrl-C was the close gesture there, so in a dialog it
# destroyed the application and the dialog answered as if refused. The
# decision, 2026-11-08: it cancels the dialog as Escape does, and a second
# one reaches the main window (TkCurses-28wi).

IN_MAINLOOP = """
import tkcurses as tk
from tkcurses import colorchooser, dialog, filedialog, messagebox, simpledialog

root = tk.Tk()
tk.Label(root, text="main window").pack()

def ask():
    result = {call}
    tk.Label(root, text="result=%r;" % (result,)).pack()
    tk.Label(root, text="still running").pack()

root.after(100, ask)
root.mainloop()
print("closed")
"""


def _answer_in_mainloop(terminal, tmp_path, call, shown, key):
    term = terminal(cols=60, rows=20)
    term.run_source(IN_MAINLOOP.format(call=call), workdir=tmp_path)
    term.wait_for_text(shown)
    term.send(key)
    term.wait_for(
        lambda t: (
            any("still running" in line for line in t.display)
            and any("result=" in line for line in t.display)
        ),
        message="the dialog's answer, with the application still running",
    )
    found = re.search(r"result=(.*?);", "\n".join(term.display))
    assert found, term.describe()
    # A second Ctrl-C reaches the main window and closes it.
    term.send(b"\x03")
    assert term.wait_for_exit(timeout=10) == 0, term.describe()
    assert "Traceback" not in term.stderr, term.stderr
    return found.group(1)


@pytest.mark.parametrize("name", sorted(DIALOGS))
def test_ctrl_c_in_a_dialog_inside_mainloop_cancels_it_as_escape_does(
    terminal, tmp_path, name
):
    call, shown = DIALOGS[name]
    escaped = _answer_in_mainloop(terminal, tmp_path / "escape", call, shown, b"\x1b")
    interrupted = _answer_in_mainloop(
        terminal, tmp_path / "ctrl-c", call, shown, b"\x03"
    )
    assert interrupted == escaped


MODAL_WITHOUT_ESCAPE = """
import tkcurses as tk

root = tk.Tk()
tk.Label(root, text="main window").pack()

def ask():
    top = tk.Toplevel(root)
    tk.Label(top, text="a modal window").pack()
    top.grab_set()
    top.focus_set()
    root.wait_window(top)
    tk.Label(root, text="modal closed;").pack()

root.after(100, ask)
root.mainloop()
"""


def test_ctrl_c_closes_a_modal_window_that_has_no_escape_binding(terminal, tmp_path):
    """Escape does nothing there, so Ctrl-C closes the window instead."""
    term = terminal(cols=60, rows=20)
    term.run_source(MODAL_WITHOUT_ESCAPE, workdir=tmp_path)
    term.wait_for_text("a modal window")
    term.send(b"\x03")
    term.wait_for_text("modal closed;")
    term.send(b"\x03")
    assert term.wait_for_exit(timeout=10) == 0, term.describe()


SELECTED = """
import tkcurses as tk
from tkcurses import simpledialog

root = tk.Tk()

def ask():
    result = simpledialog.askstring("Q", "Your name?", initialvalue="Ada")
    tk.Label(root, text="result=%r;" % (result,)).pack()

root.after(100, ask)
root.mainloop()
"""


def test_ctrl_c_with_a_selection_in_a_dialog_copies_and_leaves_it_open(
    terminal, tmp_path
):
    term = terminal(cols=60, rows=20)
    term.run_source(SELECTED, workdir=tmp_path)
    term.wait_for_text("Your name?")
    term.wait_for_idle()
    term.send(b"\x03")
    term.wait_for_idle()
    assert any("Your name?" in line for line in term.display), term.describe()
    assert not any("result=" in line for line in term.display), term.describe()
    term.send(b"\x1b")
    term.wait_for_text("result=None;")
    term.send(b"\x03")
    assert term.wait_for_exit(timeout=10) == 0, term.describe()
