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
    assert str(PhotoImage(master=root, name="banner", data=[["red"]])) == "banner"


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
    assert root.image_types() == ("photo", "bitmap")


def test_two_images_of_a_name_are_equal(root):
    first = PhotoImage(master=root, name="same", data=[["red"]])
    second = PhotoImage(master=root, name="same", data=[["blue"]])
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


def test_put_with_too_many_coordinates_raises(root):
    """Three are taken as Tk takes them, the third standing for the fourth."""
    photo = PhotoImage(master=root, width=3, height=3)
    photo.put("red", to=(1, 1, 2))
    assert photo.rows()[1] == [None, "red", None]
    with pytest.raises(TclError):
        photo.put("red", to=(1, 1, 2, 2, 3))


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


# ---------------------------------------------------------- copy_replace
#
# Every expectation below was produced by Tk 9.0.2 through tkinter, from the
# same three-by-two source, and transcribed: R red, B blue, . a hole. The
# table is the record; photo(n) leaves most of these rules out.


def _letters(photo):
    names = {"red": "R", "blue": "B", None: "."}
    return "|".join("".join(names[pixel] for pixel in row) for row in photo.rows())


@pytest.fixture
def source(root):
    """BRR over RR., the source every measurement was taken from."""
    return PhotoImage(master=root, data=[["blue", "red", "red"], ["red", "red", None]])


def _unsized(root, width, height):
    return PhotoImage(master=root, data=[["blue"] * width] * height)


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({}, "BRR|RR."),
        ({"to": (2, 1)}, ".....|..BRR|..RR."),
        ({"to": (0, 0, 5, 3)}, "BRRBR|RR.RR|BRRBR"),
        ({"to": (1,)}, "....|.BRR|.RR."),
        ({"to": (0, 0, 1)}, "B"),
        ({"from_coords": (1, 0)}, "RR|R."),
        ({"from_coords": (1,)}, "R."),
        ({"from_coords": (1, 0, 2, 2)}, "R|R"),
        ({"from_coords": (2, 2, 1, 0)}, "R|R"),
        ({"from_coords": (0, 0, 1)}, "B"),
        ({"zoom": 2}, "BBRRRR|BBRRRR|RRRR..|RRRR.."),
        ({"zoom": (2, 1)}, "BBRRRR|RRRR.."),
        ({"subsample": 2}, "BR"),
        ({"subsample": -1}, ".RR|RRB"),
        ({"subsample": (-1, 1)}, "RRB|.RR"),
        ({"subsample": 0}, ""),
        ({"subsample": 2, "zoom": 3}, "BBBRRR|BBBRRR|BBBRRR"),
    ],
)
def test_copy_replace_into_an_empty_image(root, source, options, expected):
    dest = PhotoImage(master=root)
    dest.copy_replace(source, **options)
    assert _letters(dest) == expected


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({}, "BRRB|RRBB|BBBB|BBBB"),
        ({"shrink": True}, "BRR|RRB"),
        ({"shrink": True, "to": (1, 1)}, "BBBB|BBRR|BRRB"),
    ],
)
def test_an_unsized_image_grows_and_shrink_trims_it(root, source, options, expected):
    dest = _unsized(root, 4, 4)
    dest.copy_replace(source, **options)
    assert _letters(dest) == expected


@pytest.mark.parametrize("shrink", [False, True])
def test_an_image_given_a_size_keeps_it_and_clips(root, source, shrink):
    dest = PhotoImage(master=root, width=2, height=2)
    dest.put("blue", to=(0, 0, 2, 2))
    dest.copy_replace(source, shrink=shrink)
    assert _letters(dest) == "BR|RR"


def test_overlay_shows_the_destination_through_the_holes(root, source):
    dest = _unsized(root, 3, 2)
    dest.copy_replace(source)
    assert _letters(dest) == "BRR|RRB"


def test_set_copies_the_holes_too(root, source):
    dest = _unsized(root, 3, 2)
    dest.copy_replace(source, compositingrule="set")
    assert _letters(dest) == "BRR|RR."


def test_copy_replace_takes_a_source_by_name(root, source):
    dest = PhotoImage(master=root)
    dest.copy_replace(str(source))
    assert _letters(dest) == "BRR|RR."


