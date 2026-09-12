"""Tests for tkcurses._core.geometry.

Geometry is pure integer arithmetic, so it is checked both by example (the
cases ARCHITECTURE.md spells out) and by property, over randomly generated
rectangles. The properties matter more: layout bugs show up at sizes nobody
thinks to write a test for, which is what forced manual UAT previously.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses._core.geometry import (
    BORDER_WIDTH,
    Insets,
    Point,
    Rect,
    Size,
    clamp,
    clip_text,
    content_rect,
    content_size,
)

coords = st.integers(min_value=-50, max_value=50)
extents = st.integers(min_value=0, max_value=80)
rects = st.builds(Rect, x=coords, y=coords, width=extents, height=extents)
sizes = st.builds(Size, width=extents, height=extents)
insets = st.builds(
    Insets,
    left=st.integers(0, 10),
    top=st.integers(0, 10),
    right=st.integers(0, 10),
    bottom=st.integers(0, 10),
)


# --------------------------------------------------------------- by example


def test_architecture_example_30x8_window():
    """The worked example from ARCHITECTURE.md 'Window Content Areas'."""
    window = Rect(0, 0, 30, 8)
    content = content_rect(window)
    assert content == Rect(1, 1, 28, 6)
    assert content.origin == Point(1, 1)
    assert content.size == Size(28, 6)
    # "Rows: 1..6, columns 1 through 28"
    assert content.top == 1 and content.bottom == 6
    assert content.left == 1 and content.right == 28


def test_borderless_window_uses_the_whole_area():
    window = Rect(0, 0, 30, 8)
    assert content_rect(window, bordered=False) == window


def test_content_size_removes_both_edges():
    assert content_size(Size(30, 8)) == Size(28, 6)
    assert content_size(Size(30, 8), bordered=False) == Size(30, 8)


@pytest.mark.parametrize("dimension", [0, 1, 2])
def test_window_too_small_for_a_border_has_no_interior(dimension):
    """Two cells are consumed by the border, so anything narrower has none."""
    assert content_size(Size(dimension, dimension)).is_empty


def test_content_rect_of_a_tiny_window_is_empty_not_negative():
    content = content_rect(Rect(5, 5, 1, 1))
    assert content.is_empty
    assert content.width == 0 and content.height == 0


def test_content_rect_applies_padding_on_top_of_the_border():
    content = content_rect(Rect(0, 0, 20, 10), padding=Insets.uniform(2))
    assert content == Rect(3, 3, 14, 4)


def test_offset_window_keeps_its_content_relative():
    content = content_rect(Rect(10, 4, 30, 8))
    assert content == Rect(11, 5, 28, 6)


def test_border_width_is_one_cell():
    assert BORDER_WIDTH == 1


# ------------------------------------------------------------------- types


def test_negative_sizes_are_rejected():
    with pytest.raises(ValueError, match="negative size"):
        Size(-1, 4)
    with pytest.raises(ValueError, match="negative size"):
        Rect(0, 0, 4, -1)


def test_negative_insets_are_rejected():
    with pytest.raises(ValueError, match="negative inset"):
        Insets(left=-1)


def test_rect_may_sit_at_negative_coordinates():
    """A partly off-screen widget must be describable before it is clipped."""
    rect = Rect(-5, -2, 10, 10)
    assert rect.left == -5
    assert rect.intersection(Rect(0, 0, 20, 20)) == Rect(0, 0, 5, 8)


def test_insets_combine():
    assert Insets.uniform(1) + Insets.symmetric(horizontal=2) == Insets(3, 1, 3, 1)


def test_clamp_rejects_an_empty_range():
    with pytest.raises(ValueError, match="empty range"):
        clamp(1, 10, 0)


@pytest.mark.parametrize(
    ("value", "expected"), [(-5, 0), (0, 0), (5, 5), (10, 10), (99, 10)]
)
def test_clamp(value, expected):
    assert clamp(value, 0, 10) == expected


@pytest.mark.parametrize(
    ("text", "width", "expected"),
    [
        ("hello", 10, "hello"),
        ("hello", 5, "hello"),
        ("hello", 3, "hel"),
        ("hello", 0, ""),
        ("hello", -1, ""),
        ("", 5, ""),
    ],
)
def test_clip_text(text, width, expected):
    assert clip_text(text, width) == expected


# -------------------------------------------------------------- properties


@given(size=sizes)
def test_content_is_never_larger_than_the_window(size):
    content = content_size(size)
    assert content.width <= size.width
    assert content.height <= size.height


@given(rect=rects)
def test_content_never_escapes_its_window(rect):
    """The invariant that keeps widgets from overwriting their own border."""
    assert rect.contains(content_rect(rect))


@given(rect=rects, padding=insets)
def test_padded_content_never_escapes_its_window(rect, padding):
    assert rect.contains(content_rect(rect, padding=padding))


@given(rect=rects, padding=insets)
def test_inset_never_produces_negative_dimensions(rect, padding):
    result = rect.inset(padding)
    assert result.width >= 0 and result.height >= 0


@given(a=rects, b=rects)
def test_intersection_is_commutative(a, b):
    left, right = a.intersection(b), b.intersection(a)
    assert left.size == right.size
    if not left.is_empty:
        assert left == right


@given(a=rects, b=rects)
def test_intersection_is_contained_in_both(a, b):
    overlap = a.intersection(b)
    assert a.contains(overlap)
    assert b.contains(overlap)


@given(rect=rects, dx=coords, dy=coords)
def test_translation_preserves_size(rect, dx, dy):
    assert rect.translated(dx, dy).size == rect.size


@given(rect=rects, dx=coords, dy=coords)
def test_translation_is_reversible(rect, dx, dy):
    assert rect.translated(dx, dy).translated(-dx, -dy) == rect


@given(rect=rects)
def test_a_rect_contains_itself(rect):
    assert rect.contains(rect)


@given(text=st.text(max_size=40), width=st.integers(-5, 40))
def test_clipped_text_never_exceeds_the_width(text, width):
    assert len(clip_text(text, width)) <= max(0, width)


@given(rect=rects)
def test_every_corner_is_inside_a_non_empty_rect(rect):
    if rect.is_empty:
        return
    for point in (
        Point(rect.left, rect.top),
        Point(rect.right, rect.top),
        Point(rect.left, rect.bottom),
        Point(rect.right, rect.bottom),
    ):
        assert rect.contains_point(point)


@given(rect=rects)
def test_empty_rect_contains_no_points(rect):
    if not rect.is_empty:
        return
    assert not rect.contains_point(rect.origin)


# ------------------------------------------------------- remaining surface


def test_point_translation():
    assert Point(3, 4).translated(-1, 2) == Point(2, 6)


def test_size_area_and_emptiness():
    assert Size(4, 5).area == 20
    assert not Size(4, 5).is_empty
    assert Size(0, 5).is_empty
    assert Size(5, 0).is_empty


def test_size_growth_clamps_at_zero():
    assert Size(4, 5).grown(2, -2) == Size(6, 3)
    assert Size(1, 1).grown(-5, -5) == Size(0, 0)


def test_rect_from_size():
    assert Rect.from_size(Size(3, 2)) == Rect(0, 0, 3, 2)
    assert Rect.from_size(Size(3, 2), Point(4, 5)) == Rect(4, 5, 3, 2)


def test_rect_area():
    assert Rect(1, 1, 4, 5).area == 20
    assert Rect(1, 1, 0, 5).area == 0


def test_an_empty_rect_contains_nothing_but_empties():
    empty = Rect(2, 2, 0, 0)
    assert empty.contains(Rect(0, 0, 0, 0))
    assert not empty.contains(Rect(2, 2, 1, 1))


def test_intersects():
    a = Rect(0, 0, 10, 10)
    assert a.intersects(Rect(5, 5, 10, 10))
    assert not a.intersects(Rect(20, 20, 5, 5))
    # Adjacent but not overlapping: a ends at column 9, b starts at 10.
    assert not a.intersects(Rect(10, 0, 5, 5))
