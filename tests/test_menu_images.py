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

"""Menu entries with images: ``-image``, ``-compound`` and ``-selectimage``.

An image is half-block pixels, two pixel rows to a cell, so an entry with
one is as tall as its image in cells - and a row taller when the label goes
above or below it. Measured on Tk 9.0.2: ``compound`` defaults to ``none``,
which shows the image in place of the label; an image that does not exist
and a ``compound`` outside Tk's six are refused in Tk's words; ``yposition``
of each entry after a tall one moves down by its height.
"""

from __future__ import annotations

import tkinter
from types import SimpleNamespace

import pytest

from tkcurses import IntVar, Menu, Misc, PhotoImage, TclError
from tkcurses._core.events import KeyEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.menus import MenuEntry, lay_out, visible_window
from tkcurses._core.panels import PanelStack


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(window_factory=stub_window, panel_factory=None)
    root._rect = Rect(0, 0, 60, 40)
    root._mapped = True
    return root


@pytest.fixture
def picture(root):
    """Four pixels square: four cells wide and two tall."""
    image = PhotoImage(master=root, width=4, height=4)
    image.put("red", to=(0, 0, 4, 4))
    return image


def entry(label, picture=None, compound="none"):
    made = MenuEntry("command", {"label": label, "compound": compound})
    made.picture = picture
    return made


# ------------------------------------------------------------- the layout


@pytest.mark.parametrize(
    ("compound", "width", "height", "label_row"),
    [
        ("none", 4, 2, 0),
        ("left", 4 + 1 + 5, 2, 0),
        ("right", 4 + 1 + 5, 2, 0),
        ("center", 5, 2, 0),
        ("top", 5, 3, 2),
        ("bottom", 5, 3, 0),
    ],
)
def test_an_entry_is_as_big_as_its_image_and_label(compound, width, height, label_row):
    made = entry("Label", (4, 2), compound)
    assert (made.content_width, made.height, made.label_row) == (
        width,
        height,
        label_row,
    )


def test_compound_none_shows_the_image_in_place_of_the_label():
    assert not entry("Label", (4, 2)).shows_label
    assert entry("Label", (4, 2), "left").shows_label
    assert entry("Label").shows_label


def test_each_entry_starts_below_the_ones_before_it():
    places, size = lay_out(
        [entry("a"), entry("b", (4, 3)), entry("c", (2, 2), "top"), entry("d")],
        indicators=False,
    )
    assert [(p.row, p.height) for p in places] == [(0, 1), (1, 3), (4, 3), (7, 1)]
    assert size[1] == 8


def test_the_window_scrolls_by_rows_not_entries():
    heights = [1, 4, 1, 1, 4, 1]
    # Six rows show; the last three entries fill them exactly.
    assert visible_window(6, 5, 6, heights) == 3
    assert visible_window(6, 3, 6, heights) == 1
    assert visible_window(6, 0, 6, heights) == 0
    # An entry taller than the window starts it.
    assert visible_window(6, 4, 3, heights) == 4
    # All one row each, it is the old answer.
    assert visible_window(10, 9, 4) == 6 == visible_window(10, 9, 4, [1] * 10)


# --------------------------------------------------------------- the menu


def menu_with_images(root, picture):
    menu = Menu(root, name="m")
    menu.add_command(label="Plain")
    menu.add_command(label="Tall", image=picture)
    menu.add_command(label="Stacked", image=picture, compound="top")
    menu.add_command(label="After")
    return menu


def test_yposition_counts_the_rows_above(root, picture):
    menu = menu_with_images(root, picture)
    menu.post(0, 0)
    assert [menu.yposition(n) for n in range(4)] == [0, 1, 3, 6]


def test_a_click_on_any_row_of_a_tall_entry_is_that_entry(root, picture):
    menu = menu_with_images(root, picture)
    menu.post(0, 0)
    area = menu._text_area()
    assert [menu._entry_at(area.x, area.y + row) for row in range(7)] == [
        0,
        1,
        1,
        2,
        2,
        2,
        3,
    ]


def test_the_menu_is_as_tall_as_its_entries(root, picture):
    menu = menu_with_images(root, picture)
    menu.post(0, 0)
    assert menu.winfo_reqheight() == 7 + 2


def test_the_arrows_step_over_tall_entries_one_at_a_time(root, picture):
    menu = menu_with_images(root, picture)
    menu.post(0, 0)
    for expected in (0, 1, 2, 3):
        menu._handle(KeyEvent(keysym="Down"))
        assert menu._active == expected


