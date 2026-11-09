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

"""Canvas image and bitmap items, measured against Tk 9.0.2 through tkinter."""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from tkcurses import Canvas, Misc, PhotoImage, TclError
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


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


@pytest.fixture
def photo(canvas):
    return PhotoImage(master=canvas, width=10, height=6)


def item_pixels(canvas, ident):
    return canvas._item_pixels(canvas._item(ident))


# ------------------------------------------------------------------ images


def test_an_image_items_defaults_are_tks(canvas):
    item = canvas.create_image(5, 5)
    assert canvas.type(item) == "image"
    assert canvas.itemcget(item, "image") == ""
    assert canvas.itemcget(item, "anchor") == "center"
    assert canvas.itemcget(item, "activeimage") == ""
    assert canvas.itemcget(item, "disabledimage") == ""
    assert canvas.bbox(item) is None


def test_an_image_reads_back_as_its_name(canvas, photo):
    item = canvas.create_image(5, 5, image=photo)
    assert canvas.itemcget(item, "image") == str(photo)


@pytest.mark.parametrize(
    ("anchor", "point", "box"),
    [
        ("center", (50, 50), (45, 47, 55, 53)),
        ("nw", (50, 50), (50, 50, 60, 56)),
        ("se", (51, 51), (41, 45, 51, 51)),
    ],
)
def test_an_image_bbox_is_its_own_size_placed_by_anchor(
    canvas, photo, anchor, point, box
):
    """Measured on Tk 9.0.2 with a 10x6 photo image."""
    item = canvas.create_image(*point, image=photo, anchor=anchor)
    assert canvas.bbox(item) == box


def test_an_image_item_follows_its_image(canvas, photo):
    """Measured: resizing the photo to 20x4 moved the bbox at once."""
    item = canvas.create_image(50, 50, image=photo)
    photo.configure(width=20, height=4)
    assert canvas.bbox(item) == (40, 48, 60, 52)


def test_an_unknown_image_is_refused_in_tks_words(canvas):
    with pytest.raises(TclError, match='image "nosuch" does not exist'):
        canvas.create_image(5, 5, image="nosuch")


def test_a_bad_anchor_is_refused_in_tks_words(canvas):
    message = 'bad anchor "bogus": must be n, ne, e, se, s, sw, w, nw, or center'
    with pytest.raises(TclError, match=re.escape(message)):
        canvas.create_image(5, 5, anchor="bogus")


def test_a_text_items_anchor_is_checked_too(canvas):
    with pytest.raises(TclError, match='bad anchor "up"'):
        canvas.create_text(5, 5, text="x", anchor="up")


def test_an_image_needs_one_point(canvas):
    with pytest.raises(TclError, match="wrong # coordinates"):
        canvas.create_image(5, 5, 6, 6)


def test_an_image_draws_its_pixels_where_it_is_placed(canvas):
    photo = PhotoImage(master=canvas, width=2, height=2)
    photo.put("red", to=(0, 0, 2, 2))
    item = canvas.create_image(4, 6, image=photo, anchor="nw")
    assert item_pixels(canvas, item) == {
        (4, 6): "red",
        (5, 6): "red",
        (4, 7): "red",
        (5, 7): "red",
    }


def test_a_transparent_pixel_draws_nothing(canvas):
    photo = PhotoImage(master=canvas, width=2, height=1)
    photo.put("red", to=(0, 0, 1, 1))
    item = canvas.create_image(0, 0, image=photo, anchor="nw")
    assert set(item_pixels(canvas, item)) == {(0, 0)}


def test_only_the_part_in_view_is_asked_for(canvas):
    photo = PhotoImage(master=canvas, width=200, height=200)
    photo.put("blue", to=(0, 0, 200, 200))
    item = canvas.create_image(0, 0, image=photo, anchor="nw")
    drawn = item_pixels(canvas, item)
    assert max(x for x, _ in drawn) < 40
    assert max(y for _, y in drawn) < 20


