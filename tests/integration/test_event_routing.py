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


"""Where an event goes, and which of the four tags answers it.

An event does not reach a widget. It reaches a *list of tags* - the widget's
own path, its class, its toplevel, then ``all`` - and every binding on every
tag runs, in that order, until one says ``"break"``. Nothing here can fail
with one widget, because the third tag is another widget and the order only
matters when more than one binding exists.

**The trap this module exists for.** Binding tags name one class, not a chain
of them. A widget that subclasses another reports its own name from
``winfo_class()``, is looked up under that tag, and finds none of the parent
class's bindings - so every gesture reaches it and does nothing. That has now
bitten four times: Spinbox/Entry, OptionMenu/Menubutton, ScrolledText/Text
and Toplevel/Dialog. tkinter never has the problem, its Tk class being
whatever the underlying widget was created as.

There are two valid cures and the library uses both. ``ScrolledText`` reports
``Text``, because it wants Text's behaviour unchanged. ``Spinbox`` and
``Menubutton`` register their bindings again under their own name, because
they add to it. What has to be true either way is one thing, and it is what
``test_every_widget_is_reachable_under_the_class_it_reports`` checks.
"""

from __future__ import annotations

import inspect

import pytest

import tkcurses
from tkcurses import scrolledtext


@pytest.fixture
def window(app):
    """A toplevel with a widget in it: three of the four tags, really present."""
    top = tkcurses.Toplevel(app, width=20, height=8)
    top.geometry("20x8+2+2")
    label = tkcurses.Label(top, name="l", text="x")
    label.place(x=1, y=1)
    app.update_layout()
    return top, label


# ------------------------------------------------------------------ the tags


def test_the_four_tags_are_path_class_toplevel_and_all(window):
    top, label = window
    assert label.bindtags() == (str(label), "Label", str(top), "all")


def test_a_toplevel_does_not_name_itself_twice(window):
    """The toplevel tag is skipped when the widget is the toplevel, or a
    window would run its own bindings twice for every event."""
    top, _label = window
    assert top.bindtags() == (str(top), "Toplevel", "all")


def test_every_tag_runs_in_order(window):
    top, label = window
    ran = []
    label.bind("<Key-a>", lambda event: ran.append("widget"))
    label.bind_class("Label", "<Key-a>", lambda event: ran.append("class"))
    top.bind("<Key-a>", lambda event: ran.append("toplevel"))
    label.bind_all("<Key-a>", lambda event: ran.append("all"))

    label.event_generate("<Key-a>")

    assert ran == ["widget", "class", "toplevel", "all"]


def test_break_from_a_widget_binding_stops_the_tags_after_it(window):
    """What lets an application override a default without removing it."""
    top, label = window
    ran = []
    label.bind("<Key-b>", lambda event: (ran.append("widget"), "break")[1])
    label.bind_class("Label", "<Key-b>", lambda event: ran.append("class"))
    top.bind("<Key-b>", lambda event: ran.append("toplevel"))

    label.event_generate("<Key-b>")

    assert ran == ["widget"]


def test_add_runs_both_bindings_on_one_tag(window):
    _top, label = window
    ran = []
    label.bind("<Key-c>", lambda event: ran.append("first"))
    label.bind("<Key-c>", lambda event: ran.append("second"), add="+")

    label.event_generate("<Key-c>")

    assert ran == ["first", "second"]


def test_binding_without_add_replaces_the_one_before_it(window):
    _top, label = window
    ran = []
    label.bind("<Key-d>", lambda event: ran.append("first"))
    label.bind("<Key-d>", lambda event: ran.append("second"))

    label.event_generate("<Key-d>")

    assert ran == ["second"]


# ------------------------------------------------- a child and its containers


def test_a_childs_event_does_not_run_its_parents_widget_binding(window):
    """A parent Frame is not one of the child's tags. Only the *toplevel* is,
    which is why a window can watch its contents and a frame cannot.
    """
    top, _label = window
    frame = tkcurses.Frame(top, name="f")
    frame.place(x=1, y=3, width=10, height=3)
    inner = tkcurses.Label(frame, name="i", text="y")
    inner.place(x=0, y=0)
    ran = []
    frame.bind("<Key-e>", lambda event: ran.append("frame"))

    inner.event_generate("<Key-e>")

    assert ran == []
    assert str(frame) not in inner.bindtags()


def test_a_childs_event_does_run_the_toplevels_tag(window):
    top, label = window
    ran = []
    top.bind("<Key-f>", lambda event: ran.append("toplevel"))

    label.event_generate("<Key-f>")

    assert ran == ["toplevel"]


