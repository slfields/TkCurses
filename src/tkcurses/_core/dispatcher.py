"""Event dispatcher and main loop for TkCurses.

Implements the CursesDispatcher that serializes all curses calls to the main thread.
Curses is NOT thread-safe, so all curses operations must go through this dispatcher.

This module is core to the TkCurses event system and ensures thread safety when
multiple threads need to interact with the terminal.
"""

from __future__ import annotations

import queue
import threading
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class CursesDispatcher:
    """Serializes all curses calls to the main thread.

    Curses is not thread-safe, so all curses operations must be serialized
    to the main thread. This dispatcher provides a thread-safe way to execute
    curses calls from any thread.

    The dispatcher uses a singleton pattern to ensure all threads use the same
    instance and queue. Calls from the main thread execute directly with a lock.
    Calls from other threads are queued and processed by the main loop.

    Example:
        >>> dispatcher = CursesDispatcher.get()
        >>> # Direct curses call (serialized)
        >>> dispatcher.call(curses.addstr, row, col, text, attr)
        >>>
        >>> # Compound operations (held under single lock)
        >>> def update_widget():
        ...     stdscr.addstr(0, 0, "Header")
        ...     stdscr.addstr(1, 0, "Content")
        ...     stdscr.refresh()
        >>> dispatcher.call(update_widget)

    Attributes:
        _instance: Singleton instance of the dispatcher.
        _lock: Threading lock for serializing curses calls.
        _queue: Thread-safe queue for calls from non-main threads.
        _main_thread_id: ID of the main thread where curses calls execute.
    """

    _instance: CursesDispatcher | None = None

    _lock: threading.Lock
    _queue: queue.Queue[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any], threading.Event, list[Any]]]
    _main_thread_id: int

    def __init__(self) -> None:
        """Initialize the dispatcher.

        Creates the serialization lock, call queue, and captures the current
        thread ID as the main thread. Should only be called once via get().
        """
        self._lock = threading.Lock()
        self._queue = queue.Queue()
        self._main_thread_id = threading.get_ident()

    @classmethod
    def get(cls) -> CursesDispatcher:
        """Get the singleton dispatcher instance.

        Creates the instance on first call. Subsequent calls return the
        same instance.

        Returns:
            The singleton CursesDispatcher instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a function with curses serialization.

        If called from the main thread, executes directly with the lock held.
        If called from another thread, queues the call for the main thread
        and blocks until it completes.

        Args:
            func: The function to execute.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            The return value of the function.

        Raises:
            Exception: Re-raises any exception that occurred during execution.
        """
        if threading.get_ident() == self._main_thread_id:
            # Already on main thread - execute directly with lock
            with self._lock:
                return func(*args, **kwargs)
        else:
            # Queue for main thread execution
            event = threading.Event()
            result: list[Any] = []
            self._queue.put((func, args, kwargs, event, result))
            event.wait()  # Block until main thread processes

            if result and isinstance(result[0], BaseException):
                raise result[0]
            return result[0]

    def process_queue(self) -> None:
        """Process all pending queued calls.

        This method should be called from the main loop to process calls
        that were queued from other threads. Each queued call is executed
        with the lock held, and the waiting thread is notified when complete.

        Exceptions raised during execution are captured and re-raised in the
        calling thread.
        """
        while not self._queue.empty():
            try:
                func, args, kwargs, event, result = self._queue.get_nowait()
                with self._lock:
                    try:
                        result.append(func(*args, **kwargs))
                    except BaseException as e:
                        result.append(e)
                event.set()
            except queue.Empty:
                break
