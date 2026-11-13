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

"""``image`` and ``compound`` on the widgets that take them.

The arrangements were measured on Tk 9.0.2 with a Label holding
``text='hello'`` and an 8x4 image:

    compound=none (DEFAULT)  10x6  <- the image, and no text at all
    compound=left/right      45x23    side by side
    compound=top/bottom      36x28    stacked
    compound=center          36x23    the text over the image

Given a 2px border, a 34x21 text block and Tk's one-pixel gap, those are the
same sums the cell arithmetic below makes.

**A widget lays out in cells and an image is measured in pixels**, which are
half a cell tall. An image 4 pixels high therefore occupies 2 rows, and that
halving is the thing most likely to be got wrong here - so the fixture's
image is deliberately 4 pixels tall and 2 cells high, and the two numbers
are never the same.
"""

from __future__ import annotations

import gc

import pytest

import tkcurses
from tkcurses import (
    BitmapImage,
    Button,
    Checkbutton,
    Label,
    Misc,
    PhotoImage,
    Radiobutton,
    TclError,
)


@pytest.fixture
def root():
    return Misc()


@pytest.fixture(autouse=True)
def _no_leaked_default_root():
    previous = tkcurses._default_root
    yield
    tkcurses._default_root = previous


@pytest.fixture
def art(root):
    """Three pixels across, four down - so 3 cells wide and 2 cells high."""
    return PhotoImage(
        master=root, data=["###", "###", "###", "###"], palette={"#": "red"}
    )


def size(widget):
    return widget.winfo_reqwidth(), widget.winfo_reqheight()


def places(widget):
    return dict(widget._content_layout())


# ------------------------------------------------------------ the option


def test_a_label_takes_an_image_object(root, art):
    """3 pixels wide is 3 cells; 4 pixels tall is 2 cells."""
    assert (art.width(), art.height()) == (3, 4)
    assert size(Label(root, image=art)) == (3, 2)


def test_a_label_takes_an_image_by_name(root, art):
    """Tk refers to an image by name, and so may a caller."""
    assert size(Label(root, image=str(art))) == (3, 2)


def test_a_widget_asks_for_cells_not_pixels(root):
    """The conversion this whole module exists to pin down."""
    tall = PhotoImage(master=root, width=6, height=10)
    assert (tall.width(), tall.height()) == (6, 10)
    assert size(Label(root, image=tall)) == (6, 5)


def test_an_odd_pixel_height_takes_a_whole_row(root):
    """Half a cell of image still needs a cell to be drawn in."""
    odd = PhotoImage(master=root, width=4, height=5)
    assert size(Label(root, image=odd)) == (4, 3)


def test_cget_gives_back_the_name_even_when_given_an_object(root, art):
    """Measured on Tk: a Label built with image=<PhotoImage> answers
    cget("image") with 'pyimage1'. The option holds a name, not an object -
    which is also what keeps a widget from owning its image."""
    assert Label(root, image=art).cget("image") == str(art)
    assert Label(root, image=str(art)).cget("image") == str(art)


def test_an_unknown_image_name_raises_tk_s_error(root):
    with pytest.raises(TclError, match='image "nosuch" does not exist'):
        Label(root, image="nosuch")


def test_setting_an_unknown_name_later_also_raises(root, art):
    label = Label(root, image=art)
    with pytest.raises(TclError, match='image "gone" does not exist'):
        label.configure(image="gone")


def _family():
    from tkcurses import Menubutton, ttk

    return [
        Label, Button, Checkbutton, Radiobutton, Menubutton,
        ttk.Label, ttk.Button, ttk.Checkbutton, ttk.Radiobutton, ttk.Menubutton,
    ]  # fmt: skip


@pytest.mark.parametrize("cls", _family(), ids=lambda c: f"{c.__module__}.{c.__name__}")
def test_a_refused_name_leaves_the_image_it_had(root, art, cls):
    """Measured on Tk 9.0.2: the configure is refused and nothing changes -
    except on the classic Menubutton, which stores the name first."""
    from tkcurses import Menubutton

    widget = cls(root, image=art)
    with pytest.raises(TclError, match='image "nosuch" does not exist'):
        widget.configure(image="nosuch")
    expected = "nosuch" if cls is Menubutton else str(art)
    assert widget.cget("image") == expected


@pytest.mark.parametrize("cls", _family(), ids=lambda c: f"{c.__module__}.{c.__name__}")
def test_a_widget_whose_image_is_gone_refuses_configure(root, cls):
    """Tk looks the image up on every configure that sets anything: once it
    has been deleted, ``configure(text=...)`` is ``image "pyimage1" does not
    exist``, and naming another image, or none, is the way out."""
    image = PhotoImage(master=root, width=2, height=2)
    name = str(image)
    widget = cls(root, image=image, text="t")
    del image
    gc.collect()
    with pytest.raises(TclError, match=f'image "{name}" does not exist'):
        widget.configure(text="x")
    assert widget.cget("text") == "t"
    widget.configure(image="")
    widget.configure(text="x")
    assert widget.cget("text") == "x"


def test_the_default_compound_is_none(root):
    assert Label(root, text="x").cget("compound") == "none"


@pytest.mark.parametrize(
    "widget", [Label, Button, Checkbutton, Radiobutton], ids=lambda w: w.__name__
)
def test_every_labelled_widget_takes_an_image(root, art, widget):
    instance = widget(root, image=art)
    assert instance.cget("image") == str(art)


