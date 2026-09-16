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

"""The curses compatibility module, where it needs no terminal.

Window drawing is tested against a ScreenBuffer directly, which is what a
window writes into - so most of the behaviour can be checked without curses
running at all. What genuinely needs a terminal is in the tty file.
"""

from __future__ import annotations

import curses as stdlib_curses
import sys

import pytest

import tkcurses.curses as tc
from tkcurses._core.screen import ScreenBuffer


@pytest.fixture
def window():
    """A detached 6x20 window, writing into a buffer of its own."""
    return tc.Window(ScreenBuffer(20, 6), 0, 0, 6, 20, owns=True)


def text(window, row):
    """One row of a window, as a string."""
    return window._read(row, 0, window.getmaxyx()[1])


# ------------------------------------------------------------- the shadowing


def test_importing_this_does_not_break_the_package():
    """The trap this module had to be arranged around.

    tkcurses.curses is a submodule, so importing it makes Python bind it as
    the attribute `curses` on the tkcurses package - which is
    tkcurses/__init__.py's own global namespace. Measured before the fix: a
    plain `import curses` there was replaced by this module, and every one of
    the fifty-one references in that file would have resolved against it.
    """
    import tkcurses.curses  # noqa: F401

    namespace = sys.modules["tkcurses"].__dict__
    assert namespace["_curses"] is stdlib_curses
    assert "curses" not in namespace or namespace["curses"] is not stdlib_curses


def test_the_package_still_works_after_the_import():
    """Not just the name - the behaviour that name is used for."""
    import tkcurses.curses

    root = tkcurses.Misc()
    assert root.winfo_rgb("red") == (52685, 0, 0)
    assert tkcurses.Frame(root, name="f").winfo_class() == "Frame"


def test_constants_come_through_without_being_listed():
    """Two hundred KEY_ names written out by hand would be two hundred
    chances to mistype one, and a list that goes stale."""
    assert tc.A_BOLD == stdlib_curses.A_BOLD
    assert tc.KEY_UP == stdlib_curses.KEY_UP
    assert tc.COLOR_RED == stdlib_curses.COLOR_RED
    assert tc.error is stdlib_curses.error


def test_a_name_that_is_in_neither_is_still_an_attribute_error():
    with pytest.raises(AttributeError, match="no attribute"):
        tc.no_such_curses_function  # noqa: B018


# ------------------------------------------------------------------ writing


def test_addstr_writes_at_the_cursor(window):
    window.addstr("hello")
    assert text(window, 0).startswith("hello")
    assert window.getyx() == (0, 5)


def test_addstr_writes_where_it_is_told(window):
    window.addstr(2, 3, "there")
    assert text(window, 2)[3:8] == "there"


def test_addstr_is_clipped_to_the_window(window):
    """Not an error, and not a write past the edge: curses truncates."""
    window.addstr(0, 17, "abcdefgh")
    assert text(window, 0)[17:] == "abc"


def test_addch_takes_a_character_or_a_code(window):
    window.addch(0, 0, "x")
    window.addch(0, 1, ord("y"))
    assert text(window, 0)[:2] == "xy"


def test_addnstr_stops_after_n(window):
    window.addnstr(0, 0, "abcdefg", 3)
    assert text(window, 0)[:4] == "abc "


def test_insstr_pushes_the_rest_of_the_line_right(window):
    window.addstr(0, 0, "world")
    window.insstr(0, 0, "hello ")
    assert text(window, 0).startswith("hello world")


def test_insch_pushes_one_cell_right(window):
    window.addstr(0, 0, "bc")
    window.insch(0, 0, "a")
    assert text(window, 0)[:3] == "abc"


def test_delch_pulls_the_rest_of_the_line_left(window):
    window.addstr(0, 0, "axbc")
    window.delch(0, 1)
    assert text(window, 0)[:3] == "abc"


# ------------------------------------------------------------------ reading


def test_inch_packs_the_character_and_its_attributes(window):
    window.addstr(0, 0, "A", stdlib_curses.A_BOLD)
    packed = window.inch(0, 0)
    assert packed & 0xFF == ord("A")
    assert packed & stdlib_curses.A_BOLD


