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

"""Every source file says who wrote it and under what terms.

The GNU GPL asks for the notice on each file rather than only in LICENSE,
because a file travels: copied into another project, pasted into a bug
report, or vendored, it carries its terms with it or it carries nothing. A
file added later without one is the way this quietly stops being true, so it
is checked rather than trusted.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import tkcurses

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIRS = ("src", "tests", "uat")

AUTHOR = "Scott L. Fields"
COPYRIGHT = f"# Copyright (C) 2026  {AUTHOR}"
SPDX = "# SPDX-License-Identifier: GPL-3.0-only"


def tracked() -> set[Path] | None:
    """The files git actually has, or None if git cannot say.

    Asked of git rather than of the filesystem because "the project" means
    what is committed, not what happens to be sitting in a working copy. A
    scratch script a developer drops in `src/` to try the library out is not
    part of the project and does not need the notice - it is theirs. The
    check exists to catch a file added *to the project* without one, and
    such a file is by definition tracked.
    """
    found = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", *SOURCE_DIRS],
        capture_output=True,
        check=False,
    )
    if found.returncode != 0:
        return None
    return {
        ROOT / name
        for name in found.stdout.decode("utf-8").split("\0")
        if name.endswith(".py")
    }


def source_files() -> list[Path]:
    """Every Python file the project is made of."""
    known = tracked()
    return sorted(
        path
        for directory in SOURCE_DIRS
        for path in (ROOT / directory).rglob("*.py")
        if "__pycache__" not in path.parts and (known is None or path in known)
    )


def test_there_are_source_files_to_check():
    """A glob that matches nothing would make every test below vacuous."""
    assert len(source_files()) > 100


def test_an_untracked_file_is_not_the_projects_to_check():
    """The filter is the point, so it is asserted rather than assumed.

    Without this, the suite fails on a developer's own throwaway script and
    the honest fix looks like deleting their file.
    """
    known = tracked()
    if known is None:
        pytest.skip("not a git checkout")
    assert known, "git listed nothing, so the filter would hide everything"
    assert ROOT / "src" / "tkcurses" / "__init__.py" in known
    assert (ROOT / "src" / "not_a_real_file_someone_left_here.py") not in known


@pytest.mark.parametrize(
    "path", source_files(), ids=lambda path: str(path.relative_to(ROOT))
)
def test_every_source_file_carries_the_notice(path):
    header = path.read_text(encoding="utf-8").split('"""', 1)[0]
    assert COPYRIGHT in header, f"no copyright line in {path}"
    assert SPDX in header, f"no SPDX identifier in {path}"
    assert "GNU General Public License version 3" in header
    assert "WITHOUT ANY WARRANTY" in header
    assert "https://www.gnu.org/licenses/" in header


def test_the_notice_is_version_3_only_everywhere():
    """-only and -or-later are different licences, and the difference is one
    clause of boilerplate that is easy to paste in by mistake."""
    later = "any later" + " version"  # split so this file is not its own match
    for path in source_files():
        header = path.read_text(encoding="utf-8").split('"""', 1)[0]
        assert later not in header, (
            f"{path} offers a later version; the project is GPL-3.0-only"
        )


def test_the_package_reports_its_author_and_licence():
    assert tkcurses.__author__ == AUTHOR
    assert tkcurses.__license__ == "GPL-3.0-only"
    assert tkcurses.__copyright__ == f"Copyright (C) 2026 {AUTHOR}"


def test_the_short_notice_says_what_the_gpl_asks_it_to():
    """Interactive programs should show this at startup: who, no warranty,
    free to redistribute, and where to read the terms."""
    notice = tkcurses.NOTICE
    assert AUTHOR in notice
    assert tkcurses.__version__ in notice
    assert "ABSOLUTELY NO WARRANTY" in notice
    assert "redistribute" in notice
    assert "https://www.gnu.org/licenses/" in notice


def test_the_packaging_metadata_agrees_with_the_source():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'name = "{AUTHOR}"' in pyproject
    assert 'license = "GPL-3.0-only"' in pyproject


def test_the_readme_carries_the_notice():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"Copyright (C) 2026 {AUTHOR}" in readme
    assert "WITHOUT ANY WARRANTY" in readme
