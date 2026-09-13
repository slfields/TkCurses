"""Tests for BaseWidget and Widget."""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

import tkcurses
from tkcurses import BaseWidget, Misc, NoDefaultRoot, TclError, Widget
from tkcurses.constants import FLAT, RAISED


class Frame(Widget):
    """A container with nothing of its own to configure."""


class Button(Widget):
    """A widget that adds options to the standard set."""

    _widget_options: ClassVar[dict[str, Any]] = {
        "text": "",
        "command": None,
        "state": "normal",
    }


@pytest.fixture
def root():
    return Misc()


@pytest.fixture(autouse=True)
def _no_leaked_default_root():
    """Keep the module-level root out of the other tests.

    It is process-wide state, so a test that sets it would otherwise decide
    what every later test sees.
    """
    previous = tkcurses._default_root
    supported = tkcurses._support_default_root
    yield
    tkcurses._default_root = previous
    tkcurses._support_default_root = supported


# ------------------------------------------------------------- construction


def test_a_widget_joins_its_masters_tree(root):
    button = Button(root, name="ok")
    assert root.winfo_children() == [button]
    assert str(button) == ".ok"


def test_a_widget_is_a_misc(root):
    assert isinstance(Button(root), Misc)
    assert isinstance(Button(root), BaseWidget)


def test_options_may_be_given_as_keywords(root):
    assert Button(root, text="OK").cget("text") == "OK"


def test_options_may_be_given_as_a_dictionary(root):
    assert Button(root, {"text": "OK"}).cget("text") == "OK"


def test_keywords_win_over_the_dictionary(root):
    assert Button(root, {"text": "from cnf"}, text="from kw").cget("text") == "from kw"


def test_an_unset_option_takes_its_declared_default(root):
    button = Button(root)
    assert button.cget("text") == ""
    assert button.cget("relief") == FLAT
    assert button.cget("state") == "normal"


def test_an_unknown_option_is_refused_at_construction(root):
    with pytest.raises(TclError, match="nonsense"):
        Button(root, nonsense=1)


# ------------------------------------------------------------------ options


def test_the_standard_options_reach_every_widget(root):
    keys = Frame(root).keys()
    assert "background" in keys
    assert "relief" in keys
    assert "takefocus" in keys


def test_a_subclass_adds_to_the_standard_set(root):
    keys = Button(root).keys()
    assert "text" in keys
    assert "background" in keys


def test_a_subclasses_options_do_not_leak_sideways(root):
    frame_keys = Frame(root).keys()
    assert "text" not in frame_keys


def test_keys_are_sorted(root):
    keys = Button(root).keys()
    assert keys == sorted(keys)


def test_configure_changes_an_option(root):
    button = Button(root, text="OK")
    button.configure(text="Cancel")
    assert button.cget("text") == "Cancel"


def test_configure_with_no_arguments_returns_the_current_values(root):
    button = Button(root, text="OK")
    assert button.configure()["text"] == "OK"


def test_configure_refuses_an_unknown_option(root):
    button = Button(root)
    with pytest.raises(TclError, match="nonsense"):
        button.configure(nonsense=1)


def test_config_is_an_alias(root):
    button = Button(root)
    button.config(text="OK")
    assert button["text"] == "OK"


def test_item_access_reads_and_writes_options(root):
    button = Button(root)
    button["text"] = "OK"
    assert button["text"] == "OK"


def test_cget_refuses_an_unknown_option(root):
    with pytest.raises(TclError, match="nonsense"):
        Button(root).cget("nonsense")


@pytest.mark.parametrize(
    ("alias", "full"),
    [("bg", "background"), ("fg", "foreground"), ("bd", "borderwidth")],
)
def test_short_option_names_are_accepted(root, alias, full):
    button = Button(root, **{alias: "blue" if "border" not in full else 2})
    assert button.cget(full) == button.cget(alias)


def test_an_alias_and_its_full_name_are_the_same_option(root):
    button = Button(root, bg="blue")
    button.configure(background="red")
    assert button.cget("bg") == "red"


# ---------------------------------------------------------------- takefocus


def test_takefocus_defaults_to_false(root):
    """A widget with nothing to do with the keyboard is not a tab stop.

    Tab landing on a Frame or a Label shows the user nothing and reads as the
    focus having vanished. The widgets that answer the keyboard turn it back
    on for themselves.
    """
    assert Button(root)._takefocus is False


