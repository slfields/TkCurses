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

"""Tests for the Entry widget."""

from __future__ import annotations

import curses
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


def root_of(widget):
    """The widget's master, for building a Variable against the same tree."""
    return widget.master


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


def test_a_navigation_key_goes_on_to_the_other_tags(entry):
    """Measured on Tk 9.0.2: entry.tcl's <<PrevChar>> does not break, so
    Left also reaches the toplevel's and ``all``'s bindings. TkCurses-wmaq."""
    seen = []
    entry.bind_all("<Key>", lambda event: seen.append(event.keysym))
    entry.insert(0, "abc")
    assert entry._handle(KeyEvent(keysym="Left", char="")) is False
    assert (entry.index("insert"), seen) == (2, ["Left"])


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


@pytest.mark.parametrize("state", ["readonly", "disabled"])
def test_code_cannot_change_a_readonly_or_disabled_entry(entry, state):
    """Measured on real Tk, which this test used to assert the opposite of.

    The old version read "insert() is the program talking, not the user" and
    expected the text to land. That is a reasonable intuition and it is not
    what Tk does: ``-state`` gates the widget commands too, which Tk's own
    documentation says in as many words - "if this option is disabled then the
    value may not be changed using widget commands". Measured on Tcl/Tk 9.0.2,
    for readonly and disabled alike, insert() and delete() do nothing.

    A program that needs to fill a locked entry uses the textvariable, which
    does get through. TkCurses-tvj.
    """
    entry.configure(state=state)
    entry.insert(0, "set from code")
    assert entry.get() == ""


@pytest.mark.parametrize("state", ["readonly", "disabled"])
def test_code_cannot_delete_from_a_readonly_or_disabled_entry(entry, state):
    entry.insert(0, "fixed")
    entry.configure(state=state)
    entry.delete(0, "end")
    assert entry.get() == "fixed"


@pytest.mark.parametrize("state", ["readonly", "disabled"])
def test_a_textvariable_still_fills_a_locked_entry(root, state):
    """The way through, and why the state gate is not a lockout."""
    var = StringVar(root, value="via the variable")
    locked = Entry(root, name="e", textvariable=var, state=state)
    assert locked.get() == "via the variable"


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


# Tk validates a programmatic edit exactly as it validates a keystroke, and
# every expectation below was measured by running the same 25 scenarios through
# tkinter and through this library and diffing text, callbacks and the validate
# option afterwards. TkCurses-tvj; Tcl/Tk 9.0.2.


@pytest.fixture
def validated(entry):
    """A digits-only entry that records its callbacks."""
    log = []
    entry.configure(
        validate="key",
        validatecommand=lambda proposed: (
            log.append(("validate", proposed)) or proposed.isdigit() or proposed == ""
        ),
        invalidcommand=lambda: log.append(("invalid",)),
    )
    return entry, log


def test_insert_asks_the_validator(validated):
    """The bug: a program could put text in a validated entry that its own
    validator would have refused, with nothing to tell it that had happened."""
    entry, log = validated
    entry.insert(0, "x")
    assert entry.get() == ""
    assert log == [("validate", "x"), ("invalid",)]


def test_insert_goes_ahead_when_the_validator_allows_it(validated):
    entry, log = validated
    entry.insert(0, "5")
    assert entry.get() == "5"
    assert log == [("validate", "5")]


def test_delete_asks_the_validator(validated):
    entry, log = validated
    entry.configure(validate="none")
    entry.insert(0, "123")
    entry.configure(validate="key", validatecommand=lambda proposed: proposed == "")
    del log[:]
    entry.delete(1)
    assert entry.get() == "123"


def test_the_validator_is_shown_the_whole_proposed_text(validated):
    """Not the inserted fragment: Tk's %P is the value the field would hold."""
    entry, log = validated
    entry.insert(0, "13")
    del log[:]
    entry.insert(1, "2")
    assert log == [("validate", "123")]
    assert entry.get() == "123"


def test_a_deletes_proposed_text_is_what_would_be_left(validated):
    entry, log = validated
    entry.insert(0, "12345")
    del log[:]
    entry.delete(1, 3)
    assert log == [("validate", "145")]
    assert entry.get() == "145"


