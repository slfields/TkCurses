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


"""Multi-event binding sequences, as Tk follows them across events.

Every expectation was MEASURED twice - with wish8.6 and wish9.0, which agree -
using synthetic key events with real timestamps two seconds apart, and the
rules then READ from tkBind.c to explain the surprising ones. Driven here
through the real path: a widget's _handle, its bindtags, the table's dispatch.
TkCurses-jfm.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Frame, Misc, TclError
from tkcurses._core.bindings import EventPattern, PatternSequence, parse_sequence
from tkcurses._core.events import MOD_CTRL, KeyEvent, MouseEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 80, 24)
    root._mapped = True
    return root


def frame(root, name):
    widget = Frame(root, name=name)
    widget._allocate(Rect(0, 0, 10, 5))
    widget._map()
    return widget


@pytest.fixture
def a(root):
    return frame(root, "a")


def keys(widget, spec):
    """Press keys: "x" plain, "^x" with Control."""
    for token in spec.split():
        control = token.startswith("^")
        keysym = token.lstrip("^")
        widget._handle(
            KeyEvent(keysym=keysym, char="", modifiers=MOD_CTRL if control else 0)
        )


def fires(widget, sequence, spec):
    fired = []
    widget.bind(sequence, lambda event: fired.append(sequence))
    keys(widget, spec)
    widget.unbind(sequence)
    return len(fired)


# ------------------------------------------------------------- parsing


def test_a_chain_parses_to_its_events():
    parsed = parse_sequence("<Control-x><Control-s>")
    assert isinstance(parsed, PatternSequence)
    assert [str(p) for p in parsed.patterns] == ["<Control-Key-x>", "<Control-Key-s>"]
    assert str(parsed) == "<Control-Key-x><Control-Key-s>"


def test_bare_characters_are_a_sequence_of_keys():
    """Tk reads "ab" as <Key-a><Key-b>, measured: binding "ab" fires on a, b."""
    parsed = parse_sequence("ab")
    assert isinstance(parsed, PatternSequence)
    assert [p.detail for p in parsed.patterns] == ["a", "b"]


def test_one_event_is_still_a_pattern():
    assert isinstance(parse_sequence("<Control-x>"), EventPattern)
    assert isinstance(parse_sequence("a"), EventPattern)


# --------------------------------------------- the measured matrix

#: (sequence, keys pressed, fires) - each measured in wish8.6 and wish9.0.
MEASURED = [
    ("<Control-x><Control-s>", "^x ^s", True),
    ("<Control-x><Control-s>", "^x a ^s", False),  # a key in between breaks it
    ("<Control-x><Control-s>", "^x s", False),  # the right key, wrong modifiers
    ("<Control-x><Control-s>", "^x ^x ^s", False),  # the quirk
    ("<Control-x><Control-s>", "^x ^x ^x ^s", True),
    ("<Control-x><Control-s>", "^x ^s ^s", True),
    ("<Key-a><Key-b>", "a a b", False),
    ("<Key-a><Key-b>", "a a a b", True),
    ("<Key-a><Key-b>", "a a a a b", False),
    ("<Key-a><Key-b>", "b a b", True),
    ("<Key-a><Key-b><Key-c>", "a b c", True),
    ("<Key-a><Key-b><Key-c>", "a b a b c", True),  # dropped on another level
    ("<Key-a><Key-b><Key-c>", "a b b c", False),
    ("<Key-a><Key-b><Key-c>", "a a b c", False),
    ("<Key-a><Key-a>", "a a", True),
    ("<Key-a><Key-a>", "a a a", True),
    ("ab", "a b", True),
]


@pytest.mark.parametrize(("sequence", "spec", "expected"), MEASURED)
def test_what_tk_measured(a, sequence, spec, expected):
    assert bool(fires(a, sequence, spec)) is expected


@pytest.mark.parametrize(("presses", "times"), [(2, 1), (3, 1), (4, 2), (5, 2), (6, 3)])
def test_a_repeated_key_chord_fires_every_other_pair(a, presses, times):
    """Measured, both Tks: <Key-g><Key-g> with g pressed 2..6 times fires
    1, 1, 2, 2, 3 times - the key that completes one cannot start the next."""
    assert fires(a, "<Key-g><Key-g>", " ".join(["g"] * presses)) == times


def test_a_click_in_between_breaks_it(a):
    fired = []
    a.bind("<Control-x><Control-s>", lambda event: fired.append(1))
    keys(a, "^x")
    a._handle(MouseEvent(button=1, state="pressed", x=1, y=1))
    a._handle(MouseEvent(button=1, state="released", x=1, y=1))
    keys(a, "^s")
    assert fired == []


def test_motion_and_focus_in_between_do_not(a):
    fired = []
    a.bind("<Control-x><Control-s>", lambda event: fired.append(1))
    keys(a, "^x")
    a._handle(MouseEvent(button=0, state="motion", x=2, y=2))
    a.event_generate("<FocusOut>")
    a.event_generate("<FocusIn>")
    keys(a, "^s")
    assert fired == [1]


def test_a_sequence_does_not_span_two_widgets(root):
    """Measured with a class tag on both and the focus really moving: Ctrl-x
    in one, Ctrl-s in the other, fires nothing."""
    first, second = frame(root, "f1"), frame(root, "f2")
    fired = []
    for widget in (first, second):
        widget.bindtags((str(widget), "Both", "all"))
    root.bind_class("Both", "<Control-x><Control-s>", lambda event: fired.append(1))
    keys(first, "^x")
    keys(second, "^s")
    assert fired == []
    keys(second, "^x ^s")
    assert fired == [1]


def test_an_event_on_another_widget_in_between_cancels_it(root, a):
    """Measured, both Tks: a real resize of another widget, a synthetic
    <Configure> or an <Expose> on it, between Ctrl-x and Ctrl-s, and the
    pair does not fire; the same <Configure> on the widget itself does not
    stop it. tkBind.c drops a waiting sequence for any event in another
    window."""
    other = frame(root, "other")
    fired = []
    a.bind("<Control-x><Control-s>", lambda event: fired.append(1))
    keys(a, "^x")
    other.event_generate("<Configure>", width=5, height=2)
    keys(a, "^s")
    assert fired == []
    keys(a, "^x")
    a.event_generate("<Configure>", width=5, height=2)
    keys(a, "^s")
    assert fired == [1]


# ------------------------------------------------------------ choosing


def test_the_sequence_outranks_its_last_key(a):
    """Measured: with <Control-x>, <Control-s> and the pair all bound, Ctrl-x
    runs <Control-x>, and Ctrl-s runs only the pair."""
    fired = []
    for sequence in ("<Control-x>", "<Control-s>", "<Control-x><Control-s>"):
        a.bind(sequence, lambda event, s=sequence: fired.append(s))
    keys(a, "^x ^s")
    assert fired == ["<Control-x>", "<Control-x><Control-s>"]


def test_the_sequence_naming_more_keys_wins(a):
    """Measured, both Tks: with <Key-a><Key-b> and <Key><Key-b> bound, a then
    b runs only the first - it names two keys, the other one."""
    fired = []
    for sequence in ("<Key-a><Key-b>", "<Key><Key-b>"):
        a.bind(sequence, lambda event, s=sequence: fired.append(s))
    keys(a, "a b")
    assert fired == ["<Key-a><Key-b>"]


def test_each_tag_finishes_its_own(root, a):
    """A class binding and a widget binding on the same sequence both run."""
    fired = []
    a.bind("<Control-x><Control-s>", lambda event: fired.append("widget"))
    root.bind_class(
        "Frame", "<Control-x><Control-s>", lambda event: fired.append("class")
    )
    keys(a, "^x ^s")
    assert fired == ["widget", "class"]


# ------------------------------------------------- the rest of the API


def test_generating_a_sequence_is_refused_as_tk_refuses_it(a):
    """Measured: "only one event specification allowed", for both forms."""
    for sequence in ("<Control-x><Control-s>", "ab"):
        with pytest.raises(TclError, match="only one event specification allowed"):
            a.event_generate(sequence)


def test_a_virtual_event_from_a_sequence_is_listed_and_never_fires(root, a):
    """Measured: event add <<Save>> <Control-x><Control-s> is reported by
    event info and does not fire - "virtual events cannot promote"."""
    fired = []
    root.event_add("<<Save>>", "<Control-x><Control-s>")
    a.bind("<<Save>>", lambda event: fired.append(1))
    keys(a, "^x ^s")
    assert fired == []
    assert root.event_info("<<Save>>") == ("<Control-Key-x><Control-Key-s>",)


def test_a_key_inside_a_sequence_counts_as_bound(root, a):
    """Control-C has to reach the program for <Control-c><Control-c>, as it
    does for <Control-c>: the terminal would otherwise make it a signal."""
    a.bind("<Control-c><Control-c>", lambda event: None)
    assert "c" in root.tk.bindings.details_bound_with(MOD_CTRL)


def test_bind_reports_the_sequence_back(a):
    a.bind("<Control-x><Control-s>", lambda event: None)
    assert a.bind() == ("<Control-Key-x><Control-Key-s>",)


def test_unbinding_a_sequence_mid_way_stops_it(a):
    fired = []
    a.bind("<Control-x><Control-s>", lambda event: fired.append(1))
    keys(a, "^x")
    a.unbind("<Control-x><Control-s>")
    keys(a, "^s")
    assert fired == []


# ------------------------------------------- the click count, as Tk has it


def test_a_double_binding_fires_on_a_triple_click(a):
    """Tk's count rule is "at least": <Double-Button-1> matches "each button
    press but the first" (bind(n)). Ours required exactly two."""
    fired = []
    a.bind("<Double-Button-1>", lambda event: fired.append(1))
    for state in ("pressed", "double", "triple"):
        a._handle(MouseEvent(button=1, state=state, x=1, y=1))
    assert fired == [1, 1]


def test_a_triple_binding_still_wins_the_third_click(a):
    fired = []
    a.bind("<Double-Button-1>", lambda event: fired.append("double"))
    a.bind("<Triple-Button-1>", lambda event: fired.append("triple"))
    for state in ("pressed", "double", "triple"):
        a._handle(MouseEvent(button=1, state=state, x=1, y=1))
    assert fired == ["double", "triple"]
