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


def test_clicking_the_thumb_moves_to_that_fraction(bar):
    bar.set(0.0, 0.5)
    bar._handle(MouseEvent(button=1, state="pressed", x=0, y=3))
    assert bar.calls[0][0] == "moveto"


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
