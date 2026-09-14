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

"""Tests for the pack geometry manager.

Several of these pin semantics the previous attempt at this library got wrong
and had to correct later: fill stretches a widget to its parcel rather than to
the container, expand is what claims leftover space, and the default anchor
centres a widget in its parcel.
"""

from __future__ import annotations

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
    """A widget's region as ``(x, y, width, height)``, relative to its master."""
    return (
        widget.winfo_x(),
        widget.winfo_y(),
        widget.winfo_width(),
        widget.winfo_height(),
    )


# --------------------------------------------------------------------- sides


def test_packing_on_top_takes_a_slice_off_the_top(root):
    box = Box(root, "a", width=10, height=2)
    box.pack()
    root.update_layout()
    assert geometry(box) == (15, 0, 10, 2)


def test_a_parcel_spans_the_cavity_across_its_axis(root):
    """A widget packed on top gets the full width to sit in, not its own."""
    box = Box(root, "a", width=10, height=2)
    box.pack(fill="x")
    root.update_layout()
    assert geometry(box) == (0, 0, 40, 2)


def test_packing_on_the_bottom_takes_a_slice_off_the_bottom(root):
    box = Box(root, "a", height=3)
    box.pack(side="bottom")
    root.update_layout()
    assert box.winfo_y() == 12 - 3


def test_packing_on_the_left_takes_a_slice_off_the_left(root):
    box = Box(root, "a", width=8)
    box.pack(side="left")
    root.update_layout()
    assert box.winfo_x() == 0


def test_packing_on_the_right_takes_a_slice_off_the_right(root):
    box = Box(root, "a", width=8)
    box.pack(side="right")
    root.update_layout()
    assert box.winfo_x() == 40 - 8


def test_children_stack_in_packing_order(root):
    first = Box(root, "a", height=2)
    second = Box(root, "b", height=3)
    first.pack()
    second.pack()
    root.update_layout()
    assert first.winfo_y() == 0
    assert second.winfo_y() == 2


def test_a_left_packed_child_does_not_share_a_row_with_a_top_packed_one(root):
    """Packing order carves the cavity; side alone does not put them together.

    The second child's parcel is everything left below the first, and the
    default anchor centres the child in it - so it lands at 6, not 2. Pinned
    because it is the semantics the previous attempt got wrong: a parcel is
    not the same shape as the widget in it.
    """
    top = Box(root, "a", height=2)
    left = Box(root, "b", width=6, height=2)
    top.pack(side="top")
    left.pack(side="left")
    root.update_layout()
    assert top.winfo_y() == 0
    assert left.winfo_y() == 2 + (10 - 2) // 2


def test_the_parcel_below_a_top_packed_child_starts_where_it_ended(root):
    """Anchoring north shows where the parcel itself begins."""
    top = Box(root, "a", height=2)
    left = Box(root, "b", width=6, height=2)
    top.pack(side="top")
    left.pack(side="left", anchor="n")
    root.update_layout()
    assert left.winfo_y() == 2


# ---------------------------------------------------------------------- fill


def test_fill_x_stretches_to_the_parcel_width(root):
    box = Box(root, "a", width=10, height=2)
    box.pack(fill="x")
    root.update_layout()
    assert box.winfo_width() == 40


def test_fill_y_stretches_a_side_packed_widget_down_the_cavity(root):
    box = Box(root, "a", width=8, height=2)
    box.pack(side="left", fill="y")
    root.update_layout()
    assert geometry(box) == (0, 0, 8, 12)


def test_fill_both_stretches_in_both_directions(root):
    box = Box(root, "a", width=4, height=1)
    box.pack(fill="both")
    root.update_layout()
    assert geometry(box) == (0, 0, 40, 1)


def test_fill_does_not_claim_space_beyond_the_parcel(root):
    """fill stretches to the parcel, not to the container: expand does that."""
    first = Box(root, "a", height=2)
    second = Box(root, "b", height=2)
    first.pack(fill="both")
    second.pack(fill="both")
    root.update_layout()
    assert first.winfo_height() == 2
    assert second.winfo_height() == 2


# -------------------------------------------------------------------- expand


def test_expand_claims_the_leftover_space(root):
    box = Box(root, "a", height=2)
    box.pack(expand=True, fill="both")
    root.update_layout()
    assert box.winfo_height() == 12