@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(lambda e: e.insert(0, ""), id="insert nothing"),
        pytest.param(lambda e: e.delete(1, 1), id="delete an empty range"),
        pytest.param(lambda e: e.delete(5, 9), id="delete past the end"),
        pytest.param(lambda e: e.delete("end"), id="delete at the end"),
    ],
)
def test_an_edit_that_changes_nothing_runs_no_callback(validated, edit):
    """Measured, not an optimisation: Tk's validator never sees these."""
    entry, log = validated
    entry.configure(validate="none")
    entry.insert(0, "12")
    entry.configure(validate="key")
    del log[:]
    edit(entry)
    assert log == []
    assert entry.get() == "12"


@pytest.mark.parametrize("mode", ["key", "all"])
def test_the_edit_modes_gate_a_programmatic_insert(validated, mode):
    entry, log = validated
    entry.configure(validate=mode)
    entry.insert(0, "x")
    assert entry.get() == ""
    assert log[0] == ("validate", "x")


@pytest.mark.parametrize("mode", ["none", "focus", "focusin", "focusout"])
def test_the_focus_modes_let_every_edit_through(validated, mode):
    """The focus modes validate when the focus moves, not when text changes.

    This library used to treat anything but "none" as gating an edit, so a
    validate="focusout" entry vetoed keystrokes real Tk allows.
    """
    entry, log = validated
    entry.configure(validate=mode)
    entry.insert(0, "x")
    assert entry.get() == "x"
    assert log == []


def test_a_validator_that_edits_the_entry_turns_validation_off(validated):
    """Tk's recursion guard, and this library needs it for the same reason.

    Once programmatic edits are validated, a validator calling insert() on the
    entry it is validating would call itself forever. Measured on real Tk: the
    nested edit lands, the edit being validated is discarded, and validate
    reads "none" afterwards.
    """
    entry, _ = validated
    entry.configure(validatecommand=lambda proposed: entry.insert("end", "!") or True)
    entry.insert(0, "a")
    assert entry.get() == "!"
    assert str(entry.cget("validate")) == "none"


def test_a_validator_that_raises_turns_validation_off_and_stays_quiet(validated):
    """An exception is the one return Tcl cannot read as a boolean.

    Measured: the edit is refused, validate becomes "none", and invalidcommand
    does not run - which is the part that would have been guessed wrong.
    """
    entry, log = validated

    def broken(proposed):
        raise RuntimeError("validator is broken")

    entry.configure(validatecommand=broken)
    entry.insert(0, "x")
    assert entry.get() == ""
    assert str(entry.cget("validate")) == "none"
    assert ("invalid",) not in log


def test_an_invalidcommand_that_edits_the_entry_turns_validation_off(validated):
    entry, _ = validated
    entry.configure(invalidcommand=lambda: entry.insert("end", "?"))
    entry.insert(0, "x")
    assert entry.get() == "?"
    assert str(entry.cget("validate")) == "none"


# ------------------------------------------- the focus and forced conditions
#
# Tk has three validation conditions and this library had one. The two added
# here were measured by running 31 scenarios through tkinter and through this
# library and diffing the callbacks, the text and the validate option: 30 agree
# exactly and the one that does not is TkCurses-doh, recorded as a divergence.
# TkCurses-jd1 (focus), TkCurses-3xb (forced), Tcl/Tk 9.0.2.


@pytest.fixture
def pair(root):
    """Two entries, so the focus has somewhere to come from and go to."""
    first = Entry(root, name="first")
    first._allocate(Rect(0, 0, 22, 3))
    first._map()
    second = Entry(root, name="second")
    second._allocate(Rect(0, 4, 22, 3))
    second._map()
    return first, second


def watched(entry, mode, verdict=lambda proposed: False):
    """Give an entry a recording validator and the mode under test."""
    log = []
    entry.configure(
        validate="none",
        validatecommand=lambda proposed: (
            log.append(("validate", proposed)) or verdict(proposed)
        ),
        invalidcommand=lambda proposed: log.append(("invalid", proposed)),
    )
    entry.insert(0, "abc")
    entry.configure(validate=mode)
    return log


