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

"""Tests for the image classes.

An image is a plane of pixels, and a pixel is one cell wide and half a cell
tall - the same pixel a Canvas draws on. The distinction between an image's
size in **pixels** and the room it needs in **cells** is what most of the
arithmetic here is about, and getting it wrong is the one mistake this
module is really guarding against.

Everything about naming, errors and the shape of the API was measured
against Tk 9.0.2 rather than remembered; the measurements are quoted where
they are not obvious.
"""

from __future__ import annotations

import gc

import pytest

import tkcurses
from tkcurses import BitmapImage, Misc, PhotoImage, TclError
from tkcurses._core.canvas import compose
from tkcurses._core.colors import ColorDepth
from tkcurses._core.images import cells_tall


@pytest.fixture
def root():
    return Misc()


@pytest.fixture(autouse=True)
def _no_leaked_default_root():
    previous = tkcurses._default_root
    yield
    tkcurses._default_root = previous


def art(root, rows, colour="red"):
    """An image from ``#`` art, one colour, holes everywhere else."""
    return PhotoImage(master=root, data=rows, palette={"#": colour})


# ------------------------------------------------------------------ naming


def test_an_image_is_referred_to_by_name(root):
    """Measured: str(p) is 'pyimage1', and a widget holds that string."""
    photo = art(root, ["##"])
    assert str(photo) == photo._name
    assert photo._name.startswith("pyimage")


def test_a_name_can_be_given(root):
    assert str(PhotoImage(master=root, name="banner", data=["##"])) == "banner"


def test_names_do_not_repeat(root):
    assert str(art(root, ["#"])) != str(art(root, ["#"]))


def test_type_is_photo(root):
    assert art(root, ["#"]).type() == "photo"


def test_an_image_is_registered_with_its_application(root):
    photo = art(root, ["#"])
    assert root.tk.images[str(photo)] is photo


def test_an_image_nothing_references_goes_away(root):
    """Tk's famous trap, reproduced deliberately rather than fixed.

    A widget showing a collected image keeps its size and draws nothing,
    which is why every tkinter tutorial says to keep a reference. Code
    written against tkinter is written around this, so the registry is weak.
    """
    name = str(art(root, ["#"]))
    gc.collect()
    assert name not in root.tk.images


def test_image_names_lists_what_is_still_held(root):
    photo = art(root, ["#"])
    assert str(photo) in root.image_names()


def test_image_types_are_the_two_there_are(root):
    assert root.image_types() == ("bitmap", "photo")


def test_two_images_of_a_name_are_equal(root):
    first = PhotoImage(master=root, name="same", data=["#"])
    second = PhotoImage(master=root, name="same", data=["."])
    assert first == second
    assert hash(first) == hash(second)


def test_an_image_is_not_equal_to_other_things(root):
    assert art(root, ["#"]) != "pyimage1"


def test_repr_says_the_size_in_pixels(root):
    assert "2x1" in repr(art(root, ["##"]))


# ---------------------------------------------- pixels, and cells of them


def test_size_is_counted_in_pixels(root):
    photo = art(root, ["###", "###"])
    assert (photo.width(), photo.height()) == (3, 2)


def test_two_pixel_rows_make_one_cell(root):
    """The whole point of sharing the canvas plane."""
    photo = art(root, ["###", "###"])
    assert photo.cell_height() == 1


def test_a_lone_pixel_row_still_needs_a_cell(root):
    photo = art(root, ["###"])
    assert photo.height() == 1
    assert photo.cell_height() == 1


@pytest.mark.parametrize(
    ("rows", "cells"), [(0, 0), (1, 1), (2, 1), (3, 2), (4, 2), (5, 3), (16, 8)]
)
def test_cells_tall_rounds_a_half_cell_up(rows, cells):
    assert cells_tall(rows) == cells


def test_width_is_the_same_in_both_units(root):
    """A pixel is a whole cell wide; only the height is halved."""
    photo = art(root, ["####", "####"])
    assert photo.width() == 4


def test_an_empty_image_has_no_size(root):
    photo = PhotoImage(master=root)
    assert (photo.width(), photo.height(), photo.cell_height()) == (0, 0, 0)


