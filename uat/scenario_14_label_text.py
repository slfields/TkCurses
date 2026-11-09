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

"""Label: wrapping, justification, anchoring and text that does not fit.

What to do: press w to cycle the wrap width, j to cycle justify, a to cycle
anchor, and resize the terminal to squeeze the fixed-width label at the
bottom.
What to look for: justify aligns the wrapped lines against each other, anchor
moves the whole block within the frame, and the two are visibly different
things - a one-line label would not show that, which is why the text here has
several. Text that cannot fit is cut at the edge and never spills onto a
neighbour, and a word longer than the wrap width is broken rather than allowed
to overflow.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "14 - label: wrapping, justify and anchor"

PROSE = "the quick brown fox jumps over the lazy dog"
LONG_WORD = "antidisestablishmentarianism"
WRAPS = [0, 24, 14, 8]
JUSTIFIES = ["left", "center", "right"]
ANCHORS = ["nw", "n", "ne", "w", "center", "e", "sw", "s", "se"]


def build(root, screen):
    area = _support.content_area(root)
    state = {"wrap": 24, "justify": "left", "anchor": "nw"}

    box = tkcurses.Frame(area, relief="solid", bd=1)
    box.pack(side="top", fill="both", expand=True, padx=1, pady=1)
    # Propagation left on: the frame should grow to whatever the wrapped text
    # needs, which is half of what this scenario is showing.
    prose = tkcurses.Label(box, text=PROSE)
    prose.pack(fill="both", expand=True)

    word_box = tkcurses.Frame(area, relief="solid", bd=1, height=6)
    word_box.pack(side="top", fill="x", padx=1, pady=1)
    word_box.pack_propagate(False)
    word = tkcurses.Label(word_box, text=LONG_WORD, anchor="nw", justify="left")
    word.pack(fill="both", expand=True)

    narrow = tkcurses.Frame(area, relief="solid", bd=1, width=12, height=3)
    narrow.pack(side="top", padx=1, pady=1)
    narrow.pack_propagate(False)
    tkcurses.Label(narrow, text="far too wide to fit here", anchor="w").pack(
        fill="both", expand=True
    )

    def relayout():
        prose.configure(
            wraplength=state["wrap"],
            justify=state["justify"],
            anchor=state["anchor"],
        )
        word.configure(wraplength=state["wrap"])
        root.update_layout()
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  wrap={state['wrap'] or 'none'}  justify={state['justify']}  "
            f"anchor={state['anchor']}   w wrap, j justify, a anchor",
        )
        screen.footer(" Escape quits ")
        screen.refresh()

    def cycle(name, values):
        def handler(event):
            state[name] = values[(values.index(state[name]) + 1) % len(values)]
            relayout()

        return handler

    root.bind("<Key-w>", cycle("wrap", WRAPS))
    root.bind("<Key-j>", cycle("justify", JUSTIFIES))
    root.bind("<Key-a>", cycle("anchor", ANCHORS))
    relayout()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
