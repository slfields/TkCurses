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

"""Auto-repeat while a mouse button is held, and the scrollbar's jump.
TkCurses-gm66.6.

Button, Scale, Scrollbar and Spinbox, each following its own Tk procedure:
``tk::ButtonAutoInvoke``, ``tk::ScaleIncrement``, ``tk::ScrollSelect`` and
``tk::spinbox::Invoke``. Time is a clock the test moves, so "held for 450ms"
is exact and the suite does not sleep.
"""

from __future__ import annotations

import pytest

import tkcurses
from tkcurses import Misc, TclError, ttk
from tkcurses._core.geometry import Rect
from tkcurses._core.input import MouseEvent
from tkcurses._core.timers import AfterQueue

#: The options this issue adds and Tk 9.0.2's defaults, measured.
DEFAULTS = {
    ("Button", "repeatdelay"): 0,
    ("Button", "repeatinterval"): 0,
    ("Scale", "repeatdelay"): 300,
    ("Scale", "repeatinterval"): 100,
    ("Scrollbar", "jump"): 0,
    ("Scrollbar", "repeatdelay"): 300,
    ("Scrollbar", "repeatinterval"): 100,
    ("Spinbox", "repeatdelay"): 400,
    ("Spinbox", "repeatinterval"): 100,
}

TIMINGS = [key for key in DEFAULTS if key[1] != "jump"]


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture
def root():
    return Misc()


@pytest.fixture
def clock(root):
    clock = Clock()
    root.tk.timers = AfterQueue(clock=clock)
    return clock


def hold(root, clock, ms):
    """Let ``ms`` milliseconds pass, a millisecond at a time."""
    for _ in range(ms):
        clock.now += 0.001
        root.tk.timers.run_due()


def laid_out(widget, width, height=1):
    widget._allocate(Rect(0, 0, width, height))
    widget._map()
    return widget


def press(widget, x, y=0, button=1):
    widget._handle(MouseEvent(button=button, state="pressed", x=x, y=y))


def release(widget, x, y=0, button=1):
    widget._handle(MouseEvent(button=button, state="released", x=x, y=y))


def move(widget, x, y=0):
    """Motion with button 1 held, which is what a drag reports."""
    widget._handle(MouseEvent(button=1, state="drag", x=x, y=y))


# ----------------------------------------------------------------- options


@pytest.mark.parametrize(("name", "option"), list(DEFAULTS))
def test_each_is_taken_with_tks_default(root, name, option):
    assert getattr(tkcurses, name)(root).cget(option) == DEFAULTS[(name, option)]


@pytest.mark.parametrize(("name", "option"), TIMINGS)
def test_a_timing_is_an_integer_as_tk_takes_it(root, name, option):
    widget = getattr(tkcurses, name)(root, **{option: " 7 "})
    assert widget.cget(option) == 7
    widget.configure(**{option: -5})
    assert widget.cget(option) == -5
    for bad in ("x", "2.5", ""):
        with pytest.raises(TclError, match=f'expected integer but got "{bad}"'):
            widget.configure(**{option: bad})


def test_jump_is_a_boolean(root):
    bar = tkcurses.Scrollbar(root, jump="yes")
    assert bar.cget("jump") == 1
    with pytest.raises(TclError, match='expected boolean value but got "x"'):
        bar.configure(jump="x")


# ------------------------------------------------------------------ Button


def button(root, **kw):
    count = []
    widget = laid_out(
        tkcurses.Button(root, text="Go", command=lambda: count.append(1), **kw), 10, 3
    )
    return widget, count


def test_a_button_does_not_repeat_by_default(root, clock):
    widget, count = button(root)
    press(widget, 3, 1)
    # Under PRESS_RECOVERY_MS: past it, a press with no release in sight is
    # taken for a lost release and put back up.
    hold(root, clock, 500)
    assert count == []
    release(widget, 3, 1)
    assert count == [1]


def test_a_held_button_repeats_after_the_delay(root, clock):
    """``tk::ButtonAutoInvoke``: at 300, then every 100."""
    widget, count = button(root, repeatdelay=300, repeatinterval=100)
    press(widget, 3, 1)
    hold(root, clock, 299)
    assert count == []
    hold(root, clock, 1)
    assert len(count) == 1
    hold(root, clock, 250)
    assert len(count) == 3
    release(widget, 3, 1)
    hold(root, clock, 500)
    assert len(count) == 3, "the release stops it and does not invoke again"


def test_a_short_press_on_a_repeating_button_invokes_once(root, clock):
    widget, count = button(root, repeatdelay=300, repeatinterval=100)
    press(widget, 3, 1)
    hold(root, clock, 100)
    release(widget, 3, 1)
    assert count == [1]
    hold(root, clock, 1000)
    assert count == [1]


