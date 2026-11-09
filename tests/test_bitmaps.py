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

"""The ``bitmap`` option: Tk's ten names and ``@file``, measured on Tk 9.0.2."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import (
    _BITMAP_GLYPHS,
    Button,
    Canvas,
    Checkbutton,
    Entry,
    Label,
    Menubutton,
    Message,
    Misc,
    PhotoImage,
    Radiobutton,
    TclError,
)
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack

XBM = "#define t_width 4\n#define t_height 2\nstatic unsigned char t_bits[] = { 0x0f, 0x09 };\n"


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 40, 12)
    root._mapped = True
    return root


def test_tk_has_exactly_these_ten():
    assert sorted(_BITMAP_GLYPHS) == [
        "error", "gray12", "gray25", "gray50", "gray75",
        "hourglass", "info", "questhead", "question", "warning",
    ]  # fmt: skip


@pytest.mark.parametrize("name", sorted(_BITMAP_GLYPHS))
def test_each_name_is_one_cell_and_reads_back(root, name):
    label = Label(root, bitmap=name)
    assert label.cget("bitmap") == name
    assert label._content_layout() == [("image", Rect(0, 0, 1, 1))]


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("nonsense", 'bitmap "nonsense" not defined'),
        ("INFO", 'bitmap "INFO" not defined'),
        ("info ", 'bitmap "info " not defined'),
        ("@missing.xbm", 'error reading bitmap file "missing.xbm"'),
        ("@", 'error reading bitmap file ""'),
    ],
)
def test_anything_else_is_refused_in_tks_words(root, value, message):
    with pytest.raises(TclError, match=f"^{message}$"):
        Label(root, bitmap=value)


@pytest.mark.parametrize("cls", [Button, Checkbutton, Label, Menubutton, Radiobutton])
def test_the_widgets_tk_gives_it_take_it(root, cls):
    assert cls(root, bitmap="info").cget("bitmap") == "info"


@pytest.mark.parametrize("cls", [Canvas, Entry, Message])
def test_the_others_refuse_it_as_tk_does(root, cls):
    with pytest.raises(TclError, match='unknown option "-bitmap"'):
        cls(root, bitmap="info")


def test_a_bitmap_hides_the_text_unless_compound_says_otherwise(root):
    """Measured: text and bitmap ask for the bitmap's size alone."""
    assert Label(root, text="Hi", bitmap="info")._content_layout() == [
        ("image", Rect(0, 0, 1, 1))
    ]
    assert Label(root, text="Hi", bitmap="info", compound="left")._content_layout() == [
        ("image", Rect(0, 0, 1, 1)),
        ("text", Rect(2, 0, 2, 1)),
    ]


def test_an_image_wins_over_a_bitmap(root):
    picture = PhotoImage(master=root, width=3, height=2)
    label = Label(root, bitmap="info", image=picture)
    assert label._content_layout() == [("image", Rect(0, 0, 3, 1))]


def test_an_empty_bitmap_is_none(root):
    label = Label(root, text="Hi", bitmap="info")
    label.configure(bitmap="")
    assert label._content_layout() == [("text", Rect(0, 0, 2, 1))]


def test_a_file_is_drawn_as_its_bits(root, tmp_path):
    path = tmp_path / "t.xbm"
    path.write_text(XBM)
    label = Label(root, bitmap=f"@{path}")
    assert label._content_layout() == [("image", Rect(0, 0, 4, 1))]


def test_a_file_bitmap_is_not_a_named_image(root, tmp_path):
    path = tmp_path / "t.xbm"
    path.write_text(XBM)
    before = set(root.tk.images)
    Label(root, bitmap=f"@{path}")._image()
    assert set(root.tk.images) == before


def test_a_file_bitmap_follows_the_foreground(root, tmp_path):
    path = tmp_path / "t.xbm"
    path.write_text(XBM)
    label = Label(root, bitmap=f"@{path}", foreground="red")
    first = label._image()
    label.configure(foreground="cyan")
    assert label._image() is not first
