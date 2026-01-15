"""Unit tests for tkcurses._core.input module."""

from unittest.mock import MagicMock, patch

import pytest


class TestInputHandlerImport:
    """Tests for InputHandler import and basic structure."""

    def test_input_handler_import(self):
        """InputHandler should be importable."""
        from tkcurses._core.input import InputHandler
        assert InputHandler is not None

    def test_key_map_exists(self):
        """KEY_MAP should be defined."""
        from tkcurses._core.input import KEY_MAP
        assert isinstance(KEY_MAP, dict)
        assert len(KEY_MAP) > 0

    def test_button_masks_exists(self):
        """BUTTON_MASKS should be defined."""
        from tkcurses._core.input import BUTTON_MASKS
        assert isinstance(BUTTON_MASKS, dict)
        assert len(BUTTON_MASKS) == 5  # Buttons 1-5


class TestInputHandlerWithMock:
    """Tests for InputHandler using mock curses."""

    @pytest.fixture
    def mock_curses_and_stdscr(self, mock_stdscr):
        """Set up mock curses with a mock stdscr."""
        with patch('tkcurses._core.input.curses') as mock_curses:
            # Set up constants
            mock_curses.ERR = -1
            mock_curses.KEY_MOUSE = 409
            mock_curses.KEY_RESIZE = 410
            mock_curses.KEY_UP = 259
            mock_curses.KEY_DOWN = 258
            mock_curses.ALL_MOUSE_EVENTS = 0x7ffffff
            mock_curses.REPORT_MOUSE_POSITION = 0x8000000
            mock_curses.BUTTON_SHIFT = 0x4
            mock_curses.BUTTON_CTRL = 0x2
            mock_curses.BUTTON_ALT = 0x1
            mock_curses.BUTTON1_PRESSED = 0x02
            mock_curses.BUTTON1_RELEASED = 0x01
            mock_curses.BUTTON1_CLICKED = 0x04
            mock_curses.BUTTON1_DOUBLE_CLICKED = 0x08
            mock_curses.BUTTON1_TRIPLE_CLICKED = 0x10
            mock_curses.LINES = 24
            mock_curses.COLS = 80

            # Set up functions
            mock_curses.mousemask.return_value = (0x7ffffff, 0)
            mock_curses.mouseinterval.return_value = 200

            yield mock_curses, mock_stdscr

    def test_input_handler_creation(self, mock_curses_and_stdscr):
        """InputHandler should be created with stdscr."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        from tkcurses._core.input import InputHandler

        handler = InputHandler(mock_stdscr)
        assert handler is not None

    def test_setup_enables_keypad(self, mock_curses_and_stdscr):
        """InputHandler should enable keypad mode."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        from tkcurses._core.input import InputHandler

        handler = InputHandler(mock_stdscr)
        mock_stdscr.keypad.assert_called_with(True)

    def test_setup_enables_nodelay(self, mock_curses_and_stdscr):
        """InputHandler should enable nodelay mode."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        from tkcurses._core.input import InputHandler

        handler = InputHandler(mock_stdscr)
        mock_stdscr.nodelay.assert_called_with(True)

    def test_setup_enables_mouse(self, mock_curses_and_stdscr):
        """InputHandler should enable mouse events."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        from tkcurses._core.input import InputHandler

        handler = InputHandler(mock_stdscr)
        mock_curses.mousemask.assert_called()

    def test_get_event_no_input(self, mock_curses_and_stdscr):
        """get_event() should return None when no input."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        mock_stdscr.getch.return_value = -1  # curses.ERR

        from tkcurses._core.input import InputHandler

        handler = InputHandler(mock_stdscr)
        event = handler.get_event()
        assert event is None

    def test_get_event_key(self, mock_curses_and_stdscr):
        """get_event() should return KeyEvent for key press."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        mock_stdscr.getch.return_value = ord('a')

        from tkcurses._core.input import InputHandler
        from tkcurses._core.events import KeyEvent

        handler = InputHandler(mock_stdscr)
        event = handler.get_event()

        assert isinstance(event, KeyEvent)
        assert event.keycode == ord('a')
        assert event.char == 'a'

    def test_get_event_special_key(self, mock_curses_and_stdscr):
        """get_event() should handle special keys."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        mock_stdscr.getch.return_value = 259  # KEY_UP

        from tkcurses._core.input import InputHandler
        from tkcurses._core.events import KeyEvent

        handler = InputHandler(mock_stdscr)
        event = handler.get_event()

        assert isinstance(event, KeyEvent)
        assert event.keysym == 'Up'
        assert event.char == ''

    def test_get_event_resize(self, mock_curses_and_stdscr):
        """get_event() should return ResizeEvent for KEY_RESIZE."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        mock_stdscr.getch.return_value = 410  # KEY_RESIZE
        mock_curses.COLS = 120
        mock_curses.LINES = 40

        from tkcurses._core.input import InputHandler
        from tkcurses._core.events import ResizeEvent

        handler = InputHandler(mock_stdscr)
        event = handler.get_event()

        assert isinstance(event, ResizeEvent)
        assert event.width == 120
        assert event.height == 40

    def test_keycode_to_keysym_printable(self, mock_curses_and_stdscr):
        """_keycode_to_keysym should handle printable characters."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        from tkcurses._core.input import InputHandler

        handler = InputHandler(mock_stdscr)

        assert handler._keycode_to_keysym(ord('a')) == 'a'
        assert handler._keycode_to_keysym(ord('Z')) == 'Z'
        assert handler._keycode_to_keysym(ord('5')) == '5'
        assert handler._keycode_to_keysym(ord(' ')) == ' '

    def test_keycode_to_keysym_ctrl(self, mock_curses_and_stdscr):
        """_keycode_to_keysym should handle Ctrl+key."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        from tkcurses._core.input import InputHandler

        handler = InputHandler(mock_stdscr)

        # Ctrl+A = 1, Ctrl+Z = 26
        assert handler._keycode_to_keysym(1) == 'Control-a'
        assert handler._keycode_to_keysym(26) == 'Control-z'

    def test_detect_key_modifiers_ctrl(self, mock_curses_and_stdscr):
        """_detect_key_modifiers should detect Ctrl."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        from tkcurses._core.input import InputHandler
        from tkcurses._core.events import MOD_CTRL

        handler = InputHandler(mock_stdscr)

        # Ctrl+A = 1
        mods = handler._detect_key_modifiers(1)
        assert mods & MOD_CTRL

    def test_configure_mouse(self, mock_curses_and_stdscr):
        """configure_mouse() should set mouseinterval."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        from tkcurses._core.input import InputHandler

        handler = InputHandler(mock_stdscr)
        result = handler.configure_mouse(click_interval=300)

        mock_curses.mouseinterval.assert_called_with(300)
        assert result == 300

    def test_configure_mouse_clamps(self, mock_curses_and_stdscr):
        """configure_mouse() should clamp interval to valid range."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        from tkcurses._core.input import InputHandler

        handler = InputHandler(mock_stdscr)

        # Too low
        handler.configure_mouse(click_interval=0)
        mock_curses.mouseinterval.assert_called_with(1)

        # Too high
        handler.configure_mouse(click_interval=5000)
        mock_curses.mouseinterval.assert_called_with(1000)

    def test_cleanup(self, mock_curses_and_stdscr):
        """cleanup() should reset state."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        from tkcurses._core.input import InputHandler

        handler = InputHandler(mock_stdscr)
        handler._drag_button = 1
        handler._drag_start = (10, 5)

        handler.cleanup()

        assert handler._drag_button == 0
        assert handler._drag_start == (0, 0)


