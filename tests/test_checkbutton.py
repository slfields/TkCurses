"""Tests for the Checkbutton widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import BooleanVar, Checkbutton, IntVar, Misc, StringVar
from tkcurses._core.events import KeyEvent, MouseEvent
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
    root._rect = Rect(0, 0, 40, 12)
    root._mapped = True
    return root


def laid_out(widget, width=16, height=1):
    """Give a widget a size, so a click can land inside it."""
    widget._allocate(Rect(0, 0, width, height))
    widget._map()
    return widget


def click(widget, x=1, y=0):
    """Press and release button 1 over a widget, as the loop would deliver it."""
    if widget.winfo_width() == 0:
        laid_out(widget)
    widget._handle(MouseEvent(button=1, state="pressed", x=x, y=y))
    widget._handle(MouseEvent(button=1, state="released", x=x, y=y))


# ---------------------------------------------------------------- the value


def test_a_checkbutton_without_a_variable_gets_one(root):
    """Otherwise a checkbutton made with no arguments could never be ticked."""
    box = Checkbutton(root, name="c", text="Wrap")
    assert box._options["variable"] is not None
    assert box._indicator_state == "off"


def test_two_checkbuttons_without_variables_do_not_share_one(root):
    first = Checkbutton(root, name="a", text="One")
    second = Checkbutton(root, name="b", text="Two")
    first.select()
    assert second._indicator_state == "off"


def test_select_and_deselect_write_the_variable(root):
    variable = IntVar(root, 0)
    box = Checkbutton(root, name="c", variable=variable)
    box.select()
    assert variable.get() == 1
    box.deselect()
    assert variable.get() == 0


def test_toggle_flips_the_value(root):
    variable = IntVar(root, 0)
    box = Checkbutton(root, name="c", variable=variable)
    box.toggle()
    assert variable.get() == 1
    box.toggle()
    assert variable.get() == 0


def test_custom_on_and_off_values_are_used(root):
    variable = StringVar(root, "no")
    box = Checkbutton(root, name="c", variable=variable, onvalue="yes", offvalue="no")
    box.select()
    assert variable.get() == "yes"
    assert box._indicator_state == "on"


def test_a_variable_set_from_code_moves_the_button(root):
    """The point of the variable: the widget follows it, not the other way."""
    variable = IntVar(root, 0)
    box = Checkbutton(root, name="c", variable=variable)
    variable.set(1)
    assert box._indicator_state == "on"


def test_two_checkbuttons_share_one_variable(root):
    variable = IntVar(root, 0)
    first = Checkbutton(root, name="a", variable=variable)
    second = Checkbutton(root, name="b", variable=variable)
    first.select()
    assert second._indicator_state == "on"


def test_a_string_variable_matches_an_integer_onvalue(root):
    """Tcl has one type, so "1" and 1 are the same value to a checkbutton."""
    variable = StringVar(root, "1")
    box = Checkbutton(root, name="c", variable=variable)
    assert box._indicator_state == "on"


def test_a_boolean_variable_works_unchanged(root):
    variable = BooleanVar(root, False)
    box = Checkbutton(root, name="c", variable=variable, onvalue=True, offvalue=False)
    box.toggle()
    assert variable.get() is True


def test_a_value_that_is_neither_reads_as_the_third_state(root):
    variable = StringVar(root, "some")
    box = Checkbutton(root, name="c", variable=variable, tristatevalue="some")
    assert box._indicator_state == "tristate"


def test_the_third_state_turns_on_rather_than_off(root):
    """Tk's rule: from "some of them" a click means "all of them"."""
    variable = StringVar(root, "some")
    box = Checkbutton(root, name="c", variable=variable, tristatevalue="some")
    box.toggle()
    assert variable.get() == "1"
    assert box._indicator_state == "on"


def test_an_unrecognised_value_reads_as_off(root):
    variable = StringVar(root, "rubbish")
    box = Checkbutton(root, name="c", variable=variable)
    assert box._indicator_state == "off"


