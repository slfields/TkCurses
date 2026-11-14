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

"""Tear-off menus: ``-tearoff``, the tear-off entry, and the torn-off copy.

Measured on Tk 9.0.2 and compared call by call where Tk can answer: the
tear-off entry is index 0, of type ``tearoff``, with only ``background`` and
``state``; nothing is inserted ahead of it and nothing deletes it;
``tearoff`` turned on and off adds and removes it. Invoking it is
``tk::TearOffMenu``: a copy named ``tearoff1`` of type ``tearoff`` in the
nearest toplevel, titled by the Menubutton or cascade it came from, which
stays up after a choice, and ``tearoffcommand`` is called with both names.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tkcurses import (
    Menu,
    Menubutton,
    Misc,
    TclError,
    _menu_click,
    _menu_drag,
    _menu_release,
)
from tkcurses._core.events import KeyEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack

tkinter = pytest.importorskip("tkinter")


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(window_factory=stub_window, panel_factory=None)
    root._rect = Rect(0, 0, 60, 30)
    root._mapped = True
    return root


#: Each a call on a menu made with tearoff=1 and one command "a".
STEPS: list[tuple[str, Any]] = [
    ("end", lambda m: m.index("end")),
    ("type 0", lambda m: m.type(0)),
    ("type 1", lambda m: m.type(1)),
    ("label of a", lambda m: m.index("a")),
    ("entrycget state", lambda m: m.entrycget(0, "state")),
    ("entrycget label", lambda m: m.entrycget(0, "label")),
    ("entryconfigure keys", lambda m: sorted(m.entryconfigure(0))),
    ("insert at 0", lambda m: m.insert_command(0, label="z")),
    (
        "after insert",
        lambda m: [m.type(i) for i in range(3)] + [m.entrycget(1, "label")],
    ),
    ("delete 0", lambda m: m.delete(0)),
    ("after delete 0", lambda m: m.index("end")),
    ("delete all", lambda m: m.delete(0, "end")),
    ("after delete all", lambda m: (m.index("end"), m.type(0))),
    ("add tearoff", lambda m: m.add("tearoff")),
    ("add again", lambda m: m.add_command(label="b")),
    ("tearoff off", lambda m: m.configure(tearoff=0)),
    ("after off", lambda m: (m.index("end"), m.type(0))),
    ("tearoff on", lambda m: m.configure(tearoff=1)),
    ("after on", lambda m: (m.index("end"), m.type(0), m.type(1))),
    ("disable it", lambda m: m.entryconfigure(0, state="disabled")),
    ("disabled", lambda m: m.entrycget(0, "state")),
]


def _run(menu: Any, errors: tuple[type, ...]) -> list:
    menu.add_command(label="a")
    answers = []
    for label, step in STEPS:
        try:
            answers.append((label, step(menu)))
        except errors as error:
            answers.append((label, "error", str(error)))
    return answers


def test_the_tearoff_entry_answers_as_tks_does(root):
    try:
        real = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    try:
        theirs = _run(tkinter.Menu(real, tearoff=1), (tkinter.TclError,))
        default = tkinter.Menu(real).cget("tearoff")
    finally:
        real.destroy()
    assert _run(Menu(root, tearoff=1), (TclError,)) == theirs
    assert Menu(root).cget("tearoff") == default == 0


def test_invoking_it_tears_the_menu_off(root):
    seen = []
    menu = Menu(root, tearoff=1, tearoffcommand=lambda *names: seen.append(names))
    menu.add_command(label="Hammer", command=lambda: seen.append("hammer"))
    menu.add_checkbutton(label="Sharp")
    menu.post(5, 4)
    name = menu.invoke(0)
    assert name == ".tearoff1"
    assert seen == [(".!menu", ".tearoff1")]
    assert not menu._posted
    copy = root.nametowidget(name)
    assert isinstance(copy, Menu)
    assert copy.cget("type") == "tearoff"
    assert copy.cget("tearoff") == 1
    assert [copy.type(n) for n in range(3)] == ["tearoff", "command", "checkbutton"]
    # Where the menu was, and taking no room for its own tear-off entry.
    assert (copy.winfo_rootx(), copy.winfo_rooty()) == (5, 4)
    assert copy.yposition(0) == copy.yposition(1) == 0
    # A choice runs and leaves it up.
    copy.invoke(1)
    assert seen[-1] == "hammer"
    assert copy._posted
    # The next copy takes the next name.
    menu.post(5, 4)
    assert menu.invoke(0) == ".tearoff2"


def test_a_torn_off_menu_takes_no_grab(root):
    menu = Menu(root, tearoff=1)
    menu.add_command(label="a")
    copy = root.nametowidget(menu.invoke(0))
    assert root.grab_current() is not copy


def test_the_arrows_skip_a_torn_off_menus_tearoff_entry(root):
    menu = Menu(root, tearoff=1)
    menu.add_command(label="a")
    menu.add_command(label="b")
    menu.post(0, 0)
    menu._handle(KeyEvent(keysym="Down"))
    assert menu._active == 0  # the tear-off entry, in the menu itself
    copy = root.nametowidget(menu.invoke(0))
    # Down from nothing, then wrapping round past the hidden entry 0.
    for expected in (1, 2, 1):
        copy._handle(KeyEvent(keysym="Down"))
        assert copy._active == expected


@pytest.mark.parametrize(
    ("make", "title"),
    [
        (lambda root: Menu(root, tearoff=1, title="Mine"), "Mine"),
        (lambda root: Menu(Menubutton(root, text="Edit"), tearoff=1), "Edit"),
        (lambda root: Menu(root, tearoff=1), "tearoff1"),
    ],
)
def test_the_copy_is_titled_as_tk_titles_it(root, make, title):
    menu = make(root)
    menu.add_command(label="x")
    copy = root.nametowidget(menu.invoke(0))
    assert copy._torn_title == title


def test_a_cascades_tear_off_is_titled_by_the_cascade(root):
    bar = Menu(root)
    sub = Menu(bar, tearoff=1)
    sub.add_command(label="x")
    bar.add_cascade(label="Colours", menu=sub)
    bar._as_menubar = True
    # Opened from the bar, as a click or F10 opens it: tearing off unposts
    # it, which clears the bar's active entry, so the title is read first.
    bar._open(0)
    assert sub._posted
    copy = root.nametowidget(sub.invoke(0))
    assert copy._torn_title == "Colours"
    assert str(copy) == ".tearoff1"


def test_escape_closes_a_torn_off_menu(root):
    menu = Menu(root, tearoff=1)
    menu.add_command(label="x")
    copy = root.nametowidget(menu.invoke(0))
    copy._handle(KeyEvent(keysym="Escape"))
    assert not copy.winfo_exists()


def test_a_menubar_counts_its_tearoff_entry_and_does_not_draw_it(root):
    bar = Menu(root, tearoff=1)
    bar.add_cascade(label="File")
    bar._as_menubar = True
    assert bar.index("end") == 1
    assert bar._entry_at_column(bar._text_area().x) == 1
    assert bar._label_column(1) == bar._text_area().x


def test_tk_tears_off_as_described():
    try:
        real = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    try:
        seen = []
        button = tkinter.Menubutton(real, text="Edit")
        menu = tkinter.Menu(button, tearoff=1, tearoffcommand=lambda *a: seen.append(a))
        menu.add_command(label="One")
        name = str(menu.invoke(0))
        real.update()
        assert name == ".tearoff1"
        assert seen == [(str(menu), ".tearoff1")]
        assert real.tk.eval(f"{name} cget -type") == "tearoff"
        assert real.tk.eval(f"wm title {name}") == "Edit"
        assert real.tk.eval(f"{name} yposition 0") == real.tk.eval(
            f"{name} yposition 1"
        )
    finally:
        real.destroy()


# ------------------------------------------------------------- on screen

PROGRAM = """
import tkcurses as tk
root = tk.Tk()
out = tk.Label(root, text="-")
out.place(x=30, y=10)
mb = tk.Menubutton(root, text="Tools")
mb.place(x=1, y=1)
m = tk.Menu(mb, tearoff=1)
mb["menu"] = m
m.add_command(label="Hammer", command=lambda: out.configure(text="hammer"))
m.add_command(label="Saw", command=lambda: out.configure(text="saw"))
root.after(50, lambda: m.post(3, 3))
root.mainloop()
"""


@pytest.mark.tty
def test_a_torn_off_menu_stays_up_and_takes_clicks(terminal, tmp_path):
    term = terminal(cols=50, rows=14)
    term.run_source(PROGRAM, workdir=tmp_path)
    term.wait_for_cell(4, 5, lambda c: c.data == "╌", message="the tear-off line")
    term.click(5, 4)
    term.wait_for(
        lambda t: "─Tools──" in t.row(3) and "Hammer" in t.row(4),
        message="the torn-off copy, titled",
    )
    term.click(6, 4)
    term.wait_for(
        lambda t: "hammer" in t.row(10) and "Hammer" in t.row(4),
        message="the command run, and the copy still up",
    )
    term.send(b"\x1b")
    term.wait_for(lambda t: "Hammer" not in t.row(4), message="Escape closing it")


def test_a_submenu_of_a_torn_off_menu_closes_without_a_grab(root):
    sub = Menu(root)
    sub.add_command(label="Inner")
    menu = Menu(root, tearoff=1)
    menu.add_cascade(label="More", menu=sub)
    copy = root.nametowidget(menu.invoke(0))
    copy.invoke(1)
    assert sub._posted
    assert root.grab_current() is sub
    sub._handle(KeyEvent(keysym="Escape"))
    assert not sub._posted
    assert copy._posted
    assert root.grab_current() is None


# ------------------------------------------------------------- dragging


def pointer(widget, x, y):
    return SimpleNamespace(widget=widget, x_root=x, y_root=y)


def torn_copy(root):
    menu = Menu(root, tearoff=1, title="Tools")
    menu.add_command(label="Hammer")
    menu.add_command(label="Saw")
    menu.post(5, 4)
    return root.nametowidget(menu.invoke(0))


def test_dragging_the_title_moves_a_torn_off_menu(root):
    copy = torn_copy(root)
    _menu_click(pointer(copy, 7, 4))  # the title row
    _menu_drag(pointer(copy, 12, 6))
    _menu_drag(pointer(copy, 17, 9))
    _menu_release(pointer(copy, 17, 9))
    assert (copy.winfo_rootx(), copy.winfo_rooty()) == (15, 9)
    # The drag is over: motion follows the entries again.
    _menu_drag(pointer(copy, 30, 20))
    assert (copy.winfo_rootx(), copy.winfo_rooty()) == (15, 9)


def test_a_dragged_menu_stays_on_the_screen(root, monkeypatch):
    monkeypatch.setattr(Menu, "_screen_size", lambda self: (60, 30))
    copy = torn_copy(root)
    _menu_click(pointer(copy, 7, 4))
    _menu_drag(pointer(copy, -50, -50))
    assert (copy.winfo_rootx(), copy.winfo_rooty()) == (0, 0)
    _menu_drag(pointer(copy, 500, 500))
    assert copy.winfo_rootx() + copy.winfo_width() == 60
    assert copy.winfo_rooty() + copy.winfo_height() == 30


def test_a_press_on_an_entry_chooses_it_and_does_not_drag(root):
    copy = torn_copy(root)
    seen = []
    copy.entryconfigure(1, command=lambda: seen.append("hammer"))
    _menu_click(pointer(copy, 8, 5))
    assert seen == ["hammer"]
    assert copy._drag_origin is None


def test_a_posted_menu_is_not_dragged_by_its_top_edge(root):
    menu = Menu(root)
    menu.add_command(label="a")
    menu.post(5, 4)
    _menu_click(pointer(menu, 7, 4))
    assert menu._drag_origin is None
    _menu_drag(pointer(menu, 20, 10))
    assert (menu.winfo_rootx(), menu.winfo_rooty()) == (5, 4)
