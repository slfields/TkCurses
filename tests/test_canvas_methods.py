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

"""The Canvas's searches, tags, transforms, text editing and scanning.

Every expectation here was measured on Tk 9.0.2 through tkinter, except
where a comment says the extent differs: Tk's extent of an outlined item
is a pixel wider on each side, and a TkCurses item's extent is its points.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from tkcurses import Canvas, Misc, TclError
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


@pytest.fixture
def canvas():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    widget = Canvas(root, name="c", width=40, height=10, relief="flat")
    widget._allocate(Rect(0, 0, 40, 10))
    widget._map()
    return widget


@pytest.fixture
def four(canvas):
    """Tk's measurement: two overlapping rectangles, a line and a text."""
    canvas.create_rectangle(10, 10, 20, 20, tags="a")
    canvas.create_rectangle(15, 15, 40, 40, tags="b")
    canvas.create_line(50, 50, 60, 60, tags="l")
    canvas.create_text(100, 100, text="hello", tags="t")
    return canvas


# ----------------------------------------------------------------- searching


def test_find_above_and_below_are_the_neighbours_in_the_display_list(four):
    assert four.find_above(1) == (2,)
    assert four.find_above(4) == ()
    assert four.find_below(1) == ()
    assert four.find_below(2) == (1,)


def test_above_a_tag_starts_from_its_topmost_item_and_below_from_its_lowest(four):
    four.addtag_withtag("ab", 1)
    four.addtag_withtag("ab", 2)
    assert four.find_above("ab") == (3,)
    assert four.find_below("ab") == ()
    assert four.find_above("nothing") == ()


@pytest.mark.parametrize(
    ("rect", "enclosed", "overlapping"),
    [
        ((10, 10, 20, 20), (1,), (1, 2)),
        ((11, 11, 19, 19), (), (1, 2)),
        ((10, 10, 40, 40), (1, 2), (1, 2)),
        ((0, 0, 70, 70), (1, 2, 3), (1, 2, 3)),
    ],
)
def test_enclosed_wants_the_whole_extent_and_overlapping_any_of_it(
    four, rect, enclosed, overlapping
):
    assert four.find_enclosed(*rect) == enclosed
    assert four.find_overlapping(*rect) == overlapping


def test_a_hidden_item_is_not_found_by_area(four):
    four.itemconfigure(1, state="hidden")
    assert four.find_overlapping(0, 0, 70, 70) == (2, 3)
    assert four.find_enclosed(0, 0, 70, 70) == (2, 3)


def test_find_takes_tks_search_specifications(four):
    four.addtag_withtag("ab", 1)
    four.addtag_withtag("ab", 2)
    assert four.find("enclosed", 10, 10, 20, 20) == (1,)
    assert four.find("withtag", "ab") == (1, 2)
    assert four.find("all") == (1, 2, 3, 4)
    assert four.find("above", 1) == (2,)
    assert four.find("closest", 17, 17) == (2,)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ("nonsense",),
            'bad search command "nonsense": must be above, all, below, closest,'
            " enclosed, overlapping, or withtag",
        ),
        (("above",), 'wrong # args: should be ".c find above tagOrId"'),
        (("enclosed", 1, 2), 'wrong # args: should be ".c find enclosed x1 y1 x2 y2"'),
    ],
)
def test_a_bad_search_is_refused_in_tks_words(four, args, message):
    with pytest.raises(TclError) as caught:
        four.find(*args)
    assert str(caught.value) == message


def test_closest_prefers_the_topmost_of_equals(canvas):
    for _ in range(4):
        canvas.create_rectangle(10, 10, 30, 30)
    assert canvas.find_closest(20, 20) == (4,)


@pytest.mark.parametrize(("start", "found"), [(1, 4), (2, 1), (3, 2), (4, 3)])
def test_closest_from_a_start_goes_round_from_below_it(canvas, start, found):
    for _ in range(4):
        canvas.create_rectangle(10, 10, 30, 30)
    assert canvas.find_closest(20, 20, 0, start) == (found,)