class TestInputHandlerMouse:
    """Tests for InputHandler mouse event handling."""

    @pytest.fixture
    def mock_curses_and_stdscr(self, mock_stdscr):
        """Set up mock curses with mouse support."""
        with patch('tkcurses._core.input.curses') as mock_curses:
            # Set up constants
            mock_curses.ERR = -1
            mock_curses.KEY_MOUSE = 409
            mock_curses.KEY_RESIZE = 410
            mock_curses.ALL_MOUSE_EVENTS = 0x7ffffff
            mock_curses.REPORT_MOUSE_POSITION = 0x8000000
            mock_curses.BUTTON_SHIFT = 0x4
            mock_curses.BUTTON_CTRL = 0x2
            mock_curses.BUTTON_ALT = 0x1
            mock_curses.BUTTON1_PRESSED = 0x02
            mock_curses.BUTTON1_RELEASED = 0x01
            mock_curses.BUTTON1_CLICKED = 0x04
            mock_curses.BUTTON1_DOUBLE_CLICKED = 0x08
            mock_curses.BUTTON1_TRIPLE_CLICKED = 0x10
            mock_curses.BUTTON2_PRESSED = 0x80
            mock_curses.BUTTON2_RELEASED = 0x40
            mock_curses.BUTTON2_CLICKED = 0x100
            mock_curses.BUTTON2_DOUBLE_CLICKED = 0x200
            mock_curses.BUTTON2_TRIPLE_CLICKED = 0x400
            mock_curses.BUTTON3_PRESSED = 0x2000
            mock_curses.BUTTON3_RELEASED = 0x1000
            mock_curses.BUTTON3_CLICKED = 0x4000
            mock_curses.BUTTON3_DOUBLE_CLICKED = 0x8000
            mock_curses.BUTTON3_TRIPLE_CLICKED = 0x10000
            mock_curses.BUTTON4_PRESSED = 0x80000
            mock_curses.BUTTON4_RELEASED = 0x40000
            mock_curses.BUTTON4_CLICKED = 0x100000
            mock_curses.BUTTON4_DOUBLE_CLICKED = 0x200000
            mock_curses.BUTTON4_TRIPLE_CLICKED = 0x400000
            mock_curses.LINES = 24
            mock_curses.COLS = 80

            mock_curses.mousemask.return_value = (0x7ffffff, 0)
            mock_curses.mouseinterval.return_value = 200

            yield mock_curses, mock_stdscr

    def test_mouse_click(self, mock_curses_and_stdscr):
        """Mouse click should produce MouseEvent."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        mock_stdscr.getch.return_value = 409  # KEY_MOUSE
        mock_curses.getmouse.return_value = (0, 10, 5, 0, 0x04)  # BUTTON1_CLICKED

        from tkcurses._core.input import InputHandler
        from tkcurses._core.events import MouseEvent

        handler = InputHandler(mock_stdscr)
        event = handler.get_event()

        assert isinstance(event, MouseEvent)
        assert event.x == 10
        assert event.y == 5
        assert event.button == 1
        assert event.state == 'clicked'

    def test_mouse_double_click(self, mock_curses_and_stdscr):
        """Double click should produce MouseEvent with state='double'."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        mock_stdscr.getch.return_value = 409
        mock_curses.getmouse.return_value = (0, 15, 10, 0, 0x08)  # BUTTON1_DOUBLE_CLICKED

        from tkcurses._core.input import InputHandler
        from tkcurses._core.events import MouseEvent

        handler = InputHandler(mock_stdscr)
        event = handler.get_event()

        assert isinstance(event, MouseEvent)
        assert event.state == 'double'

    def test_mouse_with_shift(self, mock_curses_and_stdscr):
        """Mouse with Shift should set modifier."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        mock_stdscr.getch.return_value = 409
        # BUTTON1_CLICKED | BUTTON_SHIFT
        mock_curses.getmouse.return_value = (0, 10, 5, 0, 0x04 | 0x4)

        from tkcurses._core.input import InputHandler
        from tkcurses._core.events import MouseEvent, MOD_SHIFT

        handler = InputHandler(mock_stdscr)
        event = handler.get_event()

        assert isinstance(event, MouseEvent)
        assert event.modifiers & MOD_SHIFT

    def test_mouse_drag_start(self, mock_curses_and_stdscr):
        """Mouse press should start drag tracking."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr
        mock_stdscr.getch.return_value = 409
        mock_curses.getmouse.return_value = (0, 10, 5, 0, 0x02)  # BUTTON1_PRESSED

        from tkcurses._core.input import InputHandler

        handler = InputHandler(mock_stdscr)
        event = handler.get_event()

        assert handler._drag_button == 1
        assert handler._drag_start == (10, 5)
        assert event.drag_start == (10, 5)

    def test_mouse_drag_end(self, mock_curses_and_stdscr):
        """Mouse release should end drag with both positions."""
        mock_curses, mock_stdscr = mock_curses_and_stdscr

        from tkcurses._core.input import InputHandler

        handler = InputHandler(mock_stdscr)

        # Simulate press
        mock_stdscr.getch.return_value = 409
        mock_curses.getmouse.return_value = (0, 10, 5, 0, 0x02)  # PRESSED
        handler.get_event()

        # Simulate release at different position
        mock_curses.getmouse.return_value = (0, 30, 20, 0, 0x01)  # RELEASED
        event = handler.get_event()

        assert event.drag_start == (10, 5)
        assert event.drag_end == (30, 20)
        assert handler._drag_button == 0  # Drag ended
