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


"""What a master's clipping does to a child's window, and to a click.

The drawing is in ``tests/test_master_clipping_tty.py``. These are the
halves with no appearance: which cells the window covers, who a click on the
clipped-off part reaches, and what the widget still reports about itself.
Measured against Tk 9.0.2 with a 90-pixel frame in a 50-pixel one: ``winfo
containing`` over the overflow answers whatever is underneath - the root, or
the sibling it covers - and a child wholly outside its master is still
mapped and viewable, at the geometry it was given. TkCurses-wbov.
"""

from __future__ import annotations

import pytest

import tkcurses
from tkcurses._core.geometry import Rect


@pytest.fixture
def tree(app):
    frame = tkcurses.Frame(app, name="frame")
    frame.place(x=10, y=2, width=5, height=3)
    wide = tkcurses.Frame(frame, name="wide")
    wide.place(x=-2, y=0, width=12, height=1)
    beside = tkcurses.Frame(app, name="beside")
    beside.place(x=16, y=2, width=4, height=3)
    gone = tkcurses.Frame(frame, name="gone")
    gone.place(x=7, y=1, width=2, height=1)
    app.update_layout()
    return {"frame": frame, "wide": wide, "beside": beside, "gone": gone}


def test_a_childs_window_covers_only_the_part_inside_its_master(tree):
    assert tree["wide"]._panel.rect == Rect(10, 2, 5, 1)


def test_its_geometry_is_what_it_was_given(tree):
    wide = tree["wide"]
    assert (wide.winfo_x(), wide.winfo_width()) == (-2, 12)


def test_a_click_inside_the_master_reaches_the_child(app, tree):
    assert app.winfo_containing(12, 2) is tree["wide"]


def test_a_click_on_the_overflow_reaches_what_is_underneath(app, tree):
    """Column 15 is between the two frames, and 16 is ``beside``: the wide
    child runs over both, and owns neither."""
    assert app.winfo_containing(15, 2) is app
    assert app.winfo_containing(16, 2) is tree["beside"]
    assert app.winfo_containing(9, 2) is app


def test_a_child_wholly_outside_its_master_has_no_window(tree):
    """And is still mapped, as Tk says it is."""
    gone = tree["gone"]
    assert gone._panel is None
    assert gone.winfo_ismapped()
    assert gone.winfo_viewable()


def test_it_gets_its_window_back_when_it_moves_inside(tree):
    gone = tree["gone"]
    gone.place(x=1, y=1)
    gone.update_layout()
    assert gone._panel is not None
    assert gone._panel.rect == Rect(11, 3, 2, 1)


def test_a_master_shrinking_clips_a_child_it_did_not_move(app, tree):
    tree["frame"].place(width=3)
    app.update_layout()
    assert tree["wide"]._panel.rect == Rect(10, 2, 3, 1)


def test_a_posted_menu_is_not_clipped_by_its_master(app, tree):
    """A Menu is a toplevel window in Tk, posted against the screen, and
    an OptionMenu makes its menu a child of the button."""
    menu = tkcurses.Menu(tree["frame"], tearoff=False)
    menu.add_command(label="a long entry that is wider than the frame")
    menu.post(10, 2)
    assert menu._panel.rect.width == menu.winfo_width()
    assert menu._panel.rect.width > 5
