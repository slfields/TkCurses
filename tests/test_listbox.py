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

"""Tests for the Listbox widget."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tkcurses import Listbox, Misc, StringVar, TclError
from tkcurses._core.events import MOD_CTRL, MOD_SHIFT, KeyEvent, MouseEvent
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
    root._rect = Rect(0, 0, 40, 20)
    root._mapped = True
    return root


@pytest.fixture
def listbox(root):
    box = Listbox(root, name="lb", height=4, width=16)
    box._allocate(Rect(0, 0, 18, 6))
    box._map()
    box.insert("end", *[f"item {n}" for n in range(8)])
    return box


def press(widget, keysym, state=0):
    widget._handle(KeyEvent(keysym=keysym, char="", modifiers=state))


# ------------------------------------------------------------------ contents


def test_a_new_listbox_is_empty(root):
    assert Listbox(root, name="lb").size() == 0


def test_inserting_at_the_end(listbox):
    listbox.insert("end", "last")
    assert listbox.get("end") == ""
    assert listbox.size() == 9
    assert listbox.get(8) == "last"


def test_inserting_in_the_middle(listbox):
    listbox.insert(1, "wedged")
    assert listbox.get(1) == "wedged"
    assert listbox.size() == 9


def test_getting_a_range(listbox):
    assert listbox.get(1, 3) == ("item 1", "item 2", "item 3")


def test_deleting_one_item(listbox):
    listbox.delete(0)
    assert listbox.get(0) == "item 1"
    assert listbox.size() == 7


def test_deleting_a_range_is_inclusive(listbox):
    """Tk's listbox ranges include the last index, unlike an entry's."""
    listbox.delete(0, 2)
    assert listbox.size() == 5
    assert listbox.get(0) == "item 3"


def test_deleting_everything(listbox):
    listbox.delete(0, "end")
    assert listbox.size() == 0


# ------------------------------------------------------------------ indices


def test_end_is_the_count(listbox):
    assert listbox.index("end") == 8


def test_active_is_the_active_item(listbox):
    listbox.activate(3)
    assert listbox.index("active") == 3


def test_a_bad_index_is_refused(listbox):
    with pytest.raises(TclError, match="bad listbox index"):
        listbox.index("sideways")


# ---------------------------------------------------------------- selection


def test_nothing_is_selected_to_begin_with(listbox):
    assert listbox.curselection() == ()


def test_selecting_one_item(listbox):
    listbox.selection_set(2)
    assert listbox.curselection() == (2,)
    assert listbox.selection_includes(2)


def test_clearing_the_selection(listbox):
    listbox.selection_set(2)
    listbox.selection_clear(0, "end")
    assert listbox.curselection() == ()


@pytest.mark.parametrize("mode", ["browse", "single", "extended", "multiple"])
def test_selection_set_adds_whatever_the_mode(listbox, mode):
    """Measured on Tk 9.0.2: the mode belongs to the bindings, not to the
    widget command. TkCurses-xk41."""
    listbox.configure(selectmode=mode)
    listbox.selection_set(1, 4)
    listbox.selection_set(0)
    assert listbox.curselection() == (0, 1, 2, 3, 4)


@pytest.mark.parametrize(
    ("first", "last", "left"),
    [
        (0, None, (1, 2, 3, 4, 5, 6, 7)),
        (2, None, (0, 1, 3, 4, 5, 6, 7)),
        (4, 1, (0, 5, 6, 7)),
        (0, "end", ()),
    ],
)
def test_selection_clear_clears_only_what_it_names(listbox, first, last, left):
    """``selection_clear(0)`` used to clear every item."""
    listbox.selection_set(0, "end")
    listbox.selection_clear(first, last)
    assert listbox.curselection() == left


def test_a_range_may_run_backwards_or_past_the_ends(listbox):
    listbox.selection_set(4, 1)
    assert listbox.curselection() == (1, 2, 3, 4)
    listbox.selection_clear(0, "end")
    listbox.selection_set(-3, 20)
    assert listbox.curselection() == tuple(range(8))


def test_multiple_mode_keeps_several(listbox):
    listbox.configure(selectmode="multiple")
    listbox.selection_set(1)
    listbox.selection_set(3)
    assert listbox.curselection() == (1, 3)


def test_extended_mode_selects_a_range(listbox):
    listbox.configure(selectmode="extended")
    listbox.selection_set(1, 3)
    assert listbox.curselection() == (1, 2, 3)


def test_the_widget_commands_fire_no_virtual_event(listbox):
    """Measured on Tk 9.0.2: only the bindings send ``<<ListboxSelect>>``,
    through ``tk::FireListboxSelectEvent``."""
    seen = []
    listbox.bind("<<ListboxSelect>>", lambda event: seen.append(1))
    listbox.selection_set(1)
    listbox.selection_clear(0, "end")
    assert seen == []


def test_the_selection_follows_deleted_items(listbox):
    listbox.configure(selectmode="multiple")
    listbox.selection_set(4)
    listbox.delete(0, 1)
    assert listbox.curselection() == (2,)


def test_deleting_a_selected_item_deselects_it(listbox):
    listbox.selection_set(2)
    listbox.delete(2)
    assert listbox.curselection() == ()


def test_inserting_moves_the_selection_along(listbox):
    listbox.selection_set(3)
    listbox.insert(0, "new")
    assert listbox.curselection() == (4,)


# ------------------------------------------------------------------ keyboard


def test_the_arrows_move_the_active_item(listbox):
    listbox.activate(0)
    press(listbox, "Down")
    assert listbox.index("active") == 1
    press(listbox, "Up")
    assert listbox.index("active") == 0


def test_browse_mode_drags_the_selection_with_the_arrows(listbox):
    listbox.activate(0)
    press(listbox, "Down")
    assert listbox.curselection() == (1,)


def test_single_mode_moves_without_selecting(listbox):
    """The active item and the selection are different things."""
    listbox.configure(selectmode="single")
    listbox.activate(0)
    press(listbox, "Down")
    assert listbox.index("active") == 1
    assert listbox.curselection() == ()


def test_space_selects_the_active_item(listbox):
    listbox.configure(selectmode="multiple")
    listbox.activate(2)
    press(listbox, "space")
    assert listbox.curselection() == (2,)


def test_space_toggles_in_multiple_mode(listbox):
    listbox.configure(selectmode="multiple")
    listbox.activate(2)
    press(listbox, "space")
    press(listbox, "space")
    assert listbox.curselection() == ()


def test_control_home_and_end_select_the_ends(listbox):
    listbox.activate(3)
    press(listbox, "Home", MOD_CTRL)
    assert (listbox.index("active"), listbox.curselection()) == (0, (0,))
    press(listbox, "End", MOD_CTRL)
    assert (listbox.index("active"), listbox.curselection()) == (7, (7,))
    assert listbox._top == 4


def test_home_and_end_scroll_sideways_and_select_nothing(listbox):
    listbox.insert("end", "x" * 40)
    listbox.activate(3)
    press(listbox, "End")
    assert listbox._left > 0
    press(listbox, "Home")
    assert (listbox._left, listbox.index("active")) == (0, 3)
    assert listbox.curselection() == ()


def test_a_key_falls_back_to_the_binding_with_fewer_modifiers(listbox):
    """Control-Up is Up's binding, as Tk matches it; Shift-Home is Home's."""
    listbox.activate(3)
    press(listbox, "Up", MOD_CTRL)
    assert listbox.index("active") == 2


def test_an_unhandled_key_is_left_alone(listbox):
    assert listbox._handle(KeyEvent(keysym="F1", char="")) is False


def test_a_handled_key_goes_on_to_the_toplevel(listbox, root):
    """listbox.tcl never breaks: a dialog's Escape still reaches it."""
    heard = []
    root.bind("<Escape>", lambda event: heard.append(event.keysym))
    listbox.configure(selectmode="extended")
    assert listbox._handle(KeyEvent(keysym="Down", char="")) is False
    listbox._handle(KeyEvent(keysym="Escape", char=""))
    assert heard == ["Escape"]


