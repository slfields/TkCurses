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

"""Which pull requests run the code checks: .github/scripts/code_changed.py,
and ci.yml's use of it.

The master ruleset requires ci.yml's "CI passed", so the workflow has to
report on every pull request, documentation alone included - where it once
did not start at all. TkCurses-tcbj.12.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".github" / "scripts" / "code_changed.py"
CI = ROOT / ".github" / "workflows" / "ci.yml"

_spec = importlib.util.spec_from_file_location("code_changed", SCRIPT)
assert _spec is not None and _spec.loader is not None
changes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(changes)

PR = ("pull_request", "refs/pull/7/merge", "a" * 40, "b" * 40)


@pytest.mark.parametrize(
    "path",
    [
        "docs/index.md",
        "docs/reference/x/y.py",
        "README.md",
        "src/x/NOTES.md",
        ".github/workflows/docs.yml",
        ".github/workflows/docs-links.yml",
    ],
)
def test_documentation_is_not_code(path):
    assert not changes.is_code(path)


@pytest.mark.parametrize(
    "path",
    [
        "src/tkcurses/__init__.py",
        "tests/test_x.py",
        "pyproject.toml",
        ".github/workflows/ci.yml",
        "requirements/dev.txt",
        "docsy.py",
    ],
)
def test_everything_else_is(path):
    assert changes.is_code(path)


def test_a_pull_request_of_documentation_alone_skips_the_code_jobs():
    assert changes.decide(*PR, ["docs/a.md", "CHANGELOG.md"]) is False


def test_one_code_file_runs_them():
    assert changes.decide(*PR, ["docs/a.md", "src/tkcurses/curses.py"]) is True


@pytest.mark.parametrize(
    ("event", "ref", "base", "changed"),
    [
        # The release calls ci.yml from a tag's push: always everything.
        ("push", "refs/tags/v0.4.2", "0" * 40, ["docs/a.md"]),
        ("push", "refs/tags/v0.4.2", "a" * 40, ["docs/a.md"]),
        ("workflow_dispatch", "refs/heads/master", "", ["docs/a.md"]),
        # A first push has nothing before it to compare with.
        ("push", "refs/heads/master", "0" * 40, ["docs/a.md"]),
        # git could not compare.
        ("pull_request", "refs/pull/7/merge", "a" * 40, None),
    ],
)
def test_anything_it_cannot_compare_runs_everything(event, ref, base, changed):
    assert changes.decide(event, ref, base, "b" * 40, changed) is True


def test_it_reads_the_difference_from_git(tmp_path, monkeypatch):
    def git(*argv):
        return subprocess.run(
            ["git", "-C", str(tmp_path), *argv],
            capture_output=True,
            text=True,
            check=True,
            env={
                "GIT_AUTHOR_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@example.invalid",
                "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@example.invalid",
                "HOME": str(tmp_path),
                "PATH": "/usr/bin:/bin",
            },
        ).stdout.strip()

    git("init", "-q")
    (tmp_path / "a.py").write_text("1")
    git("add", ".")
    git("commit", "-qm", "one")
    base = git("rev-parse", "HEAD")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "b.md").write_text("2")
    git("add", ".")
    git("commit", "-qm", "two")
    head = git("rev-parse", "HEAD")
    monkeypatch.chdir(tmp_path)
    assert changes.changed_paths(base, head) == ["docs/b.md"]
    assert changes.changed_paths("f" * 40, head) is None


# ------------------------------------------------------------------ ci.yml


def _jobs() -> dict[str, str]:
    """Each job's block of ci.yml, by its id: read as text, as the release
    workflow's tests read theirs, since the test environment has no YAML
    parser."""
    text = CI.read_text(encoding="utf-8")
    body = text[text.index("\njobs:\n") :]
    starts = [
        (match.group(1), match.start())
        for match in re.finditer(r"^  ([A-Za-z_-]+):\n", body, re.MULTILINE)
    ]
    return {
        name: body[start : (starts[i + 1][1] if i + 1 < len(starts) else len(body))]
        for i, (name, start) in enumerate(starts)
    }


def test_ci_runs_on_every_pull_request():
    """A filter here would leave the required check unreported."""
    text = CI.read_text(encoding="utf-8")
    triggers = text[: text.index("\npermissions:")]
    assert "\n  pull_request:\n" in triggers
    assert "paths-ignore:" not in triggers and "\n    paths:" not in triggers


def test_every_code_job_waits_on_the_decision():
    jobs = _jobs()
    assert set(jobs) >= {"changes", "lint", "test", "build", "security", "passed"}
    for name, job in jobs.items():
        if name in ("changes", "passed"):
            continue
        assert "\n    needs: changes\n" in job, name
        assert "\n    if: needs.changes.outputs.code == 'true'\n" in job, name


def test_the_gate_hears_from_every_job_and_always_runs():
    jobs = _jobs()
    gate = jobs["passed"]
    assert "\n    name: CI passed\n" in gate
    assert "\n    if: always()\n" in gate
    needs = re.search(r"\n    needs: \[(.*?)\]\n", gate)
    assert needs is not None
    assert sorted(n.strip() for n in needs.group(1).split(",")) == sorted(
        set(jobs) - {"passed"}
    )


def test_the_decision_takes_the_events_values_from_the_environment():
    run = re.search(r"\n        run: (.*)\n", _jobs()["changes"])
    assert run is not None
    assert "${{" not in run.group(1)
