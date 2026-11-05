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


"""Install from git, commit, ``pip install -U``: does the new code arrive?

It did not, for 330 commits. The version was written by hand as 0.1.0 and
never moved, pip compares versions before it replaces anything, and so every
upgrade from GitHub reported nothing and left the old code in place -
TkCurses-2q6o.1, measured with a venv holding e95dc81 and an upgrade to
d281a08 that installed nothing.

This is that, end to end, in a throwaway venv against a throwaway clone of
this repository: the commit it installs second adds a line the first did not
have, and the line has to be in the installed package afterwards. Then it
runs a program from the installed copy, which is the other half of "the
install works".

Not a pytest test, because pip builds in isolation and downloads setuptools
to do it - a network fetch and most of a minute, which the suite's five CI
interpreters would each pay. CI runs it once, in the build job::

    python tests/support/check_upgrade.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

from packaging.version import Version

ROOT = Path(__file__).resolve().parents[2]

#: Appended by the second commit, and looked for in the installed copy.
PROBE = "_UPGRADE_PROBE = True\n"

PROGRAM = """
import tkcurses
from tkcurses import ttk, messagebox, filedialog, scrolledtext, simpledialog
assert tkcurses.Entry and tkcurses.Text and ttk.Treeview
print(tkcurses.__version__)
"""


def run(*args: str | Path, cwd: Path | None = None) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "check",
        "GIT_AUTHOR_EMAIL": "check@example.invalid",
        "GIT_COMMITTER_NAME": "check",
        "GIT_COMMITTER_EMAIL": "check@example.invalid",
        # The repository's own hooks are bd's, and have no business in a clone.
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.hooksPath",
        "GIT_CONFIG_VALUE_0": os.devnull,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    }
    done = subprocess.run(
        [str(a) for a in args], cwd=cwd, env=env, capture_output=True, text=True
    )
    if done.returncode:
        sys.exit(f"failed: {' '.join(map(str, args))}\n{done.stdout}{done.stderr}")
    return done.stdout.strip()


def main() -> int:
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch)
        repo = work / "repo"
        head = run("git", "rev-parse", "HEAD", cwd=ROOT)
        run("git", "clone", "--quiet", "--no-checkout", ROOT, repo)
        run("git", "checkout", "--quiet", "-B", "probe", head, cwd=repo)

        venv.create(work / "venv", with_pip=True)
        python = work / "venv" / "bin" / "python"
        url = f"tkcurses @ git+file://{repo}@probe"

        run(python, "-m", "pip", "install", "--quiet", url)
        first = run(python, "-I", "-c", PROGRAM, cwd=work)

        init = repo / "src" / "tkcurses" / "__init__.py"
        init.write_text(init.read_text(encoding="utf-8") + PROBE, encoding="utf-8")
        run("git", "commit", "--quiet", "-am", "probe", cwd=repo)

        run(python, "-m", "pip", "install", "--quiet", "--upgrade", url)
        second = run(python, "-I", "-c", PROGRAM, cwd=work)
        installed = Path(
            run(
                python,
                "-I",
                "-c",
                "import tkcurses; print(tkcurses.__file__)",
                cwd=work,
            )
        )
        arrived = PROBE in installed.read_text(encoding="utf-8")

    print(f"first install:  {first}")
    print(f"after upgrade:  {second}")
    if not arrived:
        print("FAIL: the upgrade left the first commit's code installed")
        return 1
    if not Version(second) > Version(first):
        print("FAIL: the second commit's version is not above the first's")
        return 1
    print("ok: the upgrade installed the new commit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
