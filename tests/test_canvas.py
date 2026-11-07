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

"""Tests for the Canvas widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Canvas, Misc, TclError
from tkcurses._core.events import MouseEvent
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
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    return root


@pytest.fixture
def canvas(root):
    """A canvas 40 cells by 10, so a plane 40 pixels by 20."""
    widget = Canvas(root, name="c", width=40, height=10, relief="flat")
    widget._allocate(Rect(0, 0, 40, 10))
    widget._map()
    return widget


# ------------------------------------------------------------- making things


def test_each_item_gets_its_own_id(canvas):
    first = canvas.create_line(0, 0, 5, 5)
    second = canvas.create_line(0, 0, 5, 5)
    assert first != second


def test_find_all_is_in_drawing_order(canvas):
    ids = [canvas.create_line(0, 0, 1, 1) for _ in range(3)]
    assert canvas.find_all() == tuple(ids)


@pytest.mark.parametrize(
    ("maker", "args"),
    [
        ("create_line", (0, 0, 5, 5)),
        ("create_rectangle", (0, 0, 5, 5)),
        ("create_oval", (0, 0, 5, 5)),
        ("create_polygon", (0, 0, 5, 0, 5, 5)),
        ("create_text", (2, 2)),
    ],
)
def test_every_item_type_can_be_made(canvas, maker, args):
    assert getattr(canvas, maker)(*args) in canvas.find_all()


def test_coordinates_can_be_given_as_pairs(canvas):
    """Tk takes flat numbers, pairs, or one sequence of either."""
    flat = canvas.create_line(0, 1, 2, 3)
    paired = canvas.create_line((0, 1), (2, 3))
    sequence = canvas.create_line([0, 1, 2, 3])
    assert canvas.coords(flat) == canvas.coords(paired) == canvas.coords(sequence)


def test_too_few_points_is_refused(canvas):
    with pytest.raises(TclError, match="coordinates"):
        canvas.create_polygon(0, 0, 5, 5)


def test_a_rectangle_needs_exactly_two_corners(canvas):
    with pytest.raises(TclError, match="coordinates"):
        canvas.create_rectangle(0, 0, 5, 5, 9, 9)


def test_an_option_the_type_does_not_take_is_refused(canvas):
    with pytest.raises(TclError, match="unknown option"):
        canvas.create_line(0, 0, 5, 5, text="no")


def test_an_abbreviated_option_is_refused(canvas):
    """Tcl lets options be abbreviated; tkinter's Python API does not."""
    with pytest.raises(TclError, match="unknown option"):
        canvas.create_line(0, 0, 5, 5, f="red")


# ----------------------------------------------------------------- geometry


def test_bbox_of_one_item(canvas):
    item = canvas.create_rectangle(3, 4, 11, 9)
    assert canvas.bbox(item) == (3, 4, 11, 9)


def test_bbox_of_everything(canvas):
    canvas.create_rectangle(0, 0, 4, 4)
    canvas.create_rectangle(10, 8, 14, 12)
    assert canvas.bbox() == (0, 0, 14, 12)


def test_bbox_of_nothing_is_none(canvas):
    assert canvas.bbox() is None


def test_a_rectangle_given_backwards_has_the_same_bbox(canvas):
    canvas.create_rectangle(9, 9, 1, 1)
    assert canvas.bbox() == (1, 1, 9, 9)


def test_coords_reads_and_writes(canvas):
    item = canvas.create_line(0, 0, 5, 5)
    canvas.coords(item, 1, 2, 3, 4)
    assert canvas.coords(item) == [1, 2, 3, 4]


def test_move_shifts_every_point(canvas):
    item = canvas.create_line(0, 0, 5, 5)
    canvas.move(item, 2, 3)
    assert canvas.coords(item) == [2, 3, 7, 8]


def test_move_takes_a_tag(canvas):
    canvas.create_line(0, 0, 1, 1, tags="group")
    canvas.create_line(4, 4, 5, 5, tags="group")
    canvas.move("group", 1, 1)
    assert canvas.bbox() == (1, 1, 6, 6)


def test_a_text_item_occupies_whole_cells(canvas):
    """A glyph fills a cell, so a text item snaps to a cell row."""
    item = canvas.create_text(4, 5, text="abc", anchor="nw")
    left, top, right, bottom = canvas.bbox(item)
    assert top % 2 == 0
    assert bottom - top == 1  # one cell row, which is two pixel rows
    assert right - left == 2


# --------------------------------------------------------------------- tags


