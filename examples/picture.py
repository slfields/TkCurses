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

"""A picture in a Label: the Mandelbrot set, or an image file, fitted to the window.

A PhotoImage is a plane of pixels, each one column wide and half a row
tall, so a cell shows two of them one above the other. With no argument
the program computes the Mandelbrot set into one with ``put``; + and -
zoom, and the arrows move about. Given a PNG, GIF or PPM file it shows
that instead, resized to fit and cut to the colours the terminal has.
"""

import sys
from pathlib import Path

import tkcurses as tk

# Sixteen colours from deep blue through white to orange, for how quickly a
# point escapes; the set itself is black.
SHADES = (
    "#000764", "#0b2a8a", "#1a4fb0", "#2f74d0", "#5596e6", "#86b5f0",
    "#bcd6f7", "#edf3fb", "#fbe9b7", "#fed27a", "#ffb941", "#ff9f12",
    "#e8850b", "#c46b06", "#9a5203", "#6a3801",
)  # fmt: skip
LIMIT = 48  # how many steps a point gets to escape in

root = tk.Tk()
root.title("Picture")
label = tk.Label(root, borderwidth=0)
label.pack(fill="both", expand=True)
status = tk.Label(root, anchor="w")
status.pack(fill="x")
view = {"x": -0.6, "y": 0.0, "span": 3.2}
original = tk.PhotoImage(file=sys.argv[1]) if len(sys.argv) > 1 else None


def escape(c):
    """How many steps z -> z*z + c takes to leave the circle of radius 2."""
    z = 0j
    for step in range(LIMIT):
        z = z * z + c
        if abs(z) > 2:
            return step
    return None


def mandelbrot(width, height):
    picture = tk.PhotoImage(width=width, height=height)
    # A pixel is half a cell tall, and a cell is about twice as tall as it
    # is wide, so pixels are near enough square. The span fits across, and
    # three-quarters of it down, whichever is the tighter.
    scale = max(view["span"] / width, view["span"] * 0.75 / height)
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            c = complex(
                view["x"] + (x - width / 2) * scale,
                view["y"] + (y - height / 2) * scale,
            )
            step = escape(c)
            row.append("#000000" if step is None else SHADES[step % len(SHADES)])
        rows.append(row)
    picture.put(rows)
    return picture


def fitted(width, height):
    """The file's picture as large as fits, its proportions kept."""
    ratio = min(width / original.width(), height / original.height())
    size = (
        max(round(original.width() * ratio), 1),
        max(round(original.height() * ratio), 1),
    )
    return original.resize(*size).fit_pairs()


def draw(event=None):
    width, height = label.winfo_width(), 2 * label.winfo_height()
    if width < 2 or height < 2:
        return  # not laid out yet
    if original is None:
        label.picture = mandelbrot(width, height)
        status.configure(
            text=f" {view['x']:+.4f} {view['y']:+.4f}i, {3.2 / view['span']:g}x"
            "   + and - zoom, the arrows move"
        )
    else:
        label.picture = fitted(width, height)
        name = Path(sys.argv[1]).name
        status.configure(text=f" {name}, {original.width()}x{original.height()}")
    label.configure(image=label.picture)


def zoom(factor):
    view["span"] /= factor
    draw()


def move(dx, dy):
    view["x"] += dx * view["span"] / 4
    view["y"] += dy * view["span"] / 4
    draw()


if original is None:
    root.bind("+", lambda e: zoom(2))
    root.bind("=", lambda e: zoom(2))
    root.bind("-", lambda e: zoom(0.5))
    root.bind("<Left>", lambda e: move(-1, 0))
    root.bind("<Right>", lambda e: move(1, 0))
    root.bind("<Up>", lambda e: move(0, -1))
    root.bind("<Down>", lambda e: move(0, 1))
label.bind("<Configure>", draw)
root.mainloop()
