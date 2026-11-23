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

"""A treemap's focus, selection, zoom, keys, mouse and tags."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

import tkcurses as tk
from tkcurses._charts.geometry import Rect
from tkcurses.treemap import PATH_SEPARATOR as PATH
from tkcurses.treemap import TreeMap
from tkcurses.treemap._compose import SELECTED
from tkcurses.treemap._navigate import DIRECTIONS, OPPOSITE, neighbour
from tkcurses.treemap._outline import inner

# ------------------------------------------------------------- navigation


def test_right_goes_to_the_neighbour_across_a_shared_edge():
    tiles = [("b", Rect(5, 0, 5, 2)), ("c", Rect(5, 2, 5, 2))]
    assert neighbour(Rect(0, 0, 5, 4), tiles, "Right") == "b"  # ties: earlier
    assert neighbour(Rect(0, 3, 5, 1), tiles, "Right") == "c"  # level with it


def test_a_tile_level_with_the_middle_wins():
    tiles = [
        ("top", Rect(5, 0, 5, 3)),
        ("mid", Rect(5, 3, 5, 3)),
        ("low", Rect(5, 6, 5, 3)),
    ]
    assert neighbour(Rect(0, 0, 5, 9), tiles, "Right") == "mid"


def test_an_overlapping_neighbour_beats_a_nearer_diagonal_one():
    tiles = [("diagonal", Rect(5, 4, 2, 2)), ("across", Rect(9, 0, 2, 2))]
    assert neighbour(Rect(0, 0, 5, 2), tiles, "Right") == "across"


def test_nothing_that_way_is_none():
    assert neighbour(Rect(0, 0, 5, 5), [("b", Rect(5, 0, 5, 5))], "Left") is None
    assert neighbour(Rect(0, 0, 5, 5), [], "Up") is None


@given(
    st.lists(
        st.tuples(
            st.integers(0, 30), st.integers(0, 30), st.integers(1, 8), st.integers(1, 8)
        ),
        min_size=1,
        max_size=8,
    ),
    st.sampled_from(DIRECTIONS),
)
def test_a_move_goes_only_that_way(boxes, direction):
    current = Rect(10, 10, 4, 4)
    tiles = [(str(i), Rect(*box)) for i, box in enumerate(boxes)]
    found = neighbour(current, tiles, direction)
    if found is None:
        return
    rect = dict(tiles)[found]
    if direction == "Right":
        assert rect.x >= current.x + current.width
    elif direction == "Left":
        assert rect.x + rect.width <= current.x
    elif direction == "Down":
        assert rect.y >= current.y + current.height
    else:
        assert rect.y + rect.height <= current.y
    assert OPPOSITE[OPPOSITE[direction]] == direction


# ---------------------------------------------------------------- widget


@pytest.fixture
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


@pytest.fixture
def tree(root):
    """The services, placed 49 by 11, with the keyboard focus."""
    widget = TreeMap(root)
    web = widget.insert("", "end", "web", text="web")
    widget.insert(web, "end", "nginx", text="nginx", value=330, tags="front")
    widget.insert(web, "end", "apache", text="apache", value=170, tags=("front", "old"))
    widget.insert(web, "end", "php", text="php", value=50)
    db = widget.insert("", "end", "db", text="db")
    widget.insert(db, "end", "postgres", text="postgres", value=140, tags="disk")
    widget.insert(db, "end", "mysql", text="mysql", value=60, tags="disk")
    widget.insert("", "end", "cache", text="cache", value=100)
    widget._allocate(Rect(0, 0, 49, 11))
    widget._map()
    widget.focus_set()
    return widget


def events(widget, *names):
    seen = []
    for name in names:
        widget.bind(name, lambda _e, name=name: seen.append(name), add="+")
    return seen


def key(widget, name):
    widget.event_generate(f"<Key-{name}>")


def centre(widget, iid):
    rect = widget._layout_now().tile(iid).rect
    return {"x": rect.x + rect.width // 2, "y": rect.y + rect.height // 2}


def click(widget, iid, double=False):
    widget.event_generate("<Button-1>", **centre(widget, iid))
    widget.event_generate("<ButtonRelease-1>", **centre(widget, iid))
    if double:
        widget.event_generate("<Double-Button-1>", **centre(widget, iid))


def text(widget):
    width, height = widget._rect.width, widget._rect.height
    return [
        "".join(cell.char for cell in row) for row in widget._compose(width, height)
    ]


def test_it_takes_the_focus(root):
    assert TreeMap(root).cget("takefocus")


def test_the_first_arrow_focuses_the_largest(tree):
    assert tree.focus() == ""
    key(tree, "Right")
    assert tree.focus() == "web"


def test_arrows_move_between_tiles_and_back(tree):
    tree.focus("nginx")
    key(tree, "Right")
    moved = tree.focus()
    assert moved in ("apache", "php")
    key(tree, "Left")
    assert tree.focus() == "nginx"


def test_an_arrow_with_nothing_that_way_leaves_the_focus(tree):
    tree.focus("nginx")
    key(tree, "Left")
    assert tree.focus() == "nginx"


def test_arrows_stay_on_one_level(tree):
    tree.focus("web")
    key(tree, "Right")
    assert tree.focus() in ("db", "cache")


def test_space_and_return_select_and_send_the_event(tree):
    seen = events(tree, "<<TreeMapSelect>>")
    tree.focus("nginx")
    key(tree, "space")
    assert tree.selection() == ("nginx",)
    tree.focus("cache")
    key(tree, "Return")
    assert tree.selection() == ("cache",)
    assert seen == ["<<TreeMapSelect>>"] * 2


def test_return_on_a_group_zooms_in_and_escape_comes_out(tree):
    seen = events(tree, "<<TreeMapZoom>>")
    tree.focus("db")
    key(tree, "Return")
    assert tree.zoom() == "db"
    assert tree.focus() == "postgres"
    assert {t.iid for t in tree._layout_now().tiles} == {"postgres", "mysql"}
    assert text(tree)[-1].startswith(f"db{PATH}postgres")
    key(tree, "Escape")
    assert tree.zoom() == ""
    assert tree.focus() == "db"
    assert seen == ["<<TreeMapZoom>>"] * 2


def test_escape_from_a_child_goes_to_its_group(tree):
    tree.focus("mysql")
    key(tree, "Escape")
    assert tree.focus() == "db"


def test_a_click_focuses_and_selects(tree):
    seen = events(tree, "<<TreeMapSelect>>")
    click(tree, "postgres")
    assert tree.focus() == "postgres"
    assert tree.selection() == ("postgres",)
    assert seen == ["<<TreeMapSelect>>"]


def test_a_click_on_a_header_is_the_group(tree):
    header = tree._layout_now().tile("web").header
    assert tree.identify(header.x + 1, header.y) == "web"
    tree.event_generate("<Button-1>", x=header.x + 1, y=header.y)
    assert tree.selection() == ("web",)


def test_a_double_click_zooms_into_the_group(tree):
    click(tree, "nginx", double=True)
    assert tree.zoom() == "web"


def test_identify_outside_any_tile_is_empty(root, tree):
    assert tree.identify(100, 100) == ""
    assert tree.identify(5, 10) == ""  # the readout
    boxed = TreeMap(root, borderwidth=1)
    boxed.insert("", "end", text="only", value=1)
    boxed._allocate(Rect(0, 0, 20, 6))
    boxed._map()
    assert boxed.identify(0, 0) == ""  # the frame's own box
    assert boxed.identify(5, 2) == "I001"


def test_selection_set_selects_one_or_none(tree):
    tree.selection_set("mysql")
    assert tree.selection() == ("mysql",)
    tree.selection_set()
    assert tree.selection() == ()
    with pytest.raises(tk.TclError, match="one item at most"):
        tree.selection_set("mysql", "php")
    with pytest.raises(tk.TclError, match="Item nosuch not found"):
        tree.selection_set("nosuch")


@pytest.mark.parametrize("item", ["nginx", "cache", "nosuch"])
def test_only_a_group_can_be_zoomed_into(tree, item):
    with pytest.raises(tk.TclError):
        tree.zoom(item)


def test_deleting_the_zoomed_group_zooms_out(tree):
    tree.zoom("db")
    tree.delete("db")
    text(tree)
    assert tree.zoom() == ""


# ------------------------------------------------------------------ drawing


def reversed_cells(widget):
    width, height = widget._rect.width, widget._rect.height
    grid = widget._compose(width, height)
    return {
        (x, y)
        for y, row in enumerate(grid)
        for x, cell in enumerate(row)
        if cell.reverse
    }


def test_the_focused_tiles_label_row_is_reversed(tree):
    tree.focus("nginx")
    rect = inner(tree._layout_now().tile("nginx").rect)  # inside its lines
    assert reversed_cells(tree) == {
        (x, rect.y) for x in range(rect.x, rect.x + rect.width)
    }


def test_a_focused_group_reverses_its_header(tree):
    tree.configure(legend="hide")
    tree.focus("web")
    header = tree._layout_now().tile("web").header
    assert reversed_cells(tree) == {
        (x, header.y) for x in range(header.x, header.x + header.width)
    }


def test_a_tile_with_no_room_for_text_is_reversed_whole(root):
    widget = TreeMap(root, outline="off", legend="hide")
    widget.insert("", "end", "big", text="big", value=1000)
    widget.insert("", "end", "tiny", text="tiny", value=40)
    widget._allocate(Rect(0, 0, 40, 10))
    widget._map()
    widget.focus_set()
    widget.focus("tiny")
    rect = widget._layout_now().tile("tiny").rect
    assert rect.width < 3  # too narrow for a label
    whole = {
        (x, y)
        for y in range(rect.y, rect.y + rect.height)
        for x in range(rect.x, rect.x + rect.width)
    }
    assert reversed_cells(widget) == whole


def test_without_the_keyboard_focus_nothing_is_reversed(root, tree):
    tree.focus("nginx")
    other = tk.Entry(root)
    other.focus_set()
    assert reversed_cells(tree) == set()


def test_the_selected_item_is_marked(tree):
    tree.selection_set("cache")
    assert any(f"{SELECTED} cache" in row for row in text(tree))


def test_the_readout_names_the_focused_item(tree):
    tree.focus("apache")
    assert text(tree)[-1].endswith("30.91% of w…")  # 49 wide: cut, not spilled
    tree._allocate(Rect(0, 0, 60, 11))
    assert (
        text(tree)[-1].rstrip()
        == f"web{PATH}apache   170   20.00% of all   30.91% of web"
    )
    tree.focus("")
    assert text(tree)[-1].rstrip() == "total 850"


# --------------------------------------------------------------------- tags


def test_tags_are_kept_as_a_tuple(tree):
    assert tree.item("apache", "tags") == ("front", "old")
    assert tree.item("nginx", "tags") == ("front",)
    tree.item("php", tags="front new")
    assert tree.item("php", "tags") == ("front", "new")
    assert tree.tag_has("front") == ("nginx", "apache", "php")
    assert tree.tag_has("disk", "mysql")
    assert not tree.tag_has("disk", "nginx")


def test_a_tag_binding_runs_only_for_its_items(tree):
    chosen = []
    tree.tag_bind(
        "disk", "<<TreeMapSelect>>", lambda _e: chosen.append(tree.selection()[0])
    )
    tree.selection_set("nginx")
    tree.selection_set("mysql")
    click(tree, "postgres")
    tree.focus("cache")
    key(tree, "space")
    assert chosen == ["mysql", "postgres"]


def test_a_tag_binding_on_a_mouse_event_goes_to_the_tile_under_it(tree):
    hit = []
    tree.tag_bind("old", "<Button-3>", lambda _e: hit.append("old"))
    tree.event_generate("<Button-3>", **centre(tree, "nginx"))
    tree.event_generate("<Button-3>", **centre(tree, "apache"))
    assert hit == ["old"]


def test_a_tag_binding_on_a_key_goes_to_the_focused_item(tree):
    hit = []
    tree.tag_bind("front", "<Key-d>", lambda _e: hit.append(tree.focus()))
    tree.focus("nginx")
    key(tree, "d")
    tree.focus("cache")
    key(tree, "d")
    assert hit == ["nginx"]


def test_every_tag_of_an_item_runs_in_its_order(tree):
    order = []
    tree.tag_bind("old", "<<TreeMapSelect>>", lambda _e: order.append("old"))
    tree.tag_bind("front", "<<TreeMapSelect>>", lambda _e: order.append("front"))
    tree.selection_set("apache")
    assert order == ["front", "old"]


def test_a_tag_binding_on_zoom_is_for_the_group(root, tree):
    zoomed = []
    tree.item("db", tags="data")
    tree.tag_bind("data", "<<TreeMapZoom>>", lambda _e: zoomed.append(tree.zoom()))
    tree.zoom("web")
    tree.zoom("")
    tree.zoom("db")
    tree.focus("postgres")
    key(tree, "Escape")
    assert zoomed == ["db", ""]


@given(
    st.lists(st.integers(1, 200), min_size=2, max_size=12),
    st.integers(20, 70),
    st.integers(6, 20),
    st.sampled_from(DIRECTIONS),
)
def test_the_opposite_key_always_goes_back(sizes, width, height, direction):
    window = tk.Tk(useTk=False)
    try:
        widget = TreeMap(window, outline="off", readout=False)
        for size in sizes:
            widget.insert("", "end", text="x", value=size)
        widget._allocate(Rect(0, 0, width, height))
        widget._map()
        widget.focus_set()
        for tile in widget._layout_now().tiles:
            widget.focus(tile.iid)
            key(widget, direction)
            if widget.focus() != tile.iid:
                key(widget, OPPOSITE[direction])
                assert widget.focus() == tile.iid
    finally:
        window.destroy()


def test_the_readout_zoomed_with_nothing_focused_is_the_groups_total(tree):
    tree.zoom("db")
    tree.focus("")
    assert text(tree)[-1].rstrip() == f"db{PATH}total 200"
