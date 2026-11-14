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

"""Scale, Scrollbar and Menu take Tk's navigation virtual events.

scale.tcl, ttk/scale.tcl, scrlbar.tcl and menu.tcl bind ``<<PrevLine>>``,
``<<NextChar>>`` and the rest rather than the keys, so a key a program
``event_add``s to one of them works there too. Each table below was measured
through tkinter on Tk 9.0.2 - a widget with the focus, one key generated, the
value or the scroll command read back - and the live tests check it again
when there is a display.
"""

from __future__ import annotations

import tkinter
from tkinter import ttk as real_ttk
from types import SimpleNamespace

import pytest

from tkcurses import Menu, Misc, Scale, Scrollbar, ttk
from tkcurses._core.events import MOD_CTRL, KeyEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack

#: Each key as Tk names it, and as a KeyEvent carries it.
KEYS = {
    "<Up>": ("Up", 0),
    "<Down>": ("Down", 0),
    "<Left>": ("Left", 0),
    "<Right>": ("Right", 0),
    "<Control-Up>": ("Up", MOD_CTRL),
    "<Control-Down>": ("Down", MOD_CTRL),
    "<Control-Left>": ("Left", MOD_CTRL),
    "<Control-Right>": ("Right", MOD_CTRL),
    "<Prior>": ("Prior", 0),
    "<Next>": ("Next", 0),
    "<Home>": ("Home", 0),
    "<End>": ("End", 0),
    "<Control-p>": ("p", MOD_CTRL),
    "<Control-f>": ("f", MOD_CTRL),
}

#: A scale from 0 to 100 set to 50, after one key: (classic with resolution 2
#: and bigincrement 0, ttk). Both orientations answer alike, and so does a
#: reversed scale with the two directions swapped.
SCALE = {
    "<Up>": (48, 49),
    "<Down>": (52, 51),
    "<Left>": (48, 49),
    "<Right>": (52, 51),
    "<Control-Up>": (40, 40),
    "<Control-Down>": (60, 60),
    "<Control-Left>": (40, 40),
    "<Control-Right>": (60, 60),
    "<Prior>": (50, 50),
    "<Next>": (50, 50),
    "<Home>": (0, 0),
    "<End>": (100, 100),
    "<Control-p>": (48, 49),
    "<Control-f>": (52, 51),
}

#: The scroll command a classic scrollbar runs for each key, (vertical,
#: horizontal); None for none.
SCROLLBAR = {
    "<Up>": (("scroll", -1, "units"), None),
    "<Down>": (("scroll", 1, "units"), None),
    "<Left>": (None, ("scroll", -1, "units")),
    "<Right>": (None, ("scroll", 1, "units")),
    "<Control-Up>": (("scroll", -1, "pages"), None),
    "<Control-Down>": (("scroll", 1, "pages"), None),
    "<Control-Left>": (None, ("scroll", -1, "pages")),
    "<Control-Right>": (None, ("scroll", 1, "pages")),
    "<Prior>": (("scroll", -1, "pages"), ("scroll", -1, "pages")),
    "<Next>": (("scroll", 1, "pages"), ("scroll", 1, "pages")),
    "<Home>": (("moveto", 0), ("moveto", 0)),
    "<End>": (("moveto", 1), ("moveto", 1)),
    "<Control-p>": (("scroll", -1, "units"), None),
    "<Control-f>": (None, ("scroll", 1, "units")),
}


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(window_factory=stub_window, panel_factory=None)
    root._rect = Rect(0, 0, 60, 24)
    root._mapped = True
    return root


def press(widget, key):
    keysym, modifiers = KEYS[key]
    return widget._handle(KeyEvent(keysym=keysym, modifiers=modifiers))


def scroll_calls(command_log):
    """The calls a scroll command saw, with Tk's strings made numbers."""
    calls = []
    for call in command_log:
        calls.append(tuple(float(v) if v[:1] in "-0123456789" else v for v in call))
    return calls


# ---------------------------------------------------------------- Scale


@pytest.mark.parametrize("key", list(SCALE))
@pytest.mark.parametrize("orient", ["vertical", "horizontal"])
def test_a_scale_answers_each_key_as_tk_does(root, key, orient):
    classic = Scale(root, from_=0, to=100, resolution=2, bigincrement=0, orient=orient)
    themed = ttk.Scale(root, from_=0, to=100, orient=orient)
    for widget in (classic, themed):
        widget.set(50)
        press(widget, key)
    assert (classic.get(), themed.get()) == SCALE[key]


@pytest.mark.parametrize("key", ["<Up>", "<Right>", "<Control-Down>", "<Home>"])
def test_a_reversed_scale_steps_the_other_way(root, key):
    classic = Scale(root, from_=100, to=0, resolution=2, bigincrement=0)
    themed = ttk.Scale(root, from_=100, to=0)
    for widget in (classic, themed):
        widget.set(50)
        press(widget, key)
    assert (classic.get(), themed.get()) == tuple(100 - v for v in SCALE[key])


