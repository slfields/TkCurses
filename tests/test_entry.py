"""Tests for the Entry widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Entry, Misc, StringVar, TclError
from tkcurses._core.events import MOD_SHIFT, KeyEvent, MouseEvent
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


@pytest.fixture
def entry(root):
    entry = Entry(root, name="e")
    entry._allocate(Rect(0, 0, 22, 3))
    entry._map()
    return entry


def typed(widget, char, keysym=None, state=0):
    """Deliver one key as the loop would."""
    widget._handle(KeyEvent(keysym=keysym or char, char=char, modifiers=state))


# ------------------------------------------------------------------ content


def test_a_new_entry_is_empty(entry):
    assert entry.get() == ""


def test_inserting_text(entry):
    entry.insert(0, "hello")
    assert entry.get() == "hello"


def test_inserting_at_the_end(entry):
    entry.insert(0, "hello")
    entry.insert("end", " there")
    assert entry.get() == "hello there"


def test_deleting_a_range(entry):
    entry.insert(0, "hello")
    entry.delete(0, 2)
    assert entry.get() == "llo"


def test_deleting_everything(entry):
    entry.insert(0, "hello")
    entry.delete(0, "end")
    assert entry.get() == ""


# ------------------------------------------------------------------ indices


def test_end_is_the_length(entry):
    entry.insert(0, "abc")
    assert entry.index("end") == 3


def test_insert_is_the_cursor(entry):
    entry.insert(0, "abc")
    entry.icursor(1)
    assert entry.index("insert") == 1


def test_a_number_is_itself(entry):
    entry.insert(0, "abc")
    assert entry.index(2) == 2


def test_an_index_past_the_end_is_clamped(entry):
    entry.insert(0, "abc")
    assert entry.index(99) == 3


def test_a_screen_column_maps_to_an_index(entry):
    entry.insert(0, "abcdef")
    assert entry.index("@3") == 2


def test_a_selection_index_needs_a_selection(entry):
    entry.insert(0, "abc")
    with pytest.raises(TclError, match="selection"):
        entry.index("sel.first")


def test_a_bad_index_is_refused(entry):
    with pytest.raises(TclError, match="bad entry index"):
        entry.index("sideways")


# ---------------------------------------------------------------- selection


def test_selecting_a_range(entry):
    entry.insert(0, "hello")
    entry.selection_range(1, 3)
    assert entry.selection_present()
    assert entry.index("sel.first") == 1
    assert entry.index("sel.last") == 3


def test_clearing_the_selection(entry):
    entry.insert(0, "hello")
    entry.selection_range(1, 3)
    entry.selection_clear()
    assert not entry.selection_present()


def test_typing_replaces_the_selection(entry):
    entry.insert(0, "hello")
    entry.selection_range(0, 5)
    typed(entry, "X")
    assert entry.get() == "X"


def test_backspace_deletes_the_selection(entry):
    entry.insert(0, "hello")
    entry.selection_range(1, 4)
    typed(entry, "", "BackSpace")
    assert entry.get() == "ho"


# ----------------------------------------------------------------- keyboard


def test_typing_inserts_at_the_cursor(entry):
    entry.insert(0, "ac")
    entry.icursor(1)
    typed(entry, "b")
    assert entry.get() == "abc"


def test_backspace_deletes_before_the_cursor(entry):
    entry.insert(0, "abc")
    typed(entry, "", "BackSpace")
    assert entry.get() == "ab"


def test_backspace_at_the_start_does_nothing(entry):
    entry.insert(0, "abc")
    entry.icursor(0)
    typed(entry, "", "BackSpace")
    assert entry.get() == "abc"


def test_delete_removes_the_character_at_the_cursor(entry):
    entry.insert(0, "abc")
    entry.icursor(1)
    typed(entry, "", "Delete")
    assert entry.get() == "ac"


def test_the_arrows_move_the_cursor(entry):
    entry.insert(0, "abc")
    typed(entry, "", "Left")
    assert entry.index("insert") == 2
    typed(entry, "", "Right")
    assert entry.index("insert") == 3


def test_home_and_end_jump_to_the_ends(entry):
    entry.insert(0, "abc")
    typed(entry, "", "Home")
    assert entry.index("insert") == 0
    typed(entry, "", "End")
    assert entry.index("insert") == 3


def test_a_shifted_arrow_selects(entry):
    entry.insert(0, "abc")
    typed(entry, "", "Left", MOD_SHIFT)
    assert entry.selection_present()
    assert entry.index("sel.first") == 2


def test_an_unprintable_key_is_left_alone(entry):
    """So a binding on F1 is not swallowed by the field."""
    entry.insert(0, "abc")
    assert entry._handle(KeyEvent(keysym="F1", char="")) is False
    assert entry.get() == "abc"


def test_an_editing_key_stops_there(entry):
    assert entry._handle(KeyEvent(keysym="Left", char="")) is True


# -------------------------------------------------------------------- mouse


def test_clicking_moves_the_cursor(entry):
    entry.insert(0, "abcdef")
    entry._handle(MouseEvent(button=1, state="pressed", x=3, y=1))
    assert entry.index("insert") == 2


def test_clicking_takes_the_focus(entry):
    entry._handle(MouseEvent(button=1, state="pressed", x=1, y=1))
    assert entry.focus_get() is entry


# -------------------------------------------------------------------- state


def test_a_readonly_entry_refuses_typing(entry):
    entry.insert(0, "fixed")
    entry.configure(state="readonly")
    typed(entry, "X")
    assert entry.get() == "fixed"


def test_a_readonly_entry_can_still_be_read_and_selected(entry):
    entry.insert(0, "fixed")
    entry.configure(state="readonly")
    entry.selection_range(0, 3)
    assert entry.selection_present()
    assert entry.get() == "fixed"


def test_a_disabled_entry_refuses_the_focus_from_a_click(entry):
    entry.configure(state="disabled")
    entry._handle(MouseEvent(button=1, state="pressed", x=1, y=1))
    assert entry.focus_get() is None


def test_code_can_still_change_a_readonly_entry(entry):
    """insert() is the program talking, not the user."""
    entry.configure(state="readonly")
    entry.insert(0, "set from code")
    assert entry.get() == "set from code"


# ------------------------------------------------------------- textvariable


def test_a_textvariable_fills_the_entry(root):
    var = StringVar(root, value="from the variable")
    entry = Entry(root, name="e", textvariable=var)
    assert entry.get() == "from the variable"


def test_setting_the_variable_updates_the_entry(root):
    var = StringVar(root, value="before")
    entry = Entry(root, name="e", textvariable=var)
    var.set("after")
    assert entry.get() == "after"


def test_typing_updates_the_variable(root):
    var = StringVar(root, value="")
    entry = Entry(root, name="e", textvariable=var)
    entry._allocate(Rect(0, 0, 22, 3))
    entry._map()
    typed(entry, "a")
    assert var.get() == "a"


def test_typing_does_not_reset_the_cursor(root):
    """The variable's trace writes back; without a guard it fights the typing."""
    var = StringVar(root, value="")
    entry = Entry(root, name="e", textvariable=var)
    entry._allocate(Rect(0, 0, 22, 3))
    entry._map()
    for char in "abc":
        typed(entry, char)
    assert entry.get() == "abc"
    assert entry.index("insert") == 3


