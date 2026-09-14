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

"""Checkbuttons and radiobuttons: one variable, more than one reader.

What to do: click the boxes, and move between them with Tab and the space
bar. Press s to set the size from code rather than by clicking, c to put the
read-only box back into its third state, and r to reset everything.
What to look for: every widget bound to a variable moves when the variable
does, whoever moved it - the second views on the right-hand side of each box
are separate widgets over the same variables, and the line at the top is a
third reader. Only one radiobutton can be on at a time, and nothing turns
the others off; they all read the same variable. The focused widget shows
angle brackets instead of square ones, and its width does not change.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "20 - checkbutton and radiobutton: one variable, two readers"


def build(root, screen):
    area = _support.content_area(root, top=4)

    wrap = tkcurses.StringVar(root, "off")
    bold = tkcurses.IntVar(root, 0)
    files = tkcurses.StringVar(root, "some")
    size = tkcurses.StringVar(root, "medium")
    last = {"command": "-"}

    def report(*_):
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  wrap={wrap.get()!r}  bold={bold.get()!r}  "
            f"files={files.get()!r}  size={size.get()!r}",
        )
        screen.line(2, f"  last command: {last['command']}")
        screen.line(
            3, "  Tab and space move and press.  s sets size  c clears  r resets"
        )
        screen.footer(" Escape quits ")
        screen.refresh()

    for variable in (wrap, bold, files, size):
        variable.trace_add("write", report)

    def note(what):
        def run():
            last["command"] = what
            report()

        return run

    row = tkcurses.Frame(area)
    row.pack(side="top", fill="both", expand=True)

    checks = _support.labelled_box(row, "Checkbuttons")
    checks.pack(side="left", fill="both", expand=True, padx=1)
    # onvalue and offvalue that are not 1 and 0, which is the case that
    # catches a widget storing a bool and hoping for the best.
    tkcurses.Checkbutton(
        checks,
        text="Wrap lines  (on/off)",
        variable=wrap,
        onvalue="on",
        offvalue="off",
        command=note("wrap toggled"),
    ).pack(anchor="w", padx=1)
    tkcurses.Checkbutton(
        checks, text="Bold  (1/0)", variable=bold, command=note("bold toggled")
    ).pack(anchor="w", padx=1)
    # Starts in Tk's third state: neither value, so neither tick nor blank.
    tkcurses.Checkbutton(
        checks, text="Read-only files", variable=files, tristatevalue="some"
    ).pack(anchor="w", padx=1)
    tkcurses.Label(checks, text="no box - reverses when on:", anchor="w").pack(
        anchor="w", padx=1
    )
    tkcurses.Checkbutton(checks, text="Bold", variable=bold, indicatoron=False).pack(
        anchor="w", padx=1
    )
    tkcurses.Label(checks, text="second view of the same two:", anchor="w").pack(
        anchor="w", padx=1
    )
    tkcurses.Checkbutton(
        checks, text="Wrap lines", variable=wrap, onvalue="on", offvalue="off"
    ).pack(anchor="w", padx=1)
    tkcurses.Checkbutton(checks, text="Bold", variable=bold).pack(anchor="w", padx=1)

    radios = _support.labelled_box(row, "Radiobuttons")
    radios.pack(side="left", fill="both", expand=True, padx=1)
    for word in ("small", "medium", "large"):
        tkcurses.Radiobutton(
            radios,
            text=word.title(),
            variable=size,
            value=word,
            command=note(f"size -> {word}"),
        ).pack(anchor="w", padx=1)
    tkcurses.Label(radios, text="second view of the same group:", anchor="w").pack(
        anchor="w", padx=1
    )
    for word in ("small", "medium", "large"):
        tkcurses.Radiobutton(radios, text=word.title(), variable=size, value=word).pack(
            anchor="w", padx=1
        )

    def reset(event):
        wrap.set("off")
        bold.set(0)
        files.set("some")
        size.set("medium")
        last["command"] = "-"
        report()
        return "break"

    root.bind_all("<Key-s>", lambda event: size.set("large"))
    root.bind_all("<Key-c>", lambda event: files.set("some"))
    root.bind_all("<Key-r>", reset)
    root.tk_focusNext().focus_set()
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
