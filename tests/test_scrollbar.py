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

"""Tests for the Scrollbar widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Misc, Scrollbar
from tkcurses._core.events import MouseEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def stack():
    return PanelStack(window_factory=stub_window, panel_factory=None)


@pytest.fixture
def root(stack):
    root = Misc()
    root.tk.panels = stack
    root._rect = Rect(0, 0, 40, 20)
    root._mapped = True
    return root


@pytest.fixture
def bar(root):
    """A vertical scrollbar twelve cells tall, with no border to complicate it."""
    calls = []
    bar = Scrollbar(root, name="sb", relief="flat", command=lambda *a: calls.append(a))
    bar._allocate(Rect(0, 0, 1, 12))
    bar._map()
    bar.calls = calls
    return bar


# -------------------------------------------------------------------- state


def test_a_new_scrollbar_shows_the_whole_range(bar):
    assert bar.get() == (0.0, 1.0)


def test_set_records_the_view(bar):
    bar.set(0.25, 0.5)
    assert bar.get() == (0.25, 0.5)


def test_values_outside_the_range_are_clamped(bar):
    """A widget reporting a view slightly past its end is common enough."""
    bar.set(-0.5, 2.0)
    assert bar.get() == (0.0, 1.0)


def test_a_backwards_range_is_not_allowed_to_invert(bar):
    bar.set(0.8, 0.2)
    first, last = bar.get()
    assert last >= first


# ------------------------------------------------------------------ the thumb


def test_the_thumb_covers_the_visible_fraction(bar):
    bar.set(0.0, 0.5)
    start, end = bar._thumb_range()
    assert start == 0
    assert end == 5  # half of ten trough cells


def test_the_thumb_moves_with_the_view(bar):
    bar.set(0.5, 1.0)
    start, _ = bar._thumb_range()
    assert start == 5


def test_the_thumb_is_never_shorter_than_one_cell(bar):
    """A view onto a very long document would otherwise round to nothing."""
    bar.set(0.0, 0.001)
    start, end = bar._thumb_range()
    assert end - start >= 1


# ------------------------------------------------------------- hit testing


def test_the_first_arrow_is_identified(bar):
    assert bar.identify(0, 0) == "arrow1"


def test_the_last_arrow_is_identified(bar):
    assert bar.identify(0, 11) == "arrow2"


def test_the_thumb_is_identified(bar):
    bar.set(0.0, 0.5)
    assert bar.identify(0, 2) == "slider"


def test_the_trough_beyond_the_thumb_is_identified(bar):
    bar.set(0.0, 0.2)
    assert bar.identify(0, 8) == "trough2"


def test_a_fraction_is_reported_along_the_trough(bar):
    assert bar.fraction(0, 1) == 0.0
    assert bar.fraction(0, 11) == 1.0


# ------------------------------------------------------------------ clicking


def test_clicking_the_first_arrow_scrolls_back_one_unit(bar):
    bar._handle(MouseEvent(button=1, state="pressed", x=0, y=0))
    assert bar.calls == [("scroll", -1, "units")]


def test_clicking_the_last_arrow_scrolls_on_one_unit(bar):
    bar._handle(MouseEvent(button=1, state="pressed", x=0, y=11))
    assert bar.calls == [("scroll", 1, "units")]


def test_clicking_the_trough_scrolls_a_page(bar):
    bar.set(0.0, 0.2)
    bar._handle(MouseEvent(button=1, state="pressed", x=0, y=9))
    assert bar.calls == [("scroll", 1, "pages")]


def test_pressing_the_thumb_moves_nothing(bar):
    """Measured against Tk 9.0: press the slider, release it without moving,
    and the command is not called at all. A press only starts a drag."""
    bar.set(0.0, 0.5)
    bar._handle(MouseEvent(button=1, state="pressed", x=0, y=3))
    bar._handle(MouseEvent(button=1, state="released", x=0, y=3))
    assert bar.calls == []


# ------------------------------------------------------------- dragging


def press(bar, y, x=0):
    bar._handle(MouseEvent(button=1, state="pressed", x=x, y=y))


def drag(bar, y, x=0):
    bar._handle(MouseEvent(button=1, state="drag", x=x, y=y))


def release(bar, y, x=0):
    bar._handle(MouseEvent(button=1, state="released", x=x, y=y))


def test_dragging_the_thumb_moves_by_the_distance_travelled(bar):
    """Tk's arithmetic: where the view started, plus the drag as a fraction
    of the trough. Ten cells of trough here, so two cells is 0.2."""
    bar.set(0.0, 0.5)
    press(bar, 3)
    drag(bar, 5)
    assert bar.calls == [("moveto", pytest.approx(0.2))]


def test_the_view_follows_the_pointer_rather_than_jumping_to_it(bar):
    """What moves is the distance travelled, so wherever within the thumb the
    press landed stays under the pointer."""
    bar.set(0.4, 0.9)
    press(bar, 8)  # near the bottom of the thumb, not its top
    drag(bar, 9)
    assert bar.calls == [("moveto", pytest.approx(0.5))]


def test_dragging_reports_every_step(bar):
    bar.set(0.0, 0.5)
    press(bar, 3)
    drag(bar, 4)
    drag(bar, 5)
    drag(bar, 6)
    assert [call[1] for call in bar.calls] == pytest.approx([0.1, 0.2, 0.3])


def test_a_drag_past_the_end_stops_at_the_end(bar):
    bar.set(0.0, 0.5)
    press(bar, 3)
    drag(bar, 40)
    drag(bar, -40)
    assert bar.calls == [("moveto", 1.0), ("moveto", 0.0)]


def test_releasing_ends_the_drag(bar):
    bar.set(0.0, 0.5)
    press(bar, 3)
    release(bar, 3)
    drag(bar, 9)
    assert bar.calls == []


def test_a_drag_that_began_on_the_trough_does_not_move_the_thumb(bar):
    """The trough press paged, and that is all it does - the pointer sliding
    afterwards must not turn a page into a drag."""
    bar.set(0.0, 0.2)
    press(bar, 9)
    bar.calls.clear()
    drag(bar, 5)
    assert bar.calls == []


def test_a_horizontal_scrollbar_drags_along_its_own_axis(root):
    calls: list[tuple] = []
    bar = Scrollbar(
        root,
        name="sb",
        orient="horizontal",
        relief="flat",
        command=lambda *args: calls.append(args),
    )
    bar._allocate(Rect(0, 0, 12, 1))
    bar._map()
    bar.set(0.0, 0.5)
    bar._handle(MouseEvent(button=1, state="pressed", x=3, y=0))
    bar._handle(MouseEvent(button=1, state="drag", x=5, y=0))
    assert calls == [("moveto", pytest.approx(0.2))]
    # Movement across the other axis is not movement at all.
    calls.clear()
    bar._handle(MouseEvent(button=1, state="drag", x=5, y=4))
    assert calls == [("moveto", pytest.approx(0.2))]


def test_delta_is_the_fraction_of_the_trough_a_distance_covers(bar):
    assert bar.delta(0, 10) == pytest.approx(1.0)
    assert bar.delta(0, 5) == pytest.approx(0.5)
    assert bar.delta(5, 0) == 0.0, "a vertical bar does not move sideways"


def test_delta_of_a_scrollbar_with_no_trough_is_nothing(root):
    bar = Scrollbar(root, name="sb", relief="flat")
    bar._allocate(Rect(0, 0, 1, 2))
    bar._map()
    assert bar.delta(0, 5) == 0.0


def test_a_scrollbar_without_a_command_ignores_clicks(root):
    bar = Scrollbar(root, name="sb", relief="flat")
    bar._allocate(Rect(0, 0, 1, 12))
    bar._map()
    bar._handle(MouseEvent(button=1, state="pressed", x=0, y=0))


# ------------------------------------------------------------------- layout


def test_a_vertical_scrollbar_is_one_cell_wide(root):
    bar = Scrollbar(root, name="sb", relief="flat")
    assert bar.winfo_reqwidth() == 1


def test_a_horizontal_scrollbar_is_one_cell_tall(root):
    bar = Scrollbar(root, name="sb", orient="horizontal", relief="flat")
    assert bar.winfo_reqheight() == 1


def test_a_scrollbar_does_not_take_the_focus(root):
    """Nothing on it can be operated by keyboard, so it must not be a tab stop."""
    assert Scrollbar(root, name="sb")._takefocus is False


def test_identify_takes_coordinates_within_the_widget(root):
    """Tk's identify takes widget-relative coordinates, not screen ones.

    Everything here used to subtract winfo_rootx, which is the same thing
    only for a widget at the origin - which is where every test had put it.
    """
    bar = Scrollbar(root, name="b", orient="vertical")
    bar._allocate(Rect(5, 4, 1, 12))
    bar._map()
    assert bar.winfo_rooty() == 4
    assert bar.identify(0, 0) == "arrow1"
    assert bar.identify(0, 11) == "arrow2"


def test_fraction_takes_coordinates_within_the_widget(root):
    bar = Scrollbar(root, name="b", orient="vertical")
    bar._allocate(Rect(5, 4, 1, 12))
    bar._map()
    assert bar.fraction(0, 1) == 0.0
    assert bar.fraction(0, 11) == 1.0


def test_a_one_cell_wide_bar_fills_every_row_it_was_given(root):
    """Its drawn length is its whole allocation, border or no border.

    Reported from UAT 40: a scrollbar placed nine rows tall drew seven cells
    and the eighth row still answered clicks, and a restyle showed blue running
    two rows past the last glyph.

    The cause was two predicates disagreeing. A vertical scrollbar is one cell
    WIDE, so ``_border_drawn`` is False - it wants two cells each way - while
    ``_bordered`` is True, because the relief is not flat. ``_length`` took two
    rows off for a border that ``_redraw`` then inset by nothing, so the glyphs
    ran out before the window did. ``_border_drawn``'s own docstring says
    everything measuring the space inside has to agree with the painting.

    Asserted across several heights rather than the one that was reported, so a
    fix that merely shifted the off-by-two would not pass.
    """
    for height in (3, 5, 9, 12):
        bar = Scrollbar(root, name=f"b{height}", orient="vertical")
        bar._allocate(Rect(0, 0, 1, height))
        bar._map()
        assert bar._length() == height, (
            f"a bar {height} rows tall measured {bar._length()} rows of glyphs, "
            "so the rest of it is drawn blank while still taking clicks"
        )
        # one arrow at each end, trough between: the cells actually painted
        assert 2 + bar._trough_bounds() == height


def test_a_horizontal_bar_fills_its_width_too(root):
    """The same arithmetic on the other axis, which is one cell TALL."""
    for width in (3, 8, 15):
        bar = Scrollbar(root, name=f"h{width}", orient="horizontal")
        bar._allocate(Rect(0, 0, width, 1))
        bar._map()
        assert bar._length() == width


# ---------------------------------------------------------------- activate


def test_no_element_is_active_at_first(bar):
    assert bar.activate() is None


@pytest.mark.parametrize("element", ["arrow1", "slider", "arrow2"])
def test_an_element_can_be_made_active(bar, element):
    assert bar.activate(element) is None
    assert bar.activate() == element


@pytest.mark.parametrize("other", ["trough1", "trough2", "bogus", ""])
def test_any_other_name_clears_it_rather_than_raising(bar, other):
    """Measured on Tk 9.0.2: a trough cannot be active, and nothing raises."""
    bar.activate("slider")
    bar.activate(other)
    assert bar.activate() is None
