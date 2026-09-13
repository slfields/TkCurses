"""Spinboxes, messages and captioned frames.

What to do: Tab between the spinboxes, step them with Up and Down and with
their arrows, and type into the two that allow it. Press F2 to change the
message aspect and F3 to move the captions - function keys rather than
letters, because a focused entry consumes every printable key. Resize the
terminal.
What to look for: every box in this scenario is a LabelFrame, so its caption
should sit on its border and never over its contents. The spinboxes' arrows
stay at the right-hand edge whatever is in them, and the readonly one refuses
typing while still stepping. The messages choose their own line length, and
the text always starts at the top - a paragraph too tall for its box loses
its end, never its beginning.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "22 - spinbox, message and labelframe"

PARAGRAPH = (
    "A Message picks its own line length, aiming for a block of text whose "
    "width is aspect percent of its height. Resize the terminal and watch "
    "which of these boxes re-wraps."
)

ASPECTS = (100, 150, 300)


def build(root, screen):
    area = _support.content_area(root, top=4)

    size = tkcurses.StringVar(root, "medium")
    count = tkcurses.StringVar(root, "")
    state = {"aspect": 0, "caption": 0}

    def report(*_):
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  size={size.get()!r}  count={count.get()!r}  "
            f"aspect={ASPECTS[state['aspect']]}",
        )
        screen.line(2, "  Tab moves focus.  Up/Down step.  arrows click too.")
        screen.line(3, "  F2 changes the message aspect   F3 moves the captions")
        screen.footer(" Escape quits ")
        screen.refresh()

    for variable in (size, count):
        variable.trace_add("write", report)

    # Side by side rather than stacked: stacked, the three of them plus the
    # three messages below wanted more rows than the screen had, and pack
    # squeezed the last spinbox out of existence - correct, and invisible.
    steppers = tkcurses.Frame(area)
    steppers.pack(side="top", fill="x", padx=1)

    readonly = tkcurses.LabelFrame(steppers, text="readonly list")
    readonly.pack(side="left", fill="both", expand=True, padx=1)
    tkcurses.Spinbox(
        readonly,
        values=("small", "medium", "large"),
        textvariable=size,
        width=12,
        state="readonly",
    ).pack(padx=1, pady=1)

    counter = tkcurses.LabelFrame(steppers, text="0 to 12, wraps")
    counter.pack(side="left", fill="both", expand=True, padx=1)
    tkcurses.Spinbox(
        counter, from_=0, to=12, wrap=True, textvariable=count, width=12
    ).pack(padx=1, pady=1)

    fractions = tkcurses.LabelFrame(steppers, text="0.00 by 0.25, typeable")
    fractions.pack(side="left", fill="both", expand=True, padx=1)
    tkcurses.Spinbox(
        fractions, from_=0, to=1, increment=0.25, format="%0.2f", width=12
    ).pack(padx=1, pady=1)

    row = tkcurses.Frame(area)
    row.pack(side="top", fill="both", expand=True)

    boxes = []
    messages = []
    for aspect in ASPECTS:
        box = tkcurses.LabelFrame(row, text=f"aspect {aspect}")
        box.pack(side="left", fill="both", expand=True, padx=1)
        message = tkcurses.Message(box, text=PARAGRAPH, aspect=aspect)
        message.pack(fill="both", expand=True)
        boxes.append(box)
        messages.append(message)

    def next_aspect(event):
        state["aspect"] = (state["aspect"] + 1) % len(ASPECTS)
        for box, message in zip(boxes, messages, strict=True):
            aspect = ASPECTS[state["aspect"]]
            message.configure(aspect=aspect)
            box.configure(text=f"aspect {aspect}")
        report()
        return "break"

    def next_caption(event):
        state["caption"] = (state["caption"] + 1) % 3
        anchor = ("nw", "n", "se")[state["caption"]]
        for box in (readonly, counter, fractions, *boxes):
            box.configure(labelanchor=anchor)
        report()
        return "break"

    root.bind_all("<Key-F2>", next_aspect)
    root.bind_all("<Key-F3>", next_caption)
    root.tk_focusNext().focus_set()
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
