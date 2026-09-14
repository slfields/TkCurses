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

"""Serialize curses calls onto the thread that owns the screen.

Curses is not thread-safe. Every call into it goes through
:class:`CursesDispatcher`, which runs the call immediately when the caller is
the owning thread and otherwise hands it to that thread through a queue,
blocking the caller until it has run.

ARCHITECTURE.md "Thread Safety" sketches this design. The implementation here
differs in six places where the sketch would misbehave; each is noted at the
code responsible.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["CursesDispatcher", "DispatcherClosed"]

T = TypeVar("T")

#: Returned by a call that raised, to distinguish it from a returned value.
_NOTHING = object()


class DispatcherClosed(RuntimeError):
    """A call was made against a dispatcher that has shut down.

    Raised instead of blocking forever: once the main loop has stopped, nothing
    will drain the queue, so a waiting thread would hang until the process
    died.
    """


@dataclass
class _Call(Generic[T]):
    """One queued call and the slot for whatever it produces."""

    func: Callable[..., T]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    done: threading.Event = field(default_factory=threading.Event)
    value: Any = _NOTHING
    error: BaseException | None = None


class CursesDispatcher:
    """Runs curses calls on one thread, on behalf of any thread.

    Args:
        owner_thread_id: Thread permitted to execute calls directly. Defaults
            to the interpreter's main thread, which is where curses is
            initialised.
    """

    _instance: CursesDispatcher | None = None
    # Guards singleton creation. Without it two threads racing through get()
    # can each build a dispatcher, and half the application serializes against
    # the wrong lock.
    _instance_lock = threading.Lock()

    def __init__(self, owner_thread_id: int | None = None) -> None:
        # Bind to the interpreter's main thread rather than whichever thread
        # happened to construct this. Under lazy construction that could be a
        # worker, which would then be treated as the owner forever.
        if owner_thread_id is None:
            main = threading.main_thread().ident
            owner_thread_id = main if main is not None else threading.get_ident()
        self._owner_thread_id = owner_thread_id
        # Reentrant, so a compound operation may itself dispatch. A plain Lock
        # deadlocks the owner against itself the moment calls nest.
        self._lock = threading.RLock()
        self._queue: queue.Queue[_Call[Any]] = queue.Queue()
        self._closed = False

    # ------------------------------------------------------------ singleton

    @classmethod
    def get(cls) -> CursesDispatcher:
        """Return the process-wide dispatcher, creating it if needed."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Discard the process-wide dispatcher.

        For tests and for a second Tk() in one process; closing first releases
        anything still waiting.
        """
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance.close()
            cls._instance = None

    # ---------------------------------------------------------------- state

    @property
    def owner_thread_id(self) -> int:
        """Identifier of the thread allowed to touch curses directly."""
        return self._owner_thread_id

    @property
    def is_owner(self) -> bool:
        """True if the calling thread owns the screen."""
        return threading.get_ident() == self._owner_thread_id

    @property
    def closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._closed

    @property
    def pending(self) -> int:
        """Number of calls waiting to run."""
        return self._queue.qsize()

    # ----------------------------------------------------------- dispatch

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run ``func`` under the curses lock and return its result.

        On the owning thread the call runs inline. On any other thread it is
        queued and the caller blocks until the owner has run it, so exceptions
        surface at the call site rather than in the event loop.
        """
        if self.is_owner:
            with self._lock:
                return func(*args, **kwargs)

        if self._closed:
            raise DispatcherClosed("dispatcher is closed; no thread will run this call")

        pending: _Call[T] = _Call(func, args, kwargs)
        self._queue.put(pending)
        # Re-check after queueing: close() may have drained the queue between
        # the check above and the put, which would strand this caller.
        self._abort_if_closed(pending)
        pending.done.wait()
        return self._result_of(pending)

    def post(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Queue ``func`` without waiting for it.

        For fire-and-forget work such as a redraw request, where blocking the
        calling thread would serve no purpose.
        """
        if self._closed:
            raise DispatcherClosed("dispatcher is closed; no thread will run this call")
        self._queue.put(_Call(func, args, kwargs))

    def process_queue(self, limit: int | None = None) -> int:
        """Run queued calls on the owning thread. Returns how many ran.

        The main loop calls this each iteration. ``limit`` caps the batch so a
        thread queueing work in a tight loop cannot starve input handling.
        """
        if not self.is_owner:
            raise RuntimeError("process_queue() must run on the owning thread")
        ran = 0
        while limit is None or ran < limit:
            try:
                pending = self._queue.get_nowait()
            except queue.Empty:
                break
            self._run(pending)
            ran += 1
        return ran

    def close(self) -> None:
        """Shut down, releasing every thread still waiting on a call."""
        self._closed = True
        while True:
            try:
                pending = self._queue.get_nowait()
            except queue.Empty:
                break
            self._fail(pending)

    # ----------------------------------------------------------- internals

    def _run(self, pending: _Call[Any]) -> None:
        """Execute one queued call, capturing its outcome for the caller."""
        with self._lock:
            try:
                pending.value = pending.func(*pending.args, **pending.kwargs)
            except BaseException as exc:  # relayed to the calling thread
                pending.error = exc
        pending.done.set()

    def _abort_if_closed(self, pending: _Call[Any]) -> None:
        """Release a call stranded by a close that raced with its queueing.

        Kept in its own method because the check reads a flag another thread
        may have changed since the caller last looked at it.
        """
        if self._closed:
            self._fail(pending)

    def _fail(self, pending: _Call[Any]) -> None:
        """Release a waiter that will never run.

        A call that already completed is left alone: the owner may have run it
        in the window before close(), and its result belongs to the caller.
        """
        if pending.done.is_set():
            return
        pending.error = DispatcherClosed("dispatcher closed before the call ran")
        pending.done.set()

    def _result_of(self, pending: _Call[T]) -> T:
        """Unwrap a completed call, re-raising on the caller's thread.

        The outcome is carried in two fields rather than sniffed with
        isinstance, so a function that legitimately *returns* an exception
        object gets its value back instead of having it raised.
        """
        if pending.error is not None:
            raise pending.error
        value: T = pending.value
        return value