# --------------------------------------------------------------------- mouse


def test_clicking_selects_a_row(listbox):
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=2))
    assert listbox.curselection() == (1,)


def test_clicking_takes_the_focus(listbox):
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=1))
    assert listbox.focus_get() is listbox


def test_clicking_past_the_last_item_selects_the_last(listbox):
    """Tk's ``index @x,y`` is the nearest item; this used to select none."""
    listbox.delete(0, "end")
    listbox.insert("end", "only", "two")
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=4))
    assert listbox.curselection() == (1,)


def test_shift_clicking_extends_in_extended_mode(listbox):
    listbox.configure(selectmode="extended")
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=1))
    listbox._handle(
        MouseEvent(button=1, state="pressed", x=2, y=3, modifiers=MOD_SHIFT)
    )
    assert listbox.curselection() == (0, 1, 2)


def click(listbox, row, state=0):
    """Press and release on ``row``: the release is what activates it."""
    for edge in ("pressed", "released"):
        listbox._handle(
            MouseEvent(button=1, state=edge, x=2, y=1 + row, modifiers=state)
        )


def gestures(listbox, mode, steps):
    """Run ``steps`` and return the selection and the event count after each.

    ``c``/``s``/``t`` click a row plain, with Shift, with Control; ``k``
    presses a key.
    """
    # Tall enough for every row: the fixture shows four, and a click on
    # row 4 there lands on the border.
    listbox.configure(selectmode=mode, height=8)
    listbox._allocate(Rect(0, 0, 18, 10))
    seen = []
    listbox.bind("<<ListboxSelect>>", lambda event: seen.append(1))
    states = {"c": 0, "s": MOD_SHIFT, "t": MOD_CTRL}
    after = []
    for kind, what in steps:
        if kind == "k":
            press(listbox, what)
        else:
            click(listbox, what, states[kind])
        after.append((listbox.curselection(), len(seen)))
    return after


# Each table was measured through tkinter on Python 3.14 over Tk 9.0.2, with
# a timestamp on every generated click so that none read as a double-click.
@pytest.mark.parametrize(
    ("mode", "steps", "expected"),
    [
        (
            "browse",
            [("c", 1), ("c", 1), ("k", "Down"), ("k", "space"), ("k", "Up")],
            [((1,), 1), ((1,), 2), ((2,), 3), ((2,), 4), ((1,), 5)],
        ),
        (
            "single",
            [("c", 1), ("c", 1), ("k", "Down"), ("k", "space")],
            [((1,), 1), ((1,), 2), ((1,), 2), ((2,), 3)],
        ),
        (
            "multiple",
            [("c", 1), ("c", 1), ("c", 3), ("k", "Down"), ("k", "space")],
            [((1,), 1), ((), 2), ((3,), 3), ((3,), 3), ((3, 4), 4)],
        ),
        (
            "extended",
            [("c", 1), ("c", 1), ("t", 1), ("k", "Down"), ("k", "space")],
            [((1,), 1), ((1,), 2), ((), 3), ((2,), 4), ((2,), 5)],
        ),
        # Shift and Control do nothing outside extended mode.
        ("browse", [("c", 1), ("s", 3), ("t", 3)], [((1,), 1)] * 3),
        ("multiple", [("c", 1), ("s", 3), ("t", 3)], [((1,), 1)] * 3),
    ],
)
def test_each_mode_answers_a_gesture_as_listbox_tcl_does(
    listbox, mode, steps, expected
):
    assert gestures(listbox, mode, steps) == expected


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        ([("c", 1), ("s", 3)], [(1,), (1, 2, 3)]),
        ([("c", 1), ("s", 4), ("s", 2)], [(1,), (1, 2, 3, 4), (1, 2)]),
        ([("c", 3), ("s", 1), ("s", 5)], [(3,), (1, 2, 3), (3, 4, 5)]),
        ([("c", 0), ("t", 4), ("s", 2)], [(0,), (0, 4), (0, 2, 3, 4)]),
        (
            [("c", 1), ("t", 3), ("t", 4), ("s", 1)],
            [(1,), (1, 3), (1, 3, 4), (1, 2, 3, 4)],
        ),
        ([("t", 2), ("s", 4)], [(2,), (2, 3, 4)]),
        ([("s", 3)], [(3,)]),
        ([("c", 2), ("t", 2), ("s", 4)], [(2,), (), (4,)]),
    ],
)
def test_an_extended_range_runs_as_tk_listbox_motion_runs_it(listbox, steps, expected):
    """Shrinking the range gives back what was selected before it began,
    and a range from a deselected anchor deselects. Each click also sent
    exactly one event."""
    after = gestures(listbox, "extended", steps)
    assert [selection for selection, _ in after] == expected
    assert [count for _, count in after] == list(range(1, len(steps) + 1))


