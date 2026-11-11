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

"""``backgroundimage`` and ``tile`` on Frame, Toplevel and the root.

The option checks replay Tcl/Tk 9.0.2, measured through tkinter. Where the
image goes follows ``DrawFrameBackground`` in Tk's tkFrame.c, in pixels: a
cell is one pixel wide and two tall.
"""

from __future__ import annotations

import gc

import pytest

import tkcurses as tk
from tkcurses import _backdrop_cells, ttk
from tkcurses._core.canvas import FULL, LOWER, UPPER


@pytest.fixture
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


def photo(root, width, height, colour="red"):
    image = tk.PhotoImage(master=root, width=width, height=height)
    image.put(colour, to=(0, 0, width, height))
    return image


# ------------------------------------------------------------- the option


def test_it_starts_empty_and_bgimg_is_its_short_spelling(root):
    frame = tk.Frame(root)
    entry = ("backgroundimage", "backgroundImage", "BackgroundImage", "", "")
    assert frame.cget("backgroundimage") == ""
    assert frame.configure("backgroundimage") == entry
    assert frame.configure("bgimg") == entry


def test_an_image_object_is_kept_as_its_name(root):
    image = photo(root, 4, 4)
    frame = tk.Frame(root, bgimg=image)
    assert frame.cget("backgroundimage") == str(image)
    assert frame.cget("bgimg") == str(image)


def test_an_unknown_image_is_refused_and_the_old_one_kept(root):
    image = photo(root, 4, 4)
    frame = tk.Frame(root, backgroundimage=image)
    with pytest.raises(tk.TclError, match='image "nosuch" does not exist'):
        frame.configure(backgroundimage="nosuch")
    assert frame.cget("backgroundimage") == str(image)
    with pytest.raises(tk.TclError, match='image "nosuch" does not exist'):
        tk.Frame(root, backgroundimage="nosuch")
    frame.configure(backgroundimage="")
    assert frame.cget("backgroundimage") == ""


def test_the_toplevel_and_the_root_take_it_and_a_labelframe_does_not(root):
    """Measured: Tk's labelframe has none of the three."""
    image = photo(root, 4, 4)
    assert tk.Toplevel(root, backgroundimage=image).cget("bgimg") == str(image)
    root.configure(bgimg=image)
    assert root.cget("backgroundimage") == str(image)
    for name, value in (("backgroundimage", image), ("bgimg", image), ("tile", 1)):
        with pytest.raises(tk.TclError, match=f'unknown option "-{name}"'):
            tk.LabelFrame(root, **{name: value})
        with pytest.raises(tk.TclError, match=f'unknown option "-{name}"'):
            ttk.Frame(root, **{name: value})
    assert not {"backgroundimage", "tile"} & set(tk.LabelFrame(root).configure())


def test_once_its_image_is_gone_every_configure_is_refused(root):
    """Measured: Tk looks the image up again on any configure that sets
    something, and until the option is cleared nothing changes."""
    image = photo(root, 4, 4)
    name = str(image)
    frame = tk.Frame(root, backgroundimage=image, width=5)
    del image
    gc.collect()
    with pytest.raises(tk.TclError, match=f'image "{name}" does not exist'):
        frame.configure(width=10)
    assert frame.cget("width") == 5
    assert frame.cget("backgroundimage") == name
    assert frame.configure("width")[-1] == 5  # asking is not configuring
    frame.configure(backgroundimage="")
    frame.configure(bg="red", width=10)
    assert frame.cget("width") == 10


def test_tile_is_a_boolean(root):
    frame = tk.Frame(root)
    assert frame.configure("tile") == ("tile", "tile", "Tile", 0, 0)
    frame.configure(tile="yes")
    assert frame.cget("tile") == 1
    with pytest.raises(tk.TclError, match='expected boolean value but got "maybe"'):
        frame.configure(tile="maybe")


# ------------------------------------------------------------ where it goes


def two_colour(root, width, height):
    """Red, with a blue first column, so where a copy starts is visible."""
    image = photo(root, width, height)
    image.put("blue", to=(0, 0, 1, height))
    return image


def test_tiled_copies_start_inside_the_border_and_stop_at_it(root):
    image = two_colour(root, 3, 2)
    cells = _backdrop_cells(image, 9, 4, 1, True)
    # Inside a 1-cell border: columns 1-7, rows 1-2.
    assert set(cells) == {(column, row) for column in range(1, 8) for row in (1, 2)}
    # A copy every three columns from column 1; the last one cut short.
    blue = sorted(
        {column for (column, _), (_, fore, _) in cells.items() if fore == "blue"}
    )
    assert blue == [1, 4, 7]
    assert all(glyph == FULL for glyph, _, _ in cells.values())


def test_a_tiled_image_taller_than_a_cell_repeats_down_the_rows(root):
    image = photo(root, 2, 3)
    image.put("blue", to=(0, 2, 2, 3))  # red, red, blue
    cells = _backdrop_cells(image, 2, 3, 0, True)
    # Pixel rows: r r b r r b -> cells (r/r), (b/r), (r/b).
    assert [cells[(0, row)] for row in range(3)] == [
        (FULL, "red", None),
        (UPPER, "blue", "red"),
        (UPPER, "red", "blue"),
    ]


def test_a_centred_image_that_fits_is_centred_on_the_whole_window(root):
    image = photo(root, 2, 2)
    cells = _backdrop_cells(image, 10, 5, 1, False)
    # (10 - 2) // 2 = 4 across, (10 - 2) // 2 = 4 pixel rows down: cell row 2.
    assert set(cells) == {(4, 2), (5, 2)}


def test_a_centred_image_on_an_odd_pixel_row_is_paired_where_it_lands(root):
    image = photo(root, 1, 3)
    cells = _backdrop_cells(image, 3, 5, 0, False)
    # (10 - 3) // 2 = 3: pixel rows 3, 4 and 5 - half of cell 1, all of 2.
    assert cells == {(1, 1): (LOWER, "red", None), (1, 2): (FULL, "red", None)}


def test_a_centred_image_too_big_keeps_its_middle_inside_the_border(root):
    image = photo(root, 10, 2)
    image.put("blue", to=(3, 0, 4, 2))
    cells = _backdrop_cells(image, 6, 3, 1, False)
    # Four columns inside the border show image columns 3-6.
    assert sorted(column for column, _ in cells) == [1, 2, 3, 4]
    assert cells[(1, 1)][1] == "blue"
    assert all(row == 1 for _, row in cells)


def test_clear_pixels_leave_the_background(root):
    image = tk.PhotoImage(master=root, width=2, height=2)
    image.put("red", to=(0, 0, 1, 1))
    assert _backdrop_cells(image, 2, 1, 0, True) == {(0, 0): (UPPER, "red", None)}


def test_no_room_inside_the_border_is_nothing(root):
    assert _backdrop_cells(photo(root, 2, 2), 2, 2, 1, True) == {}
    assert _backdrop_cells(tk.PhotoImage(master=root), 6, 3, 0, True) == {}