def test_a_halo_makes_anything_near_enough_touch(canvas):
    canvas.create_rectangle(0, 0, 10, 10)
    canvas.create_rectangle(100, 100, 110, 110)
    assert canvas.find_closest(105, 50) == (2,)
    # Within 200 of both, both are at distance nothing, and the topmost wins
    # unless the search starts above it.
    assert canvas.find_closest(105, 50, 200, 2) == (1,)


def test_a_negative_halo_is_refused(canvas):
    canvas.create_rectangle(0, 0, 10, 10)
    with pytest.raises(
        TclError, match=re.escape('can\'t have negative halo value "-1.000000"')
    ):
        canvas.find_closest(1, 1, -1)


def test_closest_on_an_empty_canvas_is_nothing(canvas):
    assert canvas.find_closest(1, 1) == ()


# ------------------------------------------------------------------ tagging


def test_the_addtag_family_tags_what_the_matching_search_finds(four):
    four.addtag_enclosed("enc", 10, 10, 20, 20)
    four.addtag_overlapping("ov", 50, 50, 51, 51)
    four.addtag_above("up", 1)
    four.addtag_below("down", 2)
    four.addtag_all("every")
    four.addtag_closest("near", 17, 17)
    four.addtag("raw", "withtag", "t")
    assert four.find_withtag("enc") == (1,)
    assert four.find_withtag("ov") == (3,)
    assert four.find_withtag("up") == (2,)
    assert four.find_withtag("down") == (1,)
    assert four.find_withtag("every") == (1, 2, 3, 4)
    assert four.find_withtag("near") == (2,)
    assert four.find_withtag("raw") == (4,)
    assert four.gettags(1) == ("a", "enc", "down", "every")


def test_a_tag_is_added_once(four):
    four.addtag_all("x")
    four.addtag_all("x")
    assert four.gettags(1) == ("a", "x")


# --------------------------------------------------------------- transforms


def test_scale_moves_each_point_about_the_origin(canvas):
    rect = canvas.create_rectangle(10, 10, 20, 30)
    canvas.scale(rect, 10, 10, 2, 0.5)
    assert canvas.coords(rect) == [10, 10, 30, 20]


def test_scale_moves_a_text_items_point_and_not_its_text(canvas):
    text = canvas.create_text(5, 5, text="hi")
    canvas.scale(text, 0, 0, 2, 2)
    assert canvas.coords(text) == [10, 10]
    assert canvas.itemcget(text, "text") == "hi"


def test_scale_refuses_a_number_that_is_not_one(canvas):
    rect = canvas.create_rectangle(1, 1, 2, 2)
    with pytest.raises(TclError, match='expected floating-point number but got "x"'):
        canvas.scale(rect, 0, 0, "x", 1)


def test_moveto_puts_the_extents_corner_at_the_point(canvas):
    rect = canvas.create_rectangle(10, 10, 20, 30)
    canvas.moveto(rect, 5, 6)
    assert canvas.bbox(rect)[:2] == (5, 6)


def test_moveto_with_an_empty_axis_leaves_it(canvas):
    rect = canvas.create_rectangle(10, 10, 20, 30)
    canvas.moveto(rect, "", 2)
    assert canvas.coords(rect) == [10, 2, 20, 22]


def test_moveto_a_tag_moves_its_items_together_by_the_lowest(canvas):
    lowest = canvas.create_rectangle(10, 10, 12, 12, tags="g")
    other = canvas.create_rectangle(0, 0, 4, 4, tags="g")
    canvas.moveto("g", 20, 20)
    assert canvas.coords(lowest) == [20, 20, 22, 22]
    assert canvas.coords(other) == [10, 10, 14, 14]


def test_moveto_nothing_does_nothing(canvas):
    canvas.moveto("nothing", 1, 1)


def test_postscript_says_it_cannot(canvas):
    with pytest.raises(TclError, match="postscript"):
        canvas.postscript()


# ----------------------------------------------------------- editing text