def test_a_disabled_scale_does_not_move(root):
    classic = Scale(root, from_=0, to=100)
    themed = ttk.Scale(root, from_=0, to=100)
    for widget in (classic, themed):
        widget.set(50)
        widget.configure(state="disabled")
        for key in ("<Up>", "<Control-Down>", "<Home>", "<End>"):
            press(widget, key)
        assert widget.get() == 50


def test_no_key_stops_at_the_scale(root):
    """None of the scripts' bindings breaks: the key goes on to ``all``."""
    heard = []
    root.bind_all("<Key>", lambda event: heard.append(event.keysym))
    scale = Scale(root, from_=0, to=100)
    for key in ("<Up>", "<Control-Left>", "<Home>", "<Prior>"):
        press(scale, key)
    assert heard == ["Up", "Left", "Home", "Prior"]


def test_a_key_added_to_a_navigation_event_moves_a_scale(root):
    root.event_add("<<NextLine>>", "<Key-j>")
    scale = Scale(root, from_=0, to=10)
    scale._handle(KeyEvent(keysym="j", char="j"))
    assert scale.get() == 1


# ------------------------------------------------------------ Scrollbar


@pytest.mark.parametrize("key", list(SCROLLBAR))
def test_a_scrollbar_answers_each_key_as_tk_does(root, key):
    seen = {}
    for orient in ("vertical", "horizontal"):
        log = []
        bar = Scrollbar(root, orient=orient, command=lambda *a, log=log: log.append(a))
        press(bar, key)
        seen[orient] = log[0] if log else None
    assert (seen["vertical"], seen["horizontal"]) == SCROLLBAR[key]


def test_a_scrollbar_without_a_command_ignores_the_keys(root):
    bar = Scrollbar(root)
    for key in SCROLLBAR:
        press(bar, key)


def test_a_themed_scrollbar_binds_no_keys(root):
    """ttk/scrollbar.tcl copies only the wheel bindings from Scrollbar."""
    log = []
    bar = ttk.Scrollbar(root, command=lambda *a: log.append(a))
    for key in SCROLLBAR:
        press(bar, key)
    assert log == []


def test_a_key_added_to_a_navigation_event_scrolls(root):
    root.event_add("<<NextLine>>", "<Key-j>")
    log = []
    bar = Scrollbar(root, command=lambda *a: log.append(a))
    bar._handle(KeyEvent(keysym="j", char="j"))
    assert log == [("scroll", 1, "units")]


# ----------------------------------------------------------------- Menu


def test_a_key_added_to_a_navigation_event_moves_through_a_menu(root):
    root.event_add("<<NextLine>>", "<Key-j>")
    menu = Menu(root, name="m")
    for label in ("New", "Open", "Quit"):
        menu.add_command(label=label)
    menu.post(0, 0)
    menu._handle(KeyEvent(keysym="j", char="j"))
    menu._handle(KeyEvent(keysym="j", char="j"))
    assert menu._active == 1


def test_the_emacs_keys_move_through_a_menu(root):
    menu = Menu(root, name="m")
    for label in ("New", "Open", "Quit"):
        menu.add_command(label=label)
    menu.post(0, 0)
    menu._handle(KeyEvent(keysym="n", modifiers=MOD_CTRL))
    menu._handle(KeyEvent(keysym="n", modifiers=MOD_CTRL))
    menu._handle(KeyEvent(keysym="p", modifiers=MOD_CTRL))
    assert menu._active == 0


def test_with_the_arrow_taken_from_its_event_a_menu_ignores_it(root):
    """menu.tcl binds the event, not the key, so a program that deletes
    ``<Down>`` from ``<<NextLine>>`` takes Down from its menus too."""
    root.event_delete("<<NextLine>>", "<Key-Down>")
    menu = Menu(root, name="m")
    menu.add_command(label="New")
    menu.post(0, 0)
    menu._handle(KeyEvent(keysym="Down"))
    assert menu._active is None


# --------------------------------------------- the tables, checked on Tk


@pytest.fixture
def real():
    try:
        real = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    yield real
    real.destroy()


def _generate(real, widget, key):
    widget.pack()
    real.update()
    widget.focus_force()
    real.update()
    widget.event_generate(key)
    real.update()


def test_the_scale_table_is_tks(real):
    for key, expected in SCALE.items():
        got = []
        for make in (
            lambda: tkinter.Scale(real, from_=0, to=100, resolution=2, bigincrement=0),
            lambda: real_ttk.Scale(real, from_=0, to=100),
        ):
            widget = make()
            widget.set(50)
            _generate(real, widget, key)
            got.append(widget.get())
            widget.destroy()
        assert tuple(got) == expected, key


def test_the_scrollbar_table_is_tks(real):
    for key, expected in SCROLLBAR.items():
        got = []
        for orient in ("vertical", "horizontal"):
            log = []
            bar = tkinter.Scrollbar(
                real, orient=orient, command=lambda *a, log=log: log.append(a)
            )
            _generate(real, bar, key)
            calls = scroll_calls(log)
            got.append(calls[0] if calls else None)
            bar.destroy()
        assert tuple(got) == expected, key
