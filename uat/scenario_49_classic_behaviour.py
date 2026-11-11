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

"""How classic widgets behave: reliefs, holding a button, spacing, sashes.

What to do: **hold** the mouse on the Spinbox's arrows, on **Hold me**, in the
scale's trough and on the scrollbar's arrows, and watch each keep going after
a short pause. **F5** turns the scrollbar's ``jump`` on. **F6** turns the
Text's line spacing off and on; type in it and **F8** undoes, three steps at
most. **F7** turns the paned window's ``opaqueresize`` off; drag its sash.

What to look for: **six reliefs**, each its own box; **repeats that start
after the delay and stop when you let go**; **blank rows between the Text's
lines**; **a proxy line that the panes follow only on the release**.
TkCurses-gm66.5, .6, .8 and .9.
"""

from __future__ import annotations

import contextlib

import tkcurses
from uat import _support

TITLE = "49 - How classic widgets behave"

RELIEFS = ("flat", "raised", "sunken", "solid", "ridge", "groove")

PARAGRAPHS = "Blank rows above each line and between wrapped rows.\nA second line."


def build(root, screen):
    area = _support.content_area(root, top=4)
    state = {"fired": 0, "spaced": True}

    x = 0
    for relief in RELIEFS:
        tkcurses.Label(
            area, text=relief, relief=relief, borderwidth=1, name=relief
        ).place(x=x, y=0)
        x += len(relief) + 3
    toggle = tkcurses.Checkbutton(
        area,
        text="toggle",
        name="toggle",
        indicatoron=False,
        borderwidth=1,
        relief="raised",
        offrelief="groove",
    )
    toggle.place(x=x + 1, y=0)

    tkcurses.Label(area, text="Spinbox", anchor="w").place(x=0, y=4)
    spin = tkcurses.Spinbox(
        area,
        name="spin",
        from_=0,
        to=999,
        width=8,
        # Tk draws no arrow in its relief option: this changes nothing.
        buttonuprelief="sunken",
        repeatdelay=400,
        repeatinterval=100,
    )
    spin.place(x=12, y=4)

    def fired():
        state["fired"] += 1

    tkcurses.Button(
        area,
        text="Hold me",
        name="hold",
        command=fired,
        repeatdelay=500,
        repeatinterval=100,
    ).place(x=12, y=7)

    tkcurses.Label(area, text="Scale", anchor="w").place(x=0, y=10)
    scale = tkcurses.Scale(
        area,
        name="scale",
        orient="horizontal",
        from_=0,
        to=100,
        length=26,
        sliderlength=3,
        showvalue=False,
    )
    scale.place(x=12, y=10)

    listbox = tkcurses.Listbox(area, name="list", width=20, height=6)
    for number in range(1, 61):
        listbox.insert("end", f"item {number:02}")
    bar = tkcurses.Scrollbar(area, name="bar", command=listbox.yview)
    listbox.configure(yscrollcommand=bar.set)
    listbox.place(x=0, y=11)
    bar.place(x=22, y=11, height=8)

    text = tkcurses.Text(
        area,
        name="text",
        width=34,
        height=7,
        wrap="word",
        spacing1=1,
        spacing2=1,
        undo=True,
        maxundo=3,
    )
    text.insert("1.0", PARAGRAPHS)
    text.edit_reset()
    text.place(x=40, y=4)

    panes = tkcurses.PanedWindow(
        area, name="panes", sashpad=1, borderwidth=1, relief="sunken"
    )
    for side in ("left", "right"):
        pane = tkcurses.Frame(panes, name=side, width=15, height=3)
        tkcurses.Label(pane, text=side).place(x=1, y=1)
        # Room for the label and a cell either side. Narrower, and the label
        # would draw past the pane - a child is not yet clipped to its
        # container, TkCurses-wbov.
        panes.add(pane, minsize=len(side) + 2)
    panes.place(x=40, y=13, width=34, height=5)

    def on(flag):
        return "on" if flag else "off"

    def report():
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  held button: {state['fired']}   scale: {scale.get()}"
            f"   list top: {listbox.get(listbox.nearest(0))}"
            f"   jump: {on(bar.getboolean(bar.cget('jump')))}",
        )
        screen.line(
            2,
            f"  spacing: {on(state['spaced'])}"
            f"   undo groups: {text._buffer.undo_depth} of 3"
            f"   opaqueresize: {on(panes.getboolean(panes.cget('opaqueresize')))}",
        )
        screen.line(
            3,
            "  F5 jump   F6 spacing   F7 opaqueresize   F8 undo   F9 focus",
        )
        screen.footer(" Escape quits ")
        screen.refresh()

    def tick():
        report()
        root.after(150, tick)

    def toggle_jump(_event):
        bar.configure(jump=not bar.getboolean(bar.cget("jump")))
        report()
        return "break"

    def toggle_spacing(_event):
        state["spaced"] = not state["spaced"]
        rows = 1 if state["spaced"] else 0
        text.configure(spacing1=rows, spacing2=rows)
        report()
        return "break"

    def toggle_opaque(_event):
        panes.configure(opaqueresize=not panes.getboolean(panes.cget("opaqueresize")))
        report()
        return "break"

    def undo(_event):
        with contextlib.suppress(tkcurses.TclError):
            text.edit_undo()
        report()
        return "break"

    def focus_next(_event):
        current = root.focus_get() or text
        following = current.tk_focusNext()
        if following is not None:
            following.focus_set()
        return "break"

    root.bind_all("<F5>", toggle_jump)
    root.bind_all("<F6>", toggle_spacing)
    root.bind_all("<F7>", toggle_opaque)
    root.bind_all("<F8>", undo)
    root.bind_all("<F9>", focus_next)
    text.focus_set()
    text.mark_set("insert", "end")
    text.see("1.0")
    root.after(50, tick)


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
