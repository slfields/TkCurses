"""A variable, and the traces watching it.

What to do: press + and - to change the count, r to reset.
What to look for: both lines update together, and the trace line reports every
change exactly once.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "08 - variables and traces"


def build(root, screen):
    count = tkcurses.IntVar(root, value=0)
    writes = [0]

    def changed(name, index, mode):
        writes[0] += 1
        screen.line(4, f"  trace fired {writes[0]} time(s), mode={mode}")
        screen.line(3, f"  value seen by the trace: {count.get()}")
        screen.refresh()

    count.trace_add("write", changed)

    screen.lines(1, ["  + increases, - decreases, r resets", "", "", ""])
    # <Key-plus> and <Key-minus>, the tkinter spellings, do not match yet:
    # punctuation reports the character rather than the X11 keysym name.
    # Tracked as TkCurses-82n.
    root.bind("<Key-+>", lambda event: count.set(count.get() + 1))
    root.bind("<Key-=>", lambda event: count.set(count.get() + 1))
    root.bind("<Key-->", lambda event: count.set(count.get() - 1))
    root.bind("<Key-r>", lambda event: count.set(0))
    changed(str(count), "", "write")


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
