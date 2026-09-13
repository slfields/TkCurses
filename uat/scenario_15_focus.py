"""Focus: moving it, seeing it, and losing it.

What to do: press Tab and Shift-Tab to move between the three buttons and the
two entries. Press d to destroy whichever widget currently has the focus.
What to look for: the focused widget is always visibly marked - a button by
its arrows, an entry by its cursor - and you can tell at a glance which one
will answer the keyboard. Tab wraps round at the end. Destroying the focused
widget must not leave the focus pointing at something that no longer exists:
Tab afterwards should still work.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "15 - focus and traversal"


def build(root, screen):
    area = _support.content_area(root)
    row = tkcurses.Frame(area)
    row.pack(side="top", fill="x", pady=1)
    widgets = []
    for word in ("first", "second", "third"):
        # Named, so the focus report below reads as something a person can
        # match to what is on screen rather than as !button2.
        button = tkcurses.Button(row, text=word, name=word)
        button.pack(side="left", padx=1)
        widgets.append(button)
    for number in (1, 2):
        entry = tkcurses.Entry(area, width=18, name=f"field{number}")
        entry.pack(side="top", pady=1)
        widgets.append(entry)

    def report(event=None):
        focused = root.focus_get()
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  focus: {focused.winfo_name() if focused else 'nothing'}   "
            f"Tab and Shift-Tab move it, d destroys it",
        )
        screen.footer(" Escape quits ")
        screen.refresh()

    def destroy_focused(event):
        focused = root.focus_get()
        if focused is not None and focused is not root:
            focused.destroy()
            root.update_layout()
        report()
        return "break"

    root.bind_all("<FocusIn>", report)
    root.bind_all("<Key-d>", destroy_focused)
    widgets[0].focus_set()
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
