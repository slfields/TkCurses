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

"""The prompt dialogs against a real terminal.

The one that matters is what a **bad value** does: the dialog has to stay up
with the focus back in the field, having returned nothing. A prompt that
accepted nonsense and handed it back would be worse than one that never
appeared, because the caller cannot tell a refusal from an answer.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

PROGRAM = """
import tkcurses
from tkcurses import simpledialog

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
buffer.write(0, 0, "ready")
root.tk.screen.refresh()


def ask(event):
    buffer.write(1, 0, "answer=%r            " % (simpledialog.{call},))
    root.tk.screen.refresh()


root.bind("<Key-a>", ask)
root.after(10000, root.quit)
root.mainloop()
"""


def prompt(term, tmp_path, call, wait_for="Count"):
    term.run_source(PROGRAM.format(call=call), workdir=tmp_path)
    term.wait_for_text("ready")
    term.send(b"a")
    term.wait_for_text(wait_for)


INTEGER = 'askinteger("Spam", "Count", parent=root, minvalue=1, maxvalue=10)'


# ----------------------------------------------------------- the answers


def test_a_typed_value_comes_back(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    prompt(term, tmp_path, 'askstring("Spam", "Label", parent=root)', "Label")
    term.send(b"hello")
    term.send(b"\r")
    term.wait_for_text("answer='hello'")


def test_cancelling_gives_none_rather_than_the_empty_string(terminal, tmp_path):
    """Which is why askstring cannot simply return what was typed: a person
    who cancelled and a person who typed nothing meant different things."""
    term = terminal(cols=60, rows=16)
    prompt(term, tmp_path, 'askstring("Spam", "Label", parent=root)', "Label")
    term.send_keys("<Escape>")
    term.wait_for_text("answer=None")


def test_askinteger_returns_a_number_not_the_text(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    prompt(term, tmp_path, INTEGER)
    term.send(b"7")
    term.send(b"\r")
    term.wait_for_text("answer=7")


def test_askfloat_returns_a_float(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    prompt(term, tmp_path, 'askfloat("Spam", "Weight", parent=root)', "Weight")
    term.send(b"2.5")
    term.send(b"\r")
    term.wait_for_text("answer=2.5")


def test_an_initial_value_is_there_to_start_with(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    prompt(
        term,
        tmp_path,
        'askinteger("Spam", "Count", parent=root, initialvalue=144)',
    )
    assert term.contains("144")
    term.send(b"\r")
    term.wait_for_text("answer=144")


# -------------------------------------------------------------- refusing


def test_a_value_that_will_not_read_keeps_the_dialog_up(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    prompt(term, tmp_path, INTEGER)
    term.send(b"abc")
    term.send(b"\r")
    term.wait_for_text("Not an integer.")
    assert not term.contains("answer="), (
        f"a bad value was handed to the caller:\n{term.describe()}"
    )
    # Dismiss the warning and the prompt is still there, waiting.
    term.send(b"\r")
    term.wait_for(lambda t: t.contains("Count"), message="the prompt, still up")


def test_a_value_below_the_minimum_says_so(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    prompt(term, tmp_path, INTEGER)
    term.send(b"0")
    term.send(b"\r")
    term.wait_for_text("minimum value is 1")
    assert not term.contains("answer=")


def test_a_value_above_the_maximum_says_so(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    prompt(term, tmp_path, INTEGER)
    term.send(b"99")
    term.send(b"\r")
    term.wait_for_text("maximum value is 10")
    assert not term.contains("answer=")


def test_a_refused_value_can_be_corrected_and_accepted(terminal, tmp_path):
    """The whole point of staying up: the person fixes it and carries on."""
    term = terminal(cols=60, rows=16)
    prompt(term, tmp_path, INTEGER)
    term.send(b"abc")
    term.send(b"\r")
    term.wait_for_text("Not an integer.")
    term.send(b"\r")
    term.wait_for(lambda t: t.contains("Count"), message="the prompt again")
    for _ in range(4):
        term.send_keys("<BackSpace>")
    term.send(b"7")
    term.send(b"\r")
    term.wait_for_text("answer=7")


# ----------------------------------------------------------- SimpleDialog


SIMPLE = """
import tkcurses
from tkcurses.simpledialog import SimpleDialog

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
buffer.write(0, 0, "ready")
root.tk.screen.refresh()


def ask(event):
    dialog = SimpleDialog(
        root,
        text="Would this have been an actual dialog?",
        buttons=["Yes", "No", "Cancel"],
        default={default},
        cancel={cancel},
        title="Test Dialog",
    )
    buffer.write(1, 0, "num=%r        " % (dialog.go(),))
    root.tk.screen.refresh()


root.bind("<Key-a>", ask)
root.after(8000, root.quit)
root.mainloop()
"""


def simple(term, tmp_path, default=0, cancel=2):
    term.run_source(SIMPLE.format(default=default, cancel=cancel), workdir=tmp_path)
    term.wait_for_text("ready")
    term.send(b"a")
    term.wait_for_text("actual dialog")


def test_go_returns_the_index_of_the_button_pressed(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    simple(term, tmp_path)
    row = next(i for i, line in enumerate(term.display) if "No" in line)
    term.click(term.display[row].index("No") + 1, row)
    term.wait_for_text("num=1")


def test_return_presses_the_default_button(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    simple(term, tmp_path, default=1)
    term.send(b"\r")
    term.wait_for_text("num=1")


def test_dismissing_answers_with_the_cancel_index(terminal, tmp_path):
    """Its own option, separate from the default: the button Return presses
    and the answer a dismissal gives need not be the same one."""
    term = terminal(cols=60, rows=16)
    simple(term, tmp_path, default=0, cancel=2)
    term.send_keys("<Escape>")
    term.wait_for_text("num=2")
