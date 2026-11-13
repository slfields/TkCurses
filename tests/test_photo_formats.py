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

"""PhotoImage's ``data``, ``read``, ``write`` and ``put`` in Tk's formats.

Every expectation was measured on Tk 9.0.2 through tkinter. The image most
of them use is three pixels by two: red but for a blue at the top right and
an olive below it, with the middle of the bottom row never painted.
"""

from __future__ import annotations

import base64
import tkinter

import pytest

import tkcurses as tk
from tkcurses._core.errors import TclError

RED, BLUE, OLIVE, NONE = "#ff0000", "#0000ff", "#808000", "#000000"


@pytest.fixture
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


@pytest.fixture
def photo(root):
    image = tk.PhotoImage(width=3, height=2)
    image.put("red", to=(0, 0, 2, 2))
    image.put("blue", to=(2, 0, 3, 1))
    image.put("#808000", to=(2, 1, 3, 2))
    image.transparency_set(1, 1, True)
    return image


def colours(image):
    return image.data()


# ------------------------------------------------------------------ data


def test_data_is_rows_of_hex_colours(photo):
    """A name is the colour it names, and a hole is black."""
    assert photo.data() == (f"{RED} {RED} {BLUE}", f"{RED} {NONE} {OLIVE}")


def test_data_fills_the_holes_with_a_background(photo):
    assert photo.data(background="green")[1] == f"{RED} #008000 {OLIVE}"


def test_data_in_grey_is_tks_grey(photo):
    """(11r + 16g + 5b + 16) >> 5, from tkImgPhoto.c."""
    assert photo.data(grayscale=True) == (
        "#585858 #585858 #282828",
        f"#585858 {NONE} #6c6c6c",
    )


@pytest.mark.parametrize(
    ("region", "rows"),
    [((1, 1), (f"{NONE} {OLIVE}",)),
     ((0, 0, 1, 1), (RED,)),
     ((2, 2, 0, 0), (f"{RED} {RED}", f"{RED} {NONE}"))],
)  # fmt: skip
def test_data_takes_a_region(photo, region, rows):
    assert photo.data(from_coords=region) == rows


def test_a_region_outside_the_image_is_refused(photo):
    with pytest.raises(TclError, match="extend outside image"):
        photo.data(from_coords=(0, 0, 9, 9))


def test_data_in_tks_default_format_is_one_list(photo):
    assert photo.data("default") == (
        b"{#ff0000 #ff0000 #0000ff} {#ff0000 #000000 #808000}"
    )


@pytest.mark.parametrize(
    ("format", "magic"),
    [("png", b"\x89PNG\r\n\x1a\n"), ("gif", b"GIF89a"), ("PPM", b"P6\n3 2\n255\n"),
     ("gif -index 0", b"GIF89a")],
)  # fmt: skip
def test_data_in_a_file_format_is_its_bytes(photo, format, magic):
    assert photo.data(format).startswith(magic)


def test_a_ppm_has_no_holes(photo):
    assert photo.data("ppm") == (
        b"P6\n3 2\n255\n"
        b"\xff\x00\x00\xff\x00\x00\x00\x00\xff"
        b"\xff\x00\x00\x00\x00\x00\x80\x80\x00"
    )


@pytest.mark.parametrize("format", ["png", "gif"])
def test_png_and_gif_keep_the_holes(root, photo, format):
    again = tk.PhotoImage(data=photo.data(format))
    assert again.data() == photo.data()
    assert again.transparency_get(1, 1)


def test_data_refuses_a_format_as_tk_does(photo):
    with pytest.raises(TclError, match='image string format "xyz" is unknown'):
        photo.data("xyz")
    with pytest.raises(TclError, match='"svg" is not supported'):
        photo.data("svg")


def test_a_gif_holds_at_most_255_colours(root):
    """One slot is kept for transparency, hole or no hole."""
    for count, works in ((255, True), (256, False)):
        image = tk.PhotoImage(width=count, height=1)
        image.put(" ".join(f"#{n * 3:06x}" for n in range(count)).join("{}"))
        if works:
            assert image.data("gif").startswith(b"GIF89a")
        else:
            with pytest.raises(TclError, match="too many colors"):
                image.data("gif")


# ----------------------------------------------------------------- write


def test_write_is_a_ppm_unless_told(photo, tmp_path):
    photo.write(str(tmp_path / "a"))
    assert (tmp_path / "a").read_bytes() == photo.data("ppm")


