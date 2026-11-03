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
``tests/test_listbox.py`` replays against tkcurses. Each sequence starts
from one state in both libraries - anchor and active at 0, and Tk's shared
``Priv(listboxPrev)`` back to the ``""`` that ``tk.tcl`` gives it - because
Tk keeps that state global across listboxes and moves the anchor on insert,
and neither is what is being compared. TkCurses-xk41.
"""

from __future__ import annotations

import json
import random
import tkinter
from pathlib import Path

ITEMS = 7
MODES = ("browse", "single", "multiple", "extended")
#: Shift and Control as X reports them in an event's state.
STATES = {"c": 0, "s": 1, "t": 4}


#: Sequences random ones seldom reach, each for a branch of
#: tk::ListboxMotion: a range crossing its anchor after a Control-click,
#: upward and downward, which gives back what the click had kept; and a first
#: range from an anchor above items a program selected.
EDGES: list[tuple[str, list[list[object]]]] = [
    ("extended", [["c", 1], ["t", 3], ["s", 0], ["s", 5]]),
    ("extended", [["c", 5], ["t", 2], ["s", 6], ["s", 0]]),
    ("extended", [["c", 0], ["t", 6], ["t", 3], ["s", 1], ["s", 5]]),
    ("extended", [["p", 0], ["a", 5], ["p", 5], ["s", 2]]),
    ("extended", [["p", 1], ["p", 6], ["a", 4], ["p", 4], ["s", 3]]),
]


def random_steps(rng: random.Random) -> list[list[object]]:
    """A gesture sequence: clicks plain, shifted and with Control, the keys
    that select, and the two widget commands a program mixes in."""
    steps: list[list[object]] = []
    for _ in range(rng.randint(2, 9)):
        kind = rng.choice("ccssttkkpa")
        if kind == "k":
            steps.append(["k", rng.choice(["Up", "Down", "space"])])
        else:
            steps.append([kind, rng.randrange(ITEMS)])
    return steps


def record(count: int = 400, seed: int = 20261103) -> list[dict[str, object]]:
    rng = random.Random(seed)
    root = tkinter.Tk()
    clock = [1000]
    cases = []
    plans = list(EDGES)
    plans += [(rng.choice(MODES), random_steps(rng)) for _ in range(count)]
    for mode, steps in plans:
        box = tkinter.Listbox(root, selectmode=mode, height=ITEMS)
        box.insert("end", *"abcdefg"[:ITEMS])
        box.pack()
        box.focus_force()
        root.update()
        boxes = {i: box.bbox(i) for i in range(ITEMS)}
        box.selection_anchor(0)
        box.activate(0)
        root.tk.eval("set ::tk::Priv(listboxPrev) {}")
        root.tk.eval("unset -nocomplain ::tk::Priv(listboxSelection)")
        seen: list[int] = []
        box.bind("<<ListboxSelect>>", lambda event, seen=seen: seen.append(1))
        after = []
        for kind, what in steps:
            if kind == "k":
                box.event_generate("<KeyPress>", keysym=str(what))
            elif kind == "p":
                box.selection_set(what)
            elif kind == "a":
                box.selection_anchor(what)
            else:
                # A timestamp each, two seconds apart, or a repeat on the
                # same row is a double-click, which Tk's Listbox ignores.
                clock[0] += 2000
                x, y, _, _ = boxes[int(str(what))]
                state = STATES[str(kind)]
                for sequence, time in (
                    ("<Button-1>", clock[0]),
                    ("<ButtonRelease-1>", clock[0] + 5),
                ):
                    box.event_generate(
                        sequence, x=x + 1, y=y + 1, state=state, time=time
                    )
            root.update()
            after.append([list(box.curselection()), len(seen)])
        cases.append({"mode": mode, "steps": steps, "after": after})
        box.destroy()
    root.destroy()
    return cases


if __name__ == "__main__":
    out = Path(__file__).with_name("listbox_gestures.json")
    data = {
        "measured": "tkinter on Python 3.14 over Tk 9.0.2",
        "cases": record(),
    }
    out.write_text(json.dumps(data, indent=0) + "\n")
    print(f"{len(data['cases'])} cases -> {out}")
