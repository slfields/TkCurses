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

"""The classic dialog against a real terminal.

The rules under test are Tk's, read out of its own ``dialog.tcl`` rather than
remembered: Return presses whichever button has the focus, the focus starts
on ``default``, a negative default means no default at all, and a dialog
dismissed rather than answered gives -1.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

PROGRAM = """
import tkcurses
from tkcurses.dialog import Dialog, DIALOG_ICON

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
buffer.write(0, 0, "ready")
root.tk.screen.refresh()

OPTIONS = {{
    "title": " File Modified ",
    "text": 'Save "Python.h" before leaving?',
    "bitmap": DIALOG_ICON,
    "default": {default},
    "strings": ("Save File", "Discard", "Cancel"),
}}


def ask(event):
    buffer.write(1, 0, "num=%r        " % Dialog(root, OPTIONS).num)
    root.tk.screen.refresh()


root.bind("<Key-a>", ask)
root.after(8000, root.quit)
root.mainloop()
"""


def run(term, tmp_path, default=0):
    term.run_source(PROGRAM.format(default=default), workdir=tmp_path)
    term.wait_for_text("ready")
    term.send(b"a")
    term.wait_for_text("Save File")


def test_every_string_becomes_a_button_in_order(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    run(term, tmp_path)
    row = next(i for i, line in enumerate(term.display) if "Save File" in line)
    line = term.display[row]
    assert line.index("Save File") < line.index("Discard") < line.index("Cancel")


def test_the_message_is_shown(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    run(term, tmp_path)
    assert term.contains('Save "Python.h" before leaving?')


def test_pressing_a_button_answers_with_its_index(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    run(term, tmp_path)
    row = next(i for i, line in enumerate(term.display) if "Discard" in line)
    term.click(term.display[row].index("Discard"), row)
    term.wait_for_text("num=1")


def test_return_presses_the_default_button(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    run(term, tmp_path, default=2)
    term.send(b"\r")
    term.wait_for_text("num=2")


def test_return_follows_the_focus_between_buttons(terminal, tmp_path):
    """Tk rebinds Return as the focus moves rather than binding it once, so
    that the key always presses the button a person can see is selected."""
    term = terminal(cols=60, rows=14)
    run(term, tmp_path, default=0)
    term.send_keys("<Tab>")
    term.wait_for_idle()
    term.send(b"\r")
    term.wait_for_text("num=1")


def test_dismissing_the_dialog_answers_minus_one(terminal, tmp_path):
    """A terminal has no close button, so Escape is how a dialog is
    dismissed - and dismissal is what Tk's -1 means."""
    term = terminal(cols=60, rows=14)
    run(term, tmp_path)
    term.send_keys("<Escape>")
    term.wait_for_text("num=-1")


def test_without_a_default_return_does_nothing(terminal, tmp_path):
    """Tk binds Return only when default is zero or more, so a dialog that
    insists on a real choice can refuse to have one made by accident."""
    term = terminal(cols=60, rows=14)
    run(term, tmp_path, default='""')
    term.send(b"\r")
    term.wait_for_idle()
    assert not term.contains("num="), (
        f"Return answered a dialog with no default button:\n{term.describe()}"
    )
    term.send_keys("<Escape>")
    term.wait_for_text("num=-1")


def test_the_dialog_blocks_until_it_is_answered(terminal, tmp_path):
    """Constructing it shows it and waits, which is what makes num usable on
    the next line. The answer must not appear before a button is pressed."""
    term = terminal(cols=60, rows=14)
    run(term, tmp_path)
    term.wait_for_idle()
    assert not term.contains("num="), term.describe()
    term.send(b"\r")
    term.wait_for_text("num=0")
