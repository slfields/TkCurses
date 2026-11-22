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

"""The Treemap widget, its labels and its drawing, without a terminal."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

import tkcurses as tk
from tkcurses._charts.color import BLACK, WHITE, luminance, text_on
from tkcurses._charts.geometry import Rect
from tkcurses._core.cells import cells
from tkcurses.treemap import Treemap
from tkcurses.treemap._compose import EMPTY_TEXT, Scene, compose
from tkcurses.treemap._labels import MIN_LABEL, header_text, percent, tile_text
from tkcurses.treemap._layout import lay_out, regions
from tkcurses.treemap._model import Model

# ------------------------------------------------------------------ labels


def test_a_name_and_value_take_two_rows():
    assert tile_text("nginx", "38.82%", 10, 3) == ["nginx", "38.82%"]


def test_a_long_name_is_cut_but_a_value_never_is():
    assert tile_text("postgres", "16.47%", 5, 2) == ["post…"]


def test_a_name_too_short_to_cut_is_left_out():
    assert tile_text("postgres", None, MIN_LABEL - 1, 2) == []
    assert tile_text("db", None, 2, 1) == ["db"]  # whole, it fits


def test_one_row_holds_both_only_when_both_fit_whole():
    assert tile_text("php", "5.88%", 9, 1) == ["php 5.88%"]
    assert tile_text("php", "5.88%", 8, 1) == ["php"]
    assert tile_text("postgres", "1%", 6, 1) == ["postg…"]


def test_without_a_name_the_value_comes_first():
    assert tile_text(None, "5.88%", 6, 2) == ["5.88%"]
    assert tile_text("", "5.88%", 6, 1) == ["5.88%"]


def test_nothing_fits_in_nothing():
    assert tile_text("web", "1%", 0, 3) == []
    assert tile_text("web", "1%", 3, 0) == []


def test_a_header_has_both_or_the_name():
    assert header_text("web", "64.71%", 10) == "web 64.71%"
    assert header_text("web", "64.71%", 9) == "web"
    assert header_text("services", None, 6) == "servi…"


def test_percent():
    assert percent(330, 850, 2) == "38.82%"
    assert percent(1, 3, 0) == "33%"
    assert percent(1, 0, 2) == "0.00%"


@given(st.text(max_size=12), st.text(max_size=8), st.integers(0, 14), st.integers(0, 4))
def test_labels_never_overflow_a_tile(name, value, width, height):
    lines = tile_text(name, value, width, height)
    assert len(lines) <= max(0, min(height, 2))
    assert all(cells(line) <= width for line in lines)


def test_text_is_black_or_white_by_contrast():
    assert text_on((205, 205, 0)) == BLACK
    assert text_on((0, 0, 238)) == WHITE
    assert luminance((255, 255, 255)) == pytest.approx(1)
    assert luminance((0, 0, 0)) == 0


# ----------------------------------------------------------------- compose


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


PALETTE = (("green", (0, 205, 0)), ("red", (205, 0, 0)), ("blue", (0, 0, 238)))


def scene(model, width=49, height=11, **kw):
    cut = regions(Rect(0, 0, width, height))
    outlined = kw.pop("outlined", frozenset())
    layout = lay_out(model, cut.tiles, outlined=outlined)
    total = model.total()
    return Scene(
        width,
        height,
        cut,
        layout,
        model,
        outlined=outlined,
        value_text=lambda iid: percent(model.size(iid), total, 2),
        **kw,
    )


def rows(grid):
    return ["".join(cell.char for cell in row) for row in grid]


def test_tiles_take_their_groups_colour_and_shades():
    model = services()
    drawn = scene(model, colors=PALETTE)
    grid = compose(drawn)
    tile = {t.iid: t for t in drawn.layout.tiles}

    def bg(iid):
        rect = tile[iid].rect
        return grid[rect.y + rect.height - 1][rect.x + rect.width - 1].bg

    assert bg("cache") == "blue"
    web_children = {bg(i) for i in ("nginx", "apache", "php")}
    assert len(web_children) == 3
    assert bg("nginx") == "green"  # the largest takes the colour itself
    header = tile["web"].header
    cell = grid[header.y][header.x]
    assert (cell.char, cell.bg, cell.fg, cell.bold) == ("w", "green", "black", True)


def test_text_on_a_dark_tile_is_white():
    model = Model()
    model.insert("", "end", "a", text="a", value=1)
    grid = compose(scene(model, 10, 4, colors=(("blue", (0, 0, 238)),)))
    assert (grid[0][0].char, grid[0][0].fg, grid[0][0].bg) == ("a", "white", "blue")


def test_an_outlined_groups_children_share_its_colour_and_lines_divide_them():
    model = services()
    drawn = scene(model, colors=PALETTE, outlined=frozenset({"web", "db"}))
    grid = compose(drawn)
    nginx = next(t for t in drawn.layout.tiles if t.iid == "nginx")
    corner = grid[nginx.rect.y][nginx.rect.x]
    assert (corner.char, corner.bg, corner.fg) == ("┌", "green", "black")
    inside = grid[nginx.rect.y + 1][nginx.rect.x + 1]
    assert inside.bg == "green"


def test_without_colour_nothing_is_coloured():
    grid = compose(scene(services(), outlined=frozenset({"", "web", "db"})))
    assert {(cell.fg, cell.bg) for row in grid for cell in row} == {("", "")}
    assert rows(grid)[0] == "┌──────────────────────────────┬────────────────┐"


def test_an_empty_treemap_says_so():
    grid = compose(scene(Model(), 30, 5))
    text = rows(grid)
    assert any(line.strip() == EMPTY_TEXT for line in text)


def test_the_readout_is_the_last_row():
    grid = compose(scene(services(), readout="total 850"))
    assert rows(grid)[-1].rstrip() == "total 850"


def test_a_wide_name_takes_two_cells():
    model = Model()
    model.insert("", "end", "a", text="界a", value=1)
    grid = compose(scene(model, 10, 3))
    assert [cell.char for cell in grid[0][:3]] == ["界", "", "a"]


# ------------------------------------------------------------------ widget


@pytest.fixture
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


def test_defaults(root):
    tree = Treemap(root)
    assert tree.cget("values") == "percent"
    assert tree.cget("percentdecimals") == 2
    assert tree.cget("outline") == "auto"
    assert tree.cget("relief") == "solid"


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"values": "x"}, 'bad values "x": must be percent, value, or none'),
        ({"outline": "maybe"}, 'bad outline "maybe": must be auto, on, or off'),
        ({"percentdecimals": -1}, "percentdecimals must be at least 0, not -1"),
        ({"percentdecimals": 11}, "percentdecimals must be at most 10, not 11"),
        ({"colors": ["nocolour"]}, 'unknown color name "nocolour"'),
        ({"labels": "perhaps"}, "expected a boolean, not 'perhaps'"),
    ],
)
def test_a_bad_option_is_refused_at_creation_and_in_configure(root, options, message):
    with pytest.raises(tk.TclError, match=f"^{message}$".replace("(", r"\(")):
        Treemap(root, **options)
    tree = Treemap(root)
    with pytest.raises(tk.TclError):
        tree.configure(**options)
    assert tree.cget("values") == "percent"


def test_the_item_methods_are_treeviews(root):
    tree = Treemap(root)
    web = tree.insert("", "end", text="web")
    nginx = tree.insert(web, "end", text="nginx", value=330)
    assert (web, nginx) == ("I001", "I002")
    assert tree.get_children() == (web,)
    assert tree.get_children(web) == (nginx,)
    assert tree.parent(nginx) == web
    assert tree.index(nginx) == 0
    assert tree.exists(nginx)
    assert tree.item(nginx) == {"text": "nginx", "value": 330}
    tree.item(nginx, value=400, text="NGINX")
    assert tree.item(nginx, "value") == 400
    assert tree.item(nginx, "text") == "NGINX"
    tree.move(nginx, "", 0)
    assert tree.get_children() == (nginx, web)
    tree.delete(web)
    assert not tree.exists(web)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda t: t.insert("nosuch", "end"), "Item nosuch not found"),
        (lambda t: t.insert("", "end", "I001"), "Item I001 already exists"),
        (lambda t: t.insert("I002", "end"), "two levels: I002 is already a child"),
        (lambda t: t.insert("", "end", value=-1), "cannot be negative"),
        (lambda t: t.item("nosuch"), "Item nosuch not found"),
        (lambda t: t.item("I001", colour="red"), 'unknown option "-colour"'),
        (lambda t: t.item("I001", "colour"), 'unknown option "-colour"'),
        (lambda t: t.delete("nosuch"), "Item nosuch not found"),
        (lambda t: t.parent("nosuch"), "Item nosuch not found"),
    ],
)
def test_refusals_are_tcl_errors(root, call, message):
    tree = Treemap(root)
    group = tree.insert("", "end")
    tree.insert(group, "end", value=1)
    with pytest.raises(tk.TclError, match=message):
        call(tree)


def test_many_changes_ask_for_one_repaint(root, monkeypatch):
    asked = []
    tree = Treemap(root)
    monkeypatch.setattr(tree, "after_idle", lambda f: asked.append(f) or "after#1")
    tree._pending = None
    for n in range(100):
        tree.insert("", "end", value=n)
    assert len(asked) == 1
    tree._repaint()
    tree.insert("", "end", value=1)
    assert len(asked) == 2


def test_the_natural_size_is_40_by_12(root):
    tree = Treemap(root)
    assert (tree.winfo_reqwidth(), tree.winfo_reqheight()) == (40, 12)
    sized = Treemap(root, width=20, height=5)
    assert (sized.winfo_reqwidth(), sized.winfo_reqheight()) == (20, 5)


def test_values_none_and_value(root):
    tree = Treemap(root, values="value", units="B", digits=3)
    tree.insert("", "end", text="big", value=12345)
    assert any("12.3kB" in line for line in rows(tree._compose(40, 12)))
    tree.configure(values="none")
    tiles = "".join(rows(tree._compose(40, 12))[:-1])  # the readout keeps it
    assert "big" in tiles
    assert "12" not in tiles


def test_labels_off_leaves_the_values(root):
    tree = Treemap(root, labels=False)
    tree.insert("", "end", text="big", value=1)
    first = rows(tree._compose(40, 12))[1]
    assert "big" not in first
    assert "100.00%" in first


def test_the_readout_counts_what_is_too_small(root):
    tree = Treemap(root)
    tree.insert("", "end", value=100000)
    tree.insert("", "end", value=1)
    assert (
        rows(tree._compose(40, 12))[-1].rstrip() == "total 100001 · 1 too small to show"
    )
    tree.configure(readout=False)
    assert "total" not in rows(tree._compose(40, 12))[-1]


def test_a_border_is_left_to_the_frame(root):
    tree = Treemap(root, borderwidth=1)
    tree.insert("", "end", text="all", value=1)
    screen = rows(tree._compose(20, 6))
    # Row 0 and column 0 are the frame's; without colour the tile is
    # outlined, inside them.
    assert screen[0] == " " * 20
    assert screen[1][:4] == " ┌──"
    assert screen[2][:5] == " │all"
