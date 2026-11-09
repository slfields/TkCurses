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

"""Menubuttons, option menus and panes you can drag.

What to do: click `File` for a menu, and the option menu beside it to choose
a size - the button shows what is chosen. Drag the sashes between the panes.
Tab to a paned window and move its sash with the arrows. Press F2 to add a
pane, F3 to remove one, F4 to turn the whole thing on its side. Resize the
terminal.
What to look for: a sash you have dragged **stays where you put it** when
anything else changes - adding a pane, resizing the terminal - because that
is the difference between a paned window and a row of packed frames. A pane
never shrinks below its minimum, and the panes always add up to the window
with the sashes in between.

The sashes move with the arrows as well as the mouse: a terminal user with
no mouse would otherwise have no way to resize a pane at all.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "26 - menubutton, option menu and panes"

WORDS = ("alpha", "beta", "gamma", "delta", "epsilon")


def build(root, screen):
    area = _support.content_area(root, top=5)
    size = tkcurses.StringVar(root, "medium")
    state = {"last": "-", "added": 0, "orient": "horizontal"}

    def chose(what):
        def run(*_):
            state["last"] = what
            report()

        return run

    bar = tkcurses.Frame(area)
    bar.pack(side="top", fill="x", padx=1)

    menu = tkcurses.Menu(bar)
    for word in ("Open", "Save", "Close"):
        menu.add_command(label=word, command=chose(word))
    tkcurses.Menubutton(
        bar, text="File", menu=menu, indicatoron=True, relief="raised"
    ).pack(side="left", padx=1)

    tkcurses.Label(bar, text="size:").pack(side="left", padx=1)
    tkcurses.OptionMenu(
        bar, size, "small", "medium", "large", command=chose("size")
    ).pack(side="left", padx=1)

    panes = tkcurses.PanedWindow(area, orient="horizontal")
    panes.pack(side="top", fill="both", expand=True, padx=1)

    def add_pane(label, minsize=8):
        frame = tkcurses.Frame(panes, relief="solid", bd=1)
        tkcurses.Label(frame, text=label).pack(fill="both", expand=True)
        panes.add(frame, minsize=minsize)
        return frame

    add_pane("first (min 8)")
    inner = tkcurses.PanedWindow(panes, orient="vertical")
    panes.add(inner, minsize=10)
    for label in ("nested top", "nested bottom"):
        frame = tkcurses.Frame(inner, relief="solid", bd=1)
        tkcurses.Label(frame, text=label).pack(fill="both", expand=True)
        inner.add(frame, minsize=3)

    def report(*_):
        widths = [child.winfo_width() for child in panes._paned.slaves()]
        screen.line(0, f" {TITLE} ")
        screen.line(1, f"  size={size.get()!r}   last chosen: {state['last']}")
        screen.line(2, f"  panes={len(widths)}  widths={widths}  {state['orient']}")
        screen.line(3, "  Drag a sash, or Tab to a pane and use the arrows.")
        screen.line(4, "  F2 add a pane   F3 remove one   F4 turn it on its side")
        screen.footer(" Escape quits ")
        screen.refresh()

    size.trace_add("write", report)

    def more(event):
        state["added"] += 1
        add_pane(WORDS[state["added"] % len(WORDS)])
        root.after_idle(report)
        return "break"

    def fewer(event):
        children = panes._paned.slaves()
        if len(children) > 1:
            panes.forget(children[-1])
        root.after_idle(report)
        return "break"

    def turn(event):
        state["orient"] = (
            "vertical" if state["orient"] == "horizontal" else "horizontal"
        )
        panes.configure(orient=state["orient"])
        root.after_idle(report)
        return "break"

    root.bind_all("<Key-F2>", more)
    root.bind_all("<Key-F3>", fewer)
    root.bind_all("<Key-F4>", turn)
    root.bind_all("<ButtonRelease-1>", lambda event: root.after_idle(report))
    # The widths on line 2 are measured, so they go stale the moment the
    # terminal changes size - which is exactly when someone is reading them.
    root.bind("<Configure>", lambda event: root.after_idle(report), add="+")
    root.after(100, report)


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
