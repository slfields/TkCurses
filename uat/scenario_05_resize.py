"""Resizing the terminal while the application runs.

What to do: drag your terminal's edge, or run `resize` in another pane.
What to look for: the reported size follows the real one, the window stays
inside the screen, and nothing is left drawn outside the new bounds.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "05 - terminal resize"


def build(root, screen):
    window = tkcurses.Toplevel(root, width=24, height=6)
    window.title("stays inside")
    resizes = [0]

    def resized(event):
        resizes[0] += 1
        screen.clear()
        screen.line(0, f" {TITLE} ")
        screen.lines(
            2,
            [
                f"terminal is now {root.winfo_width()}x{root.winfo_height()}",
                f"resizes seen: {resizes[0]}",
                "",
                "Make the terminal smaller than the window and check that",
                "the window is clamped rather than drawn off the edge.",
            ],
        )
        screen.footer(" Escape quits ")
        window.geometry(f"{window.winfo_width()}x{window.winfo_height()}")
        screen.refresh()

    screen.lines(2, [f"terminal is {root.winfo_width()}x{root.winfo_height()}"])
    root.bind("<Configure>", resized)


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