def test_leftover_space_is_shared_between_expanding_children(root):
    first = Box(root, "a", height=2)
    second = Box(root, "b", height=2)
    first.pack(expand=True, fill="both")
    second.pack(expand=True, fill="both")
    root.update_layout()
    assert first.winfo_height() == second.winfo_height() == 6


def test_an_odd_leftover_gives_the_extra_cell_to_the_first(root):
    root._rect = Rect(0, 0, 40, 11)
    first = Box(root, "a", height=2)
    second = Box(root, "b", height=2)
    first.pack(expand=True, fill="both")
    second.pack(expand=True, fill="both")
    root.update_layout()
    assert first.winfo_height() == 6
    assert second.winfo_height() == 5
    assert first.winfo_height() + second.winfo_height() == 11


def test_a_child_that_does_not_expand_keeps_its_size(root):
    fixed = Box(root, "a", height=2)
    growing = Box(root, "b", height=2)
    fixed.pack()
    growing.pack(expand=True, fill="both")
    root.update_layout()
    assert fixed.winfo_height() == 2
    assert growing.winfo_height() == 10


def test_expanding_without_fill_moves_rather_than_stretches(root):
    """The parcel grows; without fill the widget only recentres inside it."""
    box = Box(root, "a", height=2)
    box.pack(expand=True)
    root.update_layout()
    assert box.winfo_height() == 2
    assert box.winfo_y() == (12 - 2) // 2


# -------------------------------------------------------------------- anchor


def test_the_default_anchor_centres_the_widget_in_its_parcel(root):
    box = Box(root, "a", width=10, height=2)
    box.pack()
    root.update_layout()
    assert box.winfo_x() == (40 - 10) // 2


@pytest.mark.parametrize(
    ("anchor", "x"),
    [("w", 0), ("center", 15), ("e", 30), ("nw", 0), ("se", 30)],
)
def test_the_anchor_places_the_widget_across_its_parcel(root, anchor, x):
    box = Box(root, "a", width=10, height=2)
    box.pack(anchor=anchor)
    root.update_layout()
    assert box.winfo_x() == x


def test_the_anchor_places_the_widget_down_its_parcel(root):
    box = Box(root, "a", width=10, height=2)
    box.pack(side="left", anchor="s")
    root.update_layout()
    assert box.winfo_y() == 12 - 2


# ------------------------------------------------------------------ padding


def test_padx_leaves_space_either_side_inside_the_parcel(root):
    box = Box(root, "a", width=10, height=2)
    box.pack(fill="x", padx=3)
    root.update_layout()
    assert geometry(box) == (3, 0, 34, 2)


def test_pady_leaves_space_above_and_below(root):
    box = Box(root, "a", height=2)
    box.pack(pady=2)
    root.update_layout()
    assert box.winfo_y() == 2


def test_ipadx_grows_the_widget_itself(root):
    box = Box(root, "a", width=10, height=2)
    box.pack(ipadx=2)
    root.update_layout()
    assert box.winfo_width() == 14


def test_ipady_grows_the_widget_itself(root):
    box = Box(root, "a", width=10, height=2)
    box.pack(ipady=1)
    root.update_layout()
    assert box.winfo_height() == 4


def test_padding_is_taken_out_of_the_next_childs_cavity(root):
    first = Box(root, "a", height=2)
    second = Box(root, "b", height=2)
    first.pack(pady=1)
    second.pack()
    root.update_layout()
    assert second.winfo_y() == 4


# ----------------------------------------------------------------- ordering


def test_before_moves_a_child_earlier_in_the_order(root):
    first = Box(root, "a", height=2)
    second = Box(root, "b", height=2)
    first.pack()
    second.pack()
    second.pack(before=first)
    root.update_layout()
    assert second.winfo_y() == 0
    assert first.winfo_y() == 2


def test_after_moves_a_child_later_in_the_order(root):
    first = Box(root, "a", height=2)
    second = Box(root, "b", height=2)
    first.pack()
    second.pack()
    first.pack(after=second)
    root.update_layout()
    assert second.winfo_y() == 0
    assert first.winfo_y() == 2


def test_repacking_keeps_a_childs_place(root):
    first = Box(root, "a", height=2)
    second = Box(root, "b", height=2)
    first.pack()
    second.pack()
    first.pack(fill="x")
    root.update_layout()
    assert first.winfo_y() == 0
    assert first.winfo_width() == 40


