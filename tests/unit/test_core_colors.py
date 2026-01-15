"""Unit tests for tkcurses._core.colors module."""

import curses
from unittest.mock import patch, MagicMock

import pytest

from tkcurses._core.colors import (
    BASE_COLORS,
    EXTENDED_COLORS,
    hex_to_curses,
    ColorManager,
)


class TestBaseColors:
    """Tests for BASE_COLORS mapping."""

    def test_base_colors_exist(self):
        """BASE_COLORS should contain standard color names."""
        expected = ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']
        for color in expected:
            assert color in BASE_COLORS

    def test_base_colors_values(self):
        """BASE_COLORS should map to curses color indices."""
        assert BASE_COLORS['black'] == curses.COLOR_BLACK
        assert BASE_COLORS['white'] == curses.COLOR_WHITE

    def test_base_colors_count(self):
        """BASE_COLORS should have 8 entries."""
        assert len(BASE_COLORS) == 8


class TestExtendedColors:
    """Tests for EXTENDED_COLORS mapping."""

    def test_extended_colors_exist(self):
        """EXTENDED_COLORS should contain common color names."""
        # Sample of expected colors
        expected = ['gray', 'grey', 'orange', 'pink', 'purple', 'brown']
        for color in expected:
            assert color in EXTENDED_COLORS

    def test_extended_returns_tuples(self):
        """EXTENDED_COLORS should map to (color, attribute) tuples."""
        for color, value in EXTENDED_COLORS.items():
            assert isinstance(value, tuple)
            assert len(value) == 2
            color_val, attr_val = value
            assert 0 <= color_val <= 7  # Valid curses color
            assert isinstance(attr_val, int)  # Valid attribute


class TestHexToCurses:
    """Tests for hex_to_curses function."""

    def test_hex_black(self):
        """Black hex should map to curses black."""
        color, attr = hex_to_curses('#000000')
        assert color == curses.COLOR_BLACK

    def test_hex_white(self):
        """White hex should map to curses white."""
        color, attr = hex_to_curses('#FFFFFF')
        assert color == curses.COLOR_WHITE
        color2, attr2 = hex_to_curses('#ffffff')
        assert color2 == curses.COLOR_WHITE

    def test_hex_red(self):
        """Red hex should map to curses red."""
        color, attr = hex_to_curses('#FF0000')
        assert color == curses.COLOR_RED

    def test_hex_green(self):
        """Green hex should map to curses green."""
        color, attr = hex_to_curses('#00FF00')
        assert color == curses.COLOR_GREEN

    def test_hex_blue(self):
        """Blue hex should map to curses blue."""
        color, attr = hex_to_curses('#0000FF')
        assert color == curses.COLOR_BLUE

    def test_returns_tuple(self):
        """hex_to_curses should return (color, attribute) tuple."""
        result = hex_to_curses('#FF0000')
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_brightness_affects_attr(self):
        """Brightness should affect the returned attribute."""
        # Very bright -> A_BOLD
        _, attr_bright = hex_to_curses('#FFFFFF')
        assert attr_bright == curses.A_BOLD

        # Very dark -> A_DIM
        _, attr_dark = hex_to_curses('#000000')
        assert attr_dark == curses.A_DIM

        # Medium brightness -> A_NORMAL
        _, attr_mid = hex_to_curses('#808080')
        assert attr_mid in [curses.A_NORMAL, curses.A_DIM]  # Gray is a special case


class TestColorManager:
    """Tests for ColorManager class."""

    @pytest.fixture
    def manager(self):
        """Create a ColorManager instance."""
        return ColorManager()

    def test_creation(self, manager):
        """ColorManager should initialize correctly."""
        assert manager is not None
        assert manager._next_pair == 1

    def test_name_to_curses_base(self, manager):
        """name_to_curses should handle base color names."""
        color, attr = manager.name_to_curses('black')
        assert color == curses.COLOR_BLACK

        color, attr = manager.name_to_curses('red')
        assert color == curses.COLOR_RED

        color, attr = manager.name_to_curses('white')
        assert color == curses.COLOR_WHITE

    def test_name_to_curses_extended(self, manager):
        """name_to_curses should handle extended color names."""
        # Gray maps to (COLOR_WHITE, A_DIM)
        color, attr = manager.name_to_curses('gray')
        assert color == curses.COLOR_WHITE
        assert attr == curses.A_DIM

    def test_name_to_curses_case_insensitive(self, manager):
        """name_to_curses should be case-insensitive."""
        result1 = manager.name_to_curses('RED')
        result2 = manager.name_to_curses('red')
        assert result1 == result2

        result3 = manager.name_to_curses('Blue')
        result4 = manager.name_to_curses('blue')
        assert result3 == result4

    def test_name_to_curses_returns_tuple(self, manager):
        """name_to_curses should return (color, attribute) tuple."""
        result = manager.name_to_curses('red')
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_name_to_curses_default(self, manager):
        """name_to_curses should return white for unknown colors."""
        color, attr = manager.name_to_curses('unknown_color')
        assert color == curses.COLOR_WHITE
        assert attr == curses.A_NORMAL

    def test_get_pair_with_mock(self, manager):
        """get_pair should create color pairs using curses."""
        with patch('tkcurses._core.colors.curses') as mock_curses:
            mock_curses.COLOR_BLACK = 0
            mock_curses.COLOR_WHITE = 7
            mock_curses.COLOR_RED = 1
            mock_curses.init_pair = MagicMock()
            mock_curses.color_pair = MagicMock(return_value=256)

            pair = manager.get_pair(1, 0)  # red on black

            mock_curses.init_pair.assert_called_once_with(1, 1, 0)
            mock_curses.color_pair.assert_called_once_with(1)
            assert pair == 256

    def test_get_pair_caches_with_mock(self, manager):
        """get_pair should cache and reuse pairs."""
        with patch('tkcurses._core.colors.curses') as mock_curses:
            mock_curses.init_pair = MagicMock()
            mock_curses.color_pair = MagicMock(return_value=256)

            pair1 = manager.get_pair(1, 0)
            pair2 = manager.get_pair(1, 0)

            # Should only call init_pair once for the same combination
            assert mock_curses.init_pair.call_count == 1
            assert pair1 == pair2

    def test_get_pair_different_orders_with_mock(self, manager):
        """get_pair should differentiate fg/bg order."""
        with patch('tkcurses._core.colors.curses') as mock_curses:
            mock_curses.init_pair = MagicMock()
            mock_curses.color_pair = MagicMock(side_effect=lambda x: x * 256)

            pair1 = manager.get_pair(1, 0)  # red on black
            pair2 = manager.get_pair(0, 1)  # black on red

            # Should create two different pairs
            assert mock_curses.init_pair.call_count == 2
            # Different pair numbers
            assert manager._pairs[(1, 0)] != manager._pairs[(0, 1)]

    def test_reset(self, manager):
        """reset() should clear all registered pairs."""
        manager._pairs[(1, 0)] = 1
        manager._pairs[(0, 1)] = 2
        manager._next_pair = 3

        manager.reset()

        assert manager._pairs == {}
        assert manager._next_pair == 1
