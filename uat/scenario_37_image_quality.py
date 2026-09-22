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

"""One picture, rendered the one way the library renders pictures.

What to do: look at the picture. Press `n` for the next one, `t` for what
the terminal can do, and change TERM to see it at another colour depth.

**This scenario used to show four pictures at once** - every n-th pixel
against block averaging, crossed with flat colour against dithering - and
ask which looked best. That question is answered, so the choice is gone.
The answer matches what chafa does, which was checked against its source:

    average the block, do not drop pixels
    do the arithmetic in linear light, not in sRGB bytes
    match colours perceptually, in a uniform space
    do not dither

The four-way comparison was also never fair. All four panels shared one
table of 255 colour pairs and did not fit in it, so the two drawn last were
always the two starved of colour - and the two drawn last were the dithered
ones. See TkCurses-8cn.

**What this library must do that chafa does not.** chafa writes its own
escape sequences and can use as many foreground/background combinations as
it likes. Going through curses there are 255, because that is all a
character attribute can name - `color_pair(300)` wraps to 44 - and a
photograph wants thousands.

So the cells are written as escape sequences here too, in whichever form the
terminal takes. Press `t` and read `direct=`:

    truecolor   COLORTERM says so; exact colour, thousands of them
    palette     256 colours and no COLORTERM; the cube, hundreds
    off         8 or 16 colours, or TKCURSES_DISPLAY_DIRECT_IMAGES=0

**Both of the first two escape the ceiling**, which is easy to miss: a
256-colour terminal has no pair limit either once the sequences are written
by hand. Only at `off` is the picture cut down to fit the free pairs, by
`PhotoImage.fit_pairs()`, and only there does `f` do anything.

What to look for: docs/UAT_IMAGES.md, "UAT: Image rendering quality",
checks 37.0 to 37.4.

Keys: `n` next picture, `t` what the terminal can do, `f` fitted or raw
(only when `direct=off`), Escape quits.
"""

from __future__ import annotations

import pathlib

import tkcurses
from tkcurses._core.colors import ColorDepth
from tkcurses._core.images import ROWS_PER_CELL
from uat import _support

TITLE = "37 - one picture, rendered the one way"

#: Where the perl-Tk demos put theirs. Used when they are installed, and
#: stood in for when they are not, so this runs anywhere.
DEMOS = pathlib.Path("/usr/share/doc/perl-Tk/demos/images")

#: A picture wants room before anything about its colour can be judged.
WANTED = (52, 16)


def built_in(root, which):
    """A picture made here, for a machine with no perl-Tk installed."""
    picture = tkcurses.PhotoImage(master=root, width=192, height=120)
    if which == "ramp":
        for x in range(192):
            level = x * 255 // 191
            picture.put(
                f"#{level:02x}{level // 2:02x}{255 - level:02x}",
                to=(x, 0, x + 1, 120),
            )
    else:
        for y in range(120):
            for x in range(0, 192, 4):
                warm = (x * 4 + y) % 256
                picture.put(
                    f"#{warm:02x}{(y * 2) % 256:02x}40", to=(x, y, x + 2, y + 1)
                )
    return picture


def build(root, screen):
    state = {"which": 0, "held": [], "fitted": True}

    screen.line(0, f" {TITLE} ")
    screen.footer(" n next   t terminal   f fitted/raw   Escape quits ")

    area = _support.content_area(root, top=4, bottom=2)
    root.update_layout()
    shown = tkcurses.Label(area, name="picture", anchor="nw")
    shown.place(x=0, y=0, relwidth=1.0, relheight=1.0)

    names = [
        str(DEMOS / n) for n in ("mickey.gif", "earth.gif") if (DEMOS / n).is_file()
    ]
    state["sources"] = names or ["ramp", "stripes"]

    def load():
        source = state["sources"][state["which"]]
        if source in ("ramp", "stripes"):
            picture = built_in(root, source)
        else:
            picture = tkcurses.PhotoImage(master=root, file=source)

        wide = max(1, area.winfo_width())
        tall = max(1, area.winfo_height())
        # Resampled to the space on offer, not to whatever a whole-number
        # factor gives. reduce(4) on a 320-wide picture in a 100-cell panel
        # delivers 80 cells and throws away a fifth of the width.
        across = min(wide, picture.width())
        down = min(tall * ROWS_PER_CELL, picture.height())
        # Keep the picture's proportions inside the space.
        scale = min(across / picture.width(), down / picture.height())
        small = picture.resize(
            max(1, round(picture.width() * scale)),
            max(1, round(picture.height() * scale)),
        )
        raw_pairs = small.pairs_needed()

        manager = getattr(root.tk, "colors", None)
        painter = getattr(root.tk, "painter", None)
        # When the cells are written past curses there is no pair table to
        # run out of, so the palette is not cut down at all. Fitting only
        # applies where curses is doing the painting.
        unlimited = painter is not None and painter.enabled
        state["form"] = painter.form if painter is not None else "off"
        # Leave some of the table for the text around the picture, which is
        # drawn from the same table. Proportional, not a fixed 24: an
        # eight-colour terminal has 63 pairs in total, so 24 of them is a
        # third of everything reserved for two lines of text.
        capacity = getattr(manager, "capacity", 255)
        budget = max(16, capacity - max(8, capacity // 8))
        drawn = small if unlimited or not state["fitted"] else small.fit_pairs(budget)
        state["unlimited"] = unlimited

        state["held"] = [picture, small, drawn]
        shown.configure(image=drawn)
        root.update_layout()

        colours = len({c for row in drawn.rows() for c in row if c})
        screen.line(
            1,
            f"  {pathlib.Path(source).name}"
            f"   {picture.width()}x{picture.height()} pixels"
            f"   resampled to {drawn.width()}x{drawn.cell_height()} cells"
            f"   {colours} colours",
        )
        screen.line(
            2,
            f"  pairs wanted: {drawn.pairs_needed()}"
            + (
                f"   written past curses as {state['form']}, so the 255-pair"
                " ceiling does not apply"
                if unlimited
                else f" of {budget} budget"
                f"   (unfitted it would want {raw_pairs})"
                f"   {'FITTED' if state['fitted'] else 'RAW - press f'}"
            ),
        )
        roomy = drawn.width() >= WANTED[0] and drawn.cell_height() >= WANTED[1]
        screen.line(
            3,
            ""
            if roomy
            else f"  only {drawn.width()}x{drawn.cell_height()} cells;"
            f" {WANTED[0]}x{WANTED[1]} is wanted to judge colour",
        )
        screen.refresh()

    def next_picture(event=None):
        del event
        state["which"] = (state["which"] + 1) % len(state["sources"])
        load()
        return "break"

    def toggle_fit(event=None):
        del event
        state["fitted"] = not state["fitted"]
        load()
        return "break"

    def explain(event=None):
        del event
        manager = getattr(root.tk, "colors", None)
        depth = getattr(manager, "depth", ColorDepth.BASIC)
        screen.line(
            3,
            f"  depth={depth.name} ({int(depth)} colours)"
            f"  pairs allocated={getattr(manager, 'allocated', 0)}"
            f"/{getattr(manager, 'capacity', 0)}"
            f"  exhausted={getattr(manager, 'exhausted', False)}"
            f"  direct={state.get('form', 'off')}",
        )
        screen.refresh()
        return "break"

    root.bind("<Key-n>", next_picture)
    root.bind("<Key-t>", explain)
    root.bind("<Key-f>", toggle_fit)

    root.update_layout()
    load()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
