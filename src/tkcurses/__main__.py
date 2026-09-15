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

"""``python -m tkcurses`` - the two halves of the library in one program.

Widgets on the left, drawn the tkinter way. A curses window on the right,
drawn the curses way, in the same process and on the same screen. They are
not two applications taking turns: the curses window attaches to the screen
the widgets are already using, and one refresh paints both.

That is the claim the library makes, and this is the smallest thing that
either demonstrates it or shows it failing.

Run it with ``python -m tkcurses``. Escape quits.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import tkcurses
from tkcurses import curses as tcurses
from tkcurses import panel as tpanel

if TYPE_CHECKING:
    from tkcurses.curses import Window

#: What the curses half draws, so the test can look for it.
CURSES_TITLE = "curses window"

#: What the widget half says when a button is pressed.
PRESSED = "the widget half answered"


def build_widgets(root: tkcurses.Tk) -> tkcurses.Label:
    """The tkinter half: a frame of ordinary widgets down the left."""
    frame = tkcurses.Frame(root, name="widgets", relief="solid")
    frame.place(x=0, y=0, relheight=1.0, width=30)

    tkcurses.Label(frame, text="widget half", anchor="w").pack(fill="x", padx=1)
    answer = tkcurses.Label(frame, text="press the button", anchor="w")
    answer.pack(fill="x", padx=1)

    entry = tkcurses.Entry(frame, name="field")
    entry.pack(fill="x", padx=1, pady=1)
    entry.insert(0, "type here")

    def press() -> None:
        answer.configure(text=PRESSED)

    tkcurses.Button(frame, text="Press", command=press).pack(pady=1)
    listbox = tkcurses.Listbox(frame, height=4)
    listbox.pack(fill="x", padx=1)
    listbox.insert("end", "one", "two", "three", "four")
    return answer


def build_curses(root: tkcurses.Tk) -> Window:
    """The curses half: a window and a panel, on the screen already running.

    ``initscr`` finds the application's screen rather than starting one, so
    what this draws lands in the same cells the widgets drew into.
    """
    stdscr = tcurses.initscr()
    del stdscr  # the application owns the screen; this half wants a window
    width = max(20, root.winfo_screenwidth() - 34)
    window = tcurses.newwin(9, width, 2, 32)
    window.box()
    window.addstr(1, 2, CURSES_TITLE)
    window.addstr(2, 2, "drawn with addstr")
    window.addstr(3, 2, "boxed with box()")
    window.addstr(5, 2, "same screen, same refresh")
    tpanel.new_panel(window)
    return window


def paint_curses() -> None:
    """Put the curses half back on the screen.

    Needed after every widget repaint, because the widgets own the buffer
    and will have drawn over whatever was in it.
    """
    tpanel.update_panels()


def main(argv: list[str] | None = None) -> int:
    """Run the demo. Returns an exit code, so this can be pointed at CI."""
    del argv
    root = tkcurses.Tk()
    root.title(" tkcurses ")
    try:
        build_widgets(root)
        window = build_curses(root)
        root.update_layout()

        def repaint(event: object = None) -> None:
            del event
            paint_curses()
            screen = root.tk.screen
            if screen is not None:
                screen.refresh()

        # After a resize the widgets lay out again and paint over everything,
        # so the curses half has to be put back.
        root.bind("<Configure>", repaint, add="+")
        root.bind("<Key-Escape>", lambda _event: root.quit())
        root.after(50, repaint)
        root.mainloop()
        del window
    finally:
        tcurses.endwin()
        root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