def test_tags_can_be_given_as_a_string_or_a_sequence(canvas):
    one = canvas.create_line(0, 0, 1, 1, tags="a b")
    many = canvas.create_line(0, 0, 1, 1, tags=("a", "b"))
    assert canvas.gettags(one) == canvas.gettags(many) == ("a", "b")


def test_find_withtag(canvas):
    first = canvas.create_line(0, 0, 1, 1, tags="wanted")
    canvas.create_line(0, 0, 1, 1, tags="other")
    assert canvas.find_withtag("wanted") == (first,)


def test_find_withtag_all_finds_everything(canvas):
    ids = [canvas.create_line(0, 0, 1, 1) for _ in range(3)]
    assert canvas.find_withtag("all") == tuple(ids)


def test_an_id_works_wherever_a_tag_does(canvas):
    item = canvas.create_line(0, 0, 1, 1)
    assert canvas.find_withtag(item) == (item,)


def test_addtag_and_dtag(canvas):
    item = canvas.create_line(0, 0, 1, 1, tags="first")
    canvas.addtag_withtag("second", "first")
    assert canvas.gettags(item) == ("first", "second")
    canvas.dtag("first", "second")
    assert canvas.gettags(item) == ("first",)


def test_delete_takes_tags(canvas):
    canvas.create_line(0, 0, 1, 1, tags="doomed")
    kept = canvas.create_line(0, 0, 1, 1)
    canvas.delete("doomed")
    assert canvas.find_all() == (kept,)


def test_delete_all(canvas):
    canvas.create_line(0, 0, 1, 1)
    canvas.delete("all")
    assert canvas.find_all() == ()


# ------------------------------------------------------------------ stacking


def test_tag_raise_moves_to_the_front(canvas):
    first = canvas.create_line(0, 0, 1, 1)
    canvas.create_line(0, 0, 1, 1)
    canvas.tag_raise(first)
    assert canvas.find_all()[-1] == first


def test_tag_lower_moves_to_the_back(canvas):
    canvas.create_line(0, 0, 1, 1)
    last = canvas.create_line(0, 0, 1, 1)
    canvas.tag_lower(last)
    assert canvas.find_all()[0] == last


def test_tag_raise_above_a_named_item(canvas):
    bottom = canvas.create_line(0, 0, 1, 1)
    middle = canvas.create_line(0, 0, 1, 1)
    top = canvas.create_line(0, 0, 1, 1)
    canvas.tag_raise(bottom, middle)
    assert canvas.find_all() == (middle, bottom, top)


# ------------------------------------------------------------------ searching


def test_find_overlapping(canvas):
    inside = canvas.create_rectangle(0, 0, 4, 4)
    canvas.create_rectangle(20, 14, 24, 18)
    assert canvas.find_overlapping(1, 1, 3, 3) == (inside,)


def test_find_overlapping_counts_a_touching_edge(canvas):
    item = canvas.create_rectangle(4, 4, 8, 8)
    assert canvas.find_overlapping(0, 0, 4, 4) == (item,)


def test_find_closest(canvas):
    near = canvas.create_rectangle(0, 0, 2, 2)
    canvas.create_rectangle(30, 16, 34, 18)
    assert canvas.find_closest(1, 1) == (near,)


def test_find_closest_on_an_empty_canvas(canvas):
    assert canvas.find_closest(0, 0) == ()


def test_find_closest_prefers_the_topmost_of_two_equals(canvas):
    canvas.create_rectangle(0, 0, 4, 4)
    later = canvas.create_rectangle(0, 0, 4, 4)
    assert canvas.find_closest(2, 2) == (later,)


# ----------------------------------------------------------------- item options


def test_itemconfigure_changes_an_option(canvas):
    item = canvas.create_rectangle(0, 0, 4, 4, fill="red")
    canvas.itemconfigure(item, fill="blue")
    assert canvas.itemcget(item, "fill") == "blue"


def test_itemconfigure_takes_a_tag(canvas):
    canvas.create_line(0, 0, 1, 1, tags="group")
    second = canvas.create_line(2, 2, 3, 3, tags="group")
    canvas.itemconfigure("group", fill="green")
    assert canvas.itemcget(second, "fill") == "green"


def test_itemcget_of_an_unknown_item_is_refused(canvas):
    with pytest.raises(TclError):
        canvas.itemcget(99, "fill")


def test_itemconfigure_refuses_an_option_of_another_type(canvas):
    item = canvas.create_line(0, 0, 4, 4)
    with pytest.raises(TclError, match="unknown option"):
        canvas.itemconfigure(item, text="no")


