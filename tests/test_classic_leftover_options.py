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

"""The per-widget options left over from TkCurses-gm66.10.

Canvas ``confine``, ``offset`` and the scroll increments; Listbox ``justify``
and ``listvariable``; Menu ``type``, ``font`` and ``tearoffcommand``;
LabelFrame ``labelwidget``; the check and radio buttons' ``selectimage`` and
``tristateimage``, and Radiobutton's ``tristatevalue``. Each rule was measured
on Tk 9.0.2 and is cited where it is asserted.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import (
    Canvas,
    Checkbutton,
    Frame,
    Label,
    LabelFrame,
    Listbox,
    Menu,
    Misc,
    PhotoImage,
    Radiobutton,
    StringVar,
    TclError,
    Toplevel,
    Variable,
    _tcl_index,
    _tcl_list,
)
from tkcurses._core.attributes import from_font
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    return root


# ------------------------------------------------------------------- Canvas


@pytest.fixture
def canvas(root):
    """A canvas 40 cells by 10, a plane 40 pixels by 20, over a region ten
    times that."""
    widget = Canvas(root, name="c", width=40, height=10, relief="flat")
    widget._allocate(Rect(0, 0, 40, 10))
    widget._map()
    widget.configure(scrollregion=(0, 0, 400, 200))
    return widget


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("confine", 1),
        ("offset", "0,0"),
        ("xscrollincrement", 0),
        ("yscrollincrement", 0),
    ],
)
def test_canvas_defaults(root, name, value):
    assert Canvas(root).cget(name) == value


def test_confine_is_a_boolean(root):
    assert Canvas(root, confine="no").cget("confine") == 0
    with pytest.raises(TclError, match='expected boolean value but got "maybe"'):
        Canvas(root, confine="maybe")


@pytest.mark.parametrize("value", ["5,3", "#5,3", "n", "center", "-2,1.5"])
def test_an_offset_tk_takes(root, value):
    assert Canvas(root, offset=value).cget("offset") == value


@pytest.mark.parametrize("value", ["x", "zz", "5", "5,", "#n"])
def test_an_offset_tk_refuses(root, value):
    with pytest.raises(TclError) as caught:
        Canvas(root, offset=value)
    assert str(caught.value) == (
        f'bad offset "{value}": expected "x,y", "#x,y", n, ne, e, se, s, sw, w, '
        "nw, or center"
    )


@pytest.mark.parametrize("name", ["xscrollincrement", "yscrollincrement"])
def test_an_increment_is_a_distance_at_least_zero(root, name):
    """Measured: -3 reads back 0."""
    assert Canvas(root, **{name: -3}).cget(name) == 0
    with pytest.raises(TclError, match='expected screen distance but got "x"'):
        Canvas(root, **{name: "x"})


def test_without_an_increment_a_unit_is_a_cell(canvas):
    canvas.yview_scroll(1, "units")
    canvas.xview_scroll(1, "units")
    assert (canvas._left, canvas._top) == (1, 2)


def test_an_increment_is_the_unit(canvas):
    """Measured: an increment of 30, and one unit is 30, three are 90."""
    canvas.configure(yscrollincrement=30, xscrollincrement=25)
    canvas.yview_scroll(1, "units")
    canvas.xview_scroll(1, "units")
    assert (canvas._left, canvas._top) == (25, 30)
    canvas.yview_scroll(2, "units")
    assert canvas._top == 90


def test_the_view_lands_on_the_nearest_multiple(canvas):
    """Measured: an increment of 30 and moveto 47 pixels lands on 60."""
    canvas.configure(yscrollincrement=30, xscrollincrement=30)
    canvas.xview_moveto(47 / 400)
    assert canvas._left == 60
    canvas.xview_moveto(44 / 400)
    assert canvas._left == 30


def test_a_vertical_view_still_lands_on_a_cell(canvas):
    canvas.configure(yscrollincrement=5)
    canvas.yview_scroll(1, "units")
    assert canvas._top % 2 == 0


def test_a_page_is_not_an_increment(canvas):
    canvas.configure(yscrollincrement=7)
    canvas.yview_scroll(1, "pages")
    assert canvas._top == 21 - 21 % 2


def test_confined_the_view_stops_at_the_region(canvas):
    canvas.yview_scroll(-5, "units")
    canvas.xview_moveto(2)
    assert canvas._top == 0
    assert canvas._left == 400 - 40


def test_unconfined_it_goes_past_either_edge(canvas):
    """Measured: -5 units from the top went to -50, moveto 2 to 2000."""
    canvas.configure(confine=False)
    canvas.yview_scroll(-5, "units")
    assert canvas._top == -10
    canvas.xview_moveto(2)
    assert canvas._left == 800


def test_a_small_region_scrolls_only_unconfined(root):
    """Measured: a region smaller than the window does not scroll confined."""
    widget = Canvas(root, width=40, height=10, scrollregion=(0, 0, 10, 10))
    widget._allocate(Rect(0, 0, 40, 10))
    widget.yview_scroll(1, "units")
    assert widget._top == 0
    widget.configure(confine=False)
    widget.yview_scroll(1, "units")
    assert widget._top == 2


def test_confining_again_pulls_the_view_back(canvas):
    """Measured: moveto 2, then confine on, and the view is at the bottom."""
    canvas.configure(confine=False)
    canvas.yview_moveto(2)
    canvas.xview_moveto(-1)
    canvas.configure(confine=True)
    assert (canvas._left, canvas._top) == (0, 200 - 20)


# ------------------------------------------------------------------ Listbox


class Window:
    """A curses window that remembers what was written where."""

    def __init__(self, rect):
        self.rect = rect
        self.cells = {}
        self.attrs = {}

    def getmaxyx(self):
        return (self.rect.height, self.rect.width)

    def bkgd(self, *_):
        pass

    def erase(self):
        self.cells.clear()

    def addstr(self, row, column, text, attr=0):
        for offset, char in enumerate(text):
            self.cells[(row, column + offset)] = char
            self.attrs[(row, column + offset)] = attr

    insstr = addstr

    def row(self, row):
        return "".join(self.cells.get((row, c), " ") for c in range(self.rect.width))


@pytest.fixture
def drawn(root):
    """A Listbox 12 cells wide with no border, painting into a Window."""
    root.tk.panels = PanelStack(window_factory=Window, panel_factory=None)
    root.tk.screen = SimpleNamespace(
        started=True, size=SimpleNamespace(width=60, height=20)
    )
    widget = Listbox(
        root, width=12, height=4, borderwidth=0, highlightthickness=0, relief="flat"
    )
    widget._allocate(Rect(0, 0, 12, 4))
    widget._map()
    return widget


def rows(widget):
    widget._redraw()
    return [widget._window.row(row) for row in range(3)]


def test_listbox_defaults(root):
    widget = Listbox(root)
    assert (widget.cget("justify"), widget.cget("listvariable")) == ("left", "")


@pytest.mark.parametrize(
    ("given", "stored"), [("c", "center"), ("r", "right"), ("left", "left")]
)
def test_justify_takes_a_prefix_and_stores_it_whole(root, given, stored):
    """Measured: ``c`` reads back ``center``."""
    assert Listbox(root, justify=given).cget("justify") == stored


@pytest.mark.parametrize("value", ["middle", "centre"])
def test_justify_refuses_anything_else(root, value):
    with pytest.raises(TclError) as caught:
        Listbox(root, justify=value)
    assert (
        str(caught.value)
        == f'bad justification "{value}": must be left, right, or center'
    )


def test_justify_aligns_within_the_window(drawn):
    """Between the markers there are 10 cells; Tk aligned 'ab' at 144 of a
    160-pixel list once nothing was wider."""
    drawn.insert("end", "ab", "xyz")
    drawn.configure(justify="right")
    assert [r[1:11] for r in rows(drawn)[:2]] == ["        ab", "       xyz"]
    drawn.configure(justify="center")
    assert [r[1:11] for r in rows(drawn)[:2]] == ["    ab    ", "   xyz    "]
    drawn.configure(justify="left")
    assert rows(drawn)[0][1:11] == "ab        "


def test_justify_aligns_within_the_widest_item(drawn):
    """Measured: with an item wider than the window, 'ab' right-justified sat
    at 224 of a 240-pixel item - the widest item's edge, not the window's."""
    drawn.insert("end", "ab", "0123456789abcdef")
    drawn.configure(justify="right")
    assert rows(drawn)[0][1:11] == "          "
    drawn.xview_moveto(1)
    assert rows(drawn)[0][1:11] == "        ab"
    assert rows(drawn)[1][1:11] == "6789abcdef"


def test_a_variable_gives_the_list_its_items(root):
    variable = StringVar(root, "a b {c d}")
    assert Listbox(root, listvariable=variable).get(0, "end") == ("a", "b", "c d")


def test_a_new_variable_is_made_from_the_items(root):
    """Measured: a name that is not a variable becomes one, holding the items."""
    widget = Listbox(root)
    widget.insert("end", "p q", "r")
    widget.configure(listvariable="fresh")
    assert root.getvar("fresh") == ("p q", "r")
    assert widget.cget("listvariable") == "fresh"


def test_an_existing_variable_wins_over_the_items(root):
    widget = Listbox(root)
    widget.insert("end", "p")
    widget.configure(listvariable=StringVar(root, "s"))
    assert widget.get(0, "end") == ("s",)


def test_inserting_and_deleting_write_the_variable(root):
    """Measured: the variable then reads as a list, which a StringVar shows
    as Python shows a tuple."""
    variable = StringVar(root, "a b")
    widget = Listbox(root, listvariable=variable)
    widget.insert("end", "e f")
    assert root.getvar(str(variable)) == ("a", "b", "e f")
    assert variable.get() == "('a', 'b', 'e f')"
    widget.delete(0)
    assert root.getvar(str(variable)) == ("b", "e f")


def test_other_traces_hear_the_write(root):
    variable = StringVar(root, "a")
    widget = Listbox(root, listvariable=variable)
    heard = []
    variable.trace_add("write", lambda *_: heard.append(root.getvar(str(variable))))
    widget.insert("end", "b")
    assert heard == [("a", "b")]


def test_two_listboxes_share_one_variable(root):
    variable = Variable(root, ("a",))
    first = Listbox(root, listvariable=variable)
    second = Listbox(root, listvariable=variable)
    first.insert("end", "b")
    assert second.get(0, "end") == ("a", "b")


def test_setting_the_variable_sets_the_items(root):
    variable = StringVar(root, "a b c d e")
    widget = Listbox(root, listvariable=variable, selectmode="extended")
    widget.selection_set(1, 4)
    widget.activate(4)
    variable.set("x y")
    assert widget.get(0, "end") == ("x", "y")
    # Measured: the selection past the end goes, the active index stays.
    assert widget.curselection() == (1,)
    assert widget._active == 4


def test_the_selection_past_the_end_goes_for_good(root):
    """Measured: shrunk to two and grown to five, only 1 is still selected."""
    variable = StringVar(root, "a b c d e")
    widget = Listbox(root, listvariable=variable, selectmode="extended")
    widget.selection_set(1, 4)
    variable.set("x y")
    variable.set("x y z w v")
    assert widget.curselection() == (1,)


def test_attaching_drops_the_selection_past_the_end(root):
    """A departure: Tk keeps 2-4 hidden here, and appending three items
    shows them selected again. ARCHITECTURE.md, Listbox."""
    widget = Listbox(root, selectmode="extended")
    widget.insert("end", *"abcde")
    widget.selection_set(1, 4)
    widget.configure(listvariable=StringVar(root, "q r"))
    assert widget.curselection() == (1,)
    widget.insert("end", *"stu")
    assert widget.curselection() == (1,)


def test_a_tuple_is_already_a_list(root):
    variable = Variable(root, "a")
    widget = Listbox(root, listvariable=variable)
    variable.set((1, "two words", 3))
    assert widget.get(0, "end") == ("1", "two words", "3")


def test_a_value_that_is_not_a_list_is_refused_and_undone(root):
    """Measured: ``can't set "PY_VAR0": invalid listvar value``, and the
    variable reads as it did."""
    variable = StringVar(root, "x y")
    widget = Listbox(root, listvariable=variable)
    with pytest.raises(TclError) as caught:
        variable.set("{a")
    assert str(caught.value) == f'can\'t set "{variable}": invalid listvar value'
    assert root.getvar(str(variable)) == ("x", "y")
    assert widget.get(0, "end") == ("x", "y")


def test_a_variable_that_is_not_a_list_cannot_be_attached(root):
    variable = StringVar(root, "{a")
    with pytest.raises(
        TclError, match=r"^unmatched open brace in list: invalid -listvariable value$"
    ):
        Listbox(root, listvariable=variable)


def test_the_old_variable_is_let_go(root):
    first = StringVar(root, "a")
    widget = Listbox(root, listvariable=first)
    widget.configure(listvariable=StringVar(root, "q r"))
    first.set("m n")
    assert widget.get(0, "end") == ("q", "r")
    widget.configure(listvariable="")
    widget.insert("end", "s")
    assert first.get() == "m n"


def test_writing_the_variable_repaints(drawn):
    variable = StringVar(drawn, "a")
    drawn.configure(listvariable=variable)
    variable.set("zz")
    assert drawn._window.row(0)[1:3] == "zz"


def test_shrinking_the_list_pulls_the_view_back(root):
    variable = StringVar(root, " ".join(str(n) for n in range(30)))
    widget = Listbox(root, listvariable=variable, height=5)
    widget._allocate(Rect(0, 0, 10, 7))
    widget.yview_moveto(1)
    variable.set("a b")
    assert widget._top == 0


@pytest.mark.parametrize(
    ("text", "elements"),
    [
        ("{a b} c", ["a b", "c"]),
        ('"a b" c', ["a b", "c"]),
        ("a\\ b c", ["a b", "c"]),
        ("{a {b c}} d", ["a {b c}", "d"]),
        ("{a \\} b} c", ["a \\} b", "c"]),
        ("  a   b  ", ["a", "b"]),
        ("a\\nb a\\tb a\\qb", ["a\nb", "a\tb", "aqb"]),
        ('"a\\"b"', ['a"b']),
        ("a}", ["a}"]),
        ('{} ""', ["", ""]),
        ("a\\", ["a\\"]),
        ("", []),
    ],
)
def test_a_tcl_list(text, elements):
    """Each measured against Tk 9.0.2's ``splitlist``."""
    assert _tcl_list(text) == elements


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("{a", "unmatched open brace in list"),
        ('"a', "unmatched open quote in list"),
        ("{a}b", 'list element in braces followed by "b" instead of space'),
        ('"a"b', 'list element in quotes followed by "b" instead of space'),
    ],
)
def test_a_tcl_list_tcl_refuses(text, message):
    with pytest.raises(TclError) as caught:
        _tcl_list(text)
    assert str(caught.value) == message