def test_width_and_height_make_a_blank_image(root):
    photo = PhotoImage(master=root, width=4, height=2)
    assert (photo.width(), photo.height()) == (4, 2)
    assert photo.transparency_get(0, 0) is True


def test_rows_given_as_one_string_split_on_newlines(root):
    photo = PhotoImage(master=root, data="##\n##", palette={"#": "red"})
    assert (photo.width(), photo.height()) == (2, 2)


def test_ragged_rows_are_padded_with_holes(root):
    """A short row must not paint out to the length of the longest."""
    photo = art(root, ["###", "#"])
    assert photo.rows() == [["red", "red", "red"], ["red", None, None]]


def test_resizing_keeps_what_overlaps(root):
    photo = art(root, ["###", "###"])
    photo.configure(width=2, height=1)
    assert photo.rows() == [["red", "red"]]


def test_growing_fills_with_holes(root):
    photo = art(root, ["##"])
    photo.configure(width=3, height=2)
    assert photo.rows() == [["red", "red", None], [None, None, None]]


# --------------------------------------------------------------- authoring


def test_characters_stand_for_colours(root):
    """XPM's idea: what a source file can hold legibly."""
    photo = PhotoImage(master=root, data=["ab"], palette={"a": "red", "b": "blue"})
    assert photo.rows() == [["red", "blue"]]


def test_a_character_with_no_palette_entry_is_a_hole(root):
    photo = PhotoImage(master=root, data=["a b"], palette={"a": "red"})
    assert photo.rows() == [["red", None, None]]


def test_rows_of_colours_are_the_literal_plane(root):
    photo = PhotoImage(master=root, data=[["red", "blue"], [None, "green"]])
    assert photo.rows() == [["red", "blue"], [None, "green"]]


def test_without_a_palette_a_space_is_a_hole(root):
    photo = PhotoImage(master=root, data=[["red", " "]])
    assert photo.rows() == [["red", None]]


# ----------------------------------------------------------------- reading


def test_get_answers_in_rgb_as_tk_does(root):
    """Tk returns (r, g, b); so does this, using what the palette renders."""
    assert art(root, ["#"], colour="red").get(0, 0) == (205, 0, 0)


def test_a_pixel_that_paints_nothing_reads_black(root):
    """Measured on Tk: a blanked PhotoImage reads (0, 0, 0) everywhere."""
    photo = art(root, [" "])
    assert photo.get(0, 0) == (0, 0, 0)
    assert photo.transparency_get(0, 0) is True


def test_a_hex_colour_round_trips(root):
    photo = PhotoImage(master=root, data=[["#ff8000"]])
    assert photo.get(0, 0) == (255, 128, 0)


def test_get_outside_the_image_raises_tk_s_error(root):
    photo = PhotoImage(master=root, name="pic", data=["#"], palette={"#": "red"})
    with pytest.raises(TclError, match="pic get: coordinates out of range"):
        photo.get(5, 5)


def test_lit_is_what_compose_takes(root):
    """The plane is shared, so an image composes exactly as a canvas does."""
    photo = art(root, ["##", "##"], colour="cyan")
    assert photo.lit() == {(x, y): "cyan" for x in range(2) for y in range(2)}
    assert compose(photo.lit()) == {
        (0, 0): ("█", "cyan", None),
        (1, 0): ("█", "cyan", None),
    }


def test_lit_leaves_out_the_holes(root):
    """Every earlier lit() test used a fully painted image, where including
    the holes would have changed nothing - so this is the one that says a
    hole is absent rather than present and empty."""
    photo = art(root, ["#.#"], colour="cyan")
    assert photo.lit() == {(0, 0): "cyan", (2, 0): "cyan"}
    assert (1, 0) not in photo.lit()


def test_one_lit_row_composes_to_a_half_block(root):
    photo = art(root, ["#"], colour="cyan")
    assert compose(photo.lit()) == {(0, 0): ("▀", "cyan", None)}


def test_two_colours_in_a_cell_keep_both(root):
    photo = PhotoImage(master=root, data=[["red"], ["blue"]])
    assert compose(photo.lit()) == {(0, 0): ("▀", "red", "blue")}


# ----------------------------------------------------------------- writing


