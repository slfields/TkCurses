"""Text: editing past the edges of the window, wrapping, tags and selection.

What to do: type. Use the arrows, Home, End, Page Up and Page Down. Select
with Shift and the arrows, and by dragging with the mouse. Press F2 to cycle
the wrap mode, F3 to add a very long line, F4 to tag the word under the
cursor. Resize the terminal.
What to look for: the cursor is visible only while the widget has the focus,
and the view follows it in both directions - down past the last visible line,
and sideways when wrapping is off. Changing the wrap mode re-flows text that
is already in the buffer, and no line ever runs over the border. The index at
the top is line.char counting from 1, and `end` is one line past the last,
which is Tk's rule and not a fault.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "23 - text: editing, wrapping, tags and selection"

WRAPS = ("word", "char", "none")

PARAGRAPH = (
    "A Text widget is a window onto something bigger than itself. "
    "Everything is addressed by index, written line.char with lines counting "
    "from 1. Marks survive editing; tags describe ranges that move with the "
    "text under them.\n"
    "This is a second paragraph, so that Up and Down have somewhere to go.\n"
)


def build(root, screen):
    area = _support.content_area(root, top=4)
    state = {"wrap": 0}

    row = tkcurses.Frame(area)
    row.pack(side="top", fill="both", expand=True, padx=1)
    text = tkcurses.Text(row, width=40, height=10, wrap=WRAPS[0])
    text.pack(side="left", fill="both", expand=True)
    bar = tkcurses.Scrollbar(row, command=text.yview)
    bar.pack(side="left", fill="y")
    text.configure(yscrollcommand=bar.set)

    text.insert("1.0", PARAGRAPH * 3)
    text.tag_configure("found", background="yellow", foreground="black")
    text.mark_set("insert", "1.0")
    text.see("1.0")

    def report(*_):
        try:
            selection = text.get("sel.first", "sel.last")
        except Exception:
            selection = ""
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  insert={text.index('insert')}  end={text.index('end')}  "
            f"wrap={WRAPS[state['wrap']]!r}  selected={len(selection)} chars",
        )
        screen.line(2, "  Type. Shift+arrows or drag to select.")
        screen.line(3, "  F2 wrap mode   F3 add a long line   F4 tag the word")
        screen.footer(" Escape quits ")
        screen.refresh()

    def next_wrap(event):
        state["wrap"] = (state["wrap"] + 1) % len(WRAPS)
        text.configure(wrap=WRAPS[state["wrap"]])
        text.see("insert")
        report()
        return "break"

    def add_long_line(event):
        text.insert("insert lineend", "\n" + "long " * 30)
        text.see("insert")
        report()
        return "break"

    def tag_word(event):
        text.tag_add("found", "insert wordstart", "insert wordend")
        report()
        return "break"

    text.bind("<Key>", lambda event: root.after_idle(report), add=True)
    text.bind("<Button-1>", lambda event: root.after_idle(report), add=True)
    text.bind("<Motion>", lambda event: root.after_idle(report), add=True)
    root.bind_all("<Key-F2>", next_wrap)
    root.bind_all("<Key-F3>", add_long_line)
    root.bind_all("<Key-F4>", tag_word)
    text.focus_set()
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