def test_pack_slaves_reports_the_packing_order(root):
    first = Box(root, "a")
    second = Box(root, "b")
    first.pack()
    second.pack()
    assert root.pack_slaves() == [first, second]


def test_a_container_with_nothing_packed_has_no_slaves(root):
    assert root.pack_slaves() == []


# ------------------------------------------------------------------- forget


def test_forgetting_removes_a_child_from_the_layout(root):
    first = Box(root, "a", height=2)
    second = Box(root, "b", height=2)
    first.pack()
    second.pack()
    first.pack_forget()
    root.update_layout()
    assert root.pack_slaves() == [second]
    assert second.winfo_y() == 0


def test_forgetting_unmaps_the_widget(root):
    box = Box(root, "a")
    box.pack()
    box.pack_forget()
    assert not box.winfo_ismapped()
    assert box.winfo_manager() == ""


def test_forgetting_something_unpacked_is_harmless(root):
    Box(root, "a").pack_forget()


def test_packing_again_after_forgetting_starts_from_the_defaults(root):
    box = Box(root, "a", width=10, height=2)
    box.pack(fill="x")
    box.pack_forget()
    box.pack()
    root.update_layout()
    assert box.winfo_width() == 10


# --------------------------------------------------------------------- info


def test_pack_info_reports_the_options(root):
    box = Box(root, "a")
    box.pack(side="left", fill="y", expand=True, padx=2)
    info = box.pack_info()
    assert info["side"] == "left"
    assert info["fill"] == "y"
    assert info["expand"] is True
    assert info["padx"] == 2
    assert info["in"] is root


def test_pack_info_on_an_unpacked_widget_is_refused(root):
    with pytest.raises(TclError, match="not packed"):
        Box(root, "a").pack_info()


def test_packing_marks_the_widget_as_managed_and_mapped(root):
    box = Box(root, "a")
    box.pack()
    assert box.winfo_manager() == "pack"
    assert box.winfo_ismapped()


# ------------------------------------------------------------- container fit


def test_a_container_asks_for_what_its_children_need(root):
    frame = Widget(root, name="frame")
    Box(frame, "a", width=10, height=2).pack()
    Box(frame, "b", width=14, height=3).pack()
    root.update_layout()
    # Heights add along the packing axis; widths do not.
    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (14, 5)


def test_a_container_with_propagation_off_keeps_its_size(root):
    frame = Widget(root, name="frame")
    frame._requested = Size(4, 1)
    frame.pack_propagate(False)
    Box(frame, "a", width=20, height=6).pack()
    root.update_layout()
    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (4, 1)


def test_a_child_too_large_for_the_cavity_is_clipped_to_it(root):
    root._rect = Rect(0, 0, 10, 3)
    box = Box(root, "a", width=40, height=20)
    box.pack()
    root.update_layout()
    assert box.winfo_width() <= 10
    assert box.winfo_height() <= 3


def test_no_child_is_given_a_negative_size(root):
    root._rect = Rect(0, 0, 2, 1)
    box = Box(root, "a", width=10, height=4)
    box.pack(padx=4, pady=4)
    root.update_layout()
    assert box.winfo_width() >= 0
    assert box.winfo_height() >= 0


# ---------------------------------------------------------------- validation


@pytest.mark.parametrize(
    ("option", "value"),
    [("side", "sideways"), ("fill", "everything"), ("anchor", "elsewhere")],
)
def test_a_bad_option_value_is_refused(root, option, value):
    with pytest.raises(TclError):
        Box(root, "a").pack(**{option: value})


def test_an_unknown_option_is_refused(root):
    with pytest.raises(TclError, match="unknown option"):
        Box(root, "a").pack(nonsense=1)


def test_a_bad_pad_value_is_refused(root):
    with pytest.raises(TclError, match="pad value"):
        Box(root, "a").pack(padx="wide")


def test_packing_into_another_container(root):
    frame = Widget(root, name="frame")
    box = Box(root, "a")
    box.pack(in_=frame)
    assert frame.pack_slaves() == [box]


# ------------------------------------------------- reconfiguring one option


