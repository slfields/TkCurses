"""A layout under a terminal resize, including one with no room left.

Two frames A and B share the screen. Pressing d puts two more *inside* B, side
by side - B stays where it is and keeps its border, with 1 and 2 within it.
They are numbered rather than lettered because they belong to B; a C and D
would suggest two more siblings.

What to do: resize the terminal, especially smaller than the layout wants.
Press d to nest the inner pair.
What to look for: the frames follow the new size immediately; nothing is drawn
outside the screen or left behind from the previous size; the nested pair
resizes along with B and stays inside it; and when the terminal is too small
the frames shrink or vanish rather than overlapping or wrapping. Make it very
small - a few cells - and check it neither crashes nor draws nonsense.
"""

from __future__ import annotations

from uat import _support

TITLE = "13 - layout under resize"


def build(root, screen):
    area = _support.content_area(root)
    boxes = []
    for letter in "AB":
        box = _support.labelled_box(area, letter, width=10, height=3)
        box.pack(side="top", fill="both", expand=True, padx=1, pady=1)
        boxes.append(box)
    nested = {"on": False}

    def relayout(event=None):
        root.update_layout()
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  terminal {root.winfo_width()}x{root.winfo_height()}   "
            f"d nests a pair inside B, resize the terminal",
        )
        screen.footer(" Escape quits ")
        screen.refresh()

    def nest(event):
        if nested["on"]:
            return
        nested["on"] = True
        for index, side in enumerate(("left", "right")):
            inner = _support.labelled_box(boxes[1], "12"[index], width=4, height=1)
            inner.pack(side=side, fill="both", expand=True, padx=1)
        relayout()

    root.bind("<Configure>", relayout)
    root.bind("<Key-d>", nest)
    relayout()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
