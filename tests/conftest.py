"""Shared fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.support import TerminalHarness

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
