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

"""The suite exercises the library beside it, not one installed elsewhere.

``pip install -e .`` puts the checkout it was run in onto ``sys.path``, and that
entry is there for every *other* checkout of the same repository too. A git
worktree has no entry of its own, so without help its tests import the original
checkout's library - and the pre-push gate in CLAUDE.md, which exists so that
the working copy cannot influence a verification, was verifying the working
copy. A commit that forgot to ``git add`` a new source file would have passed.

``tests/conftest.py`` puts ``<root>/src`` first to stop that. TkCurses-6dw.

**Why this is a subprocess in a worktree and not an assertion.** The obvious
test - that ``tkcurses.__file__`` sits under this root - passes whether or not
the fix is present, because in the only checkout CI has, the installed path and
this root are the same directory. Measured: ``src`` is on ``sys.path`` without
the conftest line at all. An assertion like that would have been a test that
cannot fail, which is worth less than no test, because it looks like cover.

The fault only exists where two checkouts do, so the test makes the second one.

**It checks HEAD, not the working copy**, because that is what ``git worktree
add`` gives it. Delete the line from ``conftest.py`` and run the suite without
committing and this test still passes - which caught me out while checking the
test itself was worth having. It fails the moment the deletion is committed,
which is before anything is pushed or reviewed, so it guards what it needs to;
but do not read a pass here as "my uncommitted change to the import setup is
fine".
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Patched in the worktree to something no test would accept. A module-level
#: constant with one test asserting its value is the cheapest sabotage that a
#: real run notices: no behaviour to simulate, and the failure names itself.
SABOTAGE = (
    Path("src/tkcurses/_core/textlayout.py"),
    "DEFAULT_EVERY = 8",
    "DEFAULT_EVERY = 99",
)
#: Run in the worktree. One file, so the check costs a second rather than five
#: minutes, and it is the file whose test asserts the constant above.
WITNESS = "tests/test_core_textlayout.py"


def _git(*args: str, cwd: Path = PROJECT_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )


@pytest.fixture
def sabotaged_worktree(tmp_path: Path):
    """A second checkout of HEAD whose own source has been altered."""
    if _git("rev-parse", "--git-dir").returncode != 0:
        pytest.skip("not a git checkout")
    worktree = tmp_path / "second-checkout"
    # Without the developer's hooks: bd's post-checkout hook would import
    # HEAD's tracker export into the live issue database, and under bd 1.0.4
    # that rolled back a claim mid-run. TkCurses-enu.
    made = _git(
        "-c",
        "core.hooksPath=/dev/null",
        "worktree",
        "add",
        "-q",
        "--detach",
        str(worktree),
        "HEAD",
    )
    if made.returncode != 0:
        pytest.skip(f"could not add a worktree: {made.stderr.strip()}")
    try:
        path, before, after = SABOTAGE
        target = worktree / path
        source = target.read_text(encoding="utf-8")
        # Asserted rather than assumed: if the constant is renamed or moved,
        # this says so instead of quietly patching nothing and then reporting
        # that the suite failed to notice a change that was never made.
        assert before in source, (
            f"{path} no longer contains {before!r}, so this test is sabotaging "
            "nothing. Point SABOTAGE at another module-level constant that one "
            "test asserts the value of."
        )
        target.write_text(source.replace(before, after, 1), encoding="utf-8")
        yield worktree
    finally:
        _git("worktree", "remove", "--force", str(worktree))
        _git("worktree", "prune")


def test_a_second_checkout_runs_its_own_source(sabotaged_worktree: Path):
    """A worktree's tests see a change made only in that worktree."""
    env = {
        key: value
        for key, value in os.environ.items()
        # Both would decide the outcome instead of the code under test:
        # PYTHONPATH could supply a different src, and the inherited coverage
        # settings would have the child tracing into this run's data files.
        if key not in ("PYTHONPATH", "COVERAGE_PROCESS_START", "COV_CORE_SOURCE")
    }
    ran = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:randomly", WITNESS],
        cwd=sabotaged_worktree,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert ran.returncode != 0, (
        "a worktree's test run did not notice its own source being changed, so "
        "it was importing the library from somewhere else - the pre-push gate "
        "in CLAUDE.md is verifying the working copy rather than the commit.\n"
        f"--- stdout ---\n{ran.stdout}\n--- stderr ---\n{ran.stderr}"
    )
