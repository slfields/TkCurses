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

"""A mark book: a Treeview that selects cells rather than rows.

With selecttype="cell" a click selects the cell under the pointer, the
arrow keys move from cell to cell, Control-click adds or removes one, and
Shift-click selects the rectangle from the last cell chosen. The line
under the table adds up whatever is selected, as a spreadsheet's status
line does, each time <<TreeviewSelect>> says the selection changed. Row
selects the whole of the keyboard's row and Column the whole of the last
cell's column, each as a rectangle between two corners.

tkinter has no methods for the cell selection, so this reaches Tk's
cellselection command through tree.tk.call, as a tkinter program must, and
runs under tkinter with only the imports changed - and the sizes, which
are in characters here and in pixels there.
"""

import tkcurses as tk
from tkcurses import ttk

TESTS = ("Essay", "Quiz", "Lab", "Exam")
MARKS = {
    "Ada": (72, 85, 90, 78),
    "Grace": (88, 79, 95, 91),
    "Alan": (65, 92, 70, 84),
    "Edsger": (91, 68, 82, 87),
    "Barbara": (77, 81, 88, 69),
}
#: Sizes: characters under TkCurses, pixels under tkinter - the one line to
#: change, with the imports, to run this under tkinter.
NAME_WIDTH, MARK_WIDTH, GAP = 10, 6, 1

root = tk.Tk()
root.title("Marks")

table = ttk.Treeview(root, columns=TESTS, height=len(MARKS), selecttype="cell")
table.heading("#0", text="Student")
table.column("#0", width=NAME_WIDTH, stretch=False)
for test in TESTS:
    table.heading(test, text=test)
    table.column(test, width=MARK_WIDTH, stretch=False)
for name, marks in MARKS.items():
    table.insert("", "end", iid=name, text=name, values=marks)
table.pack(anchor="w", padx=GAP, pady=(GAP, 0))

summary = ttk.Label(root, text="")
summary.pack(anchor="w", padx=GAP)


def cellselection(*args):
    """Tk's cellselection command: the cells selected, as (row, column)
    pairs, or with arguments a change to them."""
    answer = table.tk.call(table, "cellselection", *args)
    return [tuple(table.tk.splitlist(cell)) for cell in table.tk.splitlist(answer)]


def add_up(event=None):
    """Count, total and mean of the marks selected; names do not count."""
    marks = [
        float(table.set(item, column))
        for item, column in cellselection()
        if column != "#0"
    ]
    if not marks:
        summary.configure(text="Nothing selected")
        return
    total = sum(marks)
    summary.configure(
        text=f"{len(marks)} marks, total {total:g}, mean {total / len(marks):.1f}"
    )


def whole_row():
    """The row the keyboard is on, from the first test to the last."""
    item = table.focus()
    if item:
        cellselection("set", (item, TESTS[0]), (item, TESTS[-1]))


def whole_column():
    """The column of the last cell chosen, from the first student to the last."""
    chosen = cellselection()
    column = chosen[-1][1] if chosen and chosen[-1][1] != "#0" else TESTS[0]
    students = table.get_children()
    cellselection("set", (students[0], column), (students[-1], column))


table.bind("<<TreeviewSelect>>", add_up)

buttons = ttk.Frame(root)
buttons.pack(anchor="w", padx=GAP, pady=(GAP, 0))
ttk.Button(buttons, text="Row", command=whole_row).pack(side="left")
ttk.Button(buttons, text="Column", command=whole_column).pack(
    side="left", padx=(GAP, 0)
)
ttk.Button(buttons, text="Quit", command=root.destroy).pack(side="left", padx=(GAP, 0))

table.focus_set()
table.focus("Ada")
cellselection("set", [("Ada", "Essay")])
add_up()
root.mainloop()