def test_put_one_colour_fills_the_region(root):
    """A plain string is a colour, as in Tk's put('red', to=...)."""
    photo = PhotoImage(master=root, width=3, height=2)
    photo.put("blue", to=(0, 0, 2, 2))
    assert photo.rows() == [["blue", "blue", None], ["blue", "blue", None]]


def test_a_colour_name_is_not_split_into_characters(root):
    """It was once, and painted four holes instead of one colour."""
    photo = PhotoImage(master=root, width=4, height=1)
    photo.put("blue", to=(0, 0, 4, 1))
    assert photo.rows() == [["blue"] * 4]


def test_put_rows_writes_a_block(root):
    photo = PhotoImage(master=root, width=4, height=3, palette={"#": "red"})
    photo.put(["##"], to=(1, 1))
    assert photo.rows()[1] == [None, "red", "red", None]


def test_put_without_a_destination_writes_at_the_origin(root):
    photo = PhotoImage(master=root, width=4, height=2, palette={"#": "red"})
    photo.put(["##"])
    assert photo.rows()[0] == ["red", "red", None, None]


def test_put_tiles_to_fill_a_box(root):
    photo = PhotoImage(master=root, width=4, height=2, palette={"#": "red"})
    photo.put(["#"], to=(0, 0, 3, 2))
    assert photo.rows() == [["red"] * 3 + [None]] * 2


def test_put_clips_at_the_edge(root):
    photo = PhotoImage(master=root, width=2, height=1)
    photo.put("red", to=(1, 0, 9, 9))
    assert photo.rows() == [[None, "red"]]


def test_put_with_the_wrong_number_of_coordinates_raises(root):
    photo = PhotoImage(master=root, width=2, height=1)
    with pytest.raises(TclError, match="wrong # coordinates"):
        photo.put("red", to=(1, 2, 3))


def test_put_nothing_changes_nothing(root):
    photo = art(root, ["##"])
    photo.put([])
    assert photo.rows() == [["red", "red"]]


def test_blank_keeps_the_size_and_clears_the_pixels(root):
    photo = art(root, ["##", "##"])
    photo.blank()
    assert (photo.width(), photo.height()) == (2, 2)
    assert photo.rows() == [[None, None], [None, None]]


def test_transparency_is_a_pixel_that_paints_nothing(root):
    photo = art(root, ["#"])
    assert photo.transparency_get(0, 0) is False
    photo.transparency_set(0, 0, True)
    assert photo.transparency_get(0, 0) is True
    photo.transparency_set(0, 0, False)
    assert photo.transparency_get(0, 0) is False


def test_transparency_outside_the_image_raises(root):
    photo = art(root, ["#"])
    with pytest.raises(TclError, match="coordinates out of range"):
        photo.transparency_set(9, 9, True)


# ----------------------------------------------------------------- copying


def test_copy_is_independent(root):
    photo = art(root, ["##"])
    clone = photo.copy()
    clone.put("blue", to=(0, 0, 1, 1))
    assert photo.rows() == [["red", "red"]]
    assert clone.rows() == [["blue", "red"]]


def test_zoom_repeats_every_pixel(root):
    photo = PhotoImage(master=root, data=[["red", "blue"]])
    assert photo.zoom(2).rows() == [["red", "red", "blue", "blue"]] * 2


def test_zoom_takes_separate_factors(root):
    photo = PhotoImage(master=root, data=[["red", "blue"]])
    assert photo.zoom(2, 1).rows() == [["red", "red", "blue", "blue"]]


def test_zoom_reports_its_new_size_in_both_units(root):
    """Two pixel rows make a cell, so doubling a row fills one."""
    bigger = art(root, ["##"]).zoom(2)
    assert (bigger.width(), bigger.height(), bigger.cell_height()) == (4, 2, 1)


def test_subsample_skips_pixels(root):
    photo = PhotoImage(
        master=root,
        data=["abcd", "efgh", "ijkl", "mnop"],
        palette={c: "red" if c in "acik" else "blue" for c in "abcdefghijklmnop"},
    )
    assert photo.subsample(2).rows() == [["red", "red"], ["red", "red"]]


def test_subsample_takes_separate_factors(root):
    photo = PhotoImage(master=root, data=[["red", "blue", "red", "blue"]])
    assert photo.subsample(2, 1).rows() == [["red", "red"]]