@pytest.mark.parametrize(
    ("mode", "on_arrival", "on_departure"),
    [
        ("focus", True, True),
        ("focusin", True, False),
        ("focusout", False, True),
        ("all", True, True),
        ("key", False, False),
        ("none", False, False),
    ],
)
def test_which_modes_validate_when_the_focus_moves(
    pair, mode, on_arrival, on_departure
):
    """The measured table, which no amount of reading the docs settles."""
    other, entry = pair
    log = watched(entry, mode)
    other.focus_set()
    del log[:]

    entry.focus_set()
    assert bool(log) is on_arrival, f"arriving under {mode}"
    del log[:]

    other.focus_set()
    assert bool(log) is on_departure, f"leaving under {mode}"


def test_a_focus_validator_is_shown_the_text_that_is_there(pair):
    other, entry = pair
    log = watched(entry, "focusout")
    other.focus_set()
    entry.focus_set()
    del log[:]
    other.focus_set()
    assert log == [("validate", "abc"), ("invalid", "abc")]


def test_a_refused_focus_validation_leaves_the_text_alone(pair):
    """The focus condition gates nothing - there is no proposal to refuse."""
    other, entry = pair
    watched(entry, "focusout")
    other.focus_set()
    entry.focus_set()
    other.focus_set()
    assert entry.get() == "abc"
    assert str(entry.cget("validate")) == "focusout"


def test_a_focus_validator_that_raises_turns_validation_off(pair):
    other, entry = pair

    def broken(proposed):
        raise RuntimeError("validator is broken")

    watched(entry, "focusout", verdict=broken)
    other.focus_set()
    entry.focus_set()
    other.focus_set()
    assert entry.get() == "abc"
    assert str(entry.cget("validate")) == "none"


def test_a_focus_validator_may_edit_the_entry_without_being_cut_off(pair):
    """Under a pure focus mode there is no recursion to guard against.

    The nested insert is not itself validated - focusout does not gate edits -
    so it lands and validation stays on. Measured, and the mirror image of the
    key-mode case where the same validator is cut off.
    """
    other, entry = pair
    entry.configure(
        validate="none",
        validatecommand=lambda proposed: entry.insert("end", "!") or True,
    )
    entry.insert(0, "abc")
    entry.configure(validate="focusout")
    other.focus_set()
    entry.focus_set()
    other.focus_set()
    assert entry.get() == "abc!"
    assert str(entry.cget("validate")) == "focusout"


def test_writing_the_textvariable_revalidates(root):
    """Tk's forced condition, which this library never ran."""
    log = []
    var = StringVar(root, value="12")
    entry = Entry(
        root,
        name="e",
        textvariable=var,
        validate="none",
        validatecommand=lambda proposed: log.append(("validate", proposed)) or False,
        invalidcommand=lambda proposed: log.append(("invalid", proposed)),
    )
    entry.configure(validate="key")
    del log[:]
    var.set("xyz")
    assert log == [("validate", "xyz")], "the invalidcommand must stay quiet"
    assert entry.get() == "xyz", "a forced validation cannot refuse the value"
    assert str(entry.cget("validate")) == "none"


@pytest.mark.parametrize("mode", ["key", "focus", "focusin", "focusout", "all"])
def test_every_mode_but_none_revalidates_a_variable_write(root, mode):
    """Forced is not one of the edit conditions: the focus modes fire too."""
    log = []
    var = StringVar(root, value="12")
    entry = Entry(
        root,
        name="e",
        textvariable=var,
        validate="none",
        validatecommand=lambda proposed: log.append(proposed) or True,
    )
    entry.configure(validate=mode)
    del log[:]
    var.set("xyz")
    assert log == ["xyz"]


def test_validation_off_ignores_a_variable_write(root):
    log = []
    var = StringVar(root, value="12")
    Entry(
        root,
        name="e",
        textvariable=var,
        validate="none",
        validatecommand=lambda proposed: log.append(proposed) or False,
    )
    var.set("xyz")
    assert log == []


