"""Unit tests for tkcurses._core.geometry module."""

import pytest

from tkcurses._core.geometry import (
    Point,
    Size,
    Padding,
    Rect,
    SizeConstraints,
    center_in_rect,
    align_in_rect,
    distribute_space,
)


class TestPoint:
    """Tests for Point class."""

    def test_point_creation(self):
        """Point should store x and y coordinates."""
        p = Point(10, 20)
        assert p.x == 10
        assert p.y == 20

    def test_point_tuple_unpacking(self):
        """Point should support tuple unpacking."""
        p = Point(10, 20)
        x, y = p
        assert x == 10
        assert y == 20

    def test_point_offset(self):
        """Point.offset should create new point at offset."""
        p = Point(10, 20)
        p2 = p.offset(5, -3)
        assert p2.x == 15
        assert p2.y == 17
        # Original unchanged
        assert p.x == 10
        assert p.y == 20

    def test_point_add_point(self):
        """Point addition should work with another Point."""
        p1 = Point(10, 20)
        p2 = Point(5, 3)
        result = p1 + p2
        assert result == Point(15, 23)

    def test_point_add_tuple(self):
        """Point addition should work with tuple."""
        p = Point(10, 20)
        result = p + (5, 3)
        assert result == Point(15, 23)

    def test_point_sub_point(self):
        """Point subtraction should work with another Point."""
        p1 = Point(10, 20)
        p2 = Point(3, 5)
        result = p1 - p2
        assert result == Point(7, 15)

    def test_point_sub_tuple(self):
        """Point subtraction should work with tuple."""
        p = Point(10, 20)
        result = p - (3, 5)
        assert result == Point(7, 15)

    def test_point_equality(self):
        """Points with same coordinates should be equal."""
        p1 = Point(10, 20)
        p2 = Point(10, 20)
        assert p1 == p2

    def test_point_inequality(self):
        """Points with different coordinates should not be equal."""
        p1 = Point(10, 20)
        p2 = Point(10, 21)
        assert p1 != p2


class TestSize:
    """Tests for Size class."""

    def test_size_creation(self):
        """Size should store width and height."""
        s = Size(80, 24)
        assert s.width == 80
        assert s.height == 24

    def test_size_area(self):
        """Size.area should return width * height."""
        s = Size(10, 5)
        assert s.area == 50

    def test_size_add(self):
        """Size addition should add dimensions."""
        s1 = Size(10, 5)
        s2 = Size(3, 2)
        result = s1 + s2
        assert result == Size(13, 7)

    def test_size_add_tuple(self):
        """Size addition should work with tuple."""
        s = Size(10, 5)
        result = s + (3, 2)
        assert result == Size(13, 7)

    def test_size_sub(self):
        """Size subtraction should subtract dimensions."""
        s1 = Size(10, 5)
        s2 = Size(3, 2)
        result = s1 - s2
        assert result == Size(7, 3)

    def test_size_sub_clamped(self):
        """Size subtraction should clamp to zero."""
        s1 = Size(3, 2)
        s2 = Size(10, 5)
        result = s1 - s2
        assert result == Size(0, 0)


class TestPadding:
    """Tests for Padding class."""

    def test_padding_creation(self):
        """Padding should store all four sides."""
        p = Padding(1, 2, 3, 4)
        assert p.left == 1
        assert p.top == 2
        assert p.right == 3
        assert p.bottom == 4

    def test_padding_defaults(self):
        """Padding should default to zero."""
        p = Padding()
        assert p.left == 0
        assert p.top == 0
        assert p.right == 0
        assert p.bottom == 0

    def test_padding_uniform(self):
        """Padding.uniform should create equal padding."""
        p = Padding.uniform(5)
        assert p.left == 5
        assert p.top == 5
        assert p.right == 5
        assert p.bottom == 5

    def test_padding_symmetric(self):
        """Padding.symmetric should create symmetric padding."""
        p = Padding.symmetric(10, 5)
        assert p.left == 10
        assert p.right == 10
        assert p.top == 5
        assert p.bottom == 5

    def test_padding_horizontal(self):
        """Padding.horizontal should return left + right."""
        p = Padding(1, 2, 3, 4)
        assert p.horizontal == 4  # 1 + 3

    def test_padding_vertical(self):
        """Padding.vertical should return top + bottom."""
        p = Padding(1, 2, 3, 4)
        assert p.vertical == 6  # 2 + 4

    def test_padding_size(self):
        """Padding.size should return total size."""
        p = Padding(1, 2, 3, 4)
        assert p.size == Size(4, 6)


