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

"""What a raising callback does to the screen, and where its traceback goes.

The harness normally keeps a child's stderr on a pipe of its own, so that a
traceback cannot corrupt the output under assertion. That also means it could
never reproduce the case this is about - a traceback written to the same
terminal curses is drawing on - so these tests ask for the other wiring.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


RAISER = """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
for row in range(6):
    buffer.write(row, 0, 'row %d %s' % (row, 'x' * 20))
buffer.write(8, 0, 'ready')
root.tk.screen.refresh()

def boom(event):
    raise RuntimeError('the callback was supposed to fail')

root.bind('<Key-b>', boom)
root.bind('<Key-q>', lambda event: root.quit())
root.after(6000, root.quit)
root.mainloop()
root.destroy()
"""


def test_the_display_survives_a_raising_callback(terminal, tmp_path):
    """The whole point: a traceback must not be left lying on the screen."""
    term = terminal(cols=40, rows=12, stderr_to_terminal=True)
    term.run_source(RAISER, workdir=tmp_path)
    term.wait_for_text("ready")
    before = list(term.display)
    term.send(b"b")
    term.wait_for_idle()
    assert term.display == before, term.describe()


def test_the_application_survives_it_too(terminal, tmp_path):
    term = terminal(cols=40, rows=12, stderr_to_terminal=True)
    term.run_source(RAISER, workdir=tmp_path)
    term.wait_for_text("ready")
    term.send(b"b")
    term.wait_for_idle()
    term.send(b"q")
    assert term.wait_for_exit(timeout=10) == 0


def test_the_traceback_arrives_once_the_screen_is_given_back(terminal, tmp_path):
    """Held, not lost: a developer still needs to see what happened."""
    term = terminal(cols=40, rows=12, stderr_to_terminal=True)
    term.run_source(RAISER, workdir=tmp_path)
    term.wait_for_text("ready")
    term.send(b"b")
    term.wait_for_idle()
    assert "supposed to fail" not in "\n".join(term.display)
    term.send(b"q")
    term.wait_for_exit(timeout=10)
    term.wait_for_text("supposed to fail")


def test_several_failures_are_all_reported(terminal, tmp_path):
    # Tall enough to hold three tracebacks at once: they are printed after
    # the screen is given back, so anything that does not fit scrolls away.
    term = terminal(cols=60, rows=60, stderr_to_terminal=True)
    term.run_source(RAISER, workdir=tmp_path)
    term.wait_for_text("ready")
    for _ in range(3):
        term.send(b"b")
        term.wait_for_idle()
    term.send(b"q")
    term.wait_for_exit(timeout=10)
    term.wait_for(
        lambda t: "\n".join(t.display).count("supposed to fail") >= 3,
        message="all three tracebacks",
    )


def test_a_redirected_traceback_is_written_at_once(terminal, tmp_path):
    """Nothing to damage, and a developer watching a log wants it now.

    This is the harness's ordinary wiring, so it is also what every other
    test in the suite sees.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(RAISER, workdir=tmp_path)
    term.wait_for_text("ready")
    term.send(b"b")
    term.wait_for(
        lambda t: "supposed to fail" in t.stderr, message="the traceback on stderr"
    )
    assert "supposed to fail" not in "\n".join(term.display)
