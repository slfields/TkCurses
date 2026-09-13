"""Canvas: drawing on half-cells, where a circle is actually round.

What to do: click the shapes - each one reports itself and changes colour.
Press F2 to move the ring, F3 to hide and show the box, F4 to put the ring
behind or in front of the block. Resize the terminal so shapes fall outside
the view and come back.
What to look for: the ring is a circle, not a tall ellipse. That is the whole
reason a canvas cell is split in half: one half-cell is one cell wide and half
a cell tall, which on a normal terminal is very nearly square. The two-colour
strip is one row of cells, each holding two different colours at once - the
thing a denser character set could not do. Text sits on whole cells, so a
label snaps to a row; a shape drawn after a label covers it, and one drawn
before it does not.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "24 - canvas: half-cells, colour and items"


def build(root, screen):
    area = _support.content_area(root, top=4)
    state = {"hidden": False, "raised": False, "last": "-"}

    canvas = tkcurses.Canvas(area, width=60, height=16, relief="solid")
    canvas.pack(fill="both", expand=True, padx=1)

    # 22 pixels across and 22 down: 22 cells wide, 11 cells tall, and round.
    canvas.create_oval(1, 1, 23, 23, outline="cyan", tags=("ring", "shape"))
    canvas.create_rectangle(28, 2, 48, 22, outline="green", tags=("box", "shape"))
    canvas.create_line(28, 2, 48, 22, fill="green", tags=("box", "shape"))
    canvas.create_line(48, 2, 28, 22, fill="green", tags=("box", "shape"))
    canvas.create_polygon(
        52, 4, 68, 12, 52, 20, fill="magenta", outline="white", tags=("block", "shape")
    )
    canvas.create_text(12, 12, text="round", fill="black", tags="label")

    # One row of cells, each with a different colour in its two halves.
    for column in range(8):
        canvas.create_line(
            2 + column * 2, 26, 3 + column * 2, 26, fill="red", tags="strip"
        )
        canvas.create_line(
            2 + column * 2, 27, 3 + column * 2, 27, fill="blue", tags="strip"
        )
    canvas.create_text(20, 26, text="two colours per cell", anchor="w", tags="strip")

    def report(*_):
        box = canvas.bbox("all")
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  items={len(canvas.find_all())}  bbox={box}  "
            f"box {'hidden' if state['hidden'] else 'shown'}",
        )
        screen.line(2, f"  last clicked: {state['last']}")
        screen.line(3, "  F2 move the ring   F3 hide the box   F4 raise the ring")
        screen.footer(" Escape quits ")
        screen.refresh()

    def clicked(event):
        found = canvas.find_withtag("current")
        if found:
            tags = canvas.gettags(found[0])
            state["last"] = f"{canvas.type(found[0])} {tags}"
            canvas.itemconfigure(found[0], outline="yellow")
        report()

    canvas.tag_bind("shape", "<Button-1>", clicked)

    def move_ring(event):
        canvas.move("ring", 4, 0)
        report()
        return "break"

    def toggle_box(event):
        state["hidden"] = not state["hidden"]
        canvas.itemconfigure("box", state="hidden" if state["hidden"] else "normal")
        report()
        return "break"

    def raise_ring(event):
        state["raised"] = not state["raised"]
        if state["raised"]:
            canvas.tag_raise("ring")
        else:
            canvas.tag_lower("ring")
        report()
        return "break"

    root.bind_all("<Key-F2>", move_ring)
    root.bind_all("<Key-F3>", toggle_box)
    root.bind_all("<Key-F4>", raise_ring)
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