# --------------------------------------------------------------------- Menu


def test_menu_defaults(root):
    menu = Menu(root)
    assert {name: menu.cget(name) for name in ("font", "tearoffcommand", "type")} == {
        "font": "",
        "tearoffcommand": "",
        "type": "normal",
    }


@pytest.mark.parametrize(
    ("given", "stored"), [("m", "menubar"), ("t", "tearoff"), ("normal", "normal")]
)
def test_a_menu_type_is_a_prefix_stored_whole(root, given, stored):
    """Measured: ``m`` reads back ``menubar``."""
    assert Menu(root, type=given).cget("type") == stored


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("NORMAL", 'bad type "NORMAL": must be menubar, normal, or tearoff'),
        ("menubar ", 'bad type "menubar ": must be menubar, normal, or tearoff'),
        ("", 'ambiguous type "": must be menubar, normal, or tearoff'),
    ],
)
def test_a_menu_type_tk_refuses(root, value, message):
    with pytest.raises(TclError) as caught:
        Menu(root, type=value)
    assert str(caught.value) == message


def test_a_tearoffcommand_is_kept(root):
    def command(*_):
        pass

    assert Menu(root, tearoffcommand=command).cget("tearoffcommand") is command


def test_a_menus_font_styles_its_labels(root):
    root.tk.panels = PanelStack(window_factory=Window, panel_factory=None)
    root.tk.screen = SimpleNamespace(
        started=True, size=SimpleNamespace(width=60, height=20), refresh=lambda: None
    )
    menu = Menu(root, font="Courier 10 bold")
    menu.add_command(label="Open")
    menu.post(0, 0)
    cells = menu._window.cells
    row, column = next(place for place, char in cells.items() if char == "O")
    assert menu._window.attrs[(row, column)] & from_font(bold=True)
    menu.configure(font="Courier 10")
    menu._redraw()
    assert not menu._window.attrs[(row, column)] & from_font(bold=True)


