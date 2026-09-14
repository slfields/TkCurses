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

"""The drag-and-drop protocol, which is all this module is.

Nothing here draws anything or reads the mouse: the handler's whole job is
to decide which object is the target as the pointer moves, and to call the
right method on the right end at the right moment. All of that can be
exercised by handing it events.
"""

from __future__ import annotations

import pytest

import tkcurses
from tkcurses._core.geometry import Rect
from tkcurses.dnd import DndHandler, dnd_start


class Source:
    """Something being dragged. It need not be a widget, and is not."""

    name = "parcel"

    def __init__(self):
        self.ended: list[object] = []

    def dnd_end(self, target, event):
        self.ended.append(target)


class Target(tkcurses.Frame):
    """A widget that accepts drops, and records what it was told."""

    def __init__(self, master, accepts=True, **kw):
        super().__init__(master, **kw)
        self.accepts = accepts
        self.calls: list[str] = []

    def dnd_accept(self, source, event):
        return self if self.accepts else None

    def dnd_enter(self, source, event):
        self.calls.append("enter")

    def dnd_motion(self, source, event):
        self.calls.append("motion")

    def dnd_leave(self, source, event):
        self.calls.append("leave")

    def dnd_commit(self, source, event):
        self.calls.append("commit")


@pytest.fixture
def root():
    """A root with a size, so that widgets in it can be found by position.

    on_motion asks winfo_containing what is under the pointer rather than
    trusting the event's own widget - which is tkinter's design, and the
    reason a drag can pass over something that was never bound to anything.
    """
    root = tkcurses.Misc()
    root._rect = Rect(0, 0, 40, 12)
    root._mapped = True
    return root


def placed(master, x, y, accepts=True, **kw):
    """A target at a known position, laid out and ready to be dragged over."""
    target = Target(master, accepts=accepts, width=10, height=4, **kw)
    target.place(x=x, y=y)
    target._root().update_layout()
    return target


def press(widget, num=1, x=0, y=0):
    """A button press, as a binding would receive it."""
    event = tkcurses.Event()
    event.widget = widget
    event.num = num
    event.x_root = x
    event.y_root = y
    return event


def motion(widget, x, y):
    event = tkcurses.Event()
    event.widget = widget
    event.num = 1
    event.x_root = x
    event.y_root = y
    return event


# ---------------------------------------------------------------- starting


def test_a_drag_can_be_started(root):
    handler = dnd_start(Source(), press(root))
    assert isinstance(handler, DndHandler)
    assert root.tk.dnd is handler


def test_only_one_drag_runs_at_a_time(root):
    """Two bindings on one press both calling dnd_start is ordinary, and the
    second must not disturb the first."""
    first = dnd_start(Source(), press(root))
    assert dnd_start(Source(), press(root)) is None
    assert root.tk.dnd is first


def test_another_can_start_once_the_first_has_finished(root):
    first = dnd_start(Source(), press(root))
    first.finish(None)
    assert root.tk.dnd is None
    assert dnd_start(Source(), press(root)) is not None


@pytest.mark.parametrize("button", [4, 5, 6])
def test_the_wheel_cannot_start_a_drag(root, button):
    """Nothing can be dragged with a button that cannot be held down, and
    curses reports wheel movement as buttons 4 and 5."""
    assert dnd_start(Source(), press(root, num=button)) is None
    assert root.tk.dnd is None


def test_the_handler_binds_for_the_button_that_started_it(root):
    """The release pattern has to name that button, or the drag never ends."""
    handler = dnd_start(Source(), press(root, num=3))
    assert handler.release_pattern == "<B3-ButtonRelease-3>"


# ----------------------------------------------------------------- targets


def test_moving_onto_a_target_enters_it(root):
    target = placed(root, 0, 0)
    handler = dnd_start(Source(), press(root))
    handler.on_motion(motion(target, 1, 1))
    assert target.calls == ["enter"]
    assert handler.target is target


def test_moving_within_one_target_is_motion(root):
    target = placed(root, 0, 0)
    handler = dnd_start(Source(), press(root))
    handler.on_motion(motion(target, 1, 1))
    handler.on_motion(motion(target, 2, 1))
    assert target.calls == ["enter", "motion"]


def test_moving_between_targets_leaves_one_and_enters_the_other(root):
    first = placed(root, 0, 0)
    second = placed(root, 20, 0)
    handler = dnd_start(Source(), press(root))
    handler.on_motion(motion(first, 1, 1))
    handler.on_motion(motion(second, 21, 1))
    assert first.calls == ["enter", "leave"]
    assert second.calls == ["enter"]


def test_a_widget_that_refuses_hands_the_question_to_its_parent(root):
    """The search walks up until something answers, so a small widget inside
    a drop zone does not have to know about dropping at all."""
    zone = placed(root, 0, 0)
    inner = Target(zone, accepts=False, width=4, height=2)
    inner.place(x=1, y=1)
    root.update_layout()
    handler = dnd_start(Source(), press(root))
    handler.on_motion(motion(inner, 2, 2))
    assert handler.target is zone
    assert zone.calls == ["enter"]
    assert inner.calls == []


def test_nothing_accepting_means_no_target(root):
    plain = tkcurses.Frame(root, width=10, height=4)
    plain.place(x=0, y=0)
    root.update_layout()
    handler = dnd_start(Source(), press(root))
    handler.on_motion(motion(plain, 1, 1))
    assert handler.target is None


# ----------------------------------------------------------------- ending


def test_releasing_over_a_target_commits(root):
    source = Source()
    target = placed(root, 0, 0)
    handler = dnd_start(source, press(root))
    handler.on_motion(motion(target, 1, 1))
    handler.on_release(motion(target, 1, 1))
    assert target.calls == ["enter", "commit"]
    assert source.ended == [target]


def test_cancelling_leaves_the_target_rather_than_committing(root):
    source = Source()
    target = placed(root, 0, 0)
    handler = dnd_start(source, press(root))
    handler.on_motion(motion(target, 1, 1))
    handler.cancel()
    assert target.calls == ["enter", "leave"]
    assert source.ended == [target]


def test_the_source_is_always_told_it_is_over(root):
    """Even with no target at all: a source never told the drag ended has no
    way of putting itself back."""
    source = Source()
    handler = dnd_start(source, press(root))
    handler.finish(None)
    assert source.ended == [None]


def test_the_source_is_told_even_when_the_target_raises(root):
    """Which is why dnd_end is in a finally."""

    class Exploding(Target):
        def dnd_commit(self, source, event):
            raise RuntimeError("no thanks")

    source = Source()
    target = Exploding(root, width=10, height=4)
    target.place(x=0, y=0)
    root.update_layout()
    handler = dnd_start(source, press(root))
    handler.on_motion(motion(target, 1, 1))
    with pytest.raises(RuntimeError):
        handler.on_release(motion(target, 1, 1))
    assert source.ended == [target]


def test_finishing_releases_the_drag_for_the_next_one(root):
    handler = dnd_start(Source(), press(root))
    handler.finish(None)
    assert root.tk.dnd is None