# --------------------------------------------------------------- validation


def test_a_validator_can_refuse_an_edit(entry):
    entry.configure(validate="key", validatecommand=lambda proposed: proposed.isdigit())
    typed(entry, "x")
    assert entry.get() == ""


def test_a_validator_can_allow_an_edit(entry):
    entry.configure(validate="key", validatecommand=lambda proposed: proposed.isdigit())
    typed(entry, "7")
    assert entry.get() == "7"


def test_a_validator_that_raises_counts_as_a_refusal(entry):
    """A broken validator must not take the application down with it."""

    def broken(proposed):
        raise RuntimeError("validator is broken")

    entry.configure(validate="key", validatecommand=broken)
    typed(entry, "x")
    assert entry.get() == ""


def test_validation_off_ignores_the_command(entry):
    entry.configure(validate="none", validatecommand=lambda proposed: False)
    typed(entry, "x")
    assert entry.get() == "x"


# ------------------------------------------------------------------ display


def test_show_masks_the_text(entry):
    entry.insert(0, "secret")
    entry.configure(show="*")
    assert entry.get() == "secret"
    assert entry._displayed() == "******"


def test_without_show_the_text_is_itself(entry):
    entry.insert(0, "plain")
    assert entry._displayed() == "plain"


def test_an_entry_asks_for_its_width_plus_its_border(entry):
    assert entry.winfo_reqwidth() == 20 + 2
    assert entry.winfo_reqheight() == 1 + 2


def test_the_view_follows_the_cursor(entry):
    entry.insert(0, "x" * 50)
    assert entry.xview() > 0


def test_the_view_comes_back_when_the_cursor_does(entry):
    entry.insert(0, "x" * 50)
    entry.icursor(0)
    assert entry.xview() == 0
