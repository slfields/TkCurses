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


"""A real dialog, over a real application, on a real screen.

The headless module tests the grab and the stacking. This one runs the
actual dialog classes, because two things can only fail here: what the
screen looks like while a dialog is up and after it goes, and where the
keyboard ends up once a dialog that ends in ``wait_window()`` has returned.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


APPLICATION = """
import tkcurses
from tkcurses import simpledialog

root = tkcurses.Tk()
buffer = root.tk.screen.buffer

frame = tkcurses.Frame(root, name='main', relief='solid')
frame.place(x=0, y=2, width=34, height=8)
tkcurses.Label(frame, text='APPLICATION', anchor='w').place(x=1, y=1, width=20)
field = tkcurses.Entry(frame, name='field')
field.place(x=1, y=3, width=20)
field.insert(0, 'under')
field.focus_set()

state = {'answer': None}


def report():
    who = root.tk.focus
    buffer.write(0, 0, ('focus=%s answer=%r' % (
        who.winfo_name() if who is not None else '-', state['answer'])).ljust(46))
    root.tk.screen.refresh()


def ask(event):
    state['answer'] = simpledialog.askstring('Name', 'Who?', parent=root)
    report()
    return 'break'


# A widget binding, not a root one. The field has the focus, and Entry's
# class binding eats printable keys - 'd' landed in the field. A widget
# binding runs before the class tag and breaks before it gets there.
field.bind('<Key-d>', ask)
root.update_layout()
report()
root.after(8000, root.quit)
root.mainloop()
"""


@pytest.fixture
def running(terminal, tmp_path):
    term = terminal(cols=48, rows=16)
    term.run_source(APPLICATION, workdir=tmp_path)
    term.wait_for_text("APPLICATION")
    term.wait_for_idle()
    return term


def test_the_application_is_on_screen_before_the_dialog(running):
    assert any("APPLICATION" in row for row in running.display)
    assert any("under" in row for row in running.display)


def test_a_dialog_appears_over_the_application(running):
    running.send(b"d")
    running.wait_for_text("Who?")
    running.wait_for_idle()

    assert any("Who?" in row for row in running.display)
    # Covered, not destroyed. The dialog sits over the middle of the
    # application's frame, so the label reads as a fragment at the edge -
    # "APP" and no more. Asserting the whole word here would be asserting
    # that the dialog fails to cover anything.
    assert any("APP" in row for row in running.display), running.describe()
    assert not any("APPLICATION" in row for row in running.display), running.describe()


def test_closing_the_dialog_puts_the_screen_back(running):
    """A dialog covers cells it does not own. When it goes, whatever it was
    covering has to come back - and the widget underneath is the only thing
    that can redraw it.
    """
    running.send(b"d")
    running.wait_for_text("Who?")
    running.wait_for_idle()

    running.send(b"typed\r")
    running.wait_for_text("answer='typed'")
    running.wait_for_idle()

    assert not any("Who?" in row for row in running.display), running.describe()
    assert any("APPLICATION" in row for row in running.display), running.describe()
    assert any("under" in row for row in running.display), running.describe()


def test_the_dialog_answers_with_what_was_typed(running):
    running.send(b"d")
    running.wait_for_text("Who?")
    running.wait_for_idle()

    running.send(b"typed\r")

    running.wait_for_text("answer='typed'")


def test_escape_closes_the_dialog_without_an_answer(running):
    running.send(b"d")
    running.wait_for_text("Who?")
    running.wait_for_idle()

    running.send(b"\x1b")
    running.wait_for_text("answer=None")
    running.wait_for_idle()

    assert not any("Who?" in row for row in running.display), running.describe()


def test_closing_returns_the_keyboard_to_the_widget_that_had_it(running):
    """The application's Entry had the focus. After the dialog closes it
    should have it again - the *widget*, not merely its window.

    simpledialog.cancel() does parent.focus_set(), which lands the focus on
    the root rather than on the field, because the tuple that knew about the
    field was captured after the dialog had already taken the focus away.
    """
    running.wait_for_text("focus=field")

    running.send(b"d")
    running.wait_for_text("Who?")
    running.wait_for_idle()
    running.send(b"typed\r")
    running.wait_for_text("answer='typed'")
    running.wait_for_idle()

    assert "focus=field" in running.row(0), running.describe()
