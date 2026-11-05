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

"""Packaging smoke tests: the distribution is importable and correctly typed."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from packaging.version import Version

import tkcurses

ROOT = Path(__file__).resolve().parent.parent

#: The last release, from before the rebuild. Every build since must sort
#: above it, or pip treats that release as the newer code.
LAST_RELEASE = Version("0.2.0")


def test_version_is_exposed():
    """Whatever the build said, and above the last release.

    It was written by hand as 0.1.0 and never changed, so ``pip install -U``
    from GitHub never replaced anything - and v0.2.0, the pre-rebuild code,
    sorted above all of it. TkCurses-2q6o.1. A clone too shallow to see the
    tag fails here too: setuptools-scm then has nothing to count from.
    """
    assert Version(tkcurses.__version__) > LAST_RELEASE


def test_installed_metadata_matches_module_version():
    assert importlib.metadata.version("tkcurses") == tkcurses.__version__


def test_ships_py_typed_marker():
    """PEP 561: type hints are only honoured downstream if py.typed is shipped."""
    spec = importlib.util.find_spec("tkcurses")
    assert spec is not None and spec.origin is not None
    assert (Path(spec.origin).parent / "py.typed").is_file()


def test_licensed_gpl3():
    meta = importlib.metadata.metadata("tkcurses")
    license_field = meta.get("License-Expression") or meta.get("License", "")
    assert "GPL-3.0" in license_field


# ------------------------------------------------- the version is git's


def git(cwd: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        # A clone in a temporary directory has no business running the
        # repository's own hooks, and bd's would import the tracker.
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.hooksPath",
        "GIT_CONFIG_VALUE_0": os.devnull,
    }
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()


def scm_version(cwd: Path) -> Version:
    """What a build of ``cwd`` would be versioned as."""
    out = subprocess.run(
        [sys.executable, "-m", "setuptools_scm"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return Version(out.strip().splitlines()[-1])


@pytest.fixture
def clone(tmp_path):
    """This repository at this commit, to commit and tag in freely."""
    head = git(ROOT, "rev-parse", "HEAD")
    target = tmp_path / "repo"
    git(tmp_path, "clone", "--quiet", "--no-checkout", str(ROOT), str(target))
    git(target, "checkout", "--quiet", head)
    return target


def test_every_commit_raises_the_version(clone):
    """The property pip needs: a newer commit is a newer version."""
    before = scm_version(clone)
    git(clone, "commit", "--quiet", "--allow-empty", "-m", "another")
    after = scm_version(clone)
    assert after > before > LAST_RELEASE


def test_a_tagged_commit_is_its_tag(clone):
    """A release is the tag alone - no .dev, no local part - which is what
    PyPI requires and what a person pinning to it expects to see."""
    git(clone, "tag", "v9.8.7rc1")
    assert str(scm_version(clone)) == "9.8.7rc1"


def test_a_github_archive_knows_its_version(clone, tmp_path):
    """A "Download ZIP" or ``pip install .../archive/master.tar.gz`` has no
    .git to ask. git archive fills .git_archival.txt in instead, as GitHub
    does, and setuptools-scm reads it - without that the build fails. The
    public part is compared: git archive abbreviates the hash in the local
    part to seven characters, a clone to however many it needs."""
    unpacked = tmp_path / "unpacked"
    unpacked.mkdir()
    archive = tmp_path / "repo.tar"
    git(clone, "archive", "--format=tar", "-o", str(archive), "HEAD")
    subprocess.run(["tar", "-xf", str(archive), "-C", str(unpacked)], check=True)
    assert scm_version(unpacked).public == scm_version(clone).public
