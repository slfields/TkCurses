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

"""Tests for the grid geometry manager.

The weight and sticky tests pin the rules the previous attempt got wrong:
sticky fills the cell rather than the container, and a cell only grows beyond
its natural size if its row or column has a weight.
"""

from __future__ import annotations

import re

import pytest

from tkcurses import Misc, TclError, Widget
from tkcurses._core.geometry import Rect, Size


class Box(Widget):
    """A widget that asks for a fixed size."""

    def __init__(self, master, name, width=10, height=2, **kw):
        super().__init__(master, name=name, **kw)
        self._requested = Size(width, height)


@pytest.fixture
def root():
    root = Misc()
    root._rect = Rect(0, 0, 40, 12)
    root._mapped = True
    return root


def geometry(widget):
    return (
        widget.winfo_x(),
        widget.winfo_y(),
        widget.winfo_width(),
        widget.winfo_height(),
    )


# ------------------------------------------------------------------ placing


def test_a_single_child_sits_at_the_origin(root):
    box = Box(root, "a", width=10, height=2)
    box.grid()
    root.update_layout()
    assert geometry(box) == (0, 0, 10, 2)


def test_children_are_placed_by_row_and_column(root):
    first = Box(root, "a", width=10, height=2)
    second = Box(root, "b", width=10, height=2)
    first.grid(row=0, column=0)
    second.grid(row=1, column=1)
    root.update_layout()
    assert first.winfo_x() == 0 and first.winfo_y() == 0
    assert second.winfo_x() == 10 and second.winfo_y() == 2


def test_a_column_is_as_wide_as_its_widest_child(root):
    Box(root, "a", width=6, height=1).grid(row=0, column=0)
    Box(root, "b", width=14, height=1).grid(row=1, column=0)
    right = Box(root, "c", width=5, height=1)
    right.grid(row=0, column=1)
    root.update_layout()
    assert right.winfo_x() == 14


def test_a_row_is_as_tall_as_its_tallest_child(root):
    Box(root, "a", width=5, height=3).grid(row=0, column=0)
    below = Box(root, "b", width=5, height=1)
    below.grid(row=1, column=0)
    root.update_layout()
    assert below.winfo_y() == 3


def test_an_empty_row_still_takes_its_place(root):
    """A child at row 2 leaves rows 0 and 1 in the grid, however empty."""
    box = Box(root, "a", height=2)
    box.grid(row=2, column=0)
    root.update_layout()
    assert root.grid_size() == (1, 3)


# -------------------------------------------------------------------- sticky


def test_without_sticky_a_child_is_centred_in_its_cell(root):
    root.grid_columnconfigure(0, weight=1)
    box = Box(root, "a", width=10, height=2)
    box.grid(row=0, column=0)
    root.update_layout()
    assert box.winfo_width() == 10
    assert box.winfo_x() == (40 - 10) // 2


def test_sticky_ew_stretches_across_the_cell(root):
    root.grid_columnconfigure(0, weight=1)
    box = Box(root, "a", width=10, height=2)
    box.grid(row=0, column=0, sticky="ew")
    root.update_layout()
    assert box.winfo_width() == 40


def test_sticky_ns_stretches_down_the_cell(root):
    root.grid_rowconfigure(0, weight=1)
    box = Box(root, "a", width=10, height=2)
    box.grid(row=0, column=0, sticky="ns")
    root.update_layout()
    assert box.winfo_height() == 12


def test_sticky_nsew_stretches_both_ways(root):
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    box = Box(root, "a", width=4, height=1)
    box.grid(row=0, column=0, sticky="nsew")
    root.update_layout()
    assert geometry(box) == (0, 0, 40, 12)


def test_sticky_w_aligns_without_stretching(root):
    root.grid_columnconfigure(0, weight=1)
    box = Box(root, "a", width=10, height=2)
    box.grid(row=0, column=0, sticky="w")
    root.update_layout()
    assert (box.winfo_x(), box.winfo_width()) == (0, 10)


