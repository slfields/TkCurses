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

"""Reaching the menu bar from the keyboard: F10, and Alt with a letter.

Tk's menu.tcl binds both on ``all`` under X11 - ``tk::FirstMenu`` and
``tk::TraverseToMenu`` - and without them nothing but the mouse reached a
menu bar, so a program whose commands were in its menus could not be used in
a terminal without mouse reporting. Every expectation here was measured on
Tk 9.0.2 under X11 with the same menus. A terminal sends Alt-e as Escape and
then e. TkCurses-r3og.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

ESCAPE = b"\x1b"

PROGRAM = """
import tkcurses as tk

root = tk.Tk()
said = tk.StringVar(root, "-")

bar = tk.Menu(root)
files = tk.Menu(bar, tearoff=0)
files.add_command(label="Open", underline=0, command=lambda: said.set("open ran"))
files.add_command(label="Quit", underline=0)
edits = tk.Menu(bar, tearoff=0)
edits.add_command(label="Cut", underline=2, state="disabled")
edits.add_command(label="Copy", underline=0, command=lambda: said.set("copy ran"))
bar.add_cascade(label="File", menu=files, underline=0)
bar.add_cascade(label="Edit", menu=edits, underline=0)
bar.add_command(label="Help", underline=0, command=lambda: said.set("help ran"))
root.config(menu=bar)

field = tk.Entry(root, name="field", width=12)
field.pack(anchor="w")
text = tk.Text(root, name="notes", width=12, height=1)
text.pack(anchor="w")

tools = tk.Menubutton(root, text="Tools", underline=0)
zaps = tk.Menu(tools, tearoff=0)
zaps.add_command(label="Zap", command=lambda: said.set("zap ran"))
tools["menu"] = zaps
tools.pack(anchor="w")
dull = tk.Menubutton(root, text="Dull", underline=0, state="disabled")
drab = tk.Menu(dull, tearoff=0)
drab.add_command(label="Drab")
dull["menu"] = drab
dull.pack(anchor="w")
dim = tk.Menubutton(root, text="Dim", underline=0)
faint = tk.Menu(dim, tearoff=0)
faint.add_command(label="Faint", command=lambda: said.set("faint ran"))
dim["menu"] = faint
dim.pack(anchor="w")

readout = tk.Label(root, anchor="w")
readout.pack(side="bottom", fill="x")
field.focus_set()

def show():
    focus = root.focus_get()
    readout["text"] = "focus=%s said=%s field=[%s] notes=[%s]" % (
        focus, said.get(), field.get(), text.get("1.0", "end-1c"))
    root.after(50, show)

