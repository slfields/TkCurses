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

"""Stacked windows on a real terminal, against the real curses.panel.

Same method as the curses module's tests: run the same source twice, once
importing the standard library and once importing this, and compare the
screens. Stacking is exactly the kind of thing that looks right in a unit
test and is wrong on a screen.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

STACK = """
import {curses} as curses
import {panel} as panel


def main(stdscr):
    stdscr.addstr(0, 0, "beneath everything")
    stdscr.refresh()

    back = curses.newwin(4, 22, 2, 2)
    back.box()
    back.addstr(1, 1, "BACK")
    front = curses.newwin(4, 22, 3, 10)
    front.box()
    front.addstr(1, 1, "FRONT")

    first = panel.new_panel(back)
    second = panel.new_panel(front)
    {action}
    panel.update_panels()
    curses.doupdate()
    stdscr.addstr(9, 0, "drawn")
    stdscr.refresh()
    stdscr.getch()


curses.wrapper(main)
"""


def both(terminal, tmp_path, action="pass"):
    """The same program under each pair of modules, as two screens."""
    screens = {}
    for name, pair in (
        ("ours", ("tkcurses.curses", "tkcurses.panel")),
        ("theirs", ("curses", "curses.panel")),
    ):
        term = terminal(cols=44, rows=12)
        term.run_source(
            STACK.format(curses=pair[0], panel=pair[1], action=action),
            workdir=tmp_path,
        )
        term.wait_for_text("drawn")
        term.wait_for_idle()
        screens[name] = list(term.display)
        term.send(b"q")
    return screens


def test_the_stack_puts_the_later_panel_in_front(terminal, tmp_path):
    screens = both(terminal, tmp_path)
    assert screens["ours"] == screens["theirs"], _diff(screens)
    assert "FRONT" in "\n".join(screens["ours"])


def test_raising_the_bottom_panel_brings_it_forward(terminal, tmp_path):
    screens = both(terminal, tmp_path, action="first.top()")
    assert screens["ours"] == screens["theirs"], _diff(screens)


def test_hiding_a_panel_shows_what_was_behind_it(terminal, tmp_path):
    """The thing a stack is for: what is behind has to come back."""
    screens = both(terminal, tmp_path, action="second.hide()")
    assert screens["ours"] == screens["theirs"], _diff(screens)
    assert "FRONT" not in "\n".join(screens["ours"])
    assert "BACK" in "\n".join(screens["ours"])


def test_moving_a_panel_leaves_what_was_under_it_looking_right(terminal, tmp_path):
    screens = both(terminal, tmp_path, action="second.move(6, 18)")
    assert screens["ours"] == screens["theirs"], _diff(screens)


def test_sending_a_panel_to_the_back_hides_it_behind_the_other(terminal, tmp_path):
    screens = both(terminal, tmp_path, action="second.bottom()")
    assert screens["ours"] == screens["theirs"], _diff(screens)


@pytest.mark.parametrize(
    "action",
    [
        "second.hide()",
        "second.hide(); second.show()",
        "second.hide(); first.top()",
        "second.move(6, 18); second.hide()",
        "first.top(); second.move(5, 20)",
    ],
)
def test_the_background_comes_back_wherever_a_panel_leaves(terminal, tmp_path, action):
    """The thing a stack is for, and the one this got wrong at first.

    Hiding a panel left it on the screen, because nothing put back what was
    behind it. Measured against curses.panel, where hiding the top panel
    brings back what was underneath - including the plain background.
    """
    screens = both(terminal, tmp_path, action=action)
    assert screens["ours"] == screens["theirs"], _diff(screens)


def _diff(screens):
    """Both screens, labelled, for a failure anyone can read."""
    return (
        "tkcurses.panel:\n"
        + "\n".join(screens["ours"])
        + "\n\ncurses.panel:\n"
        + "\n".join(screens["theirs"])
    )
