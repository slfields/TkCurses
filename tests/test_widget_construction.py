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

"""What making a widget does when the name is taken or an option refused,
and what destroying one does to its geometry manager.

Measured through tkinter on Python 3.14 over Tk 9.0.2 - not through raw Tcl,
whose answers a tkinter program never sees: Tk refuses a name already in use,
but tkinter destroys the widget holding it first. TkCurses-use6, TkCurses-lwoi,
TkCurses-41zl.
"""

from __future__ import annotations

import pytest

import tkcurses
from tkcurses import Button, Frame, Label, Misc, TclError, Text, ttk
from tkcurses._core.geometry import Rect


@pytest.fixture
def root():
    root = Misc()
    root._rect = Rect(0, 0, 40, 10)
    root._mapped = True
    return root


# ------------------------------------------------------- a name already taken


def test_a_name_in_use_destroys_the_widget_holding_it(root):
    old = Button(root, name="b", text="first")
    new = Label(root, name="b", text="second")
    assert old.winfo_exists() == 0
    assert root.children["b"] is new
    assert root.nametowidget(".b") is new
    assert new.winfo_class() == "Label"
    assert new.cget("text") == "second"


def test_the_widget_replaced_hears_destroy(root):
    old = Button(root, name="b")
    heard = []
    old.bind("<Destroy>", lambda event: heard.append(event.widget))
    Label(root, name="b")
    assert heard == [old]


def test_the_widget_replaced_takes_its_children_with_it(root):
    old = Frame(root, name="f")
    child = Label(old, name="c")
    Frame(root, name="f")
    assert child.winfo_exists() == 0
    with pytest.raises(KeyError):
        root.nametowidget(".f.c")


def test_the_widget_replaced_gives_up_its_place(root):
    Label(root, name="b", text="old").pack()
    new = Label(root, name="b", text="new")
    new.pack()
    assert root.pack_slaves() == [new]


def test_a_name_used_under_another_parent_is_another_widget(root):
    first = Frame(root, name="f")
    one = Label(root, name="x")
    two = Label(first, name="x")
    assert one.winfo_exists() and two.winfo_exists()


# ---------------------------------------------------- an option refused


def test_a_refused_option_leaves_the_object_in_children_without_a_window(root):
    """As tkinter: ``nametowidget`` finds it, but Tk made no window."""
    with pytest.raises(TclError, match='unknown option "-bogus"'):
        Button(root, name="x", bogus=1)
    ghost = root.children["x"]
    assert root.nametowidget(".x") is ghost
    assert ghost.winfo_exists() == 0
    assert root.winfo_children() == []
    # Found through children, as tkinter finds it, and not as a window: no
    # event, focus or query that walks the windows reaches it.
    assert root.tk.widgets.get(".x") is None


@pytest.mark.parametrize(
    ("make", "options"),
    [
        (Button, {"width": "abc"}),
        (Label, {"bitmap": "nonsense"}),
        (Text, {"width": "abc"}),
        (ttk.Entry, {"width": "abc"}),
        (tkcurses.Scale, {"from_": "x"}),
    ],
)
def test_a_value_refused_after_the_options_are_read_leaves_no_window(
    root, make, options
):
    """Refused in the class's own ``__init__``, after ``BaseWidget``'s."""
    with pytest.raises(TclError):
        make(root, name="x", **options)
    assert root.children["x"].winfo_exists() == 0
    assert root.winfo_children() == []


def test_a_failed_widget_is_found_by_its_full_path_from_anywhere(root):
    frame = Frame(root, name="f")
    with pytest.raises(TclError):
        Button(frame, name="x", bogus=1)
    assert Label(root, name="l").nametowidget(".f.x") is frame.children["x"]


def test_a_failed_widget_still_used_its_generated_name(root):
    """Measured: the next Button after a refused one is ``!button2``."""
    with pytest.raises(TclError):
        Button(root, bogus=1)
    assert Button(root)._name == "!button2"


def test_destroying_a_failed_widget_takes_it_out_of_children(root):
    with pytest.raises(TclError):
        Button(root, name="x", bogus=1)
    root.children["x"].destroy()
    assert "x" not in root.children


def test_a_name_left_by_a_failed_widget_can_be_used(root):
    with pytest.raises(TclError):
        Button(root, name="x", bogus=1)
    real = Button(root, name="x", text="real")
    assert real.winfo_exists()
    assert root.winfo_children() == [real]


def test_a_failure_before_the_widget_is_named_arrives_unchanged(root):
    with pytest.raises(ValueError, match="may not contain"):
        Button(root, name="a.b")


def test_no_root_is_reported_as_no_root(monkeypatch):
    monkeypatch.setattr(tkcurses, "_default_root", None)
    with pytest.raises(TclError, match="No root window"):
        Button(text="x")


def test_a_subclass_that_fails_late_leaves_no_bindings_or_timers(root):
    """A program's own widget class, binding and scheduling before it fails:
    nothing it set up runs against the window that was never made."""
    ran = []

    class Failing(Button):
        def __init__(self, master, **kw):
            super().__init__(master, **kw)
            self.bind("<Key>", lambda event: ran.append("key"))
            self.after(0, lambda: ran.append("timer"))
            raise TclError("refused late")

    with pytest.raises(TclError, match="refused late"):
        Failing(root, name="x")
    assert root.tk.bindings.sequences(".x") == ()
    root.update()
    assert ran == []


# ------------------------------------------- destroy and the geometry managers


def test_a_destroyed_widget_gives_its_space_to_the_next(root):
    first = Label(root, name="a", text="AAAA")
    first.pack(side="top")
    second = Label(root, name="b", text="BBBB")
    second.pack(side="top")
    root.update_layout()
    assert second.winfo_y() == 1
    first.destroy()
    root.update_layout()
    assert second.winfo_y() == 0
    assert root.pack_slaves() == [second]


def test_a_destroyed_widget_leaves_the_grid(root):
    frame = Frame(root, name="f")
    Button(frame, name="x").grid(row=0, column=0)
    frame.children["x"].destroy()
    assert frame.grid_slaves() == []


def test_a_destroyed_widget_leaves_place(root):
    frame = Frame(root, name="f")
    Button(frame, name="x").place(x=0, y=0)
    frame.children["x"].destroy()
    assert frame.place_slaves() == []


def test_a_destroyed_container_takes_its_packed_children_quietly(root):
    frame = Frame(root, name="f")
    frame.pack()
    Label(frame, name="a").pack()
    Label(frame, name="b").pack()
    frame.destroy()
    root.update_layout()
    assert root.pack_slaves() == []
