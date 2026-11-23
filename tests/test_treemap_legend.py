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

"""A treemap's legend: entries, wrapping, size, placement and the widget's
use of them."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

import tkcurses as tk
from tkcurses._charts.geometry import Rect
from tkcurses._core.cells import cells
from tkcurses.treemap import Treemap
from tkcurses.treemap._compose import Scene, compose
from tkcurses.treemap._layout import lay_out, regions
from tkcurses.treemap._legend import (
    LEGEND_SIZES,
    SWATCH,
    Entry,
    entries,
    extent,
    place,
    shown,
    wrap,
)
from tkcurses.treemap._model import Model


def services():
    model = Model()
    model.insert("", "end", "web", text="web")
    for name, value in (("nginx", 330), ("apache", 170), ("php", 50)):
        model.insert("web", "end", name, text=name, value=value)
    model.insert("", "end", "db", text="db")
    for name, value in (("postgres", 140), ("mysql", 60)):
        model.insert("db", "end", name, text=name, value=value)
    model.insert("", "end", "cache", text="cache", value=100)
    return model


# ------------------------------------------------------------------ wrap


def test_words_wrap_at_spaces():
    assert wrap("disk usage by type", 10, 5) == ["disk usage", "by type"]


def test_a_word_longer_than_a_line_is_broken_inside():
    assert wrap("postgres", 6, 5) == ["postgr", "es"]


def test_the_last_line_holds_the_rest_cut():
    assert wrap("one two three four", 7, 2) == ["one two", "three …"]
    assert wrap("one two three", 20, 1) == ["one two three"]


def test_nothing_to_wrap_into():
    assert wrap("web", 0, 3) == []
    assert wrap("web", 5, 0) == []


@given(st.text(max_size=30), st.integers(1, 12), st.integers(1, 5))
def test_wrapped_lines_fit_and_stay_within_the_limit(text, width, limit):
    lines = wrap(text, width, limit)
    assert len(lines) <= limit
    assert all(cells(line) <= width for line in lines)


def test_wide_characters_wrap_by_cells():
    assert wrap("界界界", 4, 5) == ["界界", "界"]
    assert wrap("界", 1, 5) == ["…"]


# --------------------------------------------------------------- entries


def test_entries_are_the_top_level_largest_first():
    assert [e.iid for e in entries(services())] == ["web", "db", "cache"]


def test_a_nested_legend_lists_each_groups_children_under_it():
    listed = entries(services(), nested=True)
    assert [e.iid for e in listed] == [
        "web", "nginx", "apache", "php", "db", "postgres", "mysql", "cache",
    ]  # fmt: skip
    assert [e.nested for e in listed][:2] == [False, True]


def test_zoomed_the_legend_names_the_groups_children():
    assert [e.iid for e in entries(services(), "db", nested=True)] == [
        "postgres",
        "mysql",
    ]


def test_an_item_of_zero_has_no_entry():
    model = services()
    model.configure("cache", value=0)
    assert "cache" not in [e.iid for e in entries(model)]


def test_an_unnamed_item_is_listed_by_its_iid():
    model = Model()
    model.insert("", "end", "I9", value=3)
    assert entries(model)[0].text == "I9"


def test_auto_shows_it_for_two_or_more_at_the_top():
    one = [Entry("web", "web"), Entry("nginx", "nginx", nested=True)]
    two = [Entry("web", "web"), Entry("db", "db")]
    assert not shown("auto", one)
    assert shown("auto", two)
    assert shown("show", one)
    assert not shown("hide", two)
    assert not shown("show", [])


# ---------------------------------------------------------------- extent


LISTED = [Entry("web", "web"), Entry("db", "db"), Entry("cache", "cache")]


def test_auto_at_the_side_is_the_widest_entry_and_its_edge():
    assert extent(LISTED, "right", "auto", Rect(0, 0, 60, 8), 1) == 1 + 3 + 5


def test_auto_at_the_side_is_at_most_a_third():
    long = [Entry("a", "a rather long name for a legend")]
    assert extent(long, "left", "auto", Rect(0, 0, 60, 8), 1) == 20


@pytest.mark.parametrize(("size", "columns"), LEGEND_SIZES.items())
def test_a_named_size_is_that_many_columns(size, columns):
    assert extent(LISTED, "right", size, Rect(0, 0, 100, 8), 1) == columns


def test_at_the_top_it_takes_the_rows_its_columns_need():
    # Three entries of at most 8 cells fit across 60: one row and the edge.
    assert extent(LISTED, "top", "auto", Rect(0, 0, 60, 12), 1) == 2
    # Across 12, one a row.
    assert extent(LISTED, "bottom", "auto", Rect(0, 0, 12, 30), 1) == 4


def test_at_the_top_it_is_at_most_a_third_of_the_height():
    assert extent(LISTED, "top", "auto", Rect(0, 0, 12, 9), 1) == 3


def test_no_room_is_no_legend():
    assert extent(LISTED, "right", "auto", Rect(0, 0, 12, 8), 1) == 0
    assert extent(LISTED, "top", "auto", Rect(0, 0, 60, 5), 1) == 0
    assert extent([], "right", "auto", Rect(0, 0, 60, 8), 1) == 0


# ----------------------------------------------------------------- place


def test_at_the_side_entries_stack_inside_the_edge():
    laid = place(LISTED, Rect(50, 0, 10, 7), "right", 1)
    assert laid.edge == Rect(50, 0, 1, 7)
    assert laid.edge_glyph == "│"
    assert [(p.iid, p.x, p.y) for p in laid.placed] == [
        ("web", 51, 0),
        ("db", 51, 1),
        ("cache", 51, 2),
    ]
    assert laid.more == 0


def test_at_the_left_the_edge_is_on_the_right():
    laid = place(LISTED, Rect(0, 0, 10, 7), "left", 1)
    assert laid.edge == Rect(9, 0, 1, 7)
    assert laid.placed[0].x == 0


def test_too_many_end_with_how_many_more():
    laid = place(entries(services(), nested=True), Rect(50, 0, 13, 7), "right", 1)
    assert len(laid.placed) == 6  # the last row says how many more
    assert laid.more == 2
    assert laid.more_at == (51, 6)
    assert laid.more_text == "+2 more"


def test_wrapped_entries_take_their_lines():
    long = [Entry("a", "disk usage"), Entry("b", "b")]
    laid = place(long, Rect(0, 0, 9, 6), "left", 2)
    assert laid.placed[0].lines == ("disk", "usage")
    assert laid.placed[1].y == 2


def test_a_nested_entry_is_indented():
    listed = entries(services(), nested=True)
    laid = place(listed, Rect(40, 0, 20, 10), "right", 1)
    nginx = next(p for p in laid.placed if p.iid == "nginx")
    assert nginx.indent == 2
    assert nginx.text_rect.x == 41 + 2 + 3


def test_at_the_bottom_entries_flow_across():
    laid = place(LISTED, Rect(0, 9, 60, 2), "bottom", 1)
    assert laid.edge == Rect(0, 9, 60, 1)
    assert laid.edge_glyph == "─"
    assert [(p.x, p.y) for p in laid.placed] == [(0, 10), (10, 10), (20, 10)]


def test_at_finds_the_entry():
    laid = place(LISTED, Rect(50, 0, 10, 7), "right", 1)
    assert laid.at(55, 1) == "db"
    assert laid.at(50, 1) is None  # the edge
    assert laid.at(55, 5) is None


# --------------------------------------------------------------- compose


PALETTE = (("green", (0, 205, 0)), ("red", (205, 0, 0)), ("blue", (0, 0, 238)))


def test_a_swatch_is_its_items_colour():
    model = services()
    cut = regions(Rect(0, 0, 60, 8), legend="right", legend_extent=9)
    layout = lay_out(model, cut.tiles)
    legend = place(entries(model), cut.legend, "right", 1)
    grid = compose(Scene(60, 8, cut, layout, model, colors=PALETTE, legend=legend))
    rows = ["".join(c.char for c in row) for row in grid]
    assert rows[0][51:] == f"│{SWATCH} web  "
    assert [grid[y][52].fg for y in range(3)] == ["green", "red", "blue"]


# ---------------------------------------------------------------- widget


@pytest.fixture
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


def placed(root, width=60, height=8, **kw):
    widget = Treemap(root, **kw)
    web = widget.insert("", "end", "web", text="web")
    for name, value in (("nginx", 330), ("apache", 170), ("php", 50)):
        widget.insert(web, "end", name, text=name, value=value)
    db = widget.insert("", "end", "db", text="db")
    for name, value in (("postgres", 140), ("mysql", 60)):
        widget.insert(db, "end", name, text=name, value=value)
    widget.insert("", "end", "cache", text="cache", value=100)
    widget._allocate(Rect(0, 0, width, height))
    widget._map()
    return widget


def text(widget):
    grid = widget._compose(widget._rect.width, widget._rect.height)
    return ["".join(cell.char for cell in row) for row in grid]


def legend_rect(widget):
    return widget._scene_now().regions.legend


def test_by_default_it_is_on_the_right(root):
    widget = placed(root)
    assert legend_rect(widget) == Rect(51, 0, 9, 7)
    assert text(widget)[0].endswith(f"{SWATCH} web  ")


def test_auto_hides_it_for_one_top_level_item(root):
    widget = Treemap(root)
    widget.insert("", "end", "only", text="only", value=1)
    widget._allocate(Rect(0, 0, 60, 8))
    widget._map()
    assert legend_rect(widget) is None
    widget.configure(legend="show")
    assert legend_rect(widget) is not None


def test_hide_hides_it(root):
    assert legend_rect(placed(root, legend="hide")) is None


def test_it_gives_way_when_the_tiles_would_be_too_small(root):
    assert legend_rect(placed(root, width=14)) is None  # a third is 4
    assert legend_rect(placed(root, width=19)) == Rect(13, 0, 6, 7)


@pytest.mark.parametrize("position", ["right", "left", "top", "bottom"])
@pytest.mark.parametrize("width", [20, 40, 61])
@pytest.mark.parametrize("height", [6, 12, 20])
def test_it_never_overlaps_the_tiles_or_the_readout(root, position, width, height):
    widget = placed(
        root, width, height, legendposition=position, nestedlegend=True, legendlines=3
    )
    scene = widget._scene_now()
    cut = scene.regions
    if cut.legend is None:
        return
    legend = cut.legend

    def overlaps(a, b):
        return not (
            a.x + a.width <= b.x
            or b.x + b.width <= a.x
            or a.y + a.height <= b.y
            or b.y + b.height <= a.y
        )

    assert not overlaps(legend, cut.tiles)
    if cut.readout is not None:
        assert not overlaps(legend, cut.readout)
    for entry in scene.legend.placed:
        rect = entry.rect
        assert legend.x <= rect.x and rect.x + rect.width <= legend.x + legend.width
        assert legend.y <= rect.y and rect.y + rect.height <= legend.y + legend.height


def test_bad_values_are_refused(root):
    with pytest.raises(tk.TclError, match="legend"):
        Treemap(root, legend="sometimes")
    with pytest.raises(tk.TclError, match="legendposition"):
        Treemap(root, legendposition="middle")
    with pytest.raises(tk.TclError, match="legendsize"):
        Treemap(root, legendsize="huge")
    with pytest.raises(tk.TclError, match="at most 5"):
        Treemap(root, legendlines=6)
    with pytest.raises(tk.TclError):
        Treemap(root, legendlines=0)


def test_configure_moves_it(root):
    widget = placed(root, width=60, height=12)
    widget.configure(legendposition="bottom")
    assert legend_rect(widget) == Rect(0, 9, 60, 2)
    assert text(widget)[10].startswith(f"{SWATCH} web")


def test_zoomed_it_names_the_groups_children(root):
    widget = placed(root)
    widget.zoom("web")
    names = [p.iid for p in widget._scene_now().legend.placed]
    assert names == ["nginx", "apache", "php"]


def test_the_focused_entry_is_reversed_but_not_its_swatch(root):
    widget = placed(root, legend="show")
    widget.focus_set()
    widget.focus("db")
    entry = next(p for p in widget._scene_now().legend.placed if p.iid == "db")
    grid = widget._compose(60, 8)
    assert entry.text_rect == Rect(55, 1, 5, 1)
    assert all(grid[1][x].reverse for x in range(55, 60))
    assert not any(grid[1][x].reverse for x in range(51, 55))  # edge, swatch


def test_without_the_keyboard_focus_the_entry_is_not_reversed(root):
    widget = placed(root)
    widget.focus("db")
    tk.Entry(root).focus_set()
    grid = widget._compose(60, 8)
    assert not any(cell.reverse for row in grid for cell in row)


def test_a_click_on_an_entry_focuses_and_does_not_select(root):
    widget = placed(root)
    seen = []
    widget.bind("<<TreemapSelect>>", lambda _e: seen.append("select"))
    widget.event_generate("<Button-1>", x=55, y=2)
    assert widget.focus() == "cache"
    assert widget.focus_get() is widget
    assert widget.selection() == ()
    assert seen == []
    assert widget.identify(55, 2) == "cache"
    assert widget.identify(55, 5) == ""


def test_an_item_too_small_for_a_tile_still_has_an_entry(root):
    widget = placed(root, legend="show")
    widget.insert("", "end", "tiny", text="tiny", value=0.5)
    scene = widget._scene_now()
    assert "tiny" in scene.layout.hidden
    assert "tiny" in [p.iid for p in scene.legend.placed]


# ----------------------------------------------------------- descriptions


def described(root, width=60, height=10, **kw):
    widget = Treemap(root, **kw)
    widget.insert(
        "", "end", "web", text="web", value=550, description="front-end servers"
    )
    widget.insert(
        "",
        "end",
        "db",
        text="db",
        value=200,
        description="databases, primary and replica",
    )
    widget.insert("", "end", "cache", text="cache", value=100)
    widget._allocate(Rect(0, 0, width, height))
    widget._map()
    return widget


def test_an_item_has_a_description_to_read_and_change(root):
    widget = described(root)
    assert widget.item("web", "description") == "front-end servers"
    assert widget.item("cache")["description"] == ""
    widget.item("cache", description="redis")
    assert widget.item("cache", "description") == "redis"
    with pytest.raises(tk.TclError, match="unknown option"):
        widget.item("cache", descr="x")


def test_a_description_goes_under_the_name_in_the_legend(root):
    widget = described(root, legendsize="medium")
    rows = text(widget)
    assert legend_rect(widget).x == 40
    assert rows[0][40:] == f" {SWATCH} web".ljust(20)  # boxed tiles: no edge
    assert rows[1][41:] == "   front-end serve…"
    assert rows[2][41:] == f"{SWATCH} db".ljust(19)
    assert rows[3][41:] == "   databases, prim…"
    assert rows[4][41:].startswith(f"{SWATCH} cache")


def test_a_description_wraps_onto_legendlines(root):
    widget = described(root, legendsize="medium", legendlines=2)
    db = next(p for p in widget._scene_now().legend.placed if p.iid == "db")
    assert db.lines == ("db", "databases,", "primary and rep…")
    assert db.name_lines == 1


def test_a_description_is_shown_nowhere_but_the_legend(root):
    widget = described(root, legendsize="medium")
    widget.focus_set()
    widget.focus("db")
    scene = widget._scene_now()
    tiles = scene.regions.tiles
    rows = text(widget)
    in_tiles = "".join(
        row[tiles.x : tiles.x + tiles.width]
        for row in rows[tiles.y : tiles.y + tiles.height]
    )
    assert "front" not in in_tiles
    assert "databases" not in in_tiles
    assert "databases" not in scene.readout
    assert widget._readout(scene.layout).startswith("db   200")


def test_only_the_name_is_reversed_for_the_focus(root):
    widget = described(root, legendsize="medium")
    widget.focus_set()
    widget.focus("db")
    grid = widget._compose(60, 10)
    assert all(grid[2][x].reverse for x in range(45, 60))
    assert not any(grid[3][x].reverse for x in range(41, 60))


def test_a_description_widens_an_auto_legend_by_at_most_twenty():
    short = [Entry("a", "a", description="tiny")]
    assert extent(short, "right", "auto", Rect(0, 0, 90, 8), 1) == 1 + 3 + 4
    long = [Entry("a", "a", description="a description far longer than twenty")]
    assert extent(long, "right", "auto", Rect(0, 0, 90, 8), 1) == 1 + 3 + 20


def test_without_room_descriptions_are_cut_before_names():
    """Text 9 cells wide: alpha's description wraps to "one two",
    "three", "four"."""
    listed = [
        Entry("a", "alpha", description="one two three four"),
        Entry("b", "beta", description="five six"),
    ]
    # Three rows: one is kept for "+1 more", so alpha's description is cut.
    laid = place(listed, Rect(0, 0, 13, 3), "left", 3)
    assert [p.lines for p in laid.placed] == [("alpha", "one two …")]
    assert laid.more == 1
    # Two: the name alone.
    laid = place(listed, Rect(0, 0, 13, 2), "left", 3)
    assert [p.lines for p in laid.placed] == [("alpha",)]
    # One entry and two rows: no "+N more" to keep a row for.
    tight = place(listed[:1], Rect(0, 0, 13, 2), "left", 3)
    assert [p.lines for p in tight.placed] == [("alpha", "one two …")]
    assert tight.more == 0
    # Room for all of it: nothing is cut.
    roomy = place(listed[:1], Rect(0, 0, 13, 4), "left", 3)
    assert roomy.placed[0].lines == ("alpha", "one two", "three", "four")


def test_a_blank_description_takes_no_line():
    laid = place([Entry("a", "alpha", description="   ")], Rect(0, 0, 13, 5), "left", 2)
    assert laid.placed[0].lines == ("alpha",)


@given(
    st.lists(
        st.tuples(st.text(max_size=12), st.text(max_size=40)), min_size=1, max_size=6
    ),
    st.integers(5, 40),
    st.integers(1, 12),
    st.integers(1, 5),
)
def test_described_entries_stay_inside_the_legend(pairs, width, height, limit):
    listed = [
        Entry(str(i), name, description=told) for i, (name, told) in enumerate(pairs)
    ]
    region = Rect(0, 0, width, height)
    laid = place(listed, region, "left", limit)
    inner = Rect(0, 0, width - 1, height)
    for entry in laid.placed:
        assert entry.y + len(entry.lines) <= inner.height
        assert 1 <= entry.name_lines <= len(entry.lines) <= 2 * limit
        text_width = entry.width - entry.indent - 3
        assert all(cells(line) <= text_width for line in entry.lines)
    assert len(laid.placed) + laid.more == len(listed)