def test_attaching_a_textvariable_revalidates(root):
    """Measured: the forced condition fires when a variable is first attached,
    at construction and through configure() alike."""
    log = []
    var = StringVar(root, value="attached")
    entry = Entry(
        root,
        name="e",
        validate="key",
        validatecommand=lambda proposed: log.append(proposed) or True,
    )
    del log[:]
    entry.configure(textvariable=var)
    assert log == ["attached"]
    assert entry.get() == "attached"


def test_an_accepted_variable_write_leaves_validation_on(root):
    log = []
    var = StringVar(root, value="1")
    entry = Entry(
        root,
        name="e",
        textvariable=var,
        validate="none",
        validatecommand=lambda proposed: log.append(proposed) or True,
    )
    entry.configure(validate="key")
    var.set("2")
    assert str(entry.cget("validate")) == "key"


def test_the_widget_publishing_its_own_text_is_not_a_forced_validation(root):
    """Otherwise every accepted keystroke would validate twice.

    The field writes the variable after an edit, and that write must not come
    back round as a forced revalidation - the edit was already validated.
    """
    log = []
    var = StringVar(root, value="")
    entry = Entry(
        root,
        name="e",
        textvariable=var,
        validate="key",
        validatecommand=lambda proposed: log.append(proposed) or True,
    )
    entry._allocate(Rect(0, 0, 22, 3))
    entry._map()
    del log[:]
    entry.insert(0, "7")
    assert log == ["7"], "one validation for one edit"


def test_an_invalidcommand_is_given_the_refused_text_if_it_will_take_it(entry):
    """Tk's invalidcommand can ask for %P; this one could ask for nothing.

    A handler that takes an argument now gets the proposal. One that takes
    none still works, which is what every existing handler does. TkCurses-1d1.
    """
    seen = []
    entry.configure(
        validate="key",
        validatecommand=lambda proposed: proposed.isdigit(),
        invalidcommand=lambda proposed: seen.append(proposed),
    )
    entry.insert(0, "x")
    assert seen == ["x"]


def test_an_invalidcommand_that_takes_nothing_still_works(entry):
    called = []
    entry.configure(
        validate="key",
        validatecommand=lambda proposed: proposed.isdigit(),
        invalidcommand=lambda: called.append(1),
    )
    entry.insert(0, "x")
    assert called == [1]


def test_validation_can_be_turned_back_on_after_it_was_switched_off(validated):
    """Tk leaves it off and expects the application to restore it."""
    entry, log = validated
    entry.configure(validate="none")
    entry.insert(0, "a")
    entry.configure(validate="key")
    del log[:]
    entry.insert("end", "b")
    # "ab" is not digits, so the restored validator refuses it and the
    # invalidcommand runs - the point being that the validator ran at all.
    assert log == [("validate", "ab"), ("invalid",)]
    assert entry.get() == "a"


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


# The view and the cursor are separate, as in Tk: a keystroke or a click
# brings the cursor into view, the program's own calls do not, and xview moves
# the view alone. Measured on Tk 9.0.2; until TkCurses-i8s every xview form
# moved the cursor, and every redraw dragged the view back to it.

DIGITS = "0123456789" * 10


def first_shown(entry):
    """The index of the leftmost character on screen."""
    return entry._field.view


def test_typing_past_the_right_edge_scrolls_the_view(entry):
    for char in "x" * 50:
        typed(entry, char)
    assert entry.xview()[0] > 0


def test_a_key_brings_the_cursor_back_into_view(entry):
    for char in "x" * 50:
        typed(entry, char)
    typed(entry, "", keysym="Home")
    assert entry.xview()[0] == 0.0


def test_the_program_inserting_does_not_scroll(entry):
    """Tk: inserting at the end of a long entry leaves its view at 0."""
    entry.insert(0, "x" * 50)
    assert entry.xview()[0] == 0.0


