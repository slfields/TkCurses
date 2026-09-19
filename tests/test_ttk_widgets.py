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

"""The themed widgets that only draw, where they need no terminal.

Every behaviour asserted here was measured against real ttk on Tk 9.0 first,
and the three that surprise say so where they are pinned.
"""

from __future__ import annotations

import pytest

from tkcurses import Misc
from tkcurses.ttk import Progressbar, Separator, Sizegrip, Style


@pytest.fixture
def root():
    return Misc()


# ------------------------------------------------------------- Separator


def test_a_separator_is_themed(root):
    assert Separator(root, name="s").winfo_class() == "TSeparator"


def test_a_separator_is_horizontal_unless_told_otherwise(root):
    assert Separator(root, name="s").cget("orient") == "horizontal"


def test_a_horizontal_separator_is_one_cell_tall(root):
    assert Separator(root, name="s").winfo_reqheight() == 1


def test_a_vertical_separator_is_one_cell_wide(root):
    assert Separator(root, name="s", orient="vertical").winfo_reqwidth() == 1


def test_changing_the_orientation_re_measures(root):
    separator = Separator(root, name="s")
    separator.configure(orient="vertical")
    assert separator.winfo_reqwidth() == 1


# -------------------------------------------------------------- Sizegrip


def test_a_sizegrip_is_themed(root):
    assert Sizegrip(root, name="g").winfo_class() == "TSizegrip"


def test_a_sizegrip_asks_for_one_cell(root):
    grip = Sizegrip(root, name="g")
    assert (grip.winfo_reqwidth(), grip.winfo_reqheight()) == (1, 1)


# ----------------------------------------------------------- Progressbar


@pytest.fixture
def bar(root):
    return Progressbar(root, name="p", length=20)


def test_a_progressbar_is_themed(bar):
    assert bar.winfo_class() == "TProgressbar"


def test_the_defaults_are_tkinters(root):
    bar = Progressbar(root, name="p")
    assert bar.cget("mode") == "determinate"
    assert bar.cget("maximum") == 100.0
    assert bar.cget("value") == 0.0
    assert bar.cget("orient") == "horizontal"


def test_a_bar_is_as_long_as_its_length(root):
    assert Progressbar(root, name="p", length=30).winfo_reqwidth() == 30


def test_a_vertical_bar_is_as_tall_as_its_length(root):
    bar = Progressbar(root, name="p", length=8, orient="vertical")
    assert (bar.winfo_reqwidth(), bar.winfo_reqheight()) == (1, 8)


# ------------------------------------------------------ step(), measured


def test_step_moves_one_by_default(bar):
    """Tk's default amount is 1.0."""
    bar.step()
    assert bar.cget("value") == 1.0


def test_step_takes_an_amount(bar):
    bar.step(5)
    assert bar.cget("value") == 5.0


def test_determinate_step_wraps_at_the_maximum(bar):
    """Measured against Tk 9.0: 90 + step(30) with maximum 100 lands on 20,
    and the whole sequence from zero is 30 60 90 20 50 80."""
    seen = []
    for _ in range(6):
        bar.step(30)
        seen.append(bar.cget("value"))
    assert seen == [30.0, 60.0, 90.0, 20.0, 50.0, 80.0]


def test_indeterminate_step_does_not_wrap_at_all(bar):
    """The one that surprises. Measured: the same sequence in indeterminate
    mode is 30 60 90 120 150 180 - it accumulates without bound, and it is
    the *display* that takes it modulo a sweep."""
    bar.configure(mode="indeterminate")
    seen = []
    for _ in range(6):
        bar.step(30)
        seen.append(bar.cget("value"))
    assert seen == [30.0, 60.0, 90.0, 120.0, 150.0, 180.0]


def test_setting_the_value_directly_does_not_wrap(bar):
    """Measured: configure(value=150) on a bar whose maximum is 100 leaves
    it at 150. Only step wraps."""
    bar.configure(value=150)
    assert bar.cget("value") == 150


# ------------------------------------------------- start() and stop()