# ------------------------------------------------------------- justification


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("C", 'bad justification "C": must be left, right, or center'),
        ("centerx", 'bad justification "centerx": must be left, right, or center'),
        ("", 'ambiguous justification "": must be left, right, or center'),
    ],
)
def test_justify_measured_refusals(root, value, message):
    with pytest.raises(TclError) as caught:
        Listbox(root, justify=value)
    assert str(caught.value) == message


# --------------------------------------------------------------- LabelFrame


@pytest.fixture
def framed(root):
    """A 30x10 LabelFrame placed at (10, 2), with a child packed inside."""
    frame = LabelFrame(root, text="TEXT")
    frame.place(x=10, y=2, width=30, height=10)
    frame.inner = Frame(frame, width=5, height=2)
    frame.inner.pack(anchor="nw")
    root.update_layout()
    return frame


def test_labelwidget_defaults_empty(root):
    assert LabelFrame(root).cget("labelwidget") == ""


def test_a_label_sits_on_the_border_in_place_of_the_text(root, framed):
    """Measured: managed by "labelframe", the text kept and not drawn."""
    label = Checkbutton(framed, text="choose")
    framed.configure(labelwidget=label)
    root.update_layout()
    assert label.winfo_manager() == "labelframe"
    assert label._rect == Rect(2, 0, 10, 1)
    assert framed.cget("labelwidget") is label
    assert framed.cget("text") == "TEXT"
    assert framed._caption() == ""
    assert framed.inner._rect == Rect(1, 1, 5, 2)


