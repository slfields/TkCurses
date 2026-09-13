"""A window above the root, with a border and a title.

What to do: look at the window in the middle of the screen.
What to look for: a box drawn in single lines, its title centred on the top
edge, and the background text visible around it but not through it.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "02 - a window above the root"


def build(root, screen):
    for row in range(2, screen.height - 2):
        screen.line(row, "background " * (screen.width // 11 + 1))
    window = tkcurses.Toplevel(root, width=34, height=9)
    window.title("Hello")
    screen.line(1, "A bordered window should cover the middle of this text.")


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
