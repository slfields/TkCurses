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

"""Key sequences - chords such as Ctrl-X Ctrl-S, and "gg".

What to do: press the chords listed on screen, then press them with
something in between, or slowly.

What to look for: **the readout**, which shows the last key pressed and every
chord that has fired. The rules are Tk's, read from its source and measured in
both Tk 8.6 and 9.0 (TkCurses-jfm): another key or a click in between cancels
a chord; nothing else does, and there is no time limit.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "45 - Key sequences"

#: The chords bound, what each says when it fires.
CHORDS = (
    ("<Control-x><Control-s>", "save", "Ctrl-X then Ctrl-S"),
    ("<Control-x><Control-f>", "find", "Ctrl-X then Ctrl-F"),
    ("gg", "top", "g then g"),
    ("<Key-d><Key-d>", "delete line", "d then d"),
)


def build(root, screen):
    screen.line(0, f" {TITLE} ")
    screen.footer(" press the chords listed - Esc quits ")
    area = _support.content_area(root, top=5, bottom=1)
    fired: list[str] = []
    last = {"key": "-"}

    tkcurses.Label(
        area,
        name="help",
        anchor="w",
        justify="left",
        text="\n".join(f"{keys:<22} {name}" for _sequence, name, keys in CHORDS),
    ).place(x=2, y=1, width=50, height=len(CHORDS))
    pad = tkcurses.Frame(area, name="pad", width=4, height=1)
    pad.place(x=0, y=0)

    def show():
        screen.line(1, f" last key: {last['key']}")
        screen.line(2, f" chords: {', '.join(fired[-6:]) or '(none yet)'}")
        focus = root.focus_get()
        screen.line(
            3,
            f" fired {len(fired)} time(s)   focus: "
            f"{focus.winfo_name() if focus is not None else '-'}",
        )
        screen.refresh()

    for sequence, name, _keys in CHORDS:
        pad.bind(sequence, lambda event, name=name: (fired.append(name), show()))

    def key(event):
        last["key"] = event.keysym
        show()

    # On "all", after the pad's own bindings, so it sees every key whatever
    # the pad's chords did with it.
    root.bind_all("<Key>", key, add="+")

    def clear(event=None):
        del event
        fired.clear()
        last["key"] = "-"
        # And the focus back: a click elsewhere may have taken it, and the
        # chords are bound on the pad.
        pad.focus_set()
        show()
        return "break"

    root.bind_all("<Control-r>", clear, add="+")
    pad.focus_set()
    show()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
