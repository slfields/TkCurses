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


"""Whether .github/workflows/ci.yml has code to check: ``code=true`` or
``code=false``, for ``$GITHUB_OUTPUT``.

The workflow runs on every pull request, so that the checks the ``master``
ruleset requires always report; a change to documentation alone then skips
the code jobs, which GitHub counts as passing. It used ``paths-ignore``
before, and a required check from a workflow that never started would have
kept a documentation pull request waiting for ever.

Read from the environment, never from the workflow's text: ``EVENT`` is the
event's name, ``REF`` the ref, ``BASE`` and ``HEAD`` the commits to compare.
Anything it cannot compare - a tag, a release's call, a first push - is
code, so the doubt runs everything.
"""

from __future__ import annotations

import os
import subprocess
import sys
from fnmatch import fnmatchcase

#: Paths that are not code: what ci.yml's paths-ignore named.
NOT_CODE = (
    "docs/*",
    "*.md",
    ".github/workflows/docs.yml",
    ".github/workflows/docs-links.yml",
)

#: What git reports as the commit before a branch's first push.
NO_COMMIT = "0" * 40


def is_code(path: str) -> bool:
    """True unless ``path`` is documentation."""
    return not any(fnmatchcase(path, pattern) for pattern in NOT_CODE)


def decide(
    event: str, ref: str, base: str, head: str, changed: list[str] | None
) -> bool:
    """Whether to run the code jobs. ``changed`` is None when no comparison
    could be made."""
    if event not in ("pull_request", "push") or not ref.startswith(
        ("refs/heads/", "refs/pull/")
    ):
        return True
    if not base or base == NO_COMMIT or not head or changed is None:
        return True
    return any(is_code(path) for path in changed)


def changed_paths(base: str, head: str) -> list[str] | None:
    """The paths that differ between two commits, or None if git cannot say."""
    try:
        done = subprocess.run(
            ["git", "diff", "--name-only", base, head, "--"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return [line for line in done.stdout.splitlines() if line]


def main() -> int:
    event = os.environ.get("EVENT", "")
    ref = os.environ.get("REF", "")
    base = os.environ.get("BASE", "")
    head = os.environ.get("HEAD", "")
    comparable = base and base != NO_COMMIT and head
    changed = changed_paths(base, head) if comparable else None
    code = decide(event, ref, base, head, changed)
    print(f"code={'true' if code else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
