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
from typing import TYPE_CHECKING, Any

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
    if tcurses.isendwin():
        tcurses.initscr()
    width = max(20, root.winfo_screenwidth() - 34)
    height = max(5, min(9, root.winfo_screenheight() - 4))
    window = tcurses.newwin(height, width, 2, 32)
    window.box()
    lines = [
        CURSES_TITLE,
        "drawn with addstr",
        "boxed with box()",
        "",
        "same screen, same refresh",
    ]
    for row, line in enumerate(lines[: height - 2], start=1):
        window.addstr(row, 2, line)
    return window


def main(argv: list[str] | None = None) -> int:
    """Run the demo. Returns an exit code, so this can be pointed at CI."""
    del argv
    root = tkcurses.Tk()
    root.title(" tkcurses ")
    try:
        build_widgets(root)
        panel = tpanel.new_panel(build_curses(root))

        def repaint(event: object = None) -> None:
            """Put both halves back on the screen, in the order they stack.

            A full repaint rather than the changed cells, because a terminal
            resize clears the terminal underneath a double-buffered
            application: the buffer still holds what it drew, so nothing is
            dirty and nothing would be sent.

            The application's repaint puts the widget panels back over it,
            since they are real curses panels above stdscr.
            """
            del event
            tpanel.update_panels()
            root.tk.repaint()

        def resized(event: Any = None) -> None:
            """Rebuild the curses half at the size the terminal now is.

            A curses window does not resize itself, and one built for eighty
            columns on a screen that is now seventy is drawn clipped - the
            box came back with pieces missing. curses programs handle
            KEY_RESIZE by rebuilding, and so does this.

            The widget check is the tkinter idiom and not a detail: a child's
            ``<Configure>`` reaches its toplevel's bindings, because the
            toplevel is one of the child's binding tags. Without it every
            widget being laid out rebuilds the curses half, which is a good
            way to have nothing on the screen at all.
            """
            if event is not None and getattr(event, "widget", root) is not root:
                return
            root.update_layout()
            panel.replace(build_curses(root))
            repaint()

        root.bind("<Configure>", resized, add="+")
        root.bind("<Key-Escape>", lambda _event: root.quit())
        root.update_layout()
        root.after(50, repaint)
        root.mainloop()
    finally:
        tcurses.endwin()
        root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
