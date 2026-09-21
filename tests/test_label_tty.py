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

"""What a Label actually puts on the terminal."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
{body}
root.update_layout()
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


def test_a_label_shows_its_text(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("tkcurses.Label(root, text='hello there').place(x=3, y=2)"),
        workdir=tmp_path,
    )
    term.wait_for_text("hello there")
    assert term.display[2][3:14] == "hello there"


def test_a_label_wraps_at_its_wraplength(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tkcurses.Label(root, text='one two three four', wraplength=9,"
            " justify='left').place(x=0, y=0)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("one two")
    assert term.display[0].startswith("one two")
    assert term.display[1].startswith("three")
    assert term.display[2].startswith("four")


def test_justify_aligns_the_lines_against_each_other(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tkcurses.Label(root, text='a\\nlonger', justify='right',"
            " anchor='nw').place(x=0, y=0)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("longer")
    # The short line is pushed right to meet the long one's edge.
    assert term.display[0].startswith("     a")
    assert term.display[1].startswith("longer")


def test_anchor_places_the_text_within_the_widget(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "a = tkcurses.Label(root, text='NW', anchor='nw', width=20, height=5)\n"
            "a.place(x=0, y=0)\n"
            "b = tkcurses.Label(root, text='SE', anchor='se', width=20, height=5)\n"
            "b.place(x=0, y=6)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("NW")
    # SE is the last corner drawn and NW the first, so waiting for SE and
    # asserting NW reads two ends of one frame.
    term.wait_for_text("SE")
    term.wait_for_idle()
    assert term.display[0].startswith("NW")
    assert term.display[10][18:20] == "SE"


def test_a_bordered_label_keeps_its_text_inside(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("tkcurses.Label(root, text='inside', relief='solid').place(x=1, y=1)"),
        workdir=tmp_path,
    )
    term.wait_for_text("inside")
    term.wait_for_idle()
    assert term.display[1][1] == "┌"
    assert term.display[2][2:8] == "inside"
    assert term.display[3][1] == "└"


def test_text_wider_than_the_widget_is_clipped_not_spilled(terminal, tmp_path):
    """A character outside the widget lands on top of a neighbour."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tkcurses.Label(root, text='XXXXXXXXXXXXXXXXXXXXXXXX', width=6,"
            " anchor='w').place(x=0, y=0, width=6)\n"
            "buffer.write(4, 0, 'marker')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("marker")
    term.wait_for_idle()
    assert term.display[0].count("X") <= 6


def test_a_label_follows_its_textvariable(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "var = tkcurses.StringVar(root, value='before')\n"
            "tkcurses.Label(root, textvariable=var, anchor='w', width=20)"
            ".place(x=0, y=0)\n"
            "root.after(100, lambda: var.set('after the change'))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("before")
    term.wait_for_text("after the change")


def test_labels_pack_alongside_frames(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, relief='solid')\n"
            "f.pack(fill='both', expand=True)\n"
            "for word in ('first', 'second', 'third'):\n"
            "    tkcurses.Label(f, text=word).pack(side='top')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("first")
    term.wait_for_text("second")
    term.wait_for_text("third")
    rows = [i for i, line in enumerate(term.display) if "first" in line]
    assert rows, "the first label should be on screen"


def test_text_too_wide_keeps_its_beginning(terminal, tmp_path):
    """Clipping must cut the end, not the start.

    Justification is measured from the line's real length and applied before
    clipping. Measuring the clipped line instead pushes it right, so a label
    too narrow for its text shows the end of it hard against the far edge with
    the beginning cut off - which reads as text in the wrong place rather than
    text that does not fit.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, relief='solid', width=12, height=3)\n"
            "f.place(x=0, y=0)\n"
            "f.pack_propagate(False)\n"
            "tkcurses.Label(f, text='far too wide to fit', anchor='w')"
            ".pack(fill='both', expand=True)"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "far" in "\n".join(t.display), message="the text")
    term.wait_for_idle()
    assert term.display[1][1:11] == "far too wi"


def test_a_centred_label_narrower_than_its_text_starts_at_the_left(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, width=10, height=1)\n"
            "f.place(x=0, y=0)\n"
            "f.pack_propagate(False)\n"
            "tkcurses.Label(f, text='abcdefghijklmnop', justify='center')"
            ".pack(fill='both', expand=True)"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "abc" in "\n".join(t.display), message="the text")
    assert term.display[0].startswith("abcdefghij")
