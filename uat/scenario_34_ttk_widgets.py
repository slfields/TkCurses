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


"""The themed widgets a person operates, rather than looks at.

Scenario 33 showed that appearance lives in one place. This one asks
whether the widgets built on it behave like the tkinter widgets they claim
to be, which only a hand can answer.

What to do: open the combobox and choose from it, by mouse and by keyboard.
Switch the notebook's tabs, by click and by Left/Right. Expand the tree and
walk it. Drag the scale and watch its label. Pick from the option menu.
Then press `t` to change the theme and do it all again, because a widget
that only works under one theme is not themed - and `r` to restyle every
one of them while they are on screen.

What to look for, in the order it is easiest to get wrong:

The **combobox** drops a list from its arrow - clicking its text places the
cursor instead, as in Tk (TkCurses-fgke) - that closes three ways - choosing,
Escape, and a click anywhere else - and the value you chose is in the field
afterwards.
Typing into it works: it is an Entry underneath, and a combobox that took
keys and did nothing with them would look identical until you tried.

The **notebook** shows exactly one page. Two pages at once is the failure
worth watching for; it is what the widget did first, because a container
that is taken off screen used to leave its children behind.

The **tree** hides a closed branch's rows entirely rather than merely
marking them, indents by depth, and lines its values up under their
headings.

The **scale** and its label are one widget: drag the trough and the number
beside it follows, because they share a variable rather than because
anything copies one to the other.

The **option menu** is a menubutton - its text is the variable, and the
menu underneath holds radiobutton entries rather than plain commands, which
is what ttk's does and the classic one does not.

Keys: **Control-T** next theme, **Control-R** restyle every class,
**Control-B** put it back, Escape quits. Everything else is mouse and arrow
keys on the widgets.

The control keys are deliberate. This screen has a combobox on it, and a
combobox is an Entry underneath: a plain `t` would be typed into the field
whenever it had the focus, which is exactly the sort of thing a person
running a UAT should not have to think about. Scenario 33 has no text field
and uses plain letters.
"""

from __future__ import annotations

import tkcurses
from tkcurses import ttk
from uat import _support

TITLE = "34 - ttk: the widgets you operate"

#: What `r` paints every themed class, so that one key shows the database
#: reaching five different widgets at once.
RESTYLED = "cyan"


def build(root, screen):
    style = ttk.Style(root)
    themes = list(style.theme_names())
    state = {"theme": 0, "styled": False}

    screen.line(0, f" {TITLE} ")
    screen.footer(
        " ^T theme   ^R restyle every class   ^B back to default   Escape quits "
    )

    area = _support.content_area(root, top=3, bottom=2)

    # ------------------------------------------------------------ combobox
    tkcurses.Label(area, text="Combobox", anchor="w").place(x=1, y=0, width=12)
    combo = ttk.Combobox(area, name="combo", values=("alpha", "beta", "gamma", "delta"))
    combo.place(x=14, y=0, width=18)

    # ----------------------------------------------------------- notebook
    book = ttk.Notebook(area, name="book")
    book.place(x=1, y=4, width=31, height=9)
    for index, word in enumerate(("First", "Second", "Third")):
        page = tkcurses.Frame(book, name=f"page{index}")
        tkcurses.Label(page, text=f"page {word.lower()}", anchor="w").place(
            x=1, y=1, width=18
        )
        tkcurses.Label(page, text="one page at a time", anchor="w").place(
            x=1, y=2, width=20
        )
        book.add(page, text=word)

    # ------------------------------------------------------------- treeview
    tree = ttk.Treeview(area, name="tree", columns=("size",))
    tree.place(x=35, y=0, width=32, height=10)
    tree.heading("#0", text="Name")
    tree.heading("size", text="Size")
    tree.column("#0", width=18)
    tree.column("size", width=6)
    for folder, items in (
        ("documents", ("notes.txt", "plan.md")),
        ("pictures", ("beach.png", "hills.png", "sky.png")),
    ):
        parent = tree.insert("", "end", text=folder, values=("-",))
        for number, leaf in enumerate(items, start=1):
            tree.insert(parent, "end", text=leaf, values=(str(number * 12),))
    tree.insert("", "end", text="readme", values=("3",))

    # --------------------------------------------------------- labeledscale
    tkcurses.Label(area, text="LabeledScale", anchor="w").place(x=1, y=14, width=13)
    scale = ttk.LabeledScale(area, name="scale", from_=0, to=20)
    scale.place(x=14, y=14, width=18, height=2)

    # ----------------------------------------------------------- optionmenu
    tkcurses.Label(area, text="OptionMenu", anchor="w").place(x=1, y=17, width=13)
    picked = tkcurses.StringVar(root, value="beta")
    options = ttk.OptionMenu(
        area, picked, "beta", "alpha", "beta", "gamma", name="options"
    )
    options.place(x=14, y=17, width=18)

    # ---------------------------------------------------------------- report
    def report(event=None):
        del event
        screen.line(
            1,
            f"  theme={themes[state['theme']]}"
            f"   combobox={combo.get()!r}"
            f"   tab={book.index('current')}"
            f"   scale={scale.value}"
            f"   option={picked.get()!r}",
        )
        chosen = tree.selection()
        screen.line(
            2,
            f"  tree selection="
            f"{[tree.item(iid, 'text') for iid in chosen] if chosen else '-'}"
            f"   restyled={state['styled']}",
        )
        screen.refresh()

    combo.bind("<<ComboboxSelected>>", report)
    book.bind("<<NotebookTabChanged>>", report)
    tree.bind("<<TreeviewSelect>>", report)
    scale._variable.trace_add("write", lambda *_: report())
    picked.trace_add("write", lambda *_: report())
    # After the class binding rather than before it: a widget binding runs
    # first, so reporting here directly would show the field as it was
    # before the key landed in it.
    combo.bind("<Any-Key>", lambda event: root.after(0, report), add="+")

    # ------------------------------------------------------------- the keys
    def next_theme(event=None):
        del event
        state["theme"] = (state["theme"] + 1) % len(themes)
        style.theme_use(themes[state["theme"]])
        report()
        return "break"

    def restyle(event=None):
        """One key, five widget classes - the claim scenario 33 makes, here
        against widgets that are more than a bar and a rule."""
        del event
        state["styled"] = True
        for name in ("TCombobox", "TNotebook", "Treeview", "TMenubutton", "TLabel"):
            style.configure(name, foreground=RESTYLED)
        report()
        return "break"

    def reset(event=None):
        del event
        style.theme_use("default")
        state["theme"] = 0
        state["styled"] = False
        for name in ("TCombobox", "TNotebook", "Treeview", "TMenubutton", "TLabel"):
            style.configure(name, foreground="")
        report()
        return "break"

    # Control keys rather than plain letters: the combobox on this screen is
    # an Entry, and a plain `t` lands in the field whenever it has the focus.
    root.bind("<Control-t>", next_theme)
    root.bind("<Control-r>", restyle)
    root.bind("<Control-b>", reset)

    root.update_layout()
    tree.item(tree.get_children("")[0], open=True)
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
