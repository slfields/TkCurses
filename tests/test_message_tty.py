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

"""What a Message and a LabelFrame look like in a real terminal."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
PARAGRAPH = (
    'A Message picks its own line length, aiming for a block of text '
    'whose width is aspect percent of its height.'
)
{body}
root.update_layout()
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


def test_a_message_wraps_itself_over_several_lines(terminal, tmp_path):
    term = terminal(cols=60, rows=20)
    term.run_source(
        program("tkcurses.Message(root, text=PARAGRAPH).place(x=1, y=1)"),
        workdir=tmp_path,
    )
    term.wait_for_text("A Message")
    term.wait_for_idle()
    filled = [line for line in term.display if line.strip()]
    assert len(filled) > 3
    # Wrapped, not one long line: the default aspect of 150 aims for a block
    # half again as wide as it is tall.
    assert max(len(line.strip()) for line in filled) < 30


def test_the_text_starts_at_the_top_when_it_does_not_fit(terminal, tmp_path):
    """Centring a block taller than the widget must not lose its beginning."""
    term = terminal(cols=60, rows=20)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, relief='solid', bd=1)\n"
            "f.place(x=1, y=1, width=30, height=5)\n"
            "tkcurses.Message(f, text=PARAGRAPH, aspect=100).pack(\n"
            "    fill='both', expand=True\n"
            ")"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("A Message")


def test_a_labelframe_writes_its_caption_into_the_border(terminal, tmp_path):
    term = terminal(cols=60, rows=20)
    term.run_source(
        program(
            "f = tkcurses.LabelFrame(root, text='Options')\n"
            "f.place(x=1, y=1, width=24, height=6)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("Options")
    row = next(i for i, line in enumerate(term.display) if "Options" in line)
    # On the top border line, not inside the frame.
    assert "═" in term.display[row] or "─" in term.display[row]


def test_a_child_of_a_labelframe_sits_inside_the_border(terminal, tmp_path):
    """The mistake the geometry round's labelled_box helper made."""
    term = terminal(cols=60, rows=20)
    term.run_source(
        program(
            "f = tkcurses.LabelFrame(root, text='Options')\n"
            "f.place(x=1, y=1, width=24, height=6)\n"
            "tkcurses.Label(f, text='inside').pack(fill='both', expand=True)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("inside")
    caption = next(i for i, line in enumerate(term.display) if "Options" in line)
    inside = next(i for i, line in enumerate(term.display) if "inside" in line)
    assert inside > caption
    assert term.display[inside].index("inside") > 1


def test_the_caption_follows_its_anchor(terminal, tmp_path):
    term = terminal(cols=60, rows=20)
    term.run_source(
        program(
            "for n, anchor in enumerate(('nw', 'n', 'ne')):\n"
            "    f = tkcurses.LabelFrame(root, text=anchor, labelanchor=anchor)\n"
            "    f.place(x=1, y=1 + n * 5, width=30, height=4)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ne")
    term.wait_for_idle()
    columns = {}
    for anchor in ("nw", "n", "ne"):
        row = next(
            i
            for i, line in enumerate(term.display)
            if line.strip().replace("═", "").replace("╒", "").replace("╕", "").strip()
            == anchor
        )
        columns[anchor] = term.display[row].index(anchor)
    assert columns["nw"] < columns["n"] < columns["ne"]


def test_a_bottom_caption_lands_on_the_bottom_border(terminal, tmp_path):
    term = terminal(cols=60, rows=20)
    term.run_source(
        program(
            "f = tkcurses.LabelFrame(root, text='Totals', labelanchor='se')\n"
            "f.place(x=1, y=1, width=24, height=6)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("Totals")
    row = next(i for i, line in enumerate(term.display) if "Totals" in line)
    assert row == 6  # placed at y=1, six rows tall: the last is row 6


def test_a_caption_that_changes_repaints(terminal, tmp_path):
    term = terminal(cols=60, rows=20)
    term.run_source(
        program(
            "f = tkcurses.LabelFrame(root, text='Before')\n"
            "f.place(x=1, y=1, width=24, height=6)\n"
            "root.after(100, lambda: f.configure(text='After'))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("Before")
    term.wait_for_text("After")


def test_labelframes_pack_and_nest(terminal, tmp_path):
    term = terminal(cols=60, rows=20)
    term.run_source(
        program(
            "outer = tkcurses.LabelFrame(root, text='Outer')\n"
            "outer.pack(fill='both', expand=True, padx=1, pady=1)\n"
            "inner = tkcurses.LabelFrame(outer, text='Inner')\n"
            "inner.pack(fill='both', expand=True, padx=1, pady=1)\n"
            "tkcurses.Message(inner, text=PARAGRAPH).pack(fill='both', expand=True)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("Outer")
    term.wait_for_text("Inner")
    term.wait_for_text("A Message")
    outer = next(i for i, line in enumerate(term.display) if "Outer" in line)
    inner = next(i for i, line in enumerate(term.display) if "Inner" in line)
    assert inner > outer
