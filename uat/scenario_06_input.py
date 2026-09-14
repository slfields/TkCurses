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

"""Keys and mouse, as the application sees them.

What to do: type letters, arrows, function keys and modified keys; click and
drag with the mouse if your terminal reports it.
What to look for: every key you press is named on screen and the name matches
the key, modifiers are reported, and mouse positions match where you clicked.
"""

from __future__ import annotations

from uat import _support

TITLE = "06 - keyboard and mouse"


def build(root, screen):
    history = []

    def record(text):
        history.append(text)
        del history[: max(0, len(history) - 10)]
        screen.lines(4, [line.ljust(screen.width) for line in history])
        screen.lines(4 + len(history), [""] * (10 - len(history)))
        screen.refresh()

    def key(event):
        record(
            f"key    keysym={event.keysym!r} char={event.char!r} state={event.state}"
        )

    def button(event):
        record(f"button num={event.num} at ({event.x_root},{event.y_root})")

    def motion(event):
        record(f"motion at ({event.x_root},{event.y_root})")

    screen.lines(2, ["Press keys or use the mouse. The last ten events show below."])
    root.bind("<Any-Key>", key)
    root.bind("<Any-Button>", button)
    root.bind("<Motion>", motion)


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
