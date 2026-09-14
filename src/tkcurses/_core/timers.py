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

"""Scheduled callbacks: the queue behind ``after()`` and ``after_idle()``.

Tk's ``after`` is not a thread or a timer object; it is an entry in a queue
the event loop drains. The same design is kept here, for the same reason: a
callback that runs on the loop's thread needs no locking against the screen,
and cancelling it is removing an entry rather than stopping something already
running.

Two queues are kept, not one. Timed callbacks are due at a wall-clock moment,
while idle callbacks are due whenever the loop has nothing else to do, and the
loop treats them differently: idle work runs before a redraw, timed work runs
when its moment arrives. :meth:`AfterQueue.next_delay` exists so the loop can
pass a timeout to ``select`` instead of polling, which is what keeps an idle
application off the CPU.
"""

from __future__ import annotations

import heapq
import itertools
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["AfterQueue", "Timer", "TimerKind"]

#: Which queue a scheduled callback sits in.
TimerKind = Literal["timer", "idle"]


@dataclass(order=True)
class Timer:
    """One scheduled callback.

    Ordered by due time so the pending queue can be a heap. ``sequence``
    breaks ties, keeping two callbacks scheduled for the same millisecond in
    the order they were registered; without it the heap would compare the
    callables and raise.

    Attributes:
        due: Monotonic time the callback should run at; 0 for idle work.
        sequence: Registration order, used only for tie-breaking.
        id: The handle ``after()`` returned.
        func: The callback, or None for a bare ``after(ms)`` delay.
        args: Positional arguments to call it with.
        kind: Which queue it belongs to.
    """

    due: float
    sequence: int
    id: str = field(compare=False)
    func: Callable[..., Any] | None = field(compare=False, default=None)
    args: tuple[Any, ...] = field(compare=False, default=())
    kind: TimerKind = field(compare=False, default="timer")
    #: Cleared by cancel(). A heap entry cannot be removed cheaply, so a
    #: cancelled timer is left in place and skipped when it surfaces.
    live: bool = field(compare=False, default=True)

    def __call__(self) -> Any:
        """Run the callback, if there is one."""
        if self.func is None:
            return None
        return self.func(*self.args)