GESTURE_DATA = json.loads(
    (Path(__file__).parent / "support" / "listbox_gestures.json").read_text()
)
GESTURES = GESTURE_DATA["cases"]


MODIFIERS = {"": 0, "S": MOD_SHIFT, "C": MOD_CTRL, "CS": MOD_CTRL | MOD_SHIFT}


def replay(box, steps):
    """Run recorded ``steps`` on ``box`` and read its state after each.

    A click is the press and release a terminal reports for one. A ``d`` is
    the second click of a double only where Tk 9.0.2 makes it one: within
    five pixels of the previous press - on the same row - with no key
    between. The recorder presses an empty list at one fixed point.
    """
    seen = []
    box.bind("<<ListboxSelect>>", lambda event: seen.append(1))
    top = box._text_area().y

    def mouse(state, row, modifiers=0, button=1):
        box._handle(
            MouseEvent(
                button=button, state=state, x=2, y=top + row, modifiers=modifiers
            )
        )

    commands = {
        "p": box.selection_set,
        "a": box.selection_anchor,
        "g": box.activate,
        "e": box.see,
        "x": box.delete,
        "i": lambda at, count: box.insert(at, *(f"new{n}" for n in range(count))),
        "D": lambda: box.configure(state="disabled"),
        "N": lambda: box.configure(state="normal"),
    }
    clicks = {"c": 0, "s": MOD_SHIFT, "t": MOD_CTRL}
    previous = None
    after = []
    for kind, *args in steps:
        where = args[0] if box.size() and args else "empty"
        if kind in clicks:
            mouse("pressed", args[0], clicks[kind])
            mouse("released", args[0], clicks[kind])
        elif kind == "d":
            mouse("double" if where == previous else "pressed", args[0])
            mouse("released", args[0])
        elif kind == "m":
            mouse("pressed", args[0])
            mouse("drag", args[1], button=0)
            mouse("released", args[1])
        elif kind == "k":
            char = " " if args[0] == "space" else ""
            box._handle(
                KeyEvent(keysym=args[0], char=char, modifiers=MODIFIERS[args[1]])
            )
        elif kind == "v":
            box.event_generate(f"<<{args[0]}>>")
        else:
            commands[kind](*args)
        if kind in "cstdm":
            previous = where
        elif kind == "k":
            previous = None
        after.append(
            [
                list(box.curselection()),
                len(seen),
                box.index("active"),
                box.index("anchor"),
                box._top,
                box._left,
                box.size(),
            ]
        )
    return after


@pytest.mark.parametrize(
    "case", GESTURES, ids=[f"{n}-{c['mode']}" for n, c in enumerate(GESTURES)]
)
def test_random_gestures_end_where_tk_ends(root, case):
    """Sequences of clicks, drags, keys, virtual events, commands and state
    changes, recorded from real Tk by
    ``tests/support/record_listbox_gestures.py``. After every step: the
    selection, the ``<<ListboxSelect>>`` count, the active and anchor
    indices, the top row, the columns scrolled off and the size.

    Four columns wider than the recorded width: the border, and the two
    selection markers, so that as many characters show as did in Tk.
    """
    data = GESTURE_DATA
    height = case["height"]
    box = Listbox(
        root,
        name="g",
        height=height,
        selectmode=case["mode"],
        exportselection=False,  # as recorded
    )
    box._allocate(Rect(0, 0, data["width"] + 4, height + 2))
    box._map()
    box.insert("end", *data["items"])
    box.selection_anchor(0)
    box.activate(0)
    assert replay(box, case["steps"]) == case["after"], case["steps"]


def test_a_disabled_listbox_sends_no_event_for_a_click(listbox):
    listbox.configure(state="disabled")
    assert gestures(listbox, "browse", [("c", 1), ("k", "Down")]) == [
        ((), 0),
        ((), 0),
    ]


def test_the_wheel_scrolls_without_selecting(listbox):
    listbox.selection_set(0)
    listbox._handle(MouseEvent(button=5, state="pressed", x=2, y=2))
    assert listbox._top == 1
    assert listbox.curselection() == (0,)


# ------------------------------------------------------------------ scrolling


def test_a_short_list_does_not_scroll(listbox):
    listbox.delete(0, "end")
    listbox.insert("end", "one", "two")
    assert listbox._top == 0


def test_see_scrolls_an_item_into_view(listbox):
    listbox.see(7)
    assert listbox._top == 7 - 4 + 1


def test_see_only_moves_as_far_as_it_must(listbox):
    listbox.see(7)
    before = listbox._top
    listbox.see(5)
    assert listbox._top == before


