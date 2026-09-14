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

"""Buttons: the three ways to press one, and one that refuses all of them.

What to do: click the first button, then focus it with Tab and press Return,
then Space. Try all three on the disabled one. Press f to make the enabled
button flash.
What to look for: all three gestures invoke the button and the count goes up
by exactly one each time - not two. The disabled button does nothing at all,
shows no focus markers, and Tab skips straight past it.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "16 - buttons: click, Return, Space"


def build(root, screen):
    area = _support.content_area(root)
    counts = {"pressed": 0, "refused": 0}

    def report():
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  pressed {counts['pressed']} times, the disabled one "
            f"{counts['refused']}   f flashes",
        )
        screen.footer(" Escape quits ")
        screen.refresh()

    def pressed():
        counts["pressed"] += 1
        report()

    def refused():
        counts["refused"] += 1
        report()

    live = tkcurses.Button(area, text="Press me", command=pressed)
    live.pack(side="top", pady=1)
    dead = tkcurses.Button(
        area, text="Disabled", command=refused, state="disabled", takefocus=False
    )
    dead.pack(side="top", pady=1)
    tkcurses.Label(
        area,
        text="The disabled button should never raise its count,\n"
        "and Tab should not stop on it.",
        justify="left",
    ).pack(side="top", pady=1)

    root.bind_all("<Key-f>", lambda event: live.flash())
    live.focus_set()
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
