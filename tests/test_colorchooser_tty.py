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

"""The colour chooser against a real terminal.

A swatch is a run of coloured blanks, so almost nothing here can be read out
of the characters on screen: the tests ask the emulator what colour each cell
was painted.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

PROGRAM = """
import tkcurses
from tkcurses import colorchooser

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
buffer.write(0, 0, "ready")
root.tk.screen.refresh()


def ask(event):
    rgb, name = colorchooser.askcolor(parent=root, title=" Colour "{extra})
    buffer.write(1, 0, "picked=%s %s          " % (rgb, name))
    root.tk.screen.refresh()


root.bind("<Key-a>", ask)
root.after(8000, root.quit)
root.mainloop()
"""


def open_chooser(term, tmp_path, extra=""):
    term.run_source(PROGRAM.format(extra=extra), workdir=tmp_path)
    term.wait_for_text("ready")
    term.send(b"a")
    term.wait_for_text("or type a colour")


def swatch_rows(term):
    """The rows holding swatches, and what colours each holds.

    A row of swatches is one with *several different* colours on it. Counting
    painted cells instead finds the dialog's own background as well, which is
    painted across most of its rows and is one colour throughout.
    """
    found = {}
    for row, _ in enumerate(term.display):
        colors = [
            term.attrs_at(row, column).get("bg")
            for column in range(term.cols)
            if term.attrs_at(row, column).get("bg") not in ("default", None)
        ]
        if len(set(colors)) >= 8:
            found[row] = colors
    return found


def test_the_sixteen_colours_are_shown_as_swatches(terminal, tmp_path):
    """Two rows of eight, so a colour and its bright form line up."""
    term = terminal(cols=60, rows=18)
    open_chooser(term, tmp_path)
    rows = swatch_rows(term)
    assert len(rows) == 2, f"expected two rows of swatches:\n{term.describe()}"
    for colors in rows.values():
        # Eight colours, each a few cells wide.
        assert len(set(colors)) == 8, term.describe()


def test_the_swatches_are_the_terminal_s_own_colours(terminal, tmp_path):
    term = terminal(cols=60, rows=18)
    open_chooser(term, tmp_path)
    painted = set()
    for colors in swatch_rows(term).values():
        painted |= set(colors)
    # pyte names ANSI 3 "brown" rather than "yellow", which is the
    # traditional naming and not a fault here.
    assert {"black", "red", "green", "blue", "magenta", "cyan", "white"} <= painted


def test_clicking_a_swatch_answers_with_that_colour(terminal, tmp_path):
    term = terminal(cols=60, rows=18)
    open_chooser(term, tmp_path)
    row = next(iter(swatch_rows(term)))
    column = next(
        c for c in range(term.cols) if term.attrs_at(row, c).get("bg") == "red"
    )
    term.click(column, row)
    term.wait_for_text("picked=(205, 0, 0) #cd0000")


def test_a_typed_name_is_resolved_to_what_the_terminal_shows(terminal, tmp_path):
    """red is #ff0000 elsewhere and #cd0000 here, and here is what matters."""
    term = terminal(cols=60, rows=18)
    open_chooser(term, tmp_path)
    term.send(b"red")
    term.send(b"\r")
    term.wait_for_text("picked=(205, 0, 0) #cd0000")


def test_a_typed_hex_colour_is_its_own_answer(terminal, tmp_path):
    term = terminal(cols=60, rows=18)
    open_chooser(term, tmp_path)
    term.send(b"#005f5f")
    term.send(b"\r")
    term.wait_for_text("picked=(0, 95, 95) #005f5f")


def test_a_name_that_is_not_a_colour_is_refused_quietly(terminal, tmp_path):
    """And must not take the application down: winfo_rgb raises ValueError
    for an unknown name, which a dialog has to catch rather than let out."""
    term = terminal(cols=60, rows=18)
    open_chooser(term, tmp_path)
    term.send(b"nosuchcolour")
    term.send(b"\r")
    term.wait_for_idle()
    assert not term.contains("picked="), term.describe()
    assert "Traceback" not in term.stderr
    term.send_keys("<Escape>")
    term.wait_for_text("picked=None None")


def test_cancelling_answers_with_a_pair_of_nones(terminal, tmp_path):
    term = terminal(cols=60, rows=18)
    open_chooser(term, tmp_path)
    term.send_keys("<Escape>")
    term.wait_for_text("picked=None None")


def test_an_initial_colour_is_there_to_start_with(terminal, tmp_path):
    term = terminal(cols=60, rows=18)
    open_chooser(term, tmp_path, extra=', color="green"')
    assert term.contains("green")
    term.send(b"\r")
    term.wait_for_text("picked=(0, 205, 0) #00cd00")
