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

"""Tests for the LabelFrame widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Frame, Label, LabelFrame, Misc, StringVar
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def stack():
    return PanelStack(window_factory=stub_window, panel_factory=None)


@pytest.fixture
def root(stack):
    root = Misc()
    root.tk.panels = stack
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    return root


def laid_out(widget, x=0, y=0, width=24, height=6):
    widget._allocate(Rect(x, y, width, height))
    widget._map()
    return widget


# ------------------------------------------------------------------ the frame


def test_a_labelframe_is_bordered_by_default(root):
    """Unlike a plain Frame: a caption with no border to sit on is a label."""
    assert LabelFrame(root, name="f", text="Options")._bordered
    assert not Frame(root, name="g")._bordered


def test_the_caption_costs_the_children_nothing(root):
    """It is written on the border line, which the children never had."""
    plain = laid_out(Frame(root, name="g", relief="solid"))
    captioned = laid_out(LabelFrame(root, name="f", text="Options"), y=8)
    assert captioned._content_rect().width == plain._content_rect().width
    assert captioned._content_rect().height == plain._content_rect().height


def test_a_child_is_laid_out_inside_the_border(root):
    frame = LabelFrame(root, name="f", text="Options")
    child = Label(frame, name="c", text="inside")
    child.pack(fill="both", expand=True)
    laid_out(frame)
    frame.update_layout()
    assert child.winfo_rootx() >= 1
    assert child.winfo_rooty() >= 1


def test_a_labelframe_is_never_narrower_than_its_caption(root):
    frame = LabelFrame(root, name="f", text="A rather long caption")
    assert frame.winfo_reqwidth() >= len(" A rather long caption ") + 2


def test_an_uncaptioned_labelframe_asks_for_nothing_extra(root):
    assert LabelFrame(root, name="f", text="").winfo_reqwidth() == 0


# ---------------------------------------------------------------- the caption


def test_the_caption_is_spaced_off_the_corners(root):
    assert LabelFrame(root, name="f", text="Options")._caption() == " Options "


def test_no_text_means_no_caption(root):
    assert LabelFrame(root, name="f")._caption() == ""


def test_a_textvariable_supplies_the_caption(root):
    variable = StringVar(root, "Network")
    assert LabelFrame(root, name="f", textvariable=variable)._caption() == " Network "


def test_changing_the_variable_changes_the_caption(root):
    variable = StringVar(root, "Network")
    frame = LabelFrame(root, name="f", textvariable=variable)
    variable.set("Display")
    assert frame._caption() == " Display "


def test_changing_the_variable_re_measures(root):
    variable = StringVar(root, "a")
    frame = LabelFrame(root, name="f", textvariable=variable)
    narrow = frame.winfo_reqwidth()
    variable.set("a much longer caption")
    assert frame.winfo_reqwidth() > narrow


def test_a_new_variable_drops_the_old_trace(root):
    first, second = StringVar(root, "one"), StringVar(root, "two")
    frame = LabelFrame(root, name="f", textvariable=first)
    frame.configure(textvariable=second)
    assert frame._caption() == " two "
    assert first.trace_info() == []


@pytest.mark.parametrize(
    ("anchor", "expected"),
    [
        ("nw", ("top", "left")),
        ("n", ("top", "centre")),
        ("ne", ("top", "right")),
        ("sw", ("bottom", "left")),
        ("s", ("bottom", "centre")),
        ("se", ("bottom", "right")),
    ],
)
def test_every_horizontal_anchor_has_a_place(anchor, expected):
    assert LabelFrame._CAPTION_PLACES[anchor] == expected


@pytest.mark.parametrize("anchor", ["w", "e", "wn", "en", "ws", "es"])
def test_a_vertical_anchor_folds_onto_a_horizontal_edge(anchor):
    """A terminal cannot turn text on its side, so it goes to the nearest end."""
    edge, alignment = LabelFrame._CAPTION_PLACES[anchor]
    assert edge in ("top", "bottom")
    assert alignment in ("left", "right")


def test_an_unknown_anchor_falls_back_rather_than_raising(root):
    frame = laid_out(LabelFrame(root, name="f", text="Options", labelanchor="zz"))
    frame._redraw()  # must not raise


def test_a_caption_wider_than_the_frame_is_clipped_not_wrapped(root):
    frame = laid_out(
        LabelFrame(root, name="f", text="A caption far wider than this frame"),
        width=12,
    )
    frame._redraw()  # must not raise
