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

"""Grid sizes against Tk's own, cell for cell.

``tests/support/grid_reference.json`` holds random grids that Tk 9.0.2
laid out (``tests/support/record_grid_reference.py``); each is laid out
here and every cell's ``grid_bbox`` must be the same. Before TkCurses-xcy3
ported Tk's ``ResolveConstraints`` and ``AdjustOffsets``, 85 grids in 400
matched. The named cases below are the ones that found it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tkcurses import Misc, Widget
from tkcurses._core.geometry import Rect, Size

REFERENCE = json.loads(
    (Path(__file__).parent / "support" / "grid_reference.json").read_text()
)


class Box(Widget):
    """A widget that asks for a fixed size, as the recorder's frames do."""

    def __init__(self, master, width, height):
        super().__init__(master)
        self._requested = Size(width, height)


def lay_out(case):
    root = Misc()
    root._rect = Rect(0, 0, 200, 100)
    root._mapped = True
    outer = Box(root, case["width"], case["height"])
    outer.grid_propagate(False)
    outer.place(x=0, y=0, width=case["width"], height=case["height"])
    for child in case["children"]:
        Box(outer, child["width"], child["height"]).grid(
            row=child["row"],
            column=child["column"],
            rowspan=child["rowspan"],
            columnspan=child["columnspan"],
            padx=child["padx"],
            pady=child["pady"],
            ipadx=child["ipadx"],
        )
    for key, config in case.get("lines", {}).items():
        axis, index = key.split()
        configure = outer.columnconfigure if axis == "column" else outer.rowconfigure
        configure(int(index), **config)
    outer.grid_anchor(case.get("anchor", "nw"))
    root.update_layout()
    return outer


def bboxes(case):
    outer = lay_out(case)
    cells = [
        [list(outer.grid_bbox(column, row)) for column in range(case["columns"])]
        for row in range(case["rows"])
    ]
    return [cells, list(outer.grid_bbox())]


def test_the_reference_was_recorded_from_tk_9():
    assert REFERENCE["tk"].startswith("9.0")
    assert len(REFERENCE["cases"]) == 150


@pytest.mark.parametrize("number", range(len(REFERENCE["cases"])))
def test_a_grid_is_sized_as_tk_sizes_it(number):
    case = REFERENCE["cases"][number]
    assert bboxes(case) == case["tk"]


def uniform_row_under_a_span(span_width):
    """The probe that found it: four uniform columns, one child across them."""
    case = {
        "width": 30,
        "height": 10,
        "columns": 4,
        "rows": 2,
        "children": [
            {
                "row": 0,
                "column": 0,
                "rowspan": 1,
                "columnspan": 4,
                "width": span_width,
                "height": 1,
                "padx": 1,
                "pady": 0,
                "ipadx": 0,
            },
        ]
        + [
            {
                "row": 1,
                "column": column,
                "rowspan": 1,
                "columnspan": 1,
                "width": 5,
                "height": 1,
                "padx": [1, 0],
                "pady": 0,
                "ipadx": 0,
            }
            for column in range(4)
        ],
        "lines": {
            f"column {column}": {"weight": 1, "uniform": "k"} for column in range(4)
        },
    }
    outer = lay_out(case)
    return [list(outer.grid_bbox(column, 1))[::2] for column in range(4)]


def test_a_wide_spanning_child_leaves_uniform_columns_inside_the_container():
    # Measured on Tk 9.0.2: (0,7) (7,7) (14,7) (21,9), 30 in all. TkCurses
    # gave 33, wider than the container, and cut off the last column.
    assert uniform_row_under_a_span(23) == [[0, 7], [7, 7], [14, 7], [21, 9]]


def test_leftover_room_goes_to_the_later_columns_cumulatively():
    # Measured on Tk 9.0.2: 7, 8, 7, 8 - TkCurses gave 7, 7, 7, 9.
    widths = [width for _, width in uniform_row_under_a_span(2)]
    assert widths == [7, 8, 7, 8]


def test_five_weighted_rows_share_their_room_as_tk_shares_it():
    # Measured on Tk 9.0.2: rows of weight 1 sharing 13 are 2, 3, 2, 3, 3;
    # TkCurses gave the whole remainder to the last.
    case = {
        "width": 4,
        "height": 13,
        "columns": 1,
        "rows": 5,
        "children": [
            {
                "row": row,
                "column": 0,
                "rowspan": 1,
                "columnspan": 1,
                "width": 1,
                "height": 1,
                "padx": 0,
                "pady": 0,
                "ipadx": 0,
            }
            for row in range(5)
        ],
        "lines": {f"row {row}": {"weight": 1, "uniform": "r"} for row in range(5)},
    }
    outer = lay_out(case)
    assert [outer.grid_bbox(0, row)[3] for row in range(5)] == [2, 3, 2, 3, 3]
