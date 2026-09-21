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


"""Destroying a populated tree, and what must be left behind: nothing.

A widget alone can be destroyed and nobody notices. The interesting failures
are what a destroyed widget is still attached to - its parent's child list,
the panel stack, the binding table, a variable's trace list, a pending
timer, the focus and the grab. Each of those is somewhere else, which is why
this is an integration module.

The rule throughout: **after teardown, nothing can still reach the widget,
and nothing the widget reached is damaged.** Both halves matter. A teardown
that leaves a dead widget wired in is a crash waiting for the next event; a
teardown that takes its neighbours down with it is worse.
"""

from __future__ import annotations

import pytest

import tkcurses
from tests.integration.conftest import widget_at, z_order


@pytest.fixture
def tree(app):
    """A window, a frame in it, two widgets in that, one beside it."""
    top = tkcurses.Toplevel(app, width=30, height=10, name="top")
    top.geometry("30x10+2+2")
    frame = tkcurses.Frame(top, name="frame")
    frame.place(x=1, y=1, width=20, height=6)
    field = tkcurses.Entry(frame, name="field")
    field.place(x=1, y=1, width=10)
    button = tkcurses.Button(frame, name="button", text="Go")
    button.place(x=1, y=3, width=8)
    outside = tkcurses.Label(top, name="outside", text="kept")
    outside.place(x=1, y=8, width=10)
    app.update_layout()
    return {
        "top": top,
        "frame": frame,
        "field": field,
        "button": button,
        "outside": outside,
    }


# ------------------------------------------------------------ down the tree


def test_destroying_a_container_destroys_its_children(tree):
    tree["frame"].destroy()

    assert not tree["field"].winfo_exists()
    assert not tree["button"].winfo_exists()


def test_destroying_a_container_leaves_its_siblings_alone(tree):
    """The half that a recursive teardown gets wrong by reaching too far."""
    tree["frame"].destroy()

    assert tree["outside"].winfo_exists()
    assert tree["top"].winfo_exists()


def test_a_destroyed_subtree_leaves_the_parents_child_list(tree):
    top = tree["top"]

    tree["frame"].destroy()

    assert "frame" not in top.children
    assert "outside" in top.children


def test_destroying_twice_is_harmless(tree):
    """A parent's teardown may reach a child the application already
    destroyed, so this is a normal path rather than a defensive one.
    """
    tree["field"].destroy()
    tree["field"].destroy()

    assert not tree["field"].winfo_exists()


# --------------------------------------------------------- the panel stack


def test_a_destroyed_widget_gives_up_its_panel(tree):
    field = tree["field"]
    assert field._panel is not None

    field.destroy()

    assert field._panel is None


def test_a_destroyed_subtree_leaves_the_z_order(tree):
    frame = tree["frame"]
    field = tree["field"]
    assert field in z_order(tree["top"].master)

    frame.destroy()

    order = z_order(tree["top"].master)
    assert field not in order
    assert frame not in order
    assert tree["outside"] in order


def test_the_cells_a_destroyed_widget_had_go_back_to_what_is_under_them(tree):
    """The visible half: something else owns those cells now, and a click
    there must reach it rather than a widget that no longer exists.
    """
    app = tree["top"].master
    field = tree["field"]
    where = (field.winfo_rootx(), field.winfo_rooty())
    assert widget_at(app, *where) is field

    field.destroy()

    assert widget_at(app, *where) is tree["frame"]


# ------------------------------------------------------------- the bindings


def test_a_destroyed_widgets_bindings_are_gone(tree):
    field = tree["field"]
    fired = []
    field.bind("<Key-a>", lambda event: fired.append("x"))

    field.destroy()

    assert not field.bind()
    assert fired == []


def test_bind_hands_back_a_tuple(tree):
    """Measured on Tk 9.0.2: bind() answers () and ('a',) - tuples. Here it
    is a list, so ``widget.bind() + ('x',)`` raises and a comparison to ()
    fails on something otherwise correct.

    Separated from the test above on purpose: that one is about bindings
    being gone, and asserting the container type there would have made a
    cosmetic divergence look like a teardown failure.
    """
    assert tree["field"].bind() == ()


def test_destroying_a_child_leaves_a_siblings_bindings(tree):
    fired = []
    tree["button"].bind("<Key-a>", lambda event: fired.append("button"))

    tree["field"].destroy()
    tree["button"].event_generate("<Key-a>")

    assert fired == ["button"]


# ------------------------------------------------------- focus and the grab


def test_destroying_the_focused_widget_clears_the_focus(tree):
    field = tree["field"]
    field.focus_set()

    field.destroy()

    assert tree["top"].focus_get() is not field


def test_destroying_the_grab_holder_releases_the_grab(tree):
    """Otherwise every later event is routed to a window that is not there,
    and the application is wedged with nothing on screen to explain it.
    """
    top = tree["top"]
    top.grab_set()
    assert top.grab_current() is top

    top.destroy()

    assert tree["outside"].grab_current() is None


# ---------------------------------------------------------------- variables


def test_a_destroyed_widget_stops_following_its_variable(tree):
    shared = tkcurses.StringVar(tree["top"], value="one")
    tree["field"].configure(textvariable=shared)
    kept = tkcurses.Label(tree["top"], name="kept", textvariable=shared)
    kept.place(x=1, y=7, width=10)

    tree["field"].destroy()
    shared.set("two")

    assert kept._text() == "two"


def test_setting_a_variable_after_its_widget_died_does_not_raise(tree):
    """Measured on Tk 9.0.2: fine, no error. A trace list holding a dead
    widget would raise here instead.
    """
    shared = tkcurses.StringVar(tree["top"], value="one")
    tree["field"].configure(textvariable=shared)

    tree["field"].destroy()

    shared.set("two")
    assert shared.get() == "two"


# ------------------------------------------------------------------- timers


def test_a_pending_callback_does_not_fire_on_a_destroyed_widget(tree, app):
    """Measured on Tk 9.0.2: it does not fire. Tk owns the handle as a
    command belonging to the widget, so destroying the widget drops it.

    Here it fires, against a widget whose window and panel are None and
    which is no longer in the tree. ttk.Progressbar already works around
    this by hand - its own handle, cancelled in destroy(), plus a
    winfo_exists() guard at the top of its tick - which is the tell that
    every widget that schedules anything needs the same and only one has it.
    """
    fired = []
    tree["field"].after(0, lambda: fired.append("fired"))

    tree["field"].destroy()
    app.tk.timers.run_due()

    assert fired == []


def test_a_pending_callback_on_a_surviving_widget_still_fires(tree, app):
    """The control. A fix for the above must not simply stop running timers."""
    fired = []
    tree["outside"].after(0, lambda: fired.append("fired"))

    tree["field"].destroy()
    app.tk.timers.run_due()

    assert fired == ["fired"]


def test_a_pending_callback_does_not_fire_when_an_ancestor_is_destroyed(tree, app):
    """Destroying a container takes its children's timers with it, because
    it destroys the children and each drops its own.
    """
    fired = []
    tree["field"].after(0, lambda: fired.append("fired"))

    tree["frame"].destroy()
    app.tk.timers.run_due()

    assert fired == []


def test_a_pending_idle_callback_goes_too(tree, app):
    fired = []
    tree["field"].after_idle(lambda: fired.append("fired"))

    tree["field"].destroy()
    app.tk.timers.run_idle()

    assert fired == []
