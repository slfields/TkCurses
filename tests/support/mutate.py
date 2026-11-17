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

"""Mutation-test the modules a change touched, with mutmut.

    python3 tests/support/mutate.py                 # what HEAD changed since origin/master
    python3 tests/support/mutate.py src/tkcurses/_core/cells.py
    python3 tests/support/mutate.py --base v0.4.2   # changed since a tag

Needs ``pip install -e ".[mutation]"``. TESTING.md says how to read what it
reports. This does what was learned running mutation tests by hand, so that
nobody has to remember it:

- **The commit, not the working copy.** mutmut runs in a fresh worktree of
  HEAD, outside the repository, so nothing it does touches your files and a
  half-made change is not what gets measured. Commit first.
- **Only the modules asked about are mutated.** mutmut turns each function
  into a copy per mutant; mutating everything makes ``__init__.py`` 43 MB and
  every test slower to import. ``only_mutate`` is set in the worktree's
  ``pyproject.toml`` alone.
- **A memory cap on every process.** A mutant that removes a bound can make
  one test allocate without end: by hand, once, 12.8 GB in 35 seconds before
  the kernel killed the terminal too. The limit is inherited by every test
  mutmut forks, so such a mutant fails with MemoryError instead.
- **No bytecode written**, so a stale ``.pyc`` can never stand in for a
  source file.

mutmut itself refuses to start unless the selected tests pass unmutated,
and checks that a forced mutant fails them, so a survivor is never a
broken baseline.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import resource
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "src/tkcurses/"
#: The line in pyproject.toml this replaces in the worktree's copy.
ONLY_MUTATE = "only_mutate = []"
#: A result line from ``mutmut results``: the mutant's name and its status.
RESULT = re.compile(r"^\s*(\S+): (.+?)\s*$")


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def changed_modules(base: str) -> list[str]:
    """The library's Python files that differ between ``base`` and HEAD."""
    names = git("diff", "--name-only", f"{base}...HEAD", "--", PACKAGE)
    return sorted(name for name in names.split() if name.endswith(".py"))


def check_modules(paths: list[str]) -> list[str]:
    """``paths`` as repository-relative module files, or SystemExit."""
    modules = []
    for given in paths:
        path = Path(given).resolve()
        try:
            relative = path.relative_to(ROOT).as_posix()
        except ValueError:
            sys.exit(f"mutate.py: {given} is not in this repository")
        if not relative.startswith(PACKAGE) or path.suffix != ".py":
            sys.exit(f"mutate.py: {given} is not a module under {PACKAGE}")
        if not path.is_file():
            sys.exit(f"mutate.py: there is no {given}")
        modules.append(relative)
    return sorted(set(modules))


def configure(pyproject: str, modules: list[str]) -> str:
    """``pyproject`` with ``only_mutate`` set to ``modules``."""
    if pyproject.count(ONLY_MUTATE) != 1:
        raise ValueError(f"pyproject.toml must hold {ONLY_MUTATE!r} exactly once")
    return pyproject.replace(ONLY_MUTATE, f"only_mutate = {json.dumps(modules)}")


def results(lines: str) -> dict[str, list[str]]:
    """``mutmut results`` read as each status and the mutants that have it."""
    found: dict[str, list[str]] = {}
    for line in lines.splitlines():
        match = RESULT.match(line)
        if match:
            found.setdefault(match.group(2), []).append(match.group(1))
    return found


def cap_memory(limit: int) -> None:
    """Run in the child before mutmut starts: every process it forks keeps
    the same ceiling."""
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def make_worktree(work: Path) -> None:
    """A fresh detached worktree of HEAD at ``work``, replacing one this
    script made before - and nothing else."""
    if work.exists():
        listed = git("worktree", "list", "--porcelain")
        if f"worktree {work}\n" not in listed:
            sys.exit(
                f"mutate.py: {work} exists and is not a worktree of this repository"
            )
        git("worktree", "remove", "--force", str(work))
    git("worktree", "add", "--quiet", "--detach", str(work), "HEAD")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mutation-test the library modules a change touched."
    )
    parser.add_argument("modules", nargs="*", help="module files under src/tkcurses")
    parser.add_argument(
        "--base",
        default="origin/master",
        help="with no modules named, mutate what changed since this (origin/master)",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "tkcurses-mutation",
        help="where the worktree goes; kept afterwards for mutmut show and browse",
    )
    parser.add_argument(
        "--memory",
        type=float,
        default=8.0,
        help="address-space limit per process, in GiB (8)",
    )
    args = parser.parse_args(argv)

    modules = (
        check_modules(args.modules) if args.modules else changed_modules(args.base)
    )
    if not modules:
        print(f"mutate.py: no library module changed since {args.base}; name one")
        return 0
    try:
        import mutmut  # noqa: F401
    except ImportError:
        sys.exit('mutate.py: mutmut is not installed: pip install -e ".[mutation]"')
    if git("status", "--porcelain", "--", "src", "tests"):
        print(
            "mutate.py: note: uncommitted changes under src/ or tests/ are not included"
        )

    work = args.workdir.resolve()
    make_worktree(work)
    pyproject = work / "pyproject.toml"
    pyproject.write_text(configure(pyproject.read_text(), modules))
    print("mutating " + ", ".join(modules) + f"\nin {work}", flush=True)

    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    limit = int(args.memory * (1 << 30))
    run = subprocess.run(
        [sys.executable, "-m", "mutmut", "run"],
        cwd=work,
        env=env,
        preexec_fn=lambda: cap_memory(limit),
        check=False,
    )
    if run.returncode != 0:
        print(
            f"\nmutate.py: mutmut stopped (status {run.returncode}) before testing"
            " mutants - most often a test that fails unmutated; its output is above"
        )
        return 2

    listed = subprocess.run(
        [sys.executable, "-m", "mutmut", "results"],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    found = results(listed)
    print()
    if not found:
        print("Every mutant was killed.")
    for status, names in sorted(found.items()):
        print(f"{status}: {len(names)}")
        for name in names:
            print(f"    {name}")
    print(
        f"\nRead one:  (cd {work} && {sys.executable} -m mutmut show NAME)"
        f"\nRemove:    git worktree remove --force {work}"
    )
    return 0


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        sys.exit(main())
    sys.exit(130)
