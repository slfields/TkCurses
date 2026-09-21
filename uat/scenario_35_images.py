# TkCurses - a tkinter-compatible API layer that renders to curses
# Copyright (C) 2026  Scott L. Fields
#
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Images: a pixel is half a character cell.

The first thing to look at is the circle. It is round, and it is round for
the same reason a Canvas circle is: a pixel here is one cell wide and *half*
a cell tall, so the plane is very nearly square. An image 16 pixels across
is 16 cells wide and 8 rows tall, and `▀`, `▄` and `█` are what reaches the
screen - the same three glyphs, through the same compose(), that a Canvas
draws with. There is one pixel in this library and this is it.

Then press `c` and watch the same image sit six different ways
against the same word. That is `compound`, and the first press is the one
worth pausing on - the default is `none`, and `none` means the image wins
and the text is not drawn at all. A person who sets an image on a Label and
wonders where their caption went has met this.

Then `p` paints new art into the image under a live widget, `s` resizes it
and watches four widgets follow, `z` and `x` zoom and subsample, `h` punches
a hole through the middle, and `d` drops the last reference to the image.

What to look for: nothing is ever asked of a widget. Pressing `p` writes to
the *image*, and every widget showing it repaints - that is the same
notification Tk gives, measured at 4x2 to 20x10 moving a Label's request
from 6x4 to 22x12. `h` shows a hole is not a space: the label's own
background comes through it, not a blank the image painted.

`d` is the trap. The image goes, the widgets stay exactly the size they
were, and they draw nothing - which is why every tkinter tutorial tells you
to keep a reference. `r` builds it again.

What to look for: docs/UAT_IMAGES.md, "UAT: Images", checks 35.0 to 35.7.

Keys: `c` next compound, `p` repaint the art, `s` resize it, `z` zoom,
`x` subsample, `h` hole, `d` drop the image, `r` rebuild, Escape quits.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "35 - images: a pixel is half a character cell"

COMPOUNDS = ("none", "left", "right", "top", "bottom", "center")

#: A house, 8 pixels across and 6 down - so 8 cells wide and 3 rows tall.
#: Characters stand for colours, which is XPM's idea and the only way to
#: write an image legibly in a source file. A character with no entry in the
#: palette is a hole, so the spaces need no rule of their own.
HOUSE = [
    "  ##  ",
    " #### ",
    "######",
    "#.oo.#",
]
PALETTE = {"#": "red", ".": "white", "o": "cyan"}

#: How much bigger `s` makes it. Whole numbers only: scaling character art
#: by anything else means inventing pixels that were never drawn.
GROWN = 2

#: An XBM arrow, pointing right. Real XBM, because that is what BitmapImage
#: reads - one bit per pixel is exactly what this plane holds. The bits are
#: least significant first, which is why the row that looks like it should
#: read 0xfe is 0x7f: it was 0x08,0x0c,0xfe,0x0c,0x08 and drew an arrow
#: pointing the other way.
ARROW_XBM = """#define arrow_width 8
#define arrow_height 5
static char arrow_bits[] = {
0x10,0x30,0x7f,0x30,0x10};
"""


