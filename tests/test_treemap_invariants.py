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

"""What holds for every treemap, whatever its items and size; and the
size a treemap asks for.

The layout's own properties - squarify covering its area once, each edge
within half a cell - are in ``test_treemap_layout.py``. These are the
whole widget's: groups, headers and children together, the legend beside
them, the colours and the focus drawn over them.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import tkcurses as tk
from tkcurses._charts.geometry import Rect
from tkcurses.treemap import NATURAL_SIZE, TreeMap
from tkcurses.treemap._compose import Scene, compose
from tkcurses.treemap._layout import lay_out, regions
from tkcurses.treemap._model import Model

# -------------------------------------------------------------- strategies

#: An item: a leaf's value, or a group's children's values.
items = st.one_of(
    st.integers(0, 1000),
    st.lists(st.integers(0, 1000), min_size=1, max_size=5),
)
trees = st.lists(items, min_size=1, max_size=7)


def build(tree):
    """A Model of ``tree``: ``g3`` a group, ``g3c1`` its child, ``g4`` a leaf."""
    model = Model()
    for number, entry in enumerate(tree):
        iid = f"g{number}"
        if isinstance(entry, list):
            model.insert("", "end", iid, text=iid)
            for child, value in enumerate(entry):
                model.insert(
                    iid, "end", f"{iid}c{child}", text=f"c{child}", value=value
                )
        else:
            model.insert("", "end", iid, text=iid, value=entry)
    return model


def cells_of(rect):
    return {
        (x, y)
        for y in range(rect.y, rect.y + rect.height)
        for x in range(rect.x, rect.x + rect.width)
    }


def disjoint_union(rects):
    """The cells of ``rects``, asserting no cell is in two."""
    union = set()
    for rect in rects:
        mine = cells_of(rect)
        assert not union & mine
        union |= mine
    return union


areas = st.builds(Rect, st.just(0), st.just(0), st.integers(1, 70), st.integers(1, 30))


# ----------------------------------------------------------------- layout


@given(trees, areas)
def test_the_top_level_tiles_the_area_exactly(tree, area):
    model = build(tree)
    layout = lay_out(model, area)
    top = [t.rect for t in layout.tiles if t.level == 0]
    covered = disjoint_union(top)
    if model.total() > 0:
        assert covered == cells_of(area)
    else:
        assert covered == set()


@given(trees, areas)
def test_a_groups_children_tile_what_its_header_leaves(tree, area):
    model = build(tree)
    layout = lay_out(model, area)
    for group in (t for t in layout.tiles if t.group):
        space = group.rect.take_top(1)[1] if group.header else group.rect
        if group.header is not None:
            assert group.header == Rect(group.rect.x, group.rect.y, group.rect.width, 1)
        children = [t.rect for t in layout.tiles if model.parent(t.iid) == group.iid]
        assert disjoint_union(children) == cells_of(space)


@given(trees, areas)
def test_every_item_with_a_size_has_a_tile_or_is_counted_hidden(tree, area):
    model = build(tree)
    layout = lay_out(model, area)
    placed = {t.iid for t in layout.tiles}
    hidden = set(layout.hidden)
    assert not placed & hidden
    sized = set()
    for iid in model.get_children():
        if model.size(iid) > 0:
            sized.add(iid)
            sized.update(c for c in model.get_children(iid) if model.size(c) > 0)
    assert placed | hidden == sized


@given(trees, areas)
def test_children_nest_in_their_groups_tile(tree, area):
    model = build(tree)
    layout = lay_out(model, area)
    for tile in layout.tiles:
        if tile.level == 1:
            group = layout.tile(model.parent(tile.iid))
            assert group is not None
            assert cells_of(tile.rect) <= cells_of(group.rect)


@given(trees, areas)
def test_tiles_are_laid_largest_first(tree, area):
    model = build(tree)
    layout = lay_out(model, area)
    top = [t.iid for t in layout.tiles if t.level == 0]
    expected = [iid for iid in model.ordered() if iid in top]
    assert top == expected


@given(trees, areas)
def test_each_tiles_area_is_within_a_row_and_a_column_of_its_share(tree, area):
    """Each edge is within half a cell of exact, so width and height are each
    within one: the area is off by at most a row, a column and their corner."""
    model = build(tree)
    layout = lay_out(model, area)
    total = model.total()
    if total <= 0:
        return
    whole = area.width * area.height
    for tile in (t for t in layout.tiles if t.level == 0):
        rect = tile.rect
        share = model.size(tile.iid) / total * whole
        assert abs(rect.width * rect.height - share) <= rect.width + rect.height + 1


# --------------------------------------------------------------- drawing


PALETTE = (("green", (0, 205, 0)), ("red", (205, 0, 0)), ("blue", (0, 0, 238)))


@given(trees, areas)
def test_each_tile_is_one_colour_throughout_its_text_included(tree, area):
    """A label that ran past its tile would carry its own tile's colour into
    the next one."""
    model = build(tree)
    cut = regions(area, readout=False)
    layout = lay_out(model, cut.tiles)
    grid = compose(
        Scene(
            area.width,
            area.height,
            cut,
            layout,
            model,
            colors=PALETTE,
            value_text=lambda iid: f"{model.size(iid):g}",
        )
    )
    for tile in layout.tiles:
        if tile.group:
            if tile.header is not None:
                assert len({grid[y][x].bg for x, y in cells_of(tile.header)}) == 1
            continue
        assert len({grid[y][x].bg for x, y in cells_of(tile.rect)}) == 1


# ---------------------------------------------------------------- widget


@pytest.fixture(scope="module")
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


def overlaps(a, b):
    return bool(cells_of(a) & cells_of(b))


@settings(max_examples=60, deadline=None)
@given(
    trees,
    st.integers(1, 70),
    st.integers(1, 30),
    st.sampled_from(["right", "left", "top", "bottom"]),
    st.sampled_from(["auto", "small", "medium", "large", "xlarge"]),
    st.booleans(),
    st.integers(1, 5),
    st.booleans(),
)
def test_the_legend_never_overlaps_the_tiles_or_the_readout(
    root, tree, width, height, position, size, nested, lines, readout
):
    widget = TreeMap(
        root,
        legend="show",
        legendposition=position,
        legendsize=size,
        nestedlegend=nested,
        legendlines=lines,
        readout=readout,
    )
    try:
        for number, entry in enumerate(tree):
            iid = widget.insert("", "end", f"g{number}", text=f"group {number}")
            if isinstance(entry, list):
                for value in entry:
                    widget.insert(iid, "end", text="a child", value=value)
            else:
                widget.item(iid, value=entry)
        widget._allocate(Rect(0, 0, width, height))
        widget._map()
        scene = widget._scene_now()
        cut = scene.regions
        whole = cells_of(Rect(0, 0, width, height))
        assert cells_of(cut.tiles) <= whole
        if cut.legend is None:
            return
        assert cells_of(cut.legend) <= whole
        assert not overlaps(cut.legend, cut.tiles)
        if cut.readout is not None:
            assert not overlaps(cut.legend, cut.readout)
        for tile in scene.layout.tiles:
            assert not overlaps(tile.rect, cut.legend)
        inside = cells_of(cut.legend) - cells_of(scene.legend.edge)
        for entry in scene.legend.placed:
            assert cells_of(entry.rect) <= inside
    finally:
        widget.destroy()


@settings(max_examples=40, deadline=None)
@given(trees, st.integers(0, 40), st.booleans())
def test_only_the_focused_item_is_reversed(root, tree, pick, legend):
    widget = TreeMap(root, legend="show" if legend else "hide")
    try:
        for number, entry in enumerate(tree):
            iid = widget.insert("", "end", f"g{number}", text=f"g{number}")
            if isinstance(entry, list):
                for value in entry:
                    widget.insert(iid, "end", text="c", value=value)
            else:
                widget.item(iid, value=entry)
        widget._allocate(Rect(0, 0, 50, 14))
        widget._map()
        widget.focus_set()
        every = [i for g in widget.get_children() for i in (g, *widget.get_children(g))]
        focused = every[pick % len(every)]
        widget.focus(focused)
        scene = widget._scene_now()
        allowed = set()
        tile = scene.layout.tile(focused)
        if tile is not None:
            allowed |= cells_of(tile.rect)
        if scene.legend is not None:
            for entry in scene.legend.placed:
                if entry.iid == focused:
                    allowed |= cells_of(entry.text_rect)
        grid = widget._compose(50, 14)
        reversed_cells = {
            (x, y)
            for y, row in enumerate(grid)
            for x, cell in enumerate(row)
            if cell.reverse
        }
        assert reversed_cells <= allowed
    finally:
        widget.destroy()


# ------------------------------------------------------------------ size


SCREEN = (80, 24)


@pytest.fixture
def screen(monkeypatch):
    """An 80 by 24 terminal, resized by assigning to ``screen[0]``."""
    size = [SCREEN]
    monkeypatch.setattr(tk.Misc, "_screen_size", lambda self: size[0])
    return size


@pytest.fixture
def make(root):
    """TreeMaps on the shared root, destroyed after the test."""
    made = []

    def treemap(**options):
        widget = TreeMap(root, **options)
        made.append(widget)
        return widget

    yield treemap
    for widget in made:
        widget.destroy()


def pair(size):
    return (size.width, size.height)


def resize(root, screen, width, height):
    screen[0] = (width, height)
    root.event_generate("<Configure>", width=width, height=height)


@pytest.mark.parametrize(
    ("options", "requested"),
    [
        ({}, NATURAL_SIZE),
        ({"width": 30}, (30, NATURAL_SIZE[1])),
        ({"height": 5}, (NATURAL_SIZE[0], 5)),
        ({"width": 30, "height": 5}, (30, 5)),
        ({"width": "50%"}, (40, NATURAL_SIZE[1])),
        ({"height": "50%"}, (NATURAL_SIZE[0], 12)),
        ({"width": "25%", "height": 8}, (20, 8)),
        ({"width": 20, "height": "25%"}, (20, 6)),
        ({"width": "100%", "height": "100%"}, (80, 24)),
        ({"width": "0.1%"}, (1, NATURAL_SIZE[1])),
        ({"width": "2c"}, (8, NATURAL_SIZE[1])),
    ],
)
def test_each_axis_is_cells_or_a_share_of_the_screen(screen, make, options, requested):
    assert pair(make(**options)._requested) == requested


cells_or_share = st.one_of(
    st.integers(1, 200), st.integers(1, 100).map(lambda p: f"{p}%")
)


@settings(deadline=None)
@given(cells_or_share, cells_or_share)
def test_the_axes_are_independent(root, width, height):
    """Whatever one axis is given, the other asks for what it alone says."""
    screen_width, screen_height = root._screen_size()

    def expected(value, screen):
        if isinstance(value, str):
            return max(1, round(screen * int(value[:-1]) / 100))
        return value

    made = [
        TreeMap(root, width=width, height=height),
        TreeMap(root, width=width),
        TreeMap(root, height=height),
    ]
    try:
        both, wide, tall = (widget._requested for widget in made)
        assert pair(both) == (
            expected(width, screen_width),
            expected(height, screen_height),
        )
        assert wide.height == NATURAL_SIZE[1]
        assert tall.width == NATURAL_SIZE[0]
    finally:
        for widget in made:
            widget.destroy()


def test_a_percentage_reads_back_as_written(screen, make):
    widget = make(width="50.0%", height=" 25% ")
    assert widget.cget("width") == "50%"
    assert widget.cget("height") == "25%"


@pytest.mark.parametrize("bad", ["0%", "-5%", "101%", "x%", "nan%", "%"])
def test_a_bad_percentage_is_refused(screen, make, bad):
    with pytest.raises(tk.TclError, match="percentage"):
        make(width=bad)
    widget = make(height=5)
    with pytest.raises(tk.TclError, match="percentage"):
        widget.configure(height=bad)
    assert widget.cget("height") == 5


def test_a_share_of_the_screen_follows_a_resize(root, screen, make):
    widget = make(width="50%", height=6)
    resize(root, screen, 100, 30)
    assert pair(widget._requested) == (50, 6)


def test_cells_again_stop_following_the_screen(root, screen, make):
    widget = make(width="50%")
    assert widget._size.binding is not None
    widget.configure(width=30)
    assert widget._size.binding is None
    resize(root, screen, 100, 30)
    assert pair(widget._requested) == (30, NATURAL_SIZE[1])


def test_destroying_it_stops_following_the_screen(root, screen):
    widget = TreeMap(root, width="50%")
    widget.destroy()
    assert widget._size.binding is None
    resize(root, screen, 100, 30)  # nothing raised


def test_another_widgets_configure_is_not_a_resize(root, screen, make):
    widget = make(width="50%")
    other = tk.Frame(root)
    try:
        screen[0] = (100, 30)
        other.event_generate("<Configure>", width=5, height=5)
        assert pair(widget._requested) == (40, NATURAL_SIZE[1])
    finally:
        other.destroy()
