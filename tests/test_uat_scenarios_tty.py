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

"""Smoke tests for the acceptance scenarios.

The scenarios exist to be run by a person; these tests only check that each
one still starts, renders, and leaves cleanly. Without them a scenario would
quietly rot the first time an API moved, and nobody would find out until they
sat down to accept a release.
"""

from __future__ import annotations

import os
import sys

import pytest
from uat.__main__ import scenarios

from tests.conftest import PROJECT_ROOT

pytestmark = pytest.mark.tty

ESCAPE = b"\x1b"


@pytest.fixture
def uat_terminal(terminal):
    """A harness whose child process can import the uat package.

    uat/ sits at the repository root and is deliberately outside the
    installed distribution - it is a development tool, not library code - so a
    child can import it only if the root is on its path. Inheriting that from
    whichever directory pytest happened to be started in would make these
    tests pass or fail depending on where the command was typed, so the path
    is passed explicitly.
    """

    def _make(**kwargs):
        env = dict(kwargs.pop("env", {}))
        inherited = os.environ.get("PYTHONPATH", "")
        env.setdefault(
            "PYTHONPATH",
            os.pathsep.join(part for part in (str(PROJECT_ROOT), inherited) if part),
        )
        return terminal(env=env, **kwargs)

    return _make


@pytest.mark.parametrize("scenario", scenarios())
def test_a_scenario_starts_renders_and_exits_cleanly(uat_terminal, scenario):
    term = uat_terminal(cols=60, rows=20)
    term.run([sys.executable, "-m", f"uat.{scenario}"])
    # Every scenario puts its title on the first line before waiting.
    term.wait_for(lambda t: t.row(0).strip() != "", message="the title line")
    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0
    assert "Traceback" not in term.stderr


#: Rows the whole listing needs: two lines per scenario, plus the header and
#: the footer. Computed rather than guessed, because the listing grows every
#: time a scenario is added and a fixed number quietly starts scrolling the
#: top off instead of failing for a reason anyone can read.
def _listing_rows() -> int:
    return 2 * len(scenarios()) + 14


def test_the_runner_lists_every_scenario(uat_terminal):
    term = uat_terminal(cols=80, rows=_listing_rows())
    term.run([sys.executable, "-m", "uat"])
    assert term.wait_for_exit(timeout=10) == 0
    for scenario in scenarios():
        assert scenario in "\n".join(term.display)


def test_the_runner_refuses_a_scenario_that_does_not_exist(uat_terminal):
    term = uat_terminal(cols=80, rows=30)
    term.run([sys.executable, "-m", "uat", "99"])
    assert term.wait_for_exit(timeout=10) == 2


def test_a_scenario_reports_failure_through_its_exit_code(uat_terminal, tmp_path):
    """The contract that lets these be pointed at CI later."""
    term = uat_terminal(cols=60, rows=20)
    term.run_source(
        """
from uat import _support

def build(root, screen):
    raise RuntimeError("scenario is broken")

raise SystemExit(_support.run("broken", build))
""",
        workdir=tmp_path,
    )
    assert term.wait_for_exit(timeout=10) == 1
    assert "scenario is broken" in term.stderr


# The documented run-from-anywhere form. Given a path rather than -m, Python
# puts the uat directory itself on sys.path and never the repository root, so
# these would fail without the bootstrap in __main__.py - whatever the working
# directory. PYTHONSAFEPATH stops Python adding any path of its own, which
# rules out passing by luck.


def test_the_runner_works_when_given_its_path(terminal):
    term = terminal(cols=80, rows=_listing_rows(), env={"PYTHONSAFEPATH": "1"})
    term.run([sys.executable, str(PROJECT_ROOT / "uat")])
    assert term.wait_for_exit(timeout=10) == 0
    assert "Acceptance scenarios" in "\n".join(term.display)


def test_a_scenario_runs_when_the_runner_is_given_its_path(terminal):
    term = terminal(cols=60, rows=20, env={"PYTHONSAFEPATH": "1"})
    term.run([sys.executable, str(PROJECT_ROOT / "uat"), "2"])
    term.wait_for(lambda t: t.row(0).strip() != "", message="the title line")
    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0
    assert "Traceback" not in term.stderr