def test_an_image_can_be_copied_onto_itself(root, source):
    """The region is read before anything is written - measured, BBRR|RRR."""
    source.copy_replace(source, to=(1, 0))
    assert _letters(source) == "BBRR|RRR."


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"from_coords": (0, 0, 9, 9)}, "extend outside source image"),
        ({"from_coords": (-1, 0)}, "-from option must be non-negative"),
        ({"to": (-1, 0)}, "-to option must be non-negative"),
        ({"from_coords": ()}, '"-from" option requires one to four integer'),
        ({"to": ()}, '"-to" option requires one to four integer'),
        ({"subsample": ()}, '"-subsample" option requires one or two integer'),
        (
            {"from_coords": (0, 0, 1, 1, 1)},
            r"wrong # args: should be \"pyimage\d+ copy",
        ),
        ({"zoom": (1, 2, 3)}, r"wrong # args: should be \"pyimage\d+ copy"),
        ({"zoom": 0}, "-zoom option must be positive"),
        ({"compositingrule": "xor"}, 'bad compositing rule "xor"'),
    ],
)
def test_copy_replace_refuses_what_tk_refuses(root, source, options, message):
    dest = PhotoImage(master=root)
    with pytest.raises(TclError, match=message):
        dest.copy_replace(source, **options)
    assert dest.rows() == [], "a refused copy must change nothing"


def test_copy_replace_refuses_a_name_that_is_no_photo(root):
    with pytest.raises(TclError, match='image "nosuch" does not exist'):
        PhotoImage(master=root).copy_replace("nosuch")


def test_copy_replace_tells_the_widgets_showing_it(root, source):
    dest = PhotoImage(master=root)
    told = []
    dest._watch(root, lambda: told.append(True))
    dest.copy_replace(source)
    assert told


def test_copy_zoom_and_subsample_take_a_region(root, source):
    """Python 3.13's keywords, which reach copy_replace as tkinter's do."""
    assert _letters(source.copy(from_coords=(1, 0))) == "RR|R."
    assert _letters(source.zoom(2, from_coords=(0, 0, 1, 1))) == "BB|BB"
    assert _letters(source.subsample(2, from_coords=(1, 0))) == "R"


# ---------------------------------------------------------------- reducing


def test_reduce_averages_the_block_it_covers(root):
    """Where subsample keeps one pixel of four, this is the mean of all four.

    Half black and half white averages to ``#bcbcbc``, 188, and NOT to the
    ``#7f7f7f`` this test asserted for a long time. 127 is the mean of the
    two *bytes*; 188 is the byte of the mean *light*. sRGB carries roughly a
    2.2 gamma, so those are different numbers and only the second is what a
    camera pointed at the checkerboard would record.

    Getting this wrong darkens every edge in a shrunken picture - measured at
    14.69 levels mean and 74 worst on mickey.gif. TkCurses-wn3.
    """
    photo = PhotoImage(
        master=root, data=[["#000000", "#ffffff"], ["#ffffff", "#000000"]]
    )
    assert photo.reduce(2).rows() == [["#bcbcbc"]]
    # subsample keeps the top-left and knows nothing of the other three.
    assert photo.subsample(2).rows() == [["#000000"]]


def test_reduce_averages_light_rather_than_bytes(root):
    """The same rule stated on its own, because it is easy to 'fix' back.

    A block that is nine tenths black is still much darker than mid grey;
    what the gamma changes is where the middle sits, not the direction.
    """
    photo = PhotoImage(master=root, data=[["#000000"] * 9 + ["#ffffff"]])
    only = photo.reduce(10, 1).rows()[0][0]
    # A tenth of full light is 0.1 linear, and 1.055 * 0.1**(1/2.4) - 0.055
    # is 0.349, so 89 - which is 0x59. Averaging the bytes would give 0x19.
    assert only == "#595959", (
        f"one white pixel in ten came out {only!r}; averaging the bytes would "
        "give #191919, which is far too dark for a tenth of full light"
    )


def test_reduce_takes_separate_factors(root):
    photo = PhotoImage(
        master=root, data=[["#000000", "#ffffff"], ["#000000", "#ffffff"]]
    )
    assert photo.reduce(2, 1).rows() == [["#bcbcbc"], ["#bcbcbc"]]


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
    art(root, ["##", "# "]).write(str(path), palette={})
    photo = PhotoImage(master=root, palette={"#": "red"})
    photo.read(str(path))
    assert photo.rows() == [["red", "red"], ["red", None]]


