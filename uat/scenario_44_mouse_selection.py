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

"""Selecting with the mouse - double, triple and shift-clicks, and autoscroll.

What to do: double-click words, triple-click lines, shift-click or alt-click to
extend a selection, and drag past the edge of the narrow field and the text.
GNOME Terminal and the other VTE terminals never send a shift-click to a
program - measured - so Alt-click does the same here. A Ctrl-click moves the
cursor and leaves the selection where it is (TkCurses-mndh).

What to look for: **the readout under the title**. It names the click that
was recognised - a double-click has to land within 200ms on the same cell, so
a slow one arrives as two single clicks, and this is where you can tell - and
shows what is selected and where the cursor is, in whichever widget has the
focus.

The rules come from Tk's own bindings, read from the running interpreter and
measured on Tk 9.0.2 (TkCurses-svtr). The classic and the ttk entries differ
on purpose - Tk's do too - and the checklist says where.
"""

from __future__ import annotations

import tkcurses
from tkcurses import ttk
from uat import _support

TITLE = "44 - Selecting with the mouse"

WORDS = "hello, world  foo_bar-baz 42.5"
LONG = "the quick brown fox jumps over the lazy dog - " * 2
TEXT = "\n".join(
    [
        "one two three four",
        "foo  ",
        "  bar",
        "",
        "a line much longer than the text is wide, to scroll sideways along",
    ]
    + [f"line {n:02} of the scrolling part" for n in range(6, 41)]
)

#: Row in the content area, name, label, the widget class and its text.
FIELDS = (
    (0, "entry", "Entry", tkcurses.Entry, WORDS),
    (3, "tentry", "ttk.Entry", ttk.Entry, WORDS),
    (6, "spinbox", "Spinbox", tkcurses.Spinbox, "one two three"),
    (9, "tspinbox", "ttk.Spinbox", ttk.Spinbox, "one two three"),
    (12, "long", "narrow", tkcurses.Entry, LONG),
)


def build(root, screen):
    screen.line(0, f" {TITLE} ")
    screen.footer(
        " double: word   triple: all/line   shift or alt: extend   Esc quits "
    )
    area = _support.content_area(root, top=4, bottom=1)
    widgets = {}
    last = {"text": "nothing yet"}

    for y, name, label, kind, text in FIELDS:
        tkcurses.Label(area, name=f"l{name}", text=label, anchor="w").place(
            x=2, y=y + 1, width=14
        )
        options = {"from_": 0, "to": 10} if "spin" in name else {}
        widget = kind(area, name=name, **options)
        widget.place(x=17, y=y, width=32)
        widget.delete(0, "end")
        widget.insert(0, text)
        widget.icursor(0)
        widgets[name] = widget
    widgets["long"].place_configure(width=22)
    text = tkcurses.Text(area, name="text", width=34, height=12, wrap="none")
    text.place(x=52, y=0, width=36, height=14)
    text.insert("1.0", TEXT)
    text.mark_set("insert", "1.0")
    text.yview("moveto", 0)
    widgets["text"] = text

    def clicked(kind):
        def report(event):
            last["text"] = f"{kind} on {event.widget.winfo_name()}"

        return report

    # Reported from the "all" tag, after the widget's own class binding has
    # run, so this watches what the person did without taking part in it.
    root.bind_all("<Button-1>", clicked("click"), add="+")
    root.bind_all("<Double-Button-1>", clicked("double-click"), add="+")
    root.bind_all("<Triple-Button-1>", clicked("triple-click"), add="+")
    root.bind_all("<Shift-Button-1>", clicked("shift-click"), add="+")
    root.bind_all("<Alt-Button-1>", clicked("alt-click"), add="+")
    root.bind_all("<Control-Button-1>", clicked("ctrl-click"), add="+")

    def selection_of(widget):
        if isinstance(widget, tkcurses.Text):
            found = widget.tag_ranges("sel")
            if not found:
                return "(none)", widget.index("insert")
            first, last_ = str(found[0]), str(found[1])
            return f"{first}-{last_} {widget.get(first, last_)!r}", widget.index(
                "insert"
            )
        if not widget.selection_present():
            return "(none)", widget.index("insert")
        first, last_ = widget.index("sel.first"), widget.index("sel.last")
        return f"{first}-{last_} {widget.get()[first:last_]!r}", widget.index("insert")

    def describe():
        """Polled, so the readout depends on none of the bindings under test."""
        focus = root.focus_get()
        name = focus.winfo_name() if focus is not None else "-"
        if focus in widgets.values():
            selected, cursor = selection_of(focus)
        else:
            selected, cursor = "-", "-"
        screen.line(1, f" last: {last['text']}")
        screen.line(2, f" focus: {name:<9} cursor: {cursor}")
        screen.line(3, f" selected: {selected[:70]}")
        screen.refresh()
        root.after(100, describe)

    widgets["entry"].focus_set()
    describe()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
