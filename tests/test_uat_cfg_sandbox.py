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

"""Smoke tests for the ``tkcurses-cfg`` acceptance sandbox.

A person runs the checklist in docs/UAT_CFG.md; these only check that the
sandbox it starts from still works - its first version's ``./cfg`` failed
every command on a quoting mistake - and that each fixture is the kind of
file the checklist says it is.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

import pytest
from uat import cfg_sandbox

from tkcurses._cfg.errors import FileSyntaxError
from tkcurses._cfg.inifile import IniFile

CHECKLIST = Path(__file__).parents[1] / "docs" / "UAT_CFG.md"


@pytest.fixture
def sandbox(tmp_path):
    return cfg_sandbox.make(tmp_path / "sandbox")


def cfg(sandbox: Path, *argv: str, env=None) -> subprocess.CompletedProcess:
    clean = {k: v for k, v in os.environ.items() if not k.startswith("TKCURSES_")}
    return subprocess.run(
        [str(sandbox / "cfg"), *argv],
        cwd=sandbox,
        env=clean | (env or {}),
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_cfg_runs_this_checkouts_command_on_the_sandboxs_own_file(sandbox):
    done = cfg(sandbox, "path")
    assert done.returncode == 0, done.stderr
    assert done.stdout == f"{sandbox / 'home' / 'tkcurses' / 'tkcurses.ini'}\n"
    assert cfg(sandbox, "set", "input.escape_delay", "50").returncode == 0
    assert (sandbox / "home" / "tkcurses" / "tkcurses.ini").exists()


def test_the_fixtures_are_what_the_checklist_says(sandbox):
    fixtures = sandbox / "fixtures"
    hand = IniFile.read(fixtures / "hand-written.ini")
    assert hand.problems() == []
    assert [
        p.blocking for p in IniFile.read(fixtures / "bad-value.ini").problems()
    ] == [True]
    for name, line in (("duplicate-key.ini", 4), ("continued.ini", 3)):
        with pytest.raises(FileSyntaxError) as caught:
            IniFile.read(fixtures / name)
        assert caught.value.line == line
    kinds = [p.kind for p in IniFile.read(fixtures / "leftovers.ini").problems()]
    assert sorted(kinds) == ["removed", "unknown-key", "unknown-section"]


def test_hold_lock_holds_the_lock(sandbox):
    target = "home/tkcurses/tkcurses.ini"
    holder = subprocess.Popen(
        [str(sandbox / "hold-lock"), target, "10"],
        cwd=sandbox,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().startswith("holding")
        started = time.monotonic()
        done = cfg(sandbox, "set", "--lock-timeout", "0.5", "mouse.enabled", "off")
        assert done.returncode == 7, done.stderr
        assert time.monotonic() - started >= 0.5
    finally:
        holder.kill()
        holder.wait()


def test_every_exit_status_the_checklist_expects_is_one_the_command_has():
    from tkcurses._cfg import cli

    expected = set(re.findall(r"`echo \$\?` is (\d+)", CHECKLIST.read_text()))
    assert expected
    for status in expected:
        assert f"\n  {status} " in cli.EXIT_CODES


def test_an_existing_directory_with_files_is_refused(tmp_path, capsys):
    (tmp_path / "x").write_text("mine")
    assert cfg_sandbox.main([str(tmp_path)]) == 2
    assert (tmp_path / "x").read_text() == "mine"