def test_instr_reads_the_row_back(window):
    window.addstr(1, 2, "read me")
    assert window.instr(1, 2).startswith(b"read me")


# ------------------------------------------------------------------ erasing


def test_erase_blanks_everything(window):
    window.addstr(0, 0, "gone")
    window.erase()
    assert text(window, 0).strip() == ""
    assert window.getyx() == (0, 0)


def test_clrtoeol_blanks_from_the_cursor(window):
    window.addstr(0, 0, "keepdrop")
    window.move(0, 4)
    window.clrtoeol()
    assert text(window, 0).strip() == "keep"


def test_clrtobot_blanks_the_rest_of_the_window(window):
    window.addstr(0, 0, "keep")
    window.addstr(1, 0, "drop")
    window.addstr(2, 0, "drop")
    window.move(1, 0)
    window.clrtobot()
    assert text(window, 0).strip() == "keep"
    assert text(window, 1).strip() == ""
    assert text(window, 2).strip() == ""


def test_deleteln_pulls_the_rows_below_up(window):
    window.addstr(0, 0, "one")
    window.addstr(1, 0, "two")
    window.move(0, 0)
    window.deleteln()
    assert text(window, 0).strip() == "two"


def test_insertln_pushes_the_rows_below_down(window):
    window.addstr(0, 0, "one")
    window.move(0, 0)
    window.insertln()
    assert text(window, 0).strip() == ""
    assert text(window, 1).strip() == "one"


# ---------------------------------------------------------------- scrolling


def test_scrolling_is_refused_until_it_is_allowed(window):
    """curses' own rule, and a good one: a window that scrolls by accident
    loses whatever was on the top line."""
    with pytest.raises(stdlib_curses.error):
        window.scroll()


def test_scrolling_moves_the_rows_up(window):
    window.scrollok(True)
    window.addstr(0, 0, "one")
    window.addstr(1, 0, "two")
    window.scroll()
    assert text(window, 0).strip() == "two"


# --------------------------------------------------------------- attributes


def test_attron_applies_to_later_writes(window):
    window.attron(stdlib_curses.A_BOLD)
    window.addstr(0, 0, "bold")
    assert window._buffer.cell(0, 0).attr & stdlib_curses.A_BOLD


def test_attroff_takes_it_away_again(window):
    window.attron(stdlib_curses.A_BOLD)
    window.attroff(stdlib_curses.A_BOLD)
    window.addstr(0, 0, "plain")
    assert not window._buffer.cell(0, 0).attr & stdlib_curses.A_BOLD


def test_an_attribute_given_to_addstr_wins_for_that_call(window):
    window.addstr(0, 0, "loud", stdlib_curses.A_REVERSE)
    window.addstr(1, 0, "quiet")
    assert window._buffer.cell(0, 0).attr & stdlib_curses.A_REVERSE
    assert not window._buffer.cell(1, 0).attr & stdlib_curses.A_REVERSE


def test_chgat_restyles_without_changing_the_text(window):
    window.addstr(0, 0, "unchanged")
    window.chgat(0, 0, 9, stdlib_curses.A_UNDERLINE)
    assert text(window, 0).startswith("unchanged")
    assert window._buffer.cell(0, 0).attr & stdlib_curses.A_UNDERLINE


def test_bkgd_applies_to_what_is_already_there(window):
    window.addstr(0, 0, "text")
    window.bkgd(" ", stdlib_curses.A_DIM)
    assert window._buffer.cell(0, 0).attr & stdlib_curses.A_DIM
    assert text(window, 0).startswith("text"), "bkgd must not erase"


# ------------------------------------------------------------------ drawing


def test_hline_draws_across(window):
    window.hline(0, 0, "-", 5)
    assert text(window, 0)[:6] == "----- "


def test_vline_draws_down(window):
    window.vline(0, 0, "|", 3)
    assert [text(window, row)[0] for row in range(4)] == ["|", "|", "|", " "]


def test_box_draws_a_frame(window):
    window.box()
    top = text(window, 0)
    assert top[0] != " " and top[-1] != " "
    assert text(window, 1)[0] != " "
    assert text(window, 1)[1] == " ", "the inside is left alone"


