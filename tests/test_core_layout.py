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

"""Tests for tkcurses._core.layout.

The termination tests are the point of this file. The previous attempt at
this library looped in geometry propagation and exhausted memory, so "does it
stop" is checked here as deliberately as "is it correct".
"""

from __future__ import annotations

import pytest

from tkcurses import Misc, Widget
from tkcurses._core.geometry import Rect, Size
from tkcurses._core.layout import DEFAULT_PASS_LIMIT, LayoutEngine, LayoutLoop


class RecordingLayout:
    """A manager that reports a fixed size and remembers what it was asked."""

    def __init__(self, size: Size | None = None) -> None:
        self.size = size if size is not None else Size(10, 4)
        self.requested_calls: list[object] = []
        self.applied: list[Rect] = []

    def requested(self, container):
        self.requested_calls.append(container)
        return self.size

    def apply(self, container, area):
        self.applied.append(area)

    def slaves(self, container):
        return container.winfo_children()


class SumOfChildren:
    """A manager whose container wants exactly as much as its children use."""

    def requested(self, container):
        children = container.winfo_children()
        return Size(
            max((child.winfo_reqwidth() for child in children), default=0),
            sum(child.winfo_reqheight() for child in children),
        )

    def apply(self, container, area):
        top = area.y
        for child in container.winfo_children():
            child._rect = Rect(
                area.x - container.winfo_rootx(),
                top - container.winfo_rooty(),
                child.winfo_reqwidth(),
                child.winfo_reqheight(),
            )
            top += child.winfo_reqheight()

    def slaves(self, container):
        return container.winfo_children()


@pytest.fixture
def engine():
    return LayoutEngine()


@pytest.fixture
def root():
    root = Misc()
    root._rect = Rect(0, 0, 80, 24)
    return root


# ------------------------------------------------------------------ queueing


def test_nothing_is_queued_to_begin_with(engine):
    assert engine.pending == 0
    assert engine.run() == 0


def test_invalidating_queues_a_container(engine, root):
    engine.invalidate(root)
    assert engine.pending == 1


def test_invalidating_twice_queues_one_run(engine, root):
    engine.invalidate(root)
    engine.invalidate(root)
    assert engine.pending == 1


def test_invalidating_nothing_is_harmless(engine):
    engine.invalidate(None)
    assert engine.pending == 0


def test_clear_discards_queued_work(engine, root):
    engine.invalidate(root)
    engine.clear()
    assert engine.pending == 0


def test_a_container_with_no_manager_is_skipped(engine, root):
    engine.invalidate(root)
    assert engine.run() == 1
    assert engine.pending == 0


# ------------------------------------------------------------------- running


def test_a_run_asks_the_manager_for_a_size_and_applies_it(engine, root):
    manager = RecordingLayout()
    root._layout_manager = manager
    engine.invalidate(root)
    engine.run()
    assert manager.requested_calls == [root]
    assert len(manager.applied) == 1


def test_the_area_offered_excludes_the_border(engine, root):
    root._options["borderwidth"] = 1
    root._layout_manager = RecordingLayout()
    engine.invalidate(root)
    engine.run()
    area = root._layout_manager.applied[0]
    assert (area.width, area.height) == (78, 22)
    assert (area.x, area.y) == (1, 1)


def test_the_queue_is_empty_after_a_run(engine, root):
    root._layout_manager = RecordingLayout()
    engine.invalidate(root)
    engine.run()
    assert engine.pending == 0


def test_a_run_reports_how_many_containers_it_did(engine, root):
    child = Widget(root, name="child")
    for widget in (root, child):
        widget._layout_manager = RecordingLayout()
    engine.invalidate(root)
    engine.invalidate(child)
    assert engine.run() == 2


def test_a_run_is_not_reentrant(engine, root):
    """A manager that lays out during layout would see half-applied geometry."""
    inner = []

    class Reentrant(RecordingLayout):
        def apply(self, container, area):
            inner.append(engine.run())

    root._layout_manager = Reentrant()
    engine.invalidate(root)
    engine.run()
    assert inner == [0]


def test_work_queued_during_a_run_is_done_by_that_run(engine, root):
    child = Widget(root, name="child")
    child._layout_manager = RecordingLayout()

    class QueuesChild(RecordingLayout):
        def apply(self, container, area):
            super().apply(container, area)
            if len(self.applied) == 1:
                engine.invalidate(child)

    root._layout_manager = QueuesChild()
    engine.invalidate(root)
    done = engine.run()
    # The child was laid out by the same run that queued it, and the run left
    # nothing behind. The count is not pinned: the child's own size change
    # legitimately queues its parent again.
    assert child._layout_manager.applied
    assert done >= 2
    assert engine.pending == 0


# --------------------------------------------------------------- propagation


def test_a_containers_requested_size_comes_from_its_manager(engine, root):
    root._layout_manager = RecordingLayout(Size(20, 6))
    engine.invalidate(root)
    engine.run()
    assert (root.winfo_reqwidth(), root.winfo_reqheight()) == (20, 6)