def test_activating_does_not_scroll(listbox):
    """Tk's ``activate`` leaves the view alone; the bindings call ``see``."""
    listbox.activate(7)
    assert (listbox.index("active"), listbox._top) == (7, 0)


# Measured on Tk 9.0.2 over every top row and index, heights 1 to 9.
@pytest.mark.parametrize(
    ("height", "top", "index", "expected"),
    [
        (4, 0, 3, 0),  # in view: nothing moves
        (4, 0, 4, 1),  # one below, within a third: to the bottom edge
        (4, 0, 5, 4),  # two below: centred, not to the edge (2)
        (4, 0, 7, 6),
        (4, 5, 4, 4),  # one above: to the top edge
        (4, 5, 1, 0),  # further above: centred, then clamped
        (6, 0, 7, 2),  # two below at six rows is a third: to the edge
        (6, 0, 8, 6),  # three below: centred
        (1, 0, 1, 1),  # one row tall: everything centres on itself
    ],
)
def test_see_brings_a_near_item_to_the_edge_and_centres_a_far_one(
    root, height, top, index, expected
):
    box = Listbox(root, name="lb", height=height, width=8)
    box._allocate(Rect(0, 0, 10, height + 2))
    box._map()
    box.insert("end", *map(str, range(20)))
    box.yview(top)
    box.see(index)
    assert box._top == expected


def test_the_view_is_clamped_to_the_list(listbox):
    listbox.yview(99)
    assert listbox._top == 8 - 4


def test_bbox_reports_a_visible_row(listbox):
    assert listbox.bbox(0) is not None


def test_bbox_of_a_scrolled_out_row_is_nothing(listbox):
    assert listbox.bbox(7) is None


def test_nearest_finds_the_row_under_a_position_in_the_widget(listbox):
    # Widget-relative, as Tk's is. This asserted a screen row until
    # TkCurses-9hr, which is why listbox.nearest(event.y) - the tkinter
    # idiom - answered with the first item for every click.
    assert listbox.nearest(2) == 1


# -------------------------------------------------------------------- state


def test_a_disabled_listbox_ignores_keys(listbox):
    listbox.activate(0)
    listbox.configure(state="disabled")
    press(listbox, "Down")
    assert listbox.index("active") == 0


def test_a_disabled_listbox_refuses_the_commands_that_would_change_it(listbox):
    """Measured on Tk 9.0.2: silently, with no error. The view and the
    reading commands still work."""
    listbox.selection_set(1)
    listbox.selection_anchor(1)
    listbox.activate(1)
    listbox.configure(state="disabled")
    listbox.insert(0, "new")
    listbox.delete(0)
    listbox.selection_set(2)
    listbox.selection_clear(1)
    listbox.selection_anchor(3)
    listbox.activate(3)
    listbox.see(7)
    assert listbox.get(0, "end") == tuple(f"item {n}" for n in range(8))
    assert listbox.curselection() == (1,)
    assert listbox.selection_includes(1)
    assert (listbox.index("anchor"), listbox.index("active")) == (1, 1)
    assert listbox._top == 4


def test_a_disabled_listbox_still_takes_its_list_variable(root):

    items = StringVar(root, value="a b")
    box = Listbox(root, name="lb", listvariable=items, state="disabled")
    items.set("c d e")
    assert box.get(0, "end") == ("c", "d", "e")


def test_a_disabled_listbox_ignores_clicks(listbox):
    listbox.configure(state="disabled")
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=2))
    assert listbox.curselection() == ()


def test_a_listbox_asks_for_its_rows_and_columns(root):
    box = Listbox(root, name="lb", width=30, height=5)
    assert box.winfo_reqwidth() == 30 + 2
    assert box.winfo_reqheight() == 5 + 2


# listbox(n): "If zero or less, then the desired width for the window is made
# just large enough to hold all the elements", and the same for height.
# Measured on Tk 9.0.2 with TkFixedFont: width=0 holding 'abcdefghij' and
# 'ab' asks for ten characters and the border. The two cells past the widest
# item here are its selection markers.


@pytest.mark.parametrize("width", [0, -3])
def test_a_listbox_of_no_width_is_as_wide_as_its_widest_item(root, width):
    box = Listbox(root, name="lb", width=width, height=4)
    box.insert("end", "abcdefghij", "ab")
    assert box.winfo_reqwidth() == 10 + 2 + 2


def test_a_listbox_of_no_height_has_a_row_for_every_item(root):
    box = Listbox(root, name="lb", width=10, height=0)
    box.insert("end", "a", "b", "c")
    assert box.winfo_reqheight() == 3 + 2


def test_a_listbox_sized_to_its_items_follows_them(root):
    box = Listbox(root, name="lb", width=0, height=0)
    box.insert("end", "abc", "abcdefgh")
    box.delete(1)
    assert (box.winfo_reqwidth(), box.winfo_reqheight()) == (3 + 2 + 2, 1 + 2)


def test_a_listbox_sized_to_a_list_variable_fits_its_items(root):
    items = StringVar(root, value="one two three")
    box = Listbox(root, name="lb", width=0, height=0, listvariable=items)
    assert (box.winfo_reqwidth(), box.winfo_reqheight()) == (5 + 2 + 2, 3 + 2)
    items.set("a")
    assert (box.winfo_reqwidth(), box.winfo_reqheight()) == (1 + 2 + 2, 1 + 2)


def test_an_empty_listbox_of_no_size_still_has_a_cell(root):
    box = Listbox(root, name="lb", width=0, height=0)
    assert (box.winfo_reqwidth(), box.winfo_reqheight()) == (1 + 2 + 2, 1 + 2)


def test_a_listbox_of_no_width_measures_its_items_in_cells(root):
    box = Listbox(root, name="lb", width=0, height=1)
    box.insert("end", "日本")  # two ideographs: four cells
    assert box.winfo_reqwidth() == 4 + 2 + 2


