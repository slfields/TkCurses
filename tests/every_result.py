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

"""Fail a run that passes but leaves a collected test without a result.

Four times a full ``pytest -n 4`` in a working copy reported a few fewer
results than it collected - no failure, no error, the summary green - and
the short runs left no record of which tests were missing. A test that
silently does not run is a test that silently passes, so a run it happens
to must not pass: this plugin names the missing tests and fails it.

It counts what the controller sees. Under xdist the workers report their
collected ids through ``pytest_xdist_node_collection_finished`` and every
result through ``pytest_runtest_logreport``; without xdist the session's
own items stand in for the first. Runs that already failed, stopped early
or only collected are left alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


def missing(collected: Iterable[str], reported: Iterable[str]) -> list[str]:
    """The collected test ids with no result, in a stable order."""
    return sorted(set(collected) - set(reported))


class EveryResult:
    """The plugin: register one per session, in the controller."""

    def __init__(self) -> None:
        self.collected: set[str] = set()
        self.reported: set[str] = set()

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        # Without xdist; under it the controller has no items of its own.
        self.collected.update(item.nodeid for item in session.items)

    @pytest.hookimpl(optionalhook=True)
    def pytest_xdist_node_collection_finished(
        self, node: Any, ids: Sequence[str]
    ) -> None:
        self.collected.update(ids)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        # A result: the call's outcome, or a setup that skipped or failed.
        if report.when == "call" or not report.passed:
            self.reported.add(report.nodeid)

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        if exitstatus != pytest.ExitCode.OK or session.config.option.collectonly:
            return
        lost = missing(self.collected, self.reported)
        if not lost:
            return
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(
                f"{len(lost)} collected test(s) reported no result:", red=True
            )
            for nodeid in lost:
                reporter.write_line(f"  {nodeid}", red=True)