# -------------------------------------------------------------- compound


def test_an_image_hides_the_text_by_default(root, art):
    """The surprising one, and the reason it is reproduced.

    Measured on Tk: text='hello' with an 8x4 image asks for 10x6 - the image
    plus its border. The text contributes nothing at all.
    """
    label = Label(root, text="hello", image=art)
    assert size(label) == (3, 2)
    assert "text" not in places(label)


def test_text_alone_is_unaffected(root):
    assert size(Label(root, text="hello")) == (5, 1)


def test_an_image_alone_is_the_image(root, art):
    assert size(Label(root, image=art, compound="left")) == (3, 2)


def test_compound_left_puts_the_image_first(root, art):
    label = Label(root, text="hello", image=art, compound="left")
    assert size(label) == (3 + 1 + 5, 2)
    assert places(label)["image"].x == 0
    assert places(label)["text"].x == 4


def test_compound_right_puts_the_image_last(root, art):
    label = Label(root, text="hello", image=art, compound="right")
    assert size(label) == (5 + 1 + 3, 2)
    assert places(label)["text"].x == 0
    assert places(label)["image"].x == 6


def test_compound_top_stacks_the_image_above(root, art):
    label = Label(root, text="hello", image=art, compound="top")
    assert size(label) == (5, 3)
    assert places(label)["image"].y == 0
    assert places(label)["text"].y == 2


def test_compound_bottom_stacks_the_image_below(root, art):
    label = Label(root, text="hello", image=art, compound="bottom")
    assert size(label) == (5, 3)
    assert places(label)["text"].y == 0
    assert places(label)["image"].y == 1


def test_compound_center_overlays_them(root, art):
    """Neither adds to the other: the block is the larger of each."""
    label = Label(root, text="hello", image=art, compound="center")
    assert size(label) == (5, 2)


def test_the_shorter_of_a_side_by_side_pair_is_centred(root, art):
    label = Label(root, text="hello", image=art, compound="left")
    assert places(label)["text"].y == 0  # (2 - 1) // 2


def test_compound_survives_being_changed(root, art):
    label = Label(root, text="hello", image=art)
    label.configure(compound="left")
    assert size(label) == (9, 2)
    label.configure(compound="none")
    assert size(label) == (3, 2)


def test_an_explicit_width_still_wins(root, art):
    assert size(Label(root, image=art, width=20)) == (20, 2)


# ------------------------------------------------------- following the image


def test_a_widget_follows_its_image_s_size(root, art):
    """Measured on Tk: 4x2 -> 20x10 moved a live Label from 6x4 to 22x12."""
    label = Label(root, image=art)
    assert size(label) == (3, 2)
    art.configure(width=10, height=6)
    assert size(label) == (10, 3)


def test_a_widget_stops_following_an_image_it_was_pointed_away_from(root, art):
    other = PhotoImage(master=root, data=["##"], palette={"#": "red"})
    label = Label(root, image=art)
    label.configure(image=other)
    art.configure(width=40, height=9)
    assert size(label) == (2, 1)
    # The size alone does not prove it: a widget still listening to the old
    # image would re-measure from the new one and come out right anyway,
    # just repainting for changes that are none of its business.
    assert label not in art._users
    assert label in other._users


def test_two_widgets_can_share_one_image(root, art):
    first, second = Label(root, image=art), Label(root, image=art)
    art.configure(width=7, height=4)
    assert size(first) == size(second) == (7, 2)


def test_a_widget_does_not_keep_its_image_alive(root):
    """The other half of the trap, and the one that is easy to get wrong.

    A widget that held its image would make the weak registry pointless: no
    image would ever be collected while anything showed it. Measured on Tk,
    an image really does go when the last reference does, however many
    widgets name it.
    """
    art = PhotoImage(master=root, data=["##"], palette={"#": "red"})
    label = Label(root, image=art)
    name = str(art)
    del art
    gc.collect()
    assert name not in root.tk.images
    assert label._image() is None


def test_an_image_that_goes_away_leaves_the_widget_at_its_size(root):
    """Tk's trap, measured: the widget survives and keeps its geometry.

    Deleting an image a Label was showing left the label alive at its old
    22x12 with the dead name still in its image option. Nothing raises; the
    art simply stops being drawn, which is why tkinter code keeps a
    reference.
    """
    art = PhotoImage(master=root, width=4, height=4)
    label = Label(root, image=str(art))
    assert size(label) == (4, 2)
    name = str(art)
    del art
    gc.collect()
    assert label.cget("image") == name
    assert label._image() is None
    assert size(label) == (4, 2)


# ---------------------------------------------------------------- bitmaps


def test_a_bitmap_image_works_the_same_way(root):
    bitmap = BitmapImage(
        master=root,
        data="#define x_width 8\n#define x_height 4\nstatic char x_bits[] = {\n"
        "0xff,0x81,0x81,0xff};\n",
    )
    # 8x4 pixels, which is 8 cells across and 2 down.
    assert size(Label(root, image=bitmap)) == (8, 2)


def test_a_bitmap_carries_its_own_colours(root):
    bitmap = BitmapImage(master=root, data=["X"], foreground="red")
    label = Label(root, image=bitmap, foreground="green")
    assert bitmap.rows() == [["red"]]
    assert label._image() is bitmap
