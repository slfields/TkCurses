"""Tests for the Button widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Button, Misc, StringVar, TclError
from tkcurses._core.events import KeyEvent, MouseEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack
from tkcurses._core.timers import AfterQueue


class FakeClock:
    """A clock the test advances by hand, so no test has to sleep."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


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


def laid_out(widget, width=12, height=3):
    """Give a widget a size, so a click can land inside it."""
    widget._allocate(Rect(0, 0, width, height))
    widget._map()
    return widget


def click(widget, x=1, y=1):
    """Press and release button 1 over a widget, as the loop would deliver it."""
    if widget.winfo_width() == 0:
        laid_out(widget)
    widget._handle(MouseEvent(button=1, state="pressed", x=x, y=y))
    widget._handle(MouseEvent(button=1, state="released", x=x, y=y))


# ----------------------------------------------------------------- invoking


def test_invoke_runs_the_command(root):
    calls = []
    Button(root, name="b", text="OK", command=lambda: calls.append(1)).invoke()
    assert calls == [1]


def test_invoke_returns_what_the_command_returns(root):
    assert Button(root, name="b", command=lambda: "result").invoke() == "result"


def test_invoke_without_a_command_is_harmless(root):
    assert Button(root, name="b", text="OK").invoke() is None


def test_a_disabled_button_does_not_invoke(root):
    calls = []
    button = Button(root, name="b", command=lambda: calls.append(1), state="disabled")
    button.invoke()
    assert calls == []


def test_a_button_can_be_re_enabled(root):
    calls = []
    button = Button(root, name="b", command=lambda: calls.append(1), state="disabled")
    button.configure(state="normal")
    button.invoke()
    assert calls == [1]


# -------------------------------------------------------------------- mouse


def test_a_click_invokes_the_button(root):
    calls = []
    button = Button(root, name="b", text="OK", command=lambda: calls.append(1))
    click(button)
    assert calls == [1]


def test_pressing_leaves_the_focus_alone(root):
    """Clicking one of these leaves the focus alone, as it does in Tk.

    Checked against Tk 9.0.2: a click gives the focus to an entry, spinbox,
    text or listbox - widgets that then want the keyboard - and not to a
    button, checkbutton, radiobutton, scale or menubutton. Taking it here
    would be worse than merely unfaithful: a button binds Space and Return to invoke
    itself, so every later Space would press the last button clicked.
    """
    button = Button(root, name="b", text="OK")
    button._handle(MouseEvent(button=1, state="pressed"))
    assert button.focus_get() is None


def test_a_release_without_a_press_does_nothing(root):
    """Releasing over a button the press began elsewhere must not invoke it."""
    calls = []
    button = Button(root, name="b", command=lambda: calls.append(1))
    button._handle(MouseEvent(button=1, state="released"))
    assert calls == []


def test_a_disabled_button_ignores_a_click(root):
    calls = []
    button = Button(root, name="b", command=lambda: calls.append(1), state="disabled")
    click(button)
    assert calls == []


def test_a_button_is_not_left_pressed_after_a_click(root):
    button = Button(root, name="b", text="OK")
    click(button)
    assert button._pressed is False


# ----------------------------------------------------------------- keyboard


@pytest.mark.parametrize("keysym", ["Return", "space"])
def test_a_key_invokes_the_focused_button(root, keysym):
    calls = []
    button = Button(root, name="b", command=lambda: calls.append(1))
    button._handle(KeyEvent(keysym=keysym))
    assert calls == [1]


def test_a_key_stops_there(root):
    """Return must not both press the button and reach a dialog behind it."""
    button = Button(root, name="b")
    assert button._handle(KeyEvent(keysym="Return")) is True


def test_a_disabled_button_ignores_a_key(root):
    calls = []
    button = Button(root, name="b", command=lambda: calls.append(1), state="disabled")
    button._handle(KeyEvent(keysym="Return"))
    assert calls == []


# ------------------------------------------------------------------ binding