def test_sticky_e_aligns_to_the_far_side(root):
    root.grid_columnconfigure(0, weight=1)
    box = Box(root, "a", width=10, height=2)
    box.grid(row=0, column=0, sticky="e")
    root.update_layout()
    assert box.winfo_x() == 40 - 10


def test_sticky_without_weight_does_nothing_visible(root):
    """The rule most often missed: sticky fills the cell, weight grows it."""
    box = Box(root, "a", width=10, height=2)
    box.grid(row=0, column=0, sticky="ew")
    root.update_layout()
    assert box.winfo_width() == 10


# -------------------------------------------------------------------- weight


def test_a_weighted_column_takes_the_leftover_space(root):
    root.grid_columnconfigure(0, weight=1)
    box = Box(root, "a", width=10, height=2)
    box.grid(row=0, column=0, sticky="ew")
    root.update_layout()
    assert box.winfo_width() == 40


def test_leftover_space_is_split_by_weight(root):
    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=3)
    first = Box(root, "a", width=4, height=2)
    second = Box(root, "b", width=4, height=2)
    first.grid(row=0, column=0, sticky="ew")
    second.grid(row=0, column=1, sticky="ew")
    root.update_layout()
    assert first.winfo_width() + second.winfo_width() == 40
    assert second.winfo_width() > first.winfo_width()


def test_an_unweighted_column_keeps_its_natural_size(root):
    root.grid_columnconfigure(1, weight=1)
    fixed = Box(root, "a", width=6, height=2)
    growing = Box(root, "b", width=6, height=2)
    fixed.grid(row=0, column=0, sticky="ew")
    growing.grid(row=0, column=1, sticky="ew")
    root.update_layout()
    assert fixed.winfo_width() == 6
    assert growing.winfo_width() == 34


def test_minsize_holds_a_column_open(root):
    root.grid_columnconfigure(0, minsize=20)
    box = Box(root, "a", width=4, height=2)
    right = Box(root, "b", width=4, height=2)
    box.grid(row=0, column=0)
    right.grid(row=0, column=1)
    root.update_layout()
    assert right.winfo_x() == 20


def test_line_configuration_reads_back(root):
    root.grid_columnconfigure(0, weight=2, minsize=5)
    config = root.grid_columnconfigure(0)
    assert config["weight"] == 2
    assert config["minsize"] == 5


def test_uniform_columns_are_kept_in_proportion(root):
    root.grid_columnconfigure(0, weight=1, uniform="a")
    root.grid_columnconfigure(1, weight=1, uniform="a")
    first = Box(root, "a", width=4, height=2)
    second = Box(root, "b", width=20, height=2)
    first.grid(row=0, column=0, sticky="ew")
    second.grid(row=0, column=1, sticky="ew")
    root.update_layout()
    assert first.winfo_width() == second.winfo_width()


# --------------------------------------------------------------------- span


def test_a_child_can_span_columns(root):
    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=1)
    Box(root, "a", width=8, height=1).grid(row=0, column=0, sticky="ew")
    Box(root, "b", width=8, height=1).grid(row=0, column=1, sticky="ew")
    wide = Box(root, "c", width=4, height=1)
    wide.grid(row=1, column=0, columnspan=2, sticky="ew")
    root.update_layout()
    assert wide.winfo_width() == 40


def test_a_child_can_span_rows(root):
    root.grid_rowconfigure(0, weight=1)
    root.grid_rowconfigure(1, weight=1)
    tall = Box(root, "a", width=4, height=1)
    tall.grid(row=0, column=0, rowspan=2, sticky="ns")
    root.update_layout()
    assert tall.winfo_height() == 12


def test_a_spanning_child_widens_the_columns_it_needs(root):
    """Its shortfall is spread over the span, not loaded onto one column.

    Column 1 already holds a child two wide and column 0 holds nothing, so
    the span's 18 cells of shortfall are split nine each: the columns end up
    9 and 11, not 10 and 10. What is spread is what is missing, which leaves
    the column that already had content the wider of the two.
    """
    wide = Box(root, "a", width=20, height=1)
    wide.grid(row=0, column=0, columnspan=2)
    below = Box(root, "b", width=2, height=1)
    below.grid(row=1, column=1, sticky="w")
    root.update_layout()
    assert below.winfo_x() == 9
    assert wide.winfo_width() == 20


