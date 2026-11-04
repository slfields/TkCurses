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


"""Record where Tk's undo and redo leave a Text's cursor and view.

Run with a display and the system tkinter, from the repository root::

    DISPLAY=:0 /usr/bin/python3 tests/support/record_text_undo.py

It writes ``text_undo.json`` beside itself, which ``tests/test_text_undo.py``
replays against tkcurses. Each run edits a Text 16 by 4 and a peer of it,
in random steps, and undoes and redoes through either:

==========  =========================================================
``i a s``   ``insert a s``, and ``p a s`` the same through the peer
``d a b``   ``delete a b``, and ``q a b`` the same through the peer
``s``       ``edit separator``
``u``       ``edit undo``, and ``U`` the same through the peer
``r``       ``edit redo``, and ``R`` the same through the peer
``j i``     ``mark set insert i``
``y n``     ``yview moveto 0``, then ``yview scroll n units``
==========  =========================================================

Each widget's command is wrapped so that every ``see`` - the undo atoms'
own included - is followed by ``yview`` to the first index on screen.
Tk centres in pixels and a terminal cannot: ``see`` puts the bottom of the
line it centres at ``(dInfoPtr->y + dInfoPtr->maxY + lineHeight)/2``
(TkTextSetYView, in tkTextDisp.c), and with Tk's 3-pixel inset that leaves
the top line partly out of the window at every height. The first index on
screen is the same either way; the next ``see`` is not, since it measures
from the pixel. Measured on Tk 9.0.2 at four rows: from 16.0 reached by
``yview``, ``see 23.8`` shows 21.0; from 16.0 reached by centring on 18.9,
20.0. Each step asserts the top lines are whole.

After every step: each widget's ``insert`` and first index on screen, and
what an undo or redo answered - its ranges, or ``"error"`` when there was
nothing to take. Tk's undo atoms set the cursor of the Text that made the
edit and see it (TextPushUndoAction, in tkText.c), and ``edit undo`` answers
the ranges ``tk::TextUndoRedoProcessMarks`` makes. TkCurses-2sbq.
"""

from __future__ import annotations

import json
import random
import tkinter
import tkinter.font
from pathlib import Path

LINES = "\n".join(f"line {k:02d} " + "abc" * (k % 3) for k in range(1, 41))
INSERTS = ("x", "ab", "xyz\n", "\n", "p\nq\nr\n", "a long one ")


def random_index(rng: random.Random) -> str:
    row = rng.randrange(1, 42)
    return f"{row}.{rng.randrange(14)}"


def random_steps(rng: random.Random) -> list[list[object]]:
    steps: list[list[object]] = [["y", rng.randrange(30)]]
    for _ in range(rng.randint(3, 12)):
        choice = rng.choice("iiippddqsssuuuUrrRjy")
        if choice in "ip":
            steps.append([choice, random_index(rng), rng.choice(INSERTS)])
        elif choice in "dq":
            a, b = sorted(
                (random_index(rng), random_index(rng)),
                key=lambda i: tuple(map(int, i.split("."))),
            )
            steps.append([choice, a, b])
        elif choice == "j":
            steps.append(["j", random_index(rng)])
        elif choice == "y":
            steps.append(["y", rng.randrange(30)])
        else:
            steps.append([choice])
    return steps


def whole_lines(root, view: str) -> None:
    """Follow every ``see`` on ``view`` with ``yview`` to its first index."""
    root.tk.eval(f"""
        rename {view} {view}_tk
        proc {view} {{args}} {{
            set result [uplevel 1 [list {view}_tk {{*}}$args]]
            if {{[lindex $args 0] eq "see"}} {{
                {view}_tk yview [{view}_tk index @0,0]
            }}
            return $result
        }}
    """)


def run(root, font, auto: bool, steps) -> list[list[object]]:
    widget = tkinter.Text(
        root, font=font, width=16, height=4, wrap="none", undo=True,
        autoseparators=auto,
    )  # fmt: skip
    widget.pack()
    widget.insert("1.0", LINES)
    widget.edit_reset()
    other = f"{widget}_peer"
    root.tk.call(widget, "peer", "create", other, "-width", 16, "-height", 4)
    root.tk.call("pack", other)
    root.update()
    views = (str(widget), other)
    for view in views:
        whole_lines(root, view)
    inset = widget.dlineinfo("1.0")[1]
    after = []
    for kind, *args in steps:
        answer: object = None
        target = other if kind in "pqUR" else str(widget)
        if kind in "ip":
            root.tk.call(target, "insert", args[0], args[1])
        elif kind in "dq":
            root.tk.call(target, "delete", args[0], args[1])
        elif kind == "s":
            widget.edit_separator()
        elif kind in "uUrR":
            try:
                result = root.tk.call(
                    target, "edit", "undo" if kind in "uU" else "redo"
                )
                answer = [str(i) for i in root.tk.splitlist(result)]
            except tkinter.TclError:
                answer = "error"
        elif kind == "j":
            widget.mark_set("insert", args[0])
        else:
            widget.yview_moveto(0)
            widget.yview_scroll(args[0], "units")
        root.update()
        tops = []
        for view in views:
            top = str(root.tk.call(view, "index", "@0,0"))
            line = root.tk.splitlist(root.tk.call(view, "dlineinfo", top))
            assert int(line[1]) == inset, f"{view} is between lines at {top}"
            tops.append(top)
        after.append([
            widget.index("insert"), str(root.tk.call(other, "index", "insert")),
            tops[0], tops[1], answer,
        ])  # fmt: skip
    root.tk.call("destroy", other)
    widget.destroy()
    for view in views:
        root.tk.call("rename", view, "")
    return after


def record(count: int = 200, seed: int = 20261104) -> list[dict[str, object]]:
    rng = random.Random(seed)
    root = tkinter.Tk()
    font = tkinter.font.nametofont("TkFixedFont")
    assert len({font.measure(c) for c in "iW0-"}) == 1, "not monospaced"
    cases = []
    for n in range(count):
        auto = n % 2 == 1
        steps = random_steps(rng)
        cases.append(
            {"auto": auto, "steps": steps, "after": run(root, font, auto, steps)}
        )
    root.destroy()
    return cases


if __name__ == "__main__":
    out = Path(__file__).with_name("text_undo.json")
    data = {
        "measured": "tkinter on Python 3.14 over Tk 9.0.2",
        "text": LINES,
        "cases": record(),
    }
    out.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(len(data["cases"]), "cases ->", out)