@pytest.fixture
def text(canvas):
    return canvas.create_text(20, 4, text="hello", anchor="nw")


def test_insert_puts_text_before_an_index(canvas, text):
    canvas.insert(text, 2, "XY")
    assert canvas.itemcget(text, "text") == "heXYllo"
    canvas.insert(text, "end", "!")
    assert canvas.itemcget(text, "text") == "heXYllo!"


def test_insert_reaches_every_text_item_a_tag_names(canvas):
    first = canvas.create_text(1, 1, text="a", tags="t")
    second = canvas.create_text(1, 9, text="b", tags="t")
    canvas.insert("t", "end", "!")
    assert canvas.itemcget(first, "text") == "a!"
    assert canvas.itemcget(second, "text") == "b!"


@pytest.mark.parametrize(
    ("index", "expected"), [("end", 5), (3, 3), (99, 5), (-2, 0), ("insert", 0)]
)
def test_index_forms(canvas, text, index, expected):
    assert canvas.index(text, index) == expected


def test_index_at_a_point_is_the_character_there(canvas, text):
    assert canvas.index(text, "@22,4") == 2


def test_a_newline_counts_as_a_character(canvas, text):
    canvas.itemconfigure(text, text="ab\ncd")
    assert canvas.index(text, "end") == 5
    assert canvas.index(text, "@21,6") == 4


def test_the_cursor_moves_with_text_inserted_before_it(canvas, text):
    canvas.insert(text, 2, "XY")
    canvas.icursor(text, 3)
    canvas.insert(text, "insert", "_")
    assert canvas.itemcget(text, "text") == "heX_Yllo"
    assert canvas.index(text, "insert") == 4


def test_icursor_past_the_end_is_the_end(canvas, text):
    canvas.icursor(text, 99)
    assert canvas.index(text, "insert") == 5


def test_dchars_deletes_one_or_a_range_and_the_cursor_follows(canvas, text):
    canvas.itemconfigure(text, text="heX_Yllo!")
    canvas.icursor(text, 4)
    canvas.dchars(text, 0)
    assert canvas.itemcget(text, "text") == "eX_Yllo!"
    assert canvas.index(text, "insert") == 3
    canvas.dchars(text, 1, 3)
    assert canvas.itemcget(text, "text") == "ello!"
    assert canvas.index(text, "insert") == 1
    canvas.dchars(text, 2, "end")
    assert canvas.itemcget(text, "text") == "el"


def test_dchars_backwards_deletes_nothing(canvas, text):
    canvas.dchars(text, 3, 1)
    assert canvas.itemcget(text, "text") == "hello"


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda c, t: c.index(t, "bogus"), 'bad index "bogus"'),
        (lambda c, t: c.index("nosuch", 1), 'can\'t find an indexable item "nosuch"'),
        (lambda c, t: c.index(t, "sel.first"), "selection isn't in item"),
        (lambda c, t: c.icursor(t, "zz"), 'bad index "zz"'),
        (lambda c, t: c.insert(t, "zz", "x"), 'bad index "zz"'),
        (
            lambda c, t: c.select_from("nosuch", 1),
            'can\'t find an indexable and selectable item "nosuch"',
        ),
    ],
)
def test_editing_refusals_are_tks(canvas, text, call, message):
    with pytest.raises(TclError) as caught:
        call(canvas, text)
    assert str(caught.value) == message


def test_editing_an_item_nothing_names_is_quietly_nothing(canvas):
    canvas.icursor("nosuch", 1)
    canvas.insert("nosuch", 0, "x")
    canvas.dchars("nosuch", 0)


def test_a_rectangle_cannot_be_indexed(canvas):
    rect = canvas.create_rectangle(1, 1, 5, 5)
    with pytest.raises(TclError, match="can't find an indexable item"):
        canvas.index(rect, 0)
    with pytest.raises(TclError, match="indexable and selectable"):
        canvas.select_from(rect, 1)


