"""Place: absolute and relative positions.

What to do: press a for absolute coordinates, r for relative, m for a mixture
of the two, c to cycle the anchor.
What to look for: a relatively placed box stays in proportion when you resize
the terminal while an absolutely placed one does not; the mixture is half the
width less four cells, so it keeps a two-cell margin either side at any size;
and the anchor decides which corner of the box lands on the position, so the
box moves around the point rather than the point moving.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "12 - place: absolute, relative, anchor"

ANCHORS = ["nw", "n", "ne", "e", "se", "s", "sw", "w", "center"]


def build(root, screen):
    area = _support.content_area(root)
    box = tkcurses.Widget(area, name="box")
    box._requested = tkcurses._core.geometry.Size(14, 4)
    state = {"mode": "absolute", "anchor": "nw"}

    def relayout():
        box.place_forget()
        if state["mode"] == "absolute":
            box.place(x=4, y=3, anchor=state["anchor"])
        elif state["mode"] == "relative":
            box.place(relx=0.5, rely=0.5, anchor=state["anchor"])
        else:
            box.place(
                relx=0.0,
                x=2,
                relwidth=1.0,
                width=-4,
                y=4,
                height=5,
                anchor=state["anchor"],
            )
        root.update_layout()
        screen.clear()
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  mode={state['mode']}  anchor={state['anchor']}   "
            f"a absolute, r relative, m mixed, c anchor",
        )
        screen.line(
            2,
            f"  box is at {box.winfo_geometry()} in {root.winfo_width()}x"
            f"{root.winfo_height()} - resize the terminal and watch",
        )
        screen.outline_on_redraw([box])
        screen.footer(" Escape quits ")
        screen.refresh()

    def set_mode(mode):
        state["mode"] = mode
        relayout()

    def cycle_anchor(event):
        state["anchor"] = ANCHORS[(ANCHORS.index(state["anchor"]) + 1) % len(ANCHORS)]
        relayout()

    root.bind("<Key-a>", lambda event: set_mode("absolute"))
    root.bind("<Key-r>", lambda event: set_mode("relative"))
    root.bind("<Key-m>", lambda event: set_mode("mixed"))
    root.bind("<Key-c>", cycle_anchor)
    root.bind("<Configure>", lambda event: relayout())
    relayout()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
