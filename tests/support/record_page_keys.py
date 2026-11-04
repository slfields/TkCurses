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
"""Record what real Tk does with Prior, Next and the view of a Text.

Run with a display and the system tkinter, from the repository root::

    DISPLAY=:0 /usr/bin/python3 tests/support/record_page_keys.py

It writes ``page_keys.json`` beside itself, which ``tests/test_page_keys.py``
replays against tkcurses. A step is one of:

=========  ==========================================================
``k K M``  key ``K`` with modifiers ``M`` (``S`` Shift, ``C`` Control)
``j i``    ``mark_set("insert", i)``, which does not move the view
``y n``    ``yview scroll n units``; ``Y`` pages; ``x``/``X`` sideways
``r a b``  ``tag_add("sel", a, b)``, after clearing it
=========  ==========================================================

After every step it records the cursor, the selection, the first index on
screen - ``@0,0``, which Tk answers from the top row's first visible
character - and how many columns the view is scrolled sideways.

Every line that is not empty is ``WIDTH`` characters long. Tk measures how
far a Text scrolls sideways by the longest line it is showing, and ours by
the longest line it holds; with one length the two are the same, and that
difference is not what this records. TkCurses-5co5.
"""

from __future__ import annotations

import json
import random
import tkinter
import tkinter.font
from pathlib import Path

WIDTH = 40
WORDS = [
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "zeta",
    "eta",
    "theta",
    "iota",
    "kappa",
    "lambda",
    "mu",
]


def make_text(rng: random.Random) -> str:
    lines = []
    for n in range(1, 41):
        if n % 7 == 0:
            lines.append("")
            continue
        line = f"{n:02d}"
        while len(line) < WIDTH:
            line += " " + rng.choice(WORDS)
        lines.append(line[:WIDTH])
    return "\n".join(lines)


TEXT = make_text(random.Random(5))
LINES = TEXT.split("\n")
MODIFIERS = {"": 0, "S": 1, "C": 4, "CS": 5}
KEYS = [
    *[(key, mods) for key in ("Prior", "Next") for mods in MODIFIERS] * 3,
    *[(key, mods) for key in ("Up", "Down") for mods in ("", "S")],
    *[(key, mods) for key in ("Left", "Right") for mods in ("", "S", "C")],
    *[(key, mods) for key in ("Home", "End") for mods in ("", "S", "C")],
]
#: Each widget: its height, and how it wraps. A page is three lines of four
#: and ten of twelve; see's reach is three lines in both, and four in twelve.
WIDGETS = {"Text4": (4, "none"), "Text12": (12, "none"), "Wrapped4": (4, "word")}


def random_index(rng: random.Random) -> str:
    row = rng.randrange(len(LINES))
    return f"{row + 1}.{rng.randrange(len(LINES[row]) + 1)}"


def random_steps(rng: random.Random) -> list[list[object]]:
    steps: list[list[object]] = []
    for _ in range(rng.randint(2, 10)):
        choice = rng.choice("kkkkkkkkjyYxXr")
        if choice == "k":
            steps.append(["k", *rng.choice(KEYS)])
        elif choice == "j":
            steps.append(["j", random_index(rng)])
        elif choice in "yY":
            steps.append(
                [
                    choice,
                    rng.choice([-1, 1]) * rng.randint(1, 8 if choice == "y" else 2),
                ]
            )
        elif choice in "xX":
            steps.append(
                [
                    choice,
                    rng.choice([-1, 1]) * rng.randint(1, 12 if choice == "x" else 2),
                ]
            )
        else:
            a, b = sorted(
                (random_index(rng), random_index(rng)),
                key=lambda i: tuple(map(int, i.split("."))),
            )
            steps.append(["r", a, b])
    return steps


def state(text: tkinter.Text) -> list[object]:
    return [
        text.index("insert"),
        [str(i) for i in text.tag_ranges("sel")],
        text.index("@0,0"),
        round(text.xview()[0] * WIDTH),
    ]


def run(root, font, kind: str, steps: list[list[object]]) -> list[list[object]]:
    height, wrap = WIDGETS[kind]
    text = tkinter.Text(root, font=font, width=16, height=height, wrap=wrap)
    text.configure(exportselection=False)
    text.pack()
    text.insert("1.0", TEXT)
    text.mark_set("insert", "1.0")
    text.yview_moveto(0)
    text.xview_moveto(0)
    text.focus_force()
    root.update()
    root.tk.eval("set ::tk::Priv(prevPos) {}")
    root.tk.eval("unset -nocomplain ::tk::Priv(textPosOrig)")
    after = []
    for step in steps:
        kind_of = step[0]
        if kind_of == "k":
            text.event_generate(
                "<KeyPress>", keysym=str(step[1]), state=MODIFIERS[str(step[2])]
            )
        elif kind_of == "j":
            text.mark_set("insert", step[1])
        elif kind_of in "yY":
            text.yview_scroll(step[1], "units" if kind_of == "y" else "pages")
        elif kind_of in "xX":
            text.xview_scroll(step[1], "units" if kind_of == "x" else "pages")
        else:
            text.tag_remove("sel", "1.0", "end")
            text.tag_add("sel", step[1], step[2])
        root.update()
        after.append(state(text))
    text.destroy()
    return after


def record(count: int = 150, seed: int = 20261105) -> dict[str, list[object]]:
    rng = random.Random(seed)
    root = tkinter.Tk()
    font = tkinter.font.nametofont("TkFixedFont")
    assert len({font.measure(c) for c in "iW0-"}) == 1, "not monospaced"
    cases: dict[str, list[object]] = {}
    for kind in WIDGETS:
        plans = [random_steps(rng) for _ in range(count)]
        cases[kind] = [
            {"steps": steps, "after": run(root, font, kind, steps)} for steps in plans
        ]
    root.destroy()
    return cases


if __name__ == "__main__":
    out = Path(__file__).with_name("page_keys.json")
    data = {
        "measured": "tkinter on Python 3.14 over Tk 9.0.2",
        "text": TEXT,
        "cases": record(),
    }
    out.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(sum(map(len, data["cases"].values())), "cases ->", out)
