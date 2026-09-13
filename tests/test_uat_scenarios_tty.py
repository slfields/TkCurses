"""Smoke tests for the acceptance scenarios.

The scenarios exist to be run by a person; these tests only check that each
one still starts, renders, and leaves cleanly. Without them a scenario would
quietly rot the first time an API moved, and nobody would find out until they
sat down to accept a release.
"""

from __future__ import annotations

import sys

import pytest
from uat.__main__ import scenarios

from tests.conftest import PROJECT_ROOT

pytestmark = pytest.mark.tty

ESCAPE = b"\x1b"


@pytest.mark.parametrize("scenario", scenarios())
def test_a_scenario_starts_renders_and_exits_cleanly(terminal, scenario):
    term = terminal(cols=60, rows=20)
    term.run([sys.executable, "-m", f"uat.{scenario}"])
    # Every scenario puts its title on the first line before waiting.
    term.wait_for(lambda t: t.row(0).strip() != "", message="the title line")
    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0
    assert "Traceback" not in term.stderr


def test_the_runner_lists_every_scenario(terminal):
    term = terminal(cols=80, rows=30)
    term.run([sys.executable, "-m", "uat"])
    assert term.wait_for_exit(timeout=10) == 0
    for scenario in scenarios():
        assert scenario in "\n".join(term.display)


def test_the_runner_refuses_a_scenario_that_does_not_exist(terminal):
    term = terminal(cols=80, rows=30)
    term.run([sys.executable, "-m", "uat", "99"])
    assert term.wait_for_exit(timeout=10) == 2


def test_a_scenario_reports_failure_through_its_exit_code(terminal, tmp_path):
    """The contract that lets these be pointed at CI later."""
    term = terminal(cols=60, rows=20)
    term.run_source(
        f"""
import sys
# run_source runs the script from tmp_path, so the repo is not on the path.
sys.path.insert(0, {str(PROJECT_ROOT)!r})
from uat import _support

def build(root, screen):
    raise RuntimeError("scenario is broken")

raise SystemExit(_support.run("broken", build))
""",
        workdir=tmp_path,
    )
    assert term.wait_for_exit(timeout=10) == 1
    assert "scenario is broken" in term.stderr
