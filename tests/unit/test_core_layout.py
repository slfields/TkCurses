"""Unit tests for the layout module.

Tests for PlaceLayoutEngine, PackLayoutEngine, GridLayoutEngine,
LayoutManager, and related classes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from tkcurses._core.geometry import Rect, Size
from tkcurses._core.layout import (
    GridLayoutCache,
    GridLayoutEngine,
    LayoutManager,
    LayoutResult,
    PackLayoutEngine,
    PlaceLayoutEngine,
)


# =============================================================================
# LayoutResult Tests
# =============================================================================


class TestLayoutResult:
    """Tests for the LayoutResult dataclass."""

    def test_create_layout_result(self):
        """Test creating a LayoutResult with basic values."""
        result = LayoutResult(x=10, y=5, width=100, height=50)
        assert result.x == 10
        assert result.y == 5
        assert result.width == 100
        assert result.height == 50

    def test_layout_result_equality(self):
        """Test LayoutResult equality comparison."""
        r1 = LayoutResult(x=10, y=5, width=100, height=50)
        r2 = LayoutResult(x=10, y=5, width=100, height=50)
        r3 = LayoutResult(x=10, y=5, width=100, height=60)
        assert r1 == r2
        assert r1 != r3

    def test_layout_result_zero_values(self):
        """Test LayoutResult with zero values."""
        result = LayoutResult(x=0, y=0, width=0, height=0)
        assert result.x == 0
        assert result.y == 0
        assert result.width == 0
        assert result.height == 0


# =============================================================================
# GridLayoutCache Tests
# =============================================================================


class TestGridLayoutCache:
    """Tests for the GridLayoutCache dataclass."""

    def test_create_grid_layout_cache(self):
        """Test creating a GridLayoutCache."""
        cache = GridLayoutCache(
            row_heights=[10, 20, 15],
            col_widths=[30, 40, 25],
            row_positions=[0, 10, 30],
            col_positions=[0, 30, 70],
        )
        assert cache.row_heights == [10, 20, 15]
        assert cache.col_widths == [30, 40, 25]
        assert cache.row_positions == [0, 10, 30]
        assert cache.col_positions == [0, 30, 70]

    def test_grid_layout_cache_empty(self):
        """Test GridLayoutCache with empty lists."""
        cache = GridLayoutCache(
            row_heights=[],
            col_widths=[],
            row_positions=[],
            col_positions=[],
        )
        assert cache.row_heights == []
        assert cache.col_widths == []


# =============================================================================
# PlaceLayoutEngine Tests
# =============================================================================


class TestPlaceLayoutEngine:
    """Tests for the PlaceLayoutEngine class."""

    def _create_mock_widget(
        self,
        x: int = 0,
        y: int = 0,
        relx: float = 0.0,
        rely: float = 0.0,
        width: int | None = None,
        height: int | None = None,
        relwidth: float | None = None,
        relheight: float | None = None,
        anchor: str = "nw",
        bordermode: str = "inside",
    ):
        """Create a mock widget with place options."""
        widget = MagicMock()
        widget._place_info = {
            "x": x,
            "y": y,
            "relx": relx,
            "rely": rely,
            "width": width,
            "height": height,
            "relwidth": relwidth,
            "relheight": relheight,
            "anchor": anchor,
            "bordermode": bordermode,
        }
        widget._get_natural_size.return_value = Size(10, 5)
        return widget

    def test_place_absolute_position(self):
        """Test placing widget at absolute x, y coordinates."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(x=10, y=5)

        results = PlaceLayoutEngine.calculate([widget], bounds)

        assert widget in results
        result = results[widget]
        assert result.x == 10
        assert result.y == 5

    def test_place_relative_position(self):
        """Test placing widget at relative position."""
        bounds = Rect(x=0, y=0, width=100, height=100)
        widget = self._create_mock_widget(relx=0.5, rely=0.5)

        results = PlaceLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # relx=0.5 on 100 width = 50
        assert result.x == 50
        # rely=0.5 on 100 height = 50
        assert result.y == 50

    def test_place_combined_position(self):
        """Test placing widget with both absolute and relative position."""
        bounds = Rect(x=0, y=0, width=100, height=100)
        widget = self._create_mock_widget(x=10, y=5, relx=0.5, rely=0.5)

        results = PlaceLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # x=10 + relx=0.5*100=50 = 60
        assert result.x == 60
        # y=5 + rely=0.5*100=50 = 55
        assert result.y == 55

    def test_place_explicit_size(self):
        """Test placing widget with explicit width and height."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(width=20, height=10)

        results = PlaceLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        assert result.width == 20
        assert result.height == 10

    def test_place_relative_size(self):
        """Test placing widget with relative width and height."""
        bounds = Rect(x=0, y=0, width=100, height=100)
        widget = self._create_mock_widget(relwidth=0.5, relheight=0.25)

        results = PlaceLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        assert result.width == 50  # 0.5 * 100
        assert result.height == 25  # 0.25 * 100

    def test_place_natural_size_fallback(self):
        """Test that natural size is used when no size specified."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget()  # No explicit size

        results = PlaceLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # Should use natural size from _get_natural_size
        assert result.width == 10
        assert result.height == 5

    def test_place_anchor_center(self):
        """Test placing widget with center anchor."""
        bounds = Rect(x=0, y=0, width=100, height=100)
        widget = self._create_mock_widget(x=50, y=50, width=20, height=10, anchor="center")

        results = PlaceLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # center anchor: x - width/2, y - height/2
        assert result.x == 40  # 50 - 20/2
        assert result.y == 45  # 50 - 10/2

    def test_place_anchor_ne(self):
        """Test placing widget with northeast anchor."""
        bounds = Rect(x=0, y=0, width=100, height=100)
        widget = self._create_mock_widget(x=50, y=50, width=20, height=10, anchor="ne")

        results = PlaceLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # ne anchor: x - width, y unchanged
        assert result.x == 30  # 50 - 20
        assert result.y == 50

    def test_place_anchor_sw(self):
        """Test placing widget with southwest anchor."""
        bounds = Rect(x=0, y=0, width=100, height=100)
        widget = self._create_mock_widget(x=50, y=50, width=20, height=10, anchor="sw")

        results = PlaceLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # sw anchor: x unchanged, y - height
        assert result.x == 50
        assert result.y == 40  # 50 - 10

    def test_place_anchor_se(self):
        """Test placing widget with southeast anchor."""
        bounds = Rect(x=0, y=0, width=100, height=100)
        widget = self._create_mock_widget(x=50, y=50, width=20, height=10, anchor="se")

        results = PlaceLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # se anchor: x - width, y - height
        assert result.x == 30  # 50 - 20
        assert result.y == 40  # 50 - 10

    def test_place_bounds_offset(self):
        """Test placing widget with non-zero bounds offset."""
        bounds = Rect(x=10, y=5, width=80, height=24)
        widget = self._create_mock_widget(x=5, y=3)

        results = PlaceLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # Position should be relative to bounds
        assert result.x == 15  # 10 + 5
        assert result.y == 8   # 5 + 3

    def test_place_clamp_to_bounds(self):
        """Test that widget is clamped to bounds."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(x=100, y=50, width=20, height=10)

        results = PlaceLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # Should be clamped to fit within bounds
        assert result.x <= bounds.width - 1
        assert result.y <= bounds.height - 1

    def test_place_multiple_widgets(self):
        """Test placing multiple widgets."""
        bounds = Rect(x=0, y=0, width=100, height=100)
        widget1 = self._create_mock_widget(x=10, y=10)
        widget2 = self._create_mock_widget(x=50, y=50)

        results = PlaceLayoutEngine.calculate([widget1, widget2], bounds)

        assert len(results) == 2
        assert results[widget1].x == 10
        assert results[widget2].x == 50

    def test_place_empty_list(self):
        """Test placing empty widget list."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        results = PlaceLayoutEngine.calculate([], bounds)
        assert results == {}


