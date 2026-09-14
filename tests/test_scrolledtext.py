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

"""A Text with its scrollbar attached, and the redirection that needs."""

from __future__ import annotations

import pytest

import tkcurses
from tkcurses.scrolledtext import ScrolledText


@pytest.fixture
def root():
    return tkcurses.Misc()


def test_it_is_a_text(root):
    """Every Text method has to be there, because that is what it is."""
    scrolled = ScrolledText(root)
    assert isinstance(scrolled, tkcurses.Text)
    scrolled.insert("end", "hello")
    assert scrolled.get("1.0", "end").startswith("hello")


def test_it_brings_a_frame_and_a_scrollbar(root):
    scrolled = ScrolledText(root)
    assert isinstance(scrolled.frame, tkcurses.Frame)
    assert isinstance(scrolled.vbar, tkcurses.Scrollbar)


def test_the_text_and_the_bar_are_wired_both_ways(root):
    """The text says where the view is; the bar says where to move it."""
    scrolled = ScrolledText(root)
    assert scrolled.cget("yscrollcommand") == scrolled.vbar.set
    assert scrolled.vbar.cget("command") == scrolled.yview


def test_the_text_lives_inside_the_frame(root):
    scrolled = ScrolledText(root)
    assert scrolled.master is scrolled.frame
    assert scrolled.frame.master is root


# ------------------------------------------------------- the redirection


def test_packing_it_packs_the_frame(root):
    """Not the text. Packing the text would put it inside its own frame and
    leave the frame unmanaged, so nothing would appear at all."""
    scrolled = ScrolledText(root)
    scrolled.pack()
    assert scrolled.frame.winfo_manager() == "pack"


def test_placing_goes_to_the_frame_too(root):
    scrolled = ScrolledText(root)
    scrolled.place(x=1, y=2)
    assert scrolled.frame.winfo_manager() == "place"


def test_gridding_goes_to_the_frame_too():
    # Its own root: a container may have one geometry manager, and the test
    # above has already given that one to place.
    scrolled = ScrolledText(tkcurses.Misc())
    scrolled.grid(row=1, column=1)
    assert scrolled.frame.winfo_manager() == "grid"


def test_the_geometry_info_calls_describe_the_frame(root):
    scrolled = ScrolledText(root)
    scrolled.place(x=3, y=4)
    assert scrolled.place_info()["x"] == 3


def test_configure_still_reaches_the_text(root):
    """The options are the text's, which is why config and configure are the
    two methods deliberately left un-redirected."""
    scrolled = ScrolledText(root)
    scrolled.configure(wrap="none")
    assert scrolled.cget("wrap") == "none"


def test_it_is_named_by_its_frame(root):
    """A caller manages the frame, so that is the path str() gives."""
    scrolled = ScrolledText(root)
    assert str(scrolled) == str(scrolled.frame)


# -------------------------------------------------------- binding tags


def test_it_reports_itself_as_a_text(root):
    """Binding tags name one class, not a chain.

    A widget reporting ScrolledText would be looked up under that tag and
    find none of the Text class bindings - so every key would reach it and
    do nothing, typing included. tkinter never has the problem: its Tk
    class is whatever the widget was created as, which for a Text subclass
    is still Text.
    """
    assert ScrolledText(root).winfo_class() == "Text"


def test_its_binding_tags_include_the_text_tag(root):
    assert "Text" in ScrolledText(root).bindtags()
