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

"""A program whose terminal goes away under ``mainloop``.

Closing the terminal's window, or losing the SSH connection it came over,
hangs it up: the program gets SIGHUP, and its terminal reads end of file
from then on. Measured before this was handled: with SIGHUP at its default
the process died where it stood, so no ``finally`` block, ``atexit`` handler
or code after ``mainloop()`` ran, and nothing a program meant to save was
saved; with SIGHUP ignored, as under ``nohup``, it never exited at all and
spun on the dead terminal at full CPU.

Now the loop ends the program with SystemExit, status 129, as a shell
reports a process SIGHUP killed, so a program's own cleanup runs.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

APPLICATION = """
import atexit
import signal

import tkcurses

LOG = %(log)r
HANDLING = %(handling)r


def note(what):
    with open(LOG, 'a') as log:
        log.write(what + '\\n')


if HANDLING == 'ignored':
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
elif HANDLING == 'own handler':
    signal.signal(signal.SIGHUP, lambda signum, frame: note('handler'))
atexit.register(note, 'atexit')

root = tkcurses.Tk()
tkcurses.Label(root, text='RUNNING').pack()
root.after(20000, root.quit)
try:
    root.mainloop()
    note('mainloop returned')
except SystemExit as exc:
    note('SystemExit %%s' %% exc.code)
    raise
finally:
    note('finally')
"""


@pytest.mark.parametrize("handling", ["default", "ignored", "own handler"])
def test_a_hangup_ends_the_program_and_its_cleanup_runs(terminal, tmp_path, handling):
    log = tmp_path / "events.txt"
    term = terminal(cols=30, rows=6)
    term.run_source(
        APPLICATION % {"log": str(log), "handling": handling}, workdir=tmp_path
    )
    term.wait_for_text("RUNNING")
    term.hang_up()
    assert term.wait_for_exit(timeout=5) == 129
    expected = ["SystemExit 129", "finally", "atexit"]
    if handling == "own handler":
        # The program's handler is left in charge, and runs; the loop then
        # finds the terminal gone rather than spinning on it.
        expected.insert(0, "handler")
    assert log.read_text().splitlines() == expected
    assert "Traceback" not in term.stderr


def test_quit_still_returns_from_mainloop(terminal, tmp_path):
    """Nothing about the hangup handling outlasts the loop or changes it."""
    log = tmp_path / "events.txt"
    source = APPLICATION % {"log": str(log), "handling": "default"}
    term = terminal(cols=30, rows=6)
    term.run_source(
        source.replace("root.after(20000, root.quit)", "root.after(300, root.quit)")
        + "import signal\nnote('default again: %s' % (signal.getsignal(signal.SIGHUP) is signal.SIG_DFL))\n",
        workdir=tmp_path,
    )
    assert term.wait_for_exit(timeout=10) == 0
    assert log.read_text().splitlines() == [
        "mainloop returned",
        "finally",
        "default again: True",
        "atexit",
    ]