def test_icursor_does_not_scroll(entry):
    """Tk: view at 10, icursor(0), and the view is still at 10."""
    entry.insert(0, DIGITS)
    entry.xview(10)
    entry.icursor(0)
    assert first_shown(entry) == 10


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("moveto", 0.5), 50),
        (("moveto", 0.025), 3),  # 2.5 rounds up, as Tk's does
        (("moveto", 0.015), 2),
        (("moveto", 1.0), "last"),
        (("moveto", -0.2), 0),
        (("scroll", 2, "units"), 2),
        (("scroll", 1, "pages"), "page"),
        (("scroll", 2, "pages"), "2 pages"),
        (("scroll", -1, "pages"), 0),
        (("scroll", 999, "units"), "last"),
        ((30,), 30),
        (("end",), "last"),
    ],
)
def test_xview_moves_the_view(entry, args, expected):
    width = entry._text_area().width
    resolved = {
        "last": len(DIGITS) - width,
        "page": width - 2,
        "2 pages": 2 * (width - 2),
    }.get(expected, expected)
    entry.insert(0, DIGITS)
    entry.icursor(3)
    entry.xview(*args)
    assert first_shown(entry) == resolved


def test_xview_leaves_the_cursor_and_the_selection(entry):
    """The bug as filed: Tk keeps the cursor at 3 through all three forms."""
    entry.insert(0, DIGITS)
    entry.icursor(3)
    entry.selection_range(1, 4)
    entry.xview_moveto(0.5)
    entry.xview_scroll(2, "units")
    entry.xview(10)
    assert entry.index("insert") == 3
    assert (entry.index("sel.first"), entry.index("sel.last")) == (1, 4)


def test_xview_survives_a_redraw(entry):
    """The redraw used to scroll back to the cursor, undoing every xview."""
    entry.insert(0, DIGITS)
    entry.icursor(0)
    entry.xview(40)
    entry._redraw()
    assert first_shown(entry) == 40


def test_a_short_entry_does_not_scroll(entry):
    entry.insert(0, "abc")
    entry.xview_moveto(0.5)
    assert entry.xview() == (0.0, 1.0)


def test_inserting_before_the_view_keeps_the_same_text_on_screen(entry):
    entry.insert(0, DIGITS)
    entry.xview(10)
    entry.insert(0, "XY")
    assert first_shown(entry) == 12


def test_a_scrollbar_hears_about_xview(entry):
    reported: list[tuple[float, float]] = []
    entry.insert(0, DIGITS)
    entry.configure(
        xscrollcommand=lambda first, last: reported.append((float(first), float(last)))
    )
    entry.xview(50)
    assert reported[-1][0] == 0.5


def test_an_entry_too_short_for_its_border_still_shows_its_text(root):
    """A bordered widget too small for its border draws none.

    Everything measuring the space left inside has to agree with that. It
    did not: the edge was subtracted anyway, the content area came out
    empty, and the entry rendered as a blank rectangle - indistinguishable
    from a widget that had failed to appear at all. Found by a spinbox
    packed with pady into a frame three rows tall.
    """
    entry = Entry(root, name="e", width=10)
    entry.insert(0, "visible")
    entry._allocate(Rect(0, 0, 12, 1))
    entry._map()
    assert not entry._border_drawn
    area = entry._text_area()
    assert area.height == 1
    assert area.width == 12


def test_an_entry_with_room_for_its_border_keeps_it(root):
    entry = Entry(root, name="e", width=10)
    entry._allocate(Rect(0, 0, 12, 3))
    entry._map()
    assert entry._border_drawn
    assert entry._text_area().width == 10


def test_the_invalidcommand_runs_when_an_edit_is_refused(entry):
    """The third of Tk's validation trio, which this widget did not have.

    A program could say what counted as valid and nothing could say what to do
    when an edit was refused. Measured against real Tk: a digits-only entry sent
    an 'x' calls validatecommand, calls invalidcommand, and keeps the text empty.

    TkCurses-ale, where it surfaced as ttk.Combobox lacking the option - and the
    answer was that the classic Entry lacked it too, so the mixin had nothing to
    expose.
    """
    refused = []
    entry.configure(
        validate="key",
        validatecommand=lambda proposed: proposed.isdigit(),
        invalidcommand=lambda: refused.append(1),
    )
    typed(entry, "x")
    assert entry.get() == ""
    assert refused == [1], "the edit was refused and invalidcommand never ran"


