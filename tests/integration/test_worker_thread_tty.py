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

"""A worker thread updating widgets in a running program while a person types.

The usual shape of a tkinter program with background work: a thread does the
work and reports on the widgets as it goes - a status line, a log, a list, a
variable, a callback scheduled with ``after`` - and the person keeps using
the program meanwhile. test_core_dispatcher tests the queue that carries the
worker's calls to the main thread. This runs the whole program: the
widgets, the loop and the keyboard all at once.

It found that every curses call a widget method made from a worker waited
for the loop's idle wait to time out, up to 50 ms each; an update of a
Listbox took a second, and this program's 300 updates took minutes. The loop
now wakes when a call is queued.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

UPDATES = 300

APPLICATION = """
import sys
import threading
import time
import traceback

import tkcurses

root = tkcurses.Tk()
progress = tkcurses.IntVar(root)
status = tkcurses.Label(root, text='waiting', anchor='w')
status.place(x=0, y=0, width=48)
tkcurses.Label(root, textvariable=progress, anchor='w').place(x=0, y=1, width=10)
log = tkcurses.Text(root)
log.place(x=0, y=2, width=30, height=6)
items = tkcurses.Listbox(root)
items.place(x=31, y=2, width=17, height=6)
field = tkcurses.Entry(root)
field.place(x=0, y=9, width=40)
field.focus_set()

errors = []
scheduled = []


def work():
    try:
        began = time.monotonic()
        for i in range(UPDATES):
            status.configure(text='working %d' % i)
            progress.set(i)
            log.insert('end', 'line %d\\n' % i)
            log.see('end')
            items.insert('end', i)
            if items.size() > 20:
                items.delete(0)
            root.after(0, scheduled.append, i)
        took = time.monotonic() - began
        status.configure(text='DONE errors=%d took=%.1f' % (len(errors), took))
    except Exception:
        errors.append(traceback.format_exc())
        status.configure(text='WORKER FAILED')


def report_callback_exception(*info):
    errors.append(''.join(traceback.format_exception(*info)))


def report(event):
    buffer = root.tk.screen.buffer
    buffer.write(11, 0, ('typed=%s|' % field.get()).ljust(48))
    buffer.write(12, 0, ('scheduled=%d ordered=%s errors=%d' % (
        len(scheduled), scheduled == list(range(UPDATES)),
        len(errors))).ljust(48))
    root.tk.screen.refresh()
    for error in errors:
        sys.stderr.write(error)
    return 'break'


root.report_callback_exception = report_callback_exception
field.bind('<Key-F2>', report)
root.after(0, threading.Thread(target=work, daemon=True).start)
root.after(60000, root.quit)
root.mainloop()
""".replace("UPDATES", str(UPDATES))

TYPED = "the quick brown fox jumps over"


@pytest.fixture
def running(terminal, tmp_path):
    term = terminal(cols=50, rows=13)
    term.run_source(APPLICATION, workdir=tmp_path)
    term.wait_for_text("working")
    return term


def test_the_worker_finishes_and_the_typing_all_arrives(running):
    """Every update lands, every scheduled callback runs once and in order,
    and every key typed while the worker ran reached the field."""
    for word in TYPED.split(" "):
        running.send(word.encode() + b" ")
    running.wait_for_text("DONE", timeout=30)
    running.send(b"\x1bOQ")
    running.wait_for(
        lambda screen: "typed=" in screen.row(11) and "errors=" in screen.row(12)
    )
    assert running.row(11).startswith(f"typed={TYPED} |")
    assert running.row(12).startswith(f"scheduled={UPDATES} ordered=True errors=0")
    assert "DONE errors=0" in running.row(0)


def test_the_screen_shows_the_last_update(running):
    running.wait_for_text("DONE", timeout=30)
    last = UPDATES - 1
    running.wait_for(
        lambda screen: (
            str(last) in screen.row(1) and f"line {last}" in "\n".join(screen.display)
        )
    )
    assert running.row(1).strip() == str(last)
    assert f"line {last}" in "\n".join(running.display)
