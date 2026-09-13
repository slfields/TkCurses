"""Spinboxes, messages and captioned frames.

What to do: Tab between the spinboxes, step them with Up and Down and with
their arrows, and type into the two that allow it. Press F2 to change the
text and F3 to move the captions - function keys rather than letters,
because a focused entry consumes every printable key. Resize the terminal.
What to look for: every box in this scenario is a LabelFrame, so its caption
should sit on its border and never over its contents. The spinboxes' arrows
stay at the right-hand edge whatever is in them, and the readonly one refuses
typing while still stepping. The messages choose their own line length, and
the text always starts at the top - a paragraph too tall for its box loses
its end, never its beginning. The bordered rectangle inside each of the
three lower boxes is the message itself, given an edge it would not normally
have so that the block it asked for can be seen: at aspect 100 it should be
about as tall as it is wide, and at 300 three times as wide as tall. The
three aspects stay different from each other whatever F2 does.
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

#: Cycled by F2, so all three messages re-wrap while each keeps its own
#: aspect. Short enough and long enough to change the block's shape visibly.
TEXTS = (
    PARAGRAPH,
    "Two short lines, and no more than that.",
    PARAGRAPH + " " + PARAGRAPH,
)


def build(root, screen):
    area = _support.content_area(root, top=4)

    size = tkcurses.StringVar(root, "medium")
    count = tkcurses.StringVar(root, "")
    state = {"text": 0, "caption": 0}

    def report(*_):
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  size={size.get()!r}  count={count.get()!r}  "
            f"text {state['text'] + 1} of {len(TEXTS)}  "
            f"aspects {'  '.join(str(a) for a in ASPECTS)}",
        )
        screen.line(2, "  Tab moves focus.  Up/Down step.  arrows click too.")
        screen.line(
            3, "  F2 changes the text (all three re-wrap)   F3 moves the captions"
        )
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
        # The message is given a border it would not normally have, and is
        # packed to its own size rather than filling the box. Without both,
        # the only thing on screen with an edge is the LabelFrame - which is
        # a fixed third of the row whatever the aspect is - so the block's
        # shape, which is the whole of what `aspect` controls, cannot be
        # seen at all. The bordered rectangle here is the message itself.
        message = tkcurses.Message(box, text=TEXTS[0], aspect=aspect, relief="solid")
        message.pack(anchor="n", pady=1)
        boxes.append(box)
        messages.append(message)

    def next_text(event):
        """Re-wrap all three, leaving each on its own aspect.

        Cycling the *aspect* was the first version of this, and it set all
        three boxes to the same value - which made the three columns
        identical and threw away the comparison they exist for.
        """
        state["text"] = (state["text"] + 1) % len(TEXTS)
        for message in messages:
            message.configure(text=TEXTS[state["text"]])
        report()
        return "break"

    def next_caption(event):
        state["caption"] = (state["caption"] + 1) % 3
        anchor = ("nw", "n", "se")[state["caption"]]
        for box in (readonly, counter, fractions, *boxes):
            box.configure(labelanchor=anchor)
        report()
        return "break"

    root.bind_all("<Key-F2>", next_text)
    root.bind_all("<Key-F3>", next_caption)
    root.tk_focusNext().focus_set()
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
