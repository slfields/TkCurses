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

"""Colour and text attributes, across every widget that draws text.

Each of these was missing from at least one widget: the infrastructure had
existed since the base widget system, and the widgets written afterwards
picked up the background and forgot the rest. A test per widget, because
"most of them do it" is how the gap happened in the first place.
"""

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


def find(term, needle):
    """Where a run of text starts, as ``(row, column)``."""
    row = next(i for i, line in enumerate(term.display) if needle in line)
    return row, term.display[row].index(needle)


# The widget, the source that builds a bold one showing MARKER, and the
# marker to look for.
BOLD_CASES = [
    ("Label", "tkcurses.Label(root, text='MARKER', font='bold').place(x=2, y=2)"),
    ("Button", "tkcurses.Button(root, text='MARKER', font='bold').place(x=2, y=2)"),
    (
        "Checkbutton",
        "tkcurses.Checkbutton(root, text='MARKER', font='bold').place(x=2, y=2)",
    ),
    (
        "Radiobutton",
        "tkcurses.Radiobutton(root, text='MARKER', font='bold').place(x=2, y=2)",
    ),
    (
        "Message",
        "tkcurses.Message(root, text='MARKER', font='bold', width=10).place(x=2, y=2)",
    ),
    (
        "Entry",
        "e = tkcurses.Entry(root, width=12, font='bold')\n"
        "e.place(x=2, y=2)\n"
        "e.insert(0, 'MARKER')",
    ),
    (
        "Spinbox",
        "s = tkcurses.Spinbox(root, values=('MARKER', 'other'), width=12,"
        " font='bold', state='readonly')\n"
        "s.place(x=2, y=2)",
    ),
    (
        "Text",
        "t = tkcurses.Text(root, width=12, height=3, font='bold')\n"
        "t.place(x=2, y=2)\n"
        "t.insert('1.0', 'MARKER')\n"
        "t.mark_set('insert', '1.0')",
    ),
    (
        "Listbox",
        "lb = tkcurses.Listbox(root, width=12, height=3, font='bold')\n"
        "lb.place(x=2, y=2)\n"
        "lb.insert('end', 'MARKER')",
    ),
    (
        "Scale",
        "tkcurses.Scale(root, orient='horizontal', from_=0, to=9, length=12,"
        " label='MARKER', font='bold', showvalue=False).place(x=2, y=2)",
    ),
    (
        "LabelFrame",
        "tkcurses.LabelFrame(root, text='MARKER', font='bold')"
        ".place(x=2, y=2, width=20, height=5)",
    ),
]


@pytest.mark.parametrize(
    ("widget", "source"), BOLD_CASES, ids=[case[0] for case in BOLD_CASES]
)
def test_font_bold_reaches_the_text(terminal, tmp_path, widget, source):
    term = terminal(cols=40, rows=12)
    term.run_source(program(source), workdir=tmp_path)
    term.wait_for_text("MARKER")
    row, column = find(term, "MARKER")
    assert term.attrs_at(row, column)["bold"], f"{widget} drew its text unbolded"


@pytest.mark.parametrize(
    ("widget", "source"), BOLD_CASES, ids=[case[0] for case in BOLD_CASES]
)
def test_font_underline_reaches_the_text(terminal, tmp_path, widget, source):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(source.replace("font='bold'", "font='underline'")), workdir=tmp_path
    )
    term.wait_for_text("MARKER")
    row, column = find(term, "MARKER")
    assert term.attrs_at(row, column)["underscore"], f"{widget} drew it unstyled"


COLOUR_CASES = [
    ("Label", "tkcurses.Label(root, text='MARKER', foreground='red').place(x=2, y=2)"),
    (
        "Entry",
        "e = tkcurses.Entry(root, width=12, foreground='red')\n"
        "e.place(x=2, y=2)\n"
        "e.insert(0, 'MARKER')",
    ),
    (
        "Text",
        "t = tkcurses.Text(root, width=12, height=3, foreground='red')\n"
        "t.place(x=2, y=2)\n"
        "t.insert('1.0', 'MARKER')\n"
        "t.mark_set('insert', '1.0')",
    ),
    (
        "Listbox",
        "lb = tkcurses.Listbox(root, width=12, height=3, foreground='red')\n"
        "lb.place(x=2, y=2)\n"
        "lb.insert('end', 'MARKER')",
    ),
    (
        "Scale",
        "tkcurses.Scale(root, orient='horizontal', from_=0, to=9, length=12,"
        " label='MARKER', foreground='red', showvalue=False).place(x=2, y=2)",
    ),
    (
        "LabelFrame",
        "tkcurses.LabelFrame(root, text='MARKER', foreground='red')"
        ".place(x=2, y=2, width=20, height=5)",
    ),
]


@pytest.mark.parametrize(
    ("widget", "source"), COLOUR_CASES, ids=[case[0] for case in COLOUR_CASES]
)
def test_foreground_reaches_the_text(terminal, tmp_path, widget, source):
    term = terminal(cols=40, rows=12)
    term.run_source(program(source), workdir=tmp_path)
    term.wait_for_text("MARKER")
    row, column = find(term, "MARKER")
    assert term.attrs_at(row, column)["fg"] == "red", f"{widget} drew it uncoloured"


STATE_CASES = [
    ("Label", "tkcurses.Label(root, text='MARKER', state='disabled').place(x=2, y=2)"),
    (
        "Button",
        "tkcurses.Button(root, text='MARKER', state='disabled').place(x=2, y=2)",
    ),
    (
        "Entry",
        "e = tkcurses.Entry(root, width=12, state='normal')\n"
        "e.place(x=2, y=2)\n"
        "e.insert(0, 'MARKER')\n"
        "e.configure(state='disabled')",
    ),
    (
        "Listbox",
        # Filled first: a disabled Listbox refuses insert, as Tk's does.
        "lb = tkcurses.Listbox(root, width=12, height=3)\n"
        "lb.place(x=2, y=2)\n"
        "lb.insert('end', 'MARKER')\n"
        "lb.configure(state='disabled')",
    ),
    (
        "Scale",
        "tkcurses.Scale(root, orient='horizontal', from_=0, to=9, length=12,"
        " label='MARKER', state='disabled', showvalue=False).place(x=2, y=2)",
    ),
]


@pytest.mark.parametrize(
    ("widget", "source"), STATE_CASES, ids=[case[0] for case in STATE_CASES]
)
def test_disabled_looks_different_from_normal(terminal, tmp_path, widget, source):
    """A control that refuses the user has to say so before they try it."""
    term = terminal(cols=40, rows=12)
    term.run_source(program(source), workdir=tmp_path)
    term.wait_for_text("MARKER")
    row, column = find(term, "MARKER")
    disabled = term.attrs_at(row, column)

    plain = terminal(cols=40, rows=12)
    plain.run_source(
        program(source.replace("state='disabled'", "state='normal'")),
        workdir=tmp_path / widget,
    )
    plain.wait_for_text("MARKER")
    row, column = find(plain, "MARKER")
    assert disabled != plain.attrs_at(row, column), f"{widget} ignores its state"
