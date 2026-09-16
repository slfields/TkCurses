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

"""A curses program, run against this layer or against the real curses.

What to do: run it twice and compare. The only thing that changes is which
curses it imported::

    python3 -m uat 32                       # tkcurses.curses
    TKCURSES_UAT_BACKEND=stdlib python3 -m uat 32   # the standard library

The comparison is the test. A curses program does not know or care which
module it imported, so the two screens should be the same; anywhere they are
not, this layer is wrong. The top line says which one is running, so there is
no doubt about which screen you are looking at.

What to look for: the window and its box in the same place both ways; the
three panels stacking, hiding and moving the same way; the colours the same;
and the line reporting has_colors() agreeing. Then resize the terminal and
compare again.

Keys: `1` `2` `3` raise that panel, `h` hides the top one, `s` shows
everything again, `m` moves the top panel, Escape quits.

Also worth running: `python3 -m tkcurses`, which puts widgets and a curses
window on one screen in one process - the thing this whole cycle is for.
"""

from __future__ import annotations

import os

#: Which curses to run against. The scenario is otherwise identical, which is
#: the entire point of it.
BACKEND = os.environ.get("TKCURSES_UAT_BACKEND", "tkcurses")

if BACKEND == "stdlib":
    import curses
    import curses.panel as panel
else:
    from tkcurses import curses, panel

TITLE = "32 - curses: the same program on either backend"

#: What each panel says and where it starts, back to front.
PANELS = [
    ("ONE   back", 4, 2),
    ("TWO   middle", 6, 12),
    ("THREE front", 8, 22),
]


def build(stdscr):
    """Draw everything that does not change, and make the three panels."""
    stdscr.addstr(0, 0, f" {TITLE} ")
    stdscr.addstr(1, 0, f"  backend: {BACKEND}   (TKCURSES_UAT_BACKEND=stdlib)")
    have = curses.has_colors()
    stdscr.addstr(
        2,
        0,
        f"  has_colors={have}  can_change_color={curses.can_change_color()}",
    )
    if have:
        curses.start_color()
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_GREEN)
        stdscr.addstr(3, 2, "red on black  ", curses.color_pair(1))
        stdscr.addstr(3, 18, " black on green ", curses.color_pair(2))
    stdscr.addstr(14, 0, "  1 2 3 raise   h hide top   s show all   m move top")
    stdscr.addstr(15, 0, "  Escape quits")
    stdscr.refresh()

    panels = []
    for text, top, left in PANELS:
        window = curses.newwin(4, 18, top, left)
        window.box()
        window.addstr(1, 1, text)
        window.addstr(2, 1, "panel")
        panels.append(panel.new_panel(window))
    return panels


def main(stdscr):
    """Draw, then take keys until Escape."""
    stdscr.keypad(True)
    panels = build(stdscr)
    moved = False
    while True:
        panel.update_panels()
        curses.doupdate()
        key = stdscr.getch()
        if key == 27:  # Escape
            return 0
        if key in (ord("1"), ord("2"), ord("3")):
            panels[key - ord("1")].top()
        elif key == ord("h"):
            top = panel.top_panel()
            if top is not None:
                top.hide()
        elif key == ord("s"):
            for one in panels:
                one.show()
        elif key == ord("m"):
            top = panel.top_panel()
            if top is not None:
                moved = not moved
                top.move(10 if moved else 8, 30 if moved else 22)
        elif key == getattr(curses, "KEY_RESIZE", -2):
            stdscr.clear()
            build(stdscr)


def run() -> int:
    """Run the scenario, and give the terminal back however it ends.

    The runner calls this instead of ``_support.run`` because this scenario
    has no root and no widgets: ``wrapper`` is what guarantees teardown for a
    curses program, and it is what a curses program would use anyway.
    """
    return int(curses.wrapper(main))


if __name__ == "__main__":
    raise SystemExit(run())
