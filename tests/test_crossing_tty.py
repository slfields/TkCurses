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

"""<Enter> and <Leave> made from presses, drags and releases.

The terminal does not report the pointer between presses unless hover
reporting is on, so the crossings come from the reports there are, as X11
makes them under the implicit grab: a click is a visit - Enter, the press,
the release, Leave - and a drag tells only the widget pressed that the
pointer left it and came back.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

#: Two labels side by side at columns 0-4 and 10-14 of row 1, each logging
#: what it hears to row 7, and a bordered button on rows 3-5.
PROGRAM = """
{prelude}
import tkcurses

root = tkcurses.Tk()
log = []
shown = tkcurses.Label(root, text="", anchor="w", width=60, borderwidth=0)
shown.place(x=0, y=7)


def note(word):
    log.append(word)
    shown.configure(text=" ".join(log) + " .")


for name, column in (("a", 0), ("b", 10)):
    label = tkcurses.Label(root, text=name * 5, borderwidth=0)
    label.place(x=column, y=1, width=5)
    for sequence, tag in (("<Enter>", "E"), ("<Leave>", "L"),
                          ("<ButtonPress-1>", "P"), ("<ButtonRelease-1>", "R")):
        label.bind(sequence, lambda event, word=tag + name: note(word))

button = tkcurses.Button(root, text="Go", command=lambda: note("go"))
button.place(x=0, y=3)
{body}
root.after(8000, root.quit)
root.mainloop()
"""


def start(terminal, tmp_path, body="", prelude=""):
    term = terminal(cols=70, rows=9)
    term.run_source(PROGRAM.format(body=body, prelude=prelude), workdir=tmp_path)
    term.wait_for_text("aaaaa")
    return term


def logged(term, text):
    term.wait_for(lambda t: t.display[7].rstrip().endswith(text + " ."))


def test_a_click_is_a_visit(terminal, tmp_path):
    """Enter before the press and Leave after the release, as Tk orders them."""
    term = start(terminal, tmp_path)
    term.click(1, 1)
    logged(term, "Ea Pa Ra La")


def test_a_drag_tells_only_the_widget_pressed(terminal, tmp_path):
    """X11's implicit grab: b never hears the pointer cross it."""
    term = start(terminal, tmp_path)
    term.send_mouse(1, 1, action="press")
    logged(term, "Ea Pa")
    term.send_mouse(11, 1, action="move")
    logged(term, "Ea Pa La")
    term.send_mouse(2, 1, action="move")
    logged(term, "Ea Pa La Ea")
    term.send_mouse(2, 1, action="release")
    logged(term, "Ea Pa La Ea Ra La")


def test_a_release_off_the_widget_has_left_it_already(terminal, tmp_path):
    term = start(terminal, tmp_path)
    term.send_mouse(1, 1, action="press")
    logged(term, "Ea Pa")
    term.send_mouse(11, 1, action="move")
    logged(term, "Ea Pa La")
    term.send_mouse(11, 1, action="release")
    logged(term, "Ea Pa La Ra")


def test_a_button_dragged_off_is_drawn_released(terminal, tmp_path):
    """tk::ButtonLeave: the held look goes, since letting go will not press
    it; tk::ButtonEnter brings it back."""
    term = start(terminal, tmp_path)
    term.send_mouse(3, 4, action="press")
    term.wait_for_cell(4, 1, lambda cell: cell.data == "▌")
    term.send_mouse(30, 4, action="move")
    term.wait_for_cell(4, 1, lambda cell: cell.data != "▌")
    term.send_mouse(3, 4, action="move")
    term.wait_for_cell(4, 1, lambda cell: cell.data == "▌")
    term.send_mouse(3, 4, action="release")
    logged(term, "go")


def test_a_grab_elsewhere_keeps_the_pointer_out(terminal, tmp_path):
    """Only widgets inside the grab hear the pointer, as only they hear the
    press."""
    term = start(terminal, tmp_path, body="button.grab_set()")
    term.click(1, 1)
    term.click(3, 4)
    logged(term, "go")
    assert "Ea" not in term.display[7]


def test_with_hover_reported_the_pointer_is_followed(terminal, tmp_path):
    term = start(
        terminal,
        tmp_path,
        prelude="import os\nos.environ['TKCURSES_MOUSE_REPORT_HOVER'] = '1'",
    )
    # SGR code 35: motion with no button held, which send_mouse cannot spell.
    term.send(b"\x1b[<35;2;2M")
    logged(term, "Ea")
    term.send(b"\x1b[<35;12;2M")
    logged(term, "Ea La Eb")
