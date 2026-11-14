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

"""A curses program: a pad far longer than the screen, scrolled with the keys.

Up and Down move a line, Page Up and Page Down a screen, Home and End to
either end; q quits. It is written against curses, and the only TkCurses in
it is the import: change it to ``import curses`` and it runs on the standard
library's.
"""

import contextlib

import tkcurses.curses as curses

LINES = 200


def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    height, width = stdscr.getmaxyx()
    # The pad holds every line, wider and longer than the screen; refresh
    # shows the part of it that fits under the title.
    pad = curses.newpad(LINES, width)
    for number in range(LINES):
        pad.addstr(number, 0, f"line {number + 1:03d}  " + "~" * (number % 30))
    view = height - 2
    top = 0
    while True:
        stdscr.erase()
        stdscr.addstr(0, 0, f"A pad of {LINES} lines", curses.A_BOLD)
        stdscr.addstr(height - 1, 0, "Up Down PgUp PgDn Home End, q quits"[: width - 1])
        stdscr.noutrefresh()
        pad.noutrefresh(top, 0, 1, 0, view, width - 1)
        curses.doupdate()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            break
        moves = {
            curses.KEY_UP: -1,
            curses.KEY_DOWN: 1,
            curses.KEY_PPAGE: -view,
            curses.KEY_NPAGE: view,
            curses.KEY_HOME: -LINES,
            curses.KEY_END: LINES,
        }
        top = max(0, min(LINES - view, top + moves.get(key, 0)))


# wrapper gives the terminal back before Ctrl-C reaches here.
with contextlib.suppress(KeyboardInterrupt):
    curses.wrapper(main)