class TestRect:
    """Tests for Rect class."""

    def test_rect_creation(self):
        """Rect should store position and size."""
        r = Rect(10, 5, 40, 20)
        assert r.x == 10
        assert r.y == 5
        assert r.width == 40
        assert r.height == 20

    def test_rect_properties(self):
        """Rect should have correct edge properties."""
        r = Rect(10, 5, 40, 20)
        assert r.left == 10
        assert r.top == 5
        assert r.right == 50
        assert r.bottom == 25

    def test_rect_position(self):
        """Rect.position should return top-left Point."""
        r = Rect(10, 5, 40, 20)
        assert r.position == Point(10, 5)

    def test_rect_size(self):
        """Rect.size should return Size."""
        r = Rect(10, 5, 40, 20)
        assert r.size == Size(40, 20)

    def test_rect_center(self):
        """Rect.center should return center Point."""
        r = Rect(10, 10, 20, 10)
        assert r.center == Point(20, 15)

    def test_rect_area(self):
        """Rect.area should return width * height."""
        r = Rect(0, 0, 10, 5)
        assert r.area == 50

    def test_rect_is_empty(self):
        """Rect.is_empty should detect zero-area rectangles."""
        assert Rect(0, 0, 0, 10).is_empty
        assert Rect(0, 0, 10, 0).is_empty
        assert not Rect(0, 0, 1, 1).is_empty

    def test_rect_contains_point(self):
        """Rect should detect if point is inside."""
        r = Rect(10, 10, 20, 10)
        assert r.contains_point(Point(15, 15))
        assert r.contains_point(Point(10, 10))  # Edge
        assert not r.contains_point(Point(30, 20))  # Right edge exclusive
        assert not r.contains_point(Point(5, 15))  # Outside left

    def test_rect_contains_via_in_operator(self):
        """Rect should support 'in' operator for points."""
        r = Rect(10, 10, 20, 10)
        assert Point(15, 15) in r
        assert (15, 15) in r  # Tuple also works
        assert Point(5, 15) not in r

    def test_rect_contains_rect(self):
        """Rect should detect if another rect is inside."""
        outer = Rect(0, 0, 100, 100)
        inner = Rect(10, 10, 20, 20)
        assert outer.contains_rect(inner)
        assert not inner.contains_rect(outer)

    def test_rect_intersects(self):
        """Rect.intersects should detect overlap."""
        r1 = Rect(0, 0, 20, 20)
        r2 = Rect(10, 10, 20, 20)
        r3 = Rect(30, 30, 10, 10)
        assert r1.intersects(r2)
        assert r2.intersects(r1)
        assert not r1.intersects(r3)

    def test_rect_intersection(self):
        """Rect.intersection should return overlapping area."""
        r1 = Rect(0, 0, 20, 20)
        r2 = Rect(10, 10, 20, 20)
        inter = r1.intersection(r2)
        assert inter == Rect(10, 10, 10, 10)

    def test_rect_intersection_none(self):
        """Rect.intersection should return None if no overlap."""
        r1 = Rect(0, 0, 10, 10)
        r2 = Rect(20, 20, 10, 10)
        assert r1.intersection(r2) is None

    def test_rect_union(self):
        """Rect.union should return bounding rectangle."""
        r1 = Rect(0, 0, 10, 10)
        r2 = Rect(20, 20, 10, 10)
        union = r1.union(r2)
        assert union == Rect(0, 0, 30, 30)

    def test_rect_offset(self):
        """Rect.offset should move rectangle."""
        r = Rect(10, 10, 20, 20)
        r2 = r.offset(5, -3)
        assert r2 == Rect(15, 7, 20, 20)

    def test_rect_move_to(self):
        """Rect.move_to should position rectangle."""
        r = Rect(10, 10, 20, 20)
        r2 = r.move_to(0, 0)
        assert r2 == Rect(0, 0, 20, 20)

    def test_rect_resize(self):
        """Rect.resize should change size."""
        r = Rect(10, 10, 20, 20)
        r2 = r.resize(30, 40)
        assert r2 == Rect(10, 10, 30, 40)

    def test_rect_inset(self):
        """Rect.inset should shrink by padding."""
        r = Rect(0, 0, 40, 30)
        r2 = r.inset(Padding(5, 5, 5, 5))
        assert r2 == Rect(5, 5, 30, 20)

    def test_rect_inset_uniform(self):
        """Rect.inset should work with int."""
        r = Rect(0, 0, 40, 30)
        r2 = r.inset(5)
        assert r2 == Rect(5, 5, 30, 20)

    def test_rect_outset(self):
        """Rect.outset should expand by padding."""
        r = Rect(10, 10, 20, 20)
        r2 = r.outset(Padding(5, 5, 5, 5))
        assert r2 == Rect(5, 5, 30, 30)

    def test_rect_clamp(self):
        """Rect.clamp should fit within bounds."""
        bounds = Rect(0, 0, 100, 100)
        r = Rect(-10, -10, 20, 20)
        clamped = r.clamp(bounds)
        assert clamped.x >= 0
        assert clamped.y >= 0
        assert clamped.right <= 100
        assert clamped.bottom <= 100

    def test_rect_iter_cells(self):
        """Rect.iter_cells should yield all cell positions."""
        r = Rect(0, 0, 3, 2)
        cells = list(r.iter_cells())
        assert len(cells) == 6
        assert Point(0, 0) in cells
        assert Point(2, 1) in cells

    def test_rect_to_geometry_string(self):
        """Rect should convert to geometry string."""
        r = Rect(10, 5, 80, 24)
        assert r.to_geometry_string() == '80x24+10+5'

    def test_rect_from_geometry_string(self):
        """Rect should parse geometry string."""
        r = Rect.from_geometry_string('80x24+10+5')
        assert r == Rect(10, 5, 80, 24)

    def test_rect_from_geometry_string_no_position(self):
        """Rect should parse geometry string without position."""
        r = Rect.from_geometry_string('80x24')
        assert r == Rect(0, 0, 80, 24)

    def test_rect_from_geometry_string_negative(self):
        """Rect should parse geometry string with negative position."""
        r = Rect.from_geometry_string('80x24-10-5')
        assert r == Rect(-10, -5, 80, 24)

    def test_rect_from_geometry_string_invalid(self):
        """Rect should raise on invalid geometry string."""
        with pytest.raises(ValueError):
            Rect.from_geometry_string('invalid')

    def test_rect_from_points(self):
        """Rect.from_points should create from corners."""
        r = Rect.from_points(Point(10, 5), Point(30, 25))
        assert r == Rect(10, 5, 20, 20)

    def test_rect_from_points_reversed(self):
        """Rect.from_points should normalize corners."""
        r = Rect.from_points(Point(30, 25), Point(10, 5))
        assert r == Rect(10, 5, 20, 20)

    def test_rect_from_ltrb(self):
        """Rect.from_ltrb should create from edges."""
        r = Rect.from_ltrb(10, 5, 50, 25)
        assert r == Rect(10, 5, 40, 20)


