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

"""Random grids, laid out by Tk itself, for the grid tests to match.

Each case is a container of a fixed size with gridded children of known
sizes, and row and column configuration drawn at random: weights,
``minsize``, ``pad``, ``uniform``, spans, padding and the grid's anchor.
Tk lays it out and ``grid_bbox`` of every cell is recorded;
``tests/test_grid_reference.py`` lays the same case out in TkCurses and
wants every cell the same (TkCurses-xcy3).

The children are frames sized in pixels, so a pixel stands for a cell. A
frame given no width or height makes no request and reports 1 pixel, so
every size here is at least 1.

Needs tkinter and a display; the root is withdrawn, so no window shows.
Run from the repository root, with Tk 9.0.2 or what the reference follows::

    python3 tests/support/record_grid_reference.py
"""

from __future__ import annotations

import json
import random
import tkinter
from pathlib import Path
from typing import Any

OUT = Path(__file__).with_name("grid_reference.json")

#: Fixed, so that recording again gives the same cases.
SEED = 9002
CASES = 150


def make_case(rng: random.Random) -> dict[str, Any]:
    """One random grid: its size, its children and its lines' configuration."""
    columns, rows = rng.randint(1, 5), rng.randint(1, 4)
    children = []
    for _ in range(rng.randint(1, 7)):
        column, row = rng.randrange(columns), rng.randrange(rows)
        children.append(
            {
                "column": column,
                "row": row,
                "columnspan": rng.choice([1, 1, 1, rng.randint(1, columns - column)]),
                "rowspan": rng.choice([1, 1, rng.randint(1, rows - row)]),
                "width": rng.randint(1, 14),
                "height": rng.randint(1, 5),
                "padx": rng.choice([0, 0, 1, [1, 0], [0, 2]]),
                "pady": rng.choice([0, 0, 1]),
                "ipadx": rng.choice([0, 0, 1]),
            }
        )
    lines = {}
    for axis, count in (("column", columns), ("row", rows)):
        for index in range(count):
            if rng.random() < 0.7:
                lines[f"{axis} {index}"] = {
                    "weight": rng.choice([0, 0, 1, 1, 2, 3]),
                    "minsize": rng.choice([0, 0, 0, 3, 8]),
                    "pad": rng.choice([0, 0, 0, 1, 2]),
                    "uniform": rng.choice(["", "", "", "u", "v"]),
                }
    return {
        "columns": columns,
        "rows": rows,
        "width": rng.randint(4, 60),
        "height": rng.randint(2, 20),
        "anchor": rng.choice(["nw", "nw", "center", "se", "n", "e"]),
        "children": children,
        "lines": lines,
    }


def lay_out(root: tkinter.Tk, case: dict[str, Any]) -> list[Any]:
    """Every cell's ``grid_bbox`` by rows, then the whole grid's."""
    outer = tkinter.Frame(
        root, width=case["width"], height=case["height"], bd=0, highlightthickness=0
    )
    outer.grid_propagate(False)
    outer.place(x=0, y=0, width=case["width"], height=case["height"])
    for child in case["children"]:
        frame = tkinter.Frame(
            outer,
            width=child["width"],
            height=child["height"],
            bd=0,
            highlightthickness=0,
        )
        frame.grid(
            row=child["row"],
            column=child["column"],
            rowspan=child["rowspan"],
            columnspan=child["columnspan"],
            padx=child["padx"],
            pady=child["pady"],
            ipadx=child["ipadx"],
        )
    for key, config in case["lines"].items():
        axis, index = key.split()
        configure = outer.columnconfigure if axis == "column" else outer.rowconfigure
        configure(int(index), **config)
    outer.grid_anchor(case["anchor"])
    root.update()
    cells = [
        [list(outer.grid_bbox(column, row)) for column in range(case["columns"])]
        for row in range(case["rows"])
    ]
    whole = list(outer.grid_bbox())
    outer.destroy()
    return [cells, whole]


def main() -> None:
    rng = random.Random(SEED)
    root = tkinter.Tk()
    root.geometry("200x100")
    cases = []
    for _ in range(CASES):
        case = make_case(rng)
        case["tk"] = lay_out(root, case)
        cases.append(case)
    root.destroy()
    record = {"tk": root.tk.call("info", "patchlevel"), "cases": cases}
    OUT.write_text(json.dumps(record, indent=None, separators=(",", ":")) + "\n")
    print(f"{len(cases)} grids recorded in {OUT}")


if __name__ == "__main__":
    main()
