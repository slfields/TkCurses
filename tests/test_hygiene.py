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

"""The repository holds the project and nothing else.

Each maintainer's tooling - the issue tracker's workspace, AI-assistant
instructions and settings, the code graph - lives beside the checkout and is
never committed. Committed, it is published with the source, and because the
source distribution is built from every tracked file, it ships inside each
release's sdist as well: the 0.3.0 sdist carried all of it. ``.gitignore``
keeps it out of a commit; this keeps it out of one made with ``git add -f``.
"""

from __future__ import annotations

import subprocess

import pytest

from tests.conftest import PROJECT_ROOT

#: Paths that are a maintainer's own and never the project's. A directory
#: covers everything under it.
NEVER_TRACKED = (
    ".beads/",
    ".claude/",
    "CLAUDE.md",
    "AGENTS.md",
    ".mcp.json",
    "graphify-out/",
    "tests/support/check_graph.py",
    "tests/test_check_graph.py",
)


def _tracked() -> list[str]:
    try:
        listed = subprocess.run(
            ["git", "ls-files"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return listed.stdout.splitlines()


def _forbidden(path: str) -> bool:
    return any(
        path == entry or (entry.endswith("/") and path.startswith(entry))
        for entry in NEVER_TRACKED
    )


def test_no_maintainer_tooling_is_tracked():
    assert [path for path in _tracked() if _forbidden(path)] == []


def test_the_check_recognises_what_it_forbids():
    """So that an empty answer above means nothing is tracked, not that the
    matching is wrong."""
    assert _forbidden(".beads/issues.jsonl")
    assert _forbidden(".claude/skills/dev-cycle/SKILL.md")
    assert _forbidden("CLAUDE.md")
    assert not _forbidden("docs/CLAUDE.md.txt")
    assert not _forbidden("src/tkcurses/__init__.py")


def test_gitignore_names_every_one():
    """Ignored as well as checked, so no clone adds them by accident."""
    ignored = (PROJECT_ROOT / ".gitignore").read_text().splitlines()
    assert [entry for entry in NEVER_TRACKED if entry not in ignored] == []
