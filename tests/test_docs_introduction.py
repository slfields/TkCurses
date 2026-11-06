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

"""The introduction's programs run, and do what the page says they do.

``docs/guide/introduction.md`` is read by someone who cannot tell a wrong
example from their own mistake, so every complete program on it is run
here in a terminal (TkCurses-imii.2). A program is marked in the page by a
MyST comment, ``% expect: <text>``, naming something it draws; the page
promises Ctrl-C closes any of them, so that is how each one is closed.

The interaction tests take the page's other promises in turn - Tab and
Return press a button, a binding hears a key, the to-do list adds and
removes - each with the gesture the page tells the reader to use.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PAGE = Path(__file__).parents[1] / "docs" / "guide" / "introduction.md"
PROGRAM = re.compile(r"^% expect: ([^\n]+)\n\n```python\n(.*?)^```", re.M | re.S)
BLOCK = re.compile(r"^```python\n(.*?)^```", re.M | re.S)


def programs() -> dict[str, str]:
    return dict(PROGRAM.findall(PAGE.read_text()))


def program(expect: str) -> str:
    return programs()[expect]


def test_every_example_is_python():
    blocks = BLOCK.findall(PAGE.read_text())
    assert len(blocks) >= 10
    for block in blocks:
        compile(block, str(PAGE), "exec")


def test_the_complete_programs_are_found():
    # Every block that calls mainloop is a whole program, and is run below.
    whole = [b for b in BLOCK.findall(PAGE.read_text()) if "mainloop()" in b]
    assert len(programs()) == len(whole) == 8


@pytest.mark.tty
@pytest.mark.parametrize("expect", sorted(programs()))
def test_a_program_runs_and_ctrl_c_closes_it(terminal, tmp_path, expect):
    term = terminal(cols=60, rows=16)
    term.run_source(program(expect), workdir=tmp_path)
    term.wait_for_text(expect)
    term.send(b"\x03")
    assert term.wait_for_exit() == 0


@pytest.mark.tty
def test_tab_and_return_press_the_button(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("Pressed 0 times"), workdir=tmp_path)
    term.wait_for_text("Press me")
    term.send_keys("<Tab>", "<Return>")
    term.wait_for_text("Pressed 1 times")
    term.send_keys(" ")
    term.wait_for_text("Pressed 2 times")


@pytest.mark.tty
def test_the_greeting_follows_the_field(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("Hello, stranger"), workdir=tmp_path)
    term.wait_for_text("Hello, stranger")
    term.send_keys("Q")
    term.wait_for(
        lambda t: "Hello, stranger" not in "\n".join(t.display) and "Q" in t.display[2],
        message="the greeting changed with the field",
    )
    assert "Hello, " in "\n".join(term.display)


@pytest.mark.tty
def test_a_binding_hears_the_key_and_escape_closes(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("Press a key"), workdir=tmp_path)
    term.wait_for_text("Press a key")
    term.send_keys("q")
    term.wait_for_text("You pressed q")
    term.send_keys("<Escape>")
    assert term.wait_for_exit() == 0


@pytest.mark.tty
def test_the_clock_ticks(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("Seconds:"), workdir=tmp_path)
    term.wait_for(
        lambda t: re.search(r"Seconds:\s*1\b", "\n".join(t.display)) is not None,
        message="a second has passed",
    )


@pytest.mark.tty
def test_the_to_do_list_adds_and_removes(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("To do"), workdir=tmp_path)
    term.wait_for_text("Done")
    term.send_keys("buy milk", "<Return>")

    def added(t):
        # Once on screen, and that once in the list: the field was emptied.
        return sum(row.count("buy milk") for row in t.display) == 1 and (
            t.find_text("buy milk")[0] > 4
        )

    term.wait_for(added, message="the task moved from the field to the list")
    row, column = term.find_text("buy milk")
    done = term.find_text("Done")
    assert done[0] > row, "the buttons are below the list, against the bottom"
    term.click(column, row)
    term.click(done[1], done[0])
    term.wait_for(
        lambda t: t.find_text("buy milk") is None, message="the task was removed"
    )