# =============================================================================
# PackLayoutEngine Tests
# =============================================================================


class TestPackLayoutEngine:
    """Tests for the PackLayoutEngine class."""

    def _create_mock_widget(
        self,
        side: str = "top",
        fill: str = "none",
        expand: int = 0,
        anchor: str = "center",
        padx: int = 0,
        pady: int = 0,
        ipadx: int = 0,
        ipady: int = 0,
        natural_width: int = 10,
        natural_height: int = 5,
    ):
        """Create a mock widget with pack options."""
        widget = MagicMock()
        widget._pack_info = {
            "side": side,
            "fill": fill,
            "expand": expand,
            "anchor": anchor,
            "padx": padx,
            "pady": pady,
            "ipadx": ipadx,
            "ipady": ipady,
        }
        widget._get_natural_size.return_value = Size(natural_width, natural_height)
        return widget

    def test_pack_single_widget_top(self):
        """Test packing single widget to top."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(side="top")

        results = PackLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        assert result.y == 0  # Packed at top
        assert result.height == 5  # Natural height

    def test_pack_single_widget_bottom(self):
        """Test packing single widget to bottom."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(side="bottom")

        results = PackLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        assert result.y == 24 - 5  # Packed at bottom
        assert result.height == 5

    def test_pack_single_widget_left(self):
        """Test packing single widget to left."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(side="left")

        results = PackLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        assert result.x == 0  # Packed at left
        assert result.width == 10  # Natural width

    def test_pack_single_widget_right(self):
        """Test packing single widget to right."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(side="right")

        results = PackLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        assert result.x == 80 - 10  # Packed at right
        assert result.width == 10

    def test_pack_fill_x(self):
        """Test packing widget with fill='x'."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(side="top", fill="x")

        results = PackLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        assert result.width == 80  # Fills horizontally
        assert result.height == 5  # Natural height

    def test_pack_fill_y(self):
        """Test packing widget with fill='y'."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(side="left", fill="y")

        results = PackLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        assert result.width == 10  # Natural width
        assert result.height == 24  # Fills vertically

    def test_pack_fill_both(self):
        """Test packing widget with fill='both'."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(side="top", fill="both", expand=1)

        results = PackLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        assert result.width == 80  # Fills horizontally
        # With expand, fills vertically too
        assert result.height == 24

    def test_pack_expand(self):
        """Test packing widget with expand=1."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(side="top", expand=1)

        results = PackLayoutEngine.calculate([widget], bounds)

        # Expand should give extra space
        result = results[widget]
        assert result.height == 24  # Expands to fill

    def test_pack_padding(self):
        """Test packing widget with padding."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(side="top", padx=5, pady=3)

        results = PackLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # Padding adds space around widget
        assert result.x >= 5
        assert result.y >= 3

    def test_pack_ipadding(self):
        """Test packing widget with internal padding."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(side="top", ipadx=5, ipady=3)

        results = PackLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # Internal padding increases widget size
        assert result.width == 10 + 2 * 5  # natural + 2*ipadx
        assert result.height == 5 + 2 * 3  # natural + 2*ipady

    def test_pack_multiple_top(self):
        """Test packing multiple widgets to top."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        w1 = self._create_mock_widget(side="top", natural_height=5)
        w2 = self._create_mock_widget(side="top", natural_height=3)
        w3 = self._create_mock_widget(side="top", natural_height=4)

        results = PackLayoutEngine.calculate([w1, w2, w3], bounds)

        # Widgets stack from top
        assert results[w1].y == 0
        assert results[w2].y == 5
        assert results[w3].y == 8

    def test_pack_multiple_left(self):
        """Test packing multiple widgets to left."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        w1 = self._create_mock_widget(side="left", natural_width=10)
        w2 = self._create_mock_widget(side="left", natural_width=15)
        w3 = self._create_mock_widget(side="left", natural_width=8)

        results = PackLayoutEngine.calculate([w1, w2, w3], bounds)

        # Widgets stack from left
        assert results[w1].x == 0
        assert results[w2].x == 10
        assert results[w3].x == 25

    def test_pack_mixed_sides(self):
        """Test packing widgets to different sides."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        top_widget = self._create_mock_widget(side="top", natural_height=5)
        left_widget = self._create_mock_widget(side="left", natural_width=20)

        results = PackLayoutEngine.calculate([top_widget, left_widget], bounds)

        # Top widget takes from top first
        assert results[top_widget].y == 0
        # Left widget placed in remaining cavity (y=5 to y=24, height=19)
        # With default anchor='center', widget is vertically centered: 5 + (19-5)/2 = 12
        assert results[left_widget].y == 12  # Centered in remaining cavity

    def test_pack_anchor_n(self):
        """Test packing widget with north anchor."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(side="top", anchor="n")

        results = PackLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # Widget centered horizontally, at top of cavity
        assert result.x == (80 - 10) // 2

    def test_pack_anchor_w(self):
        """Test packing widget with west anchor."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(side="top", anchor="w")

        results = PackLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # Widget at left of cavity
        assert result.x == 0

    def test_pack_anchor_e(self):
        """Test packing widget with east anchor."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(side="top", anchor="e")

        results = PackLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # Widget at right of cavity
        assert result.x == 80 - 10

    def test_pack_expand_distributes_space(self):
        """Test that expand distributes extra space among expanding widgets."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        w1 = self._create_mock_widget(side="top", expand=1, natural_height=5)
        w2 = self._create_mock_widget(side="top", expand=1, natural_height=5)

        results = PackLayoutEngine.calculate([w1, w2], bounds)

        # Extra space (24 - 10 = 14) distributed between 2 widgets
        # Each gets 14/2 = 7 extra
        total_height = results[w1].height + results[w2].height
        assert total_height == 24

    def test_pack_empty_list(self):
        """Test packing empty widget list."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        results = PackLayoutEngine.calculate([], bounds)
        assert results == {}

    def test_pack_bounds_offset(self):
        """Test packing with non-zero bounds offset."""
        bounds = Rect(x=10, y=5, width=60, height=20)
        widget = self._create_mock_widget(side="top")

        results = PackLayoutEngine.calculate([widget], bounds)

        result = results[widget]
        # Should be positioned relative to bounds
        assert result.y >= 5


