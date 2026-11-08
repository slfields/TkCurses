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

"""Tests for menu placement, measurement and scrolling."""

from __future__ import annotations

import pytest

from tkcurses._core.menus import MenuEntry, measure_entries, place_popup, visible_window


def command(label, **options):
    return MenuEntry("command", {"label": label, **options})


# ----------------------------------------------------------------- measuring


def test_width_comes_from_the_longest_label():
    entries = [command("Open"), command("Save as...")]
    assert measure_entries(entries, indicators=False)[0] == len("Save as...")


def test_a_wide_label_is_measured_in_cells():
    """Three ideographs are six cells, and so is a fullwidth accelerator."""
    wide = "\u65e5\u672c\u8a9e"
    assert measure_entries([command(wide)], indicators=False)[0] == 6
    plain = measure_entries([command("a", accelerator="F1")], indicators=False)[0]
    fullwidth = measure_entries(
        [command("a", accelerator="\uff26\uff11")], indicators=False
    )[0]
    assert fullwidth == plain + 2


def test_height_is_one_row_per_entry():
    entries = [command("a"), MenuEntry("separator"), command("b")]
    assert measure_entries(entries, indicators=False)[1] == 3


def test_an_accelerator_makes_the_menu_wider():
    plain = measure_entries([command("Open")], indicators=False)[0]
    with_key = measure_entries(
        [command("Open", accelerator="Ctrl+O")], indicators=False
    )[0]
    assert with_key > plain + len("Ctrl+O")  # plus the gap between them


def test_indicators_are_kept_for_every_entry_once_any_needs_one():
    """Otherwise the labels step in and out down the menu."""
    plain = measure_entries([command("Open")], indicators=False)[0]
    assert measure_entries([command("Open")], indicators=True)[0] == plain + 4


def test_a_cascade_makes_room_for_its_arrow():
    plain = measure_entries([command("Open")], indicators=False)[0]
    cascade = measure_entries(
        [MenuEntry("cascade", {"label": "Open"})], indicators=False
    )[0]
    assert cascade > plain


def test_an_empty_menu_still_has_a_size():
    assert measure_entries([], indicators=False) == (1, 1)


# -------------------------------------------------------------- selectability


def test_a_separator_cannot_be_active():
    assert not MenuEntry("separator").selectable


def test_a_disabled_entry_cannot_be_active():
    """An arrow key landing on one would look like the key did nothing."""
    assert not command("Open", state="disabled").selectable


def test_an_ordinary_entry_can_be():
    assert command("Open").selectable


# ------------------------------------------------------------------ placement


def test_a_menu_with_room_is_placed_where_it_was_asked():
    assert place_popup(5, 3, 10, 6, 80, 24) == (5, 3, 6)


def test_a_menu_with_no_room_below_is_flipped_above():
    _, y, height = place_popup(5, 20, 10, 6, 80, 24)
    assert y == 14
    assert height == 6


def test_a_menu_with_no_room_right_is_pulled_left():
    x, _, _ = place_popup(75, 3, 10, 6, 80, 24)
    assert x == 65


def test_a_menu_flips_in_both_directions_at_once():
    x, y, _ = place_popup(75, 20, 10, 6, 80, 24)
    assert (x, y) == (65, 14)


def test_a_menu_with_room_on_neither_side_is_clamped_not_cut():
    """Only when the menu is bigger than the screen, not merely near an edge."""
    _, y, height = place_popup(2, 2, 10, 30, 80, 24)
    assert y == 0
    assert height == 24


def test_a_menu_taller_than_the_screen_reports_a_reduced_height():
    """Which is the caller's signal that it has to scroll."""
    assert place_popup(0, 0, 10, 100, 80, 24)[2] == 24


def test_a_menu_wider_than_the_screen_is_clamped_to_it():
    x, _, _ = place_popup(0, 0, 200, 4, 80, 24)
    assert x == 0


def test_a_point_off_the_screen_is_brought_back():
    x, y, _ = place_popup(-5, -5, 10, 4, 80, 24)
    assert (x, y) == (0, 0)


@pytest.mark.parametrize("point", [(0, 0), (79, 23), (40, 12), (79, 0), (0, 23)])
def test_a_menu_is_always_on_the_screen(point):
    x, y, height = place_popup(*point, 12, 8, 80, 24)
    assert 0 <= x <= 80 - 12
    assert 0 <= y <= 24 - height


# ------------------------------------------------------------------ scrolling


def test_a_menu_that_fits_does_not_scroll():
    assert visible_window(count=5, active=4, rows=10) == 0


def test_the_window_follows_the_active_entry_down():
    assert visible_window(count=20, active=12, rows=5) == 8


def test_the_window_stops_at_the_end():
    assert visible_window(count=20, active=19, rows=5) == 15


def test_the_window_never_goes_negative():
    assert visible_window(count=20, active=0, rows=5) == 0


def test_no_rows_shows_the_start():
    assert visible_window(count=20, active=10, rows=0) == 0


@pytest.mark.parametrize("active", range(0, 20, 3))
def test_the_active_entry_is_always_in_the_window(active):
    rows = 6
    first = visible_window(count=20, active=active, rows=rows)
    assert first <= active < first + rows
