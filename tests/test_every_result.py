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

"""The guard that fails a green run with a collected test left unrun."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.every_result import EveryResult, missing


def test_missing_names_what_has_no_result():
    assert missing(["a", "b", "c"], ["b"]) == ["a", "c"]
    assert missing(["a"], ["a", "a"]) == []


def _report(nodeid, when, outcome):
    return SimpleNamespace(nodeid=nodeid, when=when, passed=outcome == "passed")


def _session(collectonly=False):
    lines = []
    reporter = SimpleNamespace(write_line=lambda text, **_: lines.append(text))
    plugins = SimpleNamespace(get_plugin=lambda name: reporter)
    config = SimpleNamespace(
        option=SimpleNamespace(collectonly=collectonly), pluginmanager=plugins
    )
    return SimpleNamespace(config=config, exitstatus=0), lines


def test_a_passing_run_missing_a_result_fails_and_says_which():
    plugin = EveryResult()
    plugin.pytest_xdist_node_collection_finished(None, ["t::a", "t::b", "t::c"])
    # a passed; b was skipped in setup; c never reported.
    plugin.pytest_runtest_logreport(_report("t::a", "setup", "passed"))
    plugin.pytest_runtest_logreport(_report("t::a", "call", "passed"))
    plugin.pytest_runtest_logreport(_report("t::b", "setup", "skipped"))
    session, lines = _session()
    plugin.pytest_sessionfinish(session, pytest.ExitCode.OK)
    assert session.exitstatus == pytest.ExitCode.TESTS_FAILED
    assert lines == ["1 collected test(s) reported no result:", "  t::c"]


@pytest.mark.parametrize(
    ("exitstatus", "collectonly"),
    [(pytest.ExitCode.TESTS_FAILED, False), (pytest.ExitCode.OK, True)],
)
def test_a_failed_or_collect_only_run_is_left_alone(exitstatus, collectonly):
    plugin = EveryResult()
    plugin.pytest_xdist_node_collection_finished(None, ["t::a"])
    session, lines = _session(collectonly)
    plugin.pytest_sessionfinish(session, exitstatus)
    assert session.exitstatus == 0 and lines == []


def test_a_complete_run_passes():
    plugin = EveryResult()
    plugin.pytest_xdist_node_collection_finished(None, ["t::a"])
    plugin.pytest_runtest_logreport(_report("t::a", "call", "passed"))
    session, lines = _session()
    plugin.pytest_sessionfinish(session, pytest.ExitCode.OK)
    assert session.exitstatus == 0 and lines == []


_CONFTEST = """
from tests.every_result import EveryResult


def pytest_configure(config):
    if not hasattr(config, "workerinput"):
        config.pluginmanager.register(EveryResult(), "every-result")


def pytest_runtest_protocol(item, nextitem):
    # Claim the protocol and report nothing: collected, never run.
    if item.name == "test_lost":
        return True
    return None
"""


def _turned_off(config):
    """The ``-p no:name`` options this run was given, for a child run: a
    plugin broken on this machine would break the child too."""
    args = list(config.invocation_params.args)
    found = []
    for index, arg in enumerate(args):
        following = args[index + 1] if index + 1 < len(args) else ""
        if arg == "-p" and following.startswith("no:"):
            found += ["-p", following]
        elif arg.startswith("-pno:"):
            found.append(arg)
    return found


@pytest.mark.parametrize("workers", [[], ["-n", "2"]])
def test_a_real_run_that_loses_a_test_fails(tmp_path, workers, pytestconfig):
    (tmp_path / "conftest.py").write_text(_CONFTEST)
    (tmp_path / "test_some.py").write_text(
        "def test_kept():\n    pass\n\n\ndef test_lost():\n    pass\n"
    )
    root = Path(__file__).resolve().parent.parent
    env = {**os.environ, "PYTHONPATH": str(root)}
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            *_turned_off(pytestconfig),
            *workers,
            ".",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert run.returncode == pytest.ExitCode.TESTS_FAILED, run.stdout + run.stderr
    assert "1 collected test(s) reported no result:" in run.stdout
    assert "test_some.py::test_lost" in run.stdout
