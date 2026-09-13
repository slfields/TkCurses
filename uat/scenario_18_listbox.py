"""Listboxes: selecting, scrolling, and the four selection modes.

What to do: press m to cycle the selection mode. Move with the arrows, Home,
End, Page Up and Page Down. Click rows, and Shift-click in extended mode. Use
the scroll wheel if your terminal sends one.
What to look for: the selected rows are marked at both ends; in browse mode
the selection follows the arrows, and in single mode the arrows move an
underlined *active* row while the selection stays put - the two are different
things. The scrollbar's thumb tracks the view, and the count below matches
what is marked.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "18 - listbox: selection and scrolling"

MODES = ["browse", "single", "multiple", "extended"]


def build(root, screen):
    area = _support.content_area(root)
    state = {"mode": "browse"}

    row = tkcurses.Frame(area)
    row.pack(side="top", fill="both", expand=True, pady=1)
    listbox = tkcurses.Listbox(row, width=24, height=8)
    listbox.pack(side="left", fill="y")
    bar = tkcurses.Scrollbar(row, command=listbox.yview)
    bar.pack(side="left", fill="y")
    listbox.configure(yscrollcommand=bar.set)
    listbox.insert("end", *[f"row {n:02d}" for n in range(30)])

    def report(event=None):
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  mode={state['mode']}  selected={listbox.curselection()}  "
            f"active={listbox.index('active')}   m cycles the mode",
        )
        screen.footer(" Escape quits ")
        screen.refresh()

    def cycle_mode(event):
        state["mode"] = MODES[(MODES.index(state["mode"]) + 1) % len(MODES)]
        listbox.configure(selectmode=state["mode"])
        listbox.selection_clear(0, "end")
        report()
        return "break"

    listbox.bind("<<ListboxSelect>>", report)
    root.bind_all("<Key-m>", cycle_mode)
    listbox.focus_set()
    listbox.activate(0)
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
