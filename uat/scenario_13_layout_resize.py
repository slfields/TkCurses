"""A layout under a terminal resize, including one with no room left.

Two boxes A and B share the screen. Pressing d puts two more *inside* B,
side by side - B stays where it is and keeps its outline, with 1 and 2 within
it. They are numbered rather than lettered because they belong to B; a fourth
and fifth letter would suggest three more siblings.

What to do: resize the terminal, especially smaller than the layout wants.
Press d to nest the inner pair.
What to look for: the boxes follow the new size immediately; nothing is drawn
outside the screen or left behind from the previous size; the nested pair
resizes along with B and stays inside it; and when the terminal is too small
the boxes shrink or vanish rather than overlapping or wrapping. Make it very
small - a few cells - and check it neither crashes nor draws nonsense.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "13 - layout under resize"


def build(root, screen):
    area = _support.content_area(root)
    boxes = []
    for name in "ab":
        box = tkcurses.Widget(area, name=name)
        box._requested = tkcurses._core.geometry.Size(10, 3)
        box.pack(side="top", fill="both", expand=True, padx=1, pady=1)
        boxes.append(box)
    inner_boxes = []
    nested = {"on": False}

    def relayout(event=None):
        root.update_layout()
        screen.clear()
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  terminal {root.winfo_width()}x{root.winfo_height()}   "
            f"d nests a layout, resize the terminal",
        )
        screen.outline_on_redraw(boxes, "AB")
        # Labelled 1 and 2 rather than D and E: they are inside B, not three
        # more siblings, and letters in sequence say the opposite.
        screen.outline_on_redraw(inner_boxes, "12")
        screen.footer(" Escape quits ")
        screen.refresh()

    def nest(event):
        if nested["on"]:
            return
        nested["on"] = True
        for index, side in enumerate(("left", "right")):
            inner = tkcurses.Widget(boxes[1], name=f"inner{index}")
            inner._requested = tkcurses._core.geometry.Size(4, 1)
            # Padded so B's own outline stays visible around them. Filling B
            # edge to edge would cover it, and B would look replaced rather
            # than occupied.
            inner.pack(side=side, fill="both", expand=True, padx=1, pady=1)
            inner_boxes.append(inner)
        relayout()

    root.bind("<Configure>", relayout)
    root.bind("<Key-d>", nest)
    relayout()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
