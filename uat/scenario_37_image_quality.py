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

"""The same picture, four ways: shrinking and colour, and what each costs.

What to do: look at the four panels. They are one image, prepared four
different ways, side by side - because the difference between them is a
thing to *see*, and a scenario that showed them one at a time would be
asking you to remember a colour instead.

    dropped + flat      every n-th pixel kept, nearest colour per pixel
    averaged + flat     the block averaged, nearest colour per pixel
    dropped + dithered
    averaged + dithered

The first is what this library did until now. **Which of the other three
is best is a real question, and the answer is not the one I expected.**

What to look for. **Shrinking**: `dropped` keeps whichever pixels landed on
the grid and discards the rest, so thin features come and go and edges
crawl; `averaged` keeps something of every pixel. Measured against a Lanczos
reference, averaging is 38% to 93% closer at every colour depth.

**Colour**: dithering trades colour accuracy for spatial noise, and that
only pays when the eye merges neighbouring pixels back together. It does
that on a monitor. It does NOT here, where a pixel is half a character cell
and you see the dither pattern itself. Measured on mickey at 256 colours,
against an ideal reduction:

    per-pixel          flat 13.48   dithered 18.50
    after a 3x3 blur   flat 10.03   dithered  3.71

Both are true; they assume different viewers, and the first is the one a
terminal gives you. **Judge it with your eyes, not with either number.**

Press `t` and the colour depth is reported. At truecolor the two dithered
panels are IDENTICAL to the flat ones, and that is correct: every colour is
available, no pixel accumulates error, and there is nothing to spread.

This one wants room. At 80x24 the pictures come out 26x8 cells, where the
differences are all present and none of them are visible; it says so when
that happens. **A terminal of 120x44 or larger** shows them at 53x17.

What to look for: docs/UAT_IMAGES.md, "UAT: Image rendering quality",
checks 37.1 to 37.4.

Keys: `n` next picture, `t` what the terminal can do, Escape quits.
"""

from __future__ import annotations

import pathlib

import tkcurses
from tkcurses._core.colors import ColorDepth
from tkcurses._core.images import ROWS_PER_CELL
from uat import _support

TITLE = "37 - the same picture, four ways"

#: Cells between the two columns, and the row each caption takes.
GAP = 2
CAPTION = 1

#: What a picture wants to be for the four to be worth comparing. At 26x8 -
#: which is what an 80x24 terminal gives - the differences are all there and
#: too small to judge, which defeats the point of showing four at once.
WANTED = (52, 16)

#: The smallest terminal that actually delivers WANTED, measured rather than
#: derived: the reduce factor is a whole number, so a panel can be big enough
#: while the picture in it still steps down to the next factor. 110x40 gives
#: a 54x16 panel holding a 45x14 picture; 120x44 gives 53x17.
ROOMY = (120, 44)

#: Where the perl-Tk demos put theirs. Used when they are installed, and
#: stood in for when they are not, so this runs anywhere.
DEMOS = pathlib.Path("/usr/share/doc/perl-Tk/demos/images")

PANELS = (
    ("dropped, flat", False, False),
    ("averaged, flat", True, False),
    ("dropped, dithered", False, True),
    ("averaged, dithered", True, True),
)


def built_in(root, which):
    """A picture made here, for a machine with no perl-Tk installed.

    Two of them, and they fail in different ways: a smooth ramp bands under
    per-pixel matching, and fine stripes disappear under dropped pixels.
    """
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


def unavailable(colours, depth):
    """How many of these the terminal would have to approximate."""
    from tkcurses._core.colors import _resolve_rgb, rgb_of_number

    count = 0
    for spec in colours:
        rgb = tuple(int(spec[i : i + 2], 16) for i in (1, 3, 5))
        if rgb_of_number(_resolve_rgb(rgb, depth).color, depth) != rgb:
            count += 1
    return count