def test_a_deleted_image_leaves_nothing_to_draw(canvas):
    photo = PhotoImage(master=canvas, width=2, height=2)
    item = canvas.create_image(5, 5, image=photo)
    canvas.tk.images.pop(str(photo))
    assert item_pixels(canvas, item) == {}
    assert canvas.bbox(item) is None


def test_the_disabled_image_shows_while_the_item_is_disabled(canvas):
    plain = PhotoImage(master=canvas, width=2, height=2)
    plain.put("red", to=(0, 0, 2, 2))
    grey = PhotoImage(master=canvas, width=2, height=2)
    grey.put("gray", to=(0, 0, 2, 2))
    item = canvas.create_image(0, 0, image=plain, disabledimage=grey, anchor="nw")
    assert set(item_pixels(canvas, item).values()) == {"red"}
    canvas.itemconfigure(item, state="disabled")
    assert set(item_pixels(canvas, item).values()) == {"gray"}
    canvas.itemconfigure(item, state="normal")
    canvas.configure(state="disabled")
    # An item's own state wins over the canvas's; "normal" was set.
    assert set(item_pixels(canvas, item).values()) == {"red"}


def test_the_active_image_shows_under_the_pointer(canvas):
    plain = PhotoImage(master=canvas, width=2, height=2)
    plain.put("red", to=(0, 0, 2, 2))
    lit = PhotoImage(master=canvas, width=2, height=2)
    lit.put("yellow", to=(0, 0, 2, 2))
    item = canvas.create_image(0, 0, image=plain, activeimage=lit, anchor="nw")
    canvas._current = item
    assert set(item_pixels(canvas, item).values()) == {"yellow"}
    assert canvas._has_active_look(item)


def test_find_closest_reaches_an_image(canvas):
    photo = PhotoImage(master=canvas, width=4, height=4)
    photo.put("red", to=(0, 0, 4, 4))
    item = canvas.create_image(10, 10, image=photo, anchor="nw")
    assert canvas.find_closest(11, 11) == (item,)


# ----------------------------------------------------------------- bitmaps


def test_a_bitmap_items_defaults_are_tks(canvas):
    item = canvas.create_bitmap(5, 5)
    assert canvas.type(item) == "bitmap"
    assert canvas.itemcget(item, "bitmap") == ""
    assert canvas.itemcget(item, "anchor") == "center"
    assert canvas.itemcget(item, "background") == ""
    assert canvas.bbox(item) is None


def test_an_unknown_bitmap_is_refused_in_tks_words(canvas):
    with pytest.raises(TclError, match='bitmap "nosuch" not defined'):
        canvas.create_bitmap(5, 5, bitmap="nosuch")


def test_a_built_in_bitmap_is_one_cell(canvas):
    item = canvas.create_bitmap(10, 9, bitmap="error")
    assert canvas.itemcget(item, "bitmap") == "error"
    # Pixel row 9 is in cell row 4, which covers pixel rows 8 and 9.
    assert canvas.bbox(item) == (10, 8, 10, 9)


def test_a_built_in_bitmap_draws_its_glyph(canvas):
    canvas.create_bitmap(10, 9, bitmap="warning", anchor="nw")
    painted = {
        (column, row): glyph
        for column, row, glyph, _ in canvas._painted(canvas._text_area(), 0)
    }
    assert painted[(10, 4)] == "⚠"


def test_a_file_bitmap_draws_its_bits(canvas, tmp_path):
    path = tmp_path / "two.xbm"
    path.write_text(
        "#define two_width 2\n#define two_height 1\n"
        "static unsigned char two_bits[] = { 0x01 };\n"
    )
    item = canvas.create_bitmap(3, 4, bitmap=f"@{path}", foreground="red", anchor="nw")
    assert item_pixels(canvas, item) == {(3, 4): "red"}
    assert canvas.bbox(item) == (3, 4, 5, 5)


def test_an_unreadable_bitmap_file_is_refused(canvas, tmp_path):
    with pytest.raises(TclError, match="error reading bitmap file"):
        canvas.create_bitmap(5, 5, bitmap=f"@{tmp_path / 'missing.xbm'}")
