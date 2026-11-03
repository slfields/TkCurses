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

"""Record what real Tk does with random Listbox gestures, as test data.

Run with a display and the system tkinter, from the repository root::

    DISPLAY=:0 /usr/bin/python3 tests/support/record_listbox_gestures.py

It writes ``listbox_gestures.json`` beside itself, which
``tests/test_listbox.py`` replays against tkcurses. A step is one of:

=========  ==========================================================
``c n``    click row ``n``; ``s``/``t`` with Shift/Control; ``d`` a
           second click at the same instant, which Tk reads as double
``m a b``  press on row ``a``, drag to row ``b``, release there
``k K M``  key ``K`` with modifiers ``M`` (``S`` Shift, ``C`` Control)
``v V``    the virtual event ``<<V>>``
``p n``    ``selection_set(n)``; ``a`` anchor, ``g`` activate,
           ``e`` see
``i n k``  insert ``k`` items before ``n``; ``x f l`` delete f to l
``D``/``N`` state disabled / normal
=========  ==========================================================

After every step it records the selection, the ``<<ListboxSelect>>``
count, the active and anchor indices, the top row and the characters
scrolled off to the left, and the size. Each sequence starts from one state
in both libraries - anchor and active at 0, and Tk's shared
``Priv(listboxPrev)`` back to the ``""`` that ``tk.tcl`` gives it - because
Tk keeps that state global across listboxes and moves the anchor on insert,
and neither is what a sequence is comparing. TkCurses-xk41, TkCurses-cpk9,
TkCurses-46ap, TkCurses-ofko.
"""

from __future__ import annotations

import json
import random
import tkinter
import tkinter.font
from pathlib import Path

#: Of different lengths, so that the view scrolls sideways as well.
ITEMS = [
    "alpha",
    "b",
    "charlie-delta-echo-foxtrot",
    "d",
    "echo",
    "f-golf-hotel",
    "g",
    "h",
    "india-juliet",
]
WIDTH = 10
HEIGHT = 4
MODES = ("browse", "single", "multiple", "extended")
#: Shift and Control as X reports them in an event's state.
STATES = {"c": 0, "s": 1, "t": 4}
MODIFIERS = {"": 0, "S": 1, "C": 4, "CS": 5}
#: The keys listbox.tcl binds, each with the modifiers it binds it under,
#: and a few it does not, to see what they fall through to.
KEYS = [
    ("Up", ""), ("Down", ""), ("Up", "S"), ("Down", "S"), ("Up", "C"),
    ("Left", ""), ("Right", ""), ("Left", "C"), ("Right", "C"),
    ("Left", "S"), ("Prior", ""), ("Next", ""), ("Prior", "C"),
    ("Next", "C"), ("Home", ""), ("End", ""), ("Home", "C"), ("End", "C"),
    ("Home", "CS"), ("End", "CS"), ("Home", "S"), ("space", ""),
    ("space", "CS"), ("space", "S"), ("Escape", ""),
]  # fmt: skip
# Not Select: this X server's keymap has no keycode for it, and Tk delivers a
# synthesised one as "??", which no binding hears.
VIRTUAL = ["SelectAll", "SelectNone"]

#: Sequences random ones seldom reach, each for a branch of
#: tk::ListboxMotion: a range crossing its anchor after a Control-click,
#: upward and downward, which gives back what the click had kept; and a first
#: range from an anchor above items a program selected. Run with every item
#: in view, ``FULL`` rows tall, since a click names a visible row.
FULL = len(ITEMS)
EDGES: list[tuple[str, list[list[object]]]] = [
    ("extended", [["c", 1], ["t", 3], ["s", 0], ["s", 5]]),
    ("extended", [["c", 5], ["t", 2], ["s", 6], ["s", 0]]),
    ("extended", [["c", 0], ["t", 6], ["t", 3], ["s", 1], ["s", 5]]),
    ("extended", [["p", 0], ["a", 5], ["p", 5], ["s", 2]]),
    ("extended", [["p", 1], ["p", 6], ["a", 4], ["p", 4], ["s", 3]]),
    # Escape restores what a Shift-range replaced, and only that.
    ("extended", [["c", 1], ["t", 3], ["s", 5], ["k", "Escape", ""]]),
    ("extended", [["c", 2], ["s", 0], ["k", "Escape", ""], ["k", "Escape", ""]]),
    # A drag in each mode.
    ("browse", [["m", 0, 3]]),
    ("extended", [["m", 1, 3], ["m", 3, 0]]),
    ("multiple", [["m", 1, 3]]),
    ("single", [["m", 1, 3]]),
    # Double-click.
    ("multiple", [["c", 2], ["d", 2]]),
    ("browse", [["c", 2], ["d", 2]]),
]


def random_steps(rng: random.Random) -> list[list[object]]:
    """A sequence of gestures, keys, commands and state changes."""
    steps: list[list[object]] = []
    rows = len(ITEMS)
    for _ in range(rng.randint(2, 10)):
        kind = rng.choice("ccssttdmkkkkkvpagexiDN")
        if kind == "k":
            key, mods = rng.choice(KEYS)
            steps.append(["k", key, mods])
        elif kind == "v":
            steps.append(["v", rng.choice(VIRTUAL)])
        elif kind == "m":
            steps.append(["m", rng.randrange(HEIGHT), rng.randrange(HEIGHT)])
        elif kind == "i":
            steps.append(["i", rng.randrange(rows + 1), rng.randint(1, 3)])
        elif kind == "x":
            first = rng.randrange(rows)
            steps.append(["x", first, rng.randrange(first, rows)])
        elif kind in "DN":
            steps.append([kind])
        elif kind in "csdt":
            # A click lands where the view shows it, so on a visible row.
            steps.append([kind, rng.randrange(HEIGHT)])
        else:
            steps.append([kind, rng.randrange(rows)])
    return steps