# =============================================================================
# GridLayoutEngine Tests
# =============================================================================


class TestGridLayoutEngine:
    """Tests for the GridLayoutEngine class."""

    def _create_mock_widget(
        self,
        row: int = 0,
        column: int = 0,
        rowspan: int = 1,
        columnspan: int = 1,
        sticky: str = "",
        padx: int = 0,
        pady: int = 0,
        ipadx: int = 0,
        ipady: int = 0,
        natural_width: int = 10,
        natural_height: int = 5,
    ):
        """Create a mock widget with grid options."""
        widget = MagicMock()
        widget._grid_info = {
            "row": row,
            "column": column,
            "rowspan": rowspan,
            "columnspan": columnspan,
            "sticky": sticky,
            "padx": padx,
            "pady": pady,
            "ipadx": ipadx,
            "ipady": ipady,
        }
        widget._get_natural_size.return_value = Size(natural_width, natural_height)
        return widget

    def test_grid_single_widget(self):
        """Test placing single widget in grid."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(row=0, column=0)

        results, cache = GridLayoutEngine.calculate([widget], bounds, {}, {})

        assert widget in results
        result = results[widget]
        assert result.x == 0
        assert result.y == 0

    def test_grid_multiple_rows(self):
        """Test placing widgets in multiple rows."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        w1 = self._create_mock_widget(row=0, column=0, natural_height=5)
        w2 = self._create_mock_widget(row=1, column=0, natural_height=3)
        w3 = self._create_mock_widget(row=2, column=0, natural_height=4)

        results, cache = GridLayoutEngine.calculate([w1, w2, w3], bounds, {}, {})

        # Widgets in different rows
        assert results[w1].y == 0
        assert results[w2].y == 5  # After first row
        assert results[w3].y == 8  # After first two rows

    def test_grid_multiple_columns(self):
        """Test placing widgets in multiple columns."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        w1 = self._create_mock_widget(row=0, column=0, natural_width=10)
        w2 = self._create_mock_widget(row=0, column=1, natural_width=15)
        w3 = self._create_mock_widget(row=0, column=2, natural_width=8)

        results, cache = GridLayoutEngine.calculate([w1, w2, w3], bounds, {}, {})

        # Widgets in different columns
        assert results[w1].x == 0
        assert results[w2].x == 10  # After first column
        assert results[w3].x == 25  # After first two columns

    def test_grid_cell_matrix(self):
        """Test placing widgets in a 2x2 grid."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        w00 = self._create_mock_widget(row=0, column=0)
        w01 = self._create_mock_widget(row=0, column=1)
        w10 = self._create_mock_widget(row=1, column=0)
        w11 = self._create_mock_widget(row=1, column=1)

        results, _ = GridLayoutEngine.calculate(
            [w00, w01, w10, w11], bounds, {}, {}
        )

        # Check relative positions
        assert results[w01].x > results[w00].x
        assert results[w10].y > results[w00].y
        assert results[w11].x > results[w10].x
        assert results[w11].y > results[w01].y

    def test_grid_rowspan(self):
        """Test widget spanning multiple rows."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        # sticky='ns' needed for widget to fill spanned rows (otherwise centers)
        w1 = self._create_mock_widget(row=0, column=0, rowspan=2, sticky="ns", natural_height=5)
        w2 = self._create_mock_widget(row=0, column=1, natural_height=5)
        w3 = self._create_mock_widget(row=1, column=1, natural_height=5)

        results, _ = GridLayoutEngine.calculate([w1, w2, w3], bounds, {}, {})

        # w1 spans both rows and fills them with sticky='ns'
        assert results[w1].height >= 10  # At least 2 rows

    def test_grid_columnspan(self):
        """Test widget spanning multiple columns."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        # sticky='ew' needed for widget to fill spanned columns (otherwise centers)
        w1 = self._create_mock_widget(row=0, column=0, columnspan=2, sticky="ew", natural_width=10)
        w2 = self._create_mock_widget(row=1, column=0, natural_width=10)
        w3 = self._create_mock_widget(row=1, column=1, natural_width=10)

        results, _ = GridLayoutEngine.calculate([w1, w2, w3], bounds, {}, {})

        # w1 spans both columns and fills them with sticky='ew'
        assert results[w1].width >= 20  # At least 2 columns

    def test_grid_sticky_nsew(self):
        """Test widget with sticky='nsew' fills cell."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(row=0, column=0, sticky="nsew")

        # weight=1 needed for cell to expand to fill bounds (otherwise cell is natural size)
        row_config = {0: {"weight": 1}}
        col_config = {0: {"weight": 1}}
        results, cache = GridLayoutEngine.calculate([widget], bounds, row_config, col_config)

        result = results[widget]
        # With weight, cell expands to bounds; with sticky='nsew', widget fills cell
        assert result.width == 80
        assert result.height == 24

    def test_grid_sticky_n(self):
        """Test widget with sticky='n' aligns to top."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(row=0, column=0, sticky="n")

        results, _ = GridLayoutEngine.calculate([widget], bounds, {}, {})

        result = results[widget]
        assert result.y == 0  # At top

    def test_grid_sticky_s(self):
        """Test widget with sticky='s' aligns to bottom."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(row=0, column=0, sticky="s")

        # weight=1 needed for cell to expand (otherwise cell is natural size)
        row_config = {0: {"weight": 1}}
        results, _ = GridLayoutEngine.calculate([widget], bounds, row_config, {})

        result = results[widget]
        assert result.y == 24 - 5  # At bottom of expanded cell

    def test_grid_sticky_e(self):
        """Test widget with sticky='e' aligns to right."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(row=0, column=0, sticky="e")

        # weight=1 needed for cell to expand (otherwise cell is natural size)
        col_config = {0: {"weight": 1}}
        results, _ = GridLayoutEngine.calculate([widget], bounds, {}, col_config)

        result = results[widget]
        assert result.x == 80 - 10  # At right of expanded cell

    def test_grid_sticky_w(self):
        """Test widget with sticky='w' aligns to left."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(row=0, column=0, sticky="w")

        results, _ = GridLayoutEngine.calculate([widget], bounds, {}, {})

        result = results[widget]
        assert result.x == 0  # At left

    def test_grid_sticky_ew(self):
        """Test widget with sticky='ew' fills width."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(row=0, column=0, sticky="ew")

        # weight=1 needed for cell to expand (otherwise cell is natural size)
        col_config = {0: {"weight": 1}}
        results, _ = GridLayoutEngine.calculate([widget], bounds, {}, col_config)

        result = results[widget]
        assert result.width == 80  # Fills horizontally (cell expanded with weight)
        assert result.height == 5  # Natural height

    def test_grid_sticky_ns(self):
        """Test widget with sticky='ns' fills height."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(row=0, column=0, sticky="ns")

        # weight=1 needed for cell to expand (otherwise cell is natural size)
        row_config = {0: {"weight": 1}}
        results, _ = GridLayoutEngine.calculate([widget], bounds, row_config, {})

        result = results[widget]
        assert result.width == 10  # Natural width
        assert result.height == 24  # Fills vertically (cell expanded with weight)

    def test_grid_row_weight(self):
        """Test row weight distributes extra space."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        w1 = self._create_mock_widget(row=0, column=0, sticky="nsew", natural_height=5)
        w2 = self._create_mock_widget(row=1, column=0, sticky="nsew", natural_height=5)

        row_config = {1: {"weight": 1}}

        results, _ = GridLayoutEngine.calculate([w1, w2], bounds, row_config, {})

        # Row 1 should get extra space
        assert results[w2].height > results[w1].height

    def test_grid_column_weight(self):
        """Test column weight distributes extra space."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        w1 = self._create_mock_widget(row=0, column=0, sticky="nsew", natural_width=10)
        w2 = self._create_mock_widget(row=0, column=1, sticky="nsew", natural_width=10)

        col_config = {1: {"weight": 1}}

        results, _ = GridLayoutEngine.calculate([w1, w2], bounds, {}, col_config)

        # Column 1 should get extra space
        assert results[w2].width > results[w1].width

    def test_grid_minsize(self):
        """Test minsize constraint on row/column."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(row=0, column=0, natural_width=10, natural_height=5)

        row_config = {0: {"minsize": 10}}
        col_config = {0: {"minsize": 20}}

        results, cache = GridLayoutEngine.calculate([widget], bounds, row_config, col_config)

        # Row and column should respect minsize
        assert cache.row_heights[0] >= 10
        assert cache.col_widths[0] >= 20

    def test_grid_padding(self):
        """Test grid padding."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(row=0, column=0, padx=5, pady=3)

        results, _ = GridLayoutEngine.calculate([widget], bounds, {}, {})

        result = results[widget]
        # Widget should be inset by padding
        assert result.x >= 5
        assert result.y >= 3

    def test_grid_ipadding(self):
        """Test grid internal padding."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = self._create_mock_widget(row=0, column=0, ipadx=5, ipady=3)

        results, _ = GridLayoutEngine.calculate([widget], bounds, {}, {})

        result = results[widget]
        # Internal padding increases widget size
        assert result.width >= 10 + 2 * 5
        assert result.height >= 5 + 2 * 3

    def test_grid_cache_populated(self):
        """Test that grid layout cache is populated correctly."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        w1 = self._create_mock_widget(row=0, column=0)
        w2 = self._create_mock_widget(row=1, column=1)

        _, cache = GridLayoutEngine.calculate([w1, w2], bounds, {}, {})

        assert len(cache.row_heights) >= 2
        assert len(cache.col_widths) >= 2
        assert len(cache.row_positions) >= 2
        assert len(cache.col_positions) >= 2

    def test_grid_empty_list(self):
        """Test grid with empty widget list."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        results, cache = GridLayoutEngine.calculate([], bounds, {}, {})

        assert results == {}
        assert cache.row_heights == []
        assert cache.col_widths == []

    def test_grid_bounds_offset(self):
        """Test grid with non-zero bounds offset."""
        bounds = Rect(x=10, y=5, width=60, height=20)
        widget = self._create_mock_widget(row=0, column=0)

        results, _ = GridLayoutEngine.calculate([widget], bounds, {}, {})

        result = results[widget]
        # Should be positioned relative to bounds
        assert result.x >= 10
        assert result.y >= 5


