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

"""Tests for the Message widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Label, Message, Misc, StringVar
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack
from tkcurses._core.text import measure, wrap


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def stack():
    return PanelStack(window_factory=stub_window, panel_factory=None)


@pytest.fixture
def root(stack):
    root = Misc()
    root.tk.panels = stack
    root._rect = Rect(0, 0, 80, 24)
    root._mapped = True
    return root


PARAGRAPH = (
    "A Message picks its own line length, aiming for a block of text "
    "whose width is aspect percent of its height."
)


def ratio(message):
    """The aspect the chosen wrap width actually produced."""
    width, height = measure(message._lines())
    return 100 * width / height


# ----------------------------------------------------------------- the shape


def test_a_message_wraps_without_being_told_where(root):
    """A Label given no wraplength is one long line; a Message is not."""
    assert len(Message(root, name="m", text=PARAGRAPH)._lines()) > 1


def test_a_wider_aspect_gives_wider_lines(root):
    narrow = Message(root, name="a", text=PARAGRAPH, aspect=100)
    wide = Message(root, name="b", text=PARAGRAPH, aspect=400)
    assert wide._wrap_width() > narrow._wrap_width()


def test_the_block_comes_out_near_the_aspect_asked_for(root):
    for aspect in (100, 200, 400):
        message = Message(root, name=f"m{aspect}", text=PARAGRAPH, aspect=aspect)
        # A step function of the width: no wrap point gives exactly the
        # ratio, so what is checked is that none of the others is closer.
        chosen = abs(ratio(message) - aspect)
        best = min(
            abs(100 * w / h - aspect)
            for w, h in (
                measure(wrap(PARAGRAPH, width))
                for width in range(1, len(PARAGRAPH) + 1)
            )
            if h
        )
        assert chosen == pytest.approx(best)


def test_width_overrides_the_aspect(root):
    message = Message(root, name="m", text=PARAGRAPH, aspect=400, width=20)
    assert message._wrap_width() == 20
    assert all(len(line) <= 20 for line in message._lines())


def test_wraplength_overrides_width(root):
    message = Message(root, name="m", text=PARAGRAPH, width=40, wraplength=15)
    assert message._wrap_width() == 15


def test_empty_text_is_harmless(root):
    """One empty line, which is what an empty Label gives too."""
    assert (
        Message(root, name="m", text="")._lines()
        == Label(root, name="l", text="")._lines()
    )


def test_one_word_is_never_broken(root):
    message = Message(root, name="m", text="antidisestablishmentarianism")
    assert message._lines() == ["antidisestablishmentarianism"]


def test_a_message_asks_for_the_block_it_chose(root):
    message = Message(root, name="m", text=PARAGRAPH)
    width, height = measure(message._lines())
    assert message.winfo_reqwidth() == width
    assert message.winfo_reqheight() == height


def test_a_message_justifies_left_where_a_label_centres(root):
    """Tk's default, and what makes it read as a paragraph, not a banner."""
    assert Message(root, name="m")._options["justify"] == "left"
    assert Label(root, name="l")._options["justify"] == "center"


# ------------------------------------------------------------- the variable


def test_a_textvariable_supplies_the_text(root):
    variable = StringVar(root, PARAGRAPH)
    assert len(Message(root, name="m", textvariable=variable)._lines()) > 1


def test_changing_the_variable_re_wraps(root):
    variable = StringVar(root, "short")
    message = Message(root, name="m", textvariable=variable)
    assert message._lines() == ["short"]
    variable.set(PARAGRAPH)
    assert len(message._lines()) > 1


def test_the_chosen_width_is_not_cached_across_a_change(root):
    """The search is cached; the cache must not outlive its text."""
    message = Message(root, name="m", text=PARAGRAPH)
    first = message._wrap_width()
    message.configure(text="a b c")
    assert message._wrap_width() != first


def test_the_chosen_width_is_not_cached_across_an_aspect_change(root):
    message = Message(root, name="m", text=PARAGRAPH, aspect=100)
    first = message._wrap_width()
    message.configure(aspect=400)
    assert message._wrap_width() != first
