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

"""Typing characters beyond ASCII into the widgets that take text.

A terminal sends such a character as its UTF-8 bytes, and curses hands them
over one at a time; until TkCurses-w9kd each became a key with no character
and nothing at all reached the widget.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

TYPED = "aé界😀b"

PROGRAM = """
import tkcurses as tk
root = tk.Tk()
field = tk.{WIDGET}
field.pack()
field.focus_set()
shown = tk.Label(root, text="ready")
shown.pack()
keys = []
field.bind("<Key-eacute>", lambda e: keys.append("eacute"))
field.bind("<Key-U754C>", lambda e: keys.append("U754C"))
def report(event):
    shown["text"] = "got=%r %s" % (field.get({RANGE}), " ".join(keys))
    return "break"
field.bind("<Key-Return>", report)
root.after(15000, root.quit)
root.mainloop()
"""


@pytest.mark.parametrize(
    ("widget", "text_range"),
    [
        ("Entry(root, width=30)", ""),
        ("Text(root, width=30, height=2)", '"1.0", "end-1c"'),
    ],
    ids=["Entry", "Text"],
)
def test_a_typed_character_beyond_ascii_reaches_the_widget(
    terminal, tmp_path, widget, text_range
):
    term = terminal(cols=50, rows=8)
    source = PROGRAM.replace("{WIDGET}", widget).replace("{RANGE}", text_range)
    term.run_source(source, workdir=tmp_path)
    term.wait_for_text("ready")
    term.send((TYPED + "\r").encode())
    expected = f"got={TYPED!r} eacute U754C"
    term.wait_for(lambda t: any(expected in row for row in t.display))


SHOWN = """
import tkcurses as tk
root = tk.Tk()
field = tk.Entry(root, width=20)
field.pack()
field.focus_set()
shown = tk.Label(root, text="ready")
shown.pack()
def report(event):
    shown["text"] = "got=%r" % field.get()
    return "break"
field.bind("<Key-Return>", report)
root.after(15000, root.quit)
root.mainloop()
"""


def test_a_typed_no_break_space_and_soft_hyphen_are_kept_and_drawn(terminal, tmp_path):
    """Python calls both unprintable; Tk inserts them, and a terminal shows
    them as a space and a hyphen."""
    term = terminal(cols=40, rows=8)
    term.run_source(SHOWN, workdir=tmp_path)
    term.wait_for_text("ready")
    term.send("a\u00a0b\u00adc\r".encode())
    term.wait_for(
        lambda t: (
            any("got='a\\xa0b\\xadc'" in row for row in t.display)
            and any("│a b-c " in row for row in t.display)
        )
    )


ZERO_WIDTH = """
import tkcurses as tk
root = tk.Tk()
field = tk.Entry(root, width=20)
field.insert(0, "a\\u200bb\\u200dc|")
field.pack()
field.focus_set()
tk.Label(root, text="ready").pack()
root.after(15000, root.quit)
root.mainloop()
"""


def test_a_zero_width_character_leaves_the_cursor_after_the_text(terminal, tmp_path):
    """Drawn as nothing, as it is measured: drawn as a ``?`` it pushed the
    text a column past the cursor."""
    term = terminal(cols=40, rows=8)
    term.run_source(ZERO_WIDTH, workdir=tmp_path)
    term.wait_for_text("ready")
    term.wait_for(lambda t: any("│abc| " in row for row in t.display))
    row = next(i for i, text in enumerate(term.display) if "│abc|" in text)
    column = term.display[row].index("│abc|") + 5
    term.wait_for(lambda t: t.cursor == (row, column))
