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


"""What the release workflow decides, checked without pushing a tag.

A pushed tag is a published release, so .github/workflows/release.yml keeps
its decisions in .github/scripts/release.py and these test them. TkCurses-2q6o.5.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".github" / "scripts" / "release.py"
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"

_spec = importlib.util.spec_from_file_location("release_script", SCRIPT)
assert _spec is not None and _spec.loader is not None
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)


def dist(tmp_path: Path, *names: str) -> Path:
    for name in names:
        (tmp_path / name).write_bytes(b"")
    return tmp_path


# ------------------------------------------------------------------ check


def test_distributions_built_at_the_tag_pass(tmp_path):
    built = dist(
        tmp_path, "tkcurses-0.3.0rc1.tar.gz", "tkcurses-0.3.0rc1-py3-none-any.whl"
    )
    assert release.check("v0.3.0rc1", built) == []


def test_a_build_past_the_tag_is_refused(tmp_path):
    """What setuptools-scm builds when the tag is not on the built commit."""
    built = dist(
        tmp_path,
        "tkcurses-0.3.0rc2.dev1+g8efce66.tar.gz",
        "tkcurses-0.3.0rc2.dev1+g8efce66-py3-none-any.whl",
    )
    problems = release.check("v0.3.0rc1", built)
    assert len(problems) == 2
    assert "the tag says 0.3.0rc1" in problems[0]


def test_a_missing_wheel_is_refused(tmp_path):
    built = dist(tmp_path, "tkcurses-0.3.0rc1.tar.gz")
    assert release.check("v0.3.0rc1", built)


@pytest.mark.parametrize(
    "tag", ["0.3.0rc1", "r0.3.0rc1", "v0.3.0rc1.dev2", "v0.3+local", "vnext"]
)
def test_a_tag_that_is_not_a_release_is_refused(tag):
    with pytest.raises(ValueError):
        release.tag_version(tag)


# ------------------------------------------------------------- prerelease


@pytest.mark.parametrize(
    ("tag", "expected"),
    [("v0.3.0rc1", True), ("v0.3.0b2", True), ("v1.0.0a1", True), ("v0.3.0", False)],
)
def test_an_rc_alpha_or_beta_is_a_prerelease(tag, expected):
    assert release.is_prerelease(tag) is expected


# ------------------------------------------------------------------ notes

CHANGELOG = """\
# Changelog

## [Unreleased]

- not yet

## [0.3.0rc1] - 2026-11-20

### Added
- Everything.

## [0.2.0] - 2026-01-18

- Phase 2.

[0.3.0rc1]: https://github.com/slfields/TkCurses/compare/v0.2.0...v0.3.0rc1
"""


def test_the_notes_are_the_tags_section(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    assert release.notes("v0.3.0rc1", changelog) == "### Added\n- Everything."


def test_the_last_section_stops_before_the_link_references(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    assert release.notes("v0.2.0", changelog) == "- Phase 2."


def test_no_section_and_no_changelog_give_no_notes(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    assert release.notes("v0.4.0", changelog) == ""
    assert release.notes("v0.3.0rc1", tmp_path / "missing.md") == ""


def test_a_version_is_not_matched_by_its_prefix(tmp_path):
    """0.3.0 must not take 0.3.0rc1's section."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    assert release.notes("v0.3.0", changelog) == ""


# --------------------------------------------------------------- workflow


def _jobs(text: str) -> dict[str, str]:
    """Each job's block of a workflow, by its id: enough structure to ask
    about without a YAML parser, which the test environment does not have."""
    body = text[text.index("\njobs:\n") :]
    starts = [
        (match.group(1), match.start())
        for match in re.finditer(r"^  ([A-Za-z_-]+):\n", body, re.MULTILINE)
    ]
    return {
        name: body[start : (starts[i + 1][1] if i + 1 < len(starts) else len(body))]
        for i, (name, start) in enumerate(starts)
    }


def test_the_workflow_releases_only_from_a_tag_push():
    """A rehearsal from the Actions tab builds and checks and publishes
    nothing; the release and the version check are the push's alone."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'tags: ["v*"]' in text
    publish = _jobs(text)["publish"]
    assert "if: github.event_name == 'push'" in publish.split("steps:")[0]
    assert "- name: Create the GitHub release" in publish
    assert "needs: ci" in text
    assert "pypi" not in text.lower().replace("not pypi", "")


def test_only_the_publishing_job_can_write_and_it_installs_nothing():
    """Third-party code - build backends, Sphinx - runs where the token is
    read-only; the job that can write only downloads, checks, attests and
    uploads. Security review TkCurses-tcbj.7."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "\npermissions:\n  contents: read\n" in text
    jobs = _jobs(text)
    writers = [name for name, block in jobs.items() if "contents: write" in block]
    assert writers == ["publish"]
    publish = jobs["publish"]
    for forbidden in (
        "pip install",
        "python -m",
        "actions/checkout",
        "actions/setup-python",
    ):
        assert forbidden not in publish, forbidden
    assert "sha256sum --strict -c" in publish
    assert "actions/attest-build-provenance@" in publish
    assert "SHA256SUMS" in publish


def test_a_tag_off_master_is_refused_before_anything_is_built():
    build = _jobs(WORKFLOW.read_text(encoding="utf-8"))["build"]
    check = build.index("git merge-base --is-ancestor")
    assert check < build.index("python -m build")


WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_every_action_is_pinned_to_a_commit(workflow):
    """A tag can be moved to other code; a commit cannot. TkCurses-tcbj.9."""
    for line in workflow.read_text(encoding="utf-8").splitlines():
        match = re.search(r"uses:\s*(\S+)", line)
        if match and not match.group(1).startswith("./"):
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", match.group(1)), line


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_no_checkout_keeps_its_credentials(workflow):
    text = workflow.read_text(encoding="utf-8")
    assert text.count("actions/checkout@") == text.count("persist-credentials: false")


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_every_workflow_reads_only_unless_a_job_says_otherwise(workflow):
    """TkCurses-tcbj.10: ci.yml had no permissions of its own."""
    assert "\npermissions:\n  contents: read\n" in workflow.read_text(encoding="utf-8")


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_everything_installed_comes_from_a_hashed_lock(workflow):
    """TkCurses-tcbj.8. The project itself is installed with no dependencies
    and no build isolation, so nothing is fetched that the lock did not name;
    the smoke install of the built wheel is the one exception, and it has no
    dependencies to fetch."""
    for line in workflow.read_text(encoding="utf-8").splitlines():
        if "pip install" not in line or line.lstrip().startswith("#"):
            continue
        assert (
            "--require-hashes -r requirements/" in line
            or "--no-deps --no-build-isolation" in line
            or "dist/*.whl" in line
        ), line


def test_ci_can_be_called_by_the_release():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "\n  workflow_call:\n" in ci


def test_publishing_waits_for_the_release_environment():
    """Its required reviewer approves each release before the write token
    is handed out. Security review TkCurses-tcbj.11."""
    publish = _jobs(WORKFLOW.read_text(encoding="utf-8"))["publish"]
    assert "\n    environment: release\n" in publish.split("steps:")[0]
    for name, job in _jobs(WORKFLOW.read_text(encoding="utf-8")).items():
        if name != "publish":
            assert "environment:" not in job, name