def test_a_spanning_child_does_not_widen_columns_that_already_fit(root):
    Box(root, "a", width=10, height=1).grid(row=0, column=0)
    Box(root, "b", width=10, height=1).grid(row=0, column=1)
    wide = Box(root, "c", width=6, height=1)
    wide.grid(row=1, column=0, columnspan=2, sticky="w")
    root.update_layout()
    assert root.grid_bbox(0, 0)[2] == 10


# ------------------------------------------------------------------ padding


def test_padx_leaves_space_inside_the_cell(root):
    root.grid_columnconfigure(0, weight=1)
    box = Box(root, "a", width=10, height=2)
    box.grid(row=0, column=0, sticky="ew", padx=3)
    root.update_layout()
    assert (box.winfo_x(), box.winfo_width()) == (3, 34)


def test_ipadx_grows_the_widget(root):
    box = Box(root, "a", width=10, height=2)
    box.grid(row=0, column=0, ipadx=2)
    root.update_layout()
    assert box.winfo_width() == 14


def test_an_asymmetric_padx_pads_one_side_of_the_cell(root):
    """``padx=(0, 3)`` keeps the widget against the left of its cell.

    The three cells come off the right instead, where ``padx=3`` would have
    taken three from each side. TkCurses-l8f wanted exactly this, for a caption
    needing one cell of clearance on its right only.
    """
    root.grid_columnconfigure(0, weight=1)
    box = Box(root, "a", width=10, height=2)
    box.grid(row=0, column=0, sticky="ew", padx=(0, 3))
    root.update_layout()
    assert (box.winfo_x(), box.winfo_width()) == (0, 37)


def test_the_near_side_of_an_asymmetric_padx_moves_the_widget(root):
    root.grid_columnconfigure(0, weight=1)
    box = Box(root, "a", width=10, height=2)
    box.grid(row=0, column=0, sticky="ew", padx=(3, 0))
    root.update_layout()
    assert (box.winfo_x(), box.winfo_width()) == (3, 37)


def test_an_asymmetric_pady_pads_the_bottom_without_moving_the_top(root):
    root.grid_rowconfigure(0, weight=1)
    box = Box(root, "a", width=10, height=2)
    box.grid(row=0, column=0, sticky="ns", pady=(0, 4))
    root.update_layout()
    assert (box.winfo_y(), box.winfo_height()) == (0, 8)


def test_an_asymmetric_pad_widens_the_column_by_its_total(root):
    """A pair contributes left plus right, not twice either half."""
    Box(root, "a", width=10, height=2).grid(row=0, column=0, padx=(1, 3))
    right = Box(root, "b", width=4, height=2)
    right.grid(row=0, column=1)
    root.update_layout()
    assert right.winfo_x() == 14


def test_padding_widens_the_column(root):
    Box(root, "a", width=10, height=2).grid(row=0, column=0, padx=2)
    right = Box(root, "b", width=4, height=2)
    right.grid(row=0, column=1)
    root.update_layout()
    assert right.winfo_x() == 14


# ------------------------------------------------------- forget and remove


def test_forget_takes_a_child_out_and_forgets_where_it_was(root):
    box = Box(root, "a", height=2)
    box.grid(row=3, column=2)
    box.grid_forget()
    box.grid()
    root.update_layout()
    assert box.grid_info()["row"] == 0
    assert box.grid_info()["column"] == 0


def test_remove_keeps_the_position_for_later(root):
    box = Box(root, "a", height=2)
    box.grid(row=3, column=2, sticky="ew")
    box.grid_remove()
    assert root.grid_slaves() == []
    box.grid()
    assert box.grid_info()["row"] == 3
    assert box.grid_info()["column"] == 2
    assert box.grid_info()["sticky"] == "ew"


