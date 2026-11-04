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


"""The navigation keys in the text widgets, held to Tk 9.0.2.

Most of it is a replay of ``tests/support/navigation_keys.json``, recorded
from real Tk by ``tests/support/record_navigation_keys.py``: random runs of
arrows, Home and End under each modifier, the navigation virtual events, and
the program moving the cursor and the selection, in each entry widget and in
a Text with and without wrapping. TkCurses-wmaq.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tkcurses import Entry, Misc, Spinbox, Text, ttk
from tkcurses._core.events import MOD_CTRL, MOD_SHIFT, KeyEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack

DATA = json.loads(
    (Path(__file__).parent / "support" / "navigation_keys.json").read_text("utf-8")
)
MODIFIERS = {"": 0, "S": MOD_SHIFT, "C": MOD_CTRL, "CS": MOD_CTRL | MOD_SHIFT}
CLASSES = {
    "Entry": Entry,
    "Spinbox": Spinbox,
    "TEntry": ttk.Entry,
    "TCombobox": ttk.Combobox,
    "TSpinbox": ttk.Spinbox,
}
#: Where the run goes on from a selection Tk reports as present and empty -
#: [30, 30, 30] - which classic Tk makes when a Shift-move lands on the
#: anchor, and this library deliberately does not (see TextField.select_to).
#: The step that makes one is compared as no selection; these are the runs
#: whose later steps then differ.
AFTER_AN_EMPTY_SELECTION = {("Spinbox", 38)}


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 30)
    root._mapped = True
    return root


def make(root, kind):
    """The widget a case was recorded in, as wide as it was there."""
    if kind.endswith("Text"):
        wrap = "word" if kind == "WrappedText" else "none"
        widget = Text(root, name="w", width=16, height=4, wrap=wrap)
        widget._allocate(Rect(0, 0, 18, 6))
    else:
        widget = CLASSES[kind](root, name="w", width=12)
        widget._allocate(Rect(0, 0, 16, 3))
    widget._map()
    widget.configure(exportselection=False)
    if kind.endswith("Text"):
        widget.insert("1.0", DATA["text"])
    else:
        widget.delete(0, "end")  # TkCurses-fdl9: ours starts with a value
        widget.insert(0, DATA["line"])
    widget.focus_set()
    return widget


def state(widget):
    if isinstance(widget, Text):
        return [widget.index("insert"), [str(i) for i in widget.tag_ranges("sel")]]
    insert = widget.index("insert")
    if widget.selection_present():
        return [insert, widget.index("sel.first"), widget.index("sel.last")]
    return [insert, None, None]


def replay(widget, steps):
    text = isinstance(widget, Text)
    after = []
    for kind, *args in steps:
        if kind == "k":
            key, mods = args
            widget._handle(KeyEvent(keysym=key, char="", modifiers=MODIFIERS[mods]))
        elif kind == "v":
            widget.event_generate(f"<<{args[0]}>>")
        elif kind == "j":
            widget.mark_set("insert", args[0]) if text else widget.icursor(args[0])
        elif text:
            widget.tag_remove("sel", "1.0", "end")
            widget.tag_add("sel", *args)
        else:
            widget.selection_range(*args)
        after.append(state(widget))
    return after


def as_tk_reports_it(row):
    """A recorded state, with Tk's present-but-empty selection as none."""
    if len(row) == 3 and row[1] is not None and row[1] == row[2]:
        return [row[0], None, None]
    return row


CASES = [
    pytest.param(
        kind,
        case,
        id=f"{kind}-{n}",
        marks=[pytest.mark.xfail(strict=True, reason="after an empty selection")]
        if (kind, n) in AFTER_AN_EMPTY_SELECTION
        else [],
    )
    for kind, cases in DATA["cases"].items()
    for n, case in enumerate(cases)
]


@pytest.mark.parametrize(("kind", "case"), CASES)
def test_each_recorded_run_ends_where_tk_ends(root, kind, case):
    widget = make(root, kind)
    expected = [as_tk_reports_it(row) for row in case["after"]]
    assert replay(widget, case["steps"]) == expected, case["steps"]


# ------------------------------------------------------------- the keys


def press(widget, keysym, modifiers=0):
    widget._handle(KeyEvent(keysym=keysym, char="", modifiers=modifiers))


@pytest.mark.parametrize("kind", ["Entry", "TEntry"])
def test_the_emacs_keys_move_an_entry(root, kind):
    """tk::EventMotifBindings, measured on Tk 9.0.2 in ``abc def``."""
    entry = CLASSES[kind](root, name="e")
    entry.insert(0, "abc def")
    moves = []
    for key in "aefb":
        if key == "f":
            entry.icursor(2)
        press(entry, key, MOD_CTRL)
        moves.append(entry.index("insert"))
    assert moves == [0, 7, 3, 2]