# ----------------------------------------------------------------- geometry


def test_a_window_reports_its_size_and_place():
    win = tc.Window(ScreenBuffer(10, 4), 2, 3, 4, 10, owns=True)
    assert win.getmaxyx() == (4, 10)
    assert win.getbegyx() == (2, 3)


def test_moving_outside_the_window_is_an_error(window):
    with pytest.raises(stdlib_curses.error):
        window.move(99, 0)


def test_enclose_answers_in_screen_coordinates():
    win = tc.Window(ScreenBuffer(10, 4), 2, 3, 4, 10, owns=True)
    assert win.enclose(2, 3)
    assert win.enclose(5, 12)
    assert not win.enclose(1, 3)
    assert not win.enclose(6, 3)


def test_a_subwindow_shares_its_parents_cells(window):
    """curses' rule, and the reason subwindows are useful rather than merely
    convenient: writing into the child shows through the parent."""
    child = window.derwin(2, 5, 1, 2)
    child.addstr(0, 0, "abc")
    assert text(window, 1)[2:5] == "abc"


def test_a_subwindow_knows_where_it_sits(window):
    child = window.derwin(2, 5, 1, 2)
    assert child.getparyx() == (1, 2)
    assert window.getparyx() == (-1, -1)


def test_a_top_level_window_does_not_share(window):
    other = tc.Window(ScreenBuffer(20, 6), 0, 0, 6, 20, owns=True)
    other.addstr(0, 0, "mine")
    assert text(window, 0).strip() == ""


# ------------------------------------------------------------- without curses


def test_windows_can_be_drawn_on_before_there_is_a_screen(window):
    """Which is what makes most of this file possible: a window is cells."""
    window.addstr(0, 0, "no terminal needed")
    assert text(window, 0).startswith("no terminal needed")


def test_refreshing_without_a_screen_says_so(window):
    with pytest.raises(stdlib_curses.error, match="initscr"):
        window.noutrefresh()


def test_newwin_without_a_screen_says_so():
    with pytest.raises(stdlib_curses.error, match="initscr"):
        tc.newwin(4, 4)


def test_isendwin_is_true_before_anything_starts():
    assert tc.isendwin()


def test_endwin_without_initscr_is_harmless():
    tc.endwin()


# ------------------------------------------------------------------ touching


def test_a_new_window_is_wholly_touched(window):
    """Which is what makes its first refresh paint its blank background over
    whatever was underneath - measured against the real curses, where a new
    window overlapping an older one hides it entirely."""
    assert all(window.is_linetouched(row) for row in range(6))
    assert window.is_wintouched()


def test_writing_touches_only_the_row_written(window):
    window.untouchwin()
    window.addstr(2, 0, "here")
    assert window.is_linetouched(2)
    assert not window.is_linetouched(1)


def test_untouchwin_clears_everything(window):
    window.untouchwin()
    assert not window.is_wintouched()


def test_touchline_marks_a_run(window):
    window.untouchwin()
    window.touchline(1, 2)
    assert [window.is_linetouched(row) for row in range(4)] == [
        False,
        True,
        True,
        False,
    ]


def test_touchline_can_unmark_a_run(window):
    window.touchline(0, 6, False)
    assert not window.is_wintouched()


def test_touchwin_marks_everything(window):
    window.untouchwin()
    window.touchwin()
    assert all(window.is_linetouched(row) for row in range(6))


def test_a_write_touches_only_the_columns_written(window):
    """The finer half of curses' refresh rule, and the one that is easy to
    miss: a program that writes five characters onto a line and refreshes
    leaves the rest of that line alone - so a panel's border further along
    survives. Copying whole lines wiped it, measured against the stdlib."""
    window.untouchwin()
    window.addstr(1, 3, "abc")
    assert window._touched == {1: (3, 5)}


def test_two_writes_on_a_row_cover_both(window):
    window.untouchwin()
    window.addstr(0, 2, "ab")
    window.addstr(0, 10, "cd")
    assert window._touched[0] == (2, 11)


def test_touchwin_marks_whole_rows(window):
    window.untouchwin()
    window.addstr(0, 2, "ab")
    window.touchwin()
    assert window._touched[0] == (0, 19)