@pytest.mark.parametrize("factor", [0, -1])
def test_scaling_by_a_non_positive_factor_raises(root, factor):
    photo = art(root, ["##"])
    with pytest.raises(TclError, match="must be positive"):
        photo.zoom(factor)
    with pytest.raises(TclError, match="must be positive"):
        photo.subsample(factor)
    with pytest.raises(TclError, match="must be positive"):
        photo.reduce(factor)


# ---------------------------------------------------------------- reducing


def test_reduce_averages_the_block_it_covers(root):
    """Where subsample keeps one pixel of four, this is the mean of all four."""
    photo = PhotoImage(
        master=root, data=[["#000000", "#ffffff"], ["#ffffff", "#000000"]]
    )
    assert photo.reduce(2).rows() == [["#7f7f7f"]]
    # subsample keeps the top-left and knows nothing of the other three.
    assert photo.subsample(2).rows() == [["#000000"]]


def test_reduce_takes_separate_factors(root):
    photo = PhotoImage(
        master=root, data=[["#000000", "#ffffff"], ["#000000", "#ffffff"]]
    )
    assert photo.reduce(2, 1).rows() == [["#7f7f7f"], ["#7f7f7f"]]


def test_reduce_reports_its_new_size_in_both_units(root):
    photo = PhotoImage(master=root, width=12, height=8)
    photo.put("red", to=(0, 0, 12, 8))
    smaller = photo.reduce(2)
    assert (smaller.width(), smaller.height(), smaller.cell_height()) == (6, 4, 2)


def test_reduce_leaves_the_original_alone(root):
    photo = PhotoImage(
        master=root, data=[["#000000", "#ffffff"], ["#ffffff", "#000000"]]
    )
    photo.reduce(2)
    assert photo.rows() == [["#000000", "#ffffff"], ["#ffffff", "#000000"]]


def test_a_block_that_is_mostly_hole_stays_a_hole(root):
    """Or a silhouette grows a fringe of half-lit edges half a block wide."""
    photo = PhotoImage(master=root, data=["#...", "...."], palette={"#": "#ff0000"})
    assert photo.reduce(2).rows() == [[None, None]]


def test_a_block_that_is_mostly_colour_keeps_it(root):
    photo = PhotoImage(master=root, data=["###.", "###."], palette={"#": "#ff0000"})
    assert photo.reduce(2).rows() == [["#ff0000", None]]


def test_reduce_ignores_a_partial_block_at_the_edge(root):
    """Five pixels reduced by two is two blocks, not two and a half."""
    photo = PhotoImage(master=root, width=5, height=5)
    photo.put("red", to=(0, 0, 5, 5))
    assert (photo.reduce(2).width(), photo.reduce(2).height()) == (2, 2)


def test_reduce_by_one_changes_nothing(root):
    photo = PhotoImage(master=root, data=[["#123456", "#abcdef"]])
    assert photo.reduce(1).rows() == [["#123456", "#abcdef"]]


# -------------------------------------------------------------------- files


def test_rows_read_from_a_file(root, tmp_path):
    path = tmp_path / "art.txt"
    path.write_text("##\n#.\n", encoding="utf-8")
    photo = PhotoImage(master=root, file=str(path), palette={"#": "red"})
    assert photo.rows() == [["red", "red"], ["red", None]]


def test_a_missing_file_raises_tk_s_error(root):
    with pytest.raises(TclError, match="couldn't open"):
        PhotoImage(master=root, file="/no/such/art.txt")


def test_the_shape_round_trips_through_a_file(root, tmp_path):
    path = tmp_path / "art.txt"
    art(root, ["##", "# "]).write(str(path))
    photo = PhotoImage(master=root, palette={"#": "red"})
    photo.read(str(path))
    assert photo.rows() == [["red", "red"], ["red", None]]


def test_data_gives_the_shape_when_no_palette_is_named(root):
    assert art(root, ["##", "# "]).data() == ["##", "# "]


def test_data_can_name_a_character_for_each_colour(root):
    photo = PhotoImage(master=root, data=[["red", "blue"]])
    assert photo.data({"red": "R", "blue": "B"}) == ["RB"]


