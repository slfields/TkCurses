"""Grid: weights, sticky and spans.

A and B sit side by side, C and D beneath them, and E is under those in the
left column; p makes E span both columns.

What to do: press w to give every row and column a weight, n to take the
weights away, s to cycle sticky, p to toggle E's span.
What to look for: with no weight the cells stay at their natural size and
sticky appears to do nothing - that is correct, and the thing people report as
a bug. With weight, the cells grow and sticky then decides whether a frame
stretches to fill its cell or sits against one side of it.

The same catch applies to the span: pressing p with no sticky makes E *centre*
itself across the two columns rather than widen, because a span decides how
many cells a widget is given and sticky decides what it does with them. Press
s until sticky is ew to see it stretch.
"""

from __future__ import annotations

from uat import _support

TITLE = "11 - grid: weight, sticky and span"

STICKIES = ["", "w", "e", "ew", "ns", "nsew"]


def build(root, screen):
    area = _support.content_area(root)
    boxes = [
        _support.labelled_box(area, letter, width=8, height=3) for letter in "ABCDE"
    ]
    cells = [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0)]
    state = {"sticky": "", "weight": 0, "span": 1}

    def relayout():
        for box in boxes:
            box.grid_forget()
        for box, (row, column) in zip(boxes, cells, strict=True):
            span = state["span"] if box is boxes[4] else 1
            box.grid(row=row, column=column, columnspan=span, sticky=state["sticky"])
        for index in range(2):
            area.grid_columnconfigure(index, weight=state["weight"])
        for index in range(3):
            area.grid_rowconfigure(index, weight=state["weight"])
        root.update_layout()
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  weight={state['weight']}  sticky={state['sticky']!r}  "
            f"E spans {state['span']}   w weight, n none, s sticky, p span",
        )
        screen.footer(" Escape quits ")
        screen.refresh()

    def cycle_sticky(event):
        state["sticky"] = STICKIES[
            (STICKIES.index(state["sticky"]) + 1) % len(STICKIES)
        ]
        relayout()

    def toggle_span(event):
        state["span"] = 1 if state["span"] == 2 else 2
        relayout()

    def set_weight(weight):
        state["weight"] = weight
        relayout()

    root.bind("<Key-w>", lambda event: set_weight(1))
    root.bind("<Key-n>", lambda event: set_weight(0))
    root.bind("<Key-s>", cycle_sticky)
    root.bind("<Key-p>", toggle_span)
    relayout()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
