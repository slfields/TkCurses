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

"""Shared fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from tests.support import TerminalHarness

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# uat/ is a development tool at the repository root, outside the installed
# distribution, so importing it depends on the root being on the path. pytest
# usually arranges that; saying so here means the tests do not rely on which
# import mode it was run with.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# The tests test THIS tree's library, not whichever one an editable install
# happens to point at. `pip install -e .` leaves an
# __editable__.tkcurses-0.1.0.pth aimed at the checkout it was run in, and that
# path wins in any OTHER checkout of the same repository - a git worktree, most
# of all, since src/ there is never placed on sys.path by anything.
#
# That broke the pre-push gate in CLAUDE.md, which runs the suite in a throwaway
# worktree precisely so the working copy cannot influence it: the worktree's
# tests ran against the working copy's library. Measured - DEFAULT_EVERY = 99
# patched into a worktree's own _core/textlayout.py and nowhere else, and the
# suite reported 26 passed. A commit that forgot to `git add` a new source file
# would have passed too.
#
# Inserting src/ ahead of it makes that structural rather than something to
# remember on the command line. TkCurses-6dw.
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))


@pytest.fixture(scope="session", autouse=True)
def _measure_coverage_in_child_processes():
    """Let coverage follow the harness into forked children.

    Code under test in a tty test runs in another process, so without this the
    entire terminal-facing half of the library reads as untested. coverage's
    startup hook activates when COVERAGE_PROCESS_START names a config file;
    the harness passes the environment through to its children already.
    """
    try:
        import coverage
    except ImportError:
        yield
        return
    if coverage.Coverage.current() is None:  # not running under --cov
        yield
        return
    previous = os.environ.get("COVERAGE_PROCESS_START")
    os.environ["COVERAGE_PROCESS_START"] = str(PROJECT_ROOT / "pyproject.toml")
    try:
        yield
    finally:
        if previous is None:
            del os.environ["COVERAGE_PROCESS_START"]
        else:
            os.environ["COVERAGE_PROCESS_START"] = previous


@pytest.fixture
def terminal(tmp_path):
    """A 40x12 terminal harness that cleans up its child process."""

    def _make(cols: int = 40, rows: int = 12, **kwargs) -> TerminalHarness:
        term = TerminalHarness(cols=cols, rows=rows, **kwargs)
        made.append(term)
        return term

    made: list[TerminalHarness] = []
    _make.tmp_path = tmp_path  # type: ignore[attr-defined]
    yield _make
    for term in made:
        term.close()