def test_configuring_one_option_leaves_the_others_alone(root):
    """Tk merges a reconfigure into what the widget already has.

    Values checked against Tk 9.0.2: a widget packed with side="left",
    fill="both", padx=7, ipadx=3 and anchor="n", then
    pack_configure(side="right"), keeps all four of the others. Ours rebuilt
    the options from scratch, so asking for the other side also threw away
    the fill, the padding and the anchor.
    """
    box = Box(root, "b")
    box.pack(side="left", fill="both", padx=7, ipadx=3, anchor="n")
    box.pack_configure(side="right")
    info = box.pack_info()
    assert info["side"] == "right"
    assert info["fill"] == "both"
    assert (info["padx"], info["ipadx"]) == (7, 3)
    assert info["anchor"] == "n"


def test_pack_is_pack_configure_so_a_second_pack_merges_too(root):
    box = Box(root, "b")
    box.pack(side="bottom", expand=True, pady=2)
    box.pack(fill="x")
    info = box.pack_info()
    assert info["side"] == "bottom"
    assert info["expand"] is True
    assert info["pady"] == 2
    assert info["fill"] == "x"


def test_forgetting_is_what_brings_the_defaults_back(root):
    """Tk 9.0.2 after pack_forget(): side="top", fill="none", padx=0,
    ipadx=0, anchor="center"."""
    box = Box(root, "b")
    box.pack(side="left", fill="both", padx=7, ipadx=3, anchor="n")
    box.pack_forget()
    box.pack()
    info = box.pack_info()
    assert info["side"] == "top"
    assert info["fill"] == "none"
    assert (info["padx"], info["ipadx"]) == (0, 0)
    assert info["anchor"] == "center"


def test_a_bad_option_in_a_reconfigure_leaves_the_widget_as_it_was(root):
    box = Box(root, "b")
    box.pack(side="left", fill="both")
    with pytest.raises(TclError):
        box.pack_configure(side="sideways")
    info = box.pack_info()
    assert (info["side"], info["fill"]) == ("left", "both")


# ----------------------------------------------------- packing somewhere else


def test_in_moves_the_widget_out_of_its_old_container(root):
    """A widget can only be laid out by one container at a time.

    Tk 9.0.2: after pack_configure(in_=second), the first container has no
    slaves and the second has the widget. Ours added it to the new container
    without taking it out of the old, so both went on laying it out and
    whichever ran first decided where it went.
    """
    first = Box(root, "first", width=20, height=6)
    second = Box(root, "second", width=20, height=6)
    box = Box(root, "b")
    box.pack(in_=first, side="left", fill="both", padx=2)
    assert first.pack_slaves() == [box]

    box.pack_configure(in_=second)
    assert first.pack_slaves() == []
    assert second.pack_slaves() == [box]


def test_moving_to_another_container_keeps_the_options(root):
    """Tk merges across a container change too - only forget resets."""
    first = Box(root, "first", width=20, height=6)
    second = Box(root, "second", width=20, height=6)
    box = Box(root, "b")
    box.pack(in_=first, side="left", fill="both", padx=2)
    box.pack_configure(in_=second)
    info = box.pack_info()
    assert (info["side"], info["fill"], info["padx"]) == ("left", "both", 2)


def test_pack_info_names_the_container_doing_the_work(root):
    """It read the master, which for a widget packed with in_ is not it."""
    holder = Box(root, "holder", width=20, height=6)
    box = Box(root, "b")
    box.pack(in_=holder)
    assert box.pack_info()["in"] is holder


def test_forgetting_removes_it_from_the_container_that_held_it(root):
    holder = Box(root, "holder", width=20, height=6)
    box = Box(root, "b")
    box.pack(in_=holder)
    box.pack_forget()
    assert holder.pack_slaves() == []
    assert box.winfo_manager() == ""


def test_gridding_a_packed_widget_elsewhere_takes_it_out_of_the_pack(root):
    """Tk 9.0.2 allows the move and leaves the old container empty; asking
    the widget for its packing afterwards is an error, because it has none."""
    packer = Box(root, "packer", width=20, height=6)
    gridder = Box(root, "gridder", width=20, height=6)
    box = Box(root, "b")
    box.pack(in_=packer, side="left")
    box.grid(in_=gridder, row=1, column=2)
    assert packer.pack_slaves() == []
    assert box.winfo_manager() == "grid"
    with pytest.raises(TclError):
        box.pack_info()
