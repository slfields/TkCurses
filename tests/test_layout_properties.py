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

"""Invariants every layout must satisfy, over trees Hypothesis invents.

These are the geometry epic's acceptance. There is nothing for a person to
look at - a manager places widgets that cannot yet draw themselves - so what
stands in for a UAT is a set of properties that must hold for any tree, any
options and any terminal size.

They are also the check the worked examples cannot be: both mistakes made
while writing the pack and grid tests were wrong *expectations*, arrived at by
computing a coordinate by hand. A property does not have that failure mode -
it says what must be true of every layout rather than what one layout happens
to produce.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tkcurses import Misc, Widget
from tkcurses._core.geometry import Rect, Size

# Trees are built inside each test, so no fixture is shared across examples.
LAYOUT = settings(
    max_examples=120,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

sizes = st.integers(min_value=0, max_value=30)
pads = st.integers(min_value=0, max_value=4)
screen = st.integers(min_value=1, max_value=60)

pack_specs = st.fixed_dictionaries(
    {
        "side": st.sampled_from(["top", "bottom", "left", "right"]),
        "fill": st.sampled_from(["none", "x", "y", "both"]),
        "expand": st.booleans(),
        "anchor": st.sampled_from(
            ["nw", "n", "ne", "w", "center", "e", "sw", "s", "se"]
        ),
        "padx": pads,
        "pady": pads,
        "ipadx": pads,
        "ipady": pads,
    }
)

grid_specs = st.fixed_dictionaries(
    {
        "sticky": st.sampled_from(["", "n", "s", "e", "w", "ew", "ns", "nsew"]),
        "padx": pads,
        "pady": pads,
        "weight": st.integers(min_value=0, max_value=3),
    }
)


def make_root(width: int, height: int) -> Misc:
    """A container of a given size, with no curses behind it."""
    root = Misc()
    root._rect = Rect(0, 0, width, height)
    root._mapped = True
    return root


def add_child(root: Misc, index: int, width: int, height: int) -> Widget:
    """A child that asks for a given size."""
    child = Widget(root, name=f"w{index}")
    child._requested = Size(width, height)
    return child


def rect_of(widget: Widget) -> Rect:
    """A widget's region in screen cells."""
    return Rect(
        widget.winfo_rootx(),
        widget.winfo_rooty(),
        widget.winfo_width(),
        widget.winfo_height(),
    )


def overlaps(first: Rect, second: Rect) -> bool:
    """True if two non-empty regions share a cell."""
    if first.is_empty or second.is_empty:
        return False
    return first.intersects(second)


# ------------------------------------------------------------------- pack


@given(
    width=screen,
    height=screen,
    children=st.lists(st.tuples(sizes, sizes, pack_specs), min_size=1, max_size=6),
)
@LAYOUT
def test_packed_children_never_overlap(width, height, children):
    root = make_root(width, height)
    packed = []
    for index, (child_width, child_height, spec) in enumerate(children):
        child = add_child(root, index, child_width, child_height)
        child.pack(**spec)
        packed.append(child)
    root.update_layout()

    rects = [rect_of(child) for child in packed]
    for i, first in enumerate(rects):
        for second in rects[i + 1 :]:
            assert not overlaps(first, second), f"{first} overlaps {second}"


@given(
    width=screen,
    height=screen,
    children=st.lists(st.tuples(sizes, sizes, pack_specs), min_size=1, max_size=6),
)
@LAYOUT
def test_packed_children_stay_inside_the_container(width, height, children):
    root = make_root(width, height)
    packed = []
    for index, (child_width, child_height, spec) in enumerate(children):
        child = add_child(root, index, child_width, child_height)
        child.pack(**spec)
        packed.append(child)
    root.update_layout()

    area = root._content_rect()
    for child in packed:
        rect = rect_of(child)
        if rect.is_empty:
            continue
        assert area.contains(rect), f"{child} at {rect} escapes {area}"


@given(
    width=screen,
    height=screen,
    children=st.lists(st.tuples(sizes, sizes, pack_specs), min_size=1, max_size=6),
)
@LAYOUT
def test_no_packed_child_gets_a_negative_size(width, height, children):
    root = make_root(width, height)
    packed = []
    for index, (child_width, child_height, spec) in enumerate(children):
        child = add_child(root, index, child_width, child_height)
        child.pack(**spec)
        packed.append(child)
    root.update_layout()

    for child in packed:
        assert child.winfo_width() >= 0
        assert child.winfo_height() >= 0


@given(
    width=screen,
    height=screen,
    children=st.lists(st.tuples(sizes, sizes, pack_specs), min_size=1, max_size=5),
)
@LAYOUT
def test_packing_is_idempotent(width, height, children):
    """Laying out twice changes nothing: the second run has nothing to do."""
    root = make_root(width, height)
    packed = []
    for index, (child_width, child_height, spec) in enumerate(children):
        child = add_child(root, index, child_width, child_height)
        child.pack(**spec)
        packed.append(child)
    root.update_layout()
    before = [rect_of(child) for child in packed]

    root._invalidate_layout()
    root.update_layout()
    assert [rect_of(child) for child in packed] == before


