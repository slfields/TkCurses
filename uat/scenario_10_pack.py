"""Pack: sides, fill and expand.

What to do: press 1 to 4 for the four sides, f to cycle fill, e to toggle
expand, r to reset.
What to look for: the frames stack against the side you chose in the order A,
B, C; fill stretches a frame across its slice but never past it; expand is
what makes them share the leftover space, and without it they keep their own
size and leave a gap.
"""

from __future__ import annotations

from uat import _support

TITLE = "10 - pack: sides, fill and expand"

FILLS = ["none", "x", "y", "both"]


def build(root, screen):
    area = _support.content_area(root)
    boxes = [
        _support.labelled_box(area, letter, width=12, height=3) for letter in "ABC"
    ]
    state = {"side": "top", "fill": "none", "expand": False}

    def relayout():
        for box in boxes:
            box.pack_forget()
        for box in boxes:
            box.pack(side=state["side"], fill=state["fill"], expand=state["expand"])
        root.update_layout()
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  side={state['side']}  fill={state['fill']}  "
            f"expand={state['expand']}   1-4 side, f fill, e expand, r reset",
        )
        screen.footer(" Escape quits ")
        screen.refresh()

    def set_side(side):
        state["side"] = side
        relayout()

    def cycle_fill(event):
        state["fill"] = FILLS[(FILLS.index(state["fill"]) + 1) % len(FILLS)]
        relayout()

    def toggle_expand(event):
        state["expand"] = not state["expand"]
        relayout()

    def reset(event):
        state.update(side="top", fill="none", expand=False)
        relayout()

    root.bind("<Key-1>", lambda event: set_side("top"))
    root.bind("<Key-2>", lambda event: set_side("bottom"))
    root.bind("<Key-3>", lambda event: set_side("left"))
    root.bind("<Key-4>", lambda event: set_side("right"))
    root.bind("<Key-f>", cycle_fill)
    root.bind("<Key-e>", toggle_expand)
    root.bind("<Key-r>", reset)
    relayout()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
