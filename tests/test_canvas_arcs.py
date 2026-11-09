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

"""Canvas arcs: the rasteriser's invariants and the item's Tk options.

The options were measured on Tk 9.0.2 through tkinter. Tk's extents carry a
pixel of outline on each side that ours do not, so its numbers are quoted
less that margin.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses import Canvas, Misc, TclError
from tkcurses._core.canvas import (
    arc_curve_pixels,
    arc_outline_pixels,
    filled_arc_pixels,
)
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


def connected(pixels):
    """Whether a set of pixels is one piece, touching at edges or corners."""
    remaining = set(pixels)
    if not remaining:
        return True
    stack = [remaining.pop()]
    while stack:
        x, y = stack.pop()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                near = (x + dx, y + dy)
                if near in remaining:
                    remaining.remove(near)
                    stack.append(near)
    return not remaining


boxes = st.tuples(
    st.integers(0, 40), st.integers(0, 40), st.integers(2, 60), st.integers(2, 60)
).map(lambda b: (b[0], b[1], b[0] + b[2], b[1] + b[3]))
angles = st.floats(0, 359.9, allow_nan=False)
extents = st.floats(-359.9, 359.9, allow_nan=False).filter(lambda e: abs(e) > 0.5)


@given(boxes, angles, extents)
def test_an_arc_is_connected_and_inside_its_box(box, start, extent):
    curve = arc_curve_pixels(*box, start, extent)
    assert connected(curve)
    for x, y in curve:
        assert box[0] <= x <= box[2]
        assert box[1] <= y <= box[3]


@given(boxes, angles, extents, st.sampled_from(["pieslice", "chord", "arc"]))
def test_every_outline_is_one_piece(box, start, extent, style):
    assert connected(arc_outline_pixels(*box, start, extent, style))


@given(boxes, angles, extents)
def test_a_pieslice_is_filled_and_holds_its_outline(box, start, extent):
    filled = set(filled_arc_pixels(*box, start, extent, "pieslice"))
    outline = set(arc_outline_pixels(*box, start, extent, "pieslice"))
    assert outline <= filled
    assert connected(filled)


def test_a_quarter_from_three_oclock_is_the_upper_right():
    """Angles go counter-clockwise on the screen, where y runs down."""
    pixels = filled_arc_pixels(0, 0, 20, 20, 0, 90, "pieslice")
    assert all(x >= 10 and y <= 10 for x, y in pixels)
    assert (15, 5) in pixels


def test_a_chord_fills_only_the_side_the_curve_is_on():
    pixels = set(filled_arc_pixels(0, 0, 20, 20, 0, 180, "chord"))
    assert (10, 5) in pixels
    assert (10, 15) not in pixels


def test_a_chord_over_half_includes_the_centre():
    assert (10, 10) in set(filled_arc_pixels(0, 0, 20, 20, 0, 270, "chord"))
    assert (10, 10) not in set(filled_arc_pixels(0, 0, 20, 20, 0, 60, "chord"))


def test_an_arc_style_is_never_filled():
    assert filled_arc_pixels(0, 0, 20, 20, 0, 90, "arc") == []


# ---------------------------------------------------------------- the item


@pytest.fixture
def canvas():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    widget = Canvas(root, name="c", width=40, height=10, relief="flat")
    widget._allocate(Rect(0, 0, 40, 10))
    widget._map()
    return widget


def test_an_arcs_defaults_are_tks(canvas):
    arc = canvas.create_arc(10, 10, 50, 50)
    assert canvas.itemcget(arc, "start") == 0.0
    assert canvas.itemcget(arc, "extent") == 90.0
    assert canvas.itemcget(arc, "style") == "pieslice"
    assert canvas.type(arc) == "arc"


@pytest.mark.parametrize(
    ("given", "start", "extent", "style", "box"),
    [
        ({}, 0.0, 90.0, "pieslice", (30, 10, 50, 30)),
        ({"extent": 400}, 0.0, 40.0, "pieslice", (30, 17, 50, 30)),
        ({"extent": -400}, 0.0, -40.0, "pieslice", (30, 30, 50, 43)),
        ({"extent": 360}, 0.0, 0.0, "pieslice", None),
        ({"start": -30}, 330.0, 90.0, "pieslice", (30, 13, 50, 40)),
        ({"start": 370}, 10.0, 90.0, "pieslice", None),
        ({"style": "ch"}, 0.0, 90.0, "chord", (30, 10, 50, 30)),
    ],
)
def test_angles_read_back_as_tk_reads_them(canvas, given, start, extent, style, box):
    arc = canvas.create_arc(10, 10, 50, 50, **given)
    assert canvas.itemcget(arc, "start") == start
    assert canvas.itemcget(arc, "extent") == extent
    assert canvas.itemcget(arc, "style") == style
    if box is not None:
        assert canvas.bbox(arc) == box


def test_a_bad_style_is_refused_in_tks_words(canvas):
    with pytest.raises(
        TclError,
        match=re.escape('bad -style option "bogus": must be arc, chord, or pieslice'),
    ):
        canvas.create_arc(10, 10, 50, 50, style="bogus")


def test_a_bad_angle_is_refused(canvas):
    with pytest.raises(TclError, match='expected floating-point number but got "x"'):
        canvas.create_arc(10, 10, 50, 50, start="x")


def test_an_arc_needs_two_corners(canvas):
    with pytest.raises(TclError, match="wrong # coordinates"):
        canvas.create_arc(10, 10, 50)


def test_an_arc_takes_no_option_tk_does_not_give_it(canvas):
    with pytest.raises(TclError, match='unknown option "-text"'):
        canvas.create_arc(10, 10, 50, 50, text="x")


def test_itemconfigure_reshapes_an_arc(canvas):
    arc = canvas.create_arc(10, 10, 50, 50)
    canvas.itemconfigure(arc, start=90, extent=-90)
    assert canvas.bbox(arc) == (30, 10, 50, 30)


def test_a_click_on_a_pieslice_finds_it(canvas):
    arc = canvas.create_arc(0, 0, 20, 20, fill="red")
    assert canvas.find_closest(15, 5) == (arc,)
    assert canvas.find_overlapping(14, 4, 16, 6) == (arc,)