class TestSizeConstraints:
    """Tests for SizeConstraints class."""

    def test_constraints_defaults(self):
        """SizeConstraints should have sensible defaults."""
        c = SizeConstraints()
        assert c.min_width == 0
        assert c.min_height == 0
        assert c.max_width is None
        assert c.max_height is None

    def test_clamp_width(self):
        """SizeConstraints should clamp width."""
        c = SizeConstraints(min_width=10, max_width=100)
        assert c.clamp_width(5) == 10
        assert c.clamp_width(50) == 50
        assert c.clamp_width(150) == 100

    def test_clamp_height(self):
        """SizeConstraints should clamp height."""
        c = SizeConstraints(min_height=5, max_height=50)
        assert c.clamp_height(3) == 5
        assert c.clamp_height(25) == 25
        assert c.clamp_height(100) == 50

    def test_clamp_size(self):
        """SizeConstraints should clamp both dimensions."""
        c = SizeConstraints(min_width=10, min_height=5, max_width=100, max_height=50)
        assert c.clamp_size(Size(5, 3)) == Size(10, 5)
        assert c.clamp_size(Size(50, 25)) == Size(50, 25)
        assert c.clamp_size(Size(150, 100)) == Size(100, 50)

    def test_min_size(self):
        """SizeConstraints.min_size should return minimum Size."""
        c = SizeConstraints(min_width=10, min_height=5)
        assert c.min_size == Size(10, 5)

    def test_max_size(self):
        """SizeConstraints.max_size should return maximum Size."""
        c = SizeConstraints(max_width=100, max_height=50)
        assert c.max_size == Size(100, 50)

    def test_max_size_none(self):
        """SizeConstraints.max_size should be None if unbounded."""
        c = SizeConstraints(max_width=100)
        assert c.max_size is None