# ------------------------------------------------------------------ options


def test_configure_with_nothing_reports_the_options(root):
    assert art(root, ["##"]).configure()["width"] == 2


def test_cget_reads_one_option(root):
    assert art(root, ["##"]).cget("width") == 2


def test_an_option_can_be_set_by_subscript(root):
    photo = art(root, ["##"])
    photo["foreground"] = "green"
    assert photo["foreground"] == "green"


def test_an_unknown_option_raises(root):
    with pytest.raises(TclError, match='unknown option "-nosuch"'):
        art(root, ["##"]).configure(nosuch=1)


def test_reading_an_unknown_option_raises(root):
    with pytest.raises(TclError, match='unknown option "-nosuch"'):
        art(root, ["##"])["nosuch"]


# ------------------------------------------------------------- telling users


def test_a_watcher_hears_about_a_change(root):
    """Measured: a live Label follows its image's size with no call on it."""
    photo = art(root, ["##"])
    calls = []
    watcher = Misc()
    photo._watch(watcher, lambda: calls.append(1))
    photo.put("blue", to=(0, 0, 1, 1))
    assert calls == [1]
    photo.configure(width=4, height=1)
    assert calls == [1, 1]


def test_a_watcher_can_stop_listening(root):
    photo = art(root, ["##"])
    calls = []
    watcher = Misc()
    photo._watch(watcher, lambda: calls.append(1))
    photo._unwatch(watcher)
    photo.blank()
    assert calls == []


def test_a_collected_watcher_is_forgotten(root):
    """Showing an image must never keep a destroyed widget alive."""
    photo = art(root, ["##"])
    watcher = Misc()
    photo._watch(watcher, lambda: None)
    assert len(photo._users) == 1
    del watcher
    gc.collect()
    assert len(photo._users) == 0


def test_reading_an_image_does_not_tell_anyone(root):
    photo = art(root, ["##"])
    calls = []
    watcher = Misc()
    photo._watch(watcher, lambda: calls.append(1))
    photo.get(0, 0)
    photo.width()
    photo.lit()
    assert calls == []


# -------------------------------------------------------------- BitmapImage


#: A 12-wide bitmap, which is the interesting width: XBM packs each row into
#: whole bytes, so 12 columns take two bytes and four bits of every second
#: byte are padding that has to be dropped, or every row after the first is
#: shifted. The expected rows below were produced by Pillow 12.3.0 decoding
#: this same source, so they are an independent decoder's answer rather than
#: a reading of the format by the code under test.
WIDE_XBM = """#define t_width 12
#define t_height 3
static char t_bits[] = {
0x0f,0x0f, 0xff,0x00, 0x01,0x08};
"""
WIDE_ROWS = ["####....####", "########....", "#..........#"]

SQUARE_XBM = (
    "#define x_width 8\n"
    "#define x_height 4\n"
    "static char x_bits[] = {\n"
    "0xff,0x81,0x81,0xff};\n"
)


def drawn(image, on="#", off="."):
    """The bitmap as rows of text, by whether each pixel paints."""
    return [
        "".join(off if pixel is None else on for pixel in row) for row in image.rows()
    ]


def test_a_bitmap_reports_its_type(root):
    assert BitmapImage(master=root, data=SQUARE_XBM).type() == "bitmap"


def test_xbm_dimensions_are_read_from_the_defines(root):
    bitmap = BitmapImage(master=root, data=SQUARE_XBM)
    assert (bitmap.width(), bitmap.height()) == (8, 4)


def test_a_bitmap_is_measured_in_the_same_pixels(root):
    """8x4 pixels is 8 cells across and 2 down, like any other image."""
    assert BitmapImage(master=root, data=SQUARE_XBM).cell_height() == 2


def test_xbm_bits_are_least_significant_first(root):
    """0xff is a full row; 0x81 is only the two ends."""
    bitmap = BitmapImage(master=root, data=SQUARE_XBM)
    assert drawn(bitmap) == ["########", "#......#", "#......#", "########"]


def test_a_row_is_padded_to_whole_bytes(root):
    """Verified against Pillow decoding the same source."""
    assert drawn(BitmapImage(master=root, data=WIDE_XBM)) == WIDE_ROWS


