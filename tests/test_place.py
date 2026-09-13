"""Tests for the place geometry manager."""

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
    return (
        widget.winfo_x(),
        widget.winfo_y(),
        widget.winfo_width(),
        widget.winfo_height(),
    )


# ---------------------------------------------------------------- absolute


def test_a_placed_widget_goes_where_it_is_told(root):
    box = Box(root, "a", width=10, height=2)
    box.place(x=4, y=3)
    root.update_layout()
    assert geometry(box) == (4, 3, 10, 2)


def test_a_placed_widget_defaults_to_the_origin(root):
    box = Box(root, "a", width=6, height=1)
    box.place()
    root.update_layout()
    assert (box.winfo_x(), box.winfo_y()) == (0, 0)


def test_a_placed_widget_keeps_its_requested_size(root):
    box = Box(root, "a", width=7, height=3)
    box.place(x=1, y=1)
    root.update_layout()
    assert (box.winfo_width(), box.winfo_height()) == (7, 3)


def test_an_explicit_size_overrides_the_requested_one(root):
    box = Box(root, "a", width=7, height=3)
    box.place(x=0, y=0, width=20, height=5)
    root.update_layout()
    assert (box.winfo_width(), box.winfo_height()) == (20, 5)


def test_a_widget_may_be_placed_partly_outside_its_container(root):
    """Place does what it is told; clipping is the renderer's business."""
    box = Box(root, "a", width=10, height=2)
    box.place(x=35, y=11)
    root.update_layout()
    assert box.winfo_x() == 35


# ---------------------------------------------------------------- relative


def test_relx_is_a_fraction_of_the_container(root):
    box = Box(root, "a", width=4, height=1)
    box.place(relx=0.5)
    root.update_layout()
    assert box.winfo_x() == 20


def test_rely_is_a_fraction_of_the_height(root):
    box = Box(root, "a", width=4, height=1)
    box.place(rely=0.5)
    root.update_layout()
    assert box.winfo_y() == 6


def test_relwidth_sizes_against_the_container(root):
    box = Box(root, "a", width=4, height=1)
    box.place(relwidth=0.5)
    root.update_layout()
    assert box.winfo_width() == 20


def test_relheight_sizes_against_the_container(root):
    box = Box(root, "a", width=4, height=1)
    box.place(relheight=0.25)
    root.update_layout()
    assert box.winfo_height() == 3


def test_a_full_size_child_fills_the_container(root):
    box = Box(root, "a", width=1, height=1)
    box.place(relwidth=1.0, relheight=1.0)
    root.update_layout()
    assert geometry(box) == (0, 0, 40, 12)


def test_absolute_and_relative_add_together(root):
    """How "half the width, less two cells" is expressed."""
    box = Box(root, "a", width=4, height=1)
    box.place(relwidth=0.5, width=-2)
    root.update_layout()
    assert box.winfo_width() == 18


def test_an_absolute_offset_shifts_a_relative_position(root):
    box = Box(root, "a", width=4, height=1)
    box.place(relx=0.5, x=3)
    root.update_layout()
    assert box.winfo_x() == 23


# ------------------------------------------------------------------ anchor


def test_the_default_anchor_is_the_top_left_corner(root):
    box = Box(root, "a", width=10, height=2)
    box.place(x=5, y=5)
    root.update_layout()
    assert (box.winfo_x(), box.winfo_y()) == (5, 5)


def test_a_centre_anchor_centres_the_widget_on_the_position(root):
    box = Box(root, "a", width=10, height=2)
    box.place(relx=0.5, rely=0.5, anchor="center")
    root.update_layout()
    assert box.winfo_x() == 20 - 5
    assert box.winfo_y() == 6 - 1


def test_a_south_east_anchor_puts_the_far_corner_on_the_position(root):
    box = Box(root, "a", width=10, height=2)
    box.place(x=40, y=12, anchor="se")
    root.update_layout()
    assert (box.winfo_x(), box.winfo_y()) == (30, 10)


# --------------------------------------------------------------- container


def test_placed_children_make_no_claim_on_the_container(root):
    """What separates place from the other two managers."""
    frame = Widget(root, name="frame")
    Box(frame, "a", width=30, height=8).place(x=0, y=0)
    root.update_layout()
    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (0, 0)


def test_place_measures_inside_the_border_by_default(root):
    root._options["borderwidth"] = 1
    box = Box(root, "a", width=4, height=1)
    box.place(x=0, y=0)
    root.update_layout()
    assert (box.winfo_x(), box.winfo_y()) == (1, 1)


def test_bordermode_outside_measures_against_the_whole_widget(root):
    root._options["borderwidth"] = 1
    box = Box(root, "a", width=4, height=1)
    box.place(x=0, y=0, bordermode="outside")
    root.update_layout()
    assert (box.winfo_x(), box.winfo_y()) == (0, 0)


# ------------------------------------------------------------ bookkeeping


def test_place_slaves_lists_the_children(root):
    first = Box(root, "a")
    second = Box(root, "b")
    first.place(x=0)
    second.place(x=5)
    assert root.place_slaves() == [first, second]


def test_placing_again_moves_the_widget(root):
    box = Box(root, "a", width=4, height=1)
    box.place(x=1, y=1)
    box.place(x=7, y=2)
    root.update_layout()
    assert (box.winfo_x(), box.winfo_y()) == (7, 2)
    assert root.place_slaves() == [box]


def test_forgetting_removes_and_unmaps(root):
    box = Box(root, "a")
    box.place(x=1)
    box.place_forget()
    assert root.place_slaves() == []
    assert not box.winfo_ismapped()
    assert box.winfo_manager() == ""


def test_place_info_reports_the_options(root):
    box = Box(root, "a")
    box.place(x=2, rely=0.5, anchor="se")
    info = box.place_info()
    assert info["x"] == 2
    assert info["rely"] == 0.5
    assert info["anchor"] == "se"
    assert info["in"] is root


def test_place_info_on_an_unplaced_widget_is_refused(root):
    with pytest.raises(TclError, match="not placed"):
        Box(root, "a").place_info()


def test_placing_marks_the_widget_as_managed(root):
    box = Box(root, "a")
    box.place(x=0)
    assert box.winfo_manager() == "place"
    assert box.winfo_ismapped()


# --------------------------------------------------------------- validation


def test_an_unknown_option_is_refused(root):
    with pytest.raises(TclError, match="unknown option"):
        Box(root, "a").place(nonsense=1)


def test_a_bad_anchor_is_refused(root):
    with pytest.raises(TclError, match="anchor"):
        Box(root, "a").place(anchor="elsewhere")


def test_a_bad_bordermode_is_refused(root):
    with pytest.raises(TclError, match="bordermode"):
        Box(root, "a").place(bordermode="sideways")


def test_a_bad_coordinate_is_refused(root):
    with pytest.raises(TclError, match="bad x value"):
        Box(root, "a").place(x="over there")


def test_a_bad_relative_value_is_refused(root):
    with pytest.raises(TclError, match="floating-point"):
        Box(root, "a").place(relx="half")


def test_a_negative_size_is_not_produced(root):
    box = Box(root, "a", width=4, height=1)
    box.place(width=-100)
    root.update_layout()
    assert box.winfo_width() >= 0


def test_mixing_place_with_pack_is_refused(root):
    Box(root, "a").pack()
    with pytest.raises(TclError, match="already has slaves managed by pack"):
        Box(root, "b").place(x=0)
