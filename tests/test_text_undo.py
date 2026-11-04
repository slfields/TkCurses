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


"""Where undo and redo leave a Text's cursor and view, held to Tk 9.0.2.

A replay of ``tests/support/text_undo.json``, recorded from real Tk by
``tests/support/record_text_undo.py``: a Text and a peer edited in random
steps, undone and redone through either, with each one's cursor and first
index on screen, and what undo and redo answered, after every step.
TkCurses-2sbq.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tkcurses import Misc, TclError, Text
from tkcurses._core.events import KeyEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack

DATA = json.loads(
    (Path(__file__).parent / "support" / "text_undo.json").read_text("utf-8")
)


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 30)
    root._mapped = True
    return root


def make(root, *, auto=True):
    """A Text 16 by 4 over the recorded lines, and a peer as big."""
    text = Text(root, name="t", width=16, height=4, wrap="none", undo=True)
    text.configure(autoseparators=auto)
    text._allocate(Rect(0, 0, 18, 6))
    text._map()
    text.insert("1.0", DATA["text"])
    text.edit_reset()
    text.yview_moveto(0)
    text.peer_create(".p", width=16, height=4)
    peer = text.nametowidget(".p")
    peer._allocate(Rect(0, 6, 18, 6))
    peer._map()
    return text, peer


def state(text, peer, answer):
    return [
        text.index("insert"),
        peer.index("insert"),
        text.index("@0,0"),
        peer.index("@0,0"),
        answer,
    ]


def replay(text, peer, steps):
    after = []
    for kind, *args in steps:
        answer = None
        target = peer if kind in "pqUR" else text
        if kind in "ip":
            target.insert(args[0], args[1])
        elif kind in "dq":
            target.delete(args[0], args[1])
        elif kind == "s":
            text.edit_separator()
        elif kind in "uUrR":
            try:
                undo = kind in "uU"
                answer = list(target.edit_undo() if undo else target.edit_redo())
            except TclError:
                answer = "error"
        elif kind == "j":
            text.mark_set("insert", args[0])
        else:
            text.yview_moveto(0)
            text.yview_scroll(args[0], "units")
        after.append(state(text, peer, answer))
    return after


@pytest.mark.parametrize("n", range(len(DATA["cases"])))
def test_each_recorded_run_ends_where_tk_ends(root, n):
    case = DATA["cases"][n]
    text, peer = make(root, auto=case["auto"])
    assert replay(text, peer, case["steps"]) == case["after"]


def blank(root, text="", **options):
    """A Text holding ``text``, with undo on and nothing yet to undo."""
    widget = Text(root, width=20, height=5, undo=True, **options)
    widget._allocate(Rect(0, 0, 22, 7))
    widget._map()
    widget.insert("1.0", text)
    widget.edit_reset()
    return widget


def undo_all(text):
    """The text after each undo, until there is nothing left to undo."""
    seen = []
    while True:
        try:
            text.edit_undo()
        except TclError:
            return seen
        seen.append(text.get("1.0", "end-1c"))


FORTY = "\n".join(f"l{k}" for k in range(1, 41))


def test_undoing_an_insertion_puts_the_cursor_before_it(root):
    """Measured on Tk 9.0.2: three lines put in at 1.0, the cursor at 30.0
    before and after; undone, the cursor is at 1.0 and the answer is the
    range the text came out of."""
    text = blank(root, FORTY)
    text.mark_set("insert", "30.0")
    text.insert("1.0", "a\nb\nc\n")
    text.mark_set("insert", "30.0")
    assert text.edit_undo() == ("1.0", "4.0")
    assert text.index("insert") == "1.0"
    assert text.index("@0,0") == "1.0"


def test_redoing_an_insertion_puts_the_cursor_after_it(root):
    text = blank(root, FORTY)
    text.insert("1.0", "a\nb\nc\n")
    text.edit_undo()
    text.mark_set("insert", "30.0")
    assert text.edit_redo() == ("1.0", "4.0")
    assert text.index("insert") == "4.0"


def test_undoing_a_deletion_puts_the_cursor_after_what_comes_back(root):
    """Measured: ``delete 2.0 4.0``, the cursor at 30.0; undone, 4.0, and
    redone, 2.0."""
    text = blank(root, FORTY)
    text.delete("2.0", "4.0")
    text.mark_set("insert", "30.0")
    assert text.edit_undo() == ("2.0", "4.0")
    assert text.index("insert") == "4.0"
    text.mark_set("insert", "30.0")
    assert text.edit_redo() == ("2.0", "4.0")
    assert text.index("insert") == "2.0"


def test_a_peers_edit_undone_here_moves_the_peers_cursor(root):
    """The atom names the widget that made the edit. Measured: a peer puts
    `` there`` in at 1.5; undone through the other, the peer's cursor goes
    to 1.5 and the other's stays at 1.0."""
    text = blank(root, "hello world")
    text.peer_create(".hp")
    peer = text.nametowidget(".hp")
    text.mark_set("insert", "1.0")
    peer.insert("1.5", " there")
    peer.mark_set("insert", "1.0")
    assert text.edit_undo() == ("1.5", "1.11")
    assert text.index("insert") == "1.0"
    assert peer.index("insert") == "1.5"


