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

"""ttk.Progressbar's ``phase``, replaying Tk 9.0.2 measured through tkinter.

The count follows AnimationEnabled, AnimateProgressProc and CheckAnimation in
ttkProgress.c. A tick is :meth:`_animate`, called here by hand; the timer that
calls it in a running program is checked by its handle.
"""

from __future__ import annotations

import pytest

import tkcurses as tk
from tkcurses import ttk


@pytest.fixture
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


def ticks(bar, count):
    seen = []
    for _ in range(count):
        bar._animate()
        seen.append(bar.cget("phase"))
    return seen


def test_it_is_an_integer_starting_at_zero(root):
    bar = ttk.Progressbar(root)
    assert bar.configure("phase") == ("phase", "phase", "Phase", 0, 0)


@pytest.mark.parametrize(
    ("given", "read"),
    [("0x10", 16), (" 7 ", 7), ("-3", -3), ("1_0", 10), ("0b11", 3),
     (2**32 - 1, 2**32 - 1), (-(2**31), -(2**31))],
)  # fmt: skip
def test_tcls_integers_are_taken(root, given, read):
    bar = ttk.Progressbar(root, phase=given)
    assert bar.cget("phase") == read


@pytest.mark.parametrize(
    ("given", "message"),
    [("x", 'expected integer but got "x"'),
     ("1.5", 'expected integer but got "1.5"'),
     ("1e3", 'expected integer but got "1e3"'),
     ("", 'expected integer but got ""'),
     (2**32, "integer value too large to represent"),
     (-(2**31) - 1, "integer value too large to represent")],
)  # fmt: skip
def test_anything_else_is_refused_in_tks_words(root, given, message):
    bar = ttk.Progressbar(root, phase=4)
    with pytest.raises(tk.TclError, match=message):
        bar.configure(phase=given)
    assert bar.cget("phase") == 4


def test_no_built_in_theme_animates_it(root):
    """Measured: start() on an indeterminate bar leaves phase at 0."""
    bar = ttk.Progressbar(root, mode="indeterminate")
    bar.start(10)
    assert bar._phase_timer is None
    assert ticks(bar, 3) == [0, 0, 0]
    bar.stop()


def test_a_style_period_counts_it_round_to_maxphase(root):
    """Measured: [0, 1, 2, 3, 0, ...] with maxphase 3, start() or not."""
    ttk.Style(root).configure("Anim.Horizontal.TProgressbar", period=20, maxphase=3)
    bar = ttk.Progressbar(
        root, style="Anim.Horizontal.TProgressbar", mode="indeterminate"
    )
    assert bar._phase_timer is not None
    assert ticks(bar, 6) == [1, 2, 3, 0, 1, 2]


def test_the_default_style_is_the_oriented_one(root):
    """Tk's bar draws from Horizontal.TProgressbar, which inherits
    TProgressbar: a period on either reaches a bar with no style."""
    style = ttk.Style(root)
    style.configure("TProgressbar", period=20, maxphase=2)
    assert ticks(ttk.Progressbar(root, mode="indeterminate"), 3) == [1, 2, 0]
    style.configure("Horizontal.TProgressbar", maxphase=1)
    assert ticks(ttk.Progressbar(root, mode="indeterminate"), 3) == [1, 0, 1]
    vertical = ttk.Progressbar(root, mode="indeterminate", orient="vertical")
    assert ticks(vertical, 3) == [1, 2, 0]


def test_a_phase_past_maxphase_comes_round_to_zero(root):
    """Measured: phase=99 under maxphase 3 goes 99, then 0, 1, 2."""
    ttk.Style(root).configure("TProgressbar", period=20, maxphase=3)
    bar = ttk.Progressbar(root, mode="indeterminate", phase=99)
    assert ticks(bar, 3) == [0, 1, 2]


def test_without_maxphase_it_stays_at_zero(root):
    ttk.Style(root).configure("TProgressbar", period=20)
    assert ticks(ttk.Progressbar(root, mode="indeterminate"), 3) == [0, 0, 0]


def test_a_period_that_is_not_an_integer_is_none(root):
    ttk.Style(root).configure("TProgressbar", period="x", maxphase=3)
    bar = ttk.Progressbar(root, mode="indeterminate")
    assert bar._phase_timer is None


def test_a_determinate_bar_does_not_count(root):
    """Measured: phase 3, determinate, a style period: it stays 3."""
    ttk.Style(root).configure("TProgressbar", period=20, maxphase=5)
    bar = ttk.Progressbar(root, phase=3)
    assert bar._phase_timer is None
    assert ticks(bar, 2) == [3, 3]
    bar.configure(mode="indeterminate")
    assert bar._phase_timer is not None
    bar.configure(mode="determinate")
    assert bar._phase_timer is None


def test_a_style_change_waits_for_the_next_configure(root):
    """Measured: a period given to a bar's style while it is showing does
    nothing until the bar is configured; a period of 0 stops it."""
    style = ttk.Style(root)
    bar = ttk.Progressbar(root, mode="indeterminate")
    style.configure("TProgressbar", period=20, maxphase=5)
    assert bar._phase_timer is None
    bar.configure(length=30)
    assert bar._phase_timer is not None
    style.configure("TProgressbar", period=0)
    assert ticks(bar, 1) == [0]
    assert bar._phase_timer is None


@pytest.mark.tty
def test_the_count_runs_in_a_real_loop(terminal, tmp_path):
    """The timer, not a hand-called tick: the label shows every phase
    from 0 to 3 in turn, and comes round to 0."""
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
ttk.Style(root).configure("TProgressbar", period=100, maxphase=3)
bar = ttk.Progressbar(root, mode="indeterminate")
bar.pack()
said = tkcurses.Label(root, text="")
said.pack()
seen = []

def watch():
    phase = bar.cget("phase")
    if not seen or seen[-1] != phase:
        seen.append(phase)
    said.configure(text=" ".join(map(str, seen[-6:])))
    root.after(5, watch)

watch()
root.after(5000, root.quit)
root.mainloop()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("0 1 2 3 0")
