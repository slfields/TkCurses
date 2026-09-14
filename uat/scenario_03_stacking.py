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

"""Two windows, and which one is in front.

What to do: press 1 to raise the left window, 2 to raise the right one.
What to look for: the raised window's border is unbroken and it covers the
other where they overlap. Pressing the same key twice changes nothing.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "03 - stacking"


def build(root, screen):
    left = tkcurses.Toplevel(root, width=26, height=8)
    left.title("one")
    left.geometry("26x8+4+4")
    right = tkcurses.Toplevel(root, width=26, height=8)
    right.title("two")
    right.geometry("26x8+16+7")

    screen.lines(2, ["1 raises 'one', 2 raises 'two'."])
    root.bind("<Key-1>", lambda event: left.tkraise())
    root.bind("<Key-2>", lambda event: right.tkraise())


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