def test_data_gives_the_shape_when_the_palette_is_empty(root):
    assert art(root, ["##", "# "]).data(palette={}) == ["##", "# "]


def test_data_can_name_a_character_for_each_colour(root):
    photo = PhotoImage(master=root, data=[["red", "blue"]])
    assert photo.data(palette={"red": "R", "blue": "B"}) == ["RB"]


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


# ------------------------------------------------- a palette of its own


def rainbow(root, width, height, step=1):
    """A picture whose pixels walk the colour cube, for palette tests."""
    art = PhotoImage(master=root, width=width, height=height)
    for y in range(height):
        for x in range(width):
            index = (y * width + x) * step
            art.put(
                f"#{index % 256:02x}{(index * 5) % 256:02x}{(index * 11) % 256:02x}",
                to=(x, y, x + 1, y + 1),
            )
    return art


def test_quantize_holds_the_palette_to_the_number_asked_for(root):
    art = rainbow(root, 12, 12)
    assert len(colours_of(art)) > 16
    assert len(colours_of(art.quantize(16))) <= 16


def test_quantize_leaves_an_image_that_already_fits_alone(root):
    """Flat art never needed this, and must not be damaged by it."""
    art = PhotoImage(master=root, width=4, height=4)
    art.put("red", to=(0, 0, 4, 2))
    art.put("blue", to=(0, 2, 4, 4))
    assert art.quantize(16).rows() == art.rows()


def test_quantize_keeps_holes_as_holes(root):
    """A hole is not a colour, so it must not be given one.

    Read through rows() rather than get(), which answers black for an unset
    pixel exactly as Tk's does - so it cannot tell a hole from a black one.
    """
    art = rainbow(root, 8, 4)
    art.put("red", to=(0, 0, 8, 1))  # something to quantise alongside
    for x in range(8):
        art.transparency_set(x, 3, True)
    quantised = art.quantize(2)
    assert len(colours_of(art)) > 2, "the picture has to need quantising"
    assert quantised.rows()[3] == [None] * 8


def test_quantize_keeps_the_colour_that_covers_the_picture(root):
    """A colour most of the picture is made of must survive the cut.

    Deliberately NOT a test of where the box is split. Both the median-pixel
    split this uses and the median-colour one it was compared against keep a
    dominant colour, because the representative is a pixel-weighted average
    either way - a first version of this test claimed to prove median-pixel
    was necessary and passed just as happily without it. What is asserted
    here is the property that actually holds and that callers rely on.
    """
    art = PhotoImage(master=root, width=10, height=10)
    art.put("#c80000", to=(0, 0, 10, 10))
    for x in range(5):
        art.put(f"#0000{0x40 + x * 8:02x}", to=(x, 0, x + 1, 1))
    red, green, blue = art.quantize(2).get(0, 5)
    assert (red, green, blue) == pytest.approx((200, 0, 0), abs=6), (
        f"95 of 100 pixels are #c80000 and came back as "
        f"{(red, green, blue)!r}; the palette was spent elsewhere"
    )


def test_the_stand_in_colour_is_weighted_by_how_many_pixels_it_covers(root):
    """One entry for two colours must land near the one that is mostly there.

    ``quantize(1)`` is what makes this sharp: it forces both colours into the
    same box, so the representative is the average and the weighting is the
    whole of what is being tested. The previous test cannot do this job -
    with two entries the colours land in boxes of their own, where a weighted
    and an unweighted average agree exactly.

    Nine tenths red, one tenth blue: weighted gives about (229, 0, 25), a
    plain mean gives (127, 0, 127).
    """
    art = PhotoImage(master=root, width=10, height=10)
    art.put("#ff0000", to=(0, 0, 10, 9))
    art.put("#0000ff", to=(0, 9, 10, 10))
    red, green, blue = art.quantize(1).get(0, 0)
    assert red > 200 and blue < 60, (
        f"the single palette entry came back as {(red, green, blue)!r}; the "
        "picture is nine tenths red, so an unweighted mean was taken"
    )


def test_quantize_refuses_a_palette_of_nothing(root):
    with pytest.raises(TclError):
        rainbow(root, 4, 4).quantize(0)


# ----------------------------------------------- sizing to a pair budget