@pytest.mark.parametrize(
    ("anchor", "place"),
    [("nw", (2, 0)), ("n", (10, 0)), ("ne", (18, 0)), ("s", (10, 9)), ("se", (18, 9))],
)
def test_the_label_goes_where_the_anchor_puts_a_caption(root, framed, anchor, place):
    label = Checkbutton(framed, text="choose")
    framed.configure(labelwidget=label, labelanchor=anchor)
    root.update_layout()
    assert (label._rect.x, label._rect.y) == place


def test_a_sibling_label_is_placed_in_its_own_masters_cells(root, framed):
    """Measured: a sibling of the frame may be its label."""
    label = Label(root, text="sib")
    framed.configure(labelwidget=label)
    root.update_layout()
    assert label._rect == Rect(12, 2, 3, 1)


def test_a_sibling_made_first_is_raised_above_the_frame(root):
    """Measured: winfo_containing over it answers the label, and it follows
    the frame in the stacking order."""
    label = Label(root, text="early")
    frame = LabelFrame(root, labelwidget=label)
    assert list(root.children.values()).index(label) > list(
        root.children.values()
    ).index(frame)


def test_the_label_moves_with_the_frame(root, framed):
    label = Label(root, text="sib")
    framed.configure(labelwidget=label)
    framed.place(x=20, y=5)
    root.update_layout()
    assert (label._rect.x, label._rect.y) == (22, 5)


