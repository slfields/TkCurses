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


"""Record where Tk's Text view goes when its text is edited, as test data.

Run with a display and the system tkinter, from the repository root::

    DISPLAY=:0 /usr/bin/python3 tests/support/record_text_view.py

It writes ``text_view.json`` beside itself, which ``tests/test_text_view.py``
replays against tkcurses. Each run scrolls a Text, then edits it and scrolls
it in random steps:

==========  =========================================================
``y n``     ``yview moveto 0``, then ``yview scroll n units``
``x n``     ``xview scroll n units``
``m f``     ``xview moveto f``, 0 or 1
``i a s``   ``insert a s``
``d a b``   ``delete a b``
``p a s``   ``insert a s`` through a peer
``q a b``   ``delete a b`` through a peer
==========  =========================================================

Only whole columns sideways: Tk's ``xview moveto`` goes to a fraction of a
pixel, part way across a character, where a terminal cell cannot.

After every step: the first index on screen and ``xview``. Tk keeps its
view as an index, so an edit above the view leaves what it shows in place
(TkCurses-ntu4), and how far it scrolls sideways is bounded by the rows on
screen rather than the whole text (TkCurses-8tjr).
"""

from __future__ import annotations

import json
import random
import tkinter
import tkinter.font
from pathlib import Path

#: Lines from empty to four rows wide, so a wrapped one is several rows and
#: an unwrapped one is wider than the view, or not.
LENGTHS = (0, 3, 8, 15, 16, 17, 24, 31, 40, 60)
INSERTS = ("", "ab", "xyz\n", "\n", "a long piece of text ", "p\nq\nr\n", "\n\n")
WIDGETS = {"Text": "none", "Wrapped": "word"}


def corpus(rng: random.Random) -> str:
    words = "alpha be gamma delta epsilon z"
    lines = []
    for number in range(1, 31):
        length = rng.choice(LENGTHS)
        line = f"{number:02d} " + (words * 4)
        lines.append(line[:length])
    return "\n".join(lines)


def random_index(rng: random.Random, text: str) -> str:
    lines = text.split("\n")
    row = rng.randrange(len(lines))
    return f"{row + 1}.{rng.randrange(len(lines[row]) + 1)}"


def random_steps(rng: random.Random, text: str) -> list[list[object]]:
    steps: list[list[object]] = [["y", rng.randrange(30)]]
    if rng.random() < 0.5:
        steps.append(["x", rng.randrange(1, 40)])
    for _ in range(rng.randint(1, 6)):
        choice = rng.choice("iiiddyxmpq")
        if choice in "ip":
            steps.append([choice, random_index(rng, text), rng.choice(INSERTS)])
        elif choice in "dq":
            a, b = sorted(
                (random_index(rng, text), random_index(rng, text)),
                key=lambda i: tuple(map(int, i.split("."))),
            )
            steps.append([choice, a, b])
        elif choice == "y":
            steps.append(["y", rng.randrange(30)])
        elif choice == "x":
            steps.append(["x", rng.randrange(-20, 30)])
        else:
            steps.append(["m", rng.choice((0.0, 1.0))])
    return steps


def state(widget: tkinter.Text) -> list[object]:
    return [widget.index("@0,0"), [round(f, 4) for f in widget.xview()]]


def run(root, font, wrap: str, text: str, steps) -> list[list[object]]:
    widget = tkinter.Text(root, font=font, width=16, height=4, wrap=wrap)
    widget.pack()
    widget.insert("1.0", text)
    other = f"{widget}_peer"
    root.tk.call(widget, "peer", "create", other)
    root.update()
    after = []
    for kind, *args in steps:
        if kind == "y":
            widget.yview_moveto(0)
            widget.yview_scroll(args[0], "units")
        elif kind == "x":
            widget.xview_scroll(args[0], "units")
        elif kind == "m":
            widget.xview_moveto(args[0])
        elif kind == "i":
            widget.insert(args[0], args[1])
        elif kind == "d":
            widget.delete(args[0], args[1])
        elif kind == "p":
            root.tk.call(other, "insert", args[0], args[1])
        else:
            root.tk.call(other, "delete", args[0], args[1])
        root.update()
        after.append(state(widget))
    root.tk.call("destroy", other)
    widget.destroy()
    return after


def record(count: int = 150, seed: int = 20261104) -> dict[str, list[object]]:
    rng = random.Random(seed)
    root = tkinter.Tk()
    font = tkinter.font.nametofont("TkFixedFont")
    assert len({font.measure(c) for c in "iW0-"}) == 1, "not monospaced"
    cases: dict[str, list[object]] = {}
    for kind, wrap in WIDGETS.items():
        cases[kind] = []
        for _ in range(count):
            text = corpus(rng)
            steps = random_steps(rng, text)
            cases[kind].append(
                {
                    "text": text,
                    "steps": steps,
                    "after": run(root, font, wrap, text, steps),
                }
            )
    root.destroy()
    return cases


if __name__ == "__main__":
    out = Path(__file__).with_name("text_view.json")
    data = {"measured": "tkinter on Python 3.14 over Tk 9.0.2", "cases": record()}
    out.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(sum(map(len, data["cases"].values())), "cases ->", out)