class AfterQueue:
    """Callbacks waiting to run, by time or by idleness.

    The queue holds no thread of its own: something must call :meth:`run_due`
    and :meth:`run_idle`, which the main loop does once per iteration.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        """
        Args:
            clock: Source of the current time, in seconds. Monotonic by
                default, so that a system clock adjustment cannot make a
                pending callback wait an hour or fire an hour early.
        """
        self._clock = clock
        self._pending: list[Timer] = []
        self._idle: list[Timer] = []
        self._by_id: dict[str, Timer] = {}
        self._ids = itertools.count(1)

    # ------------------------------------------------------------ scheduling

    def after(self, ms: int, func: Callable[..., Any] | None = None, *args: Any) -> str:
        """Schedule ``func`` to run in ``ms`` milliseconds; return its handle.

        A negative delay is treated as zero rather than rejected: Tk runs such
        a callback at the next opportunity, and arithmetic that lands slightly
        in the past is common in code that schedules against a deadline.
        """
        timer = self._make(max(ms, 0) / 1000.0 + self._clock(), func, args, "timer")
        heapq.heappush(self._pending, timer)
        return timer.id

    def after_idle(self, func: Callable[..., Any], *args: Any) -> str:
        """Schedule ``func`` to run when the loop next goes idle."""
        timer = self._make(0.0, func, args, "idle")
        self._idle.append(timer)
        return timer.id

    def cancel(self, timer_id: str) -> None:
        """Cancel a scheduled callback.

        Cancelling an unknown or already-run handle does nothing, so a widget
        tearing down does not have to track which of its timers have fired.
        """
        timer = self._by_id.pop(timer_id, None)
        if timer is not None:
            timer.live = False

    def clear(self) -> None:
        """Discard everything scheduled, as when a window is destroyed."""
        for timer in self._by_id.values():
            timer.live = False
        self._pending.clear()
        self._idle.clear()
        self._by_id.clear()

    # --------------------------------------------------------------- queries

    def info(self, timer_id: str | None = None) -> Any:
        """Mirror Tk's ``after_info``.

        With no handle, returns the handles of everything still scheduled,
        most recently scheduled first. With one, returns
        ``(func, args, kind)``.

        Raises:
            KeyError: If the handle is unknown, matching Tk, which reports an
                error for an id that has already fired.
        """
        if timer_id is None:
            return tuple(reversed(list(self._by_id)))
        timer = self._by_id[timer_id]
        return (timer.func, timer.args, timer.kind)

    def __contains__(self, timer_id: object) -> bool:
        """True while ``timer_id`` is still scheduled."""
        return timer_id in self._by_id

    def __len__(self) -> int:
        """How many callbacks are still scheduled."""
        return len(self._by_id)

    @property
    def idle_pending(self) -> int:
        """How many idle callbacks are waiting."""
        return sum(1 for timer in self._idle if timer.live)

    def next_delay(self) -> float | None:
        """Seconds until the next timed callback, for the loop's ``select``.

        Returns 0.0 when something is already due or idle work is waiting, and
        None when nothing is scheduled, meaning the loop may block until input
        arrives.
        """
        if self.idle_pending:
            return 0.0
        self._drop_cancelled()
        if not self._pending:
            return None
        return max(0.0, self._pending[0].due - self._clock())

    # --------------------------------------------------------------- running

    def run_due(self) -> int:
        """Run every timed callback whose moment has arrived; return the count.

        The due set is taken before any of it runs, so a callback that
        reschedules itself with ``after(0, ...)`` is picked up on the next
        pass instead of looping here forever.
        """
        return self._run(self.take_due())

    def run_idle(self) -> int:
        """Run every waiting idle callback; return how many ran.

        Idle callbacks queued *by* an idle callback wait for the next pass,
        for the same reason.
        """
        return self._run(self.take_idle())

    def take_due(self) -> list[Timer]:
        """Remove and return the timed callbacks that are due now."""
        now = self._clock()
        due: list[Timer] = []
        while self._pending and self._pending[0].due <= now:
            timer = heapq.heappop(self._pending)
            if timer.live:
                self._retire(timer)
                due.append(timer)
        return due

    def take_idle(self) -> list[Timer]:
        """Remove and return the waiting idle callbacks."""
        waiting, self._idle = self._idle, []
        ready = [timer for timer in waiting if timer.live]
        for timer in ready:
            self._retire(timer)
        return ready

    # ------------------------------------------------------------- internals

    def _make(
        self,
        due: float,
        func: Callable[..., Any] | None,
        args: tuple[Any, ...],
        kind: TimerKind,
    ) -> Timer:
        """Create a timer and index it by handle."""
        sequence = next(self._ids)
        timer = Timer(
            due=due,
            sequence=sequence,
            id=f"after#{sequence}",
            func=func,
            args=args,
            kind=kind,
        )
        self._by_id[timer.id] = timer
        return timer

    def _retire(self, timer: Timer) -> None:
        """Forget a timer that is about to run, so its handle stops resolving."""
        self._by_id.pop(timer.id, None)

    def _drop_cancelled(self) -> None:
        """Discard cancelled entries sitting at the head of the heap.

        Only the head matters: a cancelled timer further down costs nothing
        until it surfaces, whereas one at the head would report a delay for a
        callback that will never run.
        """
        while self._pending and not self._pending[0].live:
            heapq.heappop(self._pending)

    @staticmethod
    def _run(timers: list[Timer]) -> int:
        """Run a batch of callbacks and report how many there were."""
        for timer in timers:
            timer()
        return len(timers)