def test_removing_unmaps_the_widget(root):
    box = Box(root, "a")
    box.grid()
    box.grid_remove()
    assert not box.winfo_ismapped()


def test_forgetting_something_ungridded_is_harmless(root):
    Box(root, "a").grid_forget()


# ------------------------------------------------------------------ queries


def test_grid_size_reports_columns_and_rows(root):
    Box(root, "a").grid(row=0, column=0)
    Box(root, "b").grid(row=2, column=3)
    assert root.grid_size() == (4, 3)


def test_grid_slaves_lists_the_children(root):
    first = Box(root, "a")
    second = Box(root, "b")
    first.grid(row=0, column=0)
    second.grid(row=1, column=0)
    assert root.grid_slaves() == [first, second]


def test_grid_slaves_can_be_narrowed_to_a_row(root):
    first = Box(root, "a")
    second = Box(root, "b")
    first.grid(row=0, column=0)
    second.grid(row=1, column=0)
    assert root.grid_slaves(row=1) == [second]


def test_grid_slaves_can_be_narrowed_to_a_column(root):
    first = Box(root, "a")
    second = Box(root, "b")
    first.grid(row=0, column=0)
    second.grid(row=0, column=1)
    assert root.grid_slaves(column=1) == [second]


def test_grid_bbox_reports_a_cells_region(root):
    Box(root, "a", width=10, height=2).grid(row=0, column=0)
    Box(root, "b", width=6, height=3).grid(row=1, column=1)
    root.update_layout()
    assert root.grid_bbox(1, 1) == (10, 2, 6, 3)


def test_grid_location_finds_the_cell_at_a_position(root):
    Box(root, "a", width=10, height=2).grid(row=0, column=0)
    Box(root, "b", width=6, height=3).grid(row=1, column=1)
    root.update_layout()
    assert root.grid_location(12, 3) == (1, 1)


def test_grid_location_outside_the_grid_reports_nothing(root):
    Box(root, "a", width=4, height=1).grid(row=0, column=0)
    root.update_layout()
    assert root.grid_location(39, 11) == (-1, -1)


def test_grid_info_reports_the_options(root):
    box = Box(root, "a")
    box.grid(row=2, column=1, columnspan=3, sticky="nw", padx=1)
    info = box.grid_info()
    assert info["row"] == 2
    assert info["columnspan"] == 3
    assert info["sticky"] == "nw"
    assert info["in"] is root


def test_grid_info_on_an_ungridded_widget_is_refused(root):
    with pytest.raises(TclError, match="not gridded"):
        Box(root, "a").grid_info()


def test_gridding_marks_the_widget_as_managed(root):
    box = Box(root, "a")
    box.grid()
    assert box.winfo_manager() == "grid"
    assert box.winfo_ismapped()


# ------------------------------------------------------------------- anchor


def test_the_grid_sits_at_the_top_left_by_default(root):
    box = Box(root, "a", width=10, height=2)
    box.grid()
    root.update_layout()
    assert (box.winfo_x(), box.winfo_y()) == (0, 0)


def test_the_grid_can_be_centred_in_its_container(root):
    root.grid_anchor("center")
    box = Box(root, "a", width=10, height=2)
    box.grid()
    root.update_layout()
    assert box.winfo_x() == (40 - 10) // 2


def test_the_grid_can_be_anchored_to_the_far_side(root):
    root.grid_anchor("se")
    box = Box(root, "a", width=10, height=2)
    box.grid()
    root.update_layout()
    assert (box.winfo_x(), box.winfo_y()) == (30, 10)


# --------------------------------------------------------- container fit


def test_a_container_asks_for_what_the_grid_needs(root):
    frame = Widget(root, name="frame")
    Box(frame, "a", width=10, height=2).grid(row=0, column=0)
    Box(frame, "b", width=6, height=3).grid(row=1, column=1)
    root.update_layout()
    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (16, 5)


# ---------------------------------------------------------------- validation


def test_a_bad_sticky_value_is_refused(root):
    with pytest.raises(TclError, match="sticky"):
        Box(root, "a").grid(sticky="up")