def test_a_label_that_resizes_is_placed_again(root, framed):
    label = Label(framed, text="ab")
    framed.configure(labelwidget=label, labelanchor="ne")
    label.configure(text="abcdef")
    root.update_layout()
    assert label._rect == Rect(22, 0, 6, 1)


def test_the_frame_asks_for_room_for_its_label(root):
    frame = LabelFrame(root)
    frame.configure(labelwidget=Label(frame, text="abcdef"))
    assert frame.winfo_reqwidth() == 6 + 2 + 2


def test_a_tall_label_pushes_the_children_down(root, framed):
    """Measured: a 40-pixel label put the first child at 40, below it."""
    framed.configure(labelwidget=Frame(framed, width=4, height=3))
    root.update_layout()
    assert framed.inner._rect.y == 3


def test_a_tall_label_on_the_bottom_takes_room_there(root, framed):
    framed.configure(labelwidget=Frame(framed, width=4, height=3), labelanchor="s")
    root.update_layout()
    assert framed._content_padding().bottom - framed._content_padding().top == 2
    assert framed.inner._rect.y == 1


def test_the_previous_label_is_let_go(root, framed):
    """Measured: managed by nothing and unmapped."""
    first = Checkbutton(framed, text="one")
    framed.configure(labelwidget=first)
    framed.configure(labelwidget=Label(framed, text="two"))
    assert first.winfo_manager() == ""
    assert not first._mapped


