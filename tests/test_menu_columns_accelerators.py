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


"""Menu: -columnbreak, and the accelerator helper. TkCurses-aj1.13.1.

The column rules were MEASURED on Tk 9.0.2 with xposition, yposition and the
@x,y index; Tk's keyboard traversal, read from menu.tcl, ignores columns.
bind_accelerators is not tkinter API: Tk's -accelerator is display only.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Entry, Menu, Misc, TclError
from tkcurses._core.events import MOD_ALT, MOD_CTRL, KeyEvent, MouseEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.menus import MenuEntry, accelerator_sequence, lay_out
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


#: The menu measured on Tk 9.0.2: three columns, the middle one narrow.
MEASURED = [
    ("One", "Ctrl+1", 0),
    ("Two longer label", "", 0),
    ("Three", "", 0),
    ("Four", "F4", 1),
    ("Five", "", 0),
    ("Six", "Ctrl+Shift+6", 1),
]


@pytest.fixture
def columns(root):
    menu = Menu(root, name="cols")
    for label, accelerator, brk in MEASURED:
        menu.add_command(label=label, accelerator=accelerator, columnbreak=brk)
    menu.post(0, 0)
    return menu


# ----------------------------------------------------------------- columns


def test_columnbreak_starts_a_column_at_the_top(columns):
    """Measured: Four and Six at y=1 - the top - beside the column before."""
    assert [columns.yposition(i) for i in range(6)] == [0, 1, 2, 0, 1, 0]
    xs = [columns.xposition(i) for i in range(6)]
    assert xs[0] == xs[1] == xs[2] == 0
    assert xs[3] == xs[4] > xs[0]
    assert xs[5] > xs[3]


def test_each_column_is_as_wide_as_its_own_entries(columns):
    """Measured: the middle column, Four and F4, is narrower than either
    neighbour (65 px against 166 and 116)."""
    first, middle, last = (
        columns.xposition(3) - columns.xposition(0),
        columns.xposition(5) - columns.xposition(3),
        columns.winfo_reqwidth() - columns.xposition(5),
    )
    assert middle < first
    assert middle < last


def test_the_menu_is_as_tall_as_its_tallest_column(columns):
    _, (_, height) = lay_out(columns._entries, indicators=False)
    assert height == 3


def test_a_break_on_the_first_entry_starts_nothing():
    entries = [MenuEntry("command", {"label": "A", "columnbreak": 1})]
    places, _ = lay_out(entries, indicators=False)
    assert places[0].x == 0 and places[0].row == 0


def test_a_separator_refuses_columnbreak(root):
    """Measured: Tk 9.0.2 answers "unknown option" for a separator."""
    menu = Menu(root, name="sep")
    with pytest.raises(TclError, match="unknown option"):
        menu.add_separator(columnbreak=1)
    menu.add_command(label="A")
    assert menu.entrycget(0, "columnbreak") == 0


def test_the_at_index_takes_a_column(columns):
    """Measured: "@x,y" picks by column; "@y" alone reads the first one."""
    area = columns._text_area()
    second = area.x + columns.xposition(3) + 1
    assert columns.index(f"@{second},{area.y + 1}") == 4
    assert columns.index(f"@{second},{area.y}") == 3
    assert columns.index(f"@{area.y + 1}") == 1


def test_a_click_in_a_column_chooses_its_entry(columns):
    chosen = []
    columns.entryconfigure(4, command=lambda: chosen.append("Five"))
    area = columns._text_area()
    x = columns.winfo_rootx() + area.x + columns.xposition(4) + 1
    y = columns.winfo_rooty() + area.y + columns.yposition(4)
    for state in ("pressed", "released"):
        columns._handle(MouseEvent(button=1, state=state, x=x, y=y))
    assert chosen == ["Five"]


def test_the_arrow_keys_go_by_index_across_columns(columns):
    """Tk's traversal (menu.tcl, MenuNextEntry) ignores columns: Down from
    the foot of one goes to the top of the next."""
    columns.activate(2)
    columns._handle(KeyEvent(keysym="Down"))
    assert columns.index("active") == 3


def test_a_menu_in_columns_does_not_scroll(root):
    """Columns are how a long menu is made short. Two of 30 on a 24-row
    screen: still the top, however far down the active entry is."""
    menu = Menu(root, name="tall")
    for n in range(60):
        menu.add_command(label=f"item {n}", columnbreak=1 if n == 30 else 0)
    menu.post(0, 0)
    menu.activate(29)
    assert menu._first == 0
    assert menu.yposition(29) == 29


def test_one_column_is_drawn_and_scrolls_as_before(root):
    menu = Menu(root, name="one")
    for n in range(40):
        menu.add_command(label=f"item {n}")
    menu.post(0, 0)
    menu.activate(39)
    assert menu._first > 0
    assert menu.xposition(39) == 0


# ------------------------------------------------------- reading the text


@pytest.mark.parametrize(
    ("text", "sequence"),
    [
        ("Ctrl+O", "<Control-Key-o>"),
        ("Ctrl-O", "<Control-Key-o>"),
        ("Control+o", "<Control-Key-o>"),
        ("^S", "<Control-Key-s>"),
        ("Alt+F4", "<Alt-Key-F4>"),
        ("Option+X", "<Alt-Key-x>"),
        ("Shift+F1", "<Shift-Key-F1>"),
        ("Ctrl+Shift+S", "<Control-Shift-Key-S>"),
        ("F5", "<Key-F5>"),
        ("Del", "<Key-Delete>"),
        ("Ctrl+PgUp", "<Control-Key-Prior>"),
        ("Esc", "<Key-Escape>"),
        ("Ctrl++", "<Control-Key-plus>"),
        ("Ctrl+-", "<Control-Key-minus>"),
        ("Ctrl+,", "<Control-Key-comma>"),
        ("Ctrl+>", "<Control-Key-greater>"),
        ("Ctrl+X Ctrl+S", "<Control-Key-x><Control-Key-s>"),
        ("Ctrl+K, Ctrl+C", "<Control-Key-k><Control-Key-c>"),
    ],
)
def test_an_accelerator_is_read_as_people_write_it(text, sequence):
    assert accelerator_sequence(text) == sequence


@pytest.mark.parametrize("text", ["", "Ctrl+", "Hyper+X", "Ctrl+Click", "F25"])
def test_text_it_cannot_read_is_refused(text):
    with pytest.raises(ValueError):
        accelerator_sequence(text)


# --------------------------------------------------------- binding them


@pytest.fixture
def app(root):
    """A menubar-style File menu with a submenu, and a field to type in."""
    chosen = []
    file = Menu(root, name="file")
    file.add_command(
        label="Open", accelerator="Ctrl+O", command=lambda: chosen.append("open")
    )
    file.add_command(
        label="Save", accelerator="Ctrl+X Ctrl+S", command=lambda: chosen.append("save")
    )
    file.add_command(
        label="Print",
        accelerator="Ctrl+P",
        state="disabled",
        command=lambda: chosen.append("print"),
    )
    recent = Menu(file, name="recent")
    recent.add_command(
        label="Last", accelerator="Alt+1", command=lambda: chosen.append("last")
    )
    file.add_cascade(label="Recent", menu=recent)
    field = Entry(root, name="field")
    field._allocate(Rect(0, 20, 20, 3))
    field._map()
    field.focus_set()
    return SimpleNamespace(file=file, recent=recent, field=field, chosen=chosen)


def press(widget, keysym, modifiers=0):
    widget._handle(KeyEvent(keysym=keysym, char="", modifiers=modifiers))


def test_one_call_binds_every_accelerator(app):
    bound = app.file.bind_accelerators()
    assert bound == [
        "<Control-Key-o>",
        "<Control-Key-x><Control-Key-s>",
        "<Control-Key-p>",
        "<Alt-Key-1>",
    ]
    press(app.field, "o", MOD_CTRL)
    press(app.field, "x", MOD_CTRL)
    press(app.field, "s", MOD_CTRL)
    press(app.field, "1", MOD_ALT)
    assert app.chosen == ["open", "save", "last"]


def test_a_disabled_entrys_shortcut_does_nothing(app):
    app.file.bind_accelerators()
    press(app.field, "p", MOD_CTRL)
    assert app.chosen == []


def test_an_entry_inserted_before_does_not_move_a_shortcut(app):
    app.file.bind_accelerators()
    app.file.insert_command(0, label="New", command=lambda: app.chosen.append("new"))
    press(app.field, "o", MOD_CTRL)
    assert app.chosen == ["open"]


def test_a_deleted_entrys_shortcut_does_nothing(app):
    app.file.bind_accelerators()
    app.file.delete(0)
    press(app.field, "o", MOD_CTRL)
    assert app.chosen == []


def test_it_adds_to_what_is_bound_rather_than_replacing_it(app, root):
    mine = []
    root.bind_all("<Control-Key-o>", lambda event: mine.append(1))
    app.file.bind_accelerators()
    press(app.field, "o", MOD_CTRL)
    assert mine == [1] and app.chosen == ["open"]


def test_text_it_cannot_read_binds_nothing_at_all(app, root):
    app.recent.add_command(label="Odd", accelerator="Ctrl+Click")
    with pytest.raises(ValueError, match="'Odd'"):
        app.file.bind_accelerators()
    press(app.field, "o", MOD_CTRL)
    assert app.chosen == []


def test_a_target_narrows_where_it_binds(app, root):
    other = Entry(root, name="other")
    other._allocate(Rect(30, 20, 20, 3))
    other._map()
    app.file.bind_accelerators(target=app.field)
    press(other, "o", MOD_CTRL)
    assert app.chosen == []
    press(app.field, "o", MOD_CTRL)
    assert app.chosen == ["open"]


def test_left_in_a_menubar_dropdown_moves_along_the_bar(root):
    """Tk's MenuNextMenu: Left in a dropdown of the menubar opens the menu
    to its left; only a submenu closes back to its parent. Found while
    writing UAT 46's checklist: Left closed the dropdown instead."""
    bar = Menu(root, name="bar")
    first, second = Menu(bar, name="first"), Menu(bar, name="second")
    first.add_command(label="A")
    second.add_command(label="B")
    deeper = Menu(second, name="deeper")
    deeper.add_command(label="C")
    second.add_cascade(label="More", menu=deeper)
    bar.add_cascade(label="First", menu=first)
    bar.add_cascade(label="Second", menu=second)
    bar._as_menubar = True  # as test_menu.py's menubar tests make one
    bar.activate(1)
    bar.invoke(1)
    second.activate(1)
    second.invoke(1)  # the submenu
    deeper._handle(KeyEvent(keysym="Left"))
    assert bar._open_cascade is not None, "Left in a submenu closes only it"
    assert second._open_cascade is None
    second._handle(KeyEvent(keysym="Left"))
    assert bar.index("active") == 0


