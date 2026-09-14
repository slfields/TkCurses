"""Tests for the Menubutton and OptionMenu widgets."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Frame, Menu, Menubutton, Misc, OptionMenu, StringVar, TclError
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
    root._rect = Rect(0, 0, 60, 24)
    root._mapped = True
    return root


@pytest.fixture
def button(root):
    menu = Menu(root, name="m")
    menu.add_command(label="One")
    menu.add_command(label="Two")
    widget = Menubutton(root, name="b", text="File", menu=menu)
    widget._allocate(Rect(0, 0, 8, 3))
    widget._map()
    return widget


# ------------------------------------------------------------- menubutton


def test_clicking_posts_the_menu(button):
    button._handle(MouseEvent(button=1, state="pressed", x=1, y=1))
    assert button._options["menu"]._posted


def test_clicking_hands_the_focus_to_the_posted_menu(button):
    """The button takes it, then the menu takes it from the button.

    Which is what has to happen: the menu holds the grab while it is up, so
    every key and every click has to reach it.
    """
    button._handle(MouseEvent(button=1, state="pressed", x=1, y=1))
    assert button.focus_get() is button._options["menu"]


@pytest.mark.parametrize("keysym", ["Return", "space", "Down"])
def test_the_keyboard_posts_the_menu(button, keysym):
    button._handle(KeyEvent(keysym=keysym))
    assert button._options["menu"]._posted


def test_a_menubutton_with_no_menu_is_harmless(root):
    widget = Menubutton(root, name="b", text="Empty")
    widget._handle(KeyEvent(keysym="Return"))


def test_a_disabled_menubutton_does_not_post(root):
    menu = Menu(root, name="m")
    menu.add_command(label="One")
    widget = Menubutton(root, name="b", text="File", menu=menu, state="disabled")
    widget._handle(KeyEvent(keysym="Return"))
    assert not menu._posted


def test_the_menu_opens_below_by_default(button):
    button._handle(KeyEvent(keysym="Return"))
    assert button._options["menu"].winfo_rooty() >= button.winfo_rooty()


def test_direction_right_opens_beside_it(root):
    menu = Menu(root, name="m")
    menu.add_command(label="One")
    widget = Menubutton(root, name="b", text="File", menu=menu, direction="right")
    widget._allocate(Rect(0, 0, 8, 3))
    widget._map()
    widget._handle(KeyEvent(keysym="Return"))
    assert menu.winfo_rootx() >= widget.winfo_rootx() + 8


def test_the_indicator_takes_room_only_when_it_is_showing(root):
    plain = Menubutton(root, name="a", text="File")
    marked = Menubutton(root, name="b", text="File", indicatoron=True)
    assert marked.winfo_reqwidth() == plain.winfo_reqwidth() + 2


def test_a_menubutton_takes_the_focus(root):
    assert Menubutton(root, name="b", text="File")._takefocus is True


# -------------------------------------------------------------- optionmenu


def test_building_an_optionmenu_does_not_write_the_variable(root):
    """tkinter leaves it alone, so an empty one shows nothing until chosen.

    Checked against Tk 9.0.2, which answers '' for a variable that started
    empty and 'medium' for one that did not.
    """
    variable = StringVar(root, "")
    OptionMenu(root, variable, "small", "medium", "large", name="o")
    assert variable.get() == ""


def test_the_button_shows_the_current_value(root):
    variable = StringVar(root, "")
    widget = OptionMenu(root, variable, "small", "medium", name="o")
    variable.set("medium")
    assert widget._text() == "medium"


def test_the_menu_has_one_entry_per_value(root):
    variable = StringVar(root, "")
    widget = OptionMenu(root, variable, "a", "b", "c", name="o")
    menu = widget["menu"]
    assert [menu.entrycget(n, "label") for n in range(3)] == ["a", "b", "c"]


def test_the_entries_are_commands_as_tkinter_builds_them(root):
    """Tk 9.0.2 answers 'command' for entry 0 of an OptionMenu's menu."""
    widget = OptionMenu(root, StringVar(root, ""), "a", "b", name="o")
    assert widget["menu"].type(0) == "command"


def test_choosing_an_entry_sets_the_variable(root):
    variable = StringVar(root, "")
    widget = OptionMenu(root, variable, "a", "b", name="o")
    widget["menu"].invoke(1)
    assert variable.get() == "b"


def test_the_command_is_called_with_the_choice(root):
    seen = []
    variable = StringVar(root, "")
    widget = OptionMenu(root, variable, "a", "b", command=seen.append, name="o")
    widget["menu"].invoke(1)
    assert seen == ["b"]


def test_the_command_runs_after_the_variable_is_set(root):
    """So a callback reading the variable sees the new value, not the old."""
    seen = []
    variable = StringVar(root, "")
    widget = OptionMenu(
        root,
        variable,
        "a",
        "b",
        command=lambda _: seen.append(variable.get()),
        name="o",
    )
    widget["menu"].invoke(1)
    assert seen == ["b"]


def test_an_optionmenu_needs_at_least_one_value(root):
    with pytest.raises(TclError, match="at least one value"):
        OptionMenu(root, StringVar(root, ""), name="o")


def test_the_choices_can_be_replaced(root):
    variable = StringVar(root, "")
    widget = OptionMenu(root, variable, "a", "b", name="o")
    widget.set_menu("x", "y", "z", current="y")
    menu = widget["menu"]
    assert [menu.entrycget(n, "label") for n in range(3)] == ["x", "y", "z"]
    assert variable.get() == "y"


def test_an_optionmenu_shows_its_indicator(root):
    widget = OptionMenu(root, StringVar(root, ""), "a", name="o")
    assert widget._indicator_on


def test_an_existing_value_is_kept(root):
    """A variable that already holds something is not overwritten."""
    variable = StringVar(root, "medium")
    OptionMenu(root, variable, "small", "medium", "large", name="o")
    assert variable.get() == "medium"


def test_optionmenus_pack_like_anything_else(root):
    frame = Frame(root, name="f")
    widget = OptionMenu(frame, StringVar(root, ""), "a", "b", name="o")
    widget.pack()
    assert widget in frame._layout_manager.slaves(frame)


def test_an_optionmenu_answers_a_click_too(root):
    """Binding tags name one class, so an OptionMenu is not a Menubutton.

    Binding the gestures under the literal name left every OptionMenu inert:
    the click arrived and nothing was listening for it.
    """
    widget = OptionMenu(root, StringVar(root, ""), "a", "b", name="o")
    widget._allocate(Rect(0, 0, 10, 3))
    widget._map()
    widget._handle(MouseEvent(button=1, state="pressed", x=1, y=1))
    assert widget["menu"]._posted


def test_an_optionmenu_answers_the_keyboard_too(root):
    widget = OptionMenu(root, StringVar(root, ""), "a", "b", name="o")
    widget._handle(KeyEvent(keysym="Down"))
    assert widget["menu"]._posted