def test_the_invalidcommand_stays_quiet_when_an_edit_is_allowed(entry):
    refused = []
    entry.configure(
        validate="key",
        validatecommand=lambda proposed: proposed.isdigit(),
        invalidcommand=lambda: refused.append(1),
    )
    typed(entry, "7")
    assert entry.get() == "7"
    assert refused == []


def test_an_invalidcommand_that_raises_is_swallowed(entry):
    """As with the validator: a handler for a rejected keystroke must not take
    the application down with it."""

    def broken():
        raise RuntimeError("handler is broken")

    entry.configure(
        validate="key",
        validatecommand=lambda proposed: proposed.isdigit(),
        invalidcommand=broken,
    )
    typed(entry, "x")
    assert entry.get() == ""


def test_xview_answers_the_fractions_a_scrollbar_wants(entry):
    """Tk's contract, which this widget was the only one here not to follow.

    Measured on real tkinter: a 10-wide entry holding 43 characters answers
    ``xview() == (0.0, 0.023255813953488372)``. Ours returned the first visible
    character as an int, so -xscrollcommand could not be honoured - and Text and
    Canvas in this same codebase already answered with fractions.
    """
    entry.configure(width=10)
    entry.insert(0, "the quick brown fox jumps over the lazy dog")

    first, last = entry.xview()
    assert 0.0 <= first < last <= 1.0

    entry.xview("moveto", 0.0)
    assert entry.xview()[0] == 0.0


def test_a_scrollbar_is_told_where_the_entry_view_is(entry):
    """``-xscrollcommand`` reaches a scrollbar, which is why xview changed.

    Asserted through the callback rather than through xview alone: the option
    existing and the callback never firing is the failure this is here for.
    """
    reported: list[tuple[float, float]] = []
    entry.configure(
        width=10,
        xscrollcommand=lambda first, last: reported.append((float(first), float(last))),
    )
    entry.insert(0, "the quick brown fox jumps over the lazy dog")

    assert reported, "nothing was reported to the xscrollcommand"
    first, last = reported[-1]
    assert 0.0 <= first < last <= 1.0


# ---------------------------------------------------- negative indices
#
# Tk clamps a negative index to 0 wherever it takes one; this counted from the
# end until TkCurses-11m. Measured on Tk 9.0.2 with "abcdef".


@pytest.mark.parametrize("index", [-1, -3, -99])
def test_a_negative_index_is_zero(entry, index):
    entry.insert(0, "abcdef")
    assert entry.index(index) == 0


def test_deleting_at_a_negative_index_deletes_the_first_character(entry):
    entry.insert(0, "abcdef")
    entry.delete(-2)
    assert entry.get() == "bcdef"


def test_inserting_at_a_negative_index_inserts_at_the_start(entry):
    entry.insert(0, "abcdef")
    entry.insert(-1, "XY")
    assert entry.get() == "XYabcdef"


def test_a_negative_range_start_is_the_start(entry):
    entry.insert(0, "abcdef")
    entry.selection_range(-3, 2)
    assert (entry.index("sel.first"), entry.index("sel.last")) == (0, 2)


def test_left_at_the_start_of_the_field_stays_there(entry):
    """It went to the second-to-last position."""
    entry.insert(0, "abcdef")
    entry.icursor(0)
    typed(entry, "", keysym="Left")
    assert entry.index("insert") == 0


# ------------------------------------------------------- selection commands
#
# Measured on Tk 9.0.2: none of selection_from, selection_to or
# selection_adjust moves the insertion cursor, and selection_from does not
# touch the selection. Ours moved the cursor in all three, and selection_adjust
# was selection_to under another name. TkCurses-bfy.


@pytest.fixture
def lettered(entry):
    entry.insert(0, "abcdefghij")
    entry.icursor(5)
    return entry


