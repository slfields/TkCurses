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


"""A dialog over an application that already has widgets on it.

The dialogs are the largest things in this library built out of other
widgets, and every test of them so far has opened one over an empty root.
That cannot show the thing a dialog is *for*: being in front of, and in the
way of, an application that is still there underneath.

Four claims, and none of them is a property of the dialog alone:

- The grab holds - the application underneath does not get the clicks.
- The dialog is in front, and its own contents are in front of it.
- Closing gives back the keyboard and the grab that were displaced, rather
  than merely dropping its own.
- Nested dialogs unwind in the right order.

``take_focus_grab``/``restore_focus_grab`` exist because ``grab_release``
does not put anything back - it releases, full stop - so a dialog opened
from inside another would leave the outer one with no keyboard and the
application looking wedged.
"""

from __future__ import annotations

import pytest

import tkcurses
from tests.integration.conftest import through_grab, widget_at, z_order
from tkcurses.commondialog import restore_focus_grab, take_focus_grab


@pytest.fixture
def application(app):
    """Widgets already on screen, the way there would be under a dialog."""
    frame = tkcurses.Frame(app, name="main")
    frame.place(x=0, y=0, width=40, height=12)
    field = tkcurses.Entry(frame, name="field")
    field.place(x=1, y=1, width=20)
    button = tkcurses.Button(frame, name="go", text="Go")
    button.place(x=1, y=3, width=8)
    app.update_layout()
    field.focus_set()
    return {"frame": frame, "field": field, "button": button}


def open_dialog(app, name="dlg", **geometry):
    """A modal window shaped like one of the dialogs, taking the grab the
    same way ``commondialog`` does.

    A real Toplevel with a real grab rather than a Dialog subclass, because
    Dialog.__init__ ends in wait_window() and blocks. What is under test is
    the grab and the stacking, and those are the same either way; the real
    dialog classes are driven in the tty tests, where there is a loop to
    close them.

    **The order here is load-bearing**: the grab is taken before the focus
    moves, which is what commondialog does and what simpledialog and
    filedialog do not (TkCurses-3wi). Written the other way round, every
    restore test below fails - which is how the bug was found.
    """
    window = tkcurses.Toplevel(app, width=20, height=6, name=name)
    window.geometry(geometry.get("geometry", "20x6+5+3"))
    content = tkcurses.Entry(window, name="entry")
    content.place(x=1, y=1, width=10)
    app.update_layout()
    displaced = take_focus_grab(window)
    content.focus_set()
    return window, content, displaced


# ------------------------------------------------------------------ the grab


def test_the_dialog_holds_the_grab(app, application):
    window, _content, _displaced = open_dialog(app)
    assert window.grab_current() is window
    assert window.grab_status() == "local"


def test_a_click_on_the_application_underneath_goes_to_the_dialog(app, application):
    """The whole point of modality, and it needs both windows to show."""
    window, _content, _displaced = open_dialog(app)
    button = application["button"]

    landed = widget_at(app, button.winfo_rootx(), button.winfo_rooty())

    assert landed is button, "the click really is over the button"
    assert through_grab(app, landed) is window


def test_a_click_inside_the_dialog_reaches_the_dialogs_own_widget(app, application):
    _window, content, _displaced = open_dialog(app)

    landed = widget_at(app, content.winfo_rootx(), content.winfo_rooty())

    assert landed is content
    assert through_grab(app, landed) is content


def test_releasing_the_grab_lets_the_application_have_its_clicks_back(app, application):
    window, _content, displaced = open_dialog(app)
    button = application["button"]
    assert through_grab(app, button) is window

    restore_focus_grab(window, displaced)

    assert through_grab(app, button) is button


# --------------------------------------------------------------- the stacking


def test_the_dialog_is_in_front_of_the_application(app, application):
    window, _content, _displaced = open_dialog(app)
    order = z_order(app)
    assert order.index(window) > order.index(application["frame"])


def test_the_dialogs_own_widgets_are_in_front_of_the_dialog(app, application):
    """The bk8 rule, in the place it would be noticed first: a dialog that
    buries its own buttons is a dialog nobody can answer.
    """
    window, content, _displaced = open_dialog(app)
    window.tkraise()

    order = z_order(app)
    assert order.index(content) > order.index(window)
    assert widget_at(app, content.winfo_rootx(), content.winfo_rooty()) is content


def test_the_application_is_still_there_underneath(app, application):
    """A dialog covers; it does not destroy. The widgets under it keep their
    windows, so the screen can be put back when it closes.
    """
    _window, _content, _displaced = open_dialog(app)

    assert application["button"].winfo_exists()
    assert application["button"]._panel is not None


# ------------------------------------------------------------------ the focus


def test_opening_a_dialog_moves_the_focus_into_it(app, application):
    _window, content, _displaced = open_dialog(app)
    assert content.focus_get() is content


def test_closing_gives_the_focus_back_to_what_had_it(app, application):
    """grab_release does not put anything back, which is why the pair exists."""
    field = application["field"]
    assert field.focus_get() is field
    window, _content, displaced = open_dialog(app)

    restore_focus_grab(window, displaced)

    assert field.focus_get() is field


def test_closing_gives_the_grab_back_to_what_had_it(app, application):
    """A dialog opened from inside another. Without the pair, closing the
    inner one leaves the outer holding no grab at all, and the application
    looks wedged while a window is plainly sitting there.
    """
    outer, _outer_content, outer_displaced = open_dialog(app, name="outer")
    inner, _inner_content, inner_displaced = open_dialog(
        app, name="inner", geometry="20x6+8+5"
    )
    assert inner.grab_current() is inner

    restore_focus_grab(inner, inner_displaced)

    assert outer.grab_current() is outer

    restore_focus_grab(outer, outer_displaced)

    assert app.tk.grab is None


def test_nested_dialogs_unwind_in_order(app, application):
    field = application["field"]
    outer, outer_content, outer_displaced = open_dialog(app, name="outer")
    inner, _inner, inner_displaced = open_dialog(app, name="inner", geometry="20x6+8+5")

    restore_focus_grab(inner, inner_displaced)
    assert outer_content.focus_get() is outer_content

    restore_focus_grab(outer, outer_displaced)
    assert field.focus_get() is field


# ------------------------------------------------------------- the call order


def test_taking_the_grab_after_moving_the_focus_restores_nothing(app, application):
    """The bug itself, written as what it does rather than left implicit.

    ``take_focus_grab`` records what it displaces and then grabs, so it has
    to be called *before* the dialog moves the focus into itself. Called
    after, the tuple holds the dialog's own widget; ``restore_focus_grab``
    guards with ``winfo_exists()``, that widget is destroyed by then, and so
    nothing at all is put back - the precise failure the pair exists to
    prevent, defeated by call order.

    This passes today because it asserts the broken behaviour. It is here so
    that the two wrong call sites have something that describes them, and so
    that the fixture above cannot quietly drift into the same order.
    """
    field = application["field"]
    field.focus_set()
    window = tkcurses.Toplevel(app, width=20, height=6, name="late")
    window.geometry("20x6+5+3")
    content = tkcurses.Entry(window, name="entry")
    content.place(x=1, y=1, width=10)
    app.update_layout()

    # simpledialog.py:98 and filedialog.py:269 in miniature.
    content.focus_set()
    displaced = take_focus_grab(window)

    assert displaced[1] is content, "it displaced its own widget, not the field"

    window.destroy()
    restore_focus_grab(window, displaced)

    assert field.focus_get() is not field
