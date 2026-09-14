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

"""Panel stacking against real curses.

Overlap is the whole point of a panel stack, so these tests put windows on top
of each other and read back which one the terminal actually shows.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

PREAMBLE = """
import curses
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack
from tkcurses._core.screen import CursesScreen

screen = CursesScreen()
screen.start()
try:
    stack = PanelStack()

    def panel(x, y, w, h, text):
        p = stack.new_panel(Rect(x, y, w, h))
        p.window.border()
        p.window.addstr(1, 1, text)
        return p
"""

EPILOGUE = """
    stack.update()
    screen.stdscr.getch()
finally:
    stack.clear()
    screen.stop()
"""


def run(term, tmp_path, body):
    term.run_source(PREAMBLE + body + EPILOGUE, workdir=tmp_path)


def test_a_later_panel_covers_an_earlier_one(terminal, tmp_path):
    term = terminal(cols=30, rows=10)
    run(
        term,
        tmp_path,
        """
    panel(0, 0, 20, 5, "BACK")
    panel(4, 2, 20, 5, "FRONT")
""",
    )
    term.wait_for_text("FRONT")
    # The front panel's border overwrites the back panel's interior.
    assert term.display[2][4] == "┌"
    assert term.text_at(3, 5, 5) == "FRONT"
    term.send_keys("q")


def test_raising_a_panel_brings_it_forward(terminal, tmp_path):
    term = terminal(cols=30, rows=10)
    run(
        term,
        tmp_path,
        """
    back = panel(0, 0, 20, 5, "BACK")
    panel(4, 2, 20, 5, "FRONT")
    stack.raise_to_top(back)
""",
    )
    term.wait_for_text("BACK")
    # BACK now covers the overlap, so its bottom border is intact at row 4.
    assert term.display[4][4] == "─"
    term.send_keys("q")


def test_hiding_a_panel_reveals_what_is_behind(terminal, tmp_path):
    term = terminal(cols=30, rows=10)
    run(
        term,
        tmp_path,
        """
    panel(0, 0, 20, 5, "BACK")
    front = panel(4, 2, 20, 5, "FRONT")
    stack.hide(front)
""",
    )
    term.wait_for_text("BACK")
    assert not term.contains("FRONT")
    term.send_keys("q")


def test_showing_a_panel_again_restores_its_place(terminal, tmp_path):
    term = terminal(cols=30, rows=10)
    run(
        term,
        tmp_path,
        """
    panel(0, 0, 20, 5, "BACK")
    front = panel(4, 2, 20, 5, "FRONT")
    stack.hide(front)
    stack.update()
    stack.show(front)
""",
    )
    term.wait_for_text("FRONT")
    assert term.text_at(3, 5, 5) == "FRONT"
    term.send_keys("q")


def test_moving_a_panel_moves_its_contents(terminal, tmp_path):
    term = terminal(cols=36, rows=10)
    run(
        term,
        tmp_path,
        """
    moving = panel(0, 0, 14, 4, "MOVED")
    stack.move(moving, 12, 4)
""",
    )
    term.wait_for_text("MOVED")
    assert term.find_text("MOVED") == (5, 13)
    term.send_keys("q")


def test_replacing_a_window_resizes_the_panel(terminal, tmp_path):
    term = terminal(cols=36, rows=12)
    run(
        term,
        tmp_path,
        """
    from tkcurses._core.geometry import Rect as R
    p = panel(0, 0, 10, 3, "SMALL")
    stack.replace_window(p, R(0, 0, 24, 6))
    p.window.border()
    p.window.addstr(1, 1, "RESIZED")
""",
    )
    term.wait_for_text("RESIZED")
    term.assert_box(top=0, left=0, height=6, width=24)
    term.send_keys("q")


def test_destroying_a_panel_removes_it_from_the_display(terminal, tmp_path):
    term = terminal(cols=30, rows=10)
    run(
        term,
        tmp_path,
        """
    panel(0, 0, 20, 5, "KEPT")
    doomed = panel(4, 6, 20, 4, "GONE")
    stack.destroy(doomed)
    screen.stdscr.clear()
    screen.stdscr.refresh()
""",
    )
    term.wait_for_text("KEPT")
    assert not term.contains("GONE")
    term.send_keys("q")


def test_deep_stack_shows_the_frontmost(terminal, tmp_path):
    term = terminal(cols=40, rows=14)
    run(
        term,
        tmp_path,
        """
    for i in range(5):
        panel(i * 2, i, 16, 4, "LAYER%d" % i)
""",
    )
    term.wait_for_text("LAYER4")
    assert term.text_at(5, 9, 6) == "LAYER4"
    term.send_keys("q")
