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

"""The dialog base class against a real terminal.

A dialog is almost entirely behaviour: where it lands, what has the keyboard
while it is up, what the caller gets back, and what the screen looks like
afterwards. None of that can be read out of the library's own numbers, which
is why it is all here.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

#: A confirm dialog with two buttons, over a screen full of text, so that
#: anything the dialog leaves behind is obvious against the background.
PROGRAM = """
import tkcurses
from tkcurses.commondialog import Dialog


class Ask(Dialog):
    def body(self, window):
        tkcurses.Label(window, text="Delete everything?").pack(pady=1)
        row = tkcurses.Frame(window)
        row.pack()
        yes = tkcurses.Button(row, text="Yes", command=lambda: self.finish("yes"))
        yes.pack(side="left", padx=1)
        no = tkcurses.Button(row, text="No", command=lambda: self.finish("no"))
        no.pack(side="left", padx=1)
        return yes


root = tkcurses.Tk()
buffer = root.tk.screen.buffer
for row in range(2, root.winfo_height() - 1):
    buffer.write(row, 0, "background " * 8)
buffer.write(0, 0, "ready")
root.tk.screen.refresh()


def ask(event):
    answer = Ask(root, title=" Confirm ").show()
    buffer.write(1, 0, "answer=%r         " % (answer,))
    root.tk.screen.refresh()


