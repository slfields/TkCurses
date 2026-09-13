"""Tests for the Scale widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import DoubleVar, IntVar, Misc, Scale
from tkcurses._core.events import MOD_CTRL, KeyEvent, MouseEvent
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


def horizontal(root, **kw):
    """A scale 12 cells of trough long, laid out so positions are meaningful."""
    kw.setdefault("orient", "horizontal")
    kw.setdefault("from_", 0)
    kw.setdefault("to", 10)
    kw.setdefault("showvalue", False)
    scale = Scale(root, name=kw.pop("name", "s"), **kw)
    scale._allocate(Rect(0, 0, 14, 1))
    scale._map()
    return scale


# ---------------------------------------------------------------- the value


def test_a_scale_starts_at_from(root):
    assert Scale(root, name="s", from_=3, to=9).get() == 3


def test_set_and_get_round_trip(root):
    scale = Scale(root, name="s", from_=0, to=10)
    scale.set(7)
    assert scale.get() == 7


def test_a_value_past_the_end_is_clamped(root):
    scale = Scale(root, name="s", from_=0, to=10)
    scale.set(99)
    assert scale.get() == 10
    scale.set(-99)
    assert scale.get() == 0


def test_a_value_snaps_to_the_resolution(root):
    scale = Scale(root, name="s", from_=0, to=10, resolution=5)
    scale.set(7)
    assert scale.get() == 5
    scale.set(8)
    assert scale.get() == 10


def test_steps_are_measured_from_the_low_end(root):
    """A scale from 1 to 10 by 2 offers 1, 3, 5 - not 2, 4, 6."""
    scale = Scale(root, name="s", from_=1, to=10, resolution=2)
    scale.set(3.4)
    assert scale.get() == 3
    scale.set(4.6)
    assert scale.get() == 5


def test_a_fractional_resolution_keeps_its_decimals(root):
    scale = Scale(root, name="s", from_=0, to=1, resolution=0.1)
    scale.set(0.3)
    assert scale.get() == pytest.approx(0.3)
    assert scale._format(scale.get()) == "0.3"


def test_a_fractional_value_does_not_show_floating_point_dust(root):
    """0.30000000000000004 on screen is a scale nobody trusts."""
    scale = Scale(root, name="s", from_=0, to=1, resolution=0.1)
    for step in range(11):
        scale.set(step / 10)
        assert "0000" not in scale._format(scale.get())


def test_a_reversed_scale_runs_the_other_way(root):
    scale = Scale(root, name="s", from_=10, to=0)
    assert scale.get() == 10
    scale.set(99)
    assert scale.get() == 10
    scale.set(-1)
    assert scale.get() == 0


def test_digits_wins_over_the_resolution(root):
    scale = Scale(root, name="s", from_=0, to=1, resolution=0.25, digits=3)
    scale.set(0.25)
    assert scale._format(scale.get()) == "0.25"


# ------------------------------------------------------------------ command


def test_the_command_gets_the_value_as_text(root):
    """Tk passes a string, and code written against it expects one."""
    seen = []
    scale = Scale(root, name="s", from_=0, to=10, command=seen.append)
    scale.set(4)
    assert seen == ["4"]


def test_the_command_does_not_fire_when_nothing_changed(root):
    seen = []
    scale = Scale(root, name="s", from_=0, to=10, command=seen.append)
    scale.set(4)
    scale.set(4)
    assert seen == ["4"]


def test_a_snapped_away_change_does_not_fire_the_command(root):
    """Two positions that round to one value are one value."""
    seen = []
    scale = Scale(root, name="s", from_=0, to=10, resolution=5, command=seen.append)
    scale.set(4)
    scale.set(6)
    assert seen == ["5"]


# ----------------------------------------------------------------- variable


def test_the_variable_takes_the_value(root):
    variable = IntVar(root, 0)
    scale = Scale(root, name="s", from_=0, to=10, variable=variable)
    scale.set(6)
    assert variable.get() == 6


def test_writing_the_variable_moves_the_handle(root):
    variable = IntVar(root, 0)
    scale = Scale(root, name="s", from_=0, to=10, variable=variable)
    variable.set(8)
    assert scale.get() == 8


def test_a_variable_value_is_snapped_like_any_other(root):
    """No route into the value may leave the scale holding an unreachable one."""
    variable = DoubleVar(root, 0)
    scale = Scale(root, name="s", from_=0, to=10, resolution=5, variable=variable)
    variable.set(7)
    assert scale.get() == 5


def test_a_variable_out_of_range_is_clamped(root):
    variable = IntVar(root, 0)
    scale = Scale(root, name="s", from_=0, to=10, variable=variable)
    variable.set(500)
    assert scale.get() == 10


def test_rubbish_in_the_variable_is_ignored(root):
    """A shared variable may be written by something that is not a scale."""
    from tkcurses import StringVar

    variable = StringVar(root, "0")
    scale = Scale(root, name="s", from_=0, to=10, variable=variable)
    scale.set(4)
    variable.set("not a number")
    assert scale.get() == 4


def test_two_scales_share_one_variable(root):
    variable = IntVar(root, 0)
    first = Scale(root, name="a", from_=0, to=10, variable=variable)
    second = Scale(root, name="b", from_=0, to=10, variable=variable)
    first.set(3)
    assert second.get() == 3


# ----------------------------------------------------------------- geometry


def test_the_handle_sits_at_the_low_end_to_start(root):
    scale = horizontal(root)
    assert scale.identify(scale.coords()[0], 0) == "slider"


def test_the_handle_reaches_both_ends(root):
    scale = horizontal(root)
    low = scale.coords(0)
    scale.set(10)
    assert scale.coords()[0] > low[0]
    assert scale.identify(scale.coords()[0], 0) == "slider"


def test_identify_names_the_two_sides_of_the_trough(root):
    scale = horizontal(root)
    scale.set(5)
    handle = scale.coords()[0]
    assert scale.identify(handle - 2, 0) == "trough1"
    assert scale.identify(handle + 2, 0) == "trough2"


def test_identify_says_nothing_off_the_trough(root):
    scale = horizontal(root)
    assert scale.identify(99, 0) == ""


def test_a_vertical_scale_runs_down_the_widget(root):
    scale = Scale(root, name="s", from_=0, to=10, showvalue=False)
    scale._allocate(Rect(0, 0, 3, 14))
    scale._map()
    top = scale.coords(0)
    bottom = scale.coords(10)
    assert bottom[1] > top[1]
    assert bottom[0] == top[0]


def test_a_horizontal_scale_asks_for_its_length(root):
    assert Scale(root, name="s", orient="horizontal", length=30).winfo_reqwidth() >= 30


def test_a_vertical_scale_asks_for_its_length(root):
    assert Scale(root, name="s", length=30).winfo_reqheight() >= 30


def test_a_label_makes_room_for_itself(root):
    plain = Scale(root, name="a", orient="horizontal", showvalue=False)
    labelled = Scale(
        root, name="b", orient="horizontal", showvalue=False, label="Volume"
    )
    assert labelled.winfo_reqheight() > plain.winfo_reqheight()


def test_ticks_make_room_for_themselves(root):
    plain = Scale(root, name="a", orient="horizontal", showvalue=False)
    ticked = Scale(root, name="b", orient="horizontal", showvalue=False, tickinterval=5)
    assert ticked.winfo_reqheight() > plain.winfo_reqheight()


# -------------------------------------------------------------------- mouse


def test_a_click_on_the_trough_moves_the_handle(root):
    scale = horizontal(root)
    target = scale.coords(10)[0]
    scale._handle(MouseEvent(button=1, state="pressed", x=target, y=0))
    assert scale.get() == 10


def test_a_click_takes_the_focus(root):
    scale = horizontal(root)
    scale._handle(MouseEvent(button=1, state="pressed", x=2, y=0))
    assert scale.focus_get() is scale


def test_a_drag_follows_the_pointer(root):
    scale = horizontal(root)
    scale._handle(MouseEvent(button=1, state="pressed", x=scale.coords(0)[0], y=0))
    scale._handle(MouseEvent(button=0, state="drag", x=scale.coords(5)[0], y=0))
    assert scale.get() == 5
    scale._handle(MouseEvent(button=0, state="drag", x=scale.coords(9)[0], y=0))
    assert scale.get() == 9


def test_motion_without_a_press_does_nothing(root):
    scale = horizontal(root)
    scale._handle(MouseEvent(button=0, state="motion", x=scale.coords(9)[0], y=0))
    assert scale.get() == 0


def test_a_drag_stops_at_the_release(root):
    scale = horizontal(root)
    scale._handle(MouseEvent(button=1, state="pressed", x=scale.coords(0)[0], y=0))
    scale._handle(MouseEvent(button=1, state="released", x=scale.coords(0)[0], y=0))
    scale._handle(MouseEvent(button=0, state="motion", x=scale.coords(9)[0], y=0))
    assert scale.get() == 0


def test_a_drag_past_the_end_clamps_rather_than_escaping(root):
    scale = horizontal(root)
    scale._handle(MouseEvent(button=1, state="pressed", x=scale.coords(5)[0], y=0))
    scale._handle(MouseEvent(button=0, state="drag", x=500, y=0))
    assert scale.get() == 10


def test_a_disabled_scale_ignores_a_click(root):
    scale = horizontal(root, state="disabled")
    scale._handle(MouseEvent(button=1, state="pressed", x=scale.coords(10)[0], y=0))
    assert scale.get() == 0


# ----------------------------------------------------------------- keyboard


def test_the_arrows_step_by_the_resolution(root):
    scale = Scale(root, name="s", orient="horizontal", from_=0, to=10, resolution=2)
    scale._handle(KeyEvent(keysym="Right"))
    assert scale.get() == 2
    scale._handle(KeyEvent(keysym="Left"))
    assert scale.get() == 0


def test_a_vertical_scale_answers_the_other_two_arrows(root):
    scale = Scale(root, name="s", from_=0, to=10)
    scale._handle(KeyEvent(keysym="Down"))
    assert scale.get() == 1
    scale._handle(KeyEvent(keysym="Right"))
    assert scale.get() == 1


def test_control_steps_by_the_big_increment(root):
    scale = Scale(root, name="s", orient="horizontal", from_=0, to=100, bigincrement=25)
    scale._handle(KeyEvent(keysym="Right", modifiers=MOD_CTRL))
    assert scale.get() == 25


def test_the_big_increment_defaults_to_a_tenth_of_the_range(root):
    scale = Scale(root, name="s", orient="horizontal", from_=0, to=100)
    scale._handle(KeyEvent(keysym="Right", modifiers=MOD_CTRL))
    assert scale.get() == 10


def test_home_and_end_go_to_the_two_ends(root):
    scale = Scale(root, name="s", orient="horizontal", from_=0, to=10)
    scale._handle(KeyEvent(keysym="End"))
    assert scale.get() == 10
    scale._handle(KeyEvent(keysym="Home"))
    assert scale.get() == 0


def test_home_and_end_follow_a_reversed_scale(root):
    scale = Scale(root, name="s", orient="horizontal", from_=10, to=0)
    scale._handle(KeyEvent(keysym="End"))
    assert scale.get() == 0


def test_the_arrows_follow_a_reversed_scale(root):
    """Right moves towards `to`, whichever end that is."""
    scale = Scale(root, name="s", orient="horizontal", from_=10, to=0)
    scale._handle(KeyEvent(keysym="Right"))
    assert scale.get() == 9


def test_an_unrelated_key_is_left_alone(root):
    """Tab has to keep working, so the scale must not swallow every key."""
    scale = Scale(root, name="s", orient="horizontal")
    assert scale._handle(KeyEvent(keysym="Tab")) != "break"


def test_a_disabled_scale_ignores_the_keyboard(root):
    scale = Scale(root, name="s", orient="horizontal", state="disabled")
    scale._handle(KeyEvent(keysym="End"))
    assert scale.get() == 0


def test_a_scale_takes_the_focus(root):
    assert Scale(root, name="s")._takefocus is True
