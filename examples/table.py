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

"""A table: a Treeview with columns, sorted by a key for each column.

Press 1, 2, 3 or 4 to sort by that column, and the same key again to
reverse it. The arrows move through the rows, and Return shows the chosen
planet.
"""

import tkcurses as tk
from tkcurses import ttk

PLANETS = (
    ("Mercury", "0.39", 0, 88),
    ("Venus", "0.72", 0, 225),
    ("Earth", "1.00", 1, 365),
    ("Mars", "1.52", 2, 687),
    ("Jupiter", "5.20", 95, 4333),
    ("Saturn", "9.58", 146, 10759),
    ("Uranus", "19.22", 28, 30687),
    ("Neptune", "30.05", 16, 60190),
)
COLUMNS = (
    ("name", "Planet", 9),
    ("au", "From Sun (AU)", 14),
    ("moons", "Moons", 6),
    ("year", "Year (days)", 12),
)

root = tk.Tk()
root.title("Planets")

table = ttk.Treeview(root, columns=[c[0] for c in COLUMNS], show="headings", height=8)
scroll = ttk.Scrollbar(root, orient="vertical", command=table.yview)
table.configure(yscrollcommand=scroll.set)
chosen = ttk.Label(root, text="Return shows a planet; 1-4 sort")
chosen.pack(side="bottom", fill="x", padx=1)
scroll.pack(side="right", fill="y")
table.pack(fill="both", expand=True)

order = {"column": None, "reverse": False}


def sort_by(column):
    reverse = order["column"] == column and not order["reverse"]
    order.update(column=column, reverse=reverse)
    rows = [(table.set(item, column), item) for item in table.get_children()]
    key = str if column == "name" else float
    rows.sort(key=lambda row: key(row[0]), reverse=reverse)
    for index, (_value, item) in enumerate(rows):
        table.move(item, "", index)
    for name, title, _width in COLUMNS:
        arrow = (" v" if reverse else " ^") if name == column else ""
        table.heading(name, text=title + arrow)


for number, (name, title, width) in enumerate(COLUMNS, start=1):
    table.heading(name, text=title)
    table.column(name, width=width, anchor="w" if name == "name" else "e")
    table.bind(str(number), lambda event, c=name: sort_by(c))
for planet in PLANETS:
    table.insert("", "end", values=planet)


def show(event):
    for item in table.selection():
        name, au, moons, _year = table.item(item, "values")
        moon = "moon" if moons == "1" else "moons"
        chosen.config(text=f"{name}: {au} AU from the Sun, {moons} {moon}")


table.bind("<Return>", show)
first = table.get_children()[0]
table.selection_set(first)
table.focus(first)
table.focus_set()
root.mainloop()
