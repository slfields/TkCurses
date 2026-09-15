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

"""Colour tests that need a real terminal.

The unit tests stub curses, so these confirm the manager works against the
real library: pairs are allocated, and the colours arrive at the terminal.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def test_colours_reach_the_terminal(terminal, tmp_path):
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
        from tkcurses._core.colors import ColorManager
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            colors = ColorManager()
            colors.start()
            screen.attribute_resolver = colors.attribute_for

            buffer.write(0, 0, "red text", fg="red", bg="black")
            buffer.write(1, 0, "green text", fg="green", bg="black")
            buffer.write(2, 0, "blue on white", fg="blue", bg="white")
            screen.refresh()
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("blue on white")
    assert term.attrs_at(0, 0)["fg"] == "red"
    assert term.attrs_at(1, 0)["fg"] == "green"
    assert term.attrs_at(2, 0)["fg"] == "blue"
    assert term.attrs_at(2, 0)["bg"] == "white"
    term.send_keys("q")


PAINT = """
from tkcurses._core.colors import ColorManager
from tkcurses._core.screen import CursesScreen
import curses

screen = CursesScreen()
buffer = screen.start()
try:
    colors = ColorManager()
    colors.start()
    screen.attribute_resolver = colors.attribute_for
    buffer.write(0, 0, "A", fg="lime", bg="black")
    buffer.write(1, 0, "B", fg="black", bg="lime")
    buffer.write(2, 0, "C", fg="#ff8000", bg="black")
    buffer.write(3, 0, "D", fg="black", bg="#ff8000")
    buffer.write(4, 0, "depth=%s" % colors.depth.name)
    screen.refresh()
    screen.stdscr.getch()
finally:
    screen.stop()
"""


def paint(terminal, tmp_path, term_name):
    """Paint the same four cells on a terminal of this kind."""
    term = terminal(cols=40, rows=8, env={"TERM": term_name})
    term.run_source(PAINT, workdir=tmp_path)
    term.wait_for_text("depth=")
    return term


#: What each tier really put on the screen, measured rather than predicted.
#: Read down a column to see what changes as the terminal gets better: bright
#: green stops being green-with-bold and becomes a colour of its own, and
#: orange stops being yellow.
MEASURED = {
    "xterm": (
        "BASIC",
        {"fg": "green", "bold": True},
        {"bg": "green", "bold": False},
        {"fg": "brown"},
        {"bg": "brown"},
    ),
    "xterm-16color": (
        "BRIGHT",
        {"fg": "brightgreen", "bold": False},
        {"bg": "brightgreen", "bold": False},
        {"fg": "brown"},
        {"bg": "brown"},
    ),
    "xterm-256color": (
        "EXTENDED",
        {"fg": "brightgreen", "bold": False},
        {"bg": "brightgreen", "bold": False},
        {"fg": "ff8700"},
        {"bg": "ff8700"},
    ),
}


@pytest.mark.parametrize("term_name", sorted(MEASURED))
def test_each_tier_paints_what_it_has(terminal, tmp_path, term_name):
    depth, *rows = MEASURED[term_name]
    term = paint(terminal, tmp_path, term_name)
    assert term.row(4).strip() == f"depth={depth}", term.describe()
    for row, expected in enumerate(rows):
        attrs = term.attrs_at(row, 0)
        for key, value in expected.items():
            assert attrs[key] == value, (
                f"{term_name} row {row}: {key} was {attrs[key]!r}, "
                f"wanted {value!r}\n{term.describe()}"
            )
    term.send_keys("q")


def test_a_bright_background_needs_more_than_eight_colours(terminal, tmp_path):
    """The bug this tier work exists for.

    A_BOLD brightens a foreground and does nothing whatever to a background,
    so on an eight-colour terminal `lime` and `green` are the same background
    and half a sixteen-swatch palette is invisible. From sixteen up brightness
    is a colour number instead, and the two differ.
    """
    eight = paint(terminal, tmp_path, "xterm")
    assert eight.attrs_at(1, 0)["bg"] == "green"
    eight.send_keys("q")

    sixteen = paint(terminal, tmp_path, "xterm-16color")
    assert sixteen.attrs_at(1, 0)["bg"] == "brightgreen"
    sixteen.send_keys("q")


def test_an_eight_colour_terminal_still_uses_bold_for_brightness(terminal, tmp_path):
    """It has nothing else, so the old behaviour has to survive there."""
    term = paint(terminal, tmp_path, "xterm")
    assert term.attrs_at(0, 0)["fg"] == "green"
    assert term.attrs_at(0, 0)["bold"] is True
    term.send_keys("q")


def test_pairs_are_allocated_against_real_curses(terminal, tmp_path):
    term = terminal(cols=40, rows=6)
    term.run_source(
        """
        from tkcurses._core.colors import ColorManager
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            colors = ColorManager()
            supported = colors.start()
            colors.attribute_for("red", "black")
            colors.attribute_for("red", "black")   # reused
            colors.attribute_for("blue", "black")  # new
            buffer.write(0, 0, "colour=%s pairs=%d" % (supported, colors.allocated))
            screen.refresh()
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("pairs=")
    assert term.row(0) == "colour=True pairs=2"
    term.send_keys("q")


RGB = """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
buffer.write(0, 0, "depth=%s" % root.winfo_colordepth().name)
buffer.write(1, 0, "gray=%r" % (root.winfo_rgb("gray"),))
root.tk.screen.refresh()
root.after(8000, root.quit)
root.mainloop()
"""


@pytest.mark.parametrize(
    ("term_name", "depth", "gray"),
    [
        ("xterm", "BASIC", (29298, 29298, 29298)),
        ("xterm-256color", "EXTENDED", (30326, 30326, 30326)),
    ],
)
def test_winfo_rgb_answers_for_the_terminal_in_front_of_it(
    terminal, tmp_path, term_name, depth, gray
):
    """tkinter's winfo_rgb reports what the display will really show, and on
    a terminal that depends on how many colours it has: eight can only offer
    dim white for grey, 256 has twenty-four greys to pick the nearest from.
    """
    term = terminal(cols=50, rows=6, env={"TERM": term_name})
    term.run_source(RGB, workdir=tmp_path)
    term.wait_for_text("gray=")
    assert term.row(0).strip() == f"depth={depth}", term.describe()
    assert term.row(1).strip() == f"gray={gray!r}", term.describe()
