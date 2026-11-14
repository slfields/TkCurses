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


#: Text that is not one cell a character, the same way. An ideograph takes
#: two cells and a combining mark none; the cursor, insstr's shift and
#: writing over half of an ideograph all follow from that.
WIDE_PROGRAM = """
import {module} as curses


def main(stdscr):
    stdscr.addstr(0, 0, "\\u65e5\\u672c")
    stdscr.addstr("x")
    stdscr.addstr(1, 0, "cafe\\u0301")
    stdscr.addstr("!")
    stdscr.addstr(2, 0, "abcdef")
    stdscr.insstr(2, 1, "\\u65e5")
    stdscr.addstr(3, 0, "\\u65e5\\u672c\\u8a9e")
    stdscr.addstr(3, 1, "z")
    stdscr.addstr(4, 0, "\\u65e5\\u672c")
    stdscr.addstr(4, 2, "q")
    stdscr.addch(5, 0, "\\u65e5")
    stdscr.addch("y")
    stdscr.addstr(7, 0, "done")
    stdscr.refresh()
    stdscr.getch()


curses.wrapper(main)
"""


def test_wide_text_draws_the_same_thing_either_way(terminal, tmp_path):
    """In cells, as curses counts them: it advanced one a character."""
    screens = []
    for module in ("tkcurses.curses", "curses"):
        term = terminal(cols=30, rows=9)
        term.run_source(WIDE_PROGRAM.format(module=module), workdir=tmp_path)
        term.wait_for_text("done")
        term.wait_for_idle()
        screens.append(term)
    ours, theirs = screens
    assert ours.display == theirs.display, (
        f"tkcurses.curses:\n{ours.describe()}\n\nstdlib curses:\n{theirs.describe()}"
    )
    ours.send(b"q")
    theirs.send(b"q")


#: A header and a footer around a scrolling region: scroll() both ways and
#: newlines at the bottom of the region.
SCROLL_REGION_PROGRAM = """
import {module} as curses


def main(stdscr):
    stdscr.scrollok(True)
    stdscr.addstr(0, 0, "HEADER")
    stdscr.addstr(6, 0, "FOOTER")
    for row in range(1, 6):
        stdscr.addstr(row, 0, "row %d" % row)
    stdscr.setscrreg(1, 5)
    stdscr.scroll(1)
    stdscr.scroll(-2)
    stdscr.move(5, 0)
    for n in range(3):
        stdscr.addstr("log %d\\n" % n)
    stdscr.addstr(7, 0, "done")
    stdscr.refresh()
    stdscr.getch()


curses.wrapper(main)
"""


def test_a_scrolling_region_draws_the_same_thing_either_way(terminal, tmp_path):
    screens = []
    for module in ("tkcurses.curses", "curses"):
        term = terminal(cols=20, rows=9)
        term.run_source(SCROLL_REGION_PROGRAM.format(module=module), workdir=tmp_path)
        term.wait_for_text("done")
        term.wait_for_idle()
        screens.append(term)
    ours, theirs = screens
    assert ours.display == theirs.display, (
        f"tkcurses.curses:\n{ours.describe()}\n\nstdlib curses:\n{theirs.describe()}"
    )
    ours.send(b"q")
    theirs.send(b"q")


# ------------------------------------------------- copies, pads and saving

