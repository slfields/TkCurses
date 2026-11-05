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


"""What ``event_generate``'s ``keysym=``, ``button=`` and ``state=`` decide,
and the state number events report, held to Tk 9.0.2. TkCurses-vnmk."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Frame, Misc, TclError
from tkcurses._core.events import (
    MOD_ALT,
    MOD_BUTTON1,
    MOD_CTRL,
    MOD_SHIFT,
    KeyEvent,
    MouseEvent,
)
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack

BOUND = (
    "<Key>",
    "<Key-Up>",
    "<Shift-Key-Up>",
    "<Control-Key-Up>",
    "<Key-b>",
    "<Button-1>",
    "<Button-3>",
    "<Shift-Button-1>",
)


@pytest.fixture
def frame():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 40, 20)
    root._mapped = True
    frame = Frame(root, width=10, height=5)
    frame._allocate(Rect(0, 0, 10, 5))
    frame._map()
    frame.focus_set()
    return frame


def fired(frame, sequence, **options):
    """Which of BOUND runs for one generated event, and what it reports."""
    log = []
    for bound in BOUND:
        frame.bind(bound, lambda e, s=bound: log.append((s, e.state)))
    frame.event_generate(sequence, **options)
    return log


@pytest.mark.parametrize(
    ("sequence", "options", "expected"),
    [
        ("<KeyPress>", {"keysym": "Up", "state": 1}, ("<Shift-Key-Up>", 1)),
        ("<KeyPress>", {"keysym": "Up", "state": 4}, ("<Control-Key-Up>", 4)),
        ("<KeyPress>", {"keysym": "Up"}, ("<Key-Up>", 0)),
        ("<Shift-KeyPress-Up>", {}, ("<Shift-Key-Up>", 1)),
        ("<Shift-KeyPress-Up>", {"state": 0}, ("<Key-Up>", 0)),
        ("<KeyPress-a>", {"keysym": "b"}, ("<Key-b>", 0)),
        ("<Control-KeyPress-Up>", {"state": 1}, ("<Shift-Key-Up>", 1)),
        ("<KeyPress>", {"keysym": "Up", "state": "1"}, ("<Shift-Key-Up>", 1)),
        ("<ButtonPress>", {"button": 3}, ("<Button-3>", 0)),
        ("<ButtonPress-1>", {"button": 3}, ("<Button-3>", 0)),
        ("<ButtonPress-1>", {"state": 1}, ("<Shift-Button-1>", 1)),
    ],
)
def test_the_options_take_the_place_of_the_sequence(frame, sequence, options, expected):
    """Measured on Tk 9.0.2, one Frame with every BOUND sequence on it."""
    assert fired(frame, sequence, **options) == [expected]


def test_a_state_tk_refuses_is_refused(frame):
    with pytest.raises(TclError, match='expected integer but got "x"'):
        frame.event_generate("<KeyPress>", state="x")


@pytest.mark.parametrize(
    ("sequence", "state"),
    [
        ("<Shift-KeyPress-a>", 1),
        ("<Control-KeyPress-a>", 4),
        ("<Control-Shift-KeyPress-a>", 5),
        ("<Alt-KeyPress-a>", 131072),
        ("<Meta-KeyPress-a>", 65536),
        ("<B1-Motion>", 256),
        ("<B3-Motion>", 1024),
        ("<B5-Motion>", 4096),
    ],
)
def test_a_generated_event_reports_tks_state(frame, sequence, state):
    """Measured: a generated Alt and Meta report Tk's own masks."""
    seen = []
    frame.bind("<KeyPress>", lambda e: seen.append(e.state))
    frame.bind("<Motion>", lambda e: seen.append(e.state))
    frame.event_generate(sequence)
    assert seen == [state]


def test_mod1_is_alt(frame):
    """Measured: ``state=8`` fires an ``<Alt-...>`` binding - Alt is Mod1."""
    seen = []
    frame.bind("<Alt-KeyPress-b>", lambda e: seen.append(e.state))
    frame.event_generate("<KeyPress>", keysym="b", state=8)
    assert seen == [8]


@pytest.mark.parametrize(
    ("modifiers", "state"),
    [(MOD_SHIFT, 1), (MOD_CTRL, 4), (MOD_ALT, 8), (MOD_CTRL | MOD_SHIFT, 5)],
)
def test_a_key_from_the_terminal_reports_tks_state(frame, modifiers, state):
    """As X11 reports a real key: Alt is Mod1, 8, not the generated mask."""
    seen = []
    frame.bind("<Any-KeyPress>", lambda e: seen.append(e.state))
    frame._handle(KeyEvent(keysym="a", char="a", modifiers=modifiers))
    assert seen == [state]


def test_a_drag_reports_the_held_button(frame):
    seen = []
    frame.bind("<B1-Motion>", lambda e: seen.append(e.state))
    frame._handle(MouseEvent(x=2, y=2, button=1, state="drag", modifiers=MOD_BUTTON1))
    assert seen == [256]