def test_without_an_interval_a_button_invokes_once_more(root, clock):
    widget, count = button(root, repeatdelay=300)
    press(widget, 3, 1)
    hold(root, clock, 1000)
    assert count == [1]
    release(widget, 3, 1)
    assert count == [1]


def test_the_pointer_off_the_button_pauses_it(root, clock):
    """Tk's ``Priv(window)``: the repeat runs on, invoking only over it."""
    widget, count = button(root, repeatdelay=100, repeatinterval=100)
    press(widget, 3, 1)
    move(widget, 30, 1)
    hold(root, clock, 450)
    assert count == []
    move(widget, 3, 1)
    hold(root, clock, 100)
    assert len(count) == 1


def test_a_held_repeating_button_stays_down(root, clock):
    """The lost-release recovery would put it up mid-hold; it is not armed."""
    widget, _ = button(root, repeatdelay=300, repeatinterval=100)
    press(widget, 3, 1)
    hold(root, clock, 1500)
    assert widget._pressed


def test_a_checkbutton_shares_the_press_and_does_not_repeat(root, clock):
    count = []
    check = laid_out(tkcurses.Checkbutton(root, command=lambda: count.append(1)), 8)
    press(check, 1)
    hold(root, clock, 500)
    release(check, 1)
    assert count == [1]


# ------------------------------------------------------------------- Scale


def scale(root, **kw):
    widget = tkcurses.Scale(
        root, orient="horizontal", from_=0, to=10, showvalue=False, **kw
    )
    return laid_out(widget, 14)


def test_a_held_trough_steps_again_and_again(root, clock):
    """``tk::ScaleIncrement``: once, then at 300, then every 100."""
    widget = scale(root)
    press(widget, 12)
    assert widget.get() == 1
    hold(root, clock, 299)
    assert widget.get() == 1
    hold(root, clock, 1)
    assert widget.get() == 2
    hold(root, clock, 300)
    assert widget.get() == 5
    release(widget, 12)
    hold(root, clock, 500)
    assert widget.get() == 5


def test_the_near_side_steps_towards_from(root, clock):
    widget = scale(root)
    widget.set(5)
    press(widget, 1)
    assert widget.get() == 4


@pytest.mark.parametrize(("side", "expected"), [(12, 4), (1, 6)])
def test_a_reversed_scale_steps_towards_the_click(root, clock, side, expected):
    widget = laid_out(
        tkcurses.Scale(root, orient="horizontal", from_=10, to=0, showvalue=False),
        14,
    )
    widget.set(5)
    press(widget, side)
    assert widget.get() == expected


def test_the_steps_are_the_resolution(root, clock):
    widget = scale(root, resolution=2)
    press(widget, 12)
    assert widget.get() == 2


def test_holding_the_trough_does_not_drag(root, clock):
    widget = scale(root)
    press(widget, 12)
    move(widget, 6)
    assert widget.get() == 1


def test_a_held_handle_drags_from_where_it_was_taken(root, clock):
    """Tk's ``Priv(deltaX)``: the handle does not jump to the pointer."""
    widget = scale(root, sliderlength=3)
    widget.set(5)
    middle = widget.coords()[0]
    press(widget, middle - 1)  # the handle's first cell, not its middle
    assert widget.get() == 5
    move(widget, middle)
    assert widget.coords()[0] == middle + 1, "moved one cell, as the pointer did"


def test_button_two_drags_from_the_pointer_after_a_handle_drag(root, clock):
    """A jump puts the handle's middle under the pointer, whatever offset an
    earlier drag of the handle left behind."""
    widget = scale(root, sliderlength=3)
    widget.set(5)
    middle = widget.coords()[0]
    press(widget, middle - 1)
    release(widget, middle - 1)
    press(widget, 3, button=2)
    move(widget, 4)
    assert widget.coords()[0] == 4
    release(widget, 4, button=2)


def test_the_handle_does_not_repeat(root, clock):
    widget = scale(root)
    press(widget, 1)
    hold(root, clock, 1000)
    assert widget.get() == 0


# --------------------------------------------------------------- Scrollbar


def scrollbar(root, **kw):
    calls = []
    bar = tkcurses.Scrollbar(root, command=lambda *a: calls.append(a), **kw)
    laid_out(bar, 1, 10)
    bar.set(0.2, 0.4)
    return bar, calls


@pytest.mark.parametrize(
    ("row", "step"),
    [(0, (-1, "units")), (9, (1, "units")), (1, (-1, "pages")), (8, (1, "pages"))],
)
def test_a_held_part_scrolls_again_and_again(root, clock, row, step):
    """``tk::ScrollSelect``: once, then at 300, then every 100."""
    bar, calls = scrollbar(root)
    press(bar, 0, row)
    assert calls == [("scroll", *step)]
    hold(root, clock, 299)
    assert len(calls) == 1
    hold(root, clock, 201)
    assert len(calls) == 4
    release(bar, 0, row)
    hold(root, clock, 500)
    assert len(calls) == 4


