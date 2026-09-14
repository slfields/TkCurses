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

"""Tests for tkcurses._core.timers."""

from __future__ import annotations

import pytest

from tkcurses._core.timers import AfterQueue


class FakeClock:
    """A clock the test advances by hand, so no test has to sleep."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def queue(clock):
    return AfterQueue(clock=clock)


# ------------------------------------------------------------------- timers


def test_a_callback_does_not_run_before_its_time(queue, clock):
    calls = []
    queue.after(100, calls.append, "late")
    assert queue.run_due() == 0
    clock.advance(0.05)
    assert queue.run_due() == 0
    assert calls == []


def test_a_callback_runs_once_its_time_arrives(queue, clock):
    calls = []
    queue.after(100, calls.append, "on time")
    clock.advance(0.1)
    assert queue.run_due() == 1
    assert calls == ["on time"]


def test_a_callback_runs_only_once(queue, clock):
    calls = []
    queue.after(0, calls.append, "once")
    queue.run_due()
    queue.run_due()
    assert calls == ["once"]


def test_callbacks_run_in_due_order_not_scheduling_order(queue, clock):
    calls = []
    queue.after(200, calls.append, "second")
    queue.after(100, calls.append, "first")
    clock.advance(0.2)
    queue.run_due()
    assert calls == ["first", "second"]


def test_callbacks_due_together_run_in_scheduling_order(queue, clock):
    calls = []
    queue.after(50, calls.append, "first")
    queue.after(50, calls.append, "second")
    clock.advance(0.05)
    queue.run_due()
    assert calls == ["first", "second"]


def test_a_negative_delay_is_treated_as_immediate(queue):
    calls = []
    queue.after(-100, calls.append, "now")
    assert queue.run_due() == 1
    assert calls == ["now"]


def test_after_with_no_callback_still_schedules_a_handle(queue, clock):
    handle = queue.after(100)
    assert handle in queue
    clock.advance(0.1)
    assert queue.run_due() == 1


def test_arguments_are_passed_through(queue):
    seen = []
    queue.after(0, lambda *args: seen.append(args), 1, "two", None)
    queue.run_due()
    assert seen == [(1, "two", None)]


def test_a_callback_that_reschedules_itself_does_not_loop(queue):
    calls = []

    def tick():
        calls.append(len(calls))
        queue.after(0, tick)

    queue.after(0, tick)
    assert queue.run_due() == 1
    assert queue.run_due() == 1
    assert calls == [0, 1]


# -------------------------------------------------------------------- idle


def test_idle_callbacks_run_on_the_idle_pass(queue):
    calls = []
    queue.after_idle(calls.append, "idle")
    assert queue.run_due() == 0
    assert queue.run_idle() == 1
    assert calls == ["idle"]


def test_idle_callbacks_run_in_the_order_they_were_queued(queue):
    calls = []
    queue.after_idle(calls.append, "first")
    queue.after_idle(calls.append, "second")
    queue.run_idle()
    assert calls == ["first", "second"]


def test_idle_work_queued_while_idle_waits_for_the_next_pass(queue):
    calls = []

    def outer():
        calls.append("outer")
        queue.after_idle(calls.append, "inner")

    queue.after_idle(outer)
    assert queue.run_idle() == 1
    assert calls == ["outer"]
    assert queue.run_idle() == 1
    assert calls == ["outer", "inner"]


# --------------------------------------------------------------- cancelling


def test_a_cancelled_callback_never_runs(queue, clock):
    calls = []
    handle = queue.after(50, calls.append, "cancelled")
    queue.cancel(handle)
    clock.advance(1)
    assert queue.run_due() == 0
    assert calls == []


def test_a_cancelled_idle_callback_never_runs(queue):
    calls = []
    queue.cancel(queue.after_idle(calls.append, "cancelled"))
    assert queue.run_idle() == 0
    assert calls == []


def test_cancelling_leaves_the_other_callbacks_alone(queue, clock):
    calls = []
    queue.cancel(queue.after(50, calls.append, "gone"))
    queue.after(50, calls.append, "kept")
    clock.advance(0.05)
    queue.run_due()
    assert calls == ["kept"]


def test_cancelling_an_unknown_handle_is_not_an_error(queue):
    queue.cancel("after#404")


def test_cancelling_a_handle_that_already_ran_is_not_an_error(queue):
    handle = queue.after(0, lambda: None)
    queue.run_due()
    queue.cancel(handle)


def test_clear_discards_everything(queue, clock):
    calls = []
    queue.after(0, calls.append, "timed")
    queue.after_idle(calls.append, "idle")
    queue.clear()
    clock.advance(1)
    assert queue.run_due() == 0
    assert queue.run_idle() == 0
    assert len(queue) == 0
    assert calls == []


# ------------------------------------------------------------------ queries


def test_a_scheduled_handle_is_reported_until_it_runs(queue):
    handle = queue.after(0, lambda: None)
    assert handle in queue
    assert len(queue) == 1
    queue.run_due()
    assert handle not in queue
    assert len(queue) == 0


def test_info_reports_the_callback_and_its_arguments(queue):
    def handler(value):
        return value

    handle = queue.after(10, handler, 42)
    assert queue.info(handle) == (handler, (42,), "timer")


def test_info_distinguishes_idle_callbacks(queue):
    handle = queue.after_idle(lambda: None)
    assert queue.info(handle)[2] == "idle"


def test_info_with_no_handle_lists_the_scheduled_ones_newest_first(queue):
    first = queue.after(10, lambda: None)
    second = queue.after(20, lambda: None)
    assert queue.info() == (second, first)


def test_info_on_an_unknown_handle_raises(queue):
    with pytest.raises(KeyError):
        queue.info("after#404")


# ------------------------------------------------------------- loop timeout


def test_an_empty_queue_asks_the_loop_to_wait_indefinitely(queue):
    assert queue.next_delay() is None


def test_the_delay_counts_down_as_the_clock_advances(queue, clock):
    queue.after(100, lambda: None)
    assert queue.next_delay() == pytest.approx(0.1)
    clock.advance(0.06)
    assert queue.next_delay() == pytest.approx(0.04)


def test_an_overdue_callback_asks_for_no_wait(queue, clock):
    queue.after(10, lambda: None)
    clock.advance(1)
    assert queue.next_delay() == 0.0


def test_pending_idle_work_asks_for_no_wait(queue):
    queue.after(10_000, lambda: None)
    queue.after_idle(lambda: None)
    assert queue.next_delay() == 0.0


def test_the_delay_reflects_the_soonest_callback(queue):
    queue.after(500, lambda: None)
    queue.after(50, lambda: None)
    assert queue.next_delay() == pytest.approx(0.05)


def test_a_cancelled_head_does_not_hold_the_delay_down(queue):
    queue.cancel(queue.after(10, lambda: None))
    queue.after(500, lambda: None)
    assert queue.next_delay() == pytest.approx(0.5)


def test_the_delay_is_none_again_once_everything_is_cancelled(queue):
    queue.cancel(queue.after(10, lambda: None))
    assert queue.next_delay() is None