@given(
    width=screen,
    height=screen,
    other=screen,
    children=st.lists(st.tuples(sizes, sizes, pack_specs), min_size=1, max_size=4),
)
@LAYOUT
def test_a_layout_survives_a_resize_and_back(width, height, other, children):
    root = make_root(width, height)
    packed = []
    for index, (child_width, child_height, spec) in enumerate(children):
        child = add_child(root, index, child_width, child_height)
        child.pack(**spec)
        packed.append(child)
    root.update_layout()
    before = [rect_of(child) for child in packed]

    root._rect = Rect(0, 0, other, other)
    root._invalidate_layout()
    root.update_layout()
    root._rect = Rect(0, 0, width, height)
    root._invalidate_layout()
    root.update_layout()
    assert [rect_of(child) for child in packed] == before


@given(
    width=screen,
    height=st.integers(min_value=1, max_value=40),
    counts=st.integers(min_value=1, max_value=5),
)
@LAYOUT
def test_expanding_children_use_the_whole_cavity(width, height, counts):
    """With every child expanding and filling, the parcels tile the space."""
    root = make_root(width, height)
    packed = []
    for index in range(counts):
        child = add_child(root, index, 1, 1)
        child.pack(side="top", expand=True, fill="both")
        packed.append(child)
    root.update_layout()

    total = sum(child.winfo_height() for child in packed)
    assert total == root._content_rect().height


# ------------------------------------------------------------------- grid


@given(
    width=screen,
    height=screen,
    cells=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=3),
            st.integers(min_value=0, max_value=3),
            sizes,
            sizes,
            grid_specs,
        ),
        min_size=1,
        max_size=6,
        unique_by=lambda item: (item[0], item[1]),
    ),
)
@LAYOUT
def test_gridded_children_never_overlap(width, height, cells):
    root = make_root(width, height)
    gridded = []
    for index, (row, column, child_width, child_height, spec) in enumerate(cells):
        weight = spec.pop("weight")
        child = add_child(root, index, child_width, child_height)
        child.grid(row=row, column=column, **spec)
        root.grid_rowconfigure(row, weight=weight)
        root.grid_columnconfigure(column, weight=weight)
        gridded.append(child)
    root.update_layout()

    rects = [rect_of(child) for child in gridded]
    for i, first in enumerate(rects):
        for second in rects[i + 1 :]:
            assert not overlaps(first, second), f"{first} overlaps {second}"


@given(
    width=screen,
    height=screen,
    cells=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=3),
            st.integers(min_value=0, max_value=3),
            sizes,
            sizes,
            grid_specs,
        ),
        min_size=1,
        max_size=6,
        unique_by=lambda item: (item[0], item[1]),
    ),
)
@LAYOUT
def test_no_gridded_child_gets_a_negative_size(width, height, cells):
    root = make_root(width, height)
    gridded = []
    for index, (row, column, child_width, child_height, spec) in enumerate(cells):
        spec.pop("weight")
        child = add_child(root, index, child_width, child_height)
        child.grid(row=row, column=column, **spec)
        gridded.append(child)
    root.update_layout()

    for child in gridded:
        assert child.winfo_width() >= 0
        assert child.winfo_height() >= 0


@given(
    width=screen,
    height=screen,
    cells=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=3),
            st.integers(min_value=0, max_value=3),
            sizes,
            sizes,
            grid_specs,
        ),
        min_size=1,
        max_size=5,
        unique_by=lambda item: (item[0], item[1]),
    ),
)
@LAYOUT
def test_gridding_is_idempotent(width, height, cells):
    root = make_root(width, height)
    gridded = []
    for index, (row, column, child_width, child_height, spec) in enumerate(cells):
        spec.pop("weight")
        child = add_child(root, index, child_width, child_height)
        child.grid(row=row, column=column, **spec)
        gridded.append(child)
    root.update_layout()
    before = [rect_of(child) for child in gridded]

    root._invalidate_layout()
    root.update_layout()
    assert [rect_of(child) for child in gridded] == before


# ------------------------------------------------------------------ engine


@given(
    depth=st.integers(min_value=1, max_value=12),
    width=screen,
    height=screen,
)
@LAYOUT
def test_a_nested_tree_always_settles(depth, width, height):
    """However deep the nesting, propagation reaches a fixed point."""
    root = make_root(width, height)
    parent = root
    for level in range(depth):
        child = Widget(parent, name=f"level{level}")
        child._requested = Size(3, 1)
        child.pack(side="top", fill="both")
        parent = child
    assert root.update_layout() >= 1
    assert root.tk.layout.pending == 0
