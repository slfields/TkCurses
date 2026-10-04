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

"""Views, selections and columns - what moved when, and what stayed put.

What to do: press the buttons down the middle, which act on the entry at the
top left from code. Drag and click the scrollbar under it. Scroll the list
sideways. Press ``wider`` and ``narrower`` under the tree. Type in the check
field at the bottom left and press ``validate()``. ``Ctrl-R`` puts it all back.

What to look for: **the readout under the title.** It reports, after every
event, where each view is and what is selected - the things that changed in
pull requests #121 to #132 and that no scenario showed a person before:

* an Entry's view is not its cursor. A program inserting a long value leaves
  the START on show; scrolling moves the view and leaves the cursor and the
  selection where they were (TkCurses-i8s).
* inserting and deleting from code carry the selection with the text instead
  of dropping it, and ``selection_adjust`` moves the nearer end
  (TkCurses-61v, TkCurses-bfy).
* a Listbox scrolls sideways (TkCurses-019).
* a Treeview's columns stretch to fill it, except one that says
  ``stretch=False``; tags colour rows (TkCurses-a01, TkCurses-67u).
* ``validate()`` sets ttk's ``invalid`` state, which the default theme draws
  as nothing - so this field's style maps it to red (TkCurses-52q).

All of it was measured against Tk 9.0.2 and is pinned by tests. What tests
cannot say is whether a person watching can tell what happened. TkCurses-w1h.
"""

from __future__ import annotations

import tkcurses
from tkcurses import ttk
from uat import _support

TITLE = "42 - Views, selections and columns"

#: What the entry is filled with. Numbered, so the readout's "first shown"
#: can be checked against the screen by eye.
LONG = "0123456789abcdefghijklmnopqrstuvwxyz"

#: List items wider than the list, so it has something to scroll sideways.
ITEMS = [f"{n:02d} " + "-" * (3 * n) + f" item {n}" for n in range(1, 13)]
WIDEST = max(len(item) for item in ITEMS)

#: The tree's rows: name, size, kind, and the tags that colour them.
FILES = (
    ("README", "4", "text", ()),
    ("build", "-", "dir", ("dir",)),
    ("big.iso", "4096", "image", ("big",)),
    ("notes", "12", "text", ()),
)