# ----------------------------------------------------------- scrollbar pair


def test_yview_reports_the_window_as_fractions(listbox):
    """What a scrollbar wants, and what tkinter's yview() returns."""
    first, last = listbox.yview()
    assert first == 0.0
    assert 0.0 < last <= 1.0


def test_yview_moveto_scrolls(listbox):
    listbox.yview("moveto", 0.5)
    assert listbox._top == 4


@pytest.mark.parametrize(("rows", "top"), [(2.3, 2), (2.5, 3), (2.7, 3)])
def test_yview_moveto_rounds_to_the_nearest_row(root, rows, top):
    """Measured on Tk 9.0.2, 30 rows: Tk rounds, halves up. This truncated -
    2.7 rows put row 2 at the top. TkCurses-md5."""
    box = Listbox(root, name="tall", height=5)
    box._allocate(Rect(0, 0, 18, 7))
    box._map()
    box.insert("end", *[str(n) for n in range(30)])
    box.yview_moveto(rows / 30)
    assert box._top == top


def test_yview_scroll_by_units(listbox):
    listbox.yview("scroll", 2, "units")
    assert listbox._top == 2


def test_yview_scroll_by_pages(listbox):
    """A page is the height less two, never under one: Tk 9.0.2."""
    listbox.yview("scroll", 1, "pages")
    assert listbox._top == 2


def test_the_scroll_command_is_told_where_the_view_is(listbox):
    reports = []
    listbox.configure(yscrollcommand=lambda first, last: reports.append((first, last)))
    listbox.yview("scroll", 1, "units")
    assert reports
    assert reports[-1][0] > 0


def test_a_scrollbar_and_a_listbox_drive_each_other(root):
    """Neither knows what the other is; both speak Tk's scrolling protocol."""
    from tkcurses import Scrollbar

    listbox = Listbox(root, name="lb", height=4, width=16)
    listbox._allocate(Rect(0, 0, 18, 6))
    listbox._map()
    listbox.insert("end", *[f"item {n}" for n in range(20)])
    bar = Scrollbar(root, name="sb", command=listbox.yview)
    listbox.configure(yscrollcommand=bar.set)

    listbox.yview("scroll", 4, "units")
    first, _ = bar.get()
    assert first > 0

    bar._options["command"]("moveto", 0.0)
    assert listbox._top == 0


# ------------------------------------------------------ the horizontal view
#
# Missing outright until TkCurses-019. Every expectation below was measured
# on Tk 9.0.2 with a 10-character-wide listbox holding a 30-character item.


@pytest.fixture
def wide(root):
    """Ten cells of text between the markers, as Tk's width=10 has."""
    box = Listbox(root, name="wide", height=4)
    box._allocate(Rect(0, 0, 14, 6))
    box._map()
    box.insert("end", "x" * 30, "short")
    assert box._body_width() == 10
    return box


def test_xview_reports_the_columns_as_fractions_of_the_widest_item(wide):
    assert wide.xview() == (0.0, 10 / 30)


def test_xview_scroll_a_unit_is_one_character(wide):
    wide.xview_scroll(1, "units")
    assert wide.xview() == (1 / 30, 11 / 30)


def test_xview_scroll_a_page_is_the_width_less_two(wide):
    wide.xview_scroll(1, "pages")
    assert wide._left == 8


def test_a_page_is_never_less_than_one_character(root):
    box = Listbox(root, name="narrow")
    box._allocate(Rect(0, 0, 7, 6))  # three cells of text
    box._map()
    box.insert("end", "x" * 100)
    box.xview_scroll(1, "pages")
    assert box._left == 1


@pytest.mark.parametrize("fraction", [0.49, 0.51])
def test_xview_moveto_rounds_to_the_nearest_character(wide, fraction):
    wide.xview_moveto(fraction)
    assert wide._left == 15


@pytest.mark.parametrize(("half", "expected"), [(0.5, 1), (2.5, 3), (4.5, 5)])
def test_xview_moveto_rounds_halves_up(wide, half, expected):
    """Measured on Tk 9.0.2 over a 30-character item: 2.5 -> 3, 4.5 -> 5.

    Python's round() sends halves to the even neighbour - 2.5 -> 2 - which is
    what this did until TkCurses-5e0.
    """
    wide.xview_moveto(half / 30)
    assert wide._left == expected


def test_xview_moveto_stops_at_the_end_of_the_widest_item(wide):
    wide.xview_moveto(1.0)
    assert wide.xview() == (20 / 30, 1.0)


def test_xview_moveto_stops_at_the_start(wide):
    wide.xview_moveto(-1)
    assert wide._left == 0


def test_xview_with_an_index_is_a_character_offset_clamped_to_the_end(wide):
    wide.xview(3)
    assert wide._left == 3
    wide.xview(99)
    assert wide._left == 20


def test_the_offset_holds_when_the_wide_item_goes(wide):
    """Tk's own: measured (0.2, 1.0) over the five-character remainder."""
    wide.xview_scroll(1, "units")
    wide.delete(0)
    assert wide.xview() == (0.2, 1.0)


def test_an_empty_listbox_is_all_showing_both_ways(root):
    box = Listbox(root, name="empty")
    assert box.xview() == (0.0, 1.0)
    assert box.yview() == (0.0, 1.0)


def test_xview_refuses_a_bad_unit(wide):
    with pytest.raises(TclError, match='bad argument "bogus": must be pages or units'):
        wide.xview("scroll", 1, "bogus")


def test_xview_refuses_a_bad_subcommand(wide):
    with pytest.raises(TclError, match='expected integer but got "bogus"'):
        wide.xview("bogus")