def test_write_takes_the_format_and_region_positionally(photo, tmp_path):
    """write(filename, format, from_coords), as in tkinter: the call that
    passed "png" as a palette here before."""
    photo.write(str(tmp_path / "a.png"), "png", (2, 0))
    again = tk.PhotoImage(file=str(tmp_path / "a.png"))
    assert again.data() == (BLUE, OLIVE)


def test_write_refuses_as_tk_does(photo, tmp_path):
    with pytest.raises(TclError, match='image file format "xyz" is unknown'):
        photo.write(str(tmp_path / "a"), "xyz")
    with pytest.raises(TclError, match="has no file writing capability"):
        photo.write(str(tmp_path / "a"), "default")
    with pytest.raises(TclError, match=r"couldn't open .*: no such file or directory"):
        photo.write(str(tmp_path / "no" / "a.png"), "png")


# ------------------------------------------------------------------ read


@pytest.fixture
def png(photo, tmp_path):
    path = tmp_path / "w.png"
    photo.write(str(path), "png")
    return str(path)


def test_read_grows_an_image_without_a_size(root, png):
    image = tk.PhotoImage()
    image.read(png)
    assert (image.width(), image.height()) == (3, 2)


def test_read_keeps_what_it_does_not_cover(root, png):
    image = tk.PhotoImage()
    image.put("white", to=(0, 0, 6, 5))
    image.read(png)
    assert (image.width(), image.height()) == (6, 5)
    assert image.data(from_coords=(5, 4)) == ("#ffffff",)


def test_read_with_shrink_fits_the_image_to_it(root, png):
    image = tk.PhotoImage()
    image.put("white", to=(0, 0, 6, 5))
    image.read(png, shrink=True)
    assert (image.width(), image.height()) == (3, 2)
    image.read(png, to=(1, 1), shrink=True)
    assert (image.width(), image.height()) == (4, 3)


def test_read_into_an_image_with_a_size_clips(root, png):
    image = tk.PhotoImage(width=5, height=4)
    image.read(png, to=(4, 3))
    assert (image.width(), image.height()) == (5, 4)
    assert image.data(from_coords=(4, 3)) == (RED,)


def test_read_takes_a_region_and_a_place(root, png):
    image = tk.PhotoImage()
    image.read(png, from_coords=(1, 0), to=(2, 2))
    assert image.data() == (
        f"{NONE} {NONE} {NONE} {NONE}",
        f"{NONE} {NONE} {NONE} {NONE}",
        f"{NONE} {NONE} {RED} {BLUE}",
        f"{NONE} {NONE} {NONE} {OLIVE}",
    )


def test_read_replaces_holes_and_all(root, png):
    image = tk.PhotoImage(width=3, height=2)
    image.put("white", to=(0, 0, 3, 2))
    image.read(png)
    assert image.transparency_get(1, 1)


def test_read_refuses_as_tk_does(root, png, tmp_path):
    image = tk.PhotoImage()
    with pytest.raises(TclError, match="couldn't recognize data in image file"):
        image.read(png, "ppm")
    image.read(png, "PNG")
    with pytest.raises(TclError, match='image file format "xyz" is not supported'):
        image.read(png, "xyz")
    with pytest.raises(TclError, match="-file option isn't supported for default"):
        image.read(png, "default")
    with pytest.raises(TclError, match="extend outside source image"):
        image.read(png, from_coords=(0, 0, 9, 9))
    with pytest.raises(TclError, match="couldn't open"):
        image.read(str(tmp_path / "nothing.png"))
    text = tmp_path / "rows.txt"
    text.write_text("#ff0000 #00ff00\n")
    with pytest.raises(TclError, match="couldn't recognize data in image file"):
        image.read(str(text))


# ------------------------------------------------------------ put and data=


@pytest.mark.parametrize(
    ("data", "rows"),
    [("red", (RED,)),
     ("red blue", (RED, BLUE)),
     ("{red blue}", (f"{RED} {BLUE}",)),
     (["red blue"], (f"{RED} {BLUE}",)),
     (("red blue", "green white"), (f"{RED} {BLUE}", "#008000 #ffffff")),
     ([["red", "blue"]], (f"{RED} {BLUE}",))],
)  # fmt: skip
def test_put_takes_tks_rows(root, data, rows):
    image = tk.PhotoImage()
    image.put(data)
    assert image.data() == rows


