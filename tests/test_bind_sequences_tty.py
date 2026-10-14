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


"""Multi-event sequences with real terminal bytes: Ctrl-X then Ctrl-S.

Ctrl-S is XOFF to a terminal with flow control on, which would freeze the
output and never reach the program; the input layer turns flow control off,
and this is where that is seen to hold. TkCurses-jfm.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

CHORDS = """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
pad = tkcurses.Frame(root, width=10, height=3)
pad.place(x=0, y=2)
seen = []


def show(text):
    seen.append(text)
    buffer.write(0, 0, ("seen=" + ",".join(seen)).ljust(38))
    root.tk.screen.refresh()


pad.bind("<Control-x><Control-s>", lambda event: show("save"))
pad.bind("gg", lambda event: show("top"))
pad.bind("<Key>", lambda event: show(event.keysym))
pad.focus_set()
root.update_layout()
show("ready")
root.after(6000, root.quit)
root.mainloop()
"""


@pytest.fixture
def chords(terminal, tmp_path):
    term = terminal(cols=40, rows=6)
    term.run_source(CHORDS, workdir=tmp_path)
    term.wait_for_text("seen=ready")
    return term


def test_ctrl_x_then_ctrl_s_fires_the_chord(chords):
    chords.send(b"\x18")
    chords.wait_for_text("seen=ready,x")
    chords.send(b"\x13")
    chords.wait_for_text("seen=ready,x,save")


def test_a_key_in_between_cancels_it(chords):
    chords.send(b"\x18")
    chords.wait_for_text("seen=ready,x")
    chords.send(b"a")
    chords.wait_for_text("seen=ready,x,a")
    chords.send(b"\x13")
    chords.wait_for_text("seen=ready,x,a,s")
    assert "save" not in chords.row(0)


def test_bare_characters_are_a_chord_too(chords):
    chords.send(b"g")
    chords.wait_for_text("seen=ready,g")
    chords.send(b"g")
    chords.wait_for_text("seen=ready,g,top")