def test_two_windows_do_not_hear_each_others_events(app):
    first = tkcurses.Toplevel(app, width=10, height=4)
    second = tkcurses.Toplevel(app, width=10, height=4)
    inside = tkcurses.Label(first, name="l", text="x")
    inside.place(x=0, y=0)
    app.update_layout()
    ran = []
    first.bind("<Key-g>", lambda event: ran.append("first"))
    second.bind("<Key-g>", lambda event: ran.append("second"))

    inside.event_generate("<Key-g>")

    assert ran == ["first"]


# -------------------------------------------------------------- the class tag


def widget_classes():
    """Every widget class that installs class bindings, found rather than listed.

    Enumerated instead of hand-written on purpose. The hand-written version
    of this list missed Checkbutton and Radiobutton, and the hole was only
    found by deliberately reintroducing the bug in ``_ChoiceWidget`` and
    watching the suite stay green. A list has to be remembered; this cannot
    fall behind a widget somebody adds next year.
    """
    found = []
    for name in sorted(dir(tkcurses)):
        obj = getattr(tkcurses, name)
        if (
            inspect.isclass(obj)
            and not name.startswith("_")
            and hasattr(obj, "_install_class_bindings")
            and hasattr(obj, "winfo_class")
        ):
            found.append((name, obj))
    found.append(("ScrolledText", scrolledtext.ScrolledText))
    return found


def make(cls, parent):
    """One of ``cls``, whatever arguments it happens to need."""
    if cls is tkcurses.OptionMenu:
        return cls(parent, tkcurses.StringVar(parent), "one", "two")
    return cls(parent)


@pytest.mark.parametrize(
    ("label", "cls"), widget_classes(), ids=[n for n, _ in widget_classes()]
)
def test_every_widget_is_reachable_under_the_class_it_reports(app, label, cls):
    """The one invariant that would have caught all four traps.

    Not "winfo_class() returns the parent's name" - that is only one of the
    two cures, and Spinbox deliberately does the other. What must hold either
    way is that **a widget which installs class bindings installs them under
    the name its own instances report**. A widget reporting a class nobody
    registered gets no class bindings at all, which is exactly what each of
    the four failures was.
    """
    widget = make(cls, app)
    reported = widget.winfo_class()

    assert reported in widget.bindtags()
    assert reported in app.tk.bound_classes, (
        f"{label} reports class {reported!r}, and its bindings went somewhere else: "
        f"{sorted(app.tk.bound_classes)}"
    )
    assert app.tk.bindings.sequences(reported), (
        f"{label} reports class {reported!r}, and nothing is bound to it"
    )


def test_a_subclass_that_wants_the_parents_behaviour_reports_the_parents_class(app):
    """ScrolledText's cure, stated so it cannot be undone by accident."""
    widget = scrolledtext.ScrolledText(app, name="st")
    assert widget.winfo_class() == "Text"


def test_a_subclass_that_adds_behaviour_registers_under_its_own_name(app):
    """Spinbox's cure, likewise. It reports its own name *and* that name has
    bindings, which is the combination that works.
    """
    widget = tkcurses.Spinbox(app, name="sb")
    assert widget.winfo_class() == "Spinbox"
    assert app.tk.bindings.sequences("Spinbox")


# ----------------------------------------------------------- virtual events


def test_a_virtual_event_reaches_only_its_own_bindings(window):
    _top, label = window
    ran = []
    label.bind("<<Custom>>", lambda event: ran.append("virtual"))
    label.bind("<Key-h>", lambda event: ran.append("real"))

    label.event_generate("<<Custom>>")

    assert ran == ["virtual"]


def test_a_virtual_event_runs_through_the_tags_like_any_other(window):
    top, label = window
    ran = []
    label.bind("<<Custom>>", lambda event: ran.append("widget"))
    top.bind("<<Custom>>", lambda event: ran.append("toplevel"))

    label.event_generate("<<Custom>>")

    assert ran == ["widget", "toplevel"]


# -------------------------------------------------------------- reordering


def test_bindtags_can_be_reordered_to_put_the_class_first(window):
    """The supported way to make a class binding run before an instance one,
    and the reason bindtags is writable at all.
    """
    _top, label = window
    ran = []
    label.bind("<Key-i>", lambda event: ran.append("widget"))
    label.bind_class("Label", "<Key-i>", lambda event: ran.append("class"))
    label.bindtags(("Label", str(label)))

    label.event_generate("<Key-i>")

    assert ran == ["class", "widget"]