def test_an_open_menu_keeps_every_key_from_the_shortcuts(app, root):
    """Tk's Menu class: <KeyPress> {tk::TraverseWithinMenu %W %A; break}.
    Found by the author in UAT 46: F5 chose "Last file" while Colours was
    open, because a key with no use in the menu was let through."""
    app.file.bind_accelerators()
    other = Menu(root, name="other")
    other.add_command(label="Nothing to do with F5")
    other.post(0, 0)
    other._handle(KeyEvent(keysym="F5", char=""))
    other._handle(KeyEvent(keysym="o", char="", modifiers=MOD_CTRL))
    assert app.chosen == []


def test_escape_from_a_menubar_dropdown_clears_the_bar(root):
    """Tk's MenuUnpost, read from Tk 9.0.2: a dropdown of the menubar takes
    the bar's highlight with it ("$parent activate {}"). Found by the author
    in UAT 46: Colours stayed highlighted after Escape, as if the arrows would
    walk the bar, and they did not."""
    bar = Menu(root, name="bar")
    first = Menu(bar, name="first")
    first.add_command(label="A")
    bar.add_cascade(label="First", menu=first)
    bar._as_menubar = True
    bar.activate(0)
    bar.invoke(0)
    assert bar.index("active") == 0
    first._handle(KeyEvent(keysym="Escape"))
    assert bar.index("active") is None
    assert bar._open_cascade is None