def test_a_lines_index_counts_coordinates(canvas):
    line = canvas.create_line(0, 0, 10, 10, 20, 0)
    assert canvas.index(line, "end") == 6
    assert canvas.index(line, 3) == 2
    assert canvas.index(line, "@11,9") == 2


def test_insert_and_dchars_edit_a_lines_points(canvas):
    line = canvas.create_line(0, 0, 10, 10, 20, 0)
    canvas.insert(line, 2, (5, 5))
    assert canvas.coords(line) == [0, 0, 5, 5, 10, 10, 20, 0]
    canvas.dchars(line, 2)
    assert canvas.coords(line) == [0, 0, 10, 10, 20, 0]
    canvas.dchars(line, 0, 2)
    assert canvas.coords(line) == [20, 0]
    canvas.insert(line, "end", "30 30")
    assert canvas.coords(line) == [20, 0, 30, 30]


# ---------------------------------------------------------------- selection


def test_the_selection_runs_from_the_anchor(canvas, text):
    canvas.itemconfigure(text, text="hello world")
    assert canvas.select_item() is None
    canvas.select_from(text, 2)
    canvas.select_to(text, 5)
    assert canvas.select_item() == text
    assert (canvas.index(text, "sel.first"), canvas.index(text, "sel.last")) == (2, 5)
    canvas.select_to(text, 0)
    assert (canvas.index(text, "sel.first"), canvas.index(text, "sel.last")) == (0, 1)


def test_select_adjust_moves_the_nearer_end(canvas, text):
    canvas.itemconfigure(text, text="hello world")
    canvas.select_from(text, 2)
    canvas.select_to(text, 0)
    canvas.select_adjust(text, 8)
    assert (canvas.index(text, "sel.first"), canvas.index(text, "sel.last")) == (0, 8)
    canvas.select_adjust(text, 1)
    assert (canvas.index(text, "sel.first"), canvas.index(text, "sel.last")) == (1, 8)


def test_deleting_the_selected_text_ends_the_selection(canvas, text):
    canvas.itemconfigure(text, text="hello world")
    canvas.select_from(text, 1)
    canvas.select_to(text, 8)
    canvas.dchars(text, "sel.first", "sel.last")
    assert canvas.itemcget(text, "text") == "hld"
    assert canvas.select_item() is None


def test_select_clear(canvas, text):
    canvas.select_from(text, 0)
    canvas.select_to(text, 3)
    canvas.select_clear()
    assert canvas.select_item() is None


def test_deleting_the_item_forgets_its_selection_and_focus(canvas, text):
    canvas.select_from(text, 0)
    canvas.select_to(text, 3)
    canvas.focus(text)
    canvas.delete(text)
    assert canvas.select_item() is None
    assert canvas.focus() == ""


def test_focus_names_the_text_item_with_the_cursor(canvas, text):
    rect = canvas.create_rectangle(1, 1, 2, 2)
    assert canvas.focus() == ""
    canvas.focus(text)
    assert canvas.focus() == text
    canvas.focus(rect)  # not a text item: the focus stays
    assert canvas.focus() == text
    canvas.focus("")
    assert canvas.focus() == ""


# ----------------------------------------------------------------- scanning


def test_scan_dragto_moves_the_view_gain_times_the_drag(canvas):
    canvas.configure(scrollregion=(0, 0, 400, 400))
    canvas.scan_mark(10, 5)
    canvas.scan_dragto(8, 4)
    # Ten times two columns across; ten times one row, of two units, down.
    assert (canvas._left, canvas._top) == (20, 20)
    canvas.scan_dragto(9, 5, gain=1)
    assert (canvas._left, canvas._top) == (1, 0)


def test_scan_is_confined_to_the_region(canvas):
    canvas.configure(scrollregion=(0, 0, 400, 400))
    canvas.scan_mark(10, 5)
    canvas.scan_dragto(20, 9)
    assert (canvas._left, canvas._top) == (0, 0)


def test_scan_wants_integers(canvas):
    with pytest.raises(TclError, match=re.escape('expected integer but got "1.5"')):
        canvas.scan_mark(1.5, 2)
