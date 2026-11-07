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
"""The example programs run, and do what the examples page says they do.

Each file in ``examples/`` is on ``docs/guide/examples.md``, where the docs
build runs it for its picture; these run each one again and use it the way
the page tells a reader to.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
PAGE = ROOT / "docs" / "guide" / "examples.md"
DIRECTIVE = re.compile(r"^```\{tkcurses-example\} (\S+)$", re.M)


def source(name: str, *argv: str) -> str:
    """The program, with ``sys.argv`` set as if run with ``argv``."""
    text = (EXAMPLES / f"{name}.py").read_text()
    if not argv:
        return text
    return f"import sys\nsys.argv[1:] = {list(argv)!r}\n" + text


def start(terminal, tmp_path, name, *argv, cols=60, rows=16):
    term = terminal(cols=cols, rows=rows)
    term.run_source(source(name, *argv), workdir=tmp_path)
    term.wait_for(lambda t: any(line.strip() for line in t.display), message="a screen")
    return term


def test_every_example_is_on_the_page_and_nothing_else_is():
    shown = DIRECTIVE.findall(PAGE.read_text())
    files = sorted(f"examples/{path.name}" for path in EXAMPLES.glob("*.py"))
    assert sorted(shown) == files
    assert len(files) == 6


def test_every_example_carries_the_notice():
    for path in EXAMPLES.glob("*.py"):
        assert "SPDX-License-Identifier: GPL-3.0-only" in path.read_text()


@pytest.mark.tty
@pytest.mark.parametrize("name", sorted(p.stem for p in EXAMPLES.glob("*.py")))
def test_each_example_starts_and_ctrl_c_closes_it(terminal, tmp_path, name):
    term = start(terminal, tmp_path, name, rows=20)
    term.wait_for_idle()
    term.send(b"\x03")
    assert term.wait_for_exit() == 0
    assert term.stderr == ""


@pytest.mark.tty
def test_hello_quits_from_its_button(terminal, tmp_path):
    term = start(terminal, tmp_path, "hello")
    term.wait_for_text("Quit")
    term.send_keys("<Tab>", "<Return>")
    assert term.wait_for_exit() == 0


@pytest.mark.tty
def test_the_form_refuses_an_empty_name(terminal, tmp_path):
    term = start(terminal, tmp_path, "form", rows=20)
    term.wait_for_text("Country")
    term.send_keys(*["<Tab>"] * 7, "<Return>")
    term.wait_for_text("A name and an email address, please")


@pytest.mark.tty
def test_the_form_welcomes_a_new_account(terminal, tmp_path):
    term = start(terminal, tmp_path, "form", rows=20)
    term.wait_for_text("Country")
    # Tab to the Pro radio button, and space to choose it, as in Tk.
    term.send_keys("Ada", "<Tab>", "ada@example.org", "<Tab>", "<Tab>", "<Tab>", " ")
    term.send_keys(*["<Tab>"] * 3, "<Return>")
    term.wait_for_text("Ada, your pro account is ready.")


@pytest.mark.tty
def test_the_list_adds_marks_and_removes(terminal, tmp_path):
    term = start(terminal, tmp_path, "todo", cols=40, rows=14)
    term.wait_for_text("2 tasks, 0 done")
    term.send_keys("Buy bread", "<Return>")
    term.wait_for_text("3 tasks, 0 done")
    term.send_keys("<Tab>", " ")
    term.wait_for_text("[x] Water the plants")
    term.wait_for_text("3 tasks, 1 done")
    term.send_keys("<Delete>")
    term.wait_for(
        lambda t: t.contains("2 tasks, 0 done") and not t.contains("Water the plants"),
        message="the task removed and counted",
    )


@pytest.mark.tty
def test_the_editor_opens_edits_and_saves_a_file(terminal, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("first line\n")
    term = start(terminal, tmp_path, "editor", str(notes))
    term.wait_for_text("notes.txt   line 1, column 1")
    term.send_keys("<End>", " added")
    term.wait_for_text("notes.txt (changed)   line 1, column 17")
    term.send(b"\x13")  # Ctrl-S
    term.wait_for_text("notes.txt   line 1, column 17")
    assert notes.read_text() == "first line added\n"


@pytest.mark.tty
def test_the_editor_asks_before_losing_changes(terminal, tmp_path):
    term = start(terminal, tmp_path, "editor")
    term.wait_for_text("untitled")
    term.send_keys("words")
    term.wait_for_text("untitled (changed)")
    term.send(b"\x11")  # Ctrl-Q
    term.wait_for_text("Quit without saving?")
    term.send_keys("<Escape>")
    term.wait_for(
        lambda t: not t.contains("Quit without saving?"), message="the question gone"
    )
    assert term.exit_status is None


@pytest.mark.tty
def test_the_editor_menu_opens_from_the_keyboard(terminal, tmp_path):
    term = start(terminal, tmp_path, "editor")
    term.wait_for_text("untitled")
    term.send_keys("<F10>")
    term.wait_for_text("Ctrl+O")
    assert term.contains("Save as...")


@pytest.mark.tty
def test_the_table_shows_the_chosen_planet(terminal, tmp_path):
    term = start(terminal, tmp_path, "table", cols=52, rows=14)
    term.wait_for_text("Neptune")
    term.send_keys("<Down>", "<Down>", "<Return>")
    term.wait_for_text("Earth: 1.00 AU from the Sun, 1 moon")


@pytest.mark.tty
def test_a_number_sorts_the_table_and_again_reverses_it(terminal, tmp_path):
    term = start(terminal, tmp_path, "table", cols=52, rows=14)
    term.wait_for_text("Neptune")
    row = next(r for r, line in enumerate(term.display) if "Moons" in line)

    def first(t):
        return t.display[row + 1].lstrip("│").split()[0]

    term.send_keys("3")
    term.wait_for(
        lambda t: t.contains("Moons ^") and first(t) == "Mercury", message="fewest"
    )
    term.send_keys("3")
    term.wait_for(
        lambda t: t.contains("Moons v") and first(t) == "Saturn", message="most"
    )
    term.send_keys("1")
    term.wait_for(
        lambda t: t.contains("Planet ^") and first(t) == "Earth", message="by name"
    )


@pytest.mark.tty
def test_the_chart_draws_every_month_and_follows_a_resize(terminal, tmp_path):
    term = start(terminal, tmp_path, "chart", cols=50, rows=14)
    for month in ("Jan", "Feb", "Mar", "Apr", "May", "Jun"):
        term.wait_for_text(month)
    term.resize(60, 20)
    term.wait_for(
        lambda t: "Jun" in t.display[19] and t.display[19].index("Jun") > 45,
        message="the months along the new bottom row, spread wider",
    )
