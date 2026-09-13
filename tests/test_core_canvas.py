"""Tests for canvas rasterising and half-cell composition."""

from __future__ import annotations

import pytest

from tkcurses._core.canvas import (
    FULL,
    LOWER,
    UPPER,
    bbox_of,
    compose,
    filled_oval_pixels,
    filled_polygon_pixels,
    filled_rectangle_pixels,
    line_pixels,
    oval_pixels,
    polygon_pixels,
    rectangle_pixels,
)


def connected(pixels):
    """True if every pixel touches another, counting diagonals.

    What separates a drawn outline from a dotted approximation of one.
    """
    points = set(pixels)
    return all(
        any(
            (x + dx, y + dy) in points
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if (dx, dy) != (0, 0)
        )
        for x, y in points
    )


# --------------------------------------------------------------- composition


def test_a_lit_top_half_is_an_upper_block():
    assert compose({(0, 0): "red"}) == {(0, 0): (UPPER, "red", None)}


def test_a_lit_bottom_half_is_a_lower_block():
    assert compose({(0, 1): "red"}) == {(0, 0): (LOWER, "red", None)}


def test_two_halves_of_one_colour_are_a_full_block():
    assert compose({(0, 0): "red", (0, 1): "red"}) == {(0, 0): (FULL, "red", None)}


def test_two_halves_of_different_colours_share_a_cell():
    """The reason half blocks beat the denser sets: two colours in one cell."""
    composed = compose({(0, 0): "red", (0, 1): "blue"})
    assert composed == {(0, 0): (UPPER, "red", "blue")}


def test_pixel_rows_pair_up_into_cell_rows():
    composed = compose({(0, 0): "a", (0, 2): "b", (0, 5): "c"})
    assert set(composed) == {(0, 0), (0, 1), (0, 2)}


def test_an_empty_plane_composes_to_nothing():
    assert compose({}) == {}


def test_a_cell_with_no_ink_is_absent_rather_than_blank():
    """So the canvas background shows through instead of being painted over."""
    composed = compose({(0, 0): "red", (5, 0): "red"})
    assert (1, 0) not in composed


# ---------------------------------------------------------------------- bbox


def test_bbox_of_pixels():
    assert bbox_of([(2, 3), (7, 1), (4, 9)]) == (2, 1, 7, 9)


def test_bbox_of_nothing_is_none():
    assert bbox_of([]) is None


# --------------------------------------------------------------------- lines


def test_a_horizontal_line():
    assert line_pixels([(0, 0), (3, 0)]) == [(0, 0), (1, 0), (2, 0), (3, 0)]


def test_a_vertical_line():
    assert line_pixels([(0, 0), (0, 3)]) == [(0, 0), (0, 1), (0, 2), (0, 3)]


def test_a_diagonal_line():
    assert line_pixels([(0, 0), (3, 3)]) == [(0, 0), (1, 1), (2, 2), (3, 3)]


def test_a_line_is_the_same_from_either_end():
    """A redrawn shape that shifted by a pixel would flicker."""
    forwards = set(line_pixels([(0, 0), (11, 5)]))
    backwards = set(line_pixels([(11, 5), (0, 0)]))
    assert forwards == backwards


def test_a_steep_line_has_no_gaps():
    assert connected(line_pixels([(0, 0), (2, 20)]))


def test_a_shallow_line_has_no_gaps():
    assert connected(line_pixels([(0, 0), (20, 2)]))


def test_several_segments_join_without_repeating_the_corner():
    pixels = line_pixels([(0, 0), (3, 0), (3, 3)])
    assert len(pixels) == len(set(pixels))
    assert (3, 0) in pixels


def test_a_single_point_is_one_pixel():
    assert line_pixels([(4, 4)]) == [(4, 4)]


def test_no_points_is_nothing():
    assert line_pixels([]) == []


# ---------------------------------------------------------------- rectangles


def test_a_rectangle_outline_is_hollow():
    pixels = set(rectangle_pixels(0, 0, 4, 4))
    assert (0, 0) in pixels
    assert (4, 4) in pixels
    assert (2, 2) not in pixels


def test_a_rectangle_can_be_given_either_corner_first():
    """A rectangle dragged out with a mouse arrives in whichever order."""
    assert set(rectangle_pixels(4, 4, 0, 0)) == set(rectangle_pixels(0, 0, 4, 4))


def test_a_filled_rectangle_is_solid():
    pixels = set(filled_rectangle_pixels(0, 0, 3, 2))
    assert len(pixels) == 4 * 3
    assert (1, 1) in pixels


# --------------------------------------------------------------------- ovals


def test_an_oval_outline_is_hollow():
    pixels = set(oval_pixels(0, 0, 20, 20))
    assert (10, 10) not in pixels


def test_an_oval_outline_has_no_gaps():
    assert connected(oval_pixels(0, 0, 20, 20))


def test_a_small_oval_has_no_gaps():
    assert connected(oval_pixels(0, 0, 4, 4))


def test_an_oval_stays_inside_its_box():
    for x, y in oval_pixels(3, 5, 17, 13):
        assert 3 <= x <= 17
        assert 5 <= y <= 13


def test_an_oval_of_equal_sides_is_as_wide_as_it_is_tall():
    """The point of the half-cell plane: a circle is a circle."""
    left, top, right, bottom = bbox_of(oval_pixels(0, 0, 20, 20))
    assert right - left == bottom - top


def test_an_oval_too_thin_to_curve_is_its_rectangle():
    assert set(oval_pixels(0, 0, 6, 0)) == set(rectangle_pixels(0, 0, 6, 0))


def test_a_filled_oval_is_solid_and_round():
    pixels = set(filled_oval_pixels(0, 0, 20, 20))
    assert (10, 10) in pixels
    assert (0, 0) not in pixels  # the corners are outside the ellipse
    assert (10, 0) in pixels  # but the top of the curve is on it


def test_a_filled_oval_has_no_holes():
    pixels = set(filled_oval_pixels(0, 0, 15, 11))
    for x, y in oval_pixels(0, 0, 15, 11):
        assert (x, y) in pixels


# ------------------------------------------------------------------ polygons


def test_a_polygon_outline_closes_itself():
    pixels = set(polygon_pixels([(0, 0), (4, 0), (4, 4)]))
    assert (2, 2) in pixels  # the closing diagonal


def test_a_filled_triangle_is_solid():
    pixels = set(filled_polygon_pixels([(0, 0), (10, 0), (0, 10)]))
    assert (1, 1) in pixels
    assert (9, 9) not in pixels


def test_a_filled_polygon_includes_its_outline():
    points = [(0, 0), (10, 2), (6, 9), (1, 7)]
    pixels = set(filled_polygon_pixels(points))
    for pixel in polygon_pixels(points):
        assert pixel in pixels


def test_a_polygon_of_two_points_is_a_line():
    assert set(polygon_pixels([(0, 0), (3, 0)])) == set(line_pixels([(0, 0), (3, 0)]))


@pytest.mark.parametrize(
    "shape",
    [
        [(0, 0), (10, 0), (10, 10), (0, 10)],
        [(5, 0), (10, 5), (5, 10), (0, 5)],
        [(0, 0), (10, 3), (4, 11)],
    ],
)
def test_a_filled_shape_covers_its_own_outline(shape):
    filled = set(filled_polygon_pixels(shape))
    assert set(polygon_pixels(shape)) <= filled
