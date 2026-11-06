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

"""A curses program, run against this layer on a real terminal.

The strongest test here is the one that runs the *same source* twice - once
importing the standard library's curses and once importing this module - and
compares what each put on the screen. Anything that layer gets wrong shows up
as a difference, which is a far better question than a list of assertions
about what it ought to have drawn.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

#: A curses program written the way curses programs are written. The import
#: is the only thing that changes between the two runs.
PROGRAM = """
import {module} as curses


def main(stdscr):
    stdscr.addstr(0, 0, "top level")
    stdscr.addstr(8, 0, "after the window")
    stdscr.refresh()
    win = curses.newwin(5, 20, 2, 4)
    win.box()
    win.addstr(1, 1, "in a window")
    win.addstr(2, 1, "second line")
    win.refresh()
    stdscr.getch()


curses.wrapper(main)
"""


def run_program(terminal, tmp_path, module, **kwargs):
    """Run the program against one curses module and wait for it to draw."""
    term = terminal(cols=40, rows=12, **kwargs)
    term.run_source(PROGRAM.format(module=module), workdir=tmp_path)
    term.wait_for_text("after the window")
    term.wait_for_idle()
    return term


def test_the_same_program_draws_the_same_thing_either_way(terminal, tmp_path):
    """The question worth asking, asked once.

    A curses program does not know or care which module it imported, so the
    two screens have to match. Where they differ, this layer is wrong.
    """
    ours = run_program(terminal, tmp_path, "tkcurses.curses")
    theirs = run_program(terminal, tmp_path, "curses")
    assert ours.display == theirs.display, (
        f"tkcurses.curses:\n{ours.describe()}\n\nstdlib curses:\n{theirs.describe()}"
    )
    ours.send(b"q")
    theirs.send(b"q")


def test_a_window_is_drawn_where_it_was_put(terminal, tmp_path):
    term = run_program(terminal, tmp_path, "tkcurses.curses")
    assert term.row(0).startswith("top level")
    row = next(i for i, line in enumerate(term.display) if "in a window" in line)
    assert row == 3, term.describe()
    assert term.display[row].index("in a window") == 5, term.describe()
    term.send(b"q")


def test_a_box_is_drawn_round_it(terminal, tmp_path):
    term = run_program(terminal, tmp_path, "tkcurses.curses")
    assert "┌" in term.display[2] and "┐" in term.display[2], term.describe()
    assert "└" in term.display[6] and "┘" in term.display[6], term.describe()
    term.send(b"q")


def test_wrapper_gives_the_terminal_back(terminal, tmp_path):
    """The entire reason curses has wrapper(), and the reason to use it."""
    term = terminal(cols=40, rows=10, stderr_to_terminal=True)
    term.run_source(
        """
import tkcurses.curses as curses

def main(stdscr):
    stdscr.addstr(0, 0, "inside")
    stdscr.refresh()
    raise RuntimeError("the program failed")

try:
    curses.wrapper(main)
except RuntimeError:
    print("terminal given back")
""",
        workdir=tmp_path,
    )
    assert term.wait_for_exit(timeout=10) == 0
    term.wait_for_text("terminal given back")


# ------------------------------------------------------------------- colour


COLOUR = """
import {module} as curses


def main(stdscr):
    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_GREEN)
    stdscr.addstr(0, 0, "red on black", curses.color_pair(1))
    stdscr.addstr(1, 0, "black on green", curses.color_pair(2))
    stdscr.addstr(2, 0, "colours=%s change=%s" % (
        curses.has_colors(), curses.can_change_color()))
    stdscr.refresh()
    stdscr.getch()


curses.wrapper(main)
"""


def test_a_colour_pair_reaches_the_terminal(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    term.run_source(COLOUR.format(module="tkcurses.curses"), workdir=tmp_path)
    term.wait_for_text("colours=")
    term.wait_for_idle()
    assert term.attrs_at(0, 0)["fg"] == "red", term.describe()
    assert term.attrs_at(1, 0)["bg"] == "green", term.describe()
    term.send(b"q")


def test_colour_is_reported_the_same_way_as_the_real_curses(terminal, tmp_path):
    ours = terminal(cols=40, rows=8)
    ours.run_source(COLOUR.format(module="tkcurses.curses"), workdir=tmp_path)
    ours.wait_for_text("colours=")
    ours.wait_for_idle()
    theirs = terminal(cols=40, rows=8)
    theirs.run_source(COLOUR.format(module="curses"), workdir=tmp_path)
    theirs.wait_for_text("colours=")
    theirs.wait_for_idle()
    assert ours.display == theirs.display
    ours.send(b"q")
    theirs.send(b"q")


ASKS = """
import {module} as curses


def main(stdscr):
    curses.start_color()
    stdscr.addstr(0, 0, "colours=%s change=%s" % (
        curses.has_colors(), curses.can_change_color()))
    stdscr.refresh()
    stdscr.getch()