def test_pairs_needed_counts_combinations_not_colours(root):
    """A pair is (fg, bg), so the two numbers are different on purpose.

    The foregrounds must be the SAME in both cells and the backgrounds
    different, or counting foregrounds gives the right answer by accident -
    which is exactly what the first version of this test did.
    """
    art = PhotoImage(master=root, width=2, height=2)
    art.put("red", to=(0, 0, 1, 1))
    art.put("blue", to=(0, 1, 1, 2))
    art.put("red", to=(1, 0, 2, 1))
    art.put("green", to=(1, 1, 2, 2))
    # One foreground, two backgrounds: red over blue and red over green.
    assert {fore for _, fore, _ in compose(art.lit()).values()} == {"red"}
    assert art.pairs_needed() == 2


def test_fit_pairs_brings_a_picture_under_the_budget(root):
    art = rainbow(root, 20, 20)
    assert art.pairs_needed() > 40
    assert art.fit_pairs(40).pairs_needed() <= 40


def test_fit_pairs_spends_as_much_of_the_budget_as_it_can(root):
    """Reducing further than necessary throws away colour for nothing."""
    art = rainbow(root, 20, 20)
    fitted = art.fit_pairs(60)
    assert fitted.pairs_needed() > 30, (
        f"only {fitted.pairs_needed()} pairs used of a 60 budget, which means "
        "the search stopped well short of what would have fitted"
    )


def test_fit_pairs_leaves_a_picture_that_already_fits_untouched(root):
    art = PhotoImage(master=root, width=4, height=4)
    art.put("red", to=(0, 0, 4, 4))
    assert art.fit_pairs(255).rows() == art.rows()


def test_fit_pairs_refuses_a_budget_of_nothing(root):
    with pytest.raises(TclError):
        rainbow(root, 8, 8).fit_pairs(0)


def test_fit_pairs_survives_a_budget_of_one(root):
    """The smallest budget that is still a budget, rather than an error."""
    fitted = rainbow(root, 12, 12).fit_pairs(1)
    assert fitted.pairs_needed() <= 1


def test_fit_pairs_does_not_rebuild_the_palette_for_every_probe(root, monkeypatch):
    """The cut is grown once, not restarted for each candidate size.

    The first version binary-searched the palette size and rebuilt the whole
    median cut for every probe. The splits are identical every time, so it
    did the same work ten times over: measured at 8.7 SECONDS for one
    photograph, against 200ms once it grew the palette a colour at a time.

    Counted rather than timed, so a slow runner cannot make it flake. A
    rebuilding implementation performs O(k) splits per probe and so lands
    far above the palette it settles on; growing performs O(k) in total.
    """
    from tkcurses._core import images

    splits = 0
    real = images._split_once

    def counted(boxes):
        nonlocal splits
        splits += 1
        return real(boxes)

    monkeypatch.setattr(images, "_split_once", counted)
    art = rainbow(root, 40, 40)
    fitted = art.fit_pairs(120)
    colours = len(colours_of(fitted))
    assert splits < colours * 4 + 40, (
        f"{splits} splits to settle on {colours} colours; the palette is "
        "being rebuilt for each candidate size rather than grown"
    )


# ------------------------------------------------ resampling to a size


def test_resize_gives_exactly_the_size_asked_for(root):
    """The point of it. reduce() gives whatever a whole factor happens to."""
    art = rainbow(root, 32, 20)
    out = art.resize(13, 7)
    assert (out.width(), out.height()) == (13, 7)


def test_resize_handles_a_ratio_no_whole_number_could(root):
    """320 into 106 is 3.019 per pixel, which reduce(3) cannot express.

    reduce(3) on a 320-wide picture gives 106 columns covering 318 pixels and
    drops the last two; the grid drifts across the picture as it goes. This
    covers all 320.
    """
    art = rainbow(root, 320, 20)
    out = art.resize(106, 7)
    assert out.width() == 106
    # The last output column must be built from the last input column, which
    # is exactly what the dropped remainder would lose.
    art.put("#ff00ff", to=(319, 0, 320, 20))
    marked = art.resize(106, 7)
    assert marked.rows()[0][-1] != out.rows()[0][-1], (
        "changing the last input column changed nothing in the output, so "
        "the right-hand edge of the picture is being discarded"
    )


