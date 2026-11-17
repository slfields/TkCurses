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

"""Random classic PanedWindows, laid out by Tk itself, for the tests to match.

Each case is a paned window of a fixed length with panes of known sizes,
``minsize``, ``stretch`` and ``width`` (or ``height``) drawn at random, and
then a few things done to it in turn: the window resized, a pane's size or
stretch configured, a sash placed. After the start and after each step,
every sash's position along the window and the window's requested length
are recorded; ``tests/test_paned_reference.py`` does the same in TkCurses
and wants every number the same (TkCurses-g60s).

The panes are frames sized in pixels, so a pixel stands for a cell, and
the sashes are one pixel with no padding, as TkCurses' are. A frame given
no size reports 1 pixel, so every size here is at least 1.

Needs tkinter and a display; the root is withdrawn, so no window shows.
Run from the repository root, with Tk 9.0.2 or what the reference follows::

    python3 tests/support/record_paned_reference.py
"""

from __future__ import annotations

import json
import random
import tkinter
from pathlib import Path
from typing import Any

OUT = Path(__file__).with_name("paned_reference.json")

#: Fixed, so that recording again gives the same cases.
SEED = 9003
CASES = 200

STRETCH = ["always", "first", "last", "middle", "never"]


def make_case(rng: random.Random) -> dict[str, Any]:
    """One random paned window: its panes, and what is then done to it."""
    count = rng.randint(1, 4)
    panes = []
    for _ in range(count):
        options: dict[str, Any] = {}
        if rng.random() < 0.6:
            options["minsize"] = rng.choice([0, 3, 10, 25])
        if rng.random() < 0.5:
            options["stretch"] = rng.choice(STRETCH)
        if rng.random() < 0.25:
            options["size"] = rng.randint(1, 40)
        panes.append({"size": rng.randint(1, 30), "options": options})
    steps: list[list[Any]] = []
    for _ in range(rng.randint(1, 4)):
        kind = rng.choice(["resize", "resize", "size", "place", "place", "stretch"])
        index = rng.randrange(count)
        if kind == "resize":
            steps.append(["resize", rng.randint(5, 120)])
        elif kind == "size":
            steps.append(["size", index, rng.randint(1, 40)])
        elif kind == "stretch":
            steps.append(["stretch", index, rng.choice(STRETCH)])
        elif count > 1:
            steps.append(["place", rng.randrange(count - 1), rng.randint(0, 100)])
    return {
        "orient": rng.choice(["horizontal", "horizontal", "vertical"]),
        "length": rng.randint(5, 120),
        "panes": panes,
        "steps": steps,
    }


def lay_out(root: tkinter.Tk, case: dict[str, Any]) -> list[list[int]]:
    """Sash positions and requested length, at the start and after each step."""
    vertical = case["orient"] == "vertical"
    along = "height" if vertical else "width"
    window = tkinter.PanedWindow(
        root, orient=case["orient"], sashwidth=1, sashpad=0, showhandle=False, bd=0
    )
    fixed: dict[str, Any] = {"height": 10} if not vertical else {"width": 10}
    window.place(x=0, y=0, **fixed, **{along: case["length"]})
    children = []
    for pane in case["panes"]:
        frame = tkinter.Frame(
            window, **{along: pane["size"]}, bd=0, highlightthickness=0
        )
        frame.configure({"height" if not vertical else "width": 5})
        options = dict(pane["options"])
        if "size" in options:
            options[along] = options.pop("size")
        window.add(frame, **options)
        children.append(frame)

    def snapshot() -> list[int]:
        root.update()
        sashes = [window.sash_coord(index) for index in range(len(children) - 1)]
        requested = window.winfo_reqheight() if vertical else window.winfo_reqwidth()
        return [sash[1] if vertical else sash[0] for sash in sashes] + [requested]

    record = [snapshot()]
    for step in case["steps"]:
        if step[0] == "resize":
            window.place(**{along: step[1]})
        elif step[0] == "size":
            # typeshed leaves paneconfigure unannotated.
            window.paneconfigure(children[step[1]], **{along: step[2]})  # type: ignore[no-untyped-call]
        elif step[0] == "stretch":
            window.paneconfigure(children[step[1]], stretch=step[2])  # type: ignore[no-untyped-call]
        else:
            at = (0, step[2]) if vertical else (step[2], 0)
            window.sash_place(step[1], *at)
        record.append(snapshot())
    window.destroy()
    return record


def main() -> None:
    rng = random.Random(SEED)
    root = tkinter.Tk()
    root.geometry("400x400")
    cases = []
    for _ in range(CASES):
        case = make_case(rng)
        case["tk"] = lay_out(root, case)
        cases.append(case)
    root.destroy()
    record = {"tk": root.tk.call("info", "patchlevel"), "cases": cases}
    OUT.write_text(json.dumps(record, indent=None, separators=(",", ":")) + "\n")
    print(f"{len(cases)} paned windows recorded in {OUT}")


if __name__ == "__main__":
    main()