def build(root, screen):
    state = {"compound": 0, "photo": None, "zoomed": None, "arrow": None, "ball": None}

    screen.line(0, f" {TITLE} ")
    screen.footer(
        " c compound  p paint  s resize  z zoom  x subsample"
        "  h hole  d drop  r rebuild  Escape quits "
    )

    area = _support.content_area(root, top=3, bottom=2)

    def paint_house(picture, scale):
        """Draw the house into ``picture`` at ``scale``, resizing it to fit.

        Scaled rather than replaced with a block of colour: the claim being
        demonstrated is that a widget follows its image's *size*, and that
        is far easier to see when the thing getting bigger is still
        recognisably the same house.
        """
        wide, tall = len(HOUSE[0]) * scale, len(HOUSE) * scale
        picture.configure(width=wide, height=tall)
        picture.blank()
        for row, line in enumerate(HOUSE):
            for column, character in enumerate(line):
                colour = PALETTE.get(character)
                if colour is None:
                    continue
                picture.put(
                    colour,
                    to=(
                        column * scale,
                        row * scale,
                        (column + 1) * scale,
                        (row + 1) * scale,
                    ),
                )

    def make_photo():
        """The shared image. Every widget below names this one."""
        picture = tkcurses.PhotoImage(master=root, name="house")
        paint_house(picture, 1)
        return picture

    state["photo"] = make_photo()

    # Two columns, and each column is GRIDDED rather than placed. That is
    # deliberate and it is what UAT 35.4 is really asking about: place() is
    # absolute, so a placed widget does not move when a sibling grows - it
    # gets drawn over. grid and pack reflow, so growing the image pushes
    # everything below it down, which is the requested size propagating
    # through a geometry manager where a person can see it happen.
    # Widths are for the GROWN house, not the starting one. Sized for what
    # is on screen when the scenario opens, every column clipped the moment
    # `s` doubled the image - a button losing its right-hand border, a
    # checkbutton losing its label - which reads as a drawing bug and is
    # really a column two cells too narrow.
    left = tkcurses.Frame(area, name="left")
    left.place(x=1, y=0, relheight=1.0, width=27)
    right = tkcurses.Frame(area, name="right")
    right.place(x=29, y=0, relheight=1.0, width=29)
    # The circle gets a column of its own because it is the one thing here
    # that never changes size: sharing a column with a doubling house would
    # push it off the bottom of the screen for no reason.
    far = tkcurses.Frame(area, name="far")
    far.place(x=59, y=0, relheight=1.0, relwidth=1.0, width=-59)

    def labelled(parent, text, row):
        """A caption in column 0 of ``parent``'s grid."""
        tkcurses.Label(parent, text=text, anchor="nw").grid(
            row=row, column=0, sticky="nw", padx=1
        )

    # Four widgets over one image, so that a change to the image is visibly
    # a change to all of them rather than to the one that was touched.
    labelled(left, "Label:", 0)
    shown = tkcurses.Label(left, name="shown", image="house", anchor="nw")
    shown.grid(row=0, column=1, sticky="nw")

    labelled(left, "Caption:", 1)
    captioned = tkcurses.Label(
        left, name="captioned", text="Home", image="house", anchor="nw"
    )
    captioned.grid(row=1, column=1, sticky="nw", pady=1)

    labelled(left, "Button:", 2)
    pressed = {"count": 0}

    def press():
        pressed["count"] += 1
        report()
        screen.refresh()

    # Starts at none like everything else that gets cycled, or the status
    # line says compound=none while the button is plainly showing its text.
    button = tkcurses.Button(left, name="go", text="Open", image="house", command=press)
    button.grid(row=2, column=1, sticky="nw", pady=1)

    labelled(right, "Check:", 0)
    checked = tkcurses.BooleanVar(master=root, value=True)
    # Left at compound=left on purpose and never cycled: something has to
    # stay still to compare the others against.
    check = tkcurses.Checkbutton(
        right,
        name="tick",
        text="on",
        image="house",
        compound="left",
        variable=checked,
    )
    check.grid(row=0, column=1, sticky="nw")

    # A bitmap, which is a different class and the same idea. It never
    # changes size, so it is the fixed mark the reflowing rows move against.
    labelled(right, "Bitmap:", 1)
    # Kept in state on purpose. An image nothing references is collected and
    # the widget showing it draws nothing - so a local here would make the
    # arrow vanish the moment build() returned, which is the same trap `d`
    # springs deliberately further down.
    state["arrow"] = tkcurses.BitmapImage(
        master=root, name="arrow", data=ARROW_XBM, foreground="cyan"
    )
    tkcurses.Label(right, name="arrowed", image="arrow", anchor="nw").grid(
        row=1, column=1, sticky="nw", pady=1
    )

    # zoom() and subsample() make new images rather than changing this one,
    # so they get a widget of their own to land in.
    labelled(right, "z / x:", 2)
    scaled = tkcurses.Label(right, name="scaled", image="house", anchor="nw")
    scaled.grid(row=2, column=1, sticky="nw", pady=1)

    # The circle. It exists to be looked at rather than operated: if the
    # plane were a grid of whole cells this would be an ellipse half as tall
    # as it is wide, and the choice of half-cells would be invisible.
    labelled(far, "round:", 0)
    # 12 pixels across is 12 cells wide and 6 rows tall - which is what fits
    # above the footer, and the reason to say the two numbers out loud.
    ball = tkcurses.PhotoImage(master=root, name="ball", width=12, height=12)
    for y in range(12):
        for x in range(12):
            if (x - 5.5) ** 2 + (y - 5.5) ** 2 <= 32:
                ball.put("cyan" if x < 6 else "magenta", to=(x, y))
    state["ball"] = ball
    tkcurses.Label(far, name="ball", image="ball", anchor="nw").grid(
        row=1, column=0, sticky="nw"
    )

    def photo():
        """The image, if it still exists."""
        return state["photo"]

    def report():
        picture = photo()
        if picture is None:
            size = "gone"
        else:
            size = (
                f"{picture.width()}x{picture.height()}px"
                f" = {picture.width()}x{picture.cell_height()} cells"
            )
        screen.line(
            1,
            f"  compound={COMPOUNDS[state['compound']]}"
            f"   image={size}"
            f"   Label asks {shown.winfo_reqwidth()}x{shown.winfo_reqheight()}"
            f"   caption asks {captioned.winfo_reqwidth()}"
            f"x{captioned.winfo_reqheight()}",
        )
        screen.line(
            2,
            f"  button pressed {pressed['count']} times"
            f"   checked={checked.get()}"
            f"   registry={sorted(root.tk.images)}",
        )

    def next_compound(event=None):
        del event
        state["compound"] = (state["compound"] + 1) % len(COMPOUNDS)
        name = COMPOUNDS[state["compound"]]
        for widget in (captioned, button):
            widget.configure(compound=name)
        root.update_layout()
        report()
        screen.refresh()
        return "break"

    def paint(event=None):
        """Write into the image. Nothing is asked of any widget."""
        del event
        picture = photo()
        if picture is None:
            return "break"
        picture.put("magenta", to=(0, 0, picture.width(), picture.height() // 2))
        # Nothing below this line touches a widget. That is the whole point:
        # the write went to the image and four widgets repainted themselves.
        root.update_layout()
        report()
        screen.refresh()
        return "break"

    def resize(event=None):
        """Grow the image, and watch the rows below it move down.

        The house is redrawn at the new scale rather than replaced with a
        block of colour. Filling it in did prove the size had changed, and
        it also threw away the only evidence that it was still the same
        image - which is the thing being demonstrated.
        """
        del event
        picture = photo()
        if picture is None:
            return "break"
        paint_house(picture, 1 if picture.width() > len(HOUSE[0]) else GROWN)
        root.update_layout()
        report()
        screen.refresh()
        return "break"

    def rescale(factor):
        def handler(event=None):
            del event
            picture = photo()
            if picture is None:
                return "break"
            # From a fresh house at its original scale, not from the shared
            # image: zooming an already-doubled house is 24 cells wide and
            # simply runs out of terminal, which teaches nothing about zoom.
            base = tkcurses.PhotoImage(master=root)
            paint_house(base, 1)
            made = base.zoom(2) if factor == "zoom" else base.subsample(2)
            # Held in state: an image nothing references is collected, and a
            # widget showing a collected image draws nothing. That is the
            # whole point of `d` below, and it would happen here by accident.
            state["zoomed"] = made
            scaled.configure(image=made)
            root.update_layout()
            report()
            screen.refresh()
            return "break"

        return handler

    def hole(event=None):
        """A hole is not a space: the widget's background comes through."""
        del event
        picture = photo()
        if picture is None:
            return "break"
        for y in range(picture.height()):
            for x in range(picture.width()):
                if x == y:
                    picture.transparency_set(x, y, True)
        root.update_layout()
        report()
        screen.refresh()
        return "break"

    def drop(event=None):
        """Let go of the image and watch the trap spring."""
        del event
        state["photo"] = None
        state["zoomed"] = None
        import gc

        gc.collect()
        root.update_layout()
        report()
        screen.refresh()
        return "break"

    def rebuild(event=None):
        del event
        if photo() is not None:
            return "break"
        state["photo"] = make_photo()
        # Every widget that was showing it, the checkbutton included - it
        # was built inline once and so was the one left blank by `r`.
        for widget in (shown, captioned, button, check, scaled):
            widget.configure(image="house")
        root.update_layout()
        report()
        screen.refresh()
        return "break"

    root.bind("<Key-c>", next_compound)
    root.bind("<Key-p>", paint)
    root.bind("<Key-s>", resize)
    root.bind("<Key-z>", rescale("zoom"))
    root.bind("<Key-x>", rescale("subsample"))
    root.bind("<Key-h>", hole)
    root.bind("<Key-d>", drop)
    root.bind("<Key-r>", rebuild)

    root.update_layout()
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