def test_put_grows_an_image_without_a_size_to_its_far_corner(root):
    image = tk.PhotoImage()
    image.put("red", to=(1, 1, 3, 2))
    assert image.data() == (f"{NONE} {NONE} {NONE}", f"{NONE} {RED} {RED}")
    image.put("{red blue}", to=(2, 1))
    assert (image.width(), image.height()) == (4, 2)


def test_put_takes_image_data(root, photo):
    for data in (photo.data("png"), base64.b64encode(photo.data("png")).decode()):
        image = tk.PhotoImage()
        image.put(data, to=(1, 1))
        assert image.data(from_coords=(1, 1)) == photo.data()


def test_put_refuses_as_tk_does(root):
    image = tk.PhotoImage()
    with pytest.raises(TclError, match="invalid row # 1: all rows must have"):
        image.put(("red blue", "green"))
    with pytest.raises(TclError, match='invalid color name "nosuch"'):
        image.put("{red nosuch}")
    image.put("")
    assert (image.width(), image.height()) == (0, 0)


@pytest.mark.parametrize(
    "encode", [bytes, lambda data: base64.b64encode(data).decode()]
)
def test_data_option_takes_image_data(root, photo, encode):
    assert tk.PhotoImage(data=encode(photo.data("gif"))).data() == photo.data()


def test_data_option_takes_rows_in_braces(root):
    image = tk.PhotoImage(data="{red blue} {green white}")
    assert image.data() == (f"{RED} {BLUE}", "#008000 #ffffff")


def test_data_option_in_the_wrong_format_is_refused(root, photo):
    with pytest.raises(TclError, match="couldn't recognize image data"):
        tk.PhotoImage(data=photo.data("gif"), format="png")
    assert tk.PhotoImage(data=photo.data("png"), format="PNG").width() == 3


def test_data_given_to_an_image_with_a_size_keeps_the_size(root, photo):
    image = tk.PhotoImage(width=4, height=3)
    image.configure(data=photo.data("png"))
    assert (image.width(), image.height()) == (4, 3)
    assert image.data(from_coords=(0, 0, 3, 2)) == photo.data()


def test_data_given_to_a_grown_image_replaces_its_size(root):
    image = tk.PhotoImage()
    image.put("red", to=(0, 0, 5, 5))
    image.configure(data="{blue}")
    assert (image.width(), image.height()) == (1, 1)


# --------------------------------------------------------- character art


def test_a_palette_writes_and_answers_character_art(root, tmp_path):
    image = tk.PhotoImage(data=["#.", ".#"], palette={"#": "red"})
    assert image.data(palette={"red": "R"}) == ["R ", " R"]
    image.write(str(tmp_path / "art.txt"), palette={})
    assert (tmp_path / "art.txt").read_text() == "# \n #\n"


# -------------------------------------------------- against the real toolkit


@pytest.fixture(scope="module")
def real_root():
    try:
        real = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    real.withdraw()
    yield real
    real.destroy()


def _theirs(real_root):
    image = tkinter.PhotoImage(master=real_root, width=3, height=2)
    image.put("red", to=(0, 0, 2, 2))
    image.put("blue", to=(2, 0, 3, 1))
    image.put("#808000", to=(2, 1, 3, 2))
    image.blank()  # Tk keeps a hole's colour; one never painted is black
    image.put("red", to=(0, 0, 2, 1))
    image.put("red", to=(0, 1, 1, 2))
    image.put("blue", to=(2, 0, 3, 1))
    image.put("#808000", to=(2, 1, 3, 2))
    return image


def test_tk_answers_what_this_answers(real_root, photo):
    theirs = _theirs(real_root)
    assert theirs.data() == photo.data()
    assert theirs.data(grayscale=True) == photo.data(grayscale=True)
    assert theirs.data(background="green") == photo.data(background="green")
    assert theirs.data("ppm") == photo.data("ppm")


@pytest.mark.parametrize("format", ["png", "gif", "ppm"])
def test_tk_reads_what_this_writes(real_root, photo, tmp_path, format):
    path = tmp_path / f"ours.{format}"
    photo.write(str(path), format)
    theirs = tkinter.PhotoImage(master=real_root, file=str(path))
    assert theirs.data() == photo.data()
    if format != "ppm":
        assert theirs.transparency_get(1, 1)


@pytest.mark.parametrize("format", ["png", "gif"])
def test_this_reads_what_tk_writes(real_root, root, tmp_path, format):
    path = tmp_path / f"theirs.{format}"
    theirs = _theirs(real_root)
    theirs.write(str(path), format)
    ours = tk.PhotoImage(file=str(path))
    assert ours.data() == theirs.data()