def test_the_horizontal_scroll_command_is_told_where_the_view_is(wide):
    reports = []
    wide.configure(xscrollcommand=lambda first, last: reports.append((first, last)))
    wide.xview_scroll(2, "units")
    assert reports[-1] == (2 / 30, 12 / 30)


@pytest.mark.parametrize(
    ("call", "args"),
    [
        ("xview_moveto", (0.5,)),
        ("xview_scroll", (1, "units")),
        ("yview_moveto", (0.0,)),
        ("yview_scroll", (1, "units")),
    ],
)
def test_the_named_scroll_methods_return_none(wide, call, args):
    assert getattr(wide, call)(*args) is None


def test_yview_scroll_and_moveto_are_the_named_forms(listbox):
    listbox.yview_scroll(2, "units")
    assert listbox._top == 2
    listbox.yview_moveto(0.0)
    assert listbox._top == 0


def advance(root, ms):
    """Run the ``after`` callbacks due ``ms`` from now."""
    timers = root.tk.timers
    real = timers._clock
    timers._clock = lambda: real() + ms / 1000
    try:
        timers.run_due()
    finally:
        timers._clock = real


def test_a_drag_held_below_the_list_scrolls_it_and_selects_along(listbox, root):
    """``tk::ListboxAutoScan``: a row at once as the pointer leaves, then one
    every 50ms, the selection run to the item nearest the pointer, until the
    button comes up."""
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=1))
    listbox._handle(MouseEvent(button=0, state="drag", x=2, y=9))
    assert (listbox._top, listbox.curselection()) == (1, (4,))
    advance(root, 60)
    assert (listbox._top, listbox.curselection()) == (2, (5,))
    advance(root, 120)
    assert (listbox._top, listbox.curselection()) == (3, (6,))
    listbox._handle(MouseEvent(button=1, state="released", x=2, y=9))
    assert listbox.index("active") == 6
    advance(root, 500)
    assert listbox._top == 3


def test_a_drag_held_beside_the_list_scrolls_it_sideways(listbox, root):
    """Two columns at a time, as ``tk::ListboxAutoScan`` moves it."""
    listbox.insert("end", "x" * 60)
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=1))
    listbox._handle(MouseEvent(button=0, state="drag", x=30, y=1))
    assert listbox._left == 2
    advance(root, 60)
    assert listbox._left == 4
    listbox._handle(MouseEvent(button=0, state="drag", x=-3, y=1))
    advance(root, 120)
    assert listbox._left == 2


def test_a_drag_back_inside_stops_the_scrolling(listbox, root):
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=1))
    listbox._handle(MouseEvent(button=0, state="drag", x=2, y=9))
    listbox._handle(MouseEvent(button=0, state="drag", x=2, y=2))
    assert listbox._top == 1
    advance(root, 500)
    assert listbox._top == 1


def test_leaving_again_scrolls_again_at_once(listbox):
    """``<B1-Enter>`` cancels the repeat, so the next ``<B1-Leave>`` starts
    one - scrolling there and then - rather than waiting on the old one."""
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=1))
    listbox._handle(MouseEvent(button=0, state="drag", x=2, y=9))
    listbox._handle(MouseEvent(button=0, state="drag", x=2, y=2))
    listbox._handle(MouseEvent(button=0, state="drag", x=2, y=9))
    assert listbox._top == 2


def test_nearest_outside_the_rows_is_the_nearest_visible_item(listbox):
    """Measured on Tk 9.0.2 with four rows of eight items."""
    assert (listbox.nearest(500), listbox.nearest(-50)) == (3, 0)
    listbox.yview(2)
    assert (listbox.nearest(500), listbox.nearest(-50)) == (5, 2)
    assert listbox.index("@3,500") == 5


def test_moving_the_pointer_with_no_button_held_selects_nothing(listbox):
    """Measured on Tk 9.0.2: only ``<B1-Motion>`` is bound."""
    click(listbox, 1)
    listbox._handle(MouseEvent(button=0, state="drag", x=2, y=4))
    assert listbox.curselection() == (1,)


def test_a_browse_drag_sends_an_event_only_when_the_item_changes(listbox):
    """Measured on Tk 9.0.2: a press on 1 and motion over 2, 2, 3, 3 send
    three events, not five - ``tk::ListboxMotion`` returns at once for the
    item it last went to."""
    seen = []
    listbox.bind("<<ListboxSelect>>", lambda event: seen.append(1))
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=2))
    for row in (2, 2, 3, 3):
        listbox._handle(MouseEvent(button=0, state="drag", x=2, y=1 + row))
    assert (len(seen), listbox.curselection()) == (3, (3,))


def test_escape_gives_back_what_a_range_replaced(listbox):
    """Measured on Tk 9.0.2, extended mode: click 1, Control-click 4,
    Shift-click 0 selects 0 to 4, and Escape leaves 1, which was selected
    before the range began."""
    listbox.configure(selectmode="extended", height=8)
    listbox._allocate(Rect(0, 0, 18, 10))
    click(listbox, 1)
    click(listbox, 4, MOD_CTRL)
    click(listbox, 0, MOD_SHIFT)
    assert listbox.curselection() == (0, 1, 2, 3, 4)
    press(listbox, "Escape")
    assert listbox.curselection() == (1,)


def test_a_click_on_a_disabled_listbox_leaves_the_focus_alone(listbox, root):
    """Measured on Tk 9.0.2."""
    listbox.configure(state="disabled")
    click(listbox, 2)
    assert listbox.focus_get() is not listbox


def test_items_inserted_into_an_empty_list_leave_active_on_the_last(root):
    """Measured on Tk 9.0.2: eight inserted give active 7 and anchor 8 -
    the anchor is not kept on an item, the active index is."""
    box = Listbox(root, name="fresh")
    box.insert("end", *map(str, range(8)))
    assert (box.index("active"), box.index("anchor")) == (7, 8)


