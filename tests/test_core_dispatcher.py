"""Tests for tkcurses._core.dispatcher.

Threading tests synchronise on events rather than sleeps, so they neither race
nor pad the suite with fixed delays.
"""

from __future__ import annotations

import threading
import time

import pytest

from tkcurses._core.dispatcher import CursesDispatcher, DispatcherClosed


@pytest.fixture
def dispatcher():
    """A dispatcher owned by the thread running the test."""
    disp = CursesDispatcher(owner_thread_id=threading.get_ident())
    yield disp
    disp.close()


@pytest.fixture(autouse=True)
def _reset_singleton():
    CursesDispatcher.reset()
    yield
    CursesDispatcher.reset()


def wait_until(predicate, *, timeout: float = 5.0, what: str = "condition"):
    """Block until ``predicate`` holds, failing rather than spinning forever."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError(f"timed out after {timeout:g}s waiting for {what}")
        time.sleep(0.001)


def run_in_thread(target):
    """Run ``target`` in a thread, returning (thread, box) for its outcome."""
    box: dict[str, object] = {}

    def wrapper():
        try:
            box["value"] = target()
        except BaseException as exc:
            box["error"] = exc

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    return thread, box


# ----------------------------------------------------------- owning thread


def test_owner_runs_calls_inline(dispatcher):
    assert dispatcher.is_owner
    assert dispatcher.call(lambda a, b: a + b, 2, 3) == 5
    assert dispatcher.pending == 0, "owner calls must not be queued"


def test_owner_exceptions_propagate(dispatcher):
    def boom():
        raise ValueError("inline failure")

    with pytest.raises(ValueError, match="inline failure"):
        dispatcher.call(boom)


def test_lock_is_reentrant(dispatcher):
    """A compound operation may dispatch again without deadlocking itself."""

    def outer():
        return dispatcher.call(lambda: "inner") + "/outer"

    assert dispatcher.call(outer) == "inner/outer"


def test_keyword_arguments_are_forwarded(dispatcher):
    assert dispatcher.call(lambda a, *, b=0: a * b, 3, b=4) == 12


# ----------------------------------------------------------- other threads


def test_worker_calls_are_queued_and_run_by_the_owner(dispatcher):
    queued = threading.Event()

    def from_worker():
        queued.set()
        return dispatcher.call(lambda: "ran on owner")

    thread, box = run_in_thread(from_worker)
    queued.wait(timeout=5)
    # The worker is now blocked; nothing runs until the owner drains.
    wait_until(lambda: dispatcher.pending > 0, what="the worker to queue its call")
    assert dispatcher.process_queue() == 1
    thread.join(timeout=5)
    assert box.get("value") == "ran on owner"


def test_queued_call_runs_on_the_owning_thread(dispatcher):
    owner_id = threading.get_ident()
    recorded: list[int] = []

    thread, _box = run_in_thread(
        lambda: dispatcher.call(lambda: recorded.append(threading.get_ident()))
    )
    wait_until(lambda: dispatcher.pending > 0, what="the worker to queue its call")
    dispatcher.process_queue()
    thread.join(timeout=5)
    assert recorded == [owner_id]


def test_worker_sees_exceptions_raised_by_its_call(dispatcher):
    def boom():
        raise KeyError("worker failure")

    thread, box = run_in_thread(lambda: dispatcher.call(boom))
    wait_until(lambda: dispatcher.pending > 0, what="the worker to queue its call")
    dispatcher.process_queue()
    thread.join(timeout=5)
    assert isinstance(box.get("error"), KeyError)


def test_a_returned_exception_is_returned_not_raised(dispatcher):
    """Distinguishing the two is why the outcome is not sniffed by isinstance."""
    sentinel = ValueError("this is a value, not a failure")

    thread, box = run_in_thread(lambda: dispatcher.call(lambda: sentinel))
    wait_until(lambda: dispatcher.pending > 0, what="the worker to queue its call")
    dispatcher.process_queue()
    thread.join(timeout=5)
    assert box.get("error") is None
    assert box.get("value") is sentinel


def test_post_does_not_block(dispatcher):
    ran: list[str] = []
    done = threading.Event()

    def from_worker():
        dispatcher.post(ran.append, "queued")
        done.set()

    thread, _ = run_in_thread(from_worker)
    assert done.wait(timeout=5), "post() must return without waiting"
    thread.join(timeout=5)
    dispatcher.process_queue()
    assert ran == ["queued"]


def test_calls_run_in_order(dispatcher):
    order: list[int] = []
    for n in range(5):
        dispatcher.post(order.append, n)
    assert dispatcher.process_queue() == 5
    assert order == [0, 1, 2, 3, 4]


def test_process_queue_limit_caps_the_batch(dispatcher):
    for n in range(10):
        dispatcher.post(lambda _n=n: None)
    assert dispatcher.process_queue(limit=4) == 4
    assert dispatcher.pending == 6


def test_process_queue_rejects_non_owning_threads(dispatcher):
    thread, box = run_in_thread(dispatcher.process_queue)
    thread.join(timeout=5)
    assert isinstance(box.get("error"), RuntimeError)


# ---------------------------------------------------------------- shutdown


def test_close_releases_waiting_threads(dispatcher):
    """A worker must never block forever once the loop has stopped."""
    entered = threading.Event()

    def from_worker():
        entered.set()
        return dispatcher.call(lambda: "never runs")

    thread, box = run_in_thread(from_worker)
    entered.wait(timeout=5)
    wait_until(lambda: dispatcher.pending > 0, what="the worker to queue its call")
    dispatcher.close()
    thread.join(timeout=5)
    assert not thread.is_alive(), "close() must not leave the worker blocked"
    assert isinstance(box.get("error"), DispatcherClosed)


def test_calls_after_close_are_rejected(dispatcher):
    dispatcher.close()
    thread, box = run_in_thread(lambda: dispatcher.call(lambda: None))
    thread.join(timeout=5)
    assert isinstance(box.get("error"), DispatcherClosed)


def test_post_after_close_is_rejected(dispatcher):
    dispatcher.close()
    with pytest.raises(DispatcherClosed):
        dispatcher.post(lambda: None)


def test_owner_can_still_call_after_close(dispatcher):
    """Teardown runs on the owning thread and still needs the lock."""
    dispatcher.close()
    assert dispatcher.call(lambda: "teardown") == "teardown"


def test_closed_flag(dispatcher):
    assert not dispatcher.closed
    dispatcher.close()
    assert dispatcher.closed


# --------------------------------------------------------------- singleton


def test_get_returns_one_instance():
    assert CursesDispatcher.get() is CursesDispatcher.get()


def test_singleton_binds_to_the_interpreter_main_thread():
    """Lazy creation from a worker must not make that worker the owner."""
    thread, box = run_in_thread(CursesDispatcher.get)
    thread.join(timeout=5)
    created = box.get("value")
    assert isinstance(created, CursesDispatcher)
    assert created.owner_thread_id == threading.main_thread().ident


def test_reset_discards_the_instance():
    first = CursesDispatcher.get()
    CursesDispatcher.reset()
    assert CursesDispatcher.get() is not first


def test_concurrent_get_yields_a_single_dispatcher():
    """Two threads racing through get() must not each build one."""
    barrier = threading.Barrier(8)
    seen: list[CursesDispatcher] = []
    lock = threading.Lock()

    def grab():
        barrier.wait(timeout=5)
        instance = CursesDispatcher.get()
        with lock:
            seen.append(instance)

    threads = [threading.Thread(target=grab, daemon=True) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert len(seen) == 8
    assert len({id(d) for d in seen}) == 1


# ------------------------------------------------------------ race windows

# These paths exist for interleavings a test cannot reliably provoke, so they
# are exercised directly rather than left unverified.


def test_call_stranded_by_a_close_race_is_released(dispatcher):
    """close() may drain the queue between the closed check and the put."""
    from tkcurses._core.dispatcher import _Call

    pending: _Call[None] = _Call(lambda: None, (), {})
    dispatcher.close()
    dispatcher._abort_if_closed(pending)
    assert pending.done.is_set()
    assert isinstance(pending.error, DispatcherClosed)


def test_abort_leaves_an_open_dispatcher_alone(dispatcher):
    from tkcurses._core.dispatcher import _Call

    pending: _Call[None] = _Call(lambda: None, (), {})
    dispatcher._abort_if_closed(pending)
    assert not pending.done.is_set()


def test_close_does_not_overwrite_a_completed_result(dispatcher):
    """A call the owner ran just before close() keeps its result."""
    from tkcurses._core.dispatcher import _Call

    pending: _Call[str] = _Call(lambda: "done", (), {})
    dispatcher._run(pending)
    assert pending.value == "done"
    dispatcher._fail(pending)
    assert pending.error is None
    assert pending.value == "done"


def test_get_yields_to_a_thread_that_won_the_race():
    """The second check inside the lock must return the winner's instance."""
    winner = CursesDispatcher()

    class RacingLock:
        def __enter__(self):
            # Simulate another thread creating the instance while we waited.
            CursesDispatcher._instance = winner
            return self

        def __exit__(self, *exc):
            return False

    original = CursesDispatcher._instance_lock
    CursesDispatcher._instance = None
    CursesDispatcher._instance_lock = RacingLock()
    try:
        assert CursesDispatcher.get() is winner
    finally:
        CursesDispatcher._instance_lock = original