def selected(widget):
    if not widget.selection_present():
        return None
    return (widget.index("sel.first"), widget.index("sel.last"))


def test_the_selection_commands_leave_the_cursor(lettered):
    lettered.selection_range(2, 6)
    lettered.selection_from(3)
    assert selected(lettered) == (2, 6)
    lettered.selection_to(8)
    assert selected(lettered) == (3, 8)
    lettered.selection_adjust(1)
    assert selected(lettered) == (1, 8)
    assert lettered.index("insert") == 5


def test_selection_adjust_is_not_selection_to(lettered):
    """On 2-6, adjust(3) moves the start; selection_to(3) would give 0-3."""
    lettered.selection_range(2, 6)
    lettered.selection_adjust(3)
    assert selected(lettered) == (3, 6)


def test_a_click_sets_the_anchor(lettered):
    """Tk's Button-1 binding does selection from where it lands."""
    x = lettered._text_area().x + 3
    lettered._handle(MouseEvent(button=1, state="pressed", x=x, y=1))
    lettered.selection_to(8)
    assert selected(lettered) == (3, 8)


# -------------------------------------------------------- exportselection
#
# Four behaviours, measured on Tcl/Tk 9.0.2 by selecting in a real Entry and
# reading PRIMARY: selecting exports, turning the option off drops PRIMARY with
# the selection still in place, turning it back on exports what is already
# selected, and clearing the selection makes PRIMARY stop existing.
#
# Before this the option did not exist on Entry at all - and ttk.Combobox
# declared it while nothing acted on it, which the option-surface test could not
# see because it compares names rather than behaviour. TkCurses-163.


def primary(widget):
    """What PRIMARY holds, or None when it does not exist."""
    try:
        return widget.selection_get()
    except TclError:
        return None


def test_the_default_is_to_export(entry):
    """tkinter answers 1, not True: cget reports the value as given."""
    assert entry.cget("exportselection") == 1


def test_a_selection_goes_onto_primary(entry):
    entry.insert(0, "hello world")
    entry.selection_range(0, 5)
    assert primary(entry) == "hello"


def test_clearing_the_selection_makes_primary_stop_existing(entry):
    """Not the empty string. A caller needs to tell those apart, which is why
    tkinter raises rather than returning ''."""
    entry.insert(0, "hello world")
    entry.selection_range(0, 5)
    entry.selection_clear()
    assert primary(entry) is None


def test_turning_the_option_off_drops_primary_at_once(entry):
    """The selection itself is untouched - only the export stops."""
    entry.insert(0, "hello world")
    entry.selection_range(0, 5)
    entry.configure(exportselection=0)
    assert primary(entry) is None
    assert entry.selection_present(), "the widget's own selection must remain"


def test_nothing_is_exported_while_the_option_is_off(entry):
    entry.insert(0, "hello world")
    entry.configure(exportselection=0)
    entry.selection_range(6, 11)
    assert primary(entry) is None


def test_turning_the_option_on_exports_what_is_already_selected(entry):
    """Measured: no reselection is needed, the export happens on configure."""
    entry.insert(0, "hello world")
    entry.configure(exportselection=0)
    entry.selection_range(6, 11)
    entry.configure(exportselection=1)
    assert primary(entry) == "world"


def test_a_selection_made_with_the_keyboard_is_exported_too(entry):
    """The path a person actually uses, and the one an implementation forgets.

    Shift with a motion key makes a selection without going through
    selection_range, so hooking only the public methods would leave this silent.
    """
    entry.insert(0, "hello")
    entry.icursor(0)
    entry.focus_set()
    for _ in range(3):
        typed(entry, "", keysym="Right", state=MOD_SHIFT)
    assert entry.selection_present(), "shift-Right did not select anything"
    assert primary(entry) == "hel"


def test_an_edit_that_shortens_the_selection_is_followed(entry):
    """PRIMARY is answered by a handler at read time rather than copied, so an
    edit needs noticing by nobody."""
    entry.insert(0, "hello world")
    entry.selection_range(0, 11)
    assert primary(entry) == "hello world"
    entry.delete(5, 11)
    assert primary(entry) in (None, "hello"), (
        "PRIMARY still reported the text that was deleted"
    )