root.bind("<Key-a>", ask)
{extra}
root.after(8000, root.quit)
root.mainloop()
"""


def run(term, tmp_path, extra=""):
    term.run_source(PROGRAM.format(extra=extra), workdir=tmp_path)
    term.wait_for_text("ready")


def open_dialog(term):
    term.send(b"a")
    term.wait_for_text("Delete everything?")


def test_a_dialog_is_centred_and_sized_to_what_it_holds(terminal, tmp_path):
    """There is no window manager to place it and none to size it.

    A dialog that needs moving or resizing by hand is not a dialog, so both
    are the library's job here in a way they are not in tkinter.
    """
    term = terminal(cols=56, rows=14)
    run(term, tmp_path)
    open_dialog(term)

    top = next(i for i, line in enumerate(term.display) if "┌" in line)
    bottom = next(i for i, line in enumerate(term.display) if "└" in line)
    left = term.display[top].index("┌")
    right = term.display[top].index("┐")
    # Centred within a cell either way, since a box and a screen do not
    # always share their parity.
    assert abs(left - (56 - (right - left + 1) - left)) <= 1, term.describe()
    assert abs(top - (14 - (bottom - top + 1) - top)) <= 1, term.describe()
    # Sized to its content rather than to a default: everything the body put
    # in is on screen, and the box is no wider than it has to be. A toplevel
    # reports the room its contents need without the border it draws round
    # them, which is two cells the dialog has to add back or it clips itself.
    assert term.contains("Delete everything?"), term.describe()
    assert "Yes" in "\n".join(term.display), term.describe()
    assert "No" in "\n".join(term.display), term.describe()
    width = right - left + 1
    assert 20 <= width <= 30, f"width {width} is not content-sized:\n{term.describe()}"


def test_the_title_is_drawn_on_the_dialog(terminal, tmp_path):
    term = terminal(cols=56, rows=14)
    run(term, tmp_path)
    open_dialog(term)
    assert term.contains("Confirm")


def test_the_dialog_covers_what_is_behind_it(terminal, tmp_path):
    """Its window is opaque, as a window over a window has to be."""
    term = terminal(cols=56, rows=14)
    run(term, tmp_path)
    open_dialog(term)
    row = next(i for i, line in enumerate(term.display) if "Delete" in line)
    assert "background" not in term.display[row][17:37], term.describe()


def test_a_button_returns_its_answer_to_the_caller(terminal, tmp_path):
    """show() blocks and gives the value back, which is the whole point."""
    term = terminal(cols=56, rows=14)
    run(term, tmp_path)
    open_dialog(term)
    row = next(i for i, line in enumerate(term.display) if "No" in line)
    term.click(term.display[row].index("No"), row)
    term.wait_for_text("answer='no'")


def test_the_dialog_starts_with_the_keyboard(terminal, tmp_path):
    """The body says which widget should have it, and Return presses that."""
    term = terminal(cols=56, rows=14)
    run(term, tmp_path)
    open_dialog(term)
    term.send(b"\r")
    term.wait_for_text("answer='yes'")


def test_escape_cancels_and_returns_nothing(terminal, tmp_path):
    term = terminal(cols=56, rows=14)
    run(term, tmp_path)
    open_dialog(term)
    term.send_keys("<Escape>")
    term.wait_for_text("answer=None")


def test_the_screen_behind_comes_back_unmarked(terminal, tmp_path):
    """A dialog that leaves anything behind is worse than no dialog."""
    term = terminal(cols=56, rows=14)
    run(term, tmp_path)
    before = list(term.display[2:12])
    open_dialog(term)
    term.send_keys("<Escape>")
    term.wait_for_text("answer=None")
    term.wait_for(
        lambda t: list(t.display[2:12]) == before,
        message="the background exactly as it was",
    )


def test_the_keyboard_goes_back_to_the_application_afterwards(terminal, tmp_path):
    """The grab has to be released, or the application is dead after one
    dialog - which is how a modal window traps everything."""
    term = terminal(cols=56, rows=14)
    run(
        term,
        tmp_path,
        extra='root.bind("<Key-z>", lambda event: ('
        '    buffer.write(0, 0, "z seen"), root.tk.screen.refresh()))',
    )
    open_dialog(term)
    term.send_keys("<Escape>")
    term.wait_for_text("answer=None")
    term.send(b"z")
    term.wait_for_text("z seen")


def test_the_application_beneath_cannot_be_reached_while_it_is_up(terminal, tmp_path):
    """Modal means modal: the key must not get past the dialog."""
    term = terminal(cols=56, rows=14)
    run(
        term,
        tmp_path,
        extra='root.bind("<Key-z>", lambda event: ('
        '    buffer.write(0, 0, "z seen"), root.tk.screen.refresh()))',
    )
    open_dialog(term)
    term.send(b"z")
    term.wait_for_idle()
    assert not term.contains("z seen"), (
        f"a key reached the application under a modal dialog:\n{term.describe()}"
    )
    term.send_keys("<Escape>")


def test_a_dialog_can_be_opened_from_inside_another(terminal, tmp_path):
    """Which is what a save-before-quit prompt is."""
    term = terminal(cols=60, rows=16)
    term.run_source(
        """
import tkcurses
from tkcurses.commondialog import Dialog


class Inner(Dialog):
    def body(self, window):
        tkcurses.Label(window, text="inner dialog").pack()
        button = tkcurses.Button(
            window, text="Inner OK", command=lambda: self.finish("inner")
        )
        button.pack()
        return button


class Outer(Dialog):
    def body(self, window):
        tkcurses.Label(window, text="outer dialog").pack()
        button = tkcurses.Button(
            window, text="Go deeper", command=self.deeper
        )
        button.pack()
        return button

    def deeper(self):
        self.finish(Inner(self._window, title=" Inner ").show())


root = tkcurses.Tk()
buffer = root.tk.screen.buffer
buffer.write(0, 0, "ready")
root.tk.screen.refresh()


def ask(event):
    buffer.write(1, 0, "answer=%r      " % (Outer(root, title=" Outer ").show(),))
    root.tk.screen.refresh()


root.bind("<Key-a>", ask)
root.after(8000, root.quit)
root.mainloop()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send(b"a")
    term.wait_for_text("outer dialog")
    term.send(b"\r")
    term.wait_for_text("inner dialog")
    term.send(b"\r")
    term.wait_for_text("answer='inner'")
    term.wait_for(
        lambda t: not t.contains("outer dialog"),
        message="both dialogs to be gone",
    )