show()
root.after(20000, root.quit)
root.mainloop()
"""


def start(terminal, tmp_path):
    term = terminal(cols=60, rows=20)
    term.run_source(PROGRAM, workdir=tmp_path)
    term.wait_for_text("focus=.field")
    return term


def closed_with_focus_back(term, item):
    term.send(ESCAPE)
    term.wait_for(
        lambda t: not t.contains(item) and t.contains("focus=.field"),
        message=f"{item} closed and the focus back in the field",
    )


def test_f10_opens_the_first_menu_and_escape_returns_the_focus(terminal, tmp_path):
    term = start(terminal, tmp_path)
    term.send_keys("<F10>")
    term.wait_for(lambda t: t.contains("Open") and t.contains("Quit"), message="File")
    closed_with_focus_back(term, "Open")


@pytest.mark.parametrize("letter", [b"e", b"E"])
def test_alt_and_a_letter_opens_that_menu_at_its_first_live_entry(
    terminal, tmp_path, letter
):
    """Cut is disabled, so Copy is the entry made active: Return chooses it."""
    term = start(terminal, tmp_path)
    term.send(ESCAPE + letter)
    term.wait_for(lambda t: t.contains("Copy"), message="Edit")
    term.send(b"\r")
    term.wait_for(
        lambda t: t.contains("said=copy ran") and not t.contains("Copy"),
        message="Copy chosen",
    )


def test_alt_and_a_commands_letter_runs_it(terminal, tmp_path):
    term = start(terminal, tmp_path)
    term.send(ESCAPE + b"h")
    term.wait_for(
        lambda t: t.contains("said=help ran") and t.contains("focus=.field"),
        message="Help run, the focus left in the field",
    )


def test_alt_and_a_letter_reaches_a_menubutton(terminal, tmp_path):
    term = start(terminal, tmp_path)
    term.send(ESCAPE + b"t")
    term.wait_for(lambda t: t.contains("Zap"), message="the Tools menu")
    term.send(b"\r")
    term.wait_for(lambda t: t.contains("said=zap ran"), message="Zap chosen")


def test_a_disabled_menubutton_is_passed_over_for_the_next(terminal, tmp_path):
    """Dull and Dim are both underlined d; tk::MenuFind skips the disabled
    one and goes on to the next."""
    term = start(terminal, tmp_path)
    term.send(ESCAPE + b"d")
    term.wait_for(lambda t: t.contains("Faint"), message="Dim's menu")
    assert not term.contains("Drab")


@pytest.mark.parametrize(("name", "focus"), [("field", "field"), ("notes", "notes")])
def test_an_alt_letter_is_not_typed(terminal, tmp_path, name, focus):
    """entry.tcl and text.tcl bind <Alt-Key> to nothing: x underlines no
    menu, and still no x is typed - the a after it is."""
    term = start(terminal, tmp_path)
    if name == "notes":
        term.send(b"\t")
        term.wait_for_text("focus=.notes")
    term.send(ESCAPE + b"x")
    term.send(b"a")
    term.wait_for(
        lambda t: t.contains(f"{focus}=[a]") and t.contains(f"focus=.{name}"),
        message="only the a typed",
    )


def test_an_alt_letter_from_inside_an_open_menu_is_the_menus(terminal, tmp_path):
    """A posted menu keeps every key: Alt-h in File does not run Help."""
    term = start(terminal, tmp_path)
    term.send_keys("<F10>")
    term.wait_for(lambda t: t.contains("Open"), message="File")
    term.send(ESCAPE + b"h")
    term.send(b"o")
    term.wait_for(
        lambda t: t.contains("said=open ran") and not t.contains("Quit"),
        message="Open chosen by its letter, Help not run",
    )


COMMAND_FIRST = """
import tkcurses as tk

root = tk.Tk()
bar = tk.Menu(root)
bar.add_command(label="Go", underline=0)
later = tk.Menu(bar, tearoff=0)
later.add_command(label="Inner")
bar.add_cascade(label="More", menu=later, underline=0)
root.config(menu=bar)
field = tk.Entry(root, name="field")
field.pack()
readout = tk.Label(root, anchor="w")
readout.pack(side="bottom", fill="x")
field.focus_set()

def show():
    readout["text"] = "focus=%s active=%s" % (root.focus_get(), bar.index("active"))
    root.after(50, show)

show()
root.after(20000, root.quit)
root.mainloop()
"""


def test_f10_on_a_bar_beginning_with_a_command_only_makes_it_active(terminal, tmp_path):
    """tk::MenuFirstEntry activates the entry and does not invoke it; the
    bar has the focus, Right and Down open the next menu, and Escape from
    there gives the focus back to the field, not to the bar."""
    term = terminal(cols=50, rows=10)
    term.run_source(COMMAND_FIRST, workdir=tmp_path)
    term.wait_for_text("focus=.field")
    term.send_keys("<F10>")
    term.wait_for(
        lambda t: t.contains("active=0") and not t.contains("focus=.field"),
        message="Go active and the bar focused",
    )
    term.send_keys("<Right>", "<Down>")
    term.wait_for(lambda t: t.contains("Inner"), message="More opened")
    term.send(ESCAPE)
    term.wait_for(
        lambda t: (
            not t.contains("Inner")
            and t.contains("focus=.field")
            and t.contains("active=None")
        ),
        message="everything closed and the focus back",
    )


def test_escape_on_the_bar_gives_the_focus_back(terminal, tmp_path):
    term = terminal(cols=50, rows=10)
    term.run_source(COMMAND_FIRST, workdir=tmp_path)
    term.wait_for_text("focus=.field")
    term.send_keys("<F10>")
    term.wait_for_text("active=0")
    term.send(ESCAPE)
    term.wait_for(
        lambda t: t.contains("focus=.field") and t.contains("active=None"),
        message="the bar left",
    )