def test_a_label_is_taken_from_its_manager(root, framed):
    label = Label(root, text="placed")
    label.place(x=0, y=0)
    framed.configure(labelwidget=label)
    assert label.winfo_manager() == "labelframe"
    assert label not in root.place_slaves()


@pytest.mark.parametrize("into", ["frame", "root"])
def test_packing_the_label_elsewhere_brings_the_text_back(root, framed, into):
    """Measured: packed again, the option reads "" and the caption is text."""
    label = Label(framed if into == "frame" else root, text="L")
    framed.configure(labelwidget=label)
    # The root already places the frame, and takes no packing beside it.
    manager = "pack" if into == "frame" else "place"
    getattr(label, manager)()
    root.update_layout()
    assert framed.cget("labelwidget") == ""
    assert label.winfo_manager() == manager
    assert framed._caption() == " TEXT "


def test_destroying_the_label_brings_the_text_back(root, framed):
    label = Label(root, text="L")
    framed.configure(labelwidget=label)
    label.destroy()
    assert framed.cget("labelwidget") == ""
    assert framed._caption() == " TEXT "


def test_clearing_it_lets_the_label_go(root, framed):
    label = Label(framed, text="L")
    framed.configure(labelwidget=label)
    framed.configure(labelwidget="")
    assert label.winfo_manager() == ""
    assert framed._caption() == " TEXT "


def test_a_label_by_path(root, framed):
    label = Label(framed, text="L", name="lab")
    framed.configure(labelwidget=str(label))
    assert framed.cget("labelwidget") is label


def test_a_label_given_at_creation(root):
    label = Label(root, text="made")
    frame = LabelFrame(root, labelwidget=label)
    frame.place(x=0, y=12, width=20, height=5)
    root.update_layout()
    assert label._rect == Rect(2, 12, 4, 1)


def test_a_label_must_be_drawable_over_the_frame(root, framed):
    """Measured: a child of a sibling, and the root, are refused."""
    other = Frame(root)
    stranger = Label(other)
    with pytest.raises(TclError) as caught:
        framed.configure(labelwidget=stranger)
    assert str(caught.value) == f"can't use {stranger} as label in this frame"
    with pytest.raises(TclError, match=r"can't use \. as label in this frame"):
        framed.configure(labelwidget=root)