def test_takefocus_can_be_asked_for_at_construction(root):
    assert Button(root, takefocus=True)._takefocus is True


def test_configuring_takefocus_updates_the_focus_order(root):
    first = Button(root, name="a", takefocus=True)
    second = Button(root, name="b", takefocus=True)
    second.configure(takefocus=False)
    assert first.tk_focusNext() is first


# ----------------------------------------------------------- option database


def test_the_option_database_supplies_a_default(root):
    root.option_add("*Button.relief", RAISED)
    assert Button(root).cget("relief") == RAISED


def test_an_explicit_option_beats_the_database(root):
    root.option_add("*Button.relief", RAISED)
    assert Button(root, relief=FLAT).cget("relief") == FLAT


def test_the_database_does_not_reach_another_class(root):
    root.option_add("*Button.relief", RAISED)
    assert Frame(root).cget("relief") == FLAT


def test_the_database_is_consulted_at_construction_not_after(root):
    button = Button(root)
    root.option_add("*Button.relief", RAISED)
    assert button.cget("relief") == FLAT


# -------------------------------------------------------------- default root


def test_a_widget_without_a_master_uses_the_default_root(root):
    tkcurses._default_root = root
    assert Button().master is root


def test_a_widget_without_a_master_or_a_root_is_refused():
    tkcurses._default_root = None
    with pytest.raises(TclError, match="create a Tk"):
        Button()


def test_the_error_names_the_widget_being_created():
    tkcurses._default_root = None
    with pytest.raises(TclError, match="Button"):
        Button()


def test_no_default_root_refuses_even_when_one_exists(root):
    tkcurses._default_root = root
    NoDefaultRoot()
    with pytest.raises(TclError, match="not support default root"):
        Button()


def test_an_explicit_master_still_works_with_no_default_root(root):
    NoDefaultRoot()
    assert Button(root).master is root


# ------------------------------------------------------------------ destroy


def test_destroying_a_widget_removes_it_from_the_tree(root):
    button = Button(root, name="ok")
    button.destroy()
    assert root.winfo_children() == []
    assert not button.winfo_exists()


def test_destroying_a_container_takes_its_children(root):
    frame = Frame(root, name="frame")
    button = Button(frame, name="ok")
    frame.destroy()
    assert not button.winfo_exists()


# ------------------------------------------------------------------- naming


def test_an_unnamed_widget_is_numbered_by_class(root):
    assert str(Button(root)) == ".!button"
    assert str(Frame(root)) == ".!frame"
    assert str(Button(root)) == ".!button2"


def test_winfo_class_reports_the_class_name(root):
    assert Button(root).winfo_class() == "Button"


def test_a_widget_can_be_looked_up_by_path(root):
    button = Button(root, name="ok")
    assert root.nametowidget(".ok") is button


def test_only_widgets_that_answer_the_keyboard_are_tab_stops(root):
    """Reported from UAT scenario 17: Tab stopped on frames and labels.

    Nothing marks a focused frame or label, so the focus appeared to vanish
    every second or third press. tkinter decides takefocus by class; the
    equivalent here is a default of False that the interactive widgets turn
    back on for themselves.
    """
    import tkcurses

    frame = tkcurses.Frame(root, name="frame")
    label = tkcurses.Label(root, name="label", text="hello")
    button = tkcurses.Button(root, name="button", text="press")
    entry = tkcurses.Entry(root, name="entry")
    listbox = tkcurses.Listbox(root, name="listbox")
    scrollbar = tkcurses.Scrollbar(root, name="scrollbar")

    assert frame._takefocus is False
    assert label._takefocus is False
    assert scrollbar._takefocus is False
    assert button._takefocus is True
    assert entry._takefocus is True
    assert listbox._takefocus is True


def test_tab_order_skips_the_widgets_that_cannot_use_it(root):
    import tkcurses

    tkcurses.Label(root, name="label", text="hello")
    entry = tkcurses.Entry(root, name="entry")
    button = tkcurses.Button(root, name="button", text="press")
    assert entry.tk_focusNext() is button
    assert button.tk_focusNext() is entry