def test_resize_averages_the_fraction_of_each_pixel_it_covers(root):
    """Half a black pixel and half a white one is the mean of the two lights."""
    art = PhotoImage(master=root, data=[["#000000", "#ffffff"]])
    # One output pixel covering both inputs equally.
    assert art.resize(1, 1).rows() == [["#bcbcbc"]]


def test_resize_weights_by_how_much_of_each_pixel_is_covered(root):
    """Not a plain mean of whichever pixels are touched.

    Three inputs into two outputs: the first output covers all of input 0 and
    half of input 1, so it must be weighted 2:1, not 1:1.
    """
    art = PhotoImage(master=root, data=[["#000000", "#000000", "#ffffff"]])
    first, second = art.resize(2, 1).rows()[0]
    assert first == "#000000", "the first output covers only black"
    assert second != "#ffffff", "the second output covers half a black pixel"


def test_resize_keeps_a_mostly_hole_block_a_hole(root):
    art = PhotoImage(master=root, width=4, height=2)
    art.put("red", to=(0, 0, 1, 1))
    assert art.resize(2, 1).rows()[0][1] is None


def test_resize_can_enlarge(root):
    art = PhotoImage(master=root, data=[["#ff0000", "#00ff00"]])
    out = art.resize(4, 2)
    assert (out.width(), out.height()) == (4, 2)
    assert out.rows()[0][0] == "#ff0000"
    assert out.rows()[0][-1] == "#00ff00"


def test_resize_refuses_a_size_of_nothing(root):
    for width, height in ((0, 4), (4, 0), (-1, 4)):
        with pytest.raises(TclError):
            rainbow(root, 8, 8).resize(width, height)


def test_resize_is_not_a_pixel_by_pixel_hex_parse(root):
    """Colours are converted once each, not once per visit.

    A pixel on a block boundary is looked at by several output pixels, and
    parsing its hex every time was most of the cost - 231ms against 32ms for
    one photograph. Counted rather than timed so a slow runner cannot flake.
    """
    from tkcurses._core import images

    calls = 0
    real = images.rgb_of

    def counted(spec):
        nonlocal calls
        calls += 1
        return real(spec)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(images, "rgb_of", counted)
    try:
        art = rainbow(root, 60, 40, step=1)
        distinct = len(colours_of(art))
        art.resize(20, 12)
    finally:
        monkeypatch.undo()
    assert calls <= distinct + 5, (
        f"{calls} colour conversions for {distinct} distinct colours; they "
        "are being re-parsed per visit rather than once each"
    )


def test_pairs_needed_counts_what_the_terminal_will_resolve_to(root):
    """The stored combinations are not the ones the terminal allocates.

    A picture holds hex colours; a terminal with eight of them lands the lot
    on at most sixty-four combinations. Counting the stored ones made
    fit_pairs believe an eight-colour terminal was eighteen hundred pairs
    short - so it crushed the picture to five colours and threw away three
    quarters of what that terminal could have shown.
    """
    art = rainbow(root, 60, 40)
    stored = art.pairs_needed(ColorDepth.DIRECT)
    eight = art.pairs_needed(ColorDepth.BASIC)
    assert stored > 200, "the fixture needs plenty of distinct combinations"
    assert eight <= 64, (
        f"{eight} pairs claimed for an eight-colour terminal, which has at "
        "most 8x8 of them"
    )
    assert eight < stored / 4


def test_pairs_needed_rises_with_the_palette(root):
    """More colours, more distinct combinations - in that order."""
    art = rainbow(root, 60, 40)
    counts = [
        art.pairs_needed(depth)
        for depth in (
            ColorDepth.BASIC,
            ColorDepth.BRIGHT,
            ColorDepth.EXTENDED,
            ColorDepth.DIRECT,
        )
    ]
    assert counts == sorted(counts), counts
    assert counts[0] < counts[-1]


def test_fit_pairs_leaves_a_picture_alone_when_the_palette_already_fits(root):
    """Eight colours cannot need more than sixty-four pairs, so nothing to do.

    This is the check that would have caught the reported bug: at eight
    colours the picture came back with five colours where it should have
    come back untouched.
    """
    art = rainbow(root, 60, 40)
    fitted = art.fit_pairs(55, depth=ColorDepth.BASIC)
    assert fitted.rows() == art.rows(), (
        f"the picture was cut down to {len(colours_of(fitted))} colours for "
        "an eight-colour terminal that had room for it as it was"
    )
