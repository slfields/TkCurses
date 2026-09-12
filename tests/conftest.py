"""Shared fixtures."""

from __future__ import annotations

import pytest

from tests.support import TerminalHarness


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