def test_the_emacs_keys_move_a_text(root):
    """Measured on Tk 9.0.2, from 2.3 in ``abc def`` over ``second line``."""
    text = Text(root, name="t", width=20, height=4, wrap="none")
    text._allocate(Rect(0, 0, 22, 6))
    text._map()
    text.insert("1.0", "abc def\nsecond line")
    text.mark_set("insert", "2.3")
    moves = []
    for key in "pnea":
        press(text, key, MOD_CTRL)
        moves.append(text.index("insert"))
    assert moves == ["1.3", "2.3", "2.11", "2.0"]


@pytest.mark.parametrize("kind", ["Entry", "TEntry", "Text"])
def test_a_key_added_to_prevchar_moves_the_widget(root, kind):
    root.event_add("<<PrevChar>>", "<Key-F5>")
    if kind == "Text":
        widget = Text(root, name="w")
        widget.insert("1.0", "abc def")
        widget.mark_set("insert", "1.5")
    else:
        widget = CLASSES[kind](root, name="w")
        widget.insert(0, "abc def")
        widget.icursor(5)
    press(widget, "F5")
    assert widget.index("insert") in (4, "1.4")


@pytest.mark.parametrize(
    ("kind", "expected"),
    [("Entry", (8, 0, (8, 4, 8))), ("TEntry", (8, 0, (8, 4, 8))),
     ("TCombobox", (6, 3, (5, 4, 5))), ("TSpinbox", (6, 3, (5, 4, 5)))],
)  # fmt: skip
def test_a_hidden_entry_moves_by_word_to_an_end(root, kind, expected):
    """Measured on Tk 9.0.2 from 4 in ``ab cd ef`` with ``show="*"``: Entry
    and TEntry go to an end, as entry.tcl's class check says; the Combobox
    and the Spinbox move by word, since the check names neither."""
    widget = CLASSES[kind](root, name="w", show="*")
    widget.delete(0, "end")
    widget.insert(0, "ab cd ef")
    found = []
    for virtual in ("NextWord", "PrevWord", "SelectNextWord"):
        widget.icursor(4)
        widget.selection_clear()
        widget.event_generate(f"<<{virtual}>>")
        found.append(widget.index("insert"))
    found[2] = (found[2], widget.index("sel.first"), widget.index("sel.last"))
    assert tuple(found) == expected


def test_a_generated_nextword_moves_a_text(root):
    text = Text(root, name="t")
    text.insert("1.0", "abc def\nsecond line")
    text.mark_set("insert", "1.1")
    text.event_generate("<<NextWord>>")
    assert text.index("insert") == "1.4"


def test_prevline_steps_a_classic_spinbox(root):
    """spinbox.tcl: ``<<PrevLine>>`` is ``invoke buttonup``."""
    spinbox = Spinbox(root, name="s", from_=0, to=9)
    spinbox.event_generate("<<PrevLine>>")
    assert spinbox.get() == "1"


def test_a_ttk_spinbox_steps_on_up_and_not_on_prevline(root):
    """ttk/spinbox.tcl binds Up itself; ``<<PrevLine>>`` is TEntry's
    nothing. Measured on Tk 9.0.2 from 3: 3, then 4."""
    spinbox = ttk.Spinbox(root, name="s", from_=0, to=9)
    spinbox.set(3)
    spinbox.event_generate("<<PrevLine>>")
    after_virtual = spinbox.get()
    press(spinbox, "Up")
    assert (after_virtual, spinbox.get()) == ("3", "4")


@pytest.mark.parametrize("kind", ["Entry", "TEntry", "Text", "Spinbox", "TSpinbox"])
def test_a_navigation_key_also_reaches_all(root, kind):
    """Measured on Tk 9.0.2: none of these bindings breaks."""
    seen = []
    root.bind_all("<Key>", lambda event: seen.append(event.keysym))
    widget = Text(root, name="w") if kind == "Text" else CLASSES[kind](root, name="w")
    for key in ("Left", "Home", "Up", "Down"):
        press(widget, key)
    assert seen == ["Left", "Home", "Up", "Down"]


def test_a_paragraph_starts_past_its_indent(root):
    """text.tcl's paragraph procedures skip leading blanks. Measured on Tk
    9.0.2: from 1.1, NextPara gives 3.3 then 6.1; PrevPara from 4.2, 3.3."""
    text = Text(root, name="t")
    text.insert("1.0", "one\n\n   two\nmore\n\n\tthree\n")
    text.mark_set("insert", "1.1")
    found = []
    for virtual in ("NextPara", "NextPara"):
        text.event_generate(f"<<{virtual}>>")
        found.append(text.index("insert"))
    text.mark_set("insert", "4.2")
    text.event_generate("<<PrevPara>>")
    found.append(text.index("insert"))
    assert found == ["3.3", "6.1", "3.3"]
