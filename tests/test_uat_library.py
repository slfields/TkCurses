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

"""The acceptance scenarios run this checkout's library."""

from __future__ import annotations

import subprocess
import sys

import pytest

from tests.conftest import PROJECT_ROOT

PROBE = "import tkcurses; print(tkcurses.__file__)"


@pytest.mark.parametrize(
    "start",
    [
        ["-c", f"import uat; {PROBE}"],
        ["-c", f"import uat.scenario_52_treemap; {PROBE}"],
    ],
    ids=["the package", "a scenario"],
)
def test_a_scenario_imports_this_checkouts_library(tmp_path, start):
    """Even with another tkcurses earlier on the path, as an installed one
    is: a pip install of an older release made scenario 52 fail to import
    tkcurses.treemap, and every other scenario test the installed copy."""
    decoy = tmp_path / "tkcurses"
    decoy.mkdir()
    (decoy / "__init__.py").write_text("")
    done = subprocess.run(
        [sys.executable, *start],
        cwd=PROJECT_ROOT,
        env={"PYTHONPATH": f"{tmp_path}:{PROJECT_ROOT}", "TERM": "dumb"},
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout.strip() == str(PROJECT_ROOT / "src" / "tkcurses" / "__init__.py")
