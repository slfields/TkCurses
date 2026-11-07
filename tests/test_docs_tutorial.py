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

"""The tutorial's programs run, and do what the pages say they do.

The tutorial - ``introduction.md``, ``concepts.md``, ``widgets.md`` and
``mistakes.md`` under ``docs/guide`` - is read by someone who cannot tell a
wrong example from their own mistake, so every complete program on it is
run here in a terminal (TkCurses-imii.2, TkCurses-5dli). A program is
marked in its page by a MyST comment, ``% expect: <text>``, naming
something it draws; the introduction promises Ctrl-C closes any of them,
so that is how each one is closed.

The interaction tests take the pages' other promises in turn - Tab and
Return press a button, a binding hears a key, "break" stops a key, the
packed labels sit against the sides they name - each with the gesture the
page tells the reader to use. ``larger-program.md`` shows
``examples/notes.py``, which ``tests/test_examples.py`` runs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

GUIDE = Path(__file__).parents[1] / "docs" / "guide"
PAGES = [
    GUIDE / f"{name}.md" for name in ("introduction", "concepts", "widgets", "mistakes")
]
PROGRAM = re.compile(r"^% expect: ([^\n]+)\n\n```python\n(.*?)^```", re.M | re.S)
BLOCK = re.compile(r"^```python\n(.*?)^```", re.M | re.S)


def found(pattern: re.Pattern[str]) -> list:
    return [match for page in PAGES for match in pattern.findall(page.read_text())]


def programs() -> dict[str, str]:
    return dict(found(PROGRAM))


def program(expect: str) -> str:
    return programs()[expect]


def test_every_example_is_python():
    for page in PAGES:
        for block in BLOCK.findall(page.read_text()):
            compile(block, str(page), "exec")
    assert len(found(BLOCK)) >= 30


def test_the_complete_programs_are_found():
    # Every block that calls mainloop is a whole program, and is run below;
    # and no two say they draw the same thing, or one would hide the other.
    whole = [b for b in found(BLOCK) if "mainloop()" in b]
    assert len(found(PROGRAM)) == len(programs()) == len(whole) == 19


def test_the_pages_link_to_each_other_in_order():
    # The introduction promises a series read in order; each page ends by
    # naming the next.
    for page, after in zip(
        PAGES[:3], ("concepts", "widgets", "larger-program"), strict=True
    ):
        tail = page.read_text().rsplit("## Where next", 1)[1]
        assert f"]({after}.md)" in tail, page.name


@pytest.mark.tty
@pytest.mark.parametrize("expect", sorted(programs()))
def test_a_program_runs_and_ctrl_c_closes_it(terminal, tmp_path, expect):
    term = terminal(cols=60, rows=16)
    term.run_source(program(expect), workdir=tmp_path)
    term.wait_for_text(expect)
    term.send(b"\x03")
    assert term.wait_for_exit() == 0
    assert term.stderr == ""


@pytest.mark.tty
def test_the_tree_program_shows_the_tree_the_page_prints(terminal, tmp_path):
    page = (GUIDE / "concepts.md").read_text()
    shown = re.search(r"It shows:\n\n```text\n(.*?)```", page, re.S).group(1)
    term = terminal(cols=60, rows=16)
    term.run_source(program(".buttons  Frame"), workdir=tmp_path)
    lines = [line.strip() for line in shown.splitlines()]
    term.wait_for(
        lambda t: all(t.contains(line) for line in lines),
        message="every line of the tree the page shows",
    )


@pytest.mark.tty
def test_pack_puts_each_label_against_its_side(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("5 the rest"), workdir=tmp_path)

    def placed(t):
        found = {text: t.find_text(text) for text in ("1 top", "2 bottom", "3 left")}
        right = t.find_text("4 right")
        return (
            None not in found.values()
            and right is not None
            and found["1 top"][0] == 0
            and found["2 bottom"][0] == 15
            and found["3 left"][1] == 0
            and right[1] + len("4 right") == 60
        )

    term.wait_for(placed, message="top, bottom, left and right")


@pytest.mark.tty
def test_place_follows_the_terminal_when_it_grows(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("bottom right"), workdir=tmp_path)
    term.wait_for_cell(15, 59, lambda cell: cell.data == "t")
    term.resize(80, 20)
    term.wait_for(
        lambda t: t.find_text("bottom right") == (19, 80 - len("bottom right")),
        message="the label in the new bottom-right corner",
    )


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
def test_break_keeps_all_but_digits_out(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("Age, in digits:"), workdir=tmp_path)
    term.wait_for_text("Age, in digits:")
    term.send_keys("a1b2", "<BackSpace>", "3x")
    term.wait_for(
        lambda t: re.search(r"│13\s+│", t.display[2]) is not None,
        message="the letters stopped, the digits and BackSpace let through",
    )


@pytest.mark.tty
def test_the_clock_ticks(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("Seconds:"), workdir=tmp_path)
    term.wait_for(
        lambda t: re.search(r"Seconds:\s*1\b", "\n".join(t.display)) is not None,
        message="a second has passed",
    )


@pytest.mark.tty
def test_the_print_form_follows_every_control(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("1 x A4, mono, both sides, for Ada"), workdir=tmp_path)
    term.wait_for_text("Both sides")
    row, column = term.find_text("Both sides")
    term.click(column, row)
    term.wait_for_text("1 x A4, mono, one side, for Ada")
    row, column = term.find_text("Colour")
    term.click(column, row)
    term.wait_for_text("1 x A4, colour, one side, for Ada")


@pytest.mark.tty
def test_choosing_fruit_names_it(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("Pick some fruit"), workdir=tmp_path)
    term.wait_for_text("damson")
    row, column = term.find_text("banana")
    term.click(column, row)
    term.wait_for(
        lambda t: any(line.strip() == "banana" for line in t.display),
        message="the label names the fruit chosen",
    )


@pytest.mark.tty
def test_the_menu_opens_a_dialog_that_renames(terminal, tmp_path):
    term = terminal(cols=60, rows=16)
    term.run_source(program("F10 opens the menus"), workdir=tmp_path)
    term.wait_for_text("F10 opens the menus")
    term.send_keys("<F10>")
    term.wait_for_text("Rename...")
    term.send_keys("<Return>")
    term.wait_for_text("New name:")
    term.send_keys("Bob", "<Return>")
    term.wait_for_text("Renamed to Bob")


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
