"""Entries: typing, editing, scrolling and masking.

What to do: type into each field. Use the arrows, Home and End, Backspace and
Delete. Hold Shift with the arrows to select, then type over the selection.
Type more than fits in the narrow field.
What to look for: the cursor is visible in the focused field and *only* in the
focused one; text longer than the field scrolls within it rather than spilling
over the border; the password field shows stars but the plain copy below it
shows what you really typed; and the read-only field refuses every edit while
still letting you select and move about in it.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "17 - entry: typing, editing, scrolling"


def build(root, screen):
    area = _support.content_area(root)
    shared = tkcurses.StringVar(root, value="")

    def labelled(text, **options):
        row = tkcurses.Frame(area)
        row.pack(side="top", fill="x", pady=1)
        tkcurses.Label(row, text=text, width=12, anchor="w").pack(side="left")
        entry = tkcurses.Entry(row, **options)
        entry.pack(side="left")
        return entry

    first = labelled("normal:", width=24)
    labelled("narrow:", width=8)
    labelled("password:", width=24, show="*", textvariable=shared)
    labelled("same text:", width=24, textvariable=shared)
    readonly = labelled("read-only:", width=24)
    readonly.insert(0, "you cannot change this")
    readonly.configure(state="readonly")

    screen.line(0, f" {TITLE} ")
    screen.line(
        1, "  Tab moves between fields; the password and the copy share a variable"
    )
    screen.footer(" Escape quits ")
    first.focus_set()
    screen.refresh()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
