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


class DispatcherQueueFullError(Exception):
    """Raised when the dispatcher queue is full and cannot accept new calls."""

    pass


class DispatcherTimeoutError(Exception):
    """Raised when a cross-thread call times out waiting for completion."""

    pass


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
        _instance_lock: Lock for thread-safe singleton creation.
        _lock: Threading lock for serializing curses calls.
        _queue: Thread-safe queue for calls from non-main threads.
        _main_thread_id: ID of the main thread where curses calls execute.
        _max_queue_size: Maximum number of pending calls allowed.
        _default_timeout: Default timeout for cross-thread calls.
    """

    _instance: CursesDispatcher | None = None
    _instance_lock: threading.Lock = threading.Lock()

    _lock: threading.Lock
    _queue: queue.Queue[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any], threading.Event, list[Any]]]
    _main_thread_id: int
    _max_queue_size: int
    _default_timeout: float

    # Default limits
    DEFAULT_MAX_QUEUE_SIZE = 1000
    DEFAULT_TIMEOUT = 30.0  # 30 seconds

    def __init__(
        self,
        max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE,
        default_timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the dispatcher.

        Creates the serialization lock, call queue, and captures the current
        thread ID as the main thread. Should only be called once via get().

        Args:
            max_queue_size: Maximum number of pending calls in the queue.
                When exceeded, DispatcherQueueFullError is raised.
            default_timeout: Default timeout in seconds for cross-thread calls.
                Can be overridden per-call via the call() method.
        """
        self._lock = threading.Lock()
        self._queue: queue.Queue[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any], threading.Event, list[Any]]] = queue.Queue(maxsize=max_queue_size)
        self._main_thread_id = threading.get_ident()
        self._max_queue_size = max_queue_size
        self._default_timeout = default_timeout

    @classmethod
    def get(cls) -> CursesDispatcher:
        """Get the singleton dispatcher instance.

        Thread-safe: Uses double-checked locking to ensure only one instance
        is created even when multiple threads call get() simultaneously.

        Creates the instance on first call. Subsequent calls return the
        same instance.

        Returns:
            The singleton CursesDispatcher instance.
        """
        # Double-checked locking pattern for thread-safe singleton
        if cls._instance is None:
            with cls._instance_lock:
                # Check again inside lock in case another thread created it
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def call(
        self,
        func: Callable[..., T],
        *args: Any,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> T:
        """Execute a function with curses serialization.

        If called from the main thread, executes directly with the lock held.
        If called from another thread, queues the call for the main thread
        and blocks until it completes or times out.

        Args:
            func: The function to execute.
            *args: Positional arguments to pass to the function.
            timeout: Timeout in seconds for cross-thread calls. If None,
                uses the default timeout. Set to 0 for no timeout.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            The return value of the function.

        Raises:
            DispatcherQueueFullError: If the queue is full and cannot accept
                the call.
            DispatcherTimeoutError: If a cross-thread call times out waiting
                for completion.
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

            # Try to add to queue with timeout
            try:
                self._queue.put_nowait((func, args, kwargs, event, result))
            except queue.Full:
                raise DispatcherQueueFullError(
                    f"Dispatcher queue is full (max size: {self._max_queue_size}). "
                    "The main thread may not be processing calls fast enough."
                )

            # Determine timeout to use
            wait_timeout = timeout if timeout is not None else self._default_timeout
            if wait_timeout == 0:
                wait_timeout = None  # No timeout

            # Wait for completion with timeout
            if not event.wait(timeout=wait_timeout):
                raise DispatcherTimeoutError(
                    f"Cross-thread call to {func.__name__ if hasattr(func, '__name__') else func} "
                    f"timed out after {wait_timeout} seconds. "
                    "The main thread may be blocked or not processing the queue."
                )

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

    @property
    def queue_size(self) -> int:
        """Return the current number of pending calls in the queue."""
        return self._queue.qsize()

    @property
    def max_queue_size(self) -> int:
        """Return the maximum queue size."""
        return self._max_queue_size

    @property
    def default_timeout(self) -> float:
        """Return the default timeout for cross-thread calls."""
        return self._default_timeout
