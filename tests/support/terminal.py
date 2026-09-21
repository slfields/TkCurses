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

"""Render TkCurses applications in a real pseudo-terminal and assert on output.

Curses writes escape sequences to a terminal; it cannot be meaningfully checked
by mocking. This harness runs application code in a child process attached to a
real pty, feeds the resulting byte stream through a VT100 emulator (``pyte``),
and exposes the emulated character grid for assertions. What the tests see is
what a terminal would actually display.

Usage::

    with TerminalHarness(cols=40, rows=10) as term:
        term.run_source(
            '''
            import curses
            def main(stdscr):
                stdscr.addstr(0, 0, "hello")
                stdscr.refresh()
                stdscr.getch()
            curses.wrapper(main)
            '''
        )
        term.wait_for_text("hello")
        assert term.text_at(0, 0, 5) == "hello"
        term.send_keys("q")

Two environment details are load-bearing and were established empirically:

* The pty window size must be set on the *slave* descriptor *before* forking.
  A child that starts before the size is applied initialises curses against
  the default 80x24 and never sees the intended dimensions.
* ``NCURSES_NO_UTF8_ACS=1`` makes ncurses emit UTF-8 box-drawing characters
  directly. Without it, borders arrive as VT100 alternate-charset letters and
  a border assertion reads ``lqqqqqk`` instead of ``┌─────┐``.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import locale
import os
import pty
import select
import signal
import struct
import sys
import termios
import textwrap
import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import pyte

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

__all__ = ["TerminalHarness", "TerminalTimeout"]

#: How much longer than the base budget to wait. A shared CI runner is
#: several times slower than a development machine, and every budget here was
#: chosen on a development machine: measured, a single tty test that takes
#: 2.9s alone takes 5.5s under twelve-way contention, and CI has timed out
#: waiting for a child to exit on runs where nothing was wrong with the code.
#:
#: Scaling rather than raising the numbers outright keeps a real failure fast
#: to report locally, which is where failures are read. A generous budget
#: costs nothing when the wait is going to succeed - it only changes how long
#: a wait that was always going to fail takes to say so.
TIMEOUT_SCALE = float(os.environ.get("TKCURSES_TEST_TIMEOUT_SCALE", "1"))

#: Default time budget, in seconds, for waiting on the child to render.
DEFAULT_TIMEOUT = 5.0 * TIMEOUT_SCALE


def _utf8_locale() -> str:
    """Pick a UTF-8 locale this host actually provides.

    The locale must be real: ncurses falls back to ASCII line-drawing if it
    cannot select a UTF-8 codeset, which quietly breaks border assertions.
    C.UTF-8 exists on modern glibc, en_US.UTF-8 on macOS and most images.
    """
    previous = locale.setlocale(locale.LC_ALL)
    try:
        for candidate in ("C.UTF-8", "en_US.UTF-8", "C.utf8", "en_US.utf8"):
            try:
                locale.setlocale(locale.LC_ALL, candidate)
            except locale.Error:
                continue
            return candidate
        return "C.UTF-8"
    finally:
        locale.setlocale(locale.LC_ALL, previous)


#: A UTF-8 locale that exists on this host.
UTF8_LOCALE = _utf8_locale()

#: Environment forced on the child so rendering is deterministic across hosts.
_CHILD_ENV = {
    "TERM": "xterm-256color",
    "LANG": UTF8_LOCALE,
    "LC_ALL": UTF8_LOCALE,
    # Emit real UTF-8 box glyphs rather than VT100 charset-switching.
    "NCURSES_NO_UTF8_ACS": "1",
    "PYTHONUNBUFFERED": "1",
    # Keep tracebacks stable and free of colour escapes on 3.13+.
    "PYTHONNODEBUGRANGES": "1",
    "NO_COLOR": "1",
}


class TerminalTimeout(AssertionError):
    """A wait expired before the terminal reached the expected state.

    Subclasses :class:`AssertionError` so an expiry reads as a test failure
    rather than an infrastructure error, and carries the rendered screen plus
    any child stderr so the failure is diagnosable without a rerun.
    """


class _Screen(pyte.Screen):
    """pyte's screen, plus the one sequence ncurses uses that it lacks.

    ncurses moves the cursor with back-tab - ``CSI Z`` - whenever that is the
    shortest way to reach a column. pyte has no handler for it and drops it
    silently, so its idea of the cursor drifts from the terminal's and every
    character written afterwards lands a few cells off. That shows up as a
    screen that is stably wrong rather than as a missing update, which is
    what makes it worth implementing rather than waiting out: a test sees
    text that no real terminal would ever have shown.

    It also tracks dim, which pyte does not model at all. curses draws a
    disabled widget with A_DIM and ncurses emits it as SGR 2; pyte's Char has
    no field for it, so every disabled widget looked identical to a live one
    and nothing could assert otherwise. Tracked here as a set of cells rather
    than by extending Char, which is a namedtuple and not extensible.

    The tracking is per line: a run of dim text that wraps onto the next row
    is recorded only as far as the line it started on. Nothing here writes
    text that wraps, and widening it would mean reimplementing pyte's own
    wrapping.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._dim = False
        self._dim_cells: set[tuple[int, int]] = set()
        super().__init__(*args, **kwargs)

    def reset(self) -> None:
        """Clear the screen, and everything remembered about it."""
        super().reset()
        self._dim = False
        self._dim_cells = set()

    def select_graphic_rendition(self, *attrs: int, **kwargs: object) -> None:
        """Note dim on the way past, then let pyte handle the rest.

        SGR 2 turns it on; 0 and 22 turn it off, and ncurses usually sends
        the pair together as ``ESC [ 0 ; 2 m``, so the order matters.
        """
        for code in attrs or (0,):
            if code == 2:
                self._dim = True
            elif code in (0, 22):
                self._dim = False
        super().select_graphic_rendition(*attrs, **kwargs)

    def draw(self, data: str) -> None:
        """Write characters, recording which cells came out dim."""
        row, start = self.cursor.y, self.cursor.x
        super().draw(data)
        end = self.cursor.x if self.cursor.y == row else self.columns
        for column in range(start, max(start, end)):
            if self._dim:
                self._dim_cells.add((row, column))
            else:
                self._dim_cells.discard((row, column))

    def is_dim(self, row: int, column: int) -> bool:
        """Whether one cell was drawn dim."""
        return (row, column) in self._dim_cells

    def cursor_back_tab(self, count: int = 0) -> None:
        """Move the cursor back ``count`` tab stops, as ``CSI Z`` does."""
        for _ in range(count or 1):
            behind = [stop for stop in self.tabstops if stop < self.cursor.x]
            self.cursor.x = max(behind) if behind else 0