def test_a_label_path_naming_nothing(root, framed):
    with pytest.raises(TclError, match=r'bad window path name "\.nosuch"'):
        framed.configure(labelwidget=".nosuch")


def test_a_ttk_labelframe_takes_one_too(root):
    from tkcurses import ttk

    frame = ttk.Labelframe(root, text="T")
    label = ttk.Label(frame, text="L")
    frame.configure(labelwidget=label)
    assert label.winfo_manager() == "labelframe"


def test_changing_the_anchor_alone_moves_the_label(root, framed):
    label = Checkbutton(framed, text="choose")
    framed.configure(labelwidget=label)
    root.update_layout()
    framed.configure(labelanchor="se")
    assert (label._rect.x, label._rect.y) == (18, 9)


def test_a_centred_label_of_odd_width(root, framed):
    label = Label(framed, text="abc")
    framed.configure(labelwidget=label, labelanchor="n")
    root.update_layout()
    assert label._rect.x == (30 - 3) // 2


def test_a_tall_label_on_the_bottom_ends_on_the_border(root, framed):
    label = Frame(framed, width=4, height=3)
    framed.configure(labelwidget=label, labelanchor="sw")
    root.update_layout()
    assert (label._rect.y, label._rect.height) == (10 - 3, 3)


def test_a_label_wider_than_the_frame_is_cut_inside_its_corners(root, framed):
    label = Label(framed, text="x" * 40)
    framed.configure(labelwidget=label)
    root.update_layout()
    assert label._rect.width == 30 - 4


def test_a_toplevel_cannot_be_a_label(root, framed):
    """Measured: ``can't use .!toplevel as label in this frame``."""
    window = Toplevel(root)
    with pytest.raises(TclError, match="as label in this frame"):
        framed.configure(labelwidget=window)


def test_a_label_taken_away_redraws_the_text(root):
    """A frame with no children is laid out by nothing, so it is told."""
    root.tk.panels = PanelStack(window_factory=Window, panel_factory=None)
    root.tk.screen = SimpleNamespace(
        started=True, size=SimpleNamespace(width=60, height=20), refresh=lambda: None
    )
    frame = LabelFrame(root, text="TEXT")
    frame.place(x=0, y=0, width=20, height=5)
    label = Label(root, text="L")
    frame.configure(labelwidget=label)
    root.update_layout()
    assert "TEXT" not in frame._window.row(0)
    label.place(x=0, y=10)
    assert "TEXT" in frame._window.row(0)


# ------------------------------------------------- check and radio buttons


@pytest.fixture
def images(root):
    """Three images of different sizes, named off, on and tri."""
    return {
        name: PhotoImage(master=root, name=name, width=width, height=4)
        for name, width in (("off", 4), ("on", 6), ("tri", 8))
    }


@pytest.mark.parametrize("widget", [Checkbutton, Radiobutton])
def test_the_images_default_empty(root, widget):
    made = widget(root)
    assert (made.cget("selectimage"), made.cget("tristateimage")) == ("", "")


@pytest.mark.parametrize("widget", [Checkbutton, Radiobutton])
@pytest.mark.parametrize("name", ["selectimage", "tristateimage"])
def test_an_image_that_does_not_exist(root, widget, name):
    """Measured: ``image "nosuch" does not exist``."""
    with pytest.raises(TclError, match='image "nosuch" does not exist'):
        widget(root, **{name: "nosuch"})


def test_an_image_object_is_kept_by_name(root, images):
    assert Checkbutton(root, selectimage=images["on"]).cget("selectimage") == "on"


def test_a_checkbutton_draws_the_image_for_its_state(root, images):
    variable = StringVar(root, "0")
    button = Checkbutton(
        root, variable=variable, image="off", selectimage="on", tristateimage="tri"
    )
    assert button._drawn_image() is images["off"]
    variable.set("1")
    assert button._drawn_image() is images["on"]
    variable.set("")
    assert button._drawn_image() is images["tri"]


