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

"""A Treeview scrolled both ways, with frozen rows and columns.

What to do: scroll the tree sideways and down with its scrollbars, then
press **c** and **i** to freeze more columns and more rows, and scroll again.
Click cells in both the frozen and the scrolling parts.

What to look for: **frozen columns stay put while the rest pass under them**,
**frozen rows stay on top while the rest scroll**, and each scrollbar's
thumb sizes to the part that scrolls. The readout names the cell last
clicked. TkCurses-xe9.6.
"""

from __future__ import annotations

from tkcurses import ttk
from uat import _support

TITLE = "47 - Treeview frozen rows and columns"

#: Data columns, each wider than its heading so the tree overflows sideways.
COLUMNS = ("north", "south", "east", "west", "upper", "lower", "inner", "outer")


def build(root, screen):
    area = _support.content_area(root, top=5)
    tree = ttk.Treeview(area, columns=COLUMNS, height=10)
    tree.column("#0", width=12, stretch=False)
    tree.heading("#0", text="Region")
    for name in COLUMNS:
        tree.column(name, width=9, stretch=False)
        tree.heading(name, text=name.title())
    for group in range(4):
        parent = tree.insert(
            "", "end", text=f"Group {group}", open=group < 2, values=("-",) * 8
        )
        for n in range(9):
            tree.insert(
                parent,
                "end",
                text=f"Item {group}.{n}",
                values=[f"{name[:2]}{group}{n}" for name in COLUMNS],
            )
    down = ttk.Scrollbar(area, orient="vertical", command=tree.yview)
    across = ttk.Scrollbar(area, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=down.set, xscrollcommand=across.set)
    tree.grid(row=0, column=0, sticky="nsew")
    down.grid(row=0, column=1, sticky="ns")
    across.grid(row=1, column=0, sticky="ew")
    area.rowconfigure(0, weight=1)
    area.columnconfigure(0, weight=1)
    state = {"cell": "-"}

    def report(*_):
        x0, x1 = tree.xview()
        y0, y1 = tree.yview()
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  titlecolumns={tree.cget('titlecolumns')}  "
            f"titleitems={tree.cget('titleitems')}   c / i add one, C / I take one",
        )
        screen.line(2, f"  xview ({x0:.2f}, {x1:.2f})   yview ({y0:.2f}, {y1:.2f})")
        screen.line(3, f"  last clicked: {state['cell']}")
        screen.footer(" scrollbars or < > to scroll sideways - Escape quits ")
        screen.refresh()

    def clicked(event):
        item = tree.identify_row(event.y)
        column = tree.identify_column(event.x)
        text = tree.item(item, "text") if item else ""
        state["cell"] = f"{text or '(none)'} {column or '(none)'}"
        root.after_idle(report)

    def change(option, step):
        def run(_event):
            tree.configure({option: max(0, int(tree.cget(option)) + step)})
            report()
            return "break"

        return run

    def sideways(pages):
        def run(_event):
            tree.xview_scroll(pages, "pages")
            report()
            return "break"

        return run

    tree.bind("<Button-1>", clicked, add="+")
    root.bind_all("c", change("titlecolumns", 1))
    root.bind_all("C", change("titlecolumns", -1))
    root.bind_all("i", change("titleitems", 1))
    root.bind_all("I", change("titleitems", -1))
    root.bind_all("<less>", sideways(-1))
    root.bind_all("<greater>", sideways(1))
    tree.bind("<<TreeviewSelect>>", report, add="+")
    across.bind("<ButtonRelease-1>", report, add="+")
    down.bind("<ButtonRelease-1>", report, add="+")
    tree.focus_set()
    root.after(50, report)


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