class _ByteStream(pyte.ByteStream):
    """pyte's byte stream, taught the sequence :class:`_Screen` implements."""

    csi: ClassVar[dict[str, str]] = {
        **pyte.ByteStream.csi,
        "Z": "cursor_back_tab",
    }


class TerminalHarness:
    """Runs a program under a pty and exposes the rendered character grid.

    Args:
        cols: Terminal width in character cells.
        rows: Terminal height in character cells.
        timeout: Default seconds for :meth:`wait_for` and friends.
        env: Extra environment variables for the child process.
    """

    def __init__(
        self,
        cols: int = 80,
        rows: int = 24,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        env: dict[str, str] | None = None,
        stderr_to_terminal: bool = False,
    ) -> None:
        self.cols = cols
        self.rows = rows
        self.timeout = timeout
        self._extra_env = dict(env or {})
        #: Send the child's stderr to the pty rather than to a pipe of its
        #: own. Off by default, because a traceback written into the terminal
        #: corrupts the very output under assertion - which is the point of
        #: the option: some behaviour only exists when stderr *is* the screen,
        #: and nothing could test it while the harness always separated them.
        self._stderr_to_terminal = stderr_to_terminal

        self._screen = _Screen(cols, rows)
        self._stream = _ByteStream(self._screen)
        # Set when the application enables keypad transmit mode (smkx). A real
        # terminal then sends SS3-prefixed cursor keys, so the harness must too.
        self._app_cursor_keys = False

        self._master: int | None = None
        self._err_read: int | None = None
        self._pid: int | None = None
        self._exit_status: int | None = None
        self._stderr = bytearray()
        #: Every byte the child has sent. Kept so a test can assert what the
        #: application asked the *terminal* for - mouse modes, cursor
        #: visibility - which the rendered screen cannot show.
        self._received = bytearray()
        self._workdir: Path | None = None

    # ------------------------------------------------------------ lifecycle

    def __enter__(self) -> TerminalHarness:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def run_source(self, source: str, *, workdir: Path | None = None) -> None:
        """Run Python ``source`` in a child process attached to the pty.

        The source is dedented and written to a file so tracebacks carry real
        line numbers instead of ``<string>``.
        """
        if self._pid is not None:
            raise RuntimeError("harness is already running a program")
        if workdir is None:
            override = os.environ.get("PYTEST_CURRENT_TEST_TMPDIR", "")
            workdir = Path(override) if override else Path.cwd() / ".pytest_cache"
        workdir.mkdir(parents=True, exist_ok=True)
        script = workdir / f"tkc_app_{os.getpid()}_{id(self)}.py"
        script.write_text(textwrap.dedent(source), encoding="utf-8")
        self._workdir = workdir
        self.run([sys.executable, str(script)])

    def _install_quit_timer_shim(self) -> Path | None:
        """Put ``sitecustomize.py`` where the child will import it.

        A tty program schedules its own exit so that a wedged one cannot hang
        the suite, and those delays are constants while the harness's waiting
        budget is multiplied on CI. The shim scales the exit timers to match.
        See ``tests/support/quit_timer_shim.py`` for why that matters.

        Returns the directory to add to ``PYTHONPATH``, or None when there is
        nowhere to write it.
        """
        workdir = self._workdir
        if workdir is None:
            return None
        source = Path(__file__).with_name("quit_timer_shim.py")
        target = workdir / "sitecustomize.py"
        with contextlib.suppress(OSError):
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            return workdir
        return None

    def run(self, argv: Sequence[str]) -> None:
        """Fork a child attached to the pty and exec ``argv`` in it."""
        if self._pid is not None:
            raise RuntimeError("harness is already running a program")

        master, slave = pty.openpty()
        # Size the pty BEFORE forking so curses initialises at cols x rows.
        self._set_winsize(slave)
        # Keep the child's stderr off the rendered screen: a traceback written
        # into the terminal would corrupt the very output under assertion.
        err_r, err_w = os.pipe()

        pid = os.fork()
        if pid == 0:  # pragma: no cover - runs only in the forked child
            self._child_exec(argv, slave, master, err_r, err_w)

        os.close(slave)
        os.close(err_w)
        os.set_blocking(err_r, False)
        self._master = master
        self._err_read = err_r
        self._pid = pid

    def _child_exec(
        self, argv: Sequence[str], slave: int, master: int, err_r: int, err_w: int
    ) -> None:  # pragma: no cover - child process
        try:
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
            os.dup2(slave, 0)
            os.dup2(slave, 1)
            os.dup2(slave if self._stderr_to_terminal else err_w, 2)
            for fd in (master, slave, err_r, err_w):
                if fd > 2:
                    os.close(fd)
            env = {**os.environ, **_CHILD_ENV, **self._extra_env}
            shim = self._install_quit_timer_shim()
            if shim is not None:
                existing = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = (
                    f"{shim}{os.pathsep}{existing}" if existing else str(shim)
                )
            env["COLUMNS"] = str(self.cols)
            env["LINES"] = str(self.rows)
            os.execvpe(argv[0], list(argv), env)
        except BaseException:
            os._exit(127)

    def close(self) -> None:
        """Terminate the child if still running and release all descriptors."""
        if self._pid is not None:
            self._drain(0.05)
            with contextlib.suppress(ProcessLookupError):
                os.kill(self._pid, signal.SIGTERM)
            self._reap(timeout=1.0)
        for fd in (self._master, self._err_read):
            if fd is not None:
                with contextlib.suppress(OSError):
                    os.close(fd)
        self._master = None
        self._err_read = None
        if self._workdir is not None:
            for leftover in self._workdir.glob(f"tkc_app_{os.getpid()}_{id(self)}.py"):
                leftover.unlink(missing_ok=True)

    def _budget(self, timeout: float | None) -> float:
        """The seconds to allow for a wait.

        A timeout named by a caller is scaled the same way the default is:
        ``timeout=10`` means "generous on a development machine", and on a
        runner several times slower it has to mean several times that or it
        means nothing.
        """
        return self.timeout if timeout is None else timeout * TIMEOUT_SCALE

    def wait_for_exit(self, *, timeout: float | None = None) -> int:
        """Wait for the child to exit and return its exit code.

        Keeps pumping the terminal while it waits, so output written on the
        way out is not lost, and so a child blocked writing into a full pty
        buffer can finish.

        Raises:
            TerminalTimeout: If the child is still running when time runs out.
        """
        if self._pid is None:
            return self.exit_code
        budget = self._budget(timeout)
        deadline = time.monotonic() + budget
        while time.monotonic() < deadline:
            self._drain(0.05)
            pid, status = os.waitpid(self._pid, os.WNOHANG)
            if pid:
                self._exit_status = status
                self._pid = None
                return self.exit_code
        raise TerminalTimeout(f"child did not exit within {budget}s\n{self.describe()}")

    @property
    def exit_code(self) -> int:
        """The exit code of the child, once it has exited.

        Raises:
            RuntimeError: If it is still running, since there is no answer yet.
        """
        if self._exit_status is None:
            raise RuntimeError("the child has not exited")
        return os.waitstatus_to_exitcode(self._exit_status)

    def _reap(self, timeout: float) -> None:
        """Wait for the child, escalating to SIGKILL if it ignores SIGTERM."""
        if self._pid is None:
            return
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pid, status = os.waitpid(self._pid, os.WNOHANG)
            if pid:
                self._exit_status = status
                self._pid = None
                return
            time.sleep(0.01)
        try:
            os.kill(self._pid, signal.SIGKILL)
            _, status = os.waitpid(self._pid, 0)
            self._exit_status = status
        except (ProcessLookupError, ChildProcessError):
            pass
        self._pid = None

    @property
    def exit_status(self) -> int | None:
        """Child exit status, or ``None`` while it is still running."""
        if self._pid is not None:
            pid, status = os.waitpid(self._pid, os.WNOHANG)
            if pid:
                self._exit_status = status
                self._pid = None
        return self._exit_status

    # ----------------------------------------------------------------- I/O

    def _set_winsize(self, fd: int) -> None:
        fcntl.ioctl(
            fd, termios.TIOCSWINSZ, struct.pack("HHHH", self.rows, self.cols, 0, 0)
        )

    def _drain(self, budget: float) -> bool:
        """Read whatever is available for up to ``budget`` seconds.

        Returns True if any terminal output was consumed. Idle gaps are
        tolerated: the child may pause between writes, and treating the first
        quiet moment as end-of-output reads an empty screen, because process
        startup is slower than the first poll.
        """
        got = False
        deadline = time.monotonic() + budget
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return got
            watch = [fd for fd in (self._master, self._err_read) if fd is not None]
            if not watch:
                return got
            try:
                ready, _, _ = select.select(watch, [], [], remaining)
            except OSError as exc:
                if exc.errno == errno.EINTR:
                    continue
                return got
            if not ready:
                return got
            for fd in ready:
                try:
                    data = os.read(fd, 65536)
                except OSError:
                    # EIO on the master means the child closed the pty.
                    continue
                if not data:
                    continue
                if fd == self._master:
                    self._received.extend(data)
                    self._note_modes(data)
                    self._stream.feed(data)
                    got = True
                else:
                    self._stderr.extend(data)

    def _note_modes(self, data: bytes) -> None:
        """Track terminal modes the child sets that change how keys encode.

        ncurses' keypad(True) emits smkx (``ESC [ ? 1 h``), which switches
        cursor keys from CSI to SS3 form. A terminal that ignored this would
        send sequences the application cannot decode.
        """
        if _SMKX in data:
            self._app_cursor_keys = True
        if _RMKX in data:
            self._app_cursor_keys = False

    @property
    def application_cursor_keys(self) -> bool:
        """True while the child has keypad transmit mode enabled."""
        self._drain(0.0)
        return self._app_cursor_keys

    def wait_for(
        self,
        predicate: Callable[[TerminalHarness], bool],
        *,
        timeout: float | None = None,
        message: str = "condition",
    ) -> None:
        """Pump output until ``predicate`` holds, or fail with the screen shown.

        Polling the emulated screen beats sleeping a fixed interval: it is both
        faster when the app is quick and reliable when it is slow.
        """
        budget = self._budget(timeout)
        deadline = time.monotonic() + budget
        while True:
            if predicate(self):
                return
            if time.monotonic() >= deadline:
                raise TerminalTimeout(
                    f"timed out after {budget:g}s waiting for {message}\n"
                    f"{self.describe()}"
                )
            self._drain(min(0.05, max(0.0, deadline - time.monotonic())))

    def wait_for_text(self, text: str, *, timeout: float | None = None) -> None:
        """Wait until ``text`` appears anywhere on the screen."""
        self.wait_for(
            lambda t: t.contains(text), timeout=timeout, message=f"text {text!r}"
        )

    def wait_for_idle(
        self, quiet: float = 0.15, *, timeout: float | None = None
    ) -> None:
        """Wait until the child stops producing output for ``quiet`` seconds."""
        budget = self._budget(timeout)
        deadline = time.monotonic() + budget
        while time.monotonic() < deadline:
            if not self._drain(quiet):
                return
        raise TerminalTimeout(
            f"terminal never went idle within {budget:g}s\n{self.describe()}"
        )

    def send(self, data: bytes) -> None:
        """Write raw bytes to the terminal as though typed."""
        if self._master is None:
            raise RuntimeError("no program is running")
        os.write(self._master, data)

    def send_keys(self, *keys: str) -> None:
        """Send keystrokes. Accepts literal text and ``<Name>`` key symbols."""
        self._drain(0.0)  # observe any mode change before encoding
        for key in keys:
            self.send(_encode_key(key, app_cursor=self._app_cursor_keys))

    def send_mouse(
        self,
        x: int,
        y: int,
        *,
        button: int = 1,
        action: str = "press",
        shift: bool = False,
        alt: bool = False,
        ctrl: bool = False,
    ) -> None:
        """Report a mouse action at cell ``(x, y)``, as a terminal would.

        Uses the SGR encoding (``ESC [ < b ; col ; row M``), which ncurses
        enables for modern terminals and which, unlike the older X10 scheme,
        is not limited to the first 223 columns. Coordinates are the same
        0-based cells the rest of the harness uses; the escape sequence's
        1-based numbering is applied here.

        Args:
            x: Column, 0-based.
            y: Row, 0-based.
            button: 1 left, 2 middle, 3 right, 4 wheel up, 5 wheel down.
            action: "press", "release", or "move".
        """
        if button not in (1, 2, 3, 4, 5):
            raise ValueError(f"unknown mouse button: {button}")
        if action not in ("press", "release", "move"):
            raise ValueError(f"unknown mouse action: {action}")
        code = 64 + (button - 4) if button in (4, 5) else button - 1
        if action == "move":
            code += 32
        if shift:
            code += 4
        if alt:
            code += 8
        if ctrl:
            code += 16
        final = "m" if action == "release" else "M"
        self.send(f"\x1b[<{code};{x + 1};{y + 1}{final}".encode())

    def click(
        self, x: int, y: int, *, button: int = 1, settle: float | None = None
    ) -> None:
        """Press and release at ``(x, y)``, pausing either side, as a hand does.

        Neither pause is decoration, and they are for different faults.

        Between the press and the release: sent back to back the two escape
        sequences arrive in one read, and ncurses holds the release until
        something else turns up - so an application sees a button pressed and
        never released.

        After the release: **ncurses drops mouse reports that arrive faster
        than the application drains them.** Measured with a plain curses
        program, no TkCurses involved - a handler that takes 120ms to run
        loses two of the four events from two clicks, on an idle machine.
        Without this pause a test that clicks a list and then a button left
        the button drawn pressed and never invoked, every time on a single
        core, and intermittently on a CI runner - which is what made CI red
        more often than green.

        No real mouse produces either shape. A click takes tens of
        milliseconds and a person does not click twice in fifty of them,
        which is what ``settle`` stands in for.

        What this can promise is bounded by ``settle``: measured, an
        application answering within 0.05s gets every event, and one taking
        0.08s starts losing them. Drive something slower than that with a
        larger settle rather than expecting the default to cover it.

        Which is why the default is scaled, like every other wait here. 0.05s
        described *this* machine: on a runner six to ten times slower a canvas
        repaint takes 100-124ms, past the boundary the paragraph above names,
        and the report is dropped before the application ever drains it. That
        is the whole of the intermittent canvas-click failure on the slowest
        CI job - not a lost binding, a lost *event*. A named settle is scaled
        too, so "slower than the default" keeps meaning that everywhere.
        """
        settle = self._budget(0.05 if settle is None else settle)
        self.send_mouse(x, y, button=button, action="press")
        if settle:
            self._drain(settle)
        self.send_mouse(x, y, button=button, action="release")
        if settle:
            self._drain(settle)

    def resize(self, cols: int, rows: int) -> None:
        """Resize the terminal and signal the child, as a real resize would."""
        self.cols, self.rows = cols, rows
        self._screen.resize(rows, cols)
        if self._master is not None:
            self._set_winsize(self._master)
        if self._pid is not None:
            os.killpg(os.getpgid(self._pid), signal.SIGWINCH)

    # --------------------------------------------------------- assertions

    @property
    def display(self) -> list[str]:
        """The screen as a list of row strings, padded to the full width."""
        return list(self._screen.display)

    @property
    def received(self) -> bytes:
        """Every byte the child has written to the terminal so far."""
        self._drain(0.0)
        return bytes(self._received)

    @property
    def stderr(self) -> str:
        """Anything the child wrote to stderr, typically a traceback."""
        self._drain(0.0)
        return self._stderr.decode("utf-8", "replace")

    @property
    def cursor(self) -> tuple[int, int]:
        """Cursor position as ``(row, col)``."""
        return self._screen.cursor.y, self._screen.cursor.x

    def text_at(self, row: int, col: int, length: int | None = None) -> str:
        """Text on ``row`` starting at ``col``, defaulting to end of line."""
        line = self.display[row]
        return line[col:] if length is None else line[col : col + length]

    def row(self, row: int) -> str:
        """A whole row with trailing blanks stripped."""
        return self.display[row].rstrip()

    def contains(self, text: str) -> bool:
        """True if ``text`` appears within any single row."""
        return any(text in line for line in self.display)

    def find_text(self, text: str) -> tuple[int, int] | None:
        """Locate ``text``, returning ``(row, col)`` of its first occurrence."""
        for y, line in enumerate(self.display):
            x = line.find(text)
            if x != -1:
                return y, x
        return None

    def char_at(self, row: int, col: int) -> pyte.screens.Char:
        """The full cell at ``(row, col)``, including colour and attributes."""
        return self._screen.buffer[row][col]

    def attrs_at(self, row: int, col: int) -> dict[str, object]:
        """Rendering attributes of one cell, for style assertions."""
        cell = self.char_at(row, col)
        return {
            "fg": cell.fg,
            "bg": cell.bg,
            "bold": cell.bold,
            "reverse": cell.reverse,
            "underscore": cell.underscore,
            # pyte has no field for this; _Screen tracks it separately.
            "dim": self._screen.is_dim(row, col),
        }

    def region(self, top: int, left: int, height: int, width: int) -> list[str]:
        """A rectangular block of the screen, as row strings."""
        return [line[left : left + width] for line in self.display[top : top + height]]

    def assert_box(
        self,
        top: int,
        left: int,
        height: int,
        width: int,
        *,
        timeout: float | None = None,
    ) -> None:
        """Wait for a box-drawn border to occupy the given rectangle.

        Checks corners and edges, which is what actually distinguishes a
        correctly drawn border from an off-by-one one.

        Waits rather than asserting on one sample. curses sends a refresh as
        a series of writes and the harness can read the screen between them,
        so a box still arriving looked exactly like a box drawn wrong - a
        false failure roughly one CI run in ten, and only ever on the slowest
        machine in the matrix.
        """
        budget = self._budget(timeout)
        deadline = time.monotonic() + budget
        while True:
            faults = self._box_faults(top, left, height, width)
            if not faults:
                return
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"box at ({top},{left}) {width}x{height} is malformed:\n"
                    + "\n".join(faults[:12])
                    + f"\n{self.describe()}"
                )
            self._drain(min(0.05, max(0.0, deadline - time.monotonic())))

    def _box_faults(self, top: int, left: int, height: int, width: int) -> list[str]:
        """Every cell of a box border that is not what it should be."""
        bottom, right = top + height - 1, left + width - 1
        corners = {
            (top, left): "┌",
            (top, right): "┐",
            (bottom, left): "└",
            (bottom, right): "┘",
        }
        bad = [
            f"  ({y},{x}) expected {want!r}, got {self.display[y][x]!r}"
            for (y, x), want in corners.items()
            if self.display[y][x] != want
        ]
        for x in range(left + 1, right):
            for y in (top, bottom):
                if self.display[y][x] != "─":
                    bad.append(f"  ({y},{x}) expected '─', got {self.display[y][x]!r}")
        for y in range(top + 1, bottom):
            for x in (left, right):
                if self.display[y][x] != "│":
                    bad.append(f"  ({y},{x}) expected '│', got {self.display[y][x]!r}")
        return bad

    def describe(self) -> str:
        """A framed rendering of the screen, plus child stderr, for failures."""
        rule = "─" * self.cols
        body = "\n".join(f"│{line}│" for line in self.display)
        out = f"screen {self.cols}x{self.rows}:\n┌{rule}┐\n{body}\n└{rule}┘"
        err = self.stderr.strip()
        if err:
            out += f"\nchild stderr:\n{textwrap.indent(err, '  ')}"
        return out