def test_a_set_bit_takes_the_foreground_colour(root):
    bitmap = BitmapImage(master=root, data=SQUARE_XBM, foreground="cyan")
    assert bitmap.rows()[0] == ["cyan"] * 8


def test_a_clear_bit_is_a_hole_unless_a_background_is_named(root):
    plain = BitmapImage(master=root, data=SQUARE_XBM)
    assert plain.rows()[1][1] is None
    filled = BitmapImage(master=root, data=SQUARE_XBM, background="blue")
    assert filled.rows()[1][1] == "blue"


def test_plain_text_rows_are_accepted_too(root):
    """Not everything worth drawing is worth writing as hexadecimal."""
    bitmap = BitmapImage(master=root, data=["X.X", ".X."])
    assert drawn(bitmap) == ["#.#", ".#."]


def test_colours_are_kept(root):
    bitmap = BitmapImage(
        master=root, data=SQUARE_XBM, foreground="red", background="blue"
    )
    assert bitmap["foreground"] == "red"
    assert bitmap["background"] == "blue"


def test_a_bitmap_has_no_cget(root):
    """tkinter's own asymmetry, measured: Image defines only config,
    configure, height, type and width, and cget is PhotoImage's alone."""
    assert not hasattr(BitmapImage(master=root, data=SQUARE_XBM), "cget")
    assert hasattr(art(root, ["#"]), "cget")


def test_a_bitmap_reads_from_a_file(root, tmp_path):
    path = tmp_path / "shape.xbm"
    path.write_text(SQUARE_XBM, encoding="utf-8")
    assert drawn(BitmapImage(master=root, file=str(path)))[0] == "########"


def test_a_missing_bitmap_file_raises(root):
    with pytest.raises(TclError, match="couldn't read bitmap file"):
        BitmapImage(master=root, file="/no/such/shape.xbm")


@pytest.mark.parametrize(
    "bad",
    [
        "#define x_width 8\nstatic char x_bits[] = {0xff};",
        "#define x_width 8\n#define x_height 4\n",
        "#define x_width 8\n#define x_height 4\nstatic char x_bits[] = {0xff};",
        "#define x_width 8\n#define x_height 1\nstatic char x_bits[] = {zz};",
    ],
    ids=["no height", "no data", "too few bytes", "not numbers"],
)
def test_broken_xbm_raises_tk_s_error(root, bad):
    with pytest.raises(TclError, match="format error in bitmap data"):
        BitmapImage(master=root, data=bad)


def test_a_bitmap_tells_its_users_when_it_changes(root):
    bitmap = BitmapImage(master=root, data=SQUARE_XBM)
    calls = []
    watcher = Misc()
    bitmap._watch(watcher, lambda: calls.append(1))
    bitmap.configure(foreground="blue")
    assert calls == [1]


def test_changing_the_colours_recolours_the_same_bits(root):
    bitmap = BitmapImage(master=root, data=SQUARE_XBM, foreground="red")
    bitmap.configure(foreground="green")
    assert bitmap.rows()[0] == ["green"] * 8


# --------------------------------------------------------------- dithering


def colours_of(image):
    return {pixel for row in image.rows() for pixel in row if pixel}


def test_dithering_spreads_a_colour_the_palette_cannot_hold(root):
    """One unavailable colour becomes a mix that averages back to it."""
    photo = PhotoImage(master=root, width=8, height=8)
    photo.put("#804020", to=(0, 0, 8, 8))
    assert len(colours_of(photo)) == 1
    spread = photo.dither(ColorDepth.BASIC)
    assert len(colours_of(spread)) > 1, "a flat unavailable colour must break up"


def test_dithering_leaves_an_available_colour_alone(root):
    """Self-limiting: no error means no diffusion.

    A pixel the palette holds exactly accumulates nothing to pass on, so an
    image already made of available colours comes back unchanged. This is
    what makes dithering safe to apply without asking whether it will help.
    """
    photo = PhotoImage(master=root, width=6, height=6)
    photo.put("#cd0000", to=(0, 0, 6, 6))  # exactly the 8-colour red
    assert colours_of(photo.dither(ColorDepth.BASIC)) == {"#cd0000"}


