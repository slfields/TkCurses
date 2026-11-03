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

"""Scales: reaching both ends by keyboard and by mouse.

What to do: Tab between the scales. Move the focused one with the arrows,
Control-arrow, Page Up/Down, Home and End. Click in a trough, and hold the
button down there; middle-click in a trough; drag the handle. Resize the
terminal while you are here.
What to look for: every scale reaches both of its ends and stops there. The
second row is the same variable as the first, so moving either moves the
other and the number at the top. The reversed scale counts down from 10 to
0 and its End key goes to 0, because End means `to`, not `largest`. The
fractional scale shows one decimal and no floating-point dust. The focused
scale shows [ and ] at the ends of its trough, and nothing moves when the
focus arrives.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "21 - scale: values by keyboard and mouse"


def build(root, screen):
    area = _support.content_area(root, top=4)

    volume = tkcurses.IntVar(root, 3)
    bass = tkcurses.IntVar(root, 10)
    mix = tkcurses.DoubleVar(root, 0.5)
    last = {"command": "-"}

    def report(*_):
        screen.line(0, f" {TITLE} ")
        screen.line(
            1, f"  volume={volume.get()!r}  bass={bass.get()!r}  mix={mix.get()!r}"
        )
        screen.line(2, f"  last command: {last['command']}")
        screen.line(
            3, "  Tab moves focus.  arrows / Ctrl-arrow / PgUp / Home / End.  drag too"
        )
        screen.footer(" Escape quits ")
        screen.refresh()

    for variable in (volume, bass, mix):
        variable.trace_add("write", report)

    def note(what):
        def run(value):
            last["command"] = f"{what} -> {value}"
            report()

        return run

    # An explicit height: labelled_box turns propagation off, so a box packed
    # with fill="x" and nothing else collapses to nothing and takes its
    # contents with it - which is exactly what happened the first time.
    top = _support.labelled_box(area, "Horizontal 0..10, ticks every 5", height=9)
    top.pack(side="top", fill="x", padx=1)
    tkcurses.Scale(
        top,
        orient="horizontal",
        from_=0,
        to=10,
        length=30,
        label="Volume",
        tickinterval=5,
        variable=volume,
        command=note("volume"),
    ).pack(anchor="w", padx=1)
    # The same variable again: moving either handle moves both.
    tkcurses.Scale(
        top,
        orient="horizontal",
        from_=0,
        to=10,
        length=30,
        label="Volume (second view)",
        variable=volume,
    ).pack(anchor="w", padx=1)

    row = tkcurses.Frame(area)
    row.pack(side="top", fill="both", expand=True)

    reversed_box = _support.labelled_box(row, "Reversed: from 10 to 0")
    reversed_box.pack(side="left", fill="both", expand=True, padx=1)
    tkcurses.Scale(
        reversed_box,
        orient="horizontal",
        from_=10,
        to=0,
        length=20,
        label="Bass",
        tickinterval=5,
        variable=bass,
        command=note("bass"),
    ).pack(anchor="w", padx=1)

    fractional = _support.labelled_box(row, "Vertical, 0..1 by 0.1")
    fractional.pack(side="left", fill="both", expand=True, padx=1)
    tkcurses.Scale(
        fractional,
        from_=0,
        to=1,
        resolution=0.1,
        length=8,
        label="Mix",
        variable=mix,
        command=note("mix"),
    ).pack(side="left", padx=1)
    tkcurses.Label(fractional, textvariable=mix, width=6).pack(side="left", padx=1)

    root.tk_focusNext().focus_set()
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
