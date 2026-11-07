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

"""A line graph on a Canvas: three curves with axes and a legend.

Each curve is one line item through a point per column, drawn again
whenever the window changes size. Press 1, 2 or 3 to show or hide a
curve. Across, a canvas coordinate is a character cell; down, it is half
of one, so a curve moves in steps of half a row.
"""

import math

import tkcurses as tk

CURVES = (
    ("sin x", "tomato", math.sin),
    ("cos x", "deep sky blue", math.cos),
    ("damped", "gold", lambda x: math.exp(-x / 6) * math.sin(2 * x)),
)
TURNS = 2  # how many whole turns of the circle the x axis spans

root = tk.Tk()
root.title("Plot")
canvas = tk.Canvas(root, relief="flat", highlightthickness=0)
canvas.pack(fill="both", expand=True)
shown = [True] * len(CURVES)


def draw(event=None):
    canvas.delete("all")
    columns, rows = canvas.winfo_width(), canvas.winfo_height()
    if columns < 12 or rows < 5:
        return  # not laid out yet, or too small to say anything
    # Four columns at the left for the y labels and one row at the bottom
    # for the x labels; the graph has the rest, in half-rows down.
    left, right = 4, columns - 1
    top, bottom = 2, 2 * (rows - 1) - 1
    middle = (top + bottom) // 2
    canvas.create_line(left, top, left, bottom, fill="gray")
    canvas.create_line(left, middle, right, middle, fill="gray")
    for value, y in (("1", top), ("0", middle), ("-1", bottom)):
        canvas.create_text(left - 1, y, text=value, anchor="e")
    for turn in range(TURNS + 1):
        x = left + turn * (right - left) // TURNS
        name = f"{2 * turn}π" if turn else "0"
        anchor = "ne" if turn == TURNS else "n"
        canvas.create_text(x, 2 * (rows - 1), text=name, anchor=anchor)

    legend = left + 2
    for index, (name, colour, function) in enumerate(CURVES):
        label = f"{index + 1} {name}"
        canvas.create_text(
            legend, 0, text=label, anchor="nw", fill=colour if shown[index] else "gray"
        )
        legend += len(label) + 2
        if not shown[index]:
            continue
        points = []
        for column in range(left, right + 1):
            x = (column - left) / (right - left) * TURNS * 2 * math.pi
            points += [column, middle - function(x) * (middle - top)]
        canvas.create_line(*points, fill=colour)


def toggle(index):
    shown[index] = not shown[index]
    draw()


for number in range(len(CURVES)):
    root.bind(str(number + 1), lambda event, index=number: toggle(index))
canvas.bind("<Configure>", draw)
root.after_idle(draw)
root.mainloop()
