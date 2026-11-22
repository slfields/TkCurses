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

"""The treemap's layout: squarified, snapped to cells, cut into regions."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses._charts.geometry import Rect
from tkcurses.treemap._layout import (
    MIN_TILE_COLUMNS,
    MIN_TILE_ROWS,
    lay_out,
    regions,
)
from tkcurses.treemap._model import Model
from tkcurses.treemap._squarify import Span, snapped, squarify, tiles


def approx(span):
    return tuple(pytest.approx(edge) for edge in span)


def edges(span):
    return (span.left, span.top, span.right, span.bottom)


def test_the_papers_example_begins_as_the_paper_lays_it_out():
    """Bruls et al.'s figure: 6, 6, 4, 3, 2, 2, 1 in a 6 by 4 rectangle.
    The two sixes fill a column three wide; 4 and 3 a row along the top
    of what is left."""
    spans = squarify([6, 6, 4, 3, 2, 2, 1], Span(0, 0, 6, 4))
    assert edges(spans[0]) == approx((0, 0, 3, 2))
    assert edges(spans[1]) == approx((0, 2, 3, 4))
    assert edges(spans[2]) == approx((3, 0, 3 + 12 / 7, 7 / 3))
    assert edges(spans[3]) == approx((3 + 12 / 7, 0, 6, 7 / 3))
    areas = [span.width * span.height for span in spans]
    assert areas == pytest.approx([6, 6, 4, 3, 2, 2, 1])


def test_a_weight_with_no_size_takes_no_room():
    spans = squarify([3, 0, 1], Span(0, 0, 4, 1))
    assert spans[1] is None
    assert spans[0].width * spans[0].height == pytest.approx(3)


def test_nothing_to_lay_out():
    assert squarify([], Span(0, 0, 4, 4)) == []
    assert squarify([0, 0], Span(0, 0, 4, 4)) == [None, None]
    assert squarify([1], Span(0, 0, 0, 4)) == [None]


def test_a_weight_must_be_finite():
    with pytest.raises(ValueError, match="finite"):
        squarify([float("nan")], Span(0, 0, 1, 1))


def test_tiles_are_square_to_the_eye_not_in_cells():
    """30 by 10 cells is 30 by 20 to the eye: three equal tiles go two in a
    column 20 wide, 5 rows each - 20 by 10 to the eye - and one beside."""
    assert tiles([1, 1, 1], Rect(0, 0, 30, 10)) == [
        Rect(0, 0, 20, 5),
        Rect(0, 5, 20, 5),
        Rect(20, 0, 10, 10),
    ]


def test_snapping_rounds_each_edge_half_up():
    assert snapped(Span(0.5, 1.49, 2.5, 3.5)) == Rect(1, 1, 2, 3)


def test_a_tile_too_small_for_a_cell_is_empty():
    rects = tiles([1000, 1], Rect(0, 0, 10, 4))
    assert rects[1].empty


weights = st.lists(st.integers(0, 1000), min_size=1, max_size=12).map(
    lambda ws: sorted(ws, reverse=True)
)
areas = st.builds(Rect, st.just(0), st.just(0), st.integers(1, 80), st.integers(1, 30))


@given(weights, areas)
def test_the_tiles_cover_the_area_once(ws, area):
    covered = {}
    for index, rect in enumerate(tiles(ws, area)):
        if rect is None:
            continue
        for y in range(rect.y, rect.y + rect.height):
            for x in range(rect.x, rect.x + rect.width):
                assert (x, y) not in covered
                covered[x, y] = index
    if sum(ws):
        assert set(covered) == {
            (x, y) for x in range(area.width) for y in range(area.height)
        }
    else:
        assert not covered


@given(weights, areas)
def test_every_edge_is_within_half_a_cell_of_its_exact_place(ws, area):
    aspect = 2.0
    space = Span(0, 0, area.width, area.height * aspect)
    for span, rect in zip(squarify(ws, space), tiles(ws, area), strict=True):
        if span is None:
            assert rect is None
            continue
        assert abs(rect.x - span.left) <= 0.5
        assert abs(rect.x + rect.width - span.right) <= 0.5
        assert abs(rect.y - span.top / aspect) <= 0.5
        assert abs(rect.y + rect.height - span.bottom / aspect) <= 0.5


# ----------------------------------------------------------------- regions


def test_regions_cut_the_readout_then_the_legend():
    cut = regions(Rect(0, 0, 60, 8), legend="right", legend_extent=11)
    assert cut.readout == Rect(0, 7, 60, 1)
    assert cut.legend == Rect(49, 0, 11, 7)
    assert cut.tiles == Rect(0, 0, 49, 7)


@pytest.mark.parametrize(
    ("side", "legend", "tiles_rect"),
    [
        ("left", Rect(0, 0, 12, 9), Rect(12, 0, 28, 9)),
        ("top", Rect(0, 0, 40, 2), Rect(0, 2, 40, 7)),
        ("bottom", Rect(0, 7, 40, 2), Rect(0, 0, 40, 7)),
    ],
)
def test_the_legend_takes_its_side(side, legend, tiles_rect):
    extent = 12 if side == "left" else 2
    cut = regions(Rect(0, 0, 40, 10), legend=side, legend_extent=extent)
    assert (cut.legend, cut.tiles) == (legend, tiles_rect)


def test_the_legend_gives_way_first_then_the_readout():
    small = regions(Rect(0, 0, 20, 5), legend="right", legend_extent=12)
    assert small.legend is None
    assert small.readout is not None
    tiny = regions(Rect(0, 0, 20, 3), legend="right", legend_extent=12)
    assert (tiny.legend, tiny.readout) == (None, None)
    assert tiny.tiles == Rect(0, 0, 20, 3)


def test_without_a_legend_or_readout_the_tiles_have_it_all():
    assert regions(Rect(2, 1, 30, 9), readout=False) == regions(
        Rect(2, 1, 30, 9), readout=False, legend="left", legend_extent=0
    )
    assert regions(Rect(2, 1, 30, 9), readout=False).tiles == Rect(2, 1, 30, 9)


@given(
    st.integers(1, 100),
    st.integers(1, 40),
    st.booleans(),
    st.sampled_from(["left", "right", "top", "bottom", None]),
    st.integers(0, 40),
)
def test_regions_never_overlap_and_tiles_keep_room_while_they_can(
    width, height, readout, side, extent
):
    area = Rect(0, 0, width, height)
    cut = regions(area, readout=readout, legend=side, legend_extent=extent)
    parts = [part for part in (cut.tiles, cut.legend, cut.readout) if part]
    assert sum(part.width * part.height for part in parts) == width * height
    if width >= MIN_TILE_COLUMNS and height >= MIN_TILE_ROWS:
        assert cut.tiles.width >= MIN_TILE_COLUMNS
        assert cut.tiles.height >= MIN_TILE_ROWS


# --------------------------------------------------------------- the items


@pytest.fixture
def services():
    model = Model()
    model.insert("", "end", "web")
    for name, value in (("nginx", 330), ("apache", 170), ("php", 50)):
        model.insert("web", "end", name, value=value)
    model.insert("", "end", "db")
    for name, value in (("postgres", 140), ("mysql", 60)):
        model.insert("db", "end", name, value=value)
    model.insert("", "end", "cache", value=100)
    return model


def test_groups_come_before_their_children_with_a_header(services):
    layout = lay_out(services, Rect(0, 0, 49, 7))
    order = [tile.iid for tile in layout.tiles]
    assert order == [
        "web",
        "nginx",
        "apache",
        "php",
        "db",
        "postgres",
        "mysql",
        "cache",
    ]
    web = layout.tile("web")
    assert web.group
    assert web.header == Rect(web.rect.x, web.rect.y, web.rect.width, 1)
    for child in ("nginx", "apache", "php"):
        rect = layout.tile(child).rect
        assert rect.y > web.rect.y
        assert layout.tile(child).level == 1


def test_a_group_without_room_for_a_header_gives_it_to_its_children(services):
    layout = lay_out(services, Rect(0, 0, 49, 2))
    assert layout.tile("web").header is None
    assert layout.tile("nginx").rect.y == 0


def test_at_finds_the_innermost_tile(services):
    layout = lay_out(services, Rect(0, 0, 49, 7))
    web = layout.tile("web")
    assert layout.at(web.header.x, web.header.y).iid == "web"
    nginx = layout.tile("nginx").rect
    assert layout.at(nginx.x, nginx.y).iid == "nginx"
    assert layout.at(99, 99) is None


def test_zooming_lays_out_a_groups_children_alone(services):
    layout = lay_out(services, Rect(0, 0, 40, 10), zoom="web")
    assert [tile.iid for tile in layout.tiles] == ["nginx", "apache", "php"]
    covered = sum(tile.rect.width * tile.rect.height for tile in layout.tiles)
    assert covered == 400


def test_an_item_too_small_for_a_cell_is_counted_hidden(services):
    services.insert("", "end", "tiny", value=0.5)
    services.insert("", "end", "none", value=0)
    layout = lay_out(services, Rect(0, 0, 20, 5))
    assert "tiny" in layout.hidden
    assert "none" not in layout.hidden
    assert layout.tile("tiny") is None


def test_a_hidden_group_hides_its_children(services):
    services.insert("", "end", "small")
    services.insert("small", "end", "a", value=0.2)
    services.insert("small", "end", "b", value=0.2)
    layout = lay_out(services, Rect(0, 0, 10, 4))
    assert {"small", "a", "b"} <= set(layout.hidden)


def test_an_empty_treemap_has_no_tiles():
    layout = lay_out(Model(), Rect(0, 0, 40, 10))
    assert (layout.tiles, layout.hidden) == ((), ())
