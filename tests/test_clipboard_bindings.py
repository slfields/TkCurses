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

"""Copy, cut and paste on Entry and Text - Tk's clipboard virtual events.

Every expectation here was MEASURED on Tk 9.0.2 with ``hello world`` and 0-5
selected, the cursor at the end, unless a test says otherwise. Driven through
the real key path - a key event in, the virtual event raised from it - rather
than by generating the virtual event, because which keys raise them is half
of what is being tested. TkCurses-lw2.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Entry, Misc, StringVar, TclError, Text, ttk
from tkcurses._core.events import MOD_CTRL, MOD_SHIFT, KeyEvent, MouseEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(window_factory=stub_window, panel_factory=None)
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    return root


def press(widget, keysym, state=0, char=""):
    """Deliver one key as the loop would."""
    widget._handle(KeyEvent(keysym=keysym, char=char, modifiers=state))


def clipboard(widget):
    try:
        return widget.clipboard_get()
    except TclError:
        return None


def placed(widget):
    widget._allocate(Rect(0, 0, 22, 3))
    widget._map()
    return widget


@pytest.fixture
def entry(root):
    """An Entry holding 'hello world', 0-5 selected, the cursor at the end."""
    widget = placed(Entry(root, name="e"))
    widget.insert(0, "hello world")
    widget.icursor("end")
    widget.selection_range(0, 5)
    widget.focus_set()
    return widget


def selected(widget):
    if not widget.selection_present():
        return None
    return (widget.index("sel.first"), widget.index("sel.last"))


# ---------------------------------------------------------------- the keys


@pytest.mark.parametrize(
    ("keysym", "state"),
    [("x", MOD_CTRL), ("w", MOD_CTRL), ("Delete", MOD_SHIFT)],
)
def test_the_cut_keys_cut(entry, keysym, state):
    """Measured: ' world' left, 'hello' on the clipboard, cursor moved back
    by five. Shift-Delete cuts rather than deleting one character - Tk lets
    the virtual event have it."""
    press(entry, keysym, state)
    assert entry.get() == " world"
    assert clipboard(entry) == "hello"
    assert entry.index("insert") == 6
    assert not entry.selection_present()


def test_control_insert_copies_and_changes_nothing(entry):
    press(entry, "Insert", MOD_CTRL)
    assert clipboard(entry) == "hello"
    assert entry.get() == "hello world"


@pytest.mark.parametrize(("keysym", "state"), [("v", MOD_CTRL), ("y", MOD_CTRL)])
def test_the_paste_keys_replace_the_selection(entry, keysym, state):
    """A deliberate departure from classic Tk on Linux, which inserts at the
    cursor and keeps the selection (X11's rule). This replaces it, as ttk does
    everywhere and classic Tk does on Windows and macOS - measured, ttk.Entry
    turns 'hello world' with 'hello' selected into 'XX world'. The cursor
    being elsewhere does not matter: it is the selection that is replaced.
    TkCurses-lw2."""
    entry.clipboard_clear()
    entry.clipboard_append("ZZ")
    press(entry, keysym, state)
    assert entry.get() == "ZZ world"
    assert entry.index("insert") == 2
    assert selected(entry) is None


def test_paste_with_nothing_selected_inserts_at_the_cursor(entry):
    entry.selection_clear()
    entry.icursor(2)
    entry.clipboard_clear()
    entry.clipboard_append("ZZ")
    press(entry, "v", MOD_CTRL)
    assert entry.get() == "heZZllo world"
    assert entry.index("insert") == 4


def test_a_rejected_paste_still_replaced_the_selection_as_ttk_does(root):
    """ttk's PendingDelete deletes, then inserts: each is validated on its
    own, so a rejected insert leaves the deletion done - measured on a
    ttk.Entry, "123" with "1" selected and "ab" pasted reads "23". Followed, not
    improved on - a validatecommand sees the same two edits it would in Tk."""
    entry = placed(Entry(root, name="digits"))
    entry.insert(0, "123")
    entry.configure(validate="key", validatecommand=lambda proposed: proposed.isdigit())
    entry.selection_range(0, 1)
    entry.clipboard_clear()
    entry.clipboard_append("ab")
    press(entry, "v", MOD_CTRL)
    assert entry.get() == "23"


@pytest.mark.parametrize("keysym", ["/", "_"])
def test_control_slash_selects_all_and_leaves_the_cursor(entry, keysym):
    """Ctrl-/ arrives from a terminal as Ctrl-_ - one byte, 0x1f, for both -
    so both select all."""
    entry.icursor(3)  # not at the end, or a select-all that moved it there would pass
    press(entry, keysym, MOD_CTRL)
    assert selected(entry) == (0, 11)
    assert entry.index("insert") == 3


def test_clear_deletes_the_selection(entry):
    entry.event_generate("<<Clear>>")
    assert entry.get() == " world"


# ----------------------------------------------------------- the edge cases


def test_copy_with_nothing_selected_leaves_the_clipboard(entry):
    entry.selection_clear()
    entry.clipboard_clear()
    entry.clipboard_append("Q")
    press(entry, "Insert", MOD_CTRL)
    assert clipboard(entry) == "Q"


def test_cut_with_nothing_selected_does_nothing(entry):
    entry.selection_clear()
    entry.clipboard_clear()
    press(entry, "x", MOD_CTRL)
    assert entry.get() == "hello world"
    assert clipboard(entry) is None


def test_paste_with_an_empty_clipboard_does_nothing(entry):
    entry.clipboard_clear()
    press(entry, "v", MOD_CTRL)
    assert entry.get() == "hello world"


@pytest.mark.parametrize("state", ["readonly", "disabled"])
def test_a_read_only_entry_copies_and_refuses_cut_and_paste(entry, state):
    """Measured: copy works; cut copies but deletes nothing; paste nothing."""
    entry.configure(state=state)
    press(entry, "Insert", MOD_CTRL)
    assert clipboard(entry) == "hello"
    entry.clipboard_clear()
    press(entry, "x", MOD_CTRL)
    assert clipboard(entry) == "hello"
    assert entry.get() == "hello world"
    entry.clipboard_clear()
    entry.clipboard_append("ZZ")
    cursor = entry.index("insert")
    press(entry, "v", MOD_CTRL)
    assert entry.get() == "hello world"
    # A refused paste changes nothing at all: the selection is not replaced,
    # and the cursor is not moved to its start on the way.
    assert selected(entry) == (0, 5)
    assert entry.index("insert") == cursor


def test_a_masked_entry_copies_what_it_shows(root):
    """Measured: show='*' copies '*****', and a cut takes '***'."""
    widget = placed(Entry(root, name="m", show="*"))
    widget.insert(0, "secret")
    widget.selection_range(0, 3)
    press(widget, "Insert", MOD_CTRL)
    assert clipboard(widget) == "***"
    press(widget, "x", MOD_CTRL)
    assert widget.get() == "ret"


def test_a_paste_is_validated(entry):
    entry.configure(validate="key", validatecommand=lambda proposed: proposed.isalpha())
    entry.clipboard_clear()
    entry.clipboard_append("12")
    press(entry, "v", MOD_CTRL)
    assert entry.get() == "hello world"


def test_a_middle_click_pastes_the_primary_selection_where_it_lands(root):
    source = placed(Entry(root, name="src"))
    source.insert(0, "PRIMARY")
    source.selection_range(0, 3)  # owns PRIMARY now: "PRI"
    target = Entry(root, name="dst")
    target._allocate(Rect(0, 4, 22, 3))
    target._map()
    target.insert(0, "abcd")
    x = target._text_area().x + 2
    target._handle(MouseEvent(button=2, state="released", x=x, y=1))
    assert target.get() == "abPRIcd"


@pytest.mark.parametrize(
    "make",
    [
        lambda r: ttk.Entry(r, name="t"),
        lambda r: ttk.Combobox(r, name="t", values=("a",)),
        lambda r: ttk.Spinbox(r, name="t", from_=0, to=9),
        lambda r: __import__("tkcurses").Spinbox(r, name="t", from_=0, to=9),
    ],
    ids=["ttk.Entry", "ttk.Combobox", "ttk.Spinbox", "tk.Spinbox"],
)
def test_every_entry_class_cuts_and_pastes(root, make):
    """Each binds under its own class name; a class left out gets nothing."""
    widget = placed(make(root))
    widget.delete(0, "end")
    widget.insert(0, "hello world")
    widget.selection_range(0, 5)
    press(widget, "x", MOD_CTRL)
    assert widget.get() == " world"
    widget.icursor(0)
    press(widget, "v", MOD_CTRL)
    assert widget.get() == "hello world"
    widget.selection_range(6, 11)
    press(widget, "v", MOD_CTRL)
    assert widget.get() == "hello hello", "paste did not replace the selection"


# --------------------------------------------------------------------- Text


@pytest.fixture
def text(root):
    widget = Text(root, name="tx", width=20, height=5, wrap="none")
    widget._allocate(Rect(0, 0, 22, 7))
    widget._map()
    widget.insert("1.0", "hello world")
    widget.tag_add("sel", "1.0", "1.5")
    widget.mark_set("insert", "1.11")
    widget.focus_set()
    return widget


def test_text_copies_cuts_and_pastes(text):
    """Measured on Tk's Text: the same rules as an Entry's."""
    press(text, "Insert", MOD_CTRL)
    assert clipboard(text) == "hello"
    text.clipboard_clear()
    text.clipboard_append("ZZ")
    press(text, "v", MOD_CTRL)
    # Replaces the selection, not Linux Tk's insert-and-keep - TkCurses-lw2.
    assert text.get("1.0", "end-1c") == "ZZ world"
    assert text.index("insert") == "1.2"
    assert not text.tag_ranges("sel")
    press(text, "v", MOD_CTRL)
    assert text.get("1.0", "end-1c") == "ZZZZ world", "nothing selected: insert"
    text.tag_add("sel", "1.0", "1.4")
    press(text, "x", MOD_CTRL)
    assert text.get("1.0", "end-1c") == " world"
    assert clipboard(text) == "ZZZZ"


def test_shift_delete_cuts_in_a_text(text):
    press(text, "Delete", MOD_SHIFT)
    assert text.get("1.0", "end-1c") == " world"
    assert clipboard(text) == "hello"


def test_a_disabled_text_copies_and_refuses_cut_and_paste(text):
    """Measured: copy works; cut copies but deletes nothing; paste nothing.
    Checked by the handlers themselves, because a disabled Text here still
    takes edits from code - TkCurses-aah."""
    text.configure(state="disabled")
    press(text, "x", MOD_CTRL)
    assert clipboard(text) == "hello"
    assert text.get("1.0", "end-1c") == "hello world"
    text.clipboard_clear()
    text.clipboard_append("ZZ")
    press(text, "v", MOD_CTRL)
    assert text.get("1.0", "end-1c") == "hello world"


def test_select_all_in_a_text_leaves_the_insert_mark(text):
    press(text, "_", MOD_CTRL)
    assert [str(i) for i in text.tag_ranges("sel")] == ["1.0", text.index("end")]
    assert text.index("insert") == "1.11"


# ------------------------------------------------------------------ Ctrl-C


def test_ctrl_c_copies_when_the_focus_has_a_selection(root, entry):
    """The author's decision, TkCurses-lw2: with something selected, Ctrl-C
    copies and nothing closes."""
    root.clipboard_clear()
    assert root._copy_on_interrupt() is True
    assert clipboard(root) == "hello"


def test_ctrl_c_closes_when_nothing_is_selected(root, entry):
    entry.selection_clear()
    assert root._copy_on_interrupt() is False


def test_ctrl_c_closes_when_the_focus_cannot_copy(root):
    button = __import__("tkcurses").Button(root, name="b", text="b")
    button.focus_set()
    assert root._copy_on_interrupt() is False


def test_ctrl_c_copies_from_a_text_too(root, text):
    root.clipboard_clear()
    assert root._copy_on_interrupt() is True
    assert clipboard(root) == "hello"


def test_a_variable_follows_a_cut(root):
    variable = StringVar(root, value="hello world")
    widget = placed(Entry(root, name="v", textvariable=variable))
    widget.selection_range(0, 6)
    press(widget, "x", MOD_CTRL)
    assert variable.get() == "world"


# --------------------------------------------------------------- drag-select
#
# Tk's own bindings, read from the running interpreter: <Button-1> anchors
# at the gap under the pointer, <B1-Motion> selects from the anchor to the
# pointer either way round and moves the cursor there. Entry had no drag at
# all until a person running UAT 43 tried one. TkCurses-lw2.


def mouse(widget, state, x):
    widget._handle(MouseEvent(button=1, state=state, x=widget._text_area().x + x, y=1))


def test_dragging_across_an_entry_selects(root):
    widget = placed(Entry(root, name="d"))
    widget.insert(0, "hello world")
    mouse(widget, "pressed", 2)
    mouse(widget, "drag", 7)
    assert selected(widget) == (2, 7)
    assert widget.index("insert") == 7
    mouse(widget, "drag", 0)  # back past the anchor: the other way round
    assert selected(widget) == (0, 2)
    assert widget.index("insert") == 0
    mouse(widget, "drag", 2)  # onto the anchor: nothing selected
    assert selected(widget) is None
    mouse(widget, "released", 2)


def test_a_drag_selection_is_on_primary_and_copies(root):
    widget = placed(Entry(root, name="d"))
    widget.insert(0, "hello world")
    widget.focus_set()
    mouse(widget, "pressed", 0)
    mouse(widget, "drag", 5)
    mouse(widget, "released", 5)
    assert widget.selection_get() == "hello"
    press(widget, "Insert", MOD_CTRL)
    assert clipboard(widget) == "hello"


def test_moving_after_the_release_selects_nothing(root):
    widget = placed(Entry(root, name="d"))
    widget.insert(0, "hello world")
    mouse(widget, "pressed", 2)
    mouse(widget, "released", 2)
    mouse(widget, "drag", 8)
    assert selected(widget) is None


# ------------------------------------------------ one selection at a time
#
# Measured on Tk 9.0.2: with exportselection on, selecting in one widget
# clears the selection in whichever widget held PRIMARY before - Entry and
# Text alike, either way round. A widget with exportselection=0 keeps its own
# and clears nobody's. Copying to the clipboard clears nothing. Both stayed
# highlighted here, which a person running UAT 43 reported. TkCurses-lw2.


@pytest.fixture
def three(root):
    a = placed(Entry(root, name="a"))
    a.insert(0, "hello world")
    b = Entry(root, name="b")
    b._allocate(Rect(0, 4, 22, 3))
    b._map()
    b.insert(0, "second field")
    t = Text(root, name="t", width=20, height=3)
    t._allocate(Rect(0, 8, 22, 5))
    t._map()
    t.insert("1.0", "line one")
    return a, b, t


def test_selecting_in_one_entry_clears_another(three):
    a, b, _t = three
    a.selection_range(0, 5)
    b.selection_range(0, 6)
    assert selected(a) is None
    assert selected(b) == (0, 6)


def test_a_text_and_an_entry_clear_each_other(three):
    a, _b, t = three
    a.selection_range(0, 5)
    t.tag_add("sel", "1.0", "1.4")
    assert selected(a) is None
    assert t.selection_get() == "line"
    a.selection_range(0, 5)
    assert not t.tag_ranges("sel")
    assert a.selection_get() == "hello"


def test_a_widget_that_does_not_export_keeps_its_own_and_clears_nobody(three, root):
    a, b, _t = three
    keeper = Entry(root, name="k", exportselection=0)
    keeper._allocate(Rect(30, 0, 22, 3))
    keeper._map()
    keeper.insert(0, "keeps mine")
    a.selection_range(0, 5)
    keeper.selection_range(0, 5)
    assert selected(a) == (0, 5), "exportselection=0 cleared another widget"
    b.selection_range(0, 3)
    assert selected(keeper) == (0, 5), "a non-exporting selection was cleared"
    assert selected(a) is None


def test_copying_clears_no_selection(three):
    a, _b, _t = three
    a.selection_range(0, 5)
    a.clipboard_clear()
    a.clipboard_append("copied")
    assert selected(a) == (0, 5)


def test_selection_own_command_is_called_when_another_takes_it(three, root):
    a, _b, _t = three
    lost = []
    root.selection_own(command=lambda: lost.append("lost"))
    a.selection_range(0, 5)
    assert lost == ["lost"]


def test_the_middle_button_pastes_a_texts_selection(three):
    """Possible now that a Text's selection reaches PRIMARY - TkCurses-9e8."""
    _a, b, t = three
    t.tag_add("sel", "1.0", "1.4")
    b.delete(0, "end")
    x = b._text_area().x
    b._handle(MouseEvent(button=2, state="released", x=x, y=5))
    assert b.get() == "line"


def test_dragging_in_a_text_takes_primary_from_an_entry(three):
    """The way a person selects in a Text - by dragging, which goes through
    the Text's own selection code rather than tag_add."""
    a, _b, t = three
    a.selection_range(0, 5)
    area = t._text_area()
    t._handle(MouseEvent(button=1, state="pressed", x=area.x, y=area.y))
    t._handle(MouseEvent(button=0, state="drag", x=area.x + 4, y=area.y))
    assert t.selection_get() == "line"
    assert selected(a) is None
