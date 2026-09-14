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

"""The ways an application can end, and what the terminal looks like after.

What to do: run this three times, choosing a different ending each time -
press q to quit cleanly, c for a callback that raises, x to end the
application from inside a callback. Then press Ctrl-C on a fourth run.
What to look for: after every one of the four, the terminal is usable - prompt
back, cursor visible, typing echoed, no leftover raw mode. A callback that
raises must NOT end the application; the other three must.

The traceback from 'c' is held back while the screen is up, because stderr
here is the same terminal curses is drawing on. The display should be
untouched - the count on screen is the only sign anything went wrong - and
every traceback should appear after the application exits, one per press,
each line starting at the left edge. A traceback that steps further right
down the screen means the line endings are wrong for a terminal that has
just left curses mode.
"""

from __future__ import annotations

from uat import _support

TITLE = "09 - failure modes"


def build(root, screen):
    survived = [0]

    def broken_callback():
        raise RuntimeError("this callback was supposed to fail")

    def callback_raises(event):
        survived[0] += 1
        screen.line(6, f"  a callback raised {survived[0]} time(s) - still running")
        screen.refresh()
        root.after(1, broken_callback)

    def escapes(event):
        # A plain exception here would be caught and reported by the loop,
        # like the one behind 'c'. SystemExit is one of the two the loop
        # deliberately lets through, being the application asking to leave.
        raise SystemExit("ending from inside a callback")

    screen.lines(
        1,
        [
            "  q  quit cleanly",
            "  c  a callback raises - the application should survive",
            "  x  SystemExit from a callback - the application should end",
            "     Ctrl-C also ends it",
            "",
            "",
            "Check the terminal is usable after each ending.",
        ],
    )
    root.bind("<Key-q>", lambda event: root.quit())
    root.bind("<Key-c>", callback_raises)
    root.bind("<Key-x>", escapes)


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
