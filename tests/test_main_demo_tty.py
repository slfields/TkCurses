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

"""``python -m tkcurses``: the two halves of the library in one program.

This is the one place the library's own claim is checked end to end - that a
curses window and a tkinter widget can share a terminal rather than take
turns with it - so it is also the smoke test for both compatibility modules.
"""

from __future__ import annotations

import sys

import pytest

from tkcurses.__main__ import CURSES_TITLE, PRESSED

pytestmark = pytest.mark.tty


@pytest.fixture
def demo(terminal):
    """The demo running on an ordinary terminal, drawn and settled."""

    def _start(cols=80, rows=24):
        term = terminal(cols=cols, rows=rows)
        term.run([sys.executable, "-m", "tkcurses"])
        term.wait_for_text(CURSES_TITLE)
        term.wait_for_idle()
        return term

    return _start


def test_both_halves_are_on_the_screen_at_once(demo):
    """The claim. Not two applications taking turns: one screen, one refresh,
    a widget on one side of it and a curses window on the other."""
    term = demo()
    screen = "\n".join(term.display)
    assert "widget half" in screen, term.describe()
    assert CURSES_TITLE in screen, term.describe()
    term.send_keys("<Escape>")
    assert term.wait_for_exit(timeout=10) == 0


def test_the_curses_half_keeps_its_own_box(demo):
    term = demo()
    row = next(i for i, line in enumerate(term.display) if CURSES_TITLE in line)
    line = term.display[row]
    left = line.index(CURSES_TITLE)
    assert "│" in line[:left], term.describe()
    assert "│" in line[left:], "the curses window lost its right side"
    term.send_keys("<Escape>")


def test_the_widget_half_still_answers(demo):
    """A curses window sharing the screen must not cost the widgets their
    input - which is the way this would most plausibly go wrong."""
    term = demo()
    row = next(i for i, line in enumerate(term.display) if "Press" in line)
    term.click(term.display[row].index("Press"), row)
    term.wait_for_text(PRESSED)
    term.send_keys("<Escape>")
    assert term.wait_for_exit(timeout=10) == 0


def test_the_curses_half_survives_a_widget_repaint(demo):
    """The widgets own the buffer and will draw over anything in it, so the
    curses half has to be put back after every repaint."""
    term = demo()
    row = next(i for i, line in enumerate(term.display) if "Press" in line)
    term.click(term.display[row].index("Press"), row)
    term.wait_for_text(PRESSED)
    term.wait_for_idle()
    assert CURSES_TITLE in "\n".join(term.display), term.describe()
    term.send_keys("<Escape>")


def test_it_comes_back_after_a_resize(demo):
    """Waiting for the redraw, not for quiet.

    term.resize() resizes the emulator at once and only then signals the
    child, so the screen goes quiet immediately - holding the old content,
    truncated. wait_for_idle() returns on that quiet, before the application
    has reacted at all, and the assertion then reads a screen the application
    never drew. On this machine the child answered inside the idle window and
    the test passed; on a slower one it did not, and the failure looked like
    the demo losing its widgets. It was the test looking too early.
    """
    term = demo()
    term.resize(70, 20)
    term.wait_for(
        lambda t: (
            "widget half" in "\n".join(t.display)
            and CURSES_TITLE in "\n".join(t.display)
        ),
        message="both halves to come back after the resize",
    )
    term.send_keys("<Escape>")
    assert term.wait_for_exit(timeout=10) == 0


def test_escape_gives_the_terminal_back(demo):
    term = demo()
    term.send_keys("<Escape>")
    assert term.wait_for_exit(timeout=10) == 0
    assert "Traceback" not in term.stderr


def test_it_runs_on_a_small_terminal(demo):
    """Not everyone has eighty columns, and a demo that only works on one
    size is a demo that will be run on the other."""
    term = demo(cols=60, rows=16)
    assert CURSES_TITLE in "\n".join(term.display), term.describe()
    term.send_keys("<Escape>")
    assert term.wait_for_exit(timeout=10) == 0