def test_a_change_reaches_the_parent(engine, root):
    frame = Widget(root, name="frame")
    frame._layout_manager = RecordingLayout(Size(12, 3))
    root._layout_manager = SumOfChildren()
    engine.invalidate(frame)
    engine.run()
    assert (root.winfo_reqwidth(), root.winfo_reqheight()) == (12, 3)


def test_a_change_stops_where_it_changes_nothing(engine, root):
    """The walk up ends at the first ancestor whose own size is unaffected."""
    frame = Widget(root, name="frame")
    frame._layout_manager = RecordingLayout(Size(12, 3))
    root._layout_manager = SumOfChildren()
    engine.invalidate(frame)
    engine.run()

    counted = SumOfChildren()
    calls = []
    counted_requested = counted.requested
    counted.requested = lambda container: (
        calls.append(container) or counted_requested(container)
    )
    root._layout_manager = counted
    # Re-running with nothing changed must not walk the tree again.
    engine.invalidate(frame)
    engine.run()
    assert len(calls) <= 1


def test_propagation_can_be_switched_off(engine, root):
    frame = Widget(root, name="frame")
    frame._layout_manager = RecordingLayout(Size(12, 3))
    frame._requested = Size(4, 1)
    frame.pack_propagate(False)
    engine.invalidate(frame)
    engine.run()
    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (4, 1)


def test_a_container_with_propagation_off_does_not_tell_its_parent(engine, root):
    frame = Widget(root, name="frame")
    frame._layout_manager = RecordingLayout(Size(12, 3))
    frame.pack_propagate(False)
    root._layout_manager = SumOfChildren()
    engine.invalidate(frame)
    engine.run()
    assert root.winfo_reqwidth() == 0


def test_propagate_reports_its_current_setting(root):
    assert root.pack_propagate() is True
    root.pack_propagate(False)
    assert root.pack_propagate() is False
    assert root.grid_propagate() is False


def test_the_propagate_flags_are_one_setting(root):
    root.grid_propagate(False)
    assert root.pack_propagate() is False


# -------------------------------------------------------------- termination


def test_a_cycle_raises_rather_than_running_forever(engine, root):
    """The failure that killed the previous implementation."""
    first = Widget(root, name="a")
    second = Widget(first, name="b")

    class AlwaysDifferent:
        """A manager that never settles, as a propagation cycle would not."""

        def __init__(self):
            self.calls = 0

        def requested(self, container):
            self.calls += 1
            return Size(self.calls % 7 + 1, 1)

        def apply(self, container, area):
            engine.invalidate(container)

        def slaves(self, container):
            return []

    for widget in (root, first, second):
        widget._layout_manager = AlwaysDifferent()
    engine.invalidate(second)
    with pytest.raises(LayoutLoop, match="did not settle"):
        engine.run()


def test_the_engine_is_usable_again_after_a_loop(engine, root):
    class AlwaysDifferent:
        def __init__(self):
            self.calls = 0

        def requested(self, container):
            self.calls += 1
            return Size(self.calls % 5 + 1, 1)

        def apply(self, container, area):
            engine.invalidate(container)

        def slaves(self, container):
            return []

    root._layout_manager = AlwaysDifferent()
    engine.invalidate(root)
    with pytest.raises(LayoutLoop):
        engine.run()
    assert not engine.running
    engine.clear()
    root._layout_manager = RecordingLayout()
    engine.invalidate(root)
    assert engine.run() == 1


def test_the_pass_limit_is_respected(root):
    engine = LayoutEngine(pass_limit=5)

    class AlwaysDifferent:
        def __init__(self):
            self.calls = 0

        def requested(self, container):
            self.calls += 1
            return Size(self.calls % 3 + 1, 1)

        def apply(self, container, area):
            engine.invalidate(container)

        def slaves(self, container):
            return []

    root._layout_manager = AlwaysDifferent()
    engine.invalidate(root)
    with pytest.raises(LayoutLoop, match="after 5 passes"):
        engine.run()


def test_a_deep_tree_settles_well_inside_the_limit(engine, root):
    """A hundred nested containers must not look like a loop."""
    parent = root
    for depth in range(100):
        child = Widget(parent, name=f"w{depth}")
        child._layout_manager = RecordingLayout(Size(5, 1))
        parent._layout_manager = SumOfChildren()
        parent = child
    engine.invalidate(parent)
    assert engine.run() < DEFAULT_PASS_LIMIT


def test_walking_the_ancestry_of_a_cycle_raises(engine, root):
    """A tree made into a graph is reported, not followed round."""
    first = Widget(root, name="a")
    second = Widget(first, name="b")
    first.master = second  # the kind of damage reparenting could do
    with pytest.raises(LayoutLoop, match="cycle"):
        list(engine.ancestry(second))


def test_walking_a_normal_ancestry_reaches_the_root(engine, root):
    child = Widget(Widget(root, name="a"), name="b")
    assert list(engine.ancestry(child))[-1] is root