@pytest.mark.parametrize(
    ("edits", "answer"),
    [
        ([("i", "1.2", "XX"), ("d", "1.1", "1.5")], ("1.1", "1.4")),
        ([("d", "1.2", "1.4"), ("i", "1.1", "Z")], ("1.1", "1.4")),
        ([("i", "1.2", "XX"), ("i", "1.6", "YY")], ("1.2", "1.6")),
    ],
)
def test_overlapping_ranges_are_answered_as_one(root, edits, answer):
    """``tk::TextUndoRedoProcessMarks``: each range absorbs those starting
    inside it, where the marks are once the whole group is undone. Measured
    on Tk 9.0.2, over ``abcdefgh``, each pair one group."""
    text = blank(root, "abcdefgh", autoseparators=False)
    for kind, at, what in edits:
        if kind == "i":
            text.insert(at, what)
        else:
            text.delete(at, what)
    assert text.edit_undo() == answer
    assert text.get("1.0", "end-1c") == "abcdefgh"


def test_an_undone_insertion_answers_where_it_was(root):
    """Text that comes out answers an empty range: measured, typing ``x``
    then ``y`` at the end and undoing ``y`` answers ``1.1 1.1``."""
    text = blank(root, autoseparators=False)
    text.insert("1.0", "x")
    text.edit_separator()
    text.insert("end", "y")
    assert text.edit_undo() == ("1.1", "1.1")


def test_nothing_is_answered_without_undo(root):
    text = blank(root, "abc")
    text.configure(undo=False)
    text.insert("end", "d")
    assert text.edit_undo() == ()
    assert text.edit_redo() == ()


def test_a_disabled_text_answers_nothing_and_keeps_its_cursor(root):
    """Deliberately unlike Tk, which answers the ranges it refused to change
    and moves the cursor to them - TkCurses-aah."""
    text = blank(root, "abc")
    text.insert("1.0", "ab")
    text.mark_set("insert", "1.4")
    text.configure(state="disabled")
    assert text.edit_undo() == ()
    assert text.index("insert") == "1.4"
    assert text.get("1.0", "end-1c") == "ababc"


def test_switching_between_inserting_and_deleting_ends_the_group(root):
    """Programmatic edits included, which ours used to group as one.
    Measured: ``abc`` in, ``d`` at the end, 1.0 out, ``e`` at the end -
    undone as ``bcd``, ``abcd``, then nothing."""
    text = blank(root)
    text.insert("1.0", "abc")
    text.insert("end", "d")
    text.delete("1.0")
    text.insert("end", "e")
    assert undo_all(text) == ["bcd", "abcd", ""]


def test_the_switch_is_shared_by_peers(root):
    """``lastEditMode`` is in the shared text. Measured: a peer puts ``d``
    in and the Text takes 1.0 out; they undo apart."""
    text = blank(root, "abc")
    text.peer_create(".sp")
    text.nametowidget(".sp").insert("end", "d")
    text.delete("1.0")
    assert undo_all(text) == ["abcd", "abc"]