def build(root, screen):
    state = {"which": 0, "sources": [], "held": []}

    screen.line(0, f" {TITLE} ")
    screen.footer(" n next picture   t what the terminal can do   Escape quits ")

    area = _support.content_area(root, top=4, bottom=2)

    names = []
    for name in ("mickey.gif", "earth.gif"):
        if (DEMOS / name).is_file():
            names.append(str(DEMOS / name))
    state["sources"] = names or ["ramp", "stripes"]

    # Two by two, sized to the terminal rather than to a number chosen
    # while writing this. The first version hard-coded 38x8 and the pictures
    # came out at 26x8 cells - too small to judge, which is the whole job
    # of a scenario whose point is comparison. A panel wants about 52x16.
    root.update_layout()
    across = max(1, (area.winfo_width() - GAP) // 2)
    down = max(1, (area.winfo_height() - 2 * CAPTION) // 2)
    state["panel"] = (across, down)

    labels = {}
    captions = {}
    for index, (caption, _, _) in enumerate(PANELS):
        column, row = index % 2, index // 2
        left = column * (across + GAP)
        top = row * (down + CAPTION)
        captions[index] = tkcurses.Label(area, text=caption, anchor="w")
        captions[index].place(x=left, y=top, width=across)
        shown = tkcurses.Label(area, name=f"panel{index}", anchor="nw")
        shown.place(x=left, y=top + CAPTION, width=across, height=down)
        labels[index] = shown

    def report(picture, depth):
        source = state["sources"][state["which"]]
        screen.line(
            1,
            f"  {pathlib.Path(source).name}"
            f"   {picture.width()}x{picture.height()} pixels"
            f"   shown at {state.get('cells', '?')}"
            f"   colours in the source: {len({c for r in picture.rows() for c in r if c})}",
        )
        drawn = state.get("drawn", (0, 0))
        roomy = drawn[0] >= WANTED[0] and drawn[1] >= WANTED[1]
        screen.line(
            3,
            ""
            if roomy
            else f"  the pictures are {drawn[0]}x{drawn[1]} cells."
            f" {WANTED[0]}x{WANTED[1]} is wanted to judge them, and a terminal"
            f" of {ROOMY[0]}x{ROOMY[1]} gives that",
        )
        screen.line(
            2,
            f"  terminal depth: {depth.name} ({int(depth)} colours)"
            + (
                "   - every colour is available, so the dithered panels"
                " are identical and should be"
                if depth >= ColorDepth.DIRECT
                else "   - dithering has something to do here"
            ),
        )

    def load():
        source = state["sources"][state["which"]]
        if source in ("ramp", "stripes"):
            picture = built_in(root, source)
        else:
            picture = tkcurses.PhotoImage(master=root, file=source)

        # Fit to whatever a panel turned out to be. A cell is two pixels
        # tall, so the rows double on the way in.
        wide, tall = state["panel"]
        factor = 1
        while (
            picture.width() // factor > wide
            or picture.height() // factor > tall * ROWS_PER_CELL
        ):
            factor += 1

        manager = getattr(root.tk, "colors", None)
        depth = getattr(manager, "depth", ColorDepth.BASIC)

        # Held, or an image nothing references is collected and the label
        # draws nothing - the trap UAT 35 demonstrates on purpose.
        state["held"] = [picture]
        for index, (_, averaged, dithered) in enumerate(PANELS):
            small = picture.reduce(factor) if averaged else picture.subsample(factor)
            if dithered:
                small = small.dither(depth)
            state["held"].append(small)
            labels[index].configure(image=small)
            state["cells"] = f"{small.width()}x{small.cell_height()} cells"
            state["drawn"] = (small.width(), small.cell_height())
            # Two numbers, and the second is the one to check. Dithering
            # does not add colours - it snaps every pixel to one the
            # terminal actually has, which on an averaged image REDUCES the
            # count, from 261 to 45 on mickey. What it guarantees is that
            # nothing is left needing approximation, so the dithered panels
            # must read "0 unavailable" and the flat ones usually will not.
            used = {c for row in small.rows() for c in row if c}
            # Kept short deliberately: the panel is 38 cells and the first
            # wording ran to 41, so the word that mattered was clipped off
            # the end and the check could not be made at all.
            captions[index].configure(
                text=(
                    f"{PANELS[index][0]}  "
                    f"{unavailable(used, depth)}/{len(used)} unavailable"
                )
            )

        root.update_layout()
        report(picture, depth)
        screen.refresh()

    def next_picture(event=None):
        del event
        state["which"] = (state["which"] + 1) % len(state["sources"])
        load()
        return "break"

    def explain(event=None):
        del event
        manager = getattr(root.tk, "colors", None)
        depth = getattr(manager, "depth", ColorDepth.BASIC)
        screen.line(
            2,
            f"  depth={depth.name}  pairs allocated={getattr(manager, 'allocated', 0)}"
            f"  exhausted={getattr(manager, 'exhausted', False)}"
            f"  - a pair per (foreground, background), and only 255 can be named",
        )
        screen.refresh()
        return "break"

    root.bind("<Key-n>", next_picture)
    root.bind("<Key-t>", explain)

    root.update_layout()
    load()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
