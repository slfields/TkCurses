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

"""What each message box function actually hands back.

The eight functions do not agree on a return type, and that is tkinter's
design rather than an oversight: three give a string, four a boolean, one a
boolean or None. Code is written as ``if askyesno(...)``, so a function that
returned ``"no"`` where it promised False would be true and the application
would do the opposite of what it was told. Each contract is pinned here
through a real terminal, answered the way a person would answer it.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

PROGRAM = """
import tkcurses
from tkcurses import messagebox

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
buffer.write(0, 0, "ready")
root.tk.screen.refresh()


def run(event):
    answer = messagebox.{call}
    buffer.write(1, 0, "answer=%r          " % (answer,))
    root.tk.screen.refresh()


root.bind("<Key-a>", run)
root.after(8000, root.quit)
root.mainloop()
"""


def ask(term, tmp_path, call, wait_for="?"):
    term.run_source(PROGRAM.format(call=call), workdir=tmp_path)
    term.wait_for_text("ready")
    term.send(b"a")
    term.wait_for_text(wait_for)


def press(term, label):
    """Click the button with this label."""
    row = next(i for i, line in enumerate(term.display) if label in line)
    term.click(term.display[row].index(label) + 1, row)


# ------------------------------------------------------ the string answers


def test_showinfo_returns_the_string_ok(terminal, tmp_path):
    """Not True. Three of the eight give a string, and this is one."""
    term = terminal(cols=60, rows=14)
    ask(term, tmp_path, 'showinfo("Done", "All finished")', "All finished")
    term.send(b"\r")
    term.wait_for_text("answer='ok'")


def test_showerror_returns_ok_too(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    ask(term, tmp_path, 'showerror("Oh dear", "It broke")', "It broke")
    term.send(b"\r")
    term.wait_for_text("answer='ok'")


def test_askquestion_returns_the_name_of_the_button(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    ask(term, tmp_path, 'askquestion("Q", "Carry on?")', "Carry on?")
    press(term, "No")
    term.wait_for_text("answer='no'")


# ----------------------------------------------------- the boolean answers


def test_askyesno_is_true_for_yes(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    ask(term, tmp_path, 'askyesno("Q", "Really?")', "Really?")
    term.send(b"\r")  # Yes is the default
    term.wait_for_text("answer=True")


def test_askyesno_is_false_for_no(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    ask(term, tmp_path, 'askyesno("Q", "Really?")', "Really?")
    press(term, "No")
    term.wait_for_text("answer=False")


def test_askokcancel_is_true_for_ok(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    ask(term, tmp_path, 'askokcancel("Q", "Proceed?")', "Proceed?")
    term.send(b"\r")
    term.wait_for_text("answer=True")


def test_askretrycancel_is_true_for_retry(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    ask(term, tmp_path, 'askretrycancel("Q", "Again?")', "Again?")
    term.send(b"\r")
    term.wait_for_text("answer=True")


def test_askyesnocancel_has_three_answers(terminal, tmp_path):
    """True, False and None, which is why it cannot be a plain boolean."""
    term = terminal(cols=60, rows=14)
    ask(term, tmp_path, 'askyesnocancel("Q", "Save?")', "Save?")
    press(term, "No")
    term.wait_for_text("answer=False")


# ----------------------------------------------------------- the dismissal


def test_dismissing_a_yesno_box_answers_no(terminal, tmp_path):
    """Tk's rule: each type names the answer a dismissal stands for, and for
    yesno that is 'no'. So askyesno is False rather than something else."""
    term = terminal(cols=60, rows=14)
    ask(term, tmp_path, 'askyesno("Q", "Really?")', "Really?")
    term.send_keys("<Escape>")
    term.wait_for_text("answer=False")


def test_dismissing_a_yesnocancel_box_answers_none(terminal, tmp_path):
    """Its dismissal is 'cancel', which the function turns into None."""
    term = terminal(cols=60, rows=14)
    ask(term, tmp_path, 'askyesnocancel("Q", "Save?")', "Save?")
    term.send_keys("<Escape>")
    term.wait_for_text("answer=None")


def test_dismissing_an_info_box_still_answers_ok(terminal, tmp_path):
    """An ok box has nothing else to say, so its dismissal is 'ok' too."""
    term = terminal(cols=60, rows=14)
    ask(term, tmp_path, 'showinfo("Done", "All finished")', "All finished")
    term.send_keys("<Escape>")
    term.wait_for_text("answer='ok'")


# --------------------------------------------------------------- the boxes


def test_a_yesnocancel_box_shows_all_three_buttons(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    ask(term, tmp_path, 'askyesnocancel("Q", "Save?")', "Save?")
    row = next(i for i, line in enumerate(term.display) if "Yes" in line)
    line = term.display[row]
    assert line.index("Yes") < line.index("No") < line.index("Cancel")
    term.send_keys("<Escape>")


def test_the_title_and_the_message_both_appear(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    ask(term, tmp_path, 'showinfo("Spam", "Egg Information")', "Egg Information")
    assert term.contains("Spam")
    term.send_keys("<Escape>")


def test_the_default_button_has_the_keyboard(terminal, tmp_path):
    """Tk makes the first button the default when nobody says, so Return on
    an untouched okcancel box means OK."""
    term = terminal(cols=60, rows=14)
    ask(term, tmp_path, 'askokcancel("Q", "Proceed?")', "Proceed?")
    term.send(b"\r")
    term.wait_for_text("answer=True")


def test_a_named_default_takes_the_keyboard_instead(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    ask(
        term,
        tmp_path,
        'askokcancel("Q", "Proceed?", default=messagebox.CANCEL)',
        "Proceed?",
    )
    term.send(b"\r")
    term.wait_for_text("answer=False")
