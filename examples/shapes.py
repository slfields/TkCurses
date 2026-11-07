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

"""Shapes on a Canvas, moved with the keyboard or dragged with the mouse.

Lines, rectangles, ovals, polygons and text are Canvas items, as in
tkinter, each tagged with a name so it can be found and moved as one.
Across, a canvas coordinate is a character cell; down, it is half of one.
"""

import tkcurses as tk

root = tk.Tk()
root.title("Shapes")
canvas = tk.Canvas(
    root, relief="flat", highlightthickness=0, background="midnight blue"
)
canvas.pack(fill="both", expand=True)
status = tk.Label(root, anchor="w")
status.pack(fill="x")

# The ground and the sky are scenery; the named shapes can be moved.
canvas.create_rectangle(0, 20, 200, 100, fill="dark green", outline="")
canvas.create_text(1, 0, text="Tab picks a shape, the arrows move it", anchor="nw")
canvas.create_oval(30, 3, 37, 10, fill="gold", outline="", tags="sun")
canvas.create_rectangle(4, 10, 16, 21, fill="firebrick", outline="", tags="house")
canvas.create_polygon(2, 10, 10, 4, 18, 10, fill="slate gray", tags="house")
canvas.create_rectangle(8, 15, 11, 21, fill="saddle brown", outline="", tags="house")
canvas.create_polygon(22, 18, 25, 7, 28, 18, fill="forest green", tags="tree")
canvas.create_line(25, 18, 25, 21, fill="sienna", tags="tree")
canvas.create_text(20, 4, text="~~", fill="white", tags="bird")

NAMES = ("sun", "house", "tree", "bird")
chosen = 0
dragged = {"x": 0, "y": 0}


def show():
    status.configure(text=f" Moving the {NAMES[chosen]}")


def pick(event):
    global chosen
    chosen = (chosen + 1) % len(NAMES)
    show()
    return "break"  # keep Tab for the canvas rather than moving the focus


def nudge(dx, dy):
    canvas.move(NAMES[chosen], dx, dy)


def press(event):
    """Pick the shape under the mouse, and remember where the drag began."""
    global chosen
    # canvasx and canvasy turn the event's position in the window into
    # canvas coordinates - here, rows into half-rows.
    x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)
    for item in reversed(canvas.find_overlapping(x, y, x + 1, y + 1)):
        tags = canvas.gettags(item)
        if tags and tags[0] in NAMES:
            chosen = NAMES.index(tags[0])
            show()
            break
    dragged.update(x=x, y=y)


def drag(event):
    x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)
    nudge(x - dragged["x"], y - dragged["y"])
    dragged.update(x=x, y=y)


canvas.bind("<Tab>", pick)
canvas.bind("<Left>", lambda e: nudge(-1, 0))
canvas.bind("<Right>", lambda e: nudge(1, 0))
canvas.bind("<Up>", lambda e: nudge(0, -1))
canvas.bind("<Down>", lambda e: nudge(0, 1))
canvas.bind("<ButtonPress-1>", press)
canvas.bind("<B1-Motion>", drag)
canvas.focus_set()
show()
root.mainloop()
