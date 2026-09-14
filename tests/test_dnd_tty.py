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

"""A whole drag, driven by a real mouse through a real terminal.

The unit tests hand the handler events. This one sends the escape sequences
a terminal sends, which is the only way to check the part nothing else can:
that motion with a button held arrives at all, and that the release which
ends the drag matches the <Bn-ButtonRelease-n> pattern the handler builds.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

PROGRAM = """
import tkcurses
from tkcurses import dnd

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
log = []


def note(text):
    log.append(text)
    # Only the last few, and the line is blanked first: a log that grows
    # without bound runs off a sixty-column screen and takes the end of the
    # drag - the part these tests are about - off with it.
    del log[: max(0, len(log) - 4)]
    buffer.write(0, 0, " " * 58)
    buffer.write(0, 0, ("log: " + " ".join(log))[:58])
    root.tk.screen.refresh()


def restart(event):
    del log[:]
    note("start")
    dnd.dnd_start(parcel, event)


class Parcel:
    name = "box"

    def dnd_end(self, target, event):
        note("end=%s" % (getattr(target, "name", target),))


class Bin(tkcurses.Frame):
    def __init__(self, master, name, **kw):
        super().__init__(master, relief="solid", **kw)
        self.name = name
        tkcurses.Label(self, text=name).pack()
        self.pack_propagate(False)

    def dnd_accept(self, source, event):
        return self

    def dnd_enter(self, source, event):
        note("enter=%s" % self.name)

    def dnd_leave(self, source, event):
        note("leave=%s" % self.name)

    def dnd_motion(self, source, event):
        pass

    def dnd_commit(self, source, event):
        note("commit=%s" % self.name)


left = Bin(root, "LEFT", width=18, height=5)
left.place(x=0, y=2)
right = Bin(root, "RIGHT", width=18, height=5)
right.place(x=22, y=2)
parcel = Parcel()

left.bind("<Button-1>", restart)
root.update_layout()
buffer.write(1, 0, "ready")
root.tk.screen.refresh()
root.after(8000, root.quit)
root.mainloop()
"""


def start(term, tmp_path):
    term.run_source(PROGRAM, workdir=tmp_path)
    term.wait_for_text("ready")
    term.wait_for_idle()


def drag(term, path, release_at):
    """Press at the first point, move through the rest, release."""
    term.send_mouse(*path[0], action="press")
    term._drain(0.08)
    for point in path[1:]:
        term.send_mouse(*point, action="move", button=1)
        term._drain(0.08)
    term.send_mouse(*release_at, action="release")


def test_a_drag_from_one_widget_to_another_commits_there(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    start(term, tmp_path)
    drag(term, [(4, 4), (10, 4), (26, 4), (28, 4)], (28, 4))
    term.wait_for_text("commit=RIGHT")
    term.wait_for(lambda t: t.contains("end=RIGHT"), message="the source to be told")


def test_the_target_is_entered_and_left_as_the_pointer_crosses(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    start(term, tmp_path)
    term.send_mouse(4, 4, action="press")
    term._drain(0.08)
    term.send_mouse(6, 4, action="move", button=1)
    term.wait_for_text("enter=LEFT")
    term.send_mouse(26, 4, action="move", button=1)
    term.wait_for(
        lambda t: t.contains("leave=LEFT") and t.contains("enter=RIGHT"),
        message="the crossing",
    )
    term.send_mouse(26, 4, action="release")


def test_a_drag_released_over_nothing_still_tells_the_source(terminal, tmp_path):
    """dnd_end is the one call that always happens, so a source can put
    itself back when nobody wanted it."""
    term = terminal(cols=60, rows=14)
    start(term, tmp_path)
    drag(term, [(4, 4), (40, 12)], (40, 12))
    term.wait_for_text("end=None")


def test_the_drag_is_over_afterwards_so_another_can_start(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    start(term, tmp_path)
    drag(term, [(4, 4), (26, 4)], (26, 4))
    term.wait_for_text("commit=RIGHT")
    # The log is cleared as each drag starts, so the second commit appearing
    # after it has gone means a second drag really ran.
    term.send_mouse(4, 4, action="press")
    term.wait_for(lambda t: not t.contains("commit="), message="a fresh log")
    term.send_mouse(26, 4, action="move", button=1)
    term._drain(0.08)
    term.send_mouse(26, 4, action="release")
    term.wait_for_text("commit=RIGHT")