def test_truecolor_dithers_nothing(root):
    """Every colour is available, so there is no error to spread."""
    photo = PhotoImage(master=root, data=[["#123456", "#abcdef"]])
    assert photo.dither(ColorDepth.DIRECT).rows() == photo.rows()


def test_dithering_keeps_the_size(root):
    photo = PhotoImage(master=root, width=9, height=7)
    photo.put("#336699", to=(0, 0, 9, 7))
    spread = photo.dither(ColorDepth.BASIC)
    assert (spread.width(), spread.height()) == (9, 7)


def test_dithering_leaves_the_original_alone(root):
    photo = PhotoImage(master=root, width=4, height=4)
    photo.put("#804020", to=(0, 0, 4, 4))
    photo.dither(ColorDepth.BASIC)
    assert colours_of(photo) == {"#804020"}


def test_a_hole_stays_a_hole_and_spreads_no_error(root):
    """Transparency is not a colour, so it takes no part in the diffusion."""
    photo = PhotoImage(master=root, width=4, height=4)
    photo.put("#804020", to=(0, 0, 4, 4))
    photo.transparency_set(1, 1, True)
    spread = photo.dither(ColorDepth.BASIC)
    assert spread.transparency_get(1, 1) is True


def test_every_dithered_pixel_is_a_colour_the_terminal_has(root):
    """The whole point: nothing is left that still needs approximating."""
    photo = PhotoImage(master=root, width=12, height=12)
    for x in range(12):
        photo.put(f"#{x * 20:02x}3060", to=(x, 0, x + 1, 12))
    spread = photo.dither(ColorDepth.EXTENDED)
    from tkcurses._core.colors import _resolve_rgb, rgb_of_number

    for spec in colours_of(spread):
        rgb = tuple(int(spec[i : i + 2], 16) for i in (1, 3, 5))
        shown = rgb_of_number(
            _resolve_rgb(rgb, ColorDepth.EXTENDED).color, ColorDepth.EXTENDED
        )
        assert shown == rgb, f"{spec} still needs approximating"


def test_dithering_a_gradient_beats_matching_it_pixel_by_pixel(root):
    """Measured on the real thing, this is 10.32 against 2.93.

    Here it is a synthetic ramp, scored the same way: compare against the
    source after blurring, which is roughly what an eye does over a few
    cells. Per-pixel matching bands; dithering does not.
    """
    from tkcurses._core.colors import _resolve_rgb, rgb_of_number

    width = 48
    photo = PhotoImage(master=root, width=width, height=12)
    for x in range(width):
        level = x * 255 // (width - 1)
        photo.put(f"#{level:02x}{level:02x}{level:02x}", to=(x, 0, x + 1, 12))

    def as_rgb(image):
        return [
            [tuple(int(c[i : i + 2], 16) for i in (1, 3, 5)) for c in row]
            for row in image.rows()
        ]

    def matched(image):
        cache = {}
        rows = []
        for row in as_rgb(image):
            line = []
            for pixel in row:
                if pixel not in cache:
                    cache[pixel] = (
                        rgb_of_number(
                            _resolve_rgb(pixel, ColorDepth.BASIC).color,
                            ColorDepth.BASIC,
                        )
                        or pixel
                    )
                line.append(cache[pixel])
            rows.append(line)
        return rows

    def blurred(rows, k=4):
        return [
            [
                tuple(
                    sum(rows[y + dy][x + dx][i] for dy in range(k) for dx in range(k))
                    // (k * k)
                    for i in range(3)
                )
                for x in range(0, len(rows[0]) - k + 1, k)
            ]
            for y in range(0, len(rows) - k + 1, k)
        ]

    def error(rows, reference):
        total = count = 0
        for a, b in zip(rows, reference, strict=False):
            for one, two in zip(a, b, strict=False):
                for i in range(3):
                    total += (one[i] - two[i]) ** 2
                    count += 1
        return (total / count) ** 0.5

    reference = blurred(as_rgb(photo))
    plain = error(blurred(matched(photo)), reference)
    spread = error(blurred(as_rgb(photo.dither(ColorDepth.BASIC))), reference)
    assert spread < plain / 2, (
        f"dithering {spread:.1f} should beat matching {plain:.1f}"
    )
