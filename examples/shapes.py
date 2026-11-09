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

Lines, rectangles, ovals, polygons, an arc, an image and text are Canvas
items, as in tkinter, each tagged with a name so it can be found and moved
as one. The Reset button is a widget on the canvas too, a window item.
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
# The cloud is a picture: a PhotoImage, drawn a pixel to a half-cell,
# and made before the bird so that the bird flies in front of it.
cloud = tk.PhotoImage(width=6, height=3)
cloud.put("white", to=(1, 0, 5, 1))
cloud.put("white", to=(0, 1, 6, 3))
canvas.create_image(23, 2, image=cloud, anchor="nw", tags="cloud")
canvas.create_text(20, 4, text="~~", fill="white", tags="bird")
# The pond is the lower half of an oval, cut off by a chord.
canvas.create_arc(
    22, 18, 38, 28, start=180, extent=180, style="chord", fill="steel blue", outline=""
)

NAMES = ("sun", "house", "tree", "bird", "cloud")
# Where each shape starts, for the Reset button to put it back. moveto
# puts the top-left corner of a tag's lowest item where it is told, as in
# Tk, so that corner is what to remember - not the corner of the whole tag.
HOME = {name: canvas.bbox(canvas.find_withtag(name)[0])[:2] for name in NAMES}
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


def reset():
    for name, (x, y) in HOME.items():
        canvas.moveto(name, x, y)


# A widget on the canvas: the canvas places it, and it moves with the view.
reset_button = tk.Button(
    canvas,
    text="Reset",
    command=reset,
    borderwidth=0,
    background="gold",
    foreground="black",
)
canvas.create_window(1, 26, window=reset_button, anchor="sw")

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