def test_an_unknown_option_is_refused(root):
    with pytest.raises(TclError, match="unknown option"):
        Box(root, "a").grid(nonsense=1)


def test_a_bad_row_value_is_refused(root):
    with pytest.raises(TclError, match="integer"):
        Box(root, "a").grid(row="first")


def test_a_span_is_at_least_one(root):
    box = Box(root, "a")
    box.grid(columnspan=0)
    assert box.grid_info()["columnspan"] == 1


def test_mixing_managers_in_one_container_is_refused(root):
    # Tk 9.0.2's wording, measured.
    Box(root, "a").pack()
    with pytest.raises(TclError) as raised:
        Box(root, "b").grid()
    assert str(raised.value) == (
        'cannot use geometry manager "grid" inside ".": '
        "pack is already managing its content windows"
    )


def test_mixing_the_other_way_round_is_refused_too(root):
    Box(root, "a").grid()
    with pytest.raises(TclError) as raised:
        Box(root, "b").pack()
    assert str(raised.value) == (
        'cannot use geometry manager "pack" inside ".": '
        "grid is already managing its content windows"
    )


def test_a_container_whose_packing_is_over_can_be_gridded(root):
    """Measured on Tk 9.0.2: the refusal lasts only while pack has a child."""
    first = Box(root, "a")
    first.pack()
    first.pack_forget()
    second = Box(root, "b")
    second.grid(row=0, column=0)
    assert root.grid_slaves() == [second]
    root.update_layout()
    assert geometry(second) == (0, 0, 10, 2)


# ------------------------------------------------- reconfiguring one option


def test_configuring_one_option_leaves_the_others_alone(root):
    """Tk merges a reconfigure into what the widget already has.

    Values checked against Tk 9.0.2: a widget gridded at row=2, column=3
    with sticky="ew", padx=5 and rowspan=2, then grid_configure(column=1),
    keeps the row, the sticky, the padding and the span. Ours rebuilt the
    options from scratch and sent it to row 0 with no sticky at all.
    """
    box = Box(root, "b")
    box.grid(row=2, column=3, sticky="ew", padx=5, rowspan=2)
    box.grid_configure(column=1)
    info = box.grid_info()
    assert (info["row"], info["column"]) == (2, 1)
    assert info["sticky"] == "ew"
    assert info["padx"] == 5
    assert info["rowspan"] == 2


def test_grid_is_grid_configure_so_a_second_grid_merges_too(root):
    box = Box(root, "b")
    box.grid(row=1, column=1, columnspan=3, pady=4)
    box.grid(sticky="ns")
    info = box.grid_info()
    assert (info["row"], info["column"]) == (1, 1)
    assert info["columnspan"] == 3
    assert info["pady"] == 4
    assert info["sticky"] == "ns"


def test_forgetting_is_what_brings_the_defaults_back(root):
    """Tk 9.0.2 after grid_forget(): row=0, column=0, sticky="", padx=0,
    rowspan=1."""
    box = Box(root, "b")
    box.grid(row=2, column=3, sticky="ew", padx=5, rowspan=2)
    box.grid_forget()
    box.grid()
    info = box.grid_info()
    assert (info["row"], info["column"]) == (0, 0)
    assert info["sticky"] == ""
    assert info["padx"] == 0
    assert info["rowspan"] == 1


def test_grid_remove_still_puts_the_widget_back_where_it_was(root):
    """The one case that already merged, and must keep doing so.

    grid_remove hides a widget and remembers where it was; a bare grid()
    afterwards restores it. That is a different question from reconfiguring
    a widget that is still gridded, and both now go through the same merge.
    """
    box = Box(root, "b")
    box.grid(row=3, column=2, sticky="nsew", padx=6)
    box.grid_remove()
    box.grid()
    info = box.grid_info()
    assert (info["row"], info["column"]) == (3, 2)
    assert info["sticky"] == "nsew"
    assert info["padx"] == 6


