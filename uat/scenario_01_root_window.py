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

"""A root window that opens and closes cleanly.

What to do: watch the screen come up, then press Escape.
What to look for: the terminal clears, the title line is readable, and after
Escape your shell prompt is back with the cursor visible and typing works.
"""

from __future__ import annotations

from uat import _support

TITLE = "01 - root window"


def build(root, screen):
    screen.lines(
        2,
        [
            "The screen below this line is the root window.",
            "",
            "It should fill the terminal, and leave no stray output behind",
            "when it closes. After Escape, check that:",
            "",
            "  * your prompt is back",
            "  * the cursor is visible again",
            "  * what you type appears",
        ],
    )


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
