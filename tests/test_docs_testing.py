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

"""TESTING.md is true of the tree it describes.

A map of the suite goes wrong silently: a module renamed, a rule set
added, a property-based test written in a file the map does not name.
These hold the parts of it that can be checked mechanically.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PAGE = (ROOT / "TESTING.md").read_text()
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())

#: A path in backquotes, under one of the directories the page talks about.
PATH = re.compile(r"`((?:tests|src|docs|uat|examples|requirements|\.github)/[^`\s]*)`")
#: A Markdown link to a file in the repository.
LINK = re.compile(r"\]\(((?!https?:|#)[^)\s]+)\)")


def section(title: str) -> str:
    """The page's text from the heading ``## title`` to the next one."""
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", PAGE, re.M | re.S)
    assert match, f"TESTING.md has no section {title!r}"
    return match.group(1)


def named_paths() -> list[str]:
    return sorted(set(PATH.findall(PAGE)) | set(LINK.findall(PAGE)))


@pytest.mark.parametrize("path", named_paths())
def test_every_path_the_page_names_exists(path):
    """A glob (``tests/test_core_*.py``) must match something."""
    if any(character in path for character in "*?["):
        assert list(ROOT.glob(path)), f"TESTING.md names {path}, which matches nothing"
    else:
        assert (ROOT / path).exists(), f"TESTING.md names {path}, which is not there"


def test_the_page_names_some_paths():
    """So the test above cannot pass by finding nothing to check."""
    assert len(named_paths()) > 50


def test_the_ruff_table_lists_exactly_the_rules_selected():
    table = section("Static checks").split("| Rules |", 1)[1].split("\n\n", 1)[0]
    listed = set(re.findall(r"^\| ([^|]+) \|", table, re.M)) - {"---"}
    codes = {code.strip("` ") for row in listed for code in row.split(",")}
    assert codes == set(PYPROJECT["tool"]["ruff"]["lint"]["select"])


def test_the_property_table_names_every_module_that_uses_hypothesis():
    """A new property-based test is added to the map, and a removed one
    taken out of it."""
    uses = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "tests").rglob("test_*.py")
        if re.search(r"^\s*(from|import) hypothesis", path.read_text(), re.M)
    }
    table = section("Property-based testing and fuzzing")
    assert set(PATH.findall(table)) == uses


def test_the_markers_are_the_ones_declared():
    declared = {
        marker.split(":")[0]
        for marker in PYPROJECT["tool"]["pytest"]["ini_options"]["markers"]
    }
    described = set(re.findall(r"^- `(\w+)` marks", section("Running the tests"), re.M))
    assert described == declared


def test_mypy_is_said_to_check_what_it_checks():
    checked = PYPROJECT["tool"]["mypy"]["files"]
    assert re.search(
        r"\(`mypy`\) checks " + " and ".join(f"`{path}`" for path in checked),
        section("Static checks"),
    )