def test_an_instance_binding_runs_before_the_class_one(root):
    """And can stop it, which is what tkinter's binding order is for."""
    calls = []
    button = Button(root, name="b", command=lambda: calls.append("command"))
    button.bind("<Key-Return>", lambda event: calls.append("mine") or "break")
    button._handle(KeyEvent(keysym="Return"))
    assert calls == ["mine"]


def test_the_class_bindings_are_installed_once(root):
    Button(root, name="a")
    Button(root, name="b")
    bound = root.tk.bindings.bindings("Button")
    returns = [b for b in bound if b.pattern.detail == "Return"]
    assert len(returns) == 1


def test_two_buttons_share_the_class_bindings(root):
    calls = []
    first = Button(root, name="a", command=lambda: calls.append("a"))
    second = Button(root, name="b", command=lambda: calls.append("b"))
    click(first)
    click(second)
    assert calls == ["a", "b"]


# -------------------------------------------------------------------- sizing


def test_a_button_reserves_room_for_its_markers(root):
    """So it does not change width when it gains the focus.

    Two cells for the markers either side, and two more for the raised border
    a button wears by default.
    """
    button = Button(root, name="b", text="OK")
    assert button.winfo_reqwidth() == len("OK") + 4 + 2


def test_a_button_takes_its_text_from_a_variable(root):
    var = StringVar(root, value="Save")
    button = Button(root, name="b", textvariable=var)
    assert button.winfo_reqwidth() == len("Save") + 4 + 2


def test_a_button_is_raised_by_default(root):
    """tkinter's default too, and what makes it look pressable."""
    assert Button(root, name="b").cget("relief") == "raised"


def test_a_button_takes_focus_by_default(root):
    assert Button(root, name="b")._takefocus is True


def test_an_unknown_option_is_refused(root):
    with pytest.raises(TclError, match="unknown option"):
        Button(root, name="b", nonsense=1)


# -------------------------------------------------------------------- flash


def test_flashing_a_disabled_button_does_nothing(root):
    button = Button(root, name="b", state="disabled")
    button.flash()
    assert button._pressed is False


def test_a_flash_ends_by_itself(root):
    """The button puts itself back without blocking the loop to do it."""
    clock = FakeClock()
    root.tk.timers = AfterQueue(clock=clock)
    button = Button(root, name="b", text="OK")
    button.flash()
    assert button._pressed is True
    clock.now += 1.0
    root.tk.timers.run_due()
    assert button._pressed is False


def test_a_coalesced_click_still_invokes(root):
    """ncurses merges a quick press and release into one CLICKED report.

    Tk has no such event: a widget waits for the release to decide whether the
    press counted. Delivered as a press alone, a button would stay held down
    for ever and never invoke - which is what a fast click actually produces.
    """
    calls = []
    button = laid_out(Button(root, name="b", command=lambda: calls.append(1)))
    button._handle(MouseEvent(button=1, state="clicked", x=1, y=1))
    assert calls == [1]
    assert button._pressed is False


def test_releasing_outside_the_button_does_not_invoke_it(root):
    """Press, change your mind, move away, release - the way out of a click.

    The release reaches the button wherever the pointer ended up, because a
    pressed widget holds an implicit grab on the mouse, so whether it counts
    has to be decided by where the release actually landed.
    """
    calls = []
    button = laid_out(Button(root, name="b", command=lambda: calls.append(1)))
    button._handle(MouseEvent(button=1, state="pressed", x=1, y=1))
    button._handle(MouseEvent(button=1, state="released", x=40, y=20))
    assert calls == []
    assert button._pressed is False


def test_releasing_back_inside_still_invokes(root):
    calls = []
    button = laid_out(Button(root, name="b", command=lambda: calls.append(1)))
    button._handle(MouseEvent(button=1, state="pressed", x=1, y=1))
    button._handle(MouseEvent(button=1, state="released", x=3, y=2))
    assert calls == [1]