def test_the_widget_that_selected_last_owns_primary(root):
    """Creating a second entry must not take PRIMARY from the first."""
    first = Entry(root, name="first")
    second = Entry(root, name="second")
    for widget in (first, second):
        widget._allocate(Rect(0, 0, 22, 3))
        widget._map()
    first.insert(0, "first text")
    first.selection_range(0, 5)
    assert primary(first) == "first"

    second.insert(0, "second text")
    assert primary(first) == "first", "merely creating and filling B took PRIMARY"

    second.selection_range(0, 6)
    assert primary(second) == "second"


# --------------------------------------------------------- the placeholder
#
# Tk 9.0's ghost text. Every rule below was measured ON SCREEN by a person
# running a tkinter probe, because none of it can be read through the API:
# bbox() reports the index rather than the drawn text, the style layout has no
# placeholder element, and Tk documents -placeholder NOWHERE - it is in the
# standard-options list of entry(n), ttk_entry(n) and ttk_combobox(n) and
# described in none of them. ARCHITECTURE.md carries the rules for that reason.
# TkCurses-xe9.3.


def test_the_placeholder_options_default_to_nothing(entry):
    assert entry.cget("placeholder") == ""
    assert entry.cget("placeholderforeground") == ""


def test_the_placeholder_is_shown_only_while_the_field_is_empty(entry):
    entry.configure(placeholder="type here")
    assert entry._displayed() == "type here"
    entry.insert(0, "x")
    assert entry._displayed() == "x"
    entry.delete(0, "end")
    assert entry._displayed() == "type here", (
        "deleting the text must bring the placeholder back"
    )


def test_the_placeholder_survives_the_focus(entry):
    """Measured: a focused empty field keeps the ghost text, with the cursor
    before its first character. This was the open question."""
    entry.configure(placeholder="type here")
    entry.focus_set()
    assert entry.focus_get() is entry
    assert entry._displayed() == "type here"


@pytest.mark.parametrize("state", ["disabled", "readonly"])
def test_a_locked_field_still_shows_its_placeholder(entry, state):
    """The opposite of the insertion cursor, which those states suppress.

    So the drawing is gated on emptiness alone - not on state, and not on
    focus. Measured on screen for both states.
    """
    entry.configure(placeholder="type here", state=state)
    assert entry._displayed() == "type here"


def test_the_placeholder_is_not_masked_by_show(entry):
    """The one that would have been got wrong.

    Measured: a field with show='*' and a placeholder draws the placeholder as
    plain text, not as asterisks. ``show`` hides CONTENTS and there are none, so
    the placeholder short-circuits the mask rather than passing through it.
    """
    entry.configure(placeholder="type here", show="*")
    assert entry._displayed() == "type here"
    entry.insert(0, "secret")
    assert entry._displayed() == "******", "typed text must still be masked"


def test_the_placeholder_is_never_the_value(entry):
    """get(), the variable and the selection all behave as empty - which was
    measured programmatically and then confirmed on screen: the ghost text
    cannot be selected by triple-click or Control-a."""
    var = StringVar(root_of(entry), value="")
    entry.configure(placeholder="type here", textvariable=var)
    assert entry.get() == ""
    assert var.get() == ""
    assert not entry.selection_present()
    assert entry.index("end") == 0


def test_an_empty_placeholder_shows_nothing(entry):
    """The default. An empty placeholder must not make the field claim to be
    showing one, or every field would draw a blank line in dim."""
    assert not entry._showing_placeholder()
    entry.configure(placeholder="")
    assert not entry._showing_placeholder()


def test_the_placeholder_is_drawn_dim(entry):
    """A deliberate divergence, documented in ARCHITECTURE.md.

    Tk leaves an unset placeholderforeground in the ordinary foreground, which
    a GUI gets away with. In a terminal that would be indistinguishable from
    real content, so a field would read as full while get() answers "".
    """
    entry.configure(placeholder="type here")
    plain = 0
    assert entry._placeholder_attribute(plain) & curses.A_DIM