#: Sequences by which ncurses turns keypad transmit mode on and off.
_SMKX = b"\x1b[?1h"
_RMKX = b"\x1b[?1l"

#: Cursor keys in normal (CSI) and application (SS3) mode. Which one a real
#: terminal sends depends on whether the application enabled smkx.
_CURSOR_KEYS: dict[str, tuple[bytes, bytes]] = {
    "<Up>": (b"\x1b[A", b"\x1bOA"),
    "<Down>": (b"\x1b[B", b"\x1bOB"),
    "<Right>": (b"\x1b[C", b"\x1bOC"),
    "<Left>": (b"\x1b[D", b"\x1bOD"),
    "<Home>": (b"\x1b[H", b"\x1bOH"),
    "<End>": (b"\x1b[F", b"\x1bOF"),
}

#: Key symbols to the bytes a terminal sends for them.
_KEYS: dict[str, bytes] = {
    # Modified cursor keys use the CSI 1 ; modifier form, where the modifier
    # is 1 plus the bits: Shift is 2, Control 5, both 6. ncurses decodes
    # these through terminfo into single key codes - Shift-Down is KEY_SF,
    # Shift-Up is KEY_SR - rather than reporting a modifier separately.
    "<Shift-Up>": b"\x1b[1;2A",
    "<Shift-Down>": b"\x1b[1;2B",
    "<Shift-Right>": b"\x1b[1;2C",
    "<Shift-Left>": b"\x1b[1;2D",
    "<Shift-Home>": b"\x1b[1;2H",
    "<Shift-End>": b"\x1b[1;2F",
    "<Control-Up>": b"\x1b[1;5A",
    "<Control-Down>": b"\x1b[1;5B",
    "<Control-Right>": b"\x1b[1;5C",
    "<Control-Left>": b"\x1b[1;5D",
    "<Control-Home>": b"\x1b[1;5H",
    "<Control-End>": b"\x1b[1;5F",
    # The modifier parameter is one more than a three-bit set - 6 is Shift
    # and Control together - and ncurses gives each combination a key code
    # of its own, named for the combination.
    "<Control-Shift-Up>": b"\x1b[1;6A",
    "<Control-Shift-Down>": b"\x1b[1;6B",
    "<Control-Shift-Right>": b"\x1b[1;6C",
    "<Control-Shift-Left>": b"\x1b[1;6D",
    "<Alt-Up>": b"\x1b[1;3A",
    "<Alt-Down>": b"\x1b[1;3B",
    "<Return>": b"\r",
    "<Enter>": b"\r",
    "<Tab>": b"\t",
    "<BackSpace>": b"\x7f",
    "<Escape>": b"\x1b",
    "<Space>": b" ",
    "<Prior>": b"\x1b[5~",
    "<Next>": b"\x1b[6~",
    "<Insert>": b"\x1b[2~",
    "<Delete>": b"\x1b[3~",
    # Function keys as xterm sends them, which is what _CHILD_ENV claims to
    # be. The obvious formula - CSI 10+n ~ - is the linux and vt220 encoding:
    # under xterm it makes F1 arrive as Escape, [, 1, 1, ~ and only F5 comes
    # out right by coincidence. F1 to F4 are SS3, and the numbers above skip
    # 16 and 22.
    "<F1>": b"\x1bOP",
    "<F2>": b"\x1bOQ",
    "<F3>": b"\x1bOR",
    "<F4>": b"\x1bOS",
    **{
        f"<F{n}>": f"\x1b[{code}~".encode()
        for n, code in zip(range(5, 13), (15, 17, 18, 19, 20, 21, 23, 24), strict=True)
    },
    **{f"<Control-{c}>": bytes([ord(c) - 96]) for c in "abcdefghijklmnopqrstuvwxyz"},
}


def _encode_key(key: str, *, app_cursor: bool = False) -> bytes:
    """Encode one key specification into the bytes a terminal would send."""
    if key in _CURSOR_KEYS:
        normal, application = _CURSOR_KEYS[key]
        return application if app_cursor else normal
    if key in _KEYS:
        return _KEYS[key]
    if key.startswith("<") and key.endswith(">") and len(key) > 2:
        raise ValueError(f"unknown key symbol: {key}")
    return key.encode("utf-8")


def keys_for(spec: Iterable[str], *, app_cursor: bool = False) -> bytes:
    """Encode several key specifications into one byte string."""
    return b"".join(_encode_key(k, app_cursor=app_cursor) for k in spec)
