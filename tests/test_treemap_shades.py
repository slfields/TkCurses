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

"""The treemap's shades and outlines."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tkcurses._charts.color import mix
from tkcurses._charts.geometry import Rect
from tkcurses.treemap._layout import lay_out
from tkcurses.treemap._model import Model
from tkcurses.treemap._outline import inner, lines, shrunk
from tkcurses.treemap._shades import adjacent, assign, outlined_levels, shades_of
from tkcurses.treemap._squarify import tiles


def test_mix():
    assert mix((200, 100, 0), (0, 0, 0), 0.25) == (150, 75, 0)
    assert mix((0, 0, 0), (255, 255, 255), 0.30) == (76, 76, 76)


def test_the_four_shades():
    assert shades_of((200, 0, 100)) == (
        (200, 0, 100),
        (150, 0, 75),
        (216, 76, 146),
        (100, 0, 50),
    )


def test_adjacent_means_sharing_an_edge_not_a_corner():
    rects = [Rect(0, 0, 2, 2), Rect(2, 0, 2, 2), Rect(2, 2, 2, 2), Rect(0, 4, 4, 1)]
    assert adjacent(rects) == [{1}, {0, 2}, {1, 3}, {2}]


def test_neighbours_take_different_shades():
    rects = [Rect(0, 0, 2, 4), Rect(2, 0, 2, 2), Rect(2, 2, 2, 2)]
    assert assign(rects) == [0, 1, 2]


def test_a_tile_no_neighbour_shares_with_reuses_the_lowest():
    rects = [Rect(0, 0, 2, 2), Rect(2, 0, 2, 2), Rect(4, 0, 2, 2)]
    assert assign(rects) == [0, 1, 0]


def test_with_every_shade_taken_the_smallest_neighbours_is_reused():
    """With two shades, a tile touching both others has none left, and
    takes the shade of the smaller."""
    big, small, below = Rect(0, 0, 2, 2), Rect(2, 0, 1, 2), Rect(0, 2, 3, 1)
    assert assign([big, small, below], count=2) == [0, 1, 1]
    assert assign([big, small, below], count=3) == [0, 1, 2]


weights = st.lists(st.integers(1, 1000), min_size=1, max_size=14).map(
    lambda ws: sorted(ws, reverse=True)
)


@given(weights, st.integers(4, 80), st.integers(2, 30))
def test_neighbours_never_share_a_shade(ws, width, height):
    """Four shades are always enough for tiles that meet at edges."""
    rects = [r for r in tiles(ws, Rect(0, 0, width, height)) if r and not r.empty]
    shades = assign(rects)
    for i, neighbours in enumerate(adjacent(rects)):
        assert all(shades[i] != shades[j] for j in neighbours)


def test_a_tile_the_lowest_free_shade_would_corner_still_gets_its_own():
    """Found by Hypothesis: taking the lowest free shade, the tile at
    (35, 14) met all four among its neighbours and shared one with the tile
    left of it. Backtracking gives the earlier tile another."""
    ws = sorted([152, 183, 149, 100, 1, 94, 155, 103, 94, 43, 544], reverse=True)
    rects = [r for r in tiles(ws, Rect(0, 0, 46, 23)) if r and not r.empty]
    shades = assign(rects)
    for i, neighbours in enumerate(adjacent(rects)):
        assert all(shades[i] != shades[j] for j in neighbours)


@settings(max_examples=300, deadline=None)
@given(
    st.lists(st.integers(1, 1000), min_size=1, max_size=60).map(
        lambda ws: sorted(ws, reverse=True)
    ),
    st.integers(4, 200),
    st.integers(2, 60),
)
def test_many_tiles_still_never_share_a_shade(ws, width, height):
    rects = [r for r in tiles(ws, Rect(0, 0, width, height)) if r and not r.empty]
    shades = assign(rects)
    for i, neighbours in enumerate(adjacent(rects)):
        assert all(shades[i] != shades[j] for j in neighbours)


# ---------------------------------------------------------------- outlines

GROUPS = {"web": 3, "db": 2}


def test_off_outlines_nothing_and_on_everything():
    assert outlined_levels("off", 0, GROUPS, {}) == frozenset()
    assert outlined_levels("on", 1 << 24, GROUPS, {}) == {"", "web", "db"}


def test_auto_outlines_everything_without_colour():
    assert outlined_levels("auto", 0, GROUPS, {}) == {"", "web", "db"}


def test_auto_outlines_the_groups_below_256_colours():
    assert outlined_levels("auto", 16, GROUPS, {"web": 4, "db": 4}) == {"web", "db"}


def test_auto_outlines_a_group_whose_shades_the_palette_merged():
    assert outlined_levels("auto", 256, GROUPS, {"web": 2, "db": 2}) == {"web"}
    assert outlined_levels("auto", 256, GROUPS, {"web": 1, "db": 2}) == {"web"}
    assert outlined_levels("auto", 256, GROUPS, {"web": 1, "db": 1}) == {
        "web",
        "db",
    }
    assert outlined_levels("auto", 1 << 24, GROUPS, {"web": 4, "db": 4}) == set()


def test_junctions_come_from_the_directions_that_meet():
    drawn = lines([Rect(0, 0, 3, 2), Rect(3, 0, 2, 1), Rect(3, 1, 2, 1)])
    rows = ["".join(drawn.get((x, y), " ") for x in range(6)) for y in range(3)]
    assert rows == ["┌──┬─┐", "│  ├─┤", "└──┴─┘"]


def test_shrunk_and_inner():
    assert shrunk(Rect(2, 3, 10, 5)) == Rect(2, 3, 9, 4)
    assert inner(Rect(2, 3, 10, 5)) == Rect(3, 4, 9, 4)
    assert inner(Rect(0, 0, 1, 1)).empty


trees = st.lists(
    st.tuples(st.integers(1, 500), st.lists(st.integers(1, 500), max_size=4)),
    min_size=1,
    max_size=6,
)


@given(trees, st.integers(2, 70), st.integers(2, 25), st.booleans())
def test_every_outlined_cell_is_a_line_a_header_or_inside_one_tile(
    tree, width, height, top_too
):
    model = Model()
    for own, children in tree:
        group = model.insert("", "end", value=own)
        for value in children:
            model.insert(group, "end", value=value)
    groups = {iid for iid in model.get_children() if model.get_children(iid)}
    outlined = frozenset(groups | ({""} if top_too else set()))
    area = Rect(0, 0, width, height)
    layout = lay_out(model, area, outlined=outlined)
    owner = {}

    def claim(rect, what):
        for y in range(rect.y, rect.y + rect.height):
            for x in range(rect.x, rect.x + rect.width):
                assert (x, y) not in owner, (what, owner.get((x, y)))
                owner[x, y] = what

    for cell in lines(tile.rect for tile in layout.tiles if tile.boxed):
        assert cell not in owner
        owner[cell] = "line"
    for tile in layout.tiles:
        if tile.header:
            claim(tile.header, ("header", tile.iid))
        if not tile.group:
            claim(inner(tile.rect) if tile.boxed else tile.rect, tile.iid)
    inside = {(x, y) for x in range(width) for y in range(height)}
    assert set(owner) <= inside
    # What is left is a group's own tile, which is drawn in its colour
    # before its children: a group too small for its children's lines
    # has them hidden, and shows as itself.
    groups_area = set()
    for tile in layout.tiles:
        if tile.group:
            rect = tile.rect
            groups_area |= {
                (x, y)
                for x in range(rect.x, rect.x + rect.width)
                for y in range(rect.y, rect.y + rect.height)
            }
    assert inside - set(owner) <= groups_area


def test_an_outlined_treemap_looks_like_this():
    model = Model()
    model.insert("", "end", "web")
    for name, value in (("nginx", 330), ("apache", 170), ("php", 50)):
        model.insert("web", "end", name, value=value)
    model.insert("", "end", "db")
    for name, value in (("postgres", 140), ("mysql", 60)):
        model.insert("db", "end", name, value=value)
    model.insert("", "end", "cache", value=100)
    layout = lay_out(model, Rect(0, 0, 49, 10), outlined=frozenset({"", "web", "db"}))
    screen = [[" "] * 49 for _ in range(10)]
    for (x, y), glyph in lines(tile.rect for tile in layout.tiles).items():
        screen[y][x] = glyph
    for tile in layout.tiles:
        where = tile.header if tile.group else inner(tile.rect)
        for i, char in enumerate(tile.iid[: where.width]):
            screen[where.y][where.x + i] = char
    assert ["".join(row) for row in screen] == [
        "┌──────────────────────────────┬────────────────┐",
        "│web                           │db              │",
        "├──────────────────┬───────────┼───────────┬────┤",
        "│nginx             │apache     │postgres   │mysq│",
        "│                  │           │           │    │",
        "│                  │           │           │    │",
        "│                  │           ├───────────┴────┤",
        "│                  ├───────────┤cache           │",
        "│                  │php        │                │",
        "└──────────────────┴───────────┴────────────────┘",
    ]
