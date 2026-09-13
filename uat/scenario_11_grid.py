"""Grid: weights, sticky and spans.

What to do: press w to give every row and column a weight, n to take the
weights away, s to cycle sticky, p to toggle a two-column span on box C.
What to look for: with no weight the cells stay at their natural size and
sticky appears to do nothing - that is correct, and the thing people report as
a bug. With weight, the cells grow and sticky then decides whether a box
stretches to fill its cell or sits against one side of it.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "11 - grid: weight, sticky and span"

STICKIES = ["", "w", "e", "ew", "ns", "nsew"]


def build(root, screen):
    area = _support.content_area(root)
    boxes = []
    for name in "abcd":
        box = tkcurses.Widget(area, name=name)
        box._requested = tkcurses._core.geometry.Size(8, 2)
        boxes.append(box)

    state = {"sticky": "", "weight": 0, "span": 1}

    def relayout():
        for box in boxes:
            box.grid_forget()
        boxes[0].grid(row=0, column=0, sticky=state["sticky"])
        boxes[1].grid(row=0, column=1, sticky=state["sticky"])
        boxes[2].grid(row=1, column=0, columnspan=state["span"], sticky=state["sticky"])
        boxes[3].grid(row=2, column=1, sticky=state["sticky"])
        for index in range(2):
            area.grid_columnconfigure(index, weight=state["weight"])
        for index in range(3):
            area.grid_rowconfigure(index, weight=state["weight"])
        root.update_layout()
        screen.clear()
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  weight={state['weight']}  sticky={state['sticky']!r}  "
            f"span={state['span']}   w weight, n none, s sticky, p span",
        )
        screen.outline_on_redraw(boxes)
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