class Recorder:
    """Drives one tkinter Listbox per sequence and reads its state back."""

    def __init__(self) -> None:
        self.root = tkinter.Tk()
        # The named font, not Font(family="TkFixedFont"): that is no family,
        # and Tk quietly falls back to a proportional one.
        self.font = tkinter.font.nametofont("TkFixedFont")
        # Not metrics("fixed"): Noto Sans Mono, a monospace face, reports 0.
        widths = {self.font.measure(c) for c in "iW0-"}
        assert len(widths) == 1, f"TkFixedFont is not monospaced: {widths}"
        self.char = self.font.measure("0")
        self.clock = 1000

    def state(self, box: tkinter.Listbox, seen: list[int]) -> list[object]:
        size = box.size()
        top = round(box.yview()[0] * size) if size else 0
        widest = max((self.font.measure(box.get(i)) for i in range(size)), default=0)
        left = round(box.xview()[0] * widest / self.char)
        return [
            list(box.curselection()),
            len(seen),
            box.index("active"),
            box.index("anchor"),
            top,
            left,
            size,
        ]

    def row_y(self, box: tkinter.Listbox, row: int) -> tuple[int, int]:
        """The middle of the ``row``-th visible line, from the top line's box."""
        top = round(box.yview()[0] * box.size()) if box.size() else 0
        bbox = box.bbox(top)
        if bbox is None:  # empty listbox
            return 5, 5
        _, y, _, h = bbox
        return 3, y + h * row + h // 2

    def press(self, box, row, state=0, *, same_time=False):
        if not same_time:
            self.clock += 2000
        x, y = self.row_y(box, row)
        box.event_generate("<Button-1>", x=x, y=y, state=state, time=self.clock)
        box.event_generate(
            "<ButtonRelease-1>", x=x, y=y, state=state, time=self.clock + 5
        )

    def run(
        self, mode: str, steps: list[list[object]], height: int
    ) -> list[list[object]]:
        root = self.root
        box = tkinter.Listbox(
            root,
            selectmode=mode,
            height=height,
            width=WIDTH,
            font=self.font,
            exportselection=False,
        )
        box.insert("end", *ITEMS)
        box.pack()
        box.focus_force()
        root.update()
        box.selection_anchor(0)
        box.activate(0)
        root.tk.eval("set ::tk::Priv(listboxPrev) {}")
        root.tk.eval("unset -nocomplain ::tk::Priv(listboxSelection)")
        seen: list[int] = []
        box.bind("<<ListboxSelect>>", lambda event: seen.append(1))
        after = []
        for step in steps:
            kind = step[0]
            if kind in STATES:
                self.press(box, step[1], STATES[kind])
            elif kind == "d":
                self.press(box, step[1], same_time=True)
            elif kind == "m":
                self.clock += 2000
                x, y = self.row_y(box, step[1])
                box.event_generate("<Button-1>", x=x, y=y, time=self.clock)
                x, y = self.row_y(box, step[2])
                box.event_generate(
                    "<Motion>", x=x, y=y, state=0x100, time=self.clock + 5
                )
                box.event_generate(
                    "<ButtonRelease-1>", x=x, y=y, state=0x100, time=self.clock + 9
                )
            elif kind == "k":
                box.event_generate(
                    "<KeyPress>", keysym=str(step[1]), state=MODIFIERS[str(step[2])]
                )
            elif kind == "v":
                box.event_generate(f"<<{step[1]}>>")
            elif kind == "p":
                box.selection_set(step[1])
            elif kind == "a":
                box.selection_anchor(step[1])
            elif kind == "g":
                box.activate(step[1])
            elif kind == "e":
                box.see(step[1])
            elif kind == "i":
                box.insert(step[1], *[f"new{n}" for n in range(int(str(step[2])))])
            elif kind == "x":
                box.delete(step[1], step[2])
            elif kind == "D":
                box.configure(state="disabled")
            elif kind == "N":
                box.configure(state="normal")
            root.update()
            after.append(self.state(box, seen))
        box.destroy()
        return after


def record(count: int = 600, seed: int = 20261103) -> list[dict[str, object]]:
    rng = random.Random(seed)
    recorder = Recorder()
    plans = [(mode, steps, FULL) for mode, steps in EDGES]
    plans += [(rng.choice(MODES), random_steps(rng), HEIGHT) for _ in range(count)]
    cases = [
        {
            "mode": mode,
            "height": height,
            "steps": steps,
            "after": recorder.run(mode, steps, height),
        }
        for mode, steps, height in plans
    ]
    recorder.root.destroy()
    return cases


if __name__ == "__main__":
    out = Path(__file__).with_name("listbox_gestures.json")
    data = {
        "measured": "tkinter on Python 3.14 over Tk 9.0.2",
        "items": ITEMS,
        "width": WIDTH,
        "cases": record(),
    }
    out.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(f"{len(data['cases'])} cases -> {out}")