def test_a_bad_option_in_a_reconfigure_leaves_the_widget_as_it_was(root):
    box = Box(root, "b")
    box.grid(row=2, column=3, sticky="ew")
    with pytest.raises(TclError):
        box.grid_configure(column="sideways")
    info = box.grid_info()
    assert (info["row"], info["column"], info["sticky"]) == (2, 3, "ew")


# ----------------------------------------------------- gridding somewhere else


def test_in_moves_the_widget_out_of_its_old_container(root):
    first = Box(root, "first", width=20, height=6)
    second = Box(root, "second", width=20, height=6)
    box = Box(root, "b")
    box.grid(in_=first, row=1, column=2, sticky="ew")
    assert first.grid_slaves() == [box]

    box.grid_configure(in_=second)
    assert first.grid_slaves() == []
    assert second.grid_slaves() == [box]


def test_moving_to_another_container_keeps_the_options(root):
    first = Box(root, "first", width=20, height=6)
    second = Box(root, "second", width=20, height=6)
    box = Box(root, "b")
    box.grid(in_=first, row=1, column=2, sticky="ew", padx=3)
    box.grid_configure(in_=second)
    info = box.grid_info()
    assert (info["row"], info["column"]) == (1, 2)
    assert (info["sticky"], info["padx"]) == ("ew", 3)


def test_grid_info_names_the_container_doing_the_work(root):
    holder = Box(root, "holder", width=20, height=6)
    box = Box(root, "b")
    box.grid(in_=holder, row=1)
    assert box.grid_info()["in"] is holder


def test_forgetting_removes_it_from_the_container_that_held_it(root):
    holder = Box(root, "holder", width=20, height=6)
    box = Box(root, "b")
    box.grid(in_=holder, row=1)
    box.grid_forget()
    assert holder.grid_slaves() == []
    assert box.winfo_manager() == ""


# ------------------------------------------------- several lines at once
#
# Tk's grid rowconfigure and columnconfigure take a list of indices, "all"
# or a gridded child, as tkinter passes them. Every expectation here was
# measured on Tk 9.0.2 through tkinter. TkCurses-2lg5: a tuple was kept as
# one index, and every layout pass then raised TypeError.


@pytest.fixture
def spanning(root):
    """A child across columns 1-2 and one in row 2, column 4."""
    wide = Box(root, "wide")
    wide.grid(row=0, column=1, columnspan=2)
    low = Box(root, "low")
    low.grid(row=2, column=4)
    return wide, low


def weights(root, axis, count):
    read = root.grid_columnconfigure if axis == "column" else root.grid_rowconfigure
    return tuple(read(index, "weight") for index in range(count))


def test_a_tuple_of_columns_configures_each_and_lays_out(root):
    root.columnconfigure((0, 1), weight=1)
    assert weights(root, "column", 3) == (1, 1, 0)
    a = Box(root, "a", width=4)
    a.grid(row=0, column=0, sticky="ew")
    b = Box(root, "b", width=4)
    b.grid(row=0, column=1, sticky="ew")
    root.update_layout()
    # Laid out: the two weighted columns share the 40 cells evenly.
    assert a.winfo_width() == b.winfo_width() == 20


def test_a_list_and_a_tcl_list_string_are_indices_too(root):
    root.columnconfigure([3, 5], weight=2)
    root.columnconfigure("6 {7}", weight=3)
    assert weights(root, "column", 8) == (0, 0, 0, 2, 0, 2, 3, 3)


def test_all_is_every_line_a_gridded_child_occupies(root, spanning):
    root.columnconfigure("all", weight=4)
    assert weights(root, "column", 6) == (0, 4, 4, 0, 4, 0)
    root.rowconfigure("all", weight=5)
    assert weights(root, "row", 3) == (5, 0, 5)


def test_a_child_names_the_lines_it_spans(root, spanning):
    wide, low = spanning
    root.columnconfigure(wide, minsize=9)
    assert [root.grid_columnconfigure(i, "minsize") for i in range(4)] == [0, 9, 9, 0]
    root.rowconfigure(str(low), pad=5)
    assert [root.grid_rowconfigure(i, "pad") for i in range(4)] == [0, 0, 5, 0]


