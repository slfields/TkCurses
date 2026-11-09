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

"""A bar chart on a Canvas, drawn again whenever the window changes size.

Rectangles and text are Canvas items, as in tkinter. Across, a canvas
coordinate is a character cell; down, it is half of one, so a bar can end
halfway up a row, and a cell holds two of them one above the other.
"""

import tkcurses as tk

SALES = (("Jan", 12), ("Feb", 19), ("Mar", 7), ("Apr", 15), ("May", 23), ("Jun", 17))
COLOURS = (
    "steel blue",
    "sea green",
    "goldenrod",
    "indian red",
    "medium purple",
    "dark cyan",
)

root = tk.Tk()
root.title("Sales")
canvas = tk.Canvas(root, highlightthickness=0)
canvas.pack(fill="both", expand=True)


def draw(event=None):
    canvas.delete("all")
    columns, rows = canvas.winfo_width(), canvas.winfo_height()
    canvas.create_text(1, 0, text="Sales by month", anchor="nw")
    # Two rows at the top for the title and the tallest bar's figure, one at
    # the bottom for the months; the bars have the rest, in half-cells.
    floor = 2 * (rows - 1)
    tallest = floor - 2 * 2
    top = max(value for _month, value in SALES)
    slot = max((columns - 1) // len(SALES), 4)
    for index, ((month, value), colour) in enumerate(zip(SALES, COLOURS, strict=True)):
        left = 1 + index * slot
        height = max(round(value / top * tallest), 1)
        canvas.create_rectangle(
            left, floor - height, left + slot - 3, floor - 1, fill=colour, outline=""
        )
        figure_row = (floor - height) // 2 - 1
        canvas.create_text(left, 2 * figure_row, text=str(value), anchor="nw")
        canvas.create_text(left, floor, text=month, anchor="nw")


canvas.bind("<Configure>", draw)
root.after_idle(draw)
root.mainloop()
