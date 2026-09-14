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

"""Moving, hiding and resizing a window.

What to do: press m to move it, h to hide it, s to show it, f for fullscreen,
r to restore.
What to look for: the window moves in whole cells with no smearing, hiding
leaves the text behind it intact, and fullscreen fills the terminal exactly to
the edges.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "04 - window manager"


def build(root, screen):
    for row in range(3, screen.height - 2):
        screen.line(row, f"{row:>3} " + "." * (screen.width - 4))
    window = tkcurses.Toplevel(root, width=30, height=8)
    window.title("movable")
    positions = iter(["+2+3", "+20+6", "+8+10", "+30+4"])

    def move(event):
        nonlocal positions
        try:
            window.geometry(next(positions))
        except StopIteration:
            positions = iter(["+2+3", "+20+6", "+8+10", "+30+4"])
            window.geometry("+2+3")

    screen.lines(1, ["m move   h hide   s show   f fullscreen   r restore"])
    root.bind("<Key-m>", move)
    root.bind("<Key-h>", lambda event: window.withdraw())
    root.bind("<Key-s>", lambda event: window.deiconify())
    root.bind("<Key-f>", lambda event: window.attributes("-fullscreen", True))
    root.bind("<Key-r>", lambda event: window.geometry("30x8+2+3"))


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
