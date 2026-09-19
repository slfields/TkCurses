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


"""Stacking order, hit-testing, and the rule that ties them together.

**The widget that draws a cell is the widget that receives a click on it.**

Two separate mechanisms answer those two questions - the panel stack paints,
and hit-testing reads the panel stack back - and the whole area works only
while they agree. Both bugs this project has found by hand here were a
disagreement: TkCurses-bk8 raised a container's panel without its children's,
so the container drew over its own contents while clicks still went to the
children underneath.

Nothing in this module can fail with one widget.
"""

from __future__ import annotations

import tkcurses
from tests.integration.conftest import build, widget_at, z_order

# ------------------------------------------------ a container and its children


def test_a_child_is_in_front_of_the_container_that_holds_it(app):
    made = build(app, {"panel": {"inner": None}})
    order = z_order(app)
    assert order.index(made["inner"]) > order.index(made["panel"])


def test_a_click_inside_a_child_reaches_the_child_not_the_container(app):
    made = build(app, {"panel": {"inner": None}})
    inner = made["inner"]
    assert widget_at(app, inner.winfo_rootx(), inner.winfo_rooty()) is inner


def test_a_click_in_the_container_beside_a_child_reaches_the_container(app):
    made = build(app, {"panel": {"inner": None}})
    inner = made["inner"]
    beside = inner.winfo_rootx() + inner._rect.width + 1
    assert widget_at(app, beside, inner.winfo_rooty()) is made["panel"]


def test_raising_a_container_keeps_its_children_in_front_of_it(app):
    """Regression, TkCurses-bk8, at the level it was actually reported.

    The unit test asserts the panel order. This asserts the thing a person
    saw: the window came forward and its contents did not come with it.
    """
    made = build(app, {"first": {"inner": None}, "second": None})
    made["second"].tkraise()

    made["first"].tkraise()

    order = z_order(app)
    assert order.index(made["inner"]) > order.index(made["first"])
    assert order.index(made["first"]) > order.index(made["second"])


def test_a_raised_container_still_gives_its_cells_to_its_children(app):
    """The other half of bk8, and the half a panel-order assertion misses.

    Order being right is not the claim. The claim is that drawing and
    hit-testing agree - so after the raise, the cell the child occupies must
    still answer with the child.
    """
    made = build(app, {"first": {"inner": None}, "second": None})
    inner = made["inner"]
    made["first"].tkraise()
    assert widget_at(app, inner.winfo_rootx(), inner.winfo_rooty()) is inner


def test_lowering_a_container_takes_its_children_with_it(app):
    made = build(app, {"first": {"inner": None}, "second": None})
    made["first"].lower()
    order = z_order(app)
    assert order.index(made["first"]) < order.index(made["inner"])
    assert order.index(made["inner"]) < order.index(made["second"])


# --------------------------------------------------------- overlapping windows


def test_the_window_in_front_takes_a_click_they_both_cover(app):
    back = tkcurses.Toplevel(app, width=20, height=6)
    back.geometry("20x6+5+3")
    front = tkcurses.Toplevel(app, width=20, height=6)
    front.geometry("20x6+10+5")
    app.update_layout()

    # A cell inside both: front's top-left corner is over back's interior.
    assert widget_at(app, 12, 6) is front
    # And one only the back window covers.
    assert widget_at(app, 6, 4) is back


def test_raising_the_back_window_changes_who_takes_the_click(app):
    back = tkcurses.Toplevel(app, width=20, height=6)
    back.geometry("20x6+5+3")
    front = tkcurses.Toplevel(app, width=20, height=6)
    front.geometry("20x6+10+5")
    app.update_layout()
    assert widget_at(app, 12, 6) is front

    back.tkraise()

    assert widget_at(app, 12, 6) is back


def test_a_click_outside_every_window_reaches_the_root(app):
    window = tkcurses.Toplevel(app, width=10, height=4)
    window.geometry("10x4+2+2")
    app.update_layout()
    assert widget_at(app, 60, 20) is app


def test_a_destroyed_window_stops_taking_clicks(app):
    back = tkcurses.Toplevel(app, width=20, height=6)
    back.geometry("20x6+5+3")
    front = tkcurses.Toplevel(app, width=20, height=6)
    front.geometry("20x6+5+3")
    app.update_layout()
    assert widget_at(app, 8, 5) is front

    front.destroy()

    assert widget_at(app, 8, 5) is back


def test_a_moved_window_takes_clicks_where_it_now_is(app):
    """Moving is not resizing, and the rect is an offset from the master -
    so nothing in the tree changes when a window moves. The panel has to be
    asked where it actually went.
    """
    window = tkcurses.Toplevel(app, width=10, height=4)
    window.geometry("10x4+2+2")
    app.update_layout()
    assert widget_at(app, 4, 3) is window

    window.geometry("10x4+40+10")
    app.update_layout()

    assert widget_at(app, 4, 3) is app
    assert widget_at(app, 42, 11) is window