def build(root, screen):
    screen.line(0, f" {TITLE} ")
    screen.footer(" ^R reset   Tab / F6 move focus   Escape quits ")
    # Four rows of title and readout, one of footer, and 18 of content: this
    # scenario wants a terminal at least 23 rows tall and 90 columns wide.
    area = _support.content_area(root, top=4, bottom=1)
    last = {"text": "nothing yet"}

    # ---------------------------------------------------------- entry + bar
    entry = tkcurses.Entry(area, name="entry")
    entry.place(x=2, y=0, width=30)
    entry_bar = tkcurses.Scrollbar(
        area, name="ebar", orient="horizontal", command=entry.xview
    )
    # Three rows apart, as everything bordered is: two apart paints one
    # widget's bottom border over the next one's top (UAT 40's finding, and
    # this scenario's first run did it again).
    entry_bar.place(x=2, y=3, width=30)
    entry.configure(xscrollcommand=entry_bar.set)

    # -------------------------------------------------- list + sideways bar
    listbox = tkcurses.Listbox(area, name="list", height=4)
    listbox.place(x=2, y=6, width=30, height=6)
    list_bar = tkcurses.Scrollbar(
        area, name="lbar", orient="horizontal", command=listbox.xview
    )
    list_bar.place(x=2, y=12, width=30)
    listbox.configure(xscrollcommand=list_bar.set)

    # ------------------------------------------------- ttk entry + validate()
    style = ttk.Style(root)
    style.map("Check.TEntry", foreground=[("invalid", "red")])
    check = ttk.Entry(area, name="check", style="Check.TEntry")
    check.place(x=2, y=15, width=16)
    check.configure(
        validate="none", validatecommand=lambda proposed: proposed.isdigit()
    )

    # -------------------------------------------------------------- the tree
    tree = ttk.Treeview(area, name="tree", columns=("size", "kind"), height=5)
    tree.heading("#0", text="name")
    tree.heading("size", text="size")
    tree.heading("kind", text="kind")
    tree.column("#0", width=8)
    tree.column("size", width=5, stretch=False)
    tree.column("kind", width=5)
    tree.tag_configure("dir", foreground="cyan")
    tree.tag_configure("big", foreground="red")
    tree_width = {"cells": 34}

    def place_tree():
        tree.place(x=52, y=0, width=tree_width["cells"], height=9)

    # --------------------------------------------------------------- readout
    def describe():
        """Where each view is and what is selected - the whole point.

        Written straight to the screen rather than into a Label because it
        sits outside the content area, as scenario 41's readout does.
        """
        selected = (
            f"{entry.index('sel.first')}-{entry.index('sel.last')}"
            if entry.selection_present()
            else "none"
        )
        first = round(entry.xview()[0] * max(1, len(entry.get())))
        widths = "/".join(str(tree.column(c, "width")) for c in ("#0", "size", "kind"))
        state = "invalid" if "invalid" in check.state() else "valid"
        screen.line(
            1,
            f" entry: first shown {first}  cursor {entry.index('insert')}"
            f"  selection {selected}",
        )
        screen.line(
            2,
            f" list: first column {round(listbox.xview()[0] * WIDEST)}"
            f"   tree columns {widths} of {tree_width['cells']}"
            f"   check: {state}",
        )
        screen.line(3, f" last: {last['text']}")
        screen.refresh()

    def did(message):
        """Record what just happened, and redraw the readout once it has."""
        last["text"] = message
        root.after(1, describe)

    # The tree's column widths are measured from its laid-out width, so the
    # readout has to be redrawn once it HAS a width - when it raises
    # <Configure>, as tkinter's widgets do on every size change. Timing it
    # instead was a race: a tick later than idle won on a quiet machine and
    # lost on a loaded CI runner, where the first readout said 8/5/5, the
    # starting widths, for a tree drawn 14/5/11.
    tree.bind("<Configure>", lambda event: describe(), add="+")

    # ------------------------------------------- the buttons that act in code
    def action(text, y, run, x=36, width=14):
        def pressed():
            did(run())

        tkcurses.Button(area, name=f"b{y}_{x}", text=text, command=pressed).place(
            x=x, y=y, width=width
        )

    def fill():
        entry.delete(0, "end")
        entry.insert(0, LONG)
        return "insert(0, LONG): the START should be on show, cursor at 36"

    def select():
        entry.selection_range(2, 8)
        return "selection_range(2, 8): '234567' highlighted"

    def insert_front():
        entry.insert(0, "XY")
        return "insert(0, 'XY'): the selection moves right by two, same letters"

    def delete_front():
        entry.delete(0, 2)
        return "delete(0, 2): the selection moves back by two, same letters"

    def adjust():
        entry.selection_adjust(12)
        return "selection_adjust(12): the nearer end moves to 12, cursor stays"

    def scroll():
        entry.xview(5)
        return "xview(5): view moves, cursor and selection do not"

    action("fill", 0, fill)
    action("select 2-8", 3, select)
    action("insert XY@0", 6, insert_front)
    action("delete 0-2", 9, delete_front)
    action("adjust 12", 12, adjust)
    action("xview 5", 15, scroll)

    def validate():
        verdict = check.validate()
        return f"validate() -> {verdict}: the field should be {'plain' if verdict else 'RED'}"

    action("validate()", 15, validate, x=20, width=13)

    def wider():
        tree_width["cells"] = min(38, tree_width["cells"] + 4)
        place_tree()
        return f"tree {tree_width['cells']} wide: name and kind grow, size does not"

    def narrower():
        tree_width["cells"] = max(18, tree_width["cells"] - 4)
        place_tree()
        return f"tree {tree_width['cells']} wide: name and kind shrink, size does not"

    action("wider", 10, wider, x=52, width=10)
    action("narrower", 10, narrower, x=64, width=12)

    def reset(event=None):
        del event
        entry.delete(0, "end")
        listbox.delete(0, "end")
        listbox.insert("end", *ITEMS)
        listbox.xview_moveto(0)
        for iid in tree.get_children():
            tree.delete(iid)
        for name, size, kind, tags in FILES:
            tree.insert("", "end", text=name, values=(size, kind), tags=tags)
        tree_width["cells"] = 34
        place_tree()
        check.delete(0, "end")
        check.state(["!invalid"])
        did("reset")
        return "break"

    # Any event can move a view; refresh the readout after each one.
    for widget in (entry, entry_bar, listbox, list_bar, check, tree):
        for sequence in ("<Any-Key>", "<Button-1>", "<ButtonRelease-1>"):
            widget.bind(sequence, lambda event: root.after(1, describe), add="+")

    root.bind("<Control-r>", reset)
    reset()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
