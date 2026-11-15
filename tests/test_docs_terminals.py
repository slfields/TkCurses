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
"""The terminal guide's programs run, and its tables are true.

``docs/guide/terminals.md`` marks each complete program with
``% expect: <text>``, as the other guides do, and each is run here. The
page also makes two promises a table holds: which colour depth each
``TERM`` gives, and which settings take effect - a setting that is read and
then ignored must not be offered to a reader.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

import tkcurses
from tkcurses._core import config

PAGE = Path(__file__).parents[1] / "docs" / "guide" / "terminals.md"
PROGRAM = re.compile(r"^% expect: ([^\n]+)\n\n```python\n(.*?)^```", re.M | re.S)
BLOCK = re.compile(r"^```python\n(.*?)^```", re.M | re.S)
TERMINFO = (Path("/usr/share/terminfo"), Path("/lib/terminfo"), Path("/etc/terminfo"))

DEPTH_PROGRAM = """
import tkcurses as tk
root = tk.Tk()
tk.Label(root, text=f"depth={root.winfo_colordepth()};").pack()
root.mainloop()
"""


def programs() -> dict[str, str]:
    return dict(PROGRAM.findall(PAGE.read_text()))


def section(heading: str) -> str:
    text = PAGE.read_text()
    start = text.index(f"## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else None]


def table_rows(heading: str) -> list[list[str]]:
    """The body rows of the first table under a heading, cell by cell."""
    rows = [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in section(heading).splitlines()
        if line.startswith("|")
    ]
    return rows[2:]


def depths() -> list[tuple[str, int]]:
    """Each ``TERM`` the colour table names, with the depth it promises."""
    found = []
    for terms, _colours, depth in table_rows("Colours"):
        for term in re.findall(r"`([^`]+)`", terms):
            found.append((term, int(depth)))
    return found


def settings() -> list[tuple[str, str, str]]:
    """Each row of the settings table: variable, section and key."""
    found = []
    for variable, place, _default in table_rows("Settings"):
        name = variable.strip("`")
        where = re.fullmatch(r"`\[(\w+)\] (\w+)`", place)
        assert where, place
        found.append((name, where[1], where[2]))
    return found


def has_terminfo(term: str) -> bool:
    return any((base / term[0] / term).exists() for base in TERMINFO)


def test_every_example_is_python():
    for block in BLOCK.findall(PAGE.read_text()):
        compile(block, str(PAGE), "exec")


def test_every_tkcurses_program_is_run():
    whole = [
        block
        for block in BLOCK.findall(PAGE.read_text())
        if "mainloop()" in block and "import tkcurses" in block
    ]
    assert sorted(whole) == sorted(programs().values())
    assert len(whole) == 2


def test_the_colour_table_names_every_tier():
    assert {depth for _term, depth in depths()} == {0, 8, 16, 256, 16777216}


def test_every_setting_on_the_page_is_one_the_configuration_knows():
    known = {
        (setting.variable, setting.section, setting.key) for setting in config.SETTINGS
    }
    for row in settings():
        assert row in known


def test_every_setting_on_the_page_is_used_when_the_program_starts():
    """The page offers only settings that change something. Twelve of the
    eighteen there once were went unused, and the porting
    guide told readers to set one of them."""
    start = inspect.getsource(tkcurses.Tk._start)
    for variable, section_name, key in settings():
        assert f"{section_name}.{key}" in start, variable


def test_the_page_mentions_no_setting_outside_its_table():
    named = set(re.findall(r"TKCURSES_[A-Z_]+", PAGE.read_text()))
    assert named == {variable for variable, _section, _key in settings()}


def test_no_guide_names_a_setting_that_does_nothing():
    """The porting guide offered TKCURSES_DISPLAY_COLOR_MODE, which is
    ignored. Every guide's settings are the ones this page's table allows."""
    allowed = {variable for variable, _section, _key in settings()}
    for page in PAGE.parent.glob("*.md"):
        named = set(re.findall(r"TKCURSES_[A-Z_]+", page.read_text()))
        assert named <= allowed, (page.name, named - allowed)


@pytest.mark.tty
@pytest.mark.parametrize("expect", sorted(programs()))
def test_a_program_runs_and_ctrl_c_closes_it(terminal, tmp_path, expect):
    term = terminal(cols=60, rows=16)
    term.run_source(programs()[expect], workdir=tmp_path)
    term.wait_for_text(expect)
    term.send(b"\x03")
    assert term.wait_for_exit() == 0


@pytest.mark.tty
def test_the_size_follows_the_terminal(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(programs()["columns by"], workdir=tmp_path)
    term.wait_for_text("60 columns by 16 rows")
    term.resize(72, 20)
    term.wait_for_text("72 columns by 20 rows")


@pytest.mark.tty
def test_the_copy_button_copies(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(programs()["Copy"], workdir=tmp_path)
    term.wait_for_text("TK-4471")
    term.send_keys("<Tab>", "<Tab>", "<Return>")
    term.wait_for_text("Copied TK-4471")


@pytest.mark.tty
@pytest.mark.parametrize(("term_name", "depth"), depths())
def test_each_term_gives_the_depth_the_page_says(terminal, tmp_path, term_name, depth):
    if not has_terminfo(term_name):
        pytest.skip(f"no terminfo entry for {term_name} here")
    term = terminal(cols=40, rows=6, env={"TERM": term_name})
    term.run_source(DEPTH_PROGRAM, workdir=tmp_path)
    term.wait_for_text(f"depth={depth};")