def test_a_radiobutton_draws_the_image_for_its_state(root, images):
    variable = StringVar(root, "b")
    button = Radiobutton(
        root,
        variable=variable,
        value="a",
        image="off",
        selectimage="on",
        tristateimage="tri",
    )
    assert button._drawn_image() is images["off"]
    variable.set("a")
    assert button._drawn_image() is images["on"]
    variable.set("")
    assert button._drawn_image() is images["tri"]


def test_without_a_state_image_the_image_is_drawn(root, images):
    button = Checkbutton(root, variable=StringVar(root, "1"), image="off")
    assert button._drawn_image() is images["off"]


def test_without_an_image_the_state_images_do_nothing(root, images):
    """Measured: a selectimage on a button with only text left its size as
    a plain one's, 45x25."""
    button = Checkbutton(
        root, variable=StringVar(root, "1"), selectimage="on", text="hi"
    )
    assert button._drawn_image() is None
    assert button.winfo_reqwidth() == Checkbutton(root, text="hi").winfo_reqwidth()


def test_the_size_is_the_images_alone(root, images):
    """Measured: a bigger selectimage or tristateimage left the size 8x8."""
    plain = Checkbutton(root, image="off", indicatoron=0)
    on = Checkbutton(
        root,
        image="off",
        selectimage="tri",
        indicatoron=0,
        variable=StringVar(root, "1"),
    )
    assert on.winfo_reqwidth() == plain.winfo_reqwidth()


def test_a_deleted_state_image_falls_back_to_the_image(root, images):
    button = Checkbutton(
        root, variable=StringVar(root, "1"), image="off", selectimage="on"
    )
    root.tk.images.pop("on")
    assert button._drawn_image() is images["off"]


def test_radiobutton_tristatevalue(root):
    variable = StringVar(root, "x")
    button = Radiobutton(root, variable=variable, value="a", tristatevalue="x")
    assert button.cget("tristatevalue") == "x"
    assert button._indicator_state == "tristate"
    variable.set("")
    assert button._indicator_state == "off"
    variable.set("a")
    assert button._indicator_state == "on"


def test_value_wins_over_tristatevalue(root):
    """Tk's order, as a Checkbutton's: on is asked first."""
    button = Radiobutton(
        root, variable=StringVar(root, "a"), value="a", tristatevalue="a"
    )
    assert button._indicator_state == "on"


def test_the_third_state_is_drawn(drawn):
    button = Radiobutton(
        drawn.master, variable=StringVar(drawn.master, ""), value="a", text="A"
    )
    button._allocate(Rect(0, 6, 12, 1))
    button._map()
    button._redraw()
    assert button._window.row(0).startswith("(-)")
    assert "A" in button._window.row(0)


def test_a_ttk_radiobutton_has_no_third_state(root):
    """Measured: a ttk radiobutton over an empty variable has no alternate."""
    from tkcurses import ttk

    button = ttk.Radiobutton(root, variable=StringVar(root, ""), value="a")
    assert button._indicator_state == "off"


def test_the_state_image_is_the_one_painted(root, images, monkeypatch):
    """What the paint reads from, not only what _drawn_image answers."""
    read = []
    for name, image in images.items():
        monkeypatch.setattr(
            image, "lit", lambda box, name=name: read.append(name) or {}
        )
    button = Checkbutton(
        root, variable=StringVar(root, "1"), image="off", selectimage="on"
    )
    button._draw_image(None, None, Rect(0, 0, 10, 4), Rect(0, 0, 6, 2), [])
    assert read == ["on"]


def test_an_exact_name_wins_over_a_longer_one_it_begins(root):
    """Tcl_GetIndexFromObj's rule, for a table like the anchors: "n" is n,
    not an ambiguous prefix of n and ne."""
    assert _tcl_index("n", ("n", "ne"), "anchor") == "n"
    with pytest.raises(TclError, match='ambiguous anchor "": must be n, or ne'):
        _tcl_index("", ("n", "ne"), "anchor")
