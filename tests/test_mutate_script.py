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

"""tests/support/mutate.py, and the mutmut configuration it runs with."""

from __future__ import annotations

import resource
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from tests.support import mutate

ROOT = Path(__file__).parents[1]
CONFIG = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["mutmut"]


def test_the_configuration_leaves_only_mutate_for_the_script_to_set():
    assert CONFIG["only_mutate"] == []
    text = (ROOT / "pyproject.toml").read_text()
    assert text.count(mutate.ONLY_MUTATE) == 1


def test_configure_names_the_modules_and_nothing_else_changes():
    text = (ROOT / "pyproject.toml").read_text()
    made = mutate.configure(text, ["src/tkcurses/_core/cells.py"])
    config = tomllib.loads(made)["tool"]["mutmut"]
    assert config["only_mutate"] == ["src/tkcurses/_core/cells.py"]
    assert {**config, "only_mutate": []} == CONFIG


def test_configure_refuses_a_file_without_the_line():
    with pytest.raises(ValueError, match="exactly once"):
        mutate.configure("[tool.mutmut]\n", ["src/tkcurses/_core/cells.py"])


def test_everything_mutmut_is_told_to_copy_is_there():
    for path in CONFIG["also_copy"]:
        assert (ROOT / path).exists(), path


def test_every_test_file_left_out_is_there():
    """An --ignore naming a file that has gone ignores nothing, silently."""
    ignored = [
        arg.split("=", 1)[1]
        for arg in CONFIG["pytest_add_cli_args"]
        if arg.startswith("--ignore=")
    ]
    assert ignored
    for path in ignored:
        assert (ROOT / path).is_file(), path


def test_a_module_must_be_a_library_file():
    assert mutate.check_modules(["src/tkcurses/_core/cells.py"]) == [
        "src/tkcurses/_core/cells.py"
    ]
    with pytest.raises(SystemExit, match="not a module under"):
        mutate.check_modules(["tests/test_core_cells.py"])
    with pytest.raises(SystemExit, match="there is no"):
        mutate.check_modules(["src/tkcurses/_core/nothing.py"])
    with pytest.raises(SystemExit, match="not in this repository"):
        mutate.check_modules(["/"])


def test_results_are_grouped_by_status():
    listed = (
        "    tkcurses._core.cells.x_a__mutmut_1: survived\n"
        "    tkcurses._core.cells.x_b__mutmut_2: no tests\n"
        "    tkcurses._core.cells.x_a__mutmut_3: survived\n"
        "noise without a status\n"
    )
    assert mutate.results(listed) == {
        "survived": [
            "tkcurses._core.cells.x_a__mutmut_1",
            "tkcurses._core.cells.x_a__mutmut_3",
        ],
        "no tests": ["tkcurses._core.cells.x_b__mutmut_2"],
    }


def test_the_memory_cap_reaches_a_child_process():
    """What stops a mutant that removes a bound: the limit is set in the
    process mutmut starts in, and everything it forks inherits it."""
    limit = 3 << 30
    shown = subprocess.run(
        [
            sys.executable,
            "-c",
            "import resource; print(resource.getrlimit(resource.RLIMIT_AS)[0])",
        ],
        preexec_fn=lambda: mutate.cap_memory(limit),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert int(shown) == limit
    assert resource.getrlimit(resource.RLIMIT_AS)[0] != limit


def test_no_module_named_and_nothing_changed_says_so(monkeypatch, capsys):
    monkeypatch.setattr(mutate, "changed_modules", lambda base: [])
    assert mutate.main([]) == 0
    assert "no library module changed" in capsys.readouterr().out
