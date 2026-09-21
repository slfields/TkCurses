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


"""A tty program lives as long as the harness is willing to wait for it.

The harness's waiting budget is multiplied on CI by
``TKCURSES_TEST_TIMEOUT_SCALE``; the exit timers the programs schedule for
themselves are constants. Without something to reconcile them, a slow runner
gets a harness waiting twenty seconds for a program that quit after four -
which is TkCurses-txk, and why its failures named a different test each run.
"""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.tty

SHORT_LIFE = """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
buffer.write(0, 0, 'ready')
root.tk.screen.refresh()
root.after(600, root.quit)
root.mainloop()
"""


def lifetime(term, source, tmp_path):
    """How long the program runs after it says it is ready."""
    term.run_source(source, workdir=tmp_path)
    term.wait_for_text("ready")
    start = time.monotonic()
    term.wait_for_exit()
    return time.monotonic() - start


def test_a_quit_timer_is_scaled_with_the_harness(terminal, tmp_path, monkeypatch):
    """Measured rather than asserted about: at scale 4 the same 600ms timer
    keeps the program alive about four times as long.

    The scale is read by the child at startup, from a ``sitecustomize`` the
    harness writes beside the program - so the program itself is untouched
    and its line numbers are unchanged.
    """
    # Both arms set the scale. Reading the baseline from whatever the
    # environment happens to hold made this pass locally and fail on CI,
    # which sets the scale to 4 for the whole run - so the "unscaled" arm
    # was scaled, lived 2.51s, and failed a test asserting it was quick.
    monkeypatch.setenv("TKCURSES_TEST_TIMEOUT_SCALE", "1")
    plain = lifetime(terminal(cols=30, rows=6), SHORT_LIFE, tmp_path)

    monkeypatch.setenv("TKCURSES_TEST_TIMEOUT_SCALE", "4")
    scaled = lifetime(terminal(cols=30, rows=6), SHORT_LIFE, tmp_path / "scaled")

    assert plain < 1.5, f"unscaled life was {plain:.2f}s"
    assert scaled > plain * 2, f"{plain:.2f}s unscaled, {scaled:.2f}s scaled"


def test_only_quit_timers_are_scaled(terminal, tmp_path, monkeypatch):
    """An ordinary after() keeps its delay, or every animation the tty tests
    watch would run at a quarter speed and they would measure something else.
    """
    monkeypatch.setenv("TKCURSES_TEST_TIMEOUT_SCALE", "4")
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer


def tick():
    buffer.write(0, 0, 'ticked')
    root.tk.screen.refresh()


root.after(200, tick)
root.after(4000, root.quit)
root.tk.screen.refresh()
root.mainloop()
""",
        workdir=tmp_path,
    )
    start = time.monotonic()
    term.wait_for_text("ticked")
    assert time.monotonic() - start < 1.5


def test_the_shim_is_absent_when_nothing_asks_for_it(terminal, tmp_path, monkeypatch):
    """At scale 1 it installs nothing, so the ordinary case is untouched.

    The scale is set here rather than assumed. Asserting that the
    environment already held "1" was true on a development machine and false
    on CI, which sets it to 4 - a test that described where it was running
    rather than what the code does.
    """
    monkeypatch.setenv("TKCURSES_TEST_TIMEOUT_SCALE", "1")

    assert lifetime(terminal(cols=30, rows=6), SHORT_LIFE, tmp_path) < 1.5
