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

"""Changing one geometry option, and what happens to the rest.

What to do: press p, g, x and w to change exactly one option of one manager.
Press e to push all three hard against the screen's edges, f to forget them
and add them again with nothing set, and r to put the starting options back.
Then shrink the terminal.
What to look for: the option you changed changes, and **nothing else moves**.
The line above each strip is what the manager reports - pack_info(),
grid_info(), place_info() - so it can be read against where the box actually
is.

This is the scenario for a fault that was invisible to anyone reading the
call. ``pack_configure(fill='x')`` looks like it changes the fill, and what it
used to do was reset the side, the padding and the anchor as well: w, which
asks the placed box only to get wider, also sent it to the corner. Every
automated test passed while that was true, because each one configured a
widget once and asked where it went.

f is the exception that is not a fault. Forgetting a widget is what discards
its options in Tk, so adding it back with nothing set is supposed to give the
defaults - side=top, sticky='', anchor=nw. Checked against Tk 9.0.2.

e asks a different question. A widget the screen edge cuts in half can only
have a window holding the part that fits, because curses refuses one that
runs off the screen - so the drawing has to stop at the edge rather than
wrap round onto the next row. A box with no right-hand edge is what a box
continuing off the screen should look like; the same box with its border
running on into the line below is the fault.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "28 - geometry options: change one, keep the rest"

#: What each widget is set up with, and what r puts back. Several options at
#: once on purpose: one option cannot show that the others survived.
START = {
    "pack": {"side": "left", "fill": "y", "padx": 2, "anchor": "n"},
    "grid": {"row": 1, "column": 3, "sticky": "ew", "padx": 2},
    "place": {"x": 2, "y": 1, "width": 8, "anchor": "nw"},
}

#: The options each line reports, in the order they are shown.
SHOWN = {
    "pack": ("side", "fill", "padx", "anchor"),
    "grid": ("row", "column", "sticky", "padx"),
    "place": ("x", "y", "width", "anchor"),
}

#: Row each manager's report and strip begin on.
ROWS = {"pack": 3, "grid": 8, "place": 13}


def build(root, screen):
    boxes = {}
    for name, row in ROWS.items():
        # No border on the strip: it would eat two of the four rows the box
        # needs, and the report line above each strip already separates them.
        holder = tkcurses.Frame(root, name=f"{name}holder")
        holder.place(x=0, y=row + 1, relwidth=1.0, height=4)
        boxes[name] = tkcurses.Label(holder, text=f" {name} ", relief="solid")
        if name == "grid":
            # Five numbered columns above the box. Without siblings a grid
            # has only the columns something occupies, so moving the box
            # from column 3 to column 1 would change nothing on screen -
            # both would be the first column there is.
            # Below the box rather than above it, so that f - which sends the
            # box to row 0 - moves it into empty space instead of on top of
            # them. Correct either way, but an overlap reads as a fault.
            for column in range(5):
                tkcurses.Label(holder, text=f"  {column}     ").grid(
                    row=2, column=column
                )

    def apply(name, **options):
        """Configure one box through the manager that owns it."""
        getattr(boxes[name], f"{name}_configure")(**options)

    def reset():
        for name, options in START.items():
            getattr(boxes[name], f"{name}_forget")()
            getattr(boxes[name], name)(**options)

    def report(event=None):
        root.update_layout()
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            "  p pack side   g grid column   x place x   w place width"
            "   e edges   f forget   r reset",
        )
        for name, row in ROWS.items():
            info = getattr(boxes[name], f"{name}_info")()
            shown = "  ".join(f"{key}={info[key]!r}" for key in SHOWN[name])
            screen.line(row, f"  {name:<6} {shown}")
        screen.footer(" Escape quits ")
        screen.refresh()

    def toggle(name, option, first, second):
        def handler(event):
            info = getattr(boxes[name], f"{name}_info")()
            value = second if info[option] == first else first
            apply(name, **{option: value})
            root.after_idle(report)
            return "break"

        return handler

    def forget_all(event):
        for name in START:
            getattr(boxes[name], f"{name}_forget")()
            # Nothing set: whatever comes back is the manager's defaults,
            # which is the whole point of this key.
            getattr(boxes[name], name)()
        root.after_idle(report)
        return "break"

    def restore(event):
        reset()
        root.after_idle(report)
        return "break"

    def to_the_edges(event):
        """Push each box past an edge, so the clipping can be seen."""
        width = root.winfo_width()
        apply("pack", side="right", padx=0)
        apply("grid", column=9, padx=0)
        apply("place", x=max(0, width - 6), y=2, width=20)
        root.after_idle(report)
        return "break"

    reset()
    root.bind("<Key-p>", toggle("pack", "side", "left", "right"))
    root.bind("<Key-g>", toggle("grid", "column", 3, 1))
    root.bind("<Key-x>", toggle("place", "x", 2, 20))
    root.bind("<Key-w>", toggle("place", "width", 8, 16))
    root.bind("<Key-e>", to_the_edges)
    root.bind("<Key-f>", forget_all)
    root.bind("<Key-r>", restore)
    root.after(100, report)


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