def test_stop_resets_the_value_to_zero(bar):
    """Not a pause. Measured against Tk 9.0, where stop() zeroes it."""
    bar.configure(value=42)
    bar.stop()
    assert bar.cget("value") == 0.0


def test_stop_on_a_bar_that_was_never_started_is_harmless(bar):
    bar.stop()
    assert bar.cget("value") == 0.0


def test_starting_twice_does_not_stack_two_timers(bar):
    """Or the bar would step twice as fast for the rest of its life."""
    bar.start(1000)
    first = bar._timer
    bar.start(1000)
    assert bar._timer is first
    bar.stop()


def test_stop_cancels_the_timer(bar):
    bar.start(1000)
    bar.stop()
    assert bar._timer is None


# ------------------------------------------------------------- the fill


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 0), (25, 5), (50, 10), (100, 20), (150, 20)],
)
def test_a_determinate_bar_fills_in_proportion(bar, value, expected):
    """And a value past the maximum fills it rather than overflowing."""
    bar.configure(value=value)
    assert bar._filled_cells(20) == (0, expected)


def test_an_indeterminate_block_sweeps_out_and_back(bar):
    """Which is what makes it bounce rather than jump back to the start:
    the value is taken modulo twice the maximum, and the second half of that
    cycle is the first half reflected."""
    bar.configure(mode="indeterminate")
    positions = []
    for value in (0, 50, 100, 150, 200):
        bar.configure(value=value)
        positions.append(bar._filled_cells(20)[0])
    assert positions[0] == 0
    assert positions[2] == max(positions), "furthest out at the maximum"
    assert positions[4] == 0, "back where it started after a full cycle"
    assert positions[1] == positions[3], "the way out and the way back match"


def test_an_indeterminate_block_is_never_the_whole_bar(bar):
    bar.configure(mode="indeterminate")
    for value in range(0, 200, 7):
        bar.configure(value=value)
        _, count = bar._filled_cells(20)
        assert 0 < count < 20


# --------------------------------------------------------- and the style


def test_the_themed_widgets_take_a_style_option(root):
    for widget in (
        Separator(root, name="s"),
        Sizegrip(root, name="g"),
        Progressbar(root, name="p"),
    ):
        assert widget.cget("style") == ""


def test_configuring_a_class_reaches_every_bar_of_it(root):
    bars = [Progressbar(root, name=f"p{index}") for index in range(3)]
    Style(root).configure("TProgressbar", foreground="green")
    assert [b._styled("foreground") for b in bars] == ["green"] * 3


def test_a_bar_with_its_own_style_still_inherits_the_class(root):
    style = Style(root)
    style.configure("TProgressbar", background="trough")
    style.configure("Danger.TProgressbar", foreground="red")
    bar = Progressbar(root, name="p", style="Danger.TProgressbar")
    assert bar._styled("foreground") == "red"
    assert bar._styled("background") == "trough"


# ------------------------------------------------- which window a grip owns


def test_a_grip_on_a_toplevel_has_a_window_to_resize(root):
    import tkcurses

    top = tkcurses.Toplevel(root, name="t")
    grip = Sizegrip(top, name="g")
    assert grip._resizable_window() is top


def test_a_grip_on_the_root_has_none(root):
    """The one case the first version generalised from, and the only one it
    was right about: the root's size *is* the terminal's, and nothing an
    application draws changes that. Every other window here is the
    library's own."""
    assert Sizegrip(root, name="g")._resizable_window() is None


def test_a_window_locked_against_resizing_has_none(root):
    import tkcurses

    top = tkcurses.Toplevel(root, name="t")
    top.wm_resizable(False, False)
    assert Sizegrip(top, name="g")._resizable_window() is None


def test_a_window_locked_on_one_axis_is_still_resizable(root):
    import tkcurses

    top = tkcurses.Toplevel(root, name="t")
    top.wm_resizable(False, True)
    assert Sizegrip(top, name="g")._resizable_window() is top


def test_a_grip_starts_with_no_drag_in_progress(root):
    import tkcurses

    top = tkcurses.Toplevel(root, name="t")
    assert Sizegrip(top, name="g")._drag is None
