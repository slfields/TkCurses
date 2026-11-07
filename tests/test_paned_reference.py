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

"""Classic PanedWindow layout against Tk's own, sash for sash.

``tests/support/paned_reference.json`` holds random paned windows that Tk
9.0.2 laid out, resized, reconfigured and had sashes placed in
(``tests/support/record_paned_reference.py``); each is replayed here and
every sash position and requested length must be the same. Before
TkCurses-g60s ported Tk's ``ArrangePanes`` and ``MoveSash``, the panes
shared every change evenly and ``width`` was ignored once a window had
been laid out. The named cases below are the issue's own measurements.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tkcurses import Misc, PanedWindow, TclError, Widget
from tkcurses._core.geometry import Rect, Size

REFERENCE = json.loads(
    (Path(__file__).parent / "support" / "paned_reference.json").read_text()
)


class Box(Widget):
    """A widget that asks for a fixed size, as the recorder's frames do."""

    def __init__(self, master, width, height):
        super().__init__(master)
        self._requested = Size(width, height)


def make(orient="horizontal", length=60):
    root = Misc()
    root._rect = Rect(0, 0, 400, 400)
    root._mapped = True
    window = PanedWindow(
        root, orient=orient, sashwidth=1, sashpad=0, showhandle=0, bd=0
    )
    along = "height" if orient == "vertical" else "width"
    window.place(
        x=0,
        y=0,
        **{along: length},
        **({"height": 10} if along == "width" else {"width": 10}),
    )
    return root, window


def replay(case):
    vertical = case["orient"] == "vertical"
    along = "height" if vertical else "width"
    root, window = make(case["orient"], case["length"])
    children = []
    for pane in case["panes"]:
        size = (5, pane["size"]) if vertical else (pane["size"], 5)
        child = Box(window, *size)
        options = dict(pane["options"])
        if "size" in options:
            options[along] = options.pop("size")
        window.add(child, **options)
        children.append(child)

    def snapshot():
        root.update_layout()
        sashes = [window.sash_coord(index) for index in range(len(children) - 1)]
        requested = window.winfo_reqheight() if vertical else window.winfo_reqwidth()
        return [sash[1] if vertical else sash[0] for sash in sashes] + [requested]

    record = [snapshot()]
    for step in case["steps"]:
        if step[0] == "resize":
            window.place(**{along: step[1]})
        elif step[0] == "size":
            window.paneconfigure(children[step[1]], **{along: step[2]})
        elif step[0] == "stretch":
            window.paneconfigure(children[step[1]], stretch=step[2])
        else:
            at = (0, step[2]) if vertical else (step[2], 0)
            window.sash_place(step[1], *at)
        record.append(snapshot())
    return record


def test_the_reference_was_recorded_from_tk_9():
    assert REFERENCE["tk"].startswith("9.")
    assert len(REFERENCE["cases"]) == 200


@pytest.mark.parametrize("number", range(len(REFERENCE["cases"])))
def test_a_paned_window_lays_out_as_tk_does(number):
    case = REFERENCE["cases"][number]
    assert replay(case) == case["tk"], json.dumps(case)


def two_panes(length=60):
    """The issue's measurement in cells: panes asking 5, minsizes 12 and 20."""
    root, window = make(length=length)
    a, b = Box(window, 5, 3), Box(window, 5, 3)
    window.add(a, minsize=12)
    window.add(b, minsize=20)
    root.update_layout()
    return root, window, a, b


def widths(root, a, b):
    root.update_layout()
    return a.winfo_width(), b.winfo_width()


def test_the_last_pane_takes_the_spare_room():
    # Tk 9.0: 120 and 475 in a 600-pixel window.
    root, _window, a, b = two_panes()
    assert widths(root, a, b) == (12, 47)


def test_growth_goes_to_the_last_pane():
    root, window, a, b = two_panes()
    window.place(width=80)
    assert widths(root, a, b) == (12, 67)


def test_a_pane_width_is_kept_through_a_resize():
    root, window, a, b = two_panes()
    window.paneconfigure(a, width=18)
    assert widths(root, a, b) == (18, 41)
    window.place(width=90)
    assert widths(root, a, b) == (18, 71)


def test_stretch_always_shares_by_size():
    root, window, a, b = two_panes()
    window.paneconfigure(a, stretch="always")
    window.paneconfigure(b, stretch="always")
    # 12 and 20 share 27 spare cells in proportion, the remainder to the last.
    assert widths(root, a, b) == (22, 37)


def test_a_placed_sash_survives_a_resize():
    root, window, a, b = two_panes()
    window.sash_place(0, 30, 0)
    assert widths(root, a, b) == (30, 29)
    window.place(width=80)
    assert widths(root, a, b) == (30, 49)
    assert window.panecget(a, "width") == 30


def test_stretch_reads_back_and_refuses_what_tk_refuses():
    _root, window, a, _b = two_panes()
    assert window.panecget(a, "stretch") == "last"
    window.paneconfigure(a, stretch="middle")
    assert window.panecget(a, "stretch") == "middle"
    with pytest.raises(TclError, match='bad stretch "sideways"'):
        window.paneconfigure(a, stretch="sideways")
