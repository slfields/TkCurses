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

"""Timers firing while nothing else happens.

What to do: leave it alone for half a minute, then type.
What to look for: the clock keeps ticking once a second without you touching
anything, the process stays near zero CPU while idle (check with top), and
typing is still answered immediately while the clock runs.
"""

from __future__ import annotations

import time

from uat import _support

TITLE = "07 - timers and idling"


def build(root, screen):
    started = time.monotonic()
    ticks = [0]

    def tick():
        ticks[0] += 1
        screen.line(
            3, f"  ticks: {ticks[0]:>4}   running: {time.monotonic() - started:6.1f}s"
        )
        screen.refresh()
        root.after(1000, tick)

    def typed(event):
        screen.line(5, f"  last key: {event.keysym} (answered while the clock runs)")
        screen.refresh()

    screen.lines(
        1,
        [
            "A timer updates the line below once a second.",
            "",
            "",
            "",
            "",
            "Idle CPU should be negligible: the loop sleeps between events.",
        ],
    )
    root.bind("<Any-Key>", typed)
    root.after(1000, tick)


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