def test_an_undo_takes_the_separator_under_it(root):
    """TkUndoRevert pops the separator below the group and frees it.
    Measured, autoseparators off: ``x``, a separator, ``y``; undo; ``z``
    and a separator; and the next undo takes ``z`` and ``x`` together."""
    text = blank(root, autoseparators=False)
    text.insert("1.0", "x")
    text.edit_separator()
    text.insert("end", "y")
    text.edit_undo()
    text.insert("end", "z")
    text.edit_separator()
    assert text.edit_undo() == ("1.0", "1.0")
    assert text.get("1.0", "end-1c") == ""


def test_autoseparators_put_it_back(root):
    """The same with autoseparators on: the undo leaves ``x``."""
    text = blank(root)
    text.insert("1.0", "x")
    text.edit_separator()
    text.insert("end", "y")
    text.edit_undo()
    text.insert("end", "z")
    assert text.edit_undo() == ("1.1", "1.1")
    assert text.get("1.0", "end-1c") == "x"


def test_a_redo_with_nothing_to_redo_still_ends_the_group(root):
    """TkUndoApply puts a separator on the undo stack before it looks.
    Measured, autoseparators off: ``x``, a failed redo, ``y``; the undo
    takes only ``y``."""
    text = blank(root, autoseparators=False)
    text.insert("1.0", "x")
    with pytest.raises(TclError, match="nothing to redo"):
        text.edit_redo()
    text.insert("end", "y")
    assert text.edit_undo() == ("1.1", "1.1")
    assert text.get("1.0", "end-1c") == "x"


def press(text, *keys):
    for key in keys:
        char = {"Return": "\r", "BackSpace": "\b"}.get(key, key)
        text._handle(KeyEvent(keysym=key, char=char))


def test_return_ends_the_group_after_the_newline(root):
    """text.tcl's Return binding separates after ``tk::TextInsert``, not
    before. Measured on Tk 9.0.2 with keys: ``abc``, Return, ``def``, two
    BackSpaces and ``x`` undo as ``x``, the BackSpaces, ``def``, and then
    ``abc`` with its newline. Ours broke the group before the newline as
    well. TkCurses-hy15."""
    text = blank(root)
    text.focus_set()
    press(text, "a", "b", "c", "Return", "d", "e", "f", "BackSpace", "BackSpace", "x")
    assert undo_all(text) == ["abc\nd", "abc\ndef", "abc\n", ""]


def test_typing_over_the_selection_is_a_group_of_its_own(root):
    """``tk::TextInsert``: separators either side of the deletion and the
    insertion, with autoseparators off between them. Measured: ``q``, then
    ``X`` over ``bc`` and ``Y``, undo as ``Y``, the replacement, ``q``."""
    text = blank(root, "abcd")
    text.focus_set()
    text.mark_set("insert", "1.0")
    press(text, "q")
    text.tag_add("sel", "1.2", "1.4")
    text.mark_set("insert", "1.4")
    press(text, "X", "Y")
    assert undo_all(text) == ["qaXd", "qabcd", "abcd"]
    assert text.cget("autoseparators") == 1


@pytest.mark.parametrize(
    ("edits", "answer"),
    [
        ([("1.0", "ab"), ("1.2", "cdef"), ("1.4", "X")], ("1.0", "1.7")),
        ([("1.0", "ab"), ("1.0", "cd"), ("1.3", "X")], ("1.0", "1.5")),
    ],
)
def test_a_redo_answers_by_the_marks_gravity(root, edits, answer):
    """Each range's start has left gravity and its end right, which only
    shows where the merge compares by an end it has since extended past.
    Measured on Tk 9.0.2, one group, undone and redone."""
    text = blank(root, autoseparators=False)
    for at, what in edits:
        text.insert(at, what)
    text.edit_undo()
    assert text.edit_redo() == answer


def test_autoseparators_can_be_turned_off_later(root):
    text = blank(root)
    text.configure(autoseparators=False)
    text.insert("1.0", "abc")
    text.delete("1.0")
    assert undo_all(text) == [""]
