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

"""Bars: a bar graph's shape - bars, the series in each, stacked or
overlaid, standing up or lying down.

A TkCurses widget: neither tkinter nor Tk has a bar graph. Press m to
switch stacked and overlay, o to turn the graph on its side.
"""

import tkcurses as tk
from tkcurses.bargraph import BarGraph

# Four quarters, three products in each: one bar a quarter, one series a
# product.
SALES = [[30, 20, 10], [45, 25, 15], [35, 40, 20], [60, 30, 25]]

root = tk.Tk()
root.title("Bars")
graph = BarGraph(
    root,
    segments=4,
    series=3,
    labels=["Q1", "Q2", "Q3", "Q4"],
    colors=["green", "yellow", "cyan"],
    maximum=120,
    label="Sales",
    borderwidth=1,
    thickness=4,
)
# Packed first, so the graph cannot push it off the screen.
status = tk.Label(root)
status.pack(side="bottom", fill="x")
graph.pack(fill="both", expand=True, padx=1)
graph.set_all(SALES)


def show() -> None:
    status.configure(
        text=f"{graph.cget('mode')}, {graph.cget('orient')}"
        "   m: mode  o: orient  Ctrl-C: quit"
    )


def switch(option: str, one: str, other: str) -> None:
    graph.configure(**{option: other if graph.cget(option) == one else one})
    show()


root.bind("m", lambda event: switch("mode", "stacked", "overlay"))


def turn() -> None:
    # Lying down, a bar four rows thick would leave no room for the fourth.
    switch("orient", "vertical", "horizontal")
    graph.configure(thickness=4 if graph.cget("orient") == "vertical" else 2)


root.bind("o", lambda event: turn())
show()
root.mainloop()
