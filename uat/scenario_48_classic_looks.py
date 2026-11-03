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

"""How classic widgets look: the insertion cursor, selections, and states.

What to do: move the focus with **Tab** or a click, and watch the terminal's
cursor change shape and colour from field to field. **F5** cycles the fields
through normal, disabled and readonly; **F6** makes the buttons and the scale
active; **F7** hides the Text's selection while it has no focus. Press the
button and drag the scale with the mouse.

What to look for: **a block, a bar, a steady bar and an orange cursor**, and
your own cursor back in the plain field and after quitting; **selections in
their colours**, not reversed; **disabled and readonly fields, active buttons
and the scale's trough in theirs**. TkCurses-gm66.2, .3 and .4.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "48 - How classic widgets look"

#: What F5 steps the fields through. Only the Entry and the Spinbox have
#: readonly; the Listbox is left normal for it, as Tk has no readonly listbox.
STATES = ("normal", "disabled", "readonly")

#: Colours a terminal with only eight can show.
FIELD = {
    "disabledbackground": "blue",
    "disabledforeground": "yellow",
    "readonlybackground": "magenta",
    "selectbackground": "cyan",
    "selectforeground": "black",
    "exportselection": False,
}


def build(root, screen):
    area = _support.content_area(root, top=4)
    fields = []

    def labelled(row, text, widget):
        tkcurses.Label(area, text=text, anchor="w").place(x=0, y=row + 1)
        widget.place(x=19, y=row)
        fields.append(widget)
        return widget

    plain = labelled(
        0, "a  plain", tkcurses.Entry(area, width=18, name="plain", **FIELD)
    )
    bar = labelled(
        3,
        "b  insertwidth=1",
        tkcurses.Entry(area, width=18, insertwidth=1, name="bar", **FIELD),
    )
    labelled(
        6,
        "c  insertofftime=0",
        tkcurses.Spinbox(
            area,
            width=16,
            name="steady",
            from_=0,
            to=9,
            insertofftime=0,
            buttonbackground="green",
            **FIELD,
        ),
    )
    orange = labelled(
        9,
        "d  insertbackground",
        tkcurses.Entry(
            area, width=18, insertbackground="#ff8000", name="orange", **FIELD
        ),
    )
    block = tkcurses.Text(
        area,
        name="block",
        width=18,
        height=3,
        blockcursor=True,
        selectbackground="cyan",
        selectforeground="black",
        inactiveselectbackground="green",
        exportselection=False,
    )
    tkcurses.Label(area, text="e  blockcursor=1", anchor="w").place(x=0, y=13)
    block.place(x=19, y=12)
    for entry, text in (
        (plain, "plain field"),
        (bar, "a thin bar"),
        (orange, "orange"),
    ):
        entry.insert(0, text)
        entry.selection_range(0, 5)
    block.insert("1.0", "a block cursor\nover the text")
    block.tag_add("sel", "1.2", "1.7")

    listbox = tkcurses.Listbox(
        area,
        name="listbox",
        width=20,
        height=4,
        selectbackground="cyan",
        selectforeground="black",
        disabledforeground="yellow",
    )
    for item in ("north", "south", "east", "west"):
        listbox.insert("end", item)
    listbox.selection_set(1)
    listbox.place(x=44, y=0)
    fields.append(listbox)

    chosen = tkcurses.IntVar(value=1)
    side = tkcurses.StringVar(value="left")
    pushed = tkcurses.IntVar(value=1)
    buttons = [
        tkcurses.Checkbutton(
            area,
            text="selectcolor=green",
            name="tick",
            variable=chosen,
            selectcolor="green",
            activebackground="red",
            activeforeground="yellow",
        ),
        tkcurses.Radiobutton(
            area,
            text="left",
            name="left",
            variable=side,
            value="left",
            selectcolor="green",
            activebackground="red",
            activeforeground="yellow",
        ),
        tkcurses.Radiobutton(
            area,
            text="right",
            name="right",
            variable=side,
            value="right",
            selectcolor="green",
            activebackground="red",
            activeforeground="yellow",
        ),
        tkcurses.Checkbutton(
            area,
            text="no indicator, on",
            name="pushed",
            variable=pushed,
            indicatoron=False,
            selectcolor="green",
        ),
        tkcurses.Button(
            area,
            text="Press me",
            name="press",
            activebackground="red",
            activeforeground="yellow",
        ),
    ]
    for row, button in zip((6, 7, 8, 9, 12), buttons, strict=True):
        button.place(x=44, y=row)
    scale = tkcurses.Scale(
        area,
        orient="horizontal",
        name="scale",
        length=20,
        from_=0,
        to=10,
        troughcolor="blue",
        activebackground="red",
        showvalue=False,
    )
    scale.place(x=44, y=16)
    actives = [*buttons, scale]
    state = {"field": 0, "active": False, "hidden": False}

    def report(*_):
        focus = root.focus_get()
        name = focus.winfo_name() if focus is not None else "-"
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  fields: {STATES[state['field']]}   buttons: "
            f"{'active' if state['active'] else 'normal'}   "
            f"text's unfocused selection: {'hidden' if state['hidden'] else 'green'}",
        )
        screen.line(2, f"  focus: {name}")
        screen.line(
            3,
            "  Tab or F8 moves the focus, or click   F5 field state"
            "   F6 active   F7 hide",
        )
        screen.footer(" Escape quits - then check your shell's cursor ")
        screen.refresh()

    def cycle_fields(_event):
        state["field"] = (state["field"] + 1) % len(STATES)
        wanted = STATES[state["field"]]
        for widget in fields:
            readonly = isinstance(widget, tkcurses.Entry)
            widget.configure(
                state=wanted if readonly or wanted != "readonly" else "normal"
            )
        block.configure(state="disabled" if wanted == "disabled" else "normal")
        report()
        return "break"

    def toggle_active(_event):
        state["active"] = not state["active"]
        for widget in actives:
            widget.configure(state="active" if state["active"] else "normal")
        report()
        return "break"

    def toggle_hidden(_event):
        state["hidden"] = not state["hidden"]
        block.configure(inactiveselectbackground="" if state["hidden"] else "green")
        report()
        return "break"

    def focus_next(_event):
        current = root.focus_get() or plain
        following = current.tk_focusNext()
        if following is not None:
            following.focus_set()
        root.after_idle(report)
        return "break"

    root.bind_all("<F5>", cycle_fields)
    root.bind_all("<F6>", toggle_active)
    root.bind_all("<F7>", toggle_hidden)
    root.bind_all("<F8>", focus_next)
    root.bind_all("<FocusIn>", lambda _event: root.after_idle(report), add="+")
    plain.focus_set()
    root.after(50, report)


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
