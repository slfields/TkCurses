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

"""The porting guide's programs run, and do what the page says they do.

``docs/guide/porting.md`` marks each complete TkCurses program with a MyST
comment, ``% expect: <text>``, naming something it draws, as the
introduction does; each is run here in a terminal. The tkinter programs it
shows for comparison are only compiled - there is no Tk here to run them.
Then the page's other promises, each with the gesture it tells the reader
to use.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PAGE = Path(__file__).parents[1] / "docs" / "guide" / "porting.md"
PROGRAM = re.compile(r"^% expect: ([^\n]+)\n\n```python\n(.*?)^```", re.M | re.S)
BLOCK = re.compile(r"^```python\n(.*?)^```", re.M | re.S)


def programs() -> dict[str, str]:
    return dict(PROGRAM.findall(PAGE.read_text()))


def program(expect: str) -> str:
    return programs()[expect]


def test_every_example_is_python():
    for block in BLOCK.findall(PAGE.read_text()):
        compile(block, str(PAGE), "exec")


def test_every_tkcurses_program_is_run():
    """Each block that imports tkcurses and calls mainloop is marked."""
    whole = [
        block
        for block in BLOCK.findall(PAGE.read_text())
        if "mainloop()" in block and "import tkcurses" in block
    ]
    assert sorted(whole) == sorted(programs().values())
    assert len(whole) == 5


def test_the_star_import_the_page_promises():
    names: dict[str, object] = {}
    exec("from tkcurses import *", names)
    assert {"Tk", "Label", "Button", "END"} <= set(names)


@pytest.mark.tty
@pytest.mark.parametrize("expect", sorted(programs()))
def test_a_program_runs_and_ctrl_c_closes_it(terminal, tmp_path, monkeypatch, expect):
    monkeypatch.chdir(tmp_path)  # the logging program writes app.log here
    term = terminal(cols=60, rows=16)
    term.run_source(program(expect), workdir=tmp_path)
    term.wait_for_text(expect)
    term.send(b"\x03")
    assert term.wait_for_exit() == 0


@pytest.mark.tty
def test_the_converter_converts(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("Convert"), workdir=tmp_path)
    term.wait_for_text("0 km")
    term.send_keys("10", "<Tab>", "<Return>")
    term.wait_for_text("16.1 km")


@pytest.mark.tty
def test_ctrl_s_saves(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("Not saved"), workdir=tmp_path)
    term.wait_for_text("Not saved")
    term.send(b"\x13")
    term.wait_for_text("Saved")


@pytest.mark.tty
def test_alt_f_then_s_saves(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("Not saved"), workdir=tmp_path)
    term.wait_for_text("Not saved")
    term.send(b"\x1bf")
    term.wait_for_text("Ctrl+S")
    term.send(b"s")
    term.wait_for(
        lambda t: t.contains("Saved") and not t.contains("Not saved"),
        message="Save chosen from the menu",
    )


@pytest.mark.tty
def test_the_colour_program_reports_a_depth(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("depth"), workdir=tmp_path)
    term.wait_for(
        lambda t: re.search(r"colour depth of \d+", "\n".join(t.display)) is not None,
        message="a depth",
    )
    for name in ("SteelBlue", "light goldenrod yellow", "gray90", "#cd5c5c"):
        assert term.contains(name)


@pytest.mark.tty
def test_the_logging_program_logs_to_its_file(terminal, tmp_path, monkeypatch):
    # The program writes app.log where it is run, and the harness runs it
    # from the current directory: anywhere but the checkout.
    monkeypatch.chdir(tmp_path)
    term = terminal(cols=60, rows=16)
    term.run_source(program("Started"), workdir=tmp_path)
    term.wait_for_text("Press")
    term.send_keys("<Tab>", "<Return>")
    term.wait_for_text("see app.log")
    assert "pressed" in (tmp_path / "app.log").read_text()