@pytest.mark.parametrize(
    ("index", "message"),
    [
        ((), "no column indices specified"),
        (-1, '"-1" is out of range'),
        (10000, '"10000" is out of range'),
        ("foo", 'illegal index "foo"'),
        ("ALL", 'illegal index "ALL"'),
        ("1.5", 'illegal index "1.5"'),
        (2.0, 'illegal index "2.0"'),
        (".nope", 'illegal index ".nope"'),
    ],
)
def test_an_index_tk_refuses_is_refused_in_its_words(root, index, message):
    with pytest.raises(TclError, match=f"^{re.escape(message)}$"):
        root.columnconfigure(index, weight=1)


def test_a_child_gridded_elsewhere_is_not_an_index(root):
    elsewhere = Box(root, "elsewhere")
    elsewhere.place(x=0, y=0)
    with pytest.raises(TclError, match=r'^the window "\.elsewhere" is not managed by'):
        root.columnconfigure(elsewhere, weight=1)


def test_the_row_axis_says_row(root):
    with pytest.raises(TclError, match=r"^no row indices specified$"):
        root.rowconfigure([], weight=1)


def test_an_index_is_read_as_tcl_reads_an_integer(root):
    root.columnconfigure(" 3 ", weight="0x10")
    root.columnconfigure(True, weight=True)
    assert weights(root, "column", 4) == (0, 1, 0, 16)


def test_the_lines_before_an_error_stay_configured(root):
    with pytest.raises(TclError, match='illegal index "foo"'):
        root.columnconfigure((9, "foo"), weight=7)
    with pytest.raises(TclError, match='bad option "-bogus"'):
        root.columnconfigure((22, 23), weight=5, bogus=1)
    assert weights(root, "column", 24)[9] == 7
    assert weights(root, "column", 24)[22:] == (5, 0)


def test_reading_takes_one_integer(root, spanning):
    wide, _ = spanning
    with pytest.raises(TclError, match=r"^must specify a single element on retrieval$"):
        root.columnconfigure((0, 1))
    for index in ("all", wide):
        with pytest.raises(TclError, match="only integer indices are allowed"):
            root.columnconfigure(index, "weight")
    assert root.columnconfigure((0,), "weight") == 0
    # Out of range answers the defaults when reading.
    assert root.columnconfigure(-1) == {
        "minsize": 0,
        "pad": 0,
        "uniform": None,
        "weight": 0,
    }


def test_options_are_named_and_checked_as_tk_does(root):
    with pytest.raises(TclError, match=r'^bad option "-bogus": must be -minsize'):
        root.columnconfigure(0, bogus=1)
    root.columnconfigure(0, wei=6)
    assert root.columnconfigure(0, "wei") == 6
    with pytest.raises(TclError, match=r'^expected integer but got "1.5"$'):
        root.columnconfigure(0, weight=1.5)
    for option in ("weight", "pad"):
        with pytest.raises(TclError, match=f'^invalid arg "-{option}": should be'):
            root.columnconfigure(0, **{option: -3})
    with pytest.raises(TclError, match=r'^expected screen distance but got "x"$'):
        root.columnconfigure(0, pad="x")
    root.columnconfigure(0, uniform="")
    assert root.columnconfigure(0, "uniform") is None


def test_a_negative_minsize_is_kept_and_laid_out_as_tk_lays_it_out(root):
    # Measured on Tk 9.0.2: an empty column of minsize -30 is -30 wide, so
    # the next column starts at -30 and its child is pushed past the left
    # edge; grid_bbox says the same.
    root.columnconfigure(0, minsize=-3)
    assert root.columnconfigure(0, "minsize") == -3
    child = Box(root, "a", width=4, height=1)
    child.grid(row=0, column=1)
    root.update_layout()
    assert child.winfo_x() == -3
    assert root.grid_bbox(0, 0) == (0, 0, -3, 1)
