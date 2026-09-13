"""Menus: a bar, dropdowns, submenus, popups, and the two awkward cases.

What to do: click File or View in the bar, or press F2 to open File from the
keyboard. Move with the arrows - Left and Right walk along the bar, Up and
Down through a dropdown, Right opens a submenu and Left closes it. Escape
dismisses. Right-click anywhere for a popup, including **near the bottom
right corner**. Press F3 for a menu with more entries than the terminal has
rows.
What to look for: a dropdown covers the window beneath it and disappears
cleanly, leaving no marks behind. Clicking away from a menu closes it.
Accelerators are right-aligned and the underlined letter chooses its entry.
The two cases worth the trouble: a popup near an edge is **moved** so that
all of it is on screen rather than being cut off, and a menu too tall to fit
scrolls with the arrows instead of losing its last entries.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "25 - menu: bar, dropdowns, popups and edges"


def build(root, screen):
    area = _support.content_area(root, top=5)
    wrap = tkcurses.IntVar(root, 1)
    size = tkcurses.StringVar(root, "medium")
    state = {"last": "-"}

    def chose(what):
        def run():
            state["last"] = what
            report()

        return run

    bar = tkcurses.Menu(root)

    files = tkcurses.Menu(bar)
    files.add_command(
        label="New", accelerator="Ctrl+N", underline=0, command=chose("New")
    )
    files.add_command(
        label="Open...", accelerator="Ctrl+O", underline=0, command=chose("Open")
    )
    files.add_separator()
    files.add_command(label="Disabled", state="disabled", command=chose("never"))
    files.add_separator()
    files.add_command(
        label="Quit", accelerator="Ctrl+Q", underline=0, command=root.quit
    )
    bar.add_cascade(label="File", menu=files, underline=0)

    view = tkcurses.Menu(bar)
    view.add_checkbutton(label="Wrap lines", variable=wrap, command=chose("wrap"))
    view.add_separator()
    for word in ("small", "medium", "large"):
        view.add_radiobutton(
            label=word.title(), variable=size, value=word, command=chose(word)
        )
    deeper = tkcurses.Menu(view)
    for word in ("One", "Two", "Three"):
        deeper.add_command(label=f"Deeper {word}", command=chose(f"deeper {word}"))
    view.add_cascade(label="More", menu=deeper, underline=0)
    bar.add_cascade(label="View", menu=view, underline=0)

    root.configure(menu=bar)

    popup = tkcurses.Menu(root)
    for word in ("Cut", "Copy", "Paste"):
        popup.add_command(label=word, command=chose(word))
    popup.add_separator()
    popup.add_command(label="Select all", command=chose("Select all"))

    tall = tkcurses.Menu(root)
    for number in range(40):
        tall.add_command(label=f"Item {number:02d}", command=chose(f"item {number}"))

    tkcurses.Label(
        area,
        text="Right-click anywhere - including the bottom right corner.",
        anchor="w",
    ).pack(side="top", fill="x", padx=1, pady=1)

    def report(*_):
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  wrap={wrap.get()!r}  size={size.get()!r}  last chosen: {state['last']}",
        )
        screen.line(2, "  Click the bar, or F2 to open File from the keyboard.")
        screen.line(3, "  Arrows move.  Escape closes.  Right-click for a popup.")
        screen.line(4, "  F3 posts a menu taller than this terminal.")
        screen.footer(" Escape quits ")
        screen.refresh()

    for variable in (wrap, size):
        variable.trace_add("write", report)

    def open_file(event):
        bar.activate(0)
        bar.invoke(0)
        return "break"

    def post_tall(event):
        tall.post(2, 2)
        return "break"

    root.bind_all("<Key-F2>", open_file)
    root.bind_all("<Key-F3>", post_tall)
    root.bind_all(
        "<Button-3>", lambda event: popup.tk_popup(event.x_root, event.y_root)
    )
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