def test_invoke_selects_the_active_item_as_space_does(listbox):
    listbox.activate(2)
    listbox.event_generate("<<Invoke>>")
    assert listbox.curselection() == (2,)


# ----------------------------------------------------------- exportselection
#
# Each measured on Tk 9.0.2 with tkinter, TkCurses-9e8.


def lists(root, *names, **options):
    """Fresh extended listboxes holding one, two, three and four."""
    made = []
    for name in names:
        box = Listbox(root, name=name, selectmode="extended", **options)
        box._allocate(Rect(0, 0, 18, 6))
        box._map()
        box.insert("end", "one", "two", "three", "four")
        made.append(box)
    return made


def owner(root):
    try:
        return root.selection_own_get()
    except TclError:
        return None


def test_a_selection_is_exported_one_item_per_line(root):
    (box,) = lists(root, "a")
    box.selection_set(1)
    box.selection_set(3)
    assert owner(root) is box
    assert root.selection_get() == "two\nfour"


def test_a_cleared_selection_keeps_primary_and_reads_as_nothing(root):
    (box,) = lists(root, "a")
    box.selection_set(1)
    box.selection_clear(0, "end")
    assert owner(root) is box
    with pytest.raises(TclError):
        root.selection_get()


def test_primary_follows_the_items_when_they_change(root):
    (box,) = lists(root, "a")
    box.selection_set(0, 1)
    box.delete(0)
    assert root.selection_get() == "two"


def test_an_entry_taking_primary_clears_the_list_and_says_so(root):
    from tkcurses import Entry

    (box,) = lists(root, "a")
    seen = []
    box.bind("<<ListboxSelect>>", lambda event: seen.append(1))
    box.selection_set(1)
    entry = Entry(root, name="e")
    entry.insert(0, "entrytext")
    entry.selection_range(0, 3)
    assert (box.curselection(), len(seen)) == ((), 1)
    box.selection_set(2)
    assert owner(root) is box
    assert not entry.selection_present()


def test_another_list_taking_primary_clears_the_first(root):
    first, second = lists(root, "a", "b")
    seen = []
    first.bind("<<ListboxSelect>>", lambda event: seen.append(1))
    first.selection_set(0)
    second.selection_set(1)
    assert (first.curselection(), len(seen), owner(root)) == ((), 1, second)


def test_a_loss_sends_the_event_with_nothing_selected_and_while_disabled(root):
    first, second = lists(root, "a", "b")
    seen = []
    first.bind("<<ListboxSelect>>", lambda event: seen.append(1))
    first.selection_set(0)
    first.selection_clear(0, "end")
    second.selection_set(0)
    assert len(seen) == 1
    first.selection_set(1)
    first.configure(state="disabled")
    second.selection_set(2)
    assert (first.curselection(), len(seen)) == ((), 2)


def test_without_exportselection_nothing_is_taken_or_lost(root):
    first, second = lists(root, "a", "b")
    (quiet,) = lists(root, "q", exportselection=False)
    first.selection_set(0)
    quiet.selection_set(1)
    assert owner(root) is first
    second.selection_set(0)
    assert quiet.curselection() == (1,)


def test_turning_exportselection_on_exports_what_is_selected(root):
    (first,) = lists(root, "a")
    (quiet,) = lists(root, "q", exportselection=False)
    first.selection_set(0)
    quiet.selection_set(0, 1)
    quiet.configure(exportselection=True)
    assert (owner(root), root.selection_get()) == (quiet, "one\ntwo")
    assert first.curselection() == ()


def test_turning_exportselection_off_keeps_primary_but_reads_as_nothing(root):
    """Unlike Entry, which gives PRIMARY up."""
    from tkcurses import Entry

    (box,) = lists(root, "a")
    box.selection_set(0)
    box.configure(exportselection=False)
    assert owner(root) is box
    with pytest.raises(TclError):
        root.selection_get()
    entry = Entry(root, name="e")
    entry.insert(0, "abc")
    entry.selection_range(0, 1)
    assert box.curselection() == (0,)


def test_a_click_in_another_list_ends_a_range_begun_in_this_one(root):
    """The interleaving in TkCurses-9e8's notes: click 1 and Control-click 3
    in B, click 6 in A, Shift-click 5 in B. A's click takes PRIMARY and
    clears B, so the Shift-click finds no selected anchor and begins afresh:
    (5,). Without exportselection it is (1, 3, 4, 5)."""
    for options, expected in (({}, (5,)), ({"exportselection": False}, (1, 3, 4, 5))):
        a, b = (
            Listbox(
                root,
                name=f"{n}{len(options)}",
                selectmode="extended",
                height=8,
                **options,
            )
            for n in "ab"
        )
        for box in (a, b):
            box._allocate(Rect(0, 0, 18, 10))
            box._map()
            box.insert("end", *map(str, range(8)))
        click(b, 1)
        click(b, 3, MOD_CTRL)
        click(a, 6)
        click(b, 5, MOD_SHIFT)
        assert b.curselection() == expected


# ------------------------------------------------------------ virtual events
#
# Each measured on Tk 9.0.2 with tkinter, TkCurses-yu5l.


def test_a_generated_prevline_moves_up(listbox):
    listbox.activate(2)
    listbox.event_generate("<<PrevLine>>")
    assert (listbox.index("active"), listbox.curselection()) == (1, (1,))


def test_a_key_added_to_prevline_moves_the_list_too(listbox, root):
    listbox.activate(1)
    root.event_add("<<PrevLine>>", "<Control-Key-k>")
    press(listbox, "k", MOD_CTRL)
    assert listbox.index("active") == 0


def test_home_does_nothing_once_linestart_is_gone(listbox, root):
    listbox.insert("end", "x" * 80)
    listbox.xview("moveto", 0.5)
    root.event_delete("<<LineStart>>")
    press(listbox, "Home")
    assert listbox._left > 0