class TestCenterInRect:
    """Tests for center_in_rect function."""

    def test_center_in_rect(self):
        """center_in_rect should center size in rectangle."""
        pos = center_in_rect(Size(10, 5), Rect(0, 0, 80, 24))
        assert pos == Point(35, 9)

    def test_center_larger_than_rect(self):
        """center_in_rect should handle larger sizes."""
        pos = center_in_rect(Size(100, 50), Rect(0, 0, 80, 24))
        # Will have negative position
        assert pos.x < 0
        assert pos.y < 0


class TestAlignInRect:
    """Tests for align_in_rect function."""

    def test_align_center(self):
        """align_in_rect should center by default."""
        pos = align_in_rect(Size(10, 5), Rect(0, 0, 80, 24))
        assert pos == Point(35, 9)

    def test_align_nw(self):
        """align_in_rect should align to northwest."""
        pos = align_in_rect(Size(10, 5), Rect(0, 0, 80, 24), 'nw')
        assert pos == Point(0, 0)

    def test_align_ne(self):
        """align_in_rect should align to northeast."""
        pos = align_in_rect(Size(10, 5), Rect(0, 0, 80, 24), 'ne')
        assert pos == Point(70, 0)

    def test_align_sw(self):
        """align_in_rect should align to southwest."""
        pos = align_in_rect(Size(10, 5), Rect(0, 0, 80, 24), 'sw')
        assert pos == Point(0, 19)

    def test_align_se(self):
        """align_in_rect should align to southeast."""
        pos = align_in_rect(Size(10, 5), Rect(0, 0, 80, 24), 'se')
        assert pos == Point(70, 19)

    def test_align_n(self):
        """align_in_rect should align to north (top center)."""
        pos = align_in_rect(Size(10, 5), Rect(0, 0, 80, 24), 'n')
        assert pos == Point(35, 0)

    def test_align_s(self):
        """align_in_rect should align to south (bottom center)."""
        pos = align_in_rect(Size(10, 5), Rect(0, 0, 80, 24), 's')
        assert pos == Point(35, 19)

    def test_align_e(self):
        """align_in_rect should align to east (right center)."""
        pos = align_in_rect(Size(10, 5), Rect(0, 0, 80, 24), 'e')
        assert pos == Point(70, 9)

    def test_align_w(self):
        """align_in_rect should align to west (left center)."""
        pos = align_in_rect(Size(10, 5), Rect(0, 0, 80, 24), 'w')
        assert pos == Point(0, 9)


class TestDistributeSpace:
    """Tests for distribute_space function."""

    def test_distribute_equal(self):
        """distribute_space should distribute equally by default."""
        result = distribute_space(100, 4)
        assert sum(result) == 100
        assert len(result) == 4

    def test_distribute_weighted(self):
        """distribute_space should respect weights."""
        result = distribute_space(100, 4, [1, 2, 1, 0])
        assert sum(result) == 100
        assert result[1] == result[0] * 2
        assert result[3] == 0

    def test_distribute_empty(self):
        """distribute_space should handle zero count."""
        result = distribute_space(100, 0)
        assert result == []

    def test_distribute_single(self):
        """distribute_space should handle single item."""
        result = distribute_space(100, 1)
        assert result == [100]

    def test_distribute_weight_mismatch(self):
        """distribute_space should raise on weight count mismatch."""
        with pytest.raises(ValueError):
            distribute_space(100, 3, [1, 2])
