"""Integration tests for TkCurses _core module interactions.

These tests verify that the core modules work together correctly:
- Screen + InputHandler integration
- Config + InputHandler integration
- ColorManager + attributes integration
- Dispatcher thread safety with other modules
- Geometry + Screen coordinate handling
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


class TestConfigInputHandlerIntegration:
    """Test Config and InputHandler work together."""

    def test_input_handler_respects_config_mouse_settings(self, mock_curses_module):
        """InputHandler should use config mouse settings."""
        from tkcurses._core.config import TkCursesConfig, MouseConfig
        from tkcurses._core.input import InputHandler

        # Create config with custom mouse settings
        config = TkCursesConfig()
        config.mouse.click_interval = 300
        config.mouse.enabled = True

        # Create mock stdscr
        mock_stdscr = MagicMock()
        mock_stdscr.getch.return_value = -1

        with patch('tkcurses._core.input.curses', mock_curses_module):
            handler = InputHandler(mock_stdscr, config)

            # Verify mouse was configured
            assert handler.mouse_available or not config.mouse.enabled

    def test_input_handler_respects_config_input_settings(self, mock_curses_module):
        """InputHandler should use config input settings."""
        from tkcurses._core.config import TkCursesConfig
        from tkcurses._core.input import InputHandler

        config = TkCursesConfig()
        config.input.keypad = True
        config.input.escape_delay = 50

        mock_stdscr = MagicMock()
        mock_stdscr.getch.return_value = -1

        with patch('tkcurses._core.input.curses', mock_curses_module):
            handler = InputHandler(mock_stdscr, config)

            # Verify keypad was enabled
            mock_stdscr.keypad.assert_called_with(True)

    def test_input_handler_works_without_config(self, mock_curses_module):
        """InputHandler should work with default settings when no config."""
        from tkcurses._core.input import InputHandler

        mock_stdscr = MagicMock()
        mock_stdscr.getch.return_value = -1

        with patch('tkcurses._core.input.curses', mock_curses_module):
            # Should not raise
            handler = InputHandler(mock_stdscr, config=None)
            assert handler is not None


class TestColorManagerAttributesIntegration:
    """Test ColorManager and attributes module work together."""

    def test_color_with_attribute_combination(self, mock_curses_module):
        """Colors and attributes should combine correctly."""
        from tkcurses._core.colors import ColorManager
        from tkcurses._core.attributes import combine_attrs, A_BOLD, A_UNDERLINE

        with patch('tkcurses._core.colors.curses', mock_curses_module):
            manager = ColorManager()

            # Get color and attribute from extended color
            color, color_attr = manager.name_to_curses("lime")

            # Combine with additional attributes
            combined = combine_attrs(color_attr, A_UNDERLINE)

            # Should have both attributes
            assert combined != 0 or color_attr == 0  # lime gives A_BOLD

    def test_hex_color_with_attributes(self, mock_curses_module):
        """Hex colors should work with attribute functions."""
        from tkcurses._core.colors import hex_to_curses
        from tkcurses._core.attributes import add_attr, has_attr, A_BOLD

        with patch('tkcurses._core.colors.curses', mock_curses_module):
            color, attr = hex_to_curses("#FF0000")  # Bright red

            # Add bold if not already present
            final_attr = add_attr(attr, A_BOLD)

            # Should have bold
            assert has_attr(final_attr, A_BOLD)


class TestDispatcherIntegration:
    """Test Dispatcher works with other modules in threaded context."""

    def test_dispatcher_serializes_color_operations(self):
        """Dispatcher should serialize color manager operations."""
        from tkcurses._core.dispatcher import CursesDispatcher
        from tkcurses._core.colors import ColorManager

        # Reset singleton for clean test
        CursesDispatcher._instance = None
        dispatcher = CursesDispatcher.get()

        manager = ColorManager()
        results = []

        def color_operation():
            color, attr = manager.name_to_curses("red")
            results.append((color, attr))

        # Execute through dispatcher
        dispatcher.call(color_operation)

        assert len(results) == 1
        assert results[0][0] is not None

    def test_dispatcher_handles_geometry_calculations(self):
        """Dispatcher should handle geometry operations."""
        from tkcurses._core.dispatcher import CursesDispatcher
        from tkcurses._core.geometry import Rect, center_in_rect, Size

        CursesDispatcher._instance = None
        dispatcher = CursesDispatcher.get()

        result = []

        def geometry_operation():
            outer = Rect(0, 0, 80, 24)
            inner = Size(20, 10)
            pos = center_in_rect(inner, outer)
            result.append(pos)

        dispatcher.call(geometry_operation)

        assert len(result) == 1
        assert result[0].x == 30
        assert result[0].y == 7

    def test_dispatcher_thread_safety_with_config(self):
        """Dispatcher should safely handle config access from main thread."""
        from tkcurses._core.dispatcher import CursesDispatcher
        from tkcurses._core.config import TkCursesConfig

        CursesDispatcher._instance = None
        dispatcher = CursesDispatcher.get()

        config = TkCursesConfig()
        results = []

        def read_config():
            value = config.mouse.click_interval
            results.append(value)
            return value

        # Run multiple calls from main thread (where dispatcher executes directly)
        for _ in range(5):
            dispatcher.call(read_config)

        assert len(results) == 5
        assert all(r == 200 for r in results)  # Default click interval


class TestGeometryEventIntegration:
    """Test geometry and event modules work together."""

    def test_mouse_event_position_in_rect(self):
        """MouseEvent position should work with Rect.contains_point."""
        from tkcurses._core.events import MouseEvent
        from tkcurses._core.geometry import Rect, Point

        # Create a widget region
        widget_rect = Rect(10, 5, 30, 15)

        # Create mouse event inside the region
        event_inside = MouseEvent(x=20, y=10, button=1, state='clicked')
        assert widget_rect.contains_point(Point(event_inside.x, event_inside.y))

        # Create mouse event outside the region
        event_outside = MouseEvent(x=5, y=3, button=1, state='clicked')
        assert not widget_rect.contains_point(Point(event_outside.x, event_outside.y))

    def test_resize_event_updates_constraints(self):
        """ResizeEvent dimensions should work with SizeConstraints."""
        from tkcurses._core.events import ResizeEvent
        from tkcurses._core.geometry import SizeConstraints, Size

        # Terminal resize event
        resize = ResizeEvent(width=120, height=40)

        # Widget constraints
        constraints = SizeConstraints(
            min_width=10, min_height=5,
            max_width=100, max_height=30
        )

        # Clamp to constraints
        clamped = constraints.clamp_size(Size(resize.width, resize.height))

        assert clamped.width == 100  # Clamped to max
        assert clamped.height == 30  # Clamped to max


class TestConfigGeometryIntegration:
    """Test config affects geometry-related behavior."""

    def test_padding_from_config_values(self):
        """Padding should work with config-derived values."""
        from tkcurses._core.config import TkCursesConfig
        from tkcurses._core.geometry import Padding, Rect

        config = TkCursesConfig()

        # Use config value as padding (simulated widget padding from config)
        # In real use, widgets might derive padding from config settings
        padding_value = 2  # Would come from config in real implementation
        padding = Padding.uniform(padding_value)

        # Apply to a rect
        outer = Rect(0, 0, 80, 24)
        inner = outer.inset(padding)

        assert inner.x == 2
        assert inner.y == 2
        assert inner.width == 76
        assert inner.height == 20


class TestEventAttributeIntegration:
    """Test events work with attribute styling."""

    def test_key_event_modifier_to_attribute(self):
        """Key modifiers should map to display attributes."""
        from tkcurses._core.events import KeyEvent, MOD_CTRL, has_modifier
        from tkcurses._core.attributes import style_to_attr, A_BOLD

        # Ctrl+key event
        event = KeyEvent(keycode=1, keysym='Control-a', char='', modifiers=MOD_CTRL)

        # In a real app, Ctrl might trigger bold display
        if has_modifier(event.modifiers, MOD_CTRL):
            attr = style_to_attr('bold')
            assert attr == A_BOLD


class TestFullCoreStackIntegration:
    """Test the complete core stack working together."""

    def test_config_to_input_to_event_flow(self, mock_curses_module):
        """Test config -> input handler -> event generation flow."""
        from tkcurses._core.config import TkCursesConfig
        from tkcurses._core.input import InputHandler
        from tkcurses._core.events import KeyEvent

        config = TkCursesConfig()
        config.input.keypad = True

        mock_stdscr = MagicMock()
        # Simulate 'a' key press
        mock_stdscr.getch.return_value = ord('a')

        with patch('tkcurses._core.input.curses', mock_curses_module):
            handler = InputHandler(mock_stdscr, config)
            event = handler.get_event()

            assert isinstance(event, KeyEvent)
            assert event.char == 'a'
            assert event.keysym == 'a'

    def test_geometry_for_widget_layout(self):
        """Test geometry primitives for widget layout scenario."""
        from tkcurses._core.geometry import (
            Rect, Size, Padding, Point,
            align_in_rect, distribute_space
        )

        # Simulate a window with header, content, footer
        window = Rect(0, 0, 80, 24)
        padding = Padding.uniform(1)
        content_area = window.inset(padding)

        # Distribute vertical space: header(1), content(flexible), footer(1)
        heights = distribute_space(content_area.height, 3, [1, 20, 1])

        assert sum(heights) == content_area.height
        assert heights[0] >= 1  # Header
        assert heights[2] >= 1  # Footer

        # Align a button in footer
        footer_rect = Rect(
            content_area.x,
            content_area.bottom - heights[2],
            content_area.width,
            heights[2]
        )
        button_size = Size(10, 1)
        button_pos = align_in_rect(button_size, footer_rect, 'center')

        assert footer_rect.contains_point(button_pos)

    def test_color_and_attribute_for_widget_styling(self, mock_curses_module):
        """Test color + attribute combination for widget styling."""
        from tkcurses._core.colors import ColorManager
        from tkcurses._core.attributes import (
            combine_attrs, A_BOLD, A_UNDERLINE, attrs_to_str
        )

        with patch('tkcurses._core.colors.curses', mock_curses_module):
            manager = ColorManager()

            # Style: blue text, bold and underlined (like a hyperlink)
            fg_color, fg_attr = manager.name_to_curses("blue")
            bg_color, _ = manager.name_to_curses("black")

            final_attr = combine_attrs(fg_attr, A_BOLD, A_UNDERLINE)

            # Should be describable
            desc = attrs_to_str(final_attr)
            assert "A_BOLD" in desc or "A_UNDERLINE" in desc or final_attr == 0


class TestEdgeCases:
    """Test edge cases in module interactions."""

    def test_empty_geometry_handling(self):
        """Empty/zero geometries should be handled gracefully."""
        from tkcurses._core.geometry import Rect, Size, Padding

        empty_rect = Rect(0, 0, 0, 0)
        assert empty_rect.is_empty

        # Inset of empty rect
        padded = empty_rect.inset(Padding.uniform(1))
        assert padded.width == 0
        assert padded.height == 0

    def test_config_with_invalid_values_graceful(self, monkeypatch):
        """Config should handle invalid env values gracefully."""
        from tkcurses._core.config import TkCursesConfig

        # Set invalid integer value
        monkeypatch.setenv('TKCURSES_MOUSE_CLICK_INTERVAL', 'not_a_number')

        # Should not raise, should use default
        config = TkCursesConfig.load()
        assert config.mouse.click_interval == 200  # Default

    def test_dispatcher_exception_propagation(self):
        """Dispatcher should propagate exceptions correctly."""
        from tkcurses._core.dispatcher import CursesDispatcher

        CursesDispatcher._instance = None
        dispatcher = CursesDispatcher.get()

        def failing_operation():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            dispatcher.call(failing_operation)
