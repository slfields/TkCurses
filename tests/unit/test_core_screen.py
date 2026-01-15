"""Unit tests for tkcurses._core.screen module."""

from unittest.mock import MagicMock, patch

import pytest


class TestCursesScreen:
    """Tests for CursesScreen class.

    Note: Since CursesScreen wraps the real curses module, most tests
    use mocking to avoid requiring a real terminal.
    """

    @pytest.fixture
    def mock_curses(self):
        """Create a mock curses module."""
        mock = MagicMock()
        mock.initscr.return_value = MagicMock()
        mock.LINES = 24
        mock.COLS = 80
        mock.has_colors.return_value = True
        mock.can_change_color.return_value = True
        mock.COLORS = 256
        mock.COLOR_PAIRS = 256
        return mock

    def test_screen_import(self):
        """CursesScreen should be importable."""
        from tkcurses._core.screen import CursesScreen
        assert CursesScreen is not None

    def test_screen_has_initialize(self):
        """CursesScreen should have initialize method."""
        from tkcurses._core.screen import CursesScreen
        assert hasattr(CursesScreen, 'initialize')

    def test_screen_has_cleanup(self):
        """CursesScreen should have cleanup method."""
        from tkcurses._core.screen import CursesScreen
        assert hasattr(CursesScreen, 'cleanup')

    def test_screen_context_manager(self):
        """CursesScreen should work as context manager."""
        from tkcurses._core.screen import CursesScreen
        assert hasattr(CursesScreen, '__enter__')
        assert hasattr(CursesScreen, '__exit__')

    def test_screen_width_property(self):
        """CursesScreen should have width property."""
        from tkcurses._core.screen import CursesScreen
        # Check the class has the property defined
        assert hasattr(CursesScreen, 'width')

    def test_screen_height_property(self):
        """CursesScreen should have height property."""
        from tkcurses._core.screen import CursesScreen
        assert hasattr(CursesScreen, 'height')

    def test_screen_has_colors_property(self):
        """CursesScreen should have has_colors property."""
        from tkcurses._core.screen import CursesScreen
        assert hasattr(CursesScreen, 'has_colors')


class TestCursesScreenWithMock:
    """Tests for CursesScreen using mock curses."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the CursesScreen singleton before each test."""
        from tkcurses._core.screen import CursesScreen
        CursesScreen._instance = None
        yield
        CursesScreen._instance = None

    @pytest.fixture
    def screen_class(self):
        """Get CursesScreen class with mocked curses."""
        # Import the module
        from tkcurses._core import screen as screen_module
        return screen_module.CursesScreen

    def test_initialize_calls_initscr(self, mock_stdscr):
        """initialize() should call curses.initscr()."""
        with patch('tkcurses._core.screen.curses') as mock_curses:
            mock_curses.initscr.return_value = mock_stdscr
            mock_curses.has_colors.return_value = True
            mock_curses.LINES = 24
            mock_curses.COLS = 80

            from tkcurses._core.screen import CursesScreen
            screen = CursesScreen()
            screen.initialize()

            mock_curses.initscr.assert_called_once()

    def test_cleanup_calls_endwin(self, mock_stdscr):
        """cleanup() should call curses.endwin()."""
        with patch('tkcurses._core.screen.curses') as mock_curses:
            mock_curses.initscr.return_value = mock_stdscr
            mock_curses.has_colors.return_value = True
            mock_curses.LINES = 24
            mock_curses.COLS = 80

            from tkcurses._core.screen import CursesScreen
            screen = CursesScreen()
            screen.initialize()
            screen.cleanup()

            mock_curses.endwin.assert_called()

    def test_context_manager_initializes_and_cleans(self, mock_stdscr):
        """Context manager should initialize and cleanup."""
        with patch('tkcurses._core.screen.curses') as mock_curses:
            mock_curses.initscr.return_value = mock_stdscr
            mock_curses.has_colors.return_value = True
            mock_curses.LINES = 24
            mock_curses.COLS = 80

            from tkcurses._core.screen import CursesScreen
            screen = CursesScreen()

            with screen:
                mock_curses.initscr.assert_called()

            mock_curses.endwin.assert_called()
