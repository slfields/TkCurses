"""Layout engine implementations for TkCurses geometry managers.

This module provides the actual layout calculation algorithms for the
Pack, Grid, and Place geometry managers. Each engine calculates widget
positions and sizes based on configuration options and available space.

The layout system uses a two-phase approach:
1. Measure phase: Collect size requirements from children (bottom-up)
2. Arrange phase: Allocate space to children (top-down)

All coordinates are in character cell units (columns, rows), not pixels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from .geometry import Padding, Point, Rect, Size, align_in_rect, distribute_space

if TYPE_CHECKING:
    from .. import BaseWidget


@dataclass
class LayoutResult:
    """Result of layout calculation for a single widget.

    Attributes:
        x: X position (column) relative to parent content area.
        y: Y position (row) relative to parent content area.
        width: Allocated width in columns.
        height: Allocated height in rows.
    """

    x: int
    y: int
    width: int
    height: int

    def to_rect(self) -> Rect:
        """Convert to a Rect object."""
        return Rect(self.x, self.y, self.width, self.height)


@dataclass
class GridLayoutCache:
    """Cached grid layout information for grid_bbox() and grid_location().

    Attributes:
        col_widths: Width of each column.
        row_heights: Height of each row.
        col_positions: X position of each column start.
        row_positions: Y position of each row start.
    """

    col_widths: list[int] = field(default_factory=list)
    row_heights: list[int] = field(default_factory=list)
    col_positions: list[int] = field(default_factory=list)
    row_positions: list[int] = field(default_factory=list)


class _PlaceCalculator:
    """Internal helper for Place layout calculations."""

    def __init__(self, bounds: Rect) -> None:
        self.bounds = bounds

    def calculate_single(self, child: Any, info: dict[str, Any]) -> LayoutResult:
        """Calculate layout for a single placed widget."""
        # Determine parent area based on bordermode
        bordermode = info.get("bordermode", "inside")
        if bordermode == "inside":
            parent_rect = self.bounds
        else:
            parent_rect = self.bounds.outset(1)

        # Calculate position from x/y and relx/rely
        x = info.get("x", 0)
        y = info.get("y", 0)
        relx = info.get("relx", 0.0)
        rely = info.get("rely", 0.0)

        abs_x = parent_rect.x + x + int(relx * parent_rect.width)
        abs_y = parent_rect.y + y + int(rely * parent_rect.height)

        # Calculate size from width/height and relwidth/relheight
        width = info.get("width")
        height = info.get("height")
        relwidth = info.get("relwidth")
        relheight = info.get("relheight")

        if width is None:
            if relwidth is not None:
                width = int(relwidth * parent_rect.width)
            else:
                width = self._get_natural_width(child)

        if height is None:
            if relheight is not None:
                height = int(relheight * parent_rect.height)
            else:
                height = self._get_natural_height(child)

        # Ensure minimum size
        width = max(1, width)
        height = max(1, height)

        # Apply anchor offset
        anchor = info.get("anchor", "nw").lower()
        abs_x, abs_y = self._apply_anchor_offset(abs_x, abs_y, width, height, anchor)

        # Clamp to parent bounds
        abs_x = max(parent_rect.x, min(abs_x, parent_rect.right - width))
        abs_y = max(parent_rect.y, min(abs_y, parent_rect.bottom - height))

        return LayoutResult(abs_x, abs_y, width, height)

    def _get_natural_width(self, child: Any) -> int:
        """Get the natural width of a widget."""
        if hasattr(child, "_get_natural_size"):
            return child._get_natural_size().width
        return getattr(child, "_requested_width", None) or 10

    def _get_natural_height(self, child: Any) -> int:
        """Get the natural height of a widget."""
        if hasattr(child, "_get_natural_size"):
            return child._get_natural_size().height
        return getattr(child, "_requested_height", None) or 1

    def _apply_anchor_offset(
        self, x: int, y: int, width: int, height: int, anchor: str
    ) -> tuple[int, int]:
        """Apply anchor offset to position."""
        # Handle center specially since it contains 'e'
        if anchor == "center":
            return x - width // 2, y - height // 2

        # Horizontal adjustment
        if "e" in anchor and "w" not in anchor:
            x -= width
        elif "w" not in anchor:
            x -= width // 2

        # Vertical adjustment
        if "s" in anchor and "n" not in anchor:
            y -= height
        elif "n" not in anchor:
            y -= height // 2

        return x, y


class PlaceLayoutEngine:
    """Layout engine for the Place geometry manager.

    Place provides absolute and relative positioning. Widgets can be
    positioned using:
    - Absolute coordinates (x, y)
    - Relative coordinates (relx, rely) as fractions of parent size
    - Absolute size (width, height)
    - Relative size (relwidth, relheight) as fractions of parent size

    The anchor option determines which point of the widget is placed
    at the calculated position.

    Can be used as either:
    - Static method: PlaceLayoutEngine.calculate(widgets, bounds)
    - Instance: engine = PlaceLayoutEngine(container, bounds); engine.run()
    """

    @staticmethod
    def calculate(widgets: list, bounds: Rect) -> dict:
        """Calculate layout for a list of widgets (static method).

        This is the primary calculation method. Can be called directly
        without creating an engine instance.

        Args:
            widgets: List of widgets with _place_info attributes.
            bounds: Available area for layout.

        Returns:
            Dictionary mapping widgets to their calculated LayoutResult.
        """
        results: dict = {}
        calc = _PlaceCalculator(bounds)

        for widget in widgets:
            info = getattr(widget, "_place_info", None)
            if info is None:
                continue
            result = calc.calculate_single(widget, info)
            results[widget] = result

        return results

    def __init__(self, container: BaseWidget, bounds: Rect) -> None:
        """Initialize the Place layout engine.

        Args:
            container: Parent widget containing placed children.
            bounds: Available area for layout (content area of parent).
        """
        self.container = container
        self.bounds = bounds
        self.children = container.place_slaves()

    def run(self) -> dict[Any, LayoutResult]:
        """Calculate layout for all placed children (instance method).

        Returns:
            Dictionary mapping widgets to their calculated LayoutResult.
        """
        return PlaceLayoutEngine.calculate(self.children, self.bounds)


class _PackCalculator:
    """Internal helper for Pack layout calculations."""

    def __init__(self, bounds: Rect) -> None:
        self.bounds = bounds

    def calculate(self, widgets: list) -> dict:
        """Calculate layout for all packed widgets."""
        if not widgets:
            return {}

        results: dict = {}
        cavity = self.bounds

        # Measure all children to determine natural sizes
        measurements = self._measure_children(widgets)

        # Calculate extra space for expanding widgets
        expand_info = self._calculate_expand_info(widgets, measurements, cavity)

        # Allocate space for each child
        for child in widgets:
            info = getattr(child, "_pack_info", None)
            if info is None:
                continue

            side = info.get("side", "top").lower()

            # Get child's required size with internal padding
            ipadx = self._get_pad_value(info.get("ipadx", 0))
            ipady = self._get_pad_value(info.get("ipady", 0))
            nat_size = measurements[child]
            required_width = nat_size.width + 2 * ipadx
            required_height = nat_size.height + 2 * ipady

            # Add extra space if expanding
            if info.get("expand", 0):
                extra = expand_info.get(child, Size(0, 0))
                if side in ("top", "bottom"):
                    required_height += extra.height
                else:
                    required_width += extra.width

            # Get external padding
            padx = self._get_pad_value(info.get("padx", 0))
            pady = self._get_pad_value(info.get("pady", 0))

            # Carve cavity and get widget area
            widget_area, cavity = self._carve_cavity(
                cavity, side, required_width, required_height, padx, pady
            )

            # Apply fill option
            fill = info.get("fill", "none").lower()
            final_size = self._apply_fill(
                Size(required_width, required_height), widget_area, fill
            )

            # Apply anchor within widget area
            anchor = info.get("anchor", "center").lower()
            position = align_in_rect(final_size, widget_area, anchor)

            results[child] = LayoutResult(
                position.x, position.y, final_size.width, final_size.height
            )

        return results

    def _get_pad_value(self, pad: Any) -> int:
        """Convert padding value to integer."""
        if isinstance(pad, (list, tuple)):
            return int(pad[0]) if pad else 0
        return int(pad)

    def _measure_children(self, widgets: list) -> dict:
        """Measure natural size of each child."""
        measurements: dict = {}
        for child in widgets:
            if hasattr(child, "_get_natural_size"):
                measurements[child] = child._get_natural_size()
            else:
                w = getattr(child, "_requested_width", None) or 10
                h = getattr(child, "_requested_height", None) or 1
                measurements[child] = Size(w, h)
        return measurements

    def _calculate_expand_info(
        self, widgets: list, measurements: dict, cavity: Rect
    ) -> dict:
        """Calculate extra space distribution for expanding widgets."""
        expand_info: dict = {}
        expand_horizontal: list = []
        expand_vertical: list = []
        total_required_width = 0
        total_required_height = 0

        for child in widgets:
            info = getattr(child, "_pack_info", None)
            if info is None:
                continue

            side = info.get("side", "top").lower()
            size = measurements[child]
            ipadx = self._get_pad_value(info.get("ipadx", 0))
            ipady = self._get_pad_value(info.get("ipady", 0))
            padx = self._get_pad_value(info.get("padx", 0))
            pady = self._get_pad_value(info.get("pady", 0))

            if side in ("top", "bottom"):
                total_required_height += size.height + 2 * ipady + 2 * pady
                if info.get("expand", 0):
                    expand_vertical.append(child)
            else:
                total_required_width += size.width + 2 * ipadx + 2 * padx
                if info.get("expand", 0):
                    expand_horizontal.append(child)

        # Distribute extra space
        extra_width = max(0, cavity.width - total_required_width)
        extra_height = max(0, cavity.height - total_required_height)

        if expand_horizontal and extra_width > 0:
            shares = distribute_space(extra_width, len(expand_horizontal))
            for child, share in zip(expand_horizontal, shares):
                expand_info[child] = Size(share, 0)

        if expand_vertical and extra_height > 0:
            shares = distribute_space(extra_height, len(expand_vertical))
            for child, share in zip(expand_vertical, shares):
                existing = expand_info.get(child, Size(0, 0))
                expand_info[child] = Size(existing.width, share)

        return expand_info

    def _carve_cavity(
        self, cavity: Rect, side: str, width: int, height: int, padx: int, pady: int
    ) -> tuple[Rect, Rect]:
        """Carve space from cavity for a widget."""
        if side == "top":
            carve_height = height + 2 * pady
            widget_area = Rect(
                cavity.x + padx, cavity.y + pady, cavity.width - 2 * padx, height
            )
            new_cavity = Rect(
                cavity.x, cavity.y + carve_height,
                cavity.width, max(0, cavity.height - carve_height)
            )
        elif side == "bottom":
            carve_height = height + 2 * pady
            widget_area = Rect(
                cavity.x + padx, cavity.bottom - height - pady,
                cavity.width - 2 * padx, height
            )
            new_cavity = Rect(
                cavity.x, cavity.y, cavity.width, max(0, cavity.height - carve_height)
            )
        elif side == "left":
            carve_width = width + 2 * padx
            widget_area = Rect(
                cavity.x + padx, cavity.y + pady, width, cavity.height - 2 * pady
            )
            new_cavity = Rect(
                cavity.x + carve_width, cavity.y,
                max(0, cavity.width - carve_width), cavity.height
            )
        elif side == "right":
            carve_width = width + 2 * padx
            widget_area = Rect(
                cavity.right - width - padx, cavity.y + pady,
                width, cavity.height - 2 * pady
            )
            new_cavity = Rect(
                cavity.x, cavity.y, max(0, cavity.width - carve_width), cavity.height
            )
        else:
            return self._carve_cavity(cavity, "top", width, height, padx, pady)

        return widget_area, new_cavity

    def _apply_fill(self, size: Size, area: Rect, fill: str) -> Size:
        """Apply fill option to determine final size."""
        width = size.width
        height = size.height

        if fill in ("x", "both"):
            width = area.width
        if fill in ("y", "both"):
            height = area.height

        return Size(max(1, width), max(1, height))


class PackLayoutEngine:
    """Layout engine for the Pack geometry manager.

    Pack arranges widgets sequentially in one direction (top, bottom,
    left, right). It works by maintaining a "cavity" (remaining space)
    and carving out space for each widget in pack order.

    Features:
    - side: Direction to pack (top, bottom, left, right)
    - fill: Expand to fill cavity width/height (none, x, y, both)
    - expand: Take share of extra space when cavity has room
    - anchor: Position within allocated space (n, s, e, w, etc.)
    - padx/pady: External padding
    - ipadx/ipady: Internal padding (added to widget size)

    Can be used as either:
    - Static method: PackLayoutEngine.calculate(widgets, bounds)
    - Instance: engine = PackLayoutEngine(container, bounds); engine.run()
    """

    @staticmethod
    def calculate(widgets: list, bounds: Rect) -> dict:
        """Calculate layout for a list of widgets (static method).

        Args:
            widgets: List of widgets with _pack_info attributes.
            bounds: Available area for layout.

        Returns:
            Dictionary mapping widgets to their calculated LayoutResult.
        """
        calc = _PackCalculator(bounds)
        return calc.calculate(widgets)

    def __init__(self, container: BaseWidget, bounds: Rect) -> None:
        """Initialize the Pack layout engine.

        Args:
            container: Parent widget containing packed children.
            bounds: Available area for layout (content area of parent).
        """
        self.container = container
        self.bounds = bounds
        self.children = self._get_pack_order()

    def _get_pack_order(self) -> list[Any]:
        """Get children sorted by pack order (before/after options).

        Returns:
            List of children in pack order.
        """
        children = self.container.pack_slaves()
        if not children:
            return []

        # Build dependency graph for before/after
        # For now, use insertion order (before/after are rarely used)
        # TODO: Implement full before/after ordering if needed
        return children

    def run(self) -> dict[Any, LayoutResult]:
        """Calculate layout for all packed children (instance method).

        Returns:
            Dictionary mapping widgets to their calculated LayoutResult.
        """
        return PackLayoutEngine.calculate(self.children, self.bounds)


class _GridCalculator:
    """Internal helper for Grid layout calculations."""

    def __init__(
        self, bounds: Rect, row_config: dict, col_config: dict, num_rows: int, num_cols: int
    ) -> None:
        self.bounds = bounds
        self.row_config = row_config
        self.col_config = col_config
        self.num_rows = num_rows
        self.num_cols = num_cols

    def calculate(self, widgets: list) -> tuple[dict, GridLayoutCache]:
        """Calculate layout for all gridded widgets."""
        cache = GridLayoutCache()

        if not widgets or self.num_rows == 0 or self.num_cols == 0:
            return {}, cache

        # Calculate column widths and row heights
        col_widths = self._calculate_column_widths(widgets)
        row_heights = self._calculate_row_heights(widgets)

        # Distribute extra space by weights
        col_widths = self._distribute_extra_width(col_widths)
        row_heights = self._distribute_extra_height(row_heights)

        # Calculate cumulative positions
        col_positions = self._cumulative_positions(col_widths, self.bounds.x)
        row_positions = self._cumulative_positions(row_heights, self.bounds.y)

        # Update cache
        cache.col_widths = col_widths
        cache.row_heights = row_heights
        cache.col_positions = col_positions
        cache.row_positions = row_positions

        # Calculate position for each widget
        results: dict = {}
        for child in widgets:
            info = getattr(child, "_grid_info", None)
            if info is None:
                continue

            row = info.get("row", 0)
            col = info.get("column", 0)
            rowspan = info.get("rowspan", 1)
            colspan = info.get("columnspan", 1)

            # Ensure indices are in bounds
            if row >= self.num_rows or col >= self.num_cols:
                continue

            # Calculate cell bounds
            cell_x = col_positions[col]
            cell_y = row_positions[row]
            cell_w = sum(col_widths[col : col + colspan])
            cell_h = sum(row_heights[row : row + rowspan])
            cell_rect = Rect(cell_x, cell_y, cell_w, cell_h)

            # Apply external padding
            padx = self._get_pad_value(info.get("padx", 0))
            pady = self._get_pad_value(info.get("pady", 0))
            cell_rect = cell_rect.inset(Padding(padx, pady, padx, pady))

            # Get widget size with internal padding
            ipadx = self._get_pad_value(info.get("ipadx", 0))
            ipady = self._get_pad_value(info.get("ipady", 0))
            widget_size = self._get_widget_size(child)
            widget_size = Size(
                widget_size.width + 2 * ipadx, widget_size.height + 2 * ipady
            )

            # Apply sticky alignment
            sticky = info.get("sticky", "").lower()
            final_rect = self._apply_sticky(widget_size, cell_rect, sticky)

            results[child] = LayoutResult(
                final_rect.x, final_rect.y, final_rect.width, final_rect.height
            )

        return results, cache

    def _get_pad_value(self, pad: Any) -> int:
        """Convert padding value to integer."""
        if isinstance(pad, (list, tuple)):
            return int(pad[0]) if pad else 0
        return int(pad)

    def _get_widget_size(self, child: Any) -> Size:
        """Get the natural size of a widget."""
        if hasattr(child, "_get_natural_size"):
            return child._get_natural_size()
        w = getattr(child, "_requested_width", None) or 10
        h = getattr(child, "_requested_height", None) or 1
        return Size(w, h)

    def _calculate_column_widths(self, widgets: list) -> list[int]:
        """Calculate minimum width for each column."""
        widths = [0] * self.num_cols

        for child in widgets:
            info = getattr(child, "_grid_info", None)
            if info is None:
                continue

            col = info.get("column", 0)
            colspan = info.get("columnspan", 1)

            if colspan == 1 and col < self.num_cols:
                size = self._get_widget_size(child)
                padx = self._get_pad_value(info.get("padx", 0))
                ipadx = self._get_pad_value(info.get("ipadx", 0))
                widths[col] = max(widths[col], size.width + 2 * padx + 2 * ipadx)

        # Apply column minsize constraints
        for col, config in self.col_config.items():
            if col < self.num_cols:
                minsize = config.get("minsize", 0)
                widths[col] = max(widths[col], minsize)

        # Ensure minimum width of 1 for occupied columns
        for i in range(self.num_cols):
            if widths[i] == 0:
                widths[i] = 1

        return widths

    def _calculate_row_heights(self, widgets: list) -> list[int]:
        """Calculate minimum height for each row."""
        heights = [0] * self.num_rows

        for child in widgets:
            info = getattr(child, "_grid_info", None)
            if info is None:
                continue

            row = info.get("row", 0)
            rowspan = info.get("rowspan", 1)

            if rowspan == 1 and row < self.num_rows:
                size = self._get_widget_size(child)
                pady = self._get_pad_value(info.get("pady", 0))
                ipady = self._get_pad_value(info.get("ipady", 0))
                heights[row] = max(heights[row], size.height + 2 * pady + 2 * ipady)

        # Apply row minsize constraints
        for row, config in self.row_config.items():
            if row < self.num_rows:
                minsize = config.get("minsize", 0)
                heights[row] = max(heights[row], minsize)

        # Ensure minimum height of 1 for occupied rows
        for i in range(self.num_rows):
            if heights[i] == 0:
                heights[i] = 1

        return heights

    def _distribute_extra_width(self, widths: list[int]) -> list[int]:
        """Distribute extra width to columns based on weights."""
        total_width = sum(widths)
        extra = self.bounds.width - total_width

        if extra <= 0:
            return widths

        weights = []
        for col in range(self.num_cols):
            config = self.col_config.get(col, {})
            weights.append(config.get("weight", 0))

        total_weight = sum(weights)
        if total_weight == 0:
            return widths

        distribution = distribute_space(extra, self.num_cols, weights)
        return [w + d for w, d in zip(widths, distribution)]

    def _distribute_extra_height(self, heights: list[int]) -> list[int]:
        """Distribute extra height to rows based on weights."""
        total_height = sum(heights)
        extra = self.bounds.height - total_height

        if extra <= 0:
            return heights

        weights = []
        for row in range(self.num_rows):
            config = self.row_config.get(row, {})
            weights.append(config.get("weight", 0))

        total_weight = sum(weights)
        if total_weight == 0:
            return heights

        distribution = distribute_space(extra, self.num_rows, weights)
        return [h + d for h, d in zip(heights, distribution)]

    def _cumulative_positions(self, sizes: list[int], start: int) -> list[int]:
        """Calculate cumulative positions from sizes."""
        positions = []
        pos = start
        for size in sizes:
            positions.append(pos)
            pos += size
        return positions

    def _apply_sticky(self, widget_size: Size, cell: Rect, sticky: str) -> Rect:
        """Apply sticky alignment to position widget in cell."""
        if "e" in sticky and "w" in sticky:
            width = cell.width
        else:
            width = min(widget_size.width, cell.width)

        if "n" in sticky and "s" in sticky:
            height = cell.height
        else:
            height = min(widget_size.height, cell.height)

        if "w" in sticky:
            x = cell.x
        elif "e" in sticky:
            x = cell.right - width
        else:
            x = cell.x + (cell.width - width) // 2

        if "n" in sticky:
            y = cell.y
        elif "s" in sticky:
            y = cell.bottom - height
        else:
            y = cell.y + (cell.height - height) // 2

        return Rect(x, y, max(1, width), max(1, height))


class GridLayoutEngine:
    """Layout engine for the Grid geometry manager.

    Grid arranges widgets in a table structure with rows and columns.
    Each widget occupies one or more cells (via rowspan/columnspan).

    Features:
    - row/column: Position in grid
    - rowspan/columnspan: Span multiple cells
    - sticky: Align to cell edges (n, s, e, w combinations)
    - weight: Distribute extra space to rows/columns
    - minsize: Minimum row/column size
    - padx/pady: External padding
    - ipadx/ipady: Internal padding

    Can be used as either:
    - Static method: GridLayoutEngine.calculate(widgets, bounds, row_config, col_config)
    - Instance: engine = GridLayoutEngine(container, bounds); engine.run()
    """

    @staticmethod
    def calculate(
        widgets: list, bounds: Rect, row_config: dict, col_config: dict
    ) -> tuple[dict, GridLayoutCache]:
        """Calculate layout for a list of widgets (static method).

        Args:
            widgets: List of widgets with _grid_info attributes.
            bounds: Available area for layout.
            row_config: Row configuration dict (row index -> {weight, minsize}).
            col_config: Column configuration dict (col index -> {weight, minsize}).

        Returns:
            Tuple of (results dict, GridLayoutCache).
        """
        # Compute grid dimensions from widgets
        num_rows = 0
        num_cols = 0
        for widget in widgets:
            info = getattr(widget, "_grid_info", None)
            if info is None:
                continue
            row = info.get("row", 0)
            col = info.get("column", 0)
            rowspan = info.get("rowspan", 1)
            colspan = info.get("columnspan", 1)
            num_rows = max(num_rows, row + rowspan)
            num_cols = max(num_cols, col + colspan)

        calc = _GridCalculator(bounds, row_config, col_config, num_rows, num_cols)
        return calc.calculate(widgets)

    def __init__(self, container: BaseWidget, bounds: Rect) -> None:
        """Initialize the Grid layout engine.

        Args:
            container: Parent widget containing gridded children.
            bounds: Available area for layout (content area of parent).
        """
        self.container = container
        self.bounds = bounds
        self.children = container.grid_slaves()
        self.num_cols, self.num_rows = container.grid_size()

        # Cache for grid_bbox/grid_location
        self.cache = GridLayoutCache()

    def run(self) -> dict[Any, LayoutResult]:
        """Calculate layout for all gridded children (instance method).

        Returns:
            Dictionary mapping widgets to their calculated LayoutResult.
        """
        row_config = getattr(self.container, "_row_config", {})
        col_config = getattr(self.container, "_col_config", {})

        results, cache = GridLayoutEngine.calculate(
            self.children, self.bounds, row_config, col_config
        )

        # Update instance cache and store on container
        self.cache = cache
        self.container._grid_layout_cache = cache

        return results


class LayoutManager:
    """Coordinates layout calculation across the widget hierarchy.

    The LayoutManager provides static methods to:
    - Perform layout for a widget and its descendants
    - Apply layout results to curses windows
    - Handle layout triggering on resize events
    """

    @staticmethod
    def do_layout(widget: BaseWidget, force: bool = False) -> None:
        """Perform layout calculation for a widget and its descendants.

        This is the main entry point for layout calculation. It:
        1. Checks if layout is needed (dirty flag or force)
        2. Gets the widget's content bounds
        3. Runs appropriate layout engines for children
        4. Applies results to child widgets
        5. Recursively layouts descendants

        Args:
            widget: Widget to layout.
            force: If True, force layout even if not dirty.
        """
        # Check if layout is needed
        if not force and not getattr(widget, "_layout_dirty", True):
            return

        # Get content bounds for layout
        bounds = LayoutManager._get_content_bounds(widget)

        # Get children by geometry manager
        pack_children = (
            widget.pack_slaves() if hasattr(widget, "pack_slaves") else []
        )
        grid_children = (
            widget.grid_slaves() if hasattr(widget, "grid_slaves") else []
        )
        place_children = (
            widget.place_slaves() if hasattr(widget, "place_slaves") else []
        )

        # Layout pack children
        if pack_children:
            engine = PackLayoutEngine(widget, bounds)
            results = engine.run()
            LayoutManager._apply_results(results)

        # Layout grid children
        if grid_children:
            engine = GridLayoutEngine(widget, bounds)
            results = engine.run()
            LayoutManager._apply_results(results)

        # Layout place children (can overlap with pack/grid)
        if place_children:
            engine = PlaceLayoutEngine(widget, bounds)
            results = engine.run()
            LayoutManager._apply_results(results)

        # Clear dirty flag
        widget._layout_dirty = False

        # Recursively layout children
        children = getattr(widget, "_children", [])
        for child in children:
            LayoutManager.do_layout(child, force=False)

    @staticmethod
    def _get_content_bounds(widget: BaseWidget) -> Rect:
        """Get the content area bounds for a widget.

        The content area is the region available for child widgets,
        accounting for borders and other decorations.

        Args:
            widget: Widget to get content bounds for.

        Returns:
            Rect representing the content area.
        """
        # Get widget's allocated size
        width = getattr(widget, "_allocated_width", None)
        height = getattr(widget, "_allocated_height", None)
        x = getattr(widget, "_allocated_x", 0)
        y = getattr(widget, "_allocated_y", 0)

        # For Tk/Toplevel, use screen/window dimensions
        if width is None:
            width = getattr(widget, "_width", 80)
        if height is None:
            height = getattr(widget, "_height", 24)

        # Check if widget has a border
        has_border = getattr(widget, "_has_border", False)

        if has_border:
            # Content area is inset by 1 on all sides
            return Rect(x + 1, y + 1, max(1, width - 2), max(1, height - 2))
        else:
            return Rect(x, y, width, height)

    @staticmethod
    def _apply_results(results: dict[Any, LayoutResult]) -> None:
        """Apply layout results to widgets.

        Calls _allocate_size on each widget to update its curses window.

        Args:
            results: Dictionary mapping widgets to LayoutResult.
        """
        for widget, result in results.items():
            if hasattr(widget, "_allocate_size"):
                widget._allocate_size(
                    result.width, result.height, result.x, result.y
                )

    @staticmethod
    def mark_dirty(widget: BaseWidget) -> None:
        """Mark a widget and its ancestors as needing layout.

        Args:
            widget: Widget to mark dirty.
        """
        current: Optional[BaseWidget] = widget
        while current is not None:
            current._layout_dirty = True
            current = getattr(current, "_master", None)

    @staticmethod
    def mark_all_dirty(root: BaseWidget) -> None:
        """Mark entire widget tree as needing layout.

        Used when terminal is resized.

        Args:
            root: Root widget of the tree.
        """
        root._layout_dirty = True
        children = getattr(root, "_children", [])
        for child in children:
            LayoutManager.mark_all_dirty(child)