def test_copy_puts_the_exported_selection_on_the_clipboard(root):
    (box,) = lists(root, "a")
    box.selection_set(1, 2)
    box.event_generate("<<Copy>>")
    assert root.clipboard_get() == "two\nthree"


def test_copy_from_an_unexported_list_leaves_the_clipboard_alone(root):
    (box,) = lists(root, "q", exportselection=False)
    box.selection_set(0)
    root.clipboard_clear()
    root.clipboard_append("before")
    box.event_generate("<<Copy>>")
    assert root.clipboard_get() == "before"


def test_the_navigation_events_are_defined_as_tk_defines_them(root):
    """tk.tcl, X11, with tk_strictMotif off: each with the keys it names
    there that a terminal can send."""
    expected = {
        "<<PrevLine>>": ("<Key-Up>", "<Control-Key-p>"),
        "<<SelectNextLine>>": ("<Shift-Key-Down>",),
        "<<LineStart>>": ("<Key-Home>", "<Control-Key-a>"),
        "<<PrevWord>>": ("<Control-Key-Left>",),
        "<<SelectNextPara>>": ("<Control-Shift-Key-Down>",),
    }
    for virtual, sequences in expected.items():
        assert root.event_info(virtual) == sequences
    assert "<<SelectNone>>" not in root.event_info()


# ------------------------------------------------- per-item options, Tk's


def test_an_item_has_four_colours_of_its_own(root):
    box = Listbox(root)
    box.insert("end", "a", "b", "c")
    assert set(box.itemconfigure(0)) == {
        "background", "foreground", "selectbackground", "selectforeground",
        "bg", "fg",
    }  # fmt: skip
    box.itemconfigure(1, bg="red", foreground="blue")
    assert (box.itemcget(1, "background"), box.itemcget(1, "fg")) == ("red", "blue")
    assert box.itemcget(0, "background") == ""
    assert box.itemconfigure(1, "background") == ("background", "", "", "", "red")


@pytest.mark.parametrize(
    "call, message",
    [
        (lambda box: box.itemcget(1, "nonsense"), 'unknown option "-nonsense"'),
        (lambda box: box.itemconfigure(9, bg="red"), 'item number "9" out of range'),
        (lambda box: box.itemcget(-1, "bg"), 'item number "-1" out of range'),
        (lambda box: box.itemconfigure(1, bg="notacolour"), 'unknown color name "notacolour"'),
    ],
)  # fmt: skip
def test_what_tk_refuses_an_item_is_refused(root, call, message):
    box = Listbox(root)
    box.insert("end", "a", "b", "c")
    with pytest.raises(TclError) as caught:
        call(box)
    assert str(caught.value) == message


def test_an_items_colours_go_with_it(root):
    """Measured on Tk 9.0.2: deleting above it or inserting above it moves
    the item and its colour together."""
    box = Listbox(root)
    box.insert("end", "a", "b", "c")
    box.itemconfigure(1, bg="red")
    box.delete(0)
    assert box.itemcget(0, "bg") == "red"
    box.insert(0, "z")
    assert (box.itemcget(0, "bg"), box.itemcget(1, "bg")) == ("", "red")
    box.delete(1)
    assert [box.itemcget(i, "bg") for i in range(box.size())] == ["", ""]


# ----------------------------------------------------------------- scanning

#: A scan, as (operation, x, y) in characters and lines.
SCAN = [
    ("mark", 0, 0), ("drag", 0, -1), ("drag", 0, -2), ("drag", 0, -5),
    ("drag", 0, -4), ("drag", -1, -4), ("drag", -3, 0), ("drag", 2, 1),
    ("drag", 9, 9), ("drag", 8, 8), ("mark", 3, 3), ("drag", 3, 2),
    ("drag", 2, 2), ("drag", 5, 5),
]  # fmt: skip

SCAN_ITEMS = [f"item {n:02d} " + "x" * (n % 7) * 4 for n in range(30)]


def _scanned(box: Any, line: int, char: int) -> list[tuple[int, int]]:
    """The top item and the first character in view after each step."""
    widest = max(len(item) for item in SCAN_ITEMS)
    found = []
    for operation, x, y in SCAN:
        method = box.scan_mark if operation == "mark" else box.scan_dragto
        method(x * char, y * line)
        found.append((box.nearest(0), round(box.xview()[0] * widest)))
    return found


def test_a_scan_drags_ten_to_one_and_restarts_at_an_edge_as_tks_does(root):
    """Measured against Tk's ListboxScanTo with a fixed font, its pixels
    scaled to lines and characters: a line of drag is ten items, a drag past
    either end leaves the view there, and turning back moves it at once."""
    tkinter = pytest.importorskip("tkinter")
    from tkinter import font

    try:
        real = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    try:
        theirs_box = tkinter.Listbox(
            real, height=5, width=10, selectborderwidth=0, font="TkFixedFont"
        )
        theirs_box.insert("end", *SCAN_ITEMS)
        theirs_box.pack()
        real.update()
        # A listbox line is the font's linespace and one; bbox gives the first.
        line = theirs_box.bbox(0)[3] + 1
        char = font.nametofont("TkFixedFont").measure("0")
        theirs = _scanned(theirs_box, line, char)
    finally:
        real.destroy()

    box = Listbox(root, name="scan", height=5)
    box._allocate(Rect(0, 0, 14, 7))
    box._map()
    box.insert("end", *SCAN_ITEMS)
    assert box._body_width() == 10 and box._text_area().height == 5
    assert _scanned(box, 1, 1) == theirs


def test_a_scan_refuses_what_is_not_an_integer(listbox):
    with pytest.raises(TclError, match='expected integer but got "a"'):
        listbox.scan_mark("a", 1)
    with pytest.raises(TclError, match='expected integer but got "b"'):
        listbox.scan_dragto(1, "b")