def test_a_short_screen_scrolls_to_show_the_whole_active_entry(
    root, picture, monkeypatch
):
    monkeypatch.setattr(Menu, "_screen_size", lambda self: (60, 6))
    menu = menu_with_images(root, picture)
    menu.post(0, 0)
    assert menu._rows() == 4
    menu.activate(3)
    # Entries 2 and 3 take four rows, and fill the window between them.
    assert menu._first == 2
    assert menu.yposition(3) == 3


def test_a_cascade_opens_beside_its_own_row(root, picture):
    menu = menu_with_images(root, picture)
    sub = Menu(root, name="sub")
    sub.add_command(label="Inner")
    menu.add_cascade(label="More", menu=sub)
    menu.post(0, 0)
    menu._open(4)
    assert sub.winfo_rooty() == menu.winfo_rooty() + menu.yposition(4) == 7


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("image", "nosuch", 'image "nosuch" does not exist'),
        (
            "compound",
            "bogus",
            'bad compound "bogus": must be bottom, center, left, none, right, or top',
        ),
    ],
)
def test_bad_values_are_refused_in_tks_words(root, option, value, message):
    menu = Menu(root)
    with pytest.raises(TclError, match=message):
        menu.add_command(label="x", **{option: value})
    menu.add_command(label="y")
    with pytest.raises(TclError, match=message):
        menu.entryconfigure(0, **{option: value})


def test_a_unique_prefix_of_a_compound_is_taken_whole(root, picture):
    menu = Menu(root)
    menu.add_command(label="x", image=picture, compound="l")
    assert menu.entrycget(0, "compound") == "left"


def test_a_chosen_check_entry_shows_its_selectimage(root, picture):
    other = PhotoImage(master=root, width=4, height=4)
    variable = IntVar(root, value=0)
    menu = Menu(root)
    menu.add_checkbutton(label="c", image=picture, selectimage=other, variable=variable)
    shown = menu._entries[0]
    assert menu._entry_image(shown, drawn=True) is picture
    variable.set(1)
    assert menu._entry_image(shown, drawn=True) is other
    assert menu._entry_image(shown) is picture


def test_a_deleted_image_leaves_a_one_row_entry(root, picture):
    menu = Menu(root)
    menu.add_command(label="x", image=picture)
    root.tk.call("image", "delete", str(picture))
    menu.post(0, 0)
    assert menu._places()[0].height == 1


# --------------------------------------------- the measurements, on Tk


def test_tk_moves_each_entry_down_by_the_one_before_it():
    try:
        real = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    try:
        image = tkinter.PhotoImage(master=real, width=16, height=40)
        menu = tkinter.Menu(real, tearoff=0)
        assert menu.cget("tearoff") == 0
        menu.add_command(label="Plain")
        menu.add_command(label="Tall", image=image)
        menu.add_command(label="Stacked", image=image, compound="top")
        menu.add_command(label="After")
        assert menu.entrycget(1, "compound") == "none"
        menu.post(0, 0)
        real.update()
        rows = [menu.yposition(n) for n in range(4)]
        plain = rows[1] - rows[0]
        tall = rows[2] - rows[1]
        stacked = rows[3] - rows[2]
        # Taller with the image, and taller again with a label stacked on it.
        assert plain < tall < stacked
        menu.unpost()
    finally:
        real.destroy()


# ------------------------------------------------------------- on screen

DRAWN = """
import tkcurses as tk
root = tk.Tk()
img = tk.PhotoImage(width=4, height=4)
img.put("red", to=(0, 0, 4, 4))
m = tk.Menu(root)
m.add_command(label="Plain", accelerator="F1")
m.add_command(label="Gone", image=img)
m.add_command(label="Left", image=img, compound="left")
m.add_command(label="Top", image=img, compound="top")
m.add_command(label="Right", image=img, compound="right", accelerator="F2")
m.add_command(label="End")
root.after(50, lambda: m.post(2, 1))
root.mainloop()
"""


@pytest.mark.tty
def test_the_images_are_drawn_where_compound_puts_them(terminal, tmp_path):
    term = terminal(cols=40, rows=16)
    term.run_source(DRAWN, workdir=tmp_path)
    term.wait_for_cell(12, 4, lambda c: c.data == "E", message="the last entry")
    assert term.region(2, 4, 11, 15) == [
        "Plain       F1 ",
        "████           ",
        "████           ",
        "████ Left      ",
        "████           ",
        "████           ",
        "████           ",
        "Top            ",
        "Right ████  F2 ",
        "      ████     ",
        "End            ",
    ]
    # compound none: the image in place of the label.
    assert "Gone" not in "".join(term.display)
    assert term.attrs_at(3, 4)["fg"] in ("red", "cd0000", "ff0000")