# =============================================================================
# LayoutManager Tests
# =============================================================================


class TestLayoutManager:
    """Tests for the LayoutManager class."""

    def test_mark_dirty(self):
        """Test marking a widget as needing layout."""
        widget = MagicMock()
        widget._layout_dirty = False
        widget._master = None

        LayoutManager.mark_dirty(widget)

        assert widget._layout_dirty is True

    def test_mark_dirty_propagates_to_parent(self):
        """Test that marking dirty propagates to parent."""
        parent = MagicMock()
        parent._layout_dirty = False
        parent._master = None

        child = MagicMock()
        child._layout_dirty = False
        child._master = parent

        LayoutManager.mark_dirty(child)

        assert child._layout_dirty is True
        assert parent._layout_dirty is True

    def test_mark_all_dirty(self):
        """Test marking entire widget tree as dirty."""
        root = MagicMock()
        root._layout_dirty = False
        root._children = []

        child1 = MagicMock()
        child1._layout_dirty = False
        child1._children = []
        root._children.append(child1)

        child2 = MagicMock()
        child2._layout_dirty = False
        child2._children = []
        root._children.append(child2)

        grandchild = MagicMock()
        grandchild._layout_dirty = False
        grandchild._children = []
        child1._children.append(grandchild)

        LayoutManager.mark_all_dirty(root)

        assert root._layout_dirty is True
        assert child1._layout_dirty is True
        assert child2._layout_dirty is True
        assert grandchild._layout_dirty is True

    def test_do_layout_calls_engine(self):
        """Test that do_layout triggers layout calculation."""
        widget = MagicMock()
        widget._layout_dirty = True
        widget._children = []
        # Set proper width/height for _get_content_bounds
        widget._allocated_width = 80
        widget._allocated_height = 24
        widget._allocated_x = 0
        widget._allocated_y = 0
        widget._has_border = False
        # Mock pack/grid/place slaves to return empty lists
        widget.pack_slaves.return_value = []
        widget.grid_slaves.return_value = []
        widget.place_slaves.return_value = []

        LayoutManager.do_layout(widget)

        # After layout, dirty flag should be cleared
        assert widget._layout_dirty is False

    def test_do_layout_skips_clean_widgets(self):
        """Test that do_layout skips widgets that aren't dirty."""
        widget = MagicMock()
        widget._layout_dirty = False
        widget._children = []

        LayoutManager.do_layout(widget)

        # When not dirty, layout should be skipped (early return)
        # So pack_slaves etc should not be called
        widget.pack_slaves.assert_not_called()


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestLayoutEdgeCases:
    """Tests for edge cases and error handling in layout."""

    def test_place_missing_info(self):
        """Test place layout with missing place_info."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = MagicMock()
        widget._place_info = None

        results = PlaceLayoutEngine.calculate([widget], bounds)

        # Should handle gracefully
        assert widget not in results or results[widget] is not None

    def test_pack_missing_info(self):
        """Test pack layout with missing pack_info."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = MagicMock()
        widget._pack_info = None
        widget._get_natural_size.return_value = Size(10, 5)

        results = PackLayoutEngine.calculate([widget], bounds)

        # Should handle gracefully (widget skipped or defaults used)
        # Implementation may vary

    def test_grid_missing_info(self):
        """Test grid layout with missing grid_info."""
        bounds = Rect(x=0, y=0, width=80, height=24)
        widget = MagicMock()
        widget._grid_info = None
        widget._get_natural_size.return_value = Size(10, 5)

        results, cache = GridLayoutEngine.calculate([widget], bounds, {}, {})

        # Should handle gracefully

    def test_zero_bounds(self):
        """Test layout with zero-size bounds."""
        bounds = Rect(x=0, y=0, width=0, height=0)

        place_widget = MagicMock()
        place_widget._place_info = {"x": 0, "y": 0}
        place_widget._get_natural_size.return_value = Size(10, 5)

        pack_widget = MagicMock()
        pack_widget._pack_info = {"side": "top"}
        pack_widget._get_natural_size.return_value = Size(10, 5)

        grid_widget = MagicMock()
        grid_widget._grid_info = {"row": 0, "column": 0}
        grid_widget._get_natural_size.return_value = Size(10, 5)

        # Should not crash
        PlaceLayoutEngine.calculate([place_widget], bounds)
        PackLayoutEngine.calculate([pack_widget], bounds)
        GridLayoutEngine.calculate([grid_widget], bounds, {}, {})

    def test_negative_bounds(self):
        """Test layout with negative position bounds."""
        bounds = Rect(x=-10, y=-5, width=80, height=24)

        widget = MagicMock()
        widget._place_info = {"x": 0, "y": 0}
        widget._get_natural_size.return_value = Size(10, 5)

        results = PlaceLayoutEngine.calculate([widget], bounds)

        # Should handle negative offset
        assert widget in results

    def test_large_widget_in_small_bounds(self):
        """Test widget larger than bounds."""
        bounds = Rect(x=0, y=0, width=10, height=5)

        widget = MagicMock()
        widget._place_info = {"x": 0, "y": 0, "width": 100, "height": 100}
        widget._get_natural_size.return_value = Size(100, 100)

        results = PlaceLayoutEngine.calculate([widget], bounds)

        # Widget may be clamped or allowed to overflow
        assert widget in results