def test_without_a_delay_a_scrollbar_does_not_repeat(root, clock):
    bar, calls = scrollbar(root, repeatdelay=0)
    press(bar, 0, 0)
    hold(root, clock, 1000)
    assert len(calls) == 1


def test_without_an_interval_it_scrolls_once_more(root, clock):
    """Tk would schedule at 0 ms for ever; here the repeat stops."""
    bar, calls = scrollbar(root, repeatinterval=0)
    press(bar, 0, 0)
    hold(root, clock, 1000)
    assert len(calls) == 2


def test_a_drag_scrolls_as_it_goes_without_jump(root, clock):
    bar, calls = scrollbar(root)
    press(bar, 0, 3)
    move(bar, 0, 5)
    assert calls and calls[-1][0] == "moveto"
    release(bar, 0, 5)


def test_with_jump_the_drag_scrolls_once_at_the_release(root, clock):
    """``tk::ScrollDrag`` and ``tk::ScrollEndDrag`` with ``-jump``."""
    bar, calls = scrollbar(root, jump=True)
    press(bar, 0, 3)
    move(bar, 0, 4)
    move(bar, 0, 5)
    assert calls == []
    assert bar.get() == pytest.approx((0.45, 0.65))
    release(bar, 0, 5)
    assert calls == [("moveto", pytest.approx(0.45))]


def test_a_ttk_scrollbar_neither_repeats_nor_jumps(root, clock):
    calls = []
    with pytest.raises(TclError, match='unknown option "-jump"'):
        ttk.Scrollbar(root, jump=True)
    bar = ttk.Scrollbar(root, command=lambda *a: calls.append(a))
    laid_out(bar, 1, 10)
    bar.set(0.2, 0.4)
    press(bar, 0, 0)
    hold(root, clock, 1000)
    release(bar, 0, 0)
    assert len(calls) == 1
    press(bar, 0, 3)
    move(bar, 0, 5)
    assert calls[-1][0] == "moveto", "the drag scrolls as it goes"


# ----------------------------------------------------------------- Spinbox


def spinbox(root, **kw):
    widget = tkcurses.Spinbox(root, from_=0, to=99, width=10, **kw)
    return laid_out(widget, 12)


def test_an_arrow_steps_when_released(root, clock):
    """``tk::spinbox::ButtonUp``, not the press."""
    widget = spinbox(root)
    up, _ = widget._arrow_columns()
    press(widget, up)
    assert widget.get() == "0"
    release(widget, up)
    assert widget.get() == "1"


def test_a_held_arrow_steps_again_and_again(root, clock):
    """``tk::spinbox::Invoke``: at 400, then every 100, and none on release."""
    widget = spinbox(root)
    _, down = widget._arrow_columns()
    widget.delete(0, "end")
    widget.insert(0, "50")
    press(widget, down)
    hold(root, clock, 399)
    assert widget.get() == "50"
    hold(root, clock, 1)
    assert widget.get() == "49"
    hold(root, clock, 200)
    assert widget.get() == "47"
    release(widget, down)
    assert widget.get() == "47"
    hold(root, clock, 500)
    assert widget.get() == "47", "the release stops it"


def test_a_release_off_the_arrow_still_steps(root, clock):
    widget = spinbox(root)
    up, _ = widget._arrow_columns()
    press(widget, up)
    release(widget, 2)
    assert widget.get() == "1"


def test_a_ttk_spinbox_steps_on_the_press(root, clock):
    widget = laid_out(ttk.Spinbox(root, from_=0, to=99, width=10), 12, 3)
    # A ttk spinbox starts empty, as Tk's does - TkCurses-fdl9.
    widget.set("0")
    up, _ = widget._arrow_columns()
    press(widget, up, 1)
    assert widget.get() == "1"
    hold(root, clock, 1000)
    release(widget, up, 1)
    assert widget.get() == "1"


# ------------------------------------------------------- the lost release


def test_a_second_press_stops_a_repeat_whose_release_was_lost(clock):
    """No second press can come while the first is held, so one means the
    release went missing; without this the button would repeat for ever."""
    app = tkcurses.Tk(useTk=False)
    app.tk.timers = AfterQueue(clock=clock)
    count = []
    widget = tkcurses.Button(
        app,
        text="Go",
        repeatdelay=100,
        repeatinterval=100,
        command=lambda: count.append(1),
    )
    laid_out(widget, 10, 3)
    app._mouse_owner = widget
    press(widget, 3, 1)
    hold(app, clock, 250)
    assert len(count) == 2
    app._route(MouseEvent(button=1, state="pressed", x=30, y=10))
    hold(app, clock, 1000)
    assert len(count) == 2
    assert not widget._pressed
    app.destroy()
