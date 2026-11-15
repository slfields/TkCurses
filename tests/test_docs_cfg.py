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

"""The ``tkcurses-cfg`` page's examples are what the command prints.

Every ``console`` block on the page is one session, run in order: each
``$ tkcurses-cfg ...`` line is run - with any ``NAME=value`` in front of it
set in the environment for that command alone - and what follows it, up to
the next ``$``, must be exactly its output, standard output and standard
error together as a terminal would show them. The run starts with no
configuration files and a home directory of its own, and runs in-process
with the system-wide file moved somewhere empty, so the page cannot depend
on the machine that builds it.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import shlex
from pathlib import Path

import pytest

from tkcurses._cfg import cli

PAGE = Path(__file__).parents[1] / "docs" / "reference" / "tkcurses-cfg.md"
BLOCK = re.compile(r"```console\n(.*?)```", re.DOTALL)


def session() -> list[tuple[str, str]]:
    """Each command on the page with the output shown for it."""
    steps: list[tuple[str, str]] = []
    for block in BLOCK.findall(PAGE.read_text()):
        for line in block.splitlines(keepends=True):
            if line.startswith("$ "):
                steps.append((line[2:].strip(), ""))
            else:
                command, shown = steps[-1]
                steps[-1] = (command, shown + line)
    return steps


def test_the_page_has_examples():
    assert len(session()) >= 10


def test_every_example_prints_what_the_page_shows(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    for name in list(os.environ):
        if name.startswith("TKCURSES_"):
            monkeypatch.delenv(name)
    user = home / ".config" / "tkcurses" / "tkcurses.ini"
    system = tmp_path / "etc" / "tkcurses.ini"
    monkeypatch.setattr(cli, "config_paths", lambda: (system, user))
    for command, shown in session():
        words = shlex.split(command)
        assignments = {}
        while "=" in words[0]:
            name, _, value = words.pop(0).partition("=")
            assignments[name] = value
        assert words[0] == "tkcurses-cfg", command
        with monkeypatch.context() as scope:
            for name, value in assignments.items():
                scope.setenv(name, value)
            both = io.StringIO()
            with contextlib.redirect_stdout(both), contextlib.redirect_stderr(both):
                cli.main(words[1:])
        assert both.getvalue() == shown, f"$ {command}"


@pytest.mark.parametrize(
    "status", ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "130"]
)
def test_every_exit_status_is_on_the_page(status):
    assert f"\n| {status} | " in PAGE.read_text()
    assert f"\n  {status} " in cli.EXIT_CODES
