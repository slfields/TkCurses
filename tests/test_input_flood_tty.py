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

"""A terminal sending faster than the program handles: TkCurses-tcbj.21.

A drag across a large screen, or a long paste, used to hold the loop in
input until it stopped - a 10 ms timer ran once in seven seconds of drag
reports - and every key typed into a Text repainted it twice.
"""

from __future__ import annotations

import re

import pytest

pytestmark = pytest.mark.tty

DRAG = """
import tkcurses as tk

root = tk.Tk()
frame = tk.Frame(root, width=60, height=10)
frame.place(x=0, y=0)
seen = {"motion": 0, "ticks": 0, "last": None}

def motion(event):
    seen["motion"] += 1
    seen["last"] = (event.x, event.y)

frame.bind("<B1-Motion>", motion)

def tick():
    seen["ticks"] += 1
    root.after(10, tick)

def report(event):
    status["text"] = "ticks=%(ticks)d motion=%(motion)d last=%(last)s" % seen

root.bind("<Key-q>", report)
status = tk.Label(root, text="ready")
status.place(x=0, y=12)
root.after(10, tick)
root.after(20000, root.quit)
root.mainloop()
"""


def test_a_drag_flood_leaves_the_loop_time_for_its_timers(terminal):
    term = terminal(80, 14)
    term.run_source(DRAG)
    term.wait_for_text("ready")
    term.send_mouse(5, 5, action="press")
    reports = 20_000
    # One write: as fast as the terminal can deliver them, which is faster
    # than a handler can run.
    term.send(
        b"".join(f"\x1b[<32;{2 + i % 50};{2 + i % 8}M".encode() for i in range(reports))
    )
    last = reports - 1
    term.send_mouse(5, 5, action="release")
    term.send(b"q")
    term.wait_for(lambda t: "motion=" in t.display[12], timeout=60)
    found = re.search(r"ticks=(\d+) motion=(\d+) last=(.*)", term.display[12])
    assert found is not None
    ticks, motion = int(found.group(1)), int(found.group(2))
    # Collapsed, as Tk collapses motion: far fewer calls than reports, and
    # the last one at the last place the pointer was.
    assert motion < reports // 10
    assert found.group(3).strip() == f"({1 + last % 50}, {1 + last % 8})"
    # Timers ran while it lasted; before, one tick in the whole flood.
    assert ticks >= 5


TYPING = """
import tkcurses as tk

paints = []
original = tk.Text._paint

def counted(self):
    paints.append(1)
    original(self)

tk.Text._paint = counted
root = tk.Tk()
text = tk.Text(root, width=40, height=5)
text.place(x=0, y=0)
status = tk.Label(root, text="ready")
status.place(x=0, y=8)
text.focus_set()
start = []

def watch():
    if not start and paints:
        start.append(len(paints))
    if len(text.get("1.0", "end-1c")) >= 600:
        status["text"] = "typed paints=%d" % (len(paints) - start[0])
        return
    root.after(5, watch)

root.after(5, watch)
root.after(20000, root.quit)
root.mainloop()
"""


def test_a_burst_of_typing_paints_the_text_once_a_pass(terminal):
    """Each key repainted the Text at once, twice; now it is repainted when
    the screen is next shown, as Tk's text widget repaints when idle."""
    term = terminal(60, 10)
    term.run_source(TYPING)
    term.wait_for_text("ready")
    term.send(b"x" * 600)
    term.wait_for(lambda t: "typed paints=" in t.display[8], timeout=60)
    found = re.search(r"typed paints=(\d+)", term.display[8])
    assert found is not None
    # 600 keys arrive in a few passes of the loop; before, 1200 paints.
    assert int(found.group(1)) < 30
    term.wait_for_cell(5, 1, lambda cell: cell.data == "x")