def test_changing_the_variable_drops_the_old_trace(root):
    """A widget still answering its previous variable would repaint on noise."""
    first, second = IntVar(root, 0), IntVar(root, 0)
    box = Checkbutton(root, name="c", variable=first)
    box.configure(variable=second)
    assert box._value_trace is not None
    assert box._value_trace[0] is second
    assert first.trace_info() == []


# ------------------------------------------------------------------ invoking


def test_invoke_toggles_and_runs_the_command(root):
    calls = []
    variable = IntVar(root, 0)
    box = Checkbutton(
        root, name="c", variable=variable, command=lambda: calls.append(variable.get())
    )
    box.invoke()
    assert calls == [1]


def test_invoke_returns_what_the_command_returns(root):
    assert Checkbutton(root, name="c", command=lambda: "result").invoke() == "result"


def test_invoke_without_a_command_is_harmless(root):
    assert Checkbutton(root, name="c", text="Wrap").invoke() is None


def test_a_disabled_checkbutton_does_not_toggle(root):
    variable = IntVar(root, 0)
    box = Checkbutton(root, name="c", variable=variable, state="disabled")
    box.invoke()
    assert variable.get() == 0


def test_select_still_works_while_disabled(root):
    """Disabling refuses the user, not the program: Tk's select() still sets."""
    variable = IntVar(root, 0)
    box = Checkbutton(root, name="c", variable=variable, state="disabled")
    box.select()
    assert variable.get() == 1


# --------------------------------------------------------------------- mouse


def test_a_click_toggles_the_button(root):
    variable = IntVar(root, 0)
    box = Checkbutton(root, name="c", text="Wrap", variable=variable)
    click(box)
    assert variable.get() == 1


def test_pressing_takes_the_focus(root):
    box = Checkbutton(root, name="c", text="Wrap")
    box._handle(MouseEvent(button=1, state="pressed"))
    assert box.focus_get() is box


def test_a_press_that_leaves_the_widget_changes_nothing(root):
    """Pressing and moving away is how a click is taken back."""
    variable = IntVar(root, 0)
    box = laid_out(Checkbutton(root, name="c", text="Wrap", variable=variable))
    box._handle(MouseEvent(button=1, state="pressed", x=1, y=0))
    box._handle(MouseEvent(button=1, state="released", x=99, y=0))
    assert variable.get() == 0


def test_a_disabled_checkbutton_ignores_a_click(root):
    variable = IntVar(root, 0)
    box = Checkbutton(root, name="c", variable=variable, state="disabled")
    click(box)
    assert variable.get() == 0


# ------------------------------------------------------------------ keyboard


def test_space_toggles_the_focused_button(root):
    variable = IntVar(root, 0)
    box = Checkbutton(root, name="c", variable=variable)
    box._handle(KeyEvent(keysym="space"))
    assert variable.get() == 1


def test_return_does_not_toggle_it(root):
    """Return belongs to the dialog's default button, as it does in Tk."""
    variable = IntVar(root, 0)
    box = Checkbutton(root, name="c", variable=variable)
    box._handle(KeyEvent(keysym="Return"))
    assert variable.get() == 0


def test_a_checkbutton_takes_the_focus(root):
    assert Checkbutton(root, name="c", text="Wrap")._takefocus is True


# ---------------------------------------------------------------- geometry


def test_a_checkbutton_asks_for_room_for_its_box(root):
    label_width = Checkbutton(
        root, name="a", text="Wrap", indicatoron=False
    ).winfo_reqwidth()
    boxed = Checkbutton(root, name="b", text="Wrap").winfo_reqwidth()
    assert boxed == label_width + Checkbutton._INDICATOR_WIDTH


def test_the_text_sits_to_the_right_of_the_box(root):
    box = laid_out(Checkbutton(root, name="c", text="Wrap"), width=20)
    assert box._text_area().x >= Checkbutton._INDICATOR_WIDTH


def test_a_boxless_checkbutton_leaves_the_text_where_a_label_has_it(root):
    box = laid_out(Checkbutton(root, name="c", text="Wrap", indicatoron=False))
    assert box._text_area().x == 0


def test_indicatoron_accepts_the_strings_tcl_does(root):
    box = Checkbutton(root, name="c", text="Wrap", indicatoron="0")
    assert box._indicator_on is False