#: Every call, in order, recorded to results.json: what it answered, or the
#: exception's type and words. The same source runs on both modules.
COPYING = """
import io, json, os
import {module} as curses

HERE = os.path.dirname(os.path.abspath(__file__))
results = []


def record(label, call):
    try:
        answer = call()
    except Exception as error:
        answer = [type(error).__name__, str(error)]
    results.append([label, answer])


def rows(window, count, width):
    return [window.instr(row, 0, width).decode() for row in range(count)]


def main(stdscr):
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLUE)
    a = curses.newwin(3, 6, 1, 1)
    a.addstr(0, 0, "ab de")
    a.addstr(1, 0, "  x   ")
    a.addstr(2, 0, "12345")
    for name in ("overlay", "overwrite"):
        b = curses.newwin(3, 6, 2, 3)
        b.bkgd(".")
        b.addstr(0, 0, "QQQQQQ")
        record(name, lambda: getattr(a, name)(b))
        record(name + " gives", lambda: rows(b, 3, 6))
        c = curses.newwin(4, 8, 10, 10)
        c.bkgd("-")
        record(name + " 7", lambda: getattr(a, name)(c, 0, 1, 1, 2, 2, 5))
        record(name + " 7 gives", lambda: rows(c, 4, 8))
        record(name + " off the source", lambda: getattr(a, name)(c, 0, 0, 0, 0, 2, 7))
        record(name + " off the dest", lambda: getattr(a, name)(c, 0, 0, 0, 0, 5, 5))
        record(name + " 3 args", lambda: getattr(a, name)(c, 0, 0))
        far = curses.newwin(2, 3, 20, 20)
        record(name + " apart", lambda: getattr(a, name)(far))
    bold = curses.newwin(1, 2, 0, 0)
    bold.addstr(0, 0, "B", curses.A_BOLD | curses.color_pair(1))
    under = curses.newwin(1, 2, 0, 0)
    bold.overlay(under)
    record("attributes copied", lambda: under.inch(0, 0) == bold.inch(0, 0))

    record("encoding", lambda: a.encoding)
    a.encoding = "latin-1"
    record("encoding set", lambda: a.encoding)
    record("subwin's", lambda: a.subwin(1, 1, 1, 1).encoding)
    record("derwin's", lambda: a.derwin(1, 1, 0, 0).encoding)
    record("encoding 5", lambda: setattr(a, "encoding", 5))
    record("del encoding", lambda: delattr(a, "encoding"))

    pad = curses.newpad(5, 100)
    pad.addstr(0, 0, "pad row zero " + "z" * 80)
    pad.addstr(4, 90, "corner")
    record("pad", lambda: (pad.getbegyx(), pad.getmaxyx()))
    record("refresh()", lambda: pad.refresh())
    record("noutrefresh()", lambda: pad.noutrefresh())
    record("window refresh 6", lambda: a.refresh(0, 0, 0, 0, 1, 1))
    record("window noutrefresh 6", lambda: a.noutrefresh(0, 0, 0, 0, 1, 1))
    record("rows beyond", lambda: pad.refresh(0, 0, 0, 0, curses.LINES, 5))
    record("cols beyond", lambda: pad.refresh(0, 0, 0, 0, 1, curses.COLS))
    record("inside out", lambda: pad.refresh(0, 0, 3, 0, 1, 5))
    record("mvwin", lambda: pad.mvwin(1, 1))
    record("newpad 0", lambda: curses.newpad(0, 5))
    record("subpad", lambda: pad.subpad(2, 5, 0, 4).instr(0, 0, 5).decode())
    stdscr.clear()
    stdscr.refresh()
    pad.refresh(0, 4, 14, 2, 14, 20)
    pad.refresh(4, 88, 15, 2, 20, 40)

    w = curses.newwin(2, 5, 3, 7)
    w.addstr(0, 0, "\\\\", curses.color_pair(1))
    w.addstr(0, 1, "r s", curses.A_REVERSE | curses.A_UNDERLINE)
    w.move(1, 2)
    w.keypad(True)
    w.scrollok(True)
    w.bkgdset("~", curses.A_DIM)
    w.attrset(curses.A_BOLD | curses.color_pair(1))
    saved = io.BytesIO()
    w.putwin(saved)
    with open(os.path.join(HERE, "{module}.win"), "wb") as file:
        file.write(saved.getvalue())
    saved.seek(0)
    back = curses.getwin(saved)
    record("getwin", lambda: (
        back.getbegyx(), back.getmaxyx(), back.getyx(),
        [back.inch(0, x) for x in range(5)], rows(back, 2, 5),
    ))
    record("getwin junk", lambda: curses.getwin(io.BytesIO(b"junk")))
    record("getwin text", lambda: curses.getwin(io.StringIO("x")))
    record("putwin text", lambda: w.putwin(io.StringIO()))

    with open(os.path.join(HERE, "results.json"), "w") as file:
        json.dump(results, file)
    stdscr.addstr(0, 0, "done")
    stdscr.refresh()
    stdscr.getch()


curses.wrapper(main)
"""


def run_copying(terminal, tmp_path, module):
    term = terminal(cols=60, rows=24)
    term.run_source(COPYING.format(module=module), workdir=tmp_path)
    term.wait_for_text("done")
    term.wait_for_idle()
    import json

    return term, json.loads((tmp_path / "results.json").read_text())


def test_copies_pads_encoding_and_saving_answer_as_curses_does(terminal, tmp_path):
    ours, our_results = run_copying(terminal, tmp_path, "tkcurses.curses")
    theirs, their_results = run_copying(terminal, tmp_path, "curses")
    assert our_results == their_results
    assert ours.display == theirs.display, (
        f"tkcurses.curses:\n{ours.describe()}\n\nstdlib curses:\n{theirs.describe()}"
    )
    ours.send(b"q")
    theirs.send(b"q")


#: Reads a window the other module saved, with this one's getwin.
READING = """
import json, os
import {module} as curses

HERE = os.path.dirname(os.path.abspath(__file__))


def main(stdscr):
    with open(os.path.join(HERE, "{saved}.win"), "rb") as file:
        back = curses.getwin(file)
    found = [
        back.getbegyx(), back.getmaxyx(), back.getyx(),
        [back.inch(0, x) for x in range(5)],
        [back.instr(row, 0, 5).decode() for row in range(2)],
    ]
    with open(os.path.join(HERE, "read-{saved}.json"), "w") as file:
        json.dump(found, file)
    stdscr.addstr(0, 0, "read")
    stdscr.refresh()
    stdscr.getch()


curses.wrapper(main)
"""


def test_each_reads_the_window_the_other_saved(terminal, tmp_path):
    """ncurses' format both ways: the standard library's getwin reads what
    this module's putwin wrote, and this module's reads the standard
    library's, and both make the same window of it."""
    import json

    for module in ("tkcurses.curses", "curses"):
        term, _ = run_copying(terminal, tmp_path, module)
        term.send(b"q")
        term.wait_for_exit(timeout=10)
    answers = {}
    for reader, saved in (("curses", "tkcurses.curses"), ("tkcurses.curses", "curses")):
        term = terminal(cols=60, rows=24)
        term.run_source(READING.format(module=reader, saved=saved), workdir=tmp_path)
        term.wait_for_text("read")
        answers[reader] = json.loads((tmp_path / f"read-{saved}.json").read_text())
        term.send(b"q")
    assert answers["curses"] == answers["tkcurses.curses"]