def test_type_names_the_kind(canvas):
    assert canvas.type(canvas.create_oval(0, 0, 4, 4)) == "oval"
    assert canvas.type(99) is None


# -------------------------------------------------------------- tag bindings


def click(canvas, x, y, state="pressed", button=1):
    area = canvas._text_area()
    canvas._handle(
        MouseEvent(button=button, state=state, x=area.x + x, y=area.y + y // 2)
    )


def test_a_click_reaches_the_item_under_it(canvas):
    seen = []
    item = canvas.create_rectangle(0, 0, 8, 8, fill="red", tags="hot")
    canvas.tag_bind("hot", "<Button-1>", lambda event: seen.append(item))
    click(canvas, 2, 2)
    assert seen == [item]


def test_a_click_elsewhere_reaches_nothing(canvas):
    seen = []
    canvas.create_rectangle(0, 0, 4, 4, tags="hot")
    canvas.tag_bind("hot", "<Button-1>", lambda event: seen.append(1))
    click(canvas, 30, 16)
    assert seen == []


def test_a_binding_can_be_made_on_an_item_id(canvas):
    seen = []
    item = canvas.create_rectangle(0, 0, 8, 8, fill="white")
    canvas.tag_bind(item, "<Button-1>", lambda event: seen.append(1))
    click(canvas, 2, 2)
    assert seen == [1]


def test_the_topmost_item_gets_the_click(canvas):
    seen = []
    canvas.create_rectangle(0, 0, 8, 8, fill="white", tags="under")
    canvas.create_rectangle(0, 0, 8, 8, fill="white", tags="over")
    canvas.tag_bind("under", "<Button-1>", lambda event: seen.append("under"))
    canvas.tag_bind("over", "<Button-1>", lambda event: seen.append("over"))
    click(canvas, 2, 2)
    assert seen == ["over"]


def test_a_binding_on_all_reaches_every_item(canvas):
    seen = []
    canvas.create_rectangle(0, 0, 8, 8, fill="white")
    canvas.tag_bind("all", "<Button-1>", lambda event: seen.append(1))
    click(canvas, 2, 2)
    assert seen == [1]


def test_enter_and_leave_are_worked_out_from_movement(canvas):
    """A terminal never reports a pointer crossing an item; the canvas does."""
    seen = []
    canvas.create_rectangle(0, 0, 8, 8, fill="white", tags="hot")
    canvas.tag_bind("hot", "<Enter>", lambda event: seen.append("enter"))
    canvas.tag_bind("hot", "<Leave>", lambda event: seen.append("leave"))
    click(canvas, 2, 2, state="motion", button=0)
    click(canvas, 30, 16, state="motion", button=0)
    assert seen == ["enter", "leave"]


def test_the_current_item_is_the_one_under_the_pointer(canvas):
    item = canvas.create_rectangle(0, 0, 8, 8, fill="white")
    click(canvas, 2, 2, state="motion", button=0)
    assert canvas._current == item


def test_a_release_reaches_the_item(canvas):
    seen = []
    canvas.create_rectangle(0, 0, 8, 8, fill="white", tags="hot")
    canvas.tag_bind("hot", "<ButtonRelease-1>", lambda event: seen.append(1))
    click(canvas, 2, 2, state="released")
    assert seen == [1]


def test_two_bindings_can_be_added_to_one_event(canvas):
    seen = []
    canvas.create_rectangle(0, 0, 8, 8, fill="white", tags="hot")
    canvas.tag_bind("hot", "<Button-1>", lambda event: seen.append(1))
    canvas.tag_bind("hot", "<Button-1>", lambda event: seen.append(2), add=True)
    click(canvas, 2, 2)
    assert seen == [1, 2]


def test_a_binding_can_be_removed(canvas):
    seen = []
    canvas.create_rectangle(0, 0, 8, 8, fill="white", tags="hot")
    canvas.tag_bind("hot", "<Button-1>", lambda event: seen.append(1))
    canvas.tag_unbind("hot", "<Button-1>")
    click(canvas, 2, 2)
    assert seen == []


def test_a_hidden_item_takes_no_clicks(canvas):
    seen = []
    canvas.create_rectangle(0, 0, 8, 8, fill="white", tags="hot", state="hidden")
    canvas.tag_bind("hot", "<Button-1>", lambda event: seen.append(1))
    click(canvas, 2, 2)
    assert seen == []


def test_a_deleted_item_stops_being_current(canvas):
    canvas.create_rectangle(0, 0, 8, 8, fill="white", tags="hot")
    click(canvas, 2, 2, state="motion", button=0)
    canvas.delete("hot")
    assert canvas._current is None


# ----------------------------------------------------------------- the view


def test_canvasx_and_canvasy_convert_from_the_window(canvas):
    area = canvas._text_area()
    assert canvas.canvasx(area.x + 3) == 3
    # Two pixel rows to a cell row.
    assert canvas.canvasy(area.y + 2) == 4


def test_canvasx_takes_a_window_coordinate_wherever_the_canvas_is(root):
    """As event.x is: Tk 9.0 answers canvasx(10) = 10.0 for a canvas packed
    with padx=50, so canvasx(event.x) is the canvas point under the pointer.
    TkCurses-0n21."""
    widget = Canvas(root, width=20, height=5, relief="flat")
    widget._allocate(Rect(7, 4, 20, 5))
    widget._map()
    assert (widget.winfo_rootx(), widget.winfo_rooty()) == (7, 4)
    area = widget._text_area()
    assert widget.canvasx(area.x + 3) == 3
    assert widget.canvasy(area.y + 2) == 4


def test_canvasx_follows_the_view(canvas):
    canvas.configure(scrollregion=(0, 0, 200, 100))
    canvas.xview_moveto(0.5)
    canvas.yview_moveto(0.5)
    area = canvas._text_area()
    assert canvas.canvasx(area.x) == 100
    assert canvas.canvasy(area.y) == 50


def test_the_view_starts_at_the_origin(canvas):
    canvas.create_rectangle(0, 0, 80, 40)
    assert canvas.xview()[0] == 0.0
    assert canvas.yview()[0] == 0.0


def test_scrolling_moves_the_view(canvas):
    canvas.configure(scrollregion=(0, 0, 200, 100))
    canvas.xview_moveto(0.5)
    assert canvas._left == 100
    canvas.yview_moveto(0.5)
    assert canvas._top == 50


def test_the_vertical_view_stays_on_a_cell_boundary(canvas):
    """An odd offset would swap which half of a cell each pixel lands in."""
    canvas.configure(scrollregion=(0, 0, 200, 101))
    for fraction in (0.1, 0.3, 0.55, 0.77):
        canvas.yview_moveto(fraction)
        assert canvas._top % 2 == 0


def test_a_vertical_scroll_unit_is_a_cell(canvas):
    canvas.configure(scrollregion=(0, 0, 200, 100))
    canvas.yview_scroll(3, "units")
    assert canvas._top == 6


def test_the_view_never_leaves_the_scroll_region(canvas):
    canvas.configure(scrollregion=(0, 0, 50, 30))
    canvas.xview_moveto(1.0)
    canvas.yview_moveto(1.0)
    assert canvas._left <= 50
    assert canvas._top <= 30


def test_the_scroll_region_defaults_to_what_is_drawn(canvas):
    canvas.create_rectangle(10, 10, 30, 30)
    assert canvas._scroll_region() == (10, 10, 30, 30)


def test_a_bad_scroll_command_is_refused(canvas):
    with pytest.raises(TclError, match="moveto or scroll"):
        canvas.xview("sideways", 1)


def test_the_scrollcommand_is_told_where_the_view_is(canvas):
    seen = []
    canvas.configure(
        scrollregion=(0, 0, 200, 100),
        yscrollcommand=lambda first, last: seen.append((first, last)),
    )
    canvas.yview_moveto(0.25)
    assert seen
    assert 0.0 <= seen[-1][0] <= 1.0


def test_the_plane_is_twice_as_tall_in_pixels_as_in_cells(canvas):
    assert canvas._plane_size() == (40, 20)


def test_the_plane_is_sane_before_the_widget_is_laid_out(root):
    widget = Canvas(root, name="c", width=30, height=8)
    assert widget._plane_size() == (30, 16)


def test_a_canvas_asks_for_its_cells(root):
    widget = Canvas(root, name="c", width=30, height=8, relief="flat")
    assert widget.winfo_reqwidth() == 30
    assert widget.winfo_reqheight() == 8


def test_the_current_tag_names_what_the_pointer_is_over(canvas):
    """Tk's dynamic tag, which tag_bind's contract depends on."""
    item = canvas.create_rectangle(0, 0, 8, 8, fill="white")
    assert canvas.find_withtag("current") == ()
    click(canvas, 2, 2, state="motion", button=0)
    assert canvas.find_withtag("current") == (item,)
    click(canvas, 30, 16, state="motion", button=0)
    assert canvas.find_withtag("current") == ()


def test_a_binding_on_current_follows_the_pointer(canvas):
    seen = []
    first = canvas.create_rectangle(0, 0, 6, 6, fill="white")
    second = canvas.create_rectangle(20, 0, 26, 6, fill="white")
    canvas.tag_bind("current", "<Button-1>", lambda event: seen.append("hit"))
    click(canvas, 2, 2)
    click(canvas, 22, 2)
    assert seen == ["hit", "hit"]
    assert canvas.find_withtag("current") == (second,)
    assert first in canvas.find_all()


def test_a_centred_line_of_text_sits_on_the_cell_its_point_is_in(canvas):
    """Halving the block height in pixels first put it on the row above."""
    item = canvas.create_text(20, 10, text="MIDDLE", anchor="center")
    _, top, _, _ = canvas.bbox(item)
    assert top // 2 == 10 // 2


def test_a_block_of_text_centres_by_whole_rows(canvas):
    item = canvas.create_text(20, 10, text="one\ntwo", anchor="center")
    _, top, _, bottom = canvas.bbox(item)
    assert top // 2 == 10 // 2 - 1
    assert (bottom - top + 1) // 2 == 2


# ------------------------------------------------------- what counts as a hit


def test_clicking_inside_an_unfilled_shape_hits_nothing(canvas):
    """Tk tests an item's real shape, not its bounding box.

    An unfilled rectangle has nothing in its middle, so nothing is there to
    click - which is also what stops a thin diagonal claiming the whole
    rectangle its bounding box covers.
    """
    seen = []
    canvas.create_rectangle(0, 0, 12, 12, outline="white", tags="hot")
    canvas.tag_bind("hot", "<Button-1>", lambda event: seen.append(1))
    click(canvas, 6, 6)
    assert seen == []


def test_clicking_the_outline_of_an_unfilled_shape_hits_it(canvas):
    seen = []
    canvas.create_rectangle(0, 0, 12, 12, outline="white", tags="hot")
    canvas.tag_bind("hot", "<Button-1>", lambda event: seen.append(1))
    click(canvas, 0, 0)
    assert seen == [1]


def test_a_diagonal_does_not_claim_the_box_it_crosses(canvas):
    """Reported from UAT 24: clicking a square picked out the line across it.

    The line's bounding box is the whole square, so testing by extent gave
    it everything - including the exception that followed, because a line
    has no outline option to set.
    """
    box = canvas.create_rectangle(0, 0, 20, 20, fill="white", tags="box")
    line = canvas.create_line(0, 0, 20, 20, fill="red", tags="cross")
    # On the diagonal: the line, which is on top.
    assert canvas._item_at(10, 10) == line
    # Off it, but well inside the square: the square.
    assert canvas._item_at(3, 16) == box


def test_either_half_of_the_clicked_cell_counts(canvas):
    """A click names a cell; either of its two pixels may hold the ink."""
    line = canvas.create_line(0, 1, 10, 1, fill="white")
    assert canvas._item_at(4, 1) == line
    assert canvas._item_at(4, 0) == line


def test_a_click_just_off_a_thin_line_still_hits_it(canvas):
    """Tk's closeenough, which a terminal needs more than Tk does.

    An outline is one pixel wide and a click only names a whole cell, so
    demanding an exact hit makes thin shapes practically unclickable.
    """
    line = canvas.create_line(0, 4, 20, 4, fill="white")
    assert canvas._item_at(10, 4) == line
    assert canvas._item_at(10, 5) == line
    assert canvas._item_at(10, 9) is None


def test_closeenough_can_be_turned_off(canvas):
    canvas.configure(closeenough=0)
    line = canvas.create_line(0, 4, 20, 4, fill="white")
    assert canvas._item_at(10, 4) == line
    # Row 6 is a different cell entirely, and no longer within reach.
    assert canvas._item_at(10, 6) is None


def test_closeenough_can_be_widened(canvas):
    canvas.configure(closeenough=3)
    line = canvas.create_line(0, 4, 20, 4, fill="white")
    assert canvas._item_at(10, 7) == line  # three pixels away
    assert canvas._item_at(10, 12) is None  # eight, which is not


def test_the_tolerance_does_not_reach_across_the_canvas(canvas):
    canvas.create_line(0, 0, 4, 0, fill="white", tags="hot")
    assert canvas._item_at(30, 16) is None