curses.wrapper(main)
"""


@pytest.mark.parametrize(
    ("term_name", "expected"),
    [("vt100", "colours=False"), ("xterm-256color", "colours=True")],
)
def test_colour_support_is_reported_truthfully(terminal, tmp_path, term_name, expected):
    """The specification said has_colors() should answer True always.

    It should not. A vt100 has no colour, and a curses program asks precisely
    so it can draw differently. Both modules are run on the same terminal,
    because agreeing with the real curses is the only thing that settles it.
    """
    answers = {}
    for module in ("tkcurses.curses", "curses"):
        term = terminal(cols=40, rows=8, env={"TERM": term_name})
        term.run_source(ASKS.format(module=module), workdir=tmp_path)
        term.wait_for_text("colours=")
        term.wait_for_idle()
        answers[module] = term.row(0).strip()
        term.send(b"q")
    assert answers["tkcurses.curses"].startswith(expected), answers
    assert answers["tkcurses.curses"] == answers["curses"], answers


# -------------------------------------------------------------- overlapping


OVERLAP = """
import {module} as curses


def main(stdscr):
    stdscr.refresh()
    back = curses.newwin(4, 20, 1, 1)
    front = curses.newwin(4, 20, 2, 5)
    back.addstr(1, 1, "BACKBACKBACK")
    front.addstr(1, 1, "FRONT")
    back.refresh()
    front.refresh()
    stdscr.addstr(7, 0, "done")
    stdscr.refresh()
    stdscr.getch()


curses.wrapper(main)
"""


def test_the_window_refreshed_last_is_the_one_on_top(terminal, tmp_path):
    """curses' rule, and the one a window model has to get right: writing
    into a window changes nothing until it is refreshed."""
    screens = {}
    for module in ("tkcurses.curses", "curses"):
        term = terminal(cols=40, rows=10)
        term.run_source(OVERLAP.format(module=module), workdir=tmp_path)
        term.wait_for_text("done")
        term.wait_for_idle()
        screens[module] = list(term.display)
        term.send(b"q")
    assert screens["tkcurses.curses"] == screens["curses"], (
        "\n".join(screens["tkcurses.curses"]) + "\n---\n" + "\n".join(screens["curses"])
    )
    assert "FRONT" in "\n".join(screens["tkcurses.curses"])


# ------------------------------------------------------------------- input


def test_a_key_read_through_the_window_is_the_key_that_was_typed(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    term.run_source(
        """
import tkcurses.curses as curses

def main(stdscr):
    stdscr.keypad(True)
    stdscr.addstr(0, 0, "ready")
    stdscr.refresh()
    while True:
        key = stdscr.getch()
        if key == ord("q"):
            break
        stdscr.addstr(1, 0, "key=%s name=%s   " % (key, curses.keyname(key)))
        stdscr.refresh()

curses.wrapper(main)
""",
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send(b"a")
    term.wait_for_text("key=97")
    term.send_keys("<Up>")
    term.wait_for_text("KEY_UP")
    term.send(b"q")
    assert term.wait_for_exit(timeout=10) == 0


CLEARED = """
import tkcurses
from tkcurses import curses

root = tkcurses.Tk()
tkcurses.Label(root, text='a widget').pack(side='bottom')

def draw():
    curses.initscr()
    window = curses.newwin(3, 20, 1, 1)
    window.clearok(True)
    window.addstr(1, 1, 'curses text')
    window.refresh()

root.after(100, draw)
root.after(6000, root.quit)
root.mainloop()
"""


def test_clearok_repaints_the_widgets_beside_a_window(terminal, tmp_path):
    """clearok asks for the whole screen to be painted again, and in an
    application the widgets are part of the screen. Painting only the
    curses half wiped them. TkCurses-wbpi."""
    term = terminal(cols=40, rows=8)
    term.run_source(CLEARED, workdir=tmp_path)
    term.wait_for(
        lambda t: t.contains("curses text") and t.contains("a widget"),
        message="the window and the widget",
    )
    term.wait_for_idle()
    assert term.contains("a widget"), term.describe()


UNLOOPED = """
import time

import tkcurses
from tkcurses import curses

root = tkcurses.Tk()
tkcurses.Label(root, text='a widget').pack(side='bottom')
root.update()
curses.initscr()
window = curses.newwin(3, 20, 1, 1)
window.clearok(True)
window.addstr(1, 1, 'curses text')
window.refresh()
time.sleep(5)
"""


def test_clearok_puts_the_widgets_back_without_a_main_loop(terminal, tmp_path):
    """The repaint sends the widgets itself, rather than leaving them to the
    main loop's next pass - a program drawing with update() and no loop
    has no next pass."""
    term = terminal(cols=40, rows=8)
    term.run_source(UNLOOPED, workdir=tmp_path)
    term.wait_for(
        lambda t: t.contains("curses text") and t.contains("a widget"),
        message="the window and the widget",
    )
