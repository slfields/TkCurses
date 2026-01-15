"""Pytest configuration and fixtures for TkCurses tests.

This module contains pytest fixtures used across the test suite,
including setup/teardown for curses-related test environments.

Since curses requires a real terminal, many tests use mock objects
to simulate curses behavior without requiring an actual terminal.
"""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Mock Curses Module
# =============================================================================

@dataclass
class MockCursesWindow:
    """Mock curses window for testing without a real terminal."""

    _height: int = 24
    _width: int = 80
    _keypad_enabled: bool = False
    _nodelay_enabled: bool = False
    _content: list[list[str]] = None
    _attrs: list[list[int]] = None
    _cursor_y: int = 0
    _cursor_x: int = 0
    _input_queue: list[int] = None

    def __post_init__(self) -> None:
        """Initialize content and attribute buffers."""
        if self._content is None:
            self._content = [[' ' for _ in range(self._width)] for _ in range(self._height)]
        if self._attrs is None:
            self._attrs = [[0 for _ in range(self._width)] for _ in range(self._height)]
        if self._input_queue is None:
            self._input_queue = []

    def getmaxyx(self) -> tuple[int, int]:
        """Return window dimensions (height, width)."""
        return (self._height, self._width)

    def keypad(self, flag: bool) -> None:
        """Enable/disable keypad mode."""
        self._keypad_enabled = flag

    def nodelay(self, flag: bool) -> None:
        """Enable/disable nodelay mode."""
        self._nodelay_enabled = flag

    def getch(self) -> int:
        """Get a character from input queue or return ERR."""
        if self._input_queue:
            return self._input_queue.pop(0)
        return -1  # curses.ERR

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        """Add a string at position."""
        for i, ch in enumerate(text):
            if 0 <= x + i < self._width and 0 <= y < self._height:
                self._content[y][x + i] = ch
                self._attrs[y][x + i] = attr

    def addch(self, y: int, x: int, ch: str | int, attr: int = 0) -> None:
        """Add a character at position."""
        if 0 <= x < self._width and 0 <= y < self._height:
            self._content[y][x] = chr(ch) if isinstance(ch, int) else ch
            self._attrs[y][x] = attr

    def move(self, y: int, x: int) -> None:
        """Move cursor to position."""
        self._cursor_y = y
        self._cursor_x = x

    def clear(self) -> None:
        """Clear the window."""
        self._content = [[' ' for _ in range(self._width)] for _ in range(self._height)]
        self._attrs = [[0 for _ in range(self._width)] for _ in range(self._height)]

    def refresh(self) -> None:
        """Refresh the window (no-op in mock)."""
        pass

    def erase(self) -> None:
        """Erase the window."""
        self.clear()

    def border(self, *args: Any) -> None:
        """Draw border (no-op in mock)."""
        pass

    def box(self, *args: Any) -> None:
        """Draw box (no-op in mock)."""
        pass

    def derwin(self, height: int, width: int, y: int, x: int) -> MockCursesWindow:
        """Create a derived window."""
        return MockCursesWindow(_height=height, _width=width)

    def subwin(self, height: int, width: int, y: int, x: int) -> MockCursesWindow:
        """Create a sub-window."""
        return MockCursesWindow(_height=height, _width=width)

    def queue_input(self, *chars: int) -> None:
        """Queue input characters for getch()."""
        self._input_queue.extend(chars)

    def get_content_at(self, y: int, x: int) -> str:
        """Get content at position (for testing)."""
        if 0 <= x < self._width and 0 <= y < self._height:
            return self._content[y][x]
        return ''


class MockCurses:
    """Mock curses module for testing without a real terminal."""

    # Error code
    ERR = -1
    OK = 0

    # Attribute constants
    A_NORMAL = 0
    A_STANDOUT = 1 << 8
    A_UNDERLINE = 1 << 9
    A_REVERSE = 1 << 10
    A_BLINK = 1 << 11
    A_DIM = 1 << 12
    A_BOLD = 1 << 13
    A_PROTECT = 1 << 14
    A_INVIS = 1 << 15
    A_ALTCHARSET = 1 << 16
    A_ITALIC = 1 << 23

    # Color constants
    COLOR_BLACK = 0
    COLOR_RED = 1
    COLOR_GREEN = 2
    COLOR_YELLOW = 3
    COLOR_BLUE = 4
    COLOR_MAGENTA = 5
    COLOR_CYAN = 6
    COLOR_WHITE = 7

    # Key constants
    KEY_UP = 259
    KEY_DOWN = 258
    KEY_LEFT = 260
    KEY_RIGHT = 261
    KEY_HOME = 262
    KEY_END = 360
    KEY_NPAGE = 338
    KEY_PPAGE = 339
    KEY_IC = 331
    KEY_DC = 330
    KEY_BACKSPACE = 263
    KEY_ENTER = 343
    KEY_BTAB = 353
    KEY_F1 = 265
    KEY_F2 = 266
    KEY_F3 = 267
    KEY_F4 = 268
    KEY_F5 = 269
    KEY_F6 = 270
    KEY_F7 = 271
    KEY_F8 = 272
    KEY_F9 = 273
    KEY_F10 = 274
    KEY_F11 = 275
    KEY_F12 = 276
    KEY_SHOME = 391
    KEY_SEND = 386
    KEY_SLEFT = 393
    KEY_SRIGHT = 402
    KEY_MOUSE = 409
    KEY_RESIZE = 410

    # Mouse button constants
    BUTTON1_PRESSED = 0x02
    BUTTON1_RELEASED = 0x01
    BUTTON1_CLICKED = 0x04
    BUTTON1_DOUBLE_CLICKED = 0x08
    BUTTON1_TRIPLE_CLICKED = 0x10
    BUTTON2_PRESSED = 0x80
    BUTTON2_RELEASED = 0x40
    BUTTON2_CLICKED = 0x100
    BUTTON2_DOUBLE_CLICKED = 0x200
    BUTTON2_TRIPLE_CLICKED = 0x400
    BUTTON3_PRESSED = 0x2000
    BUTTON3_RELEASED = 0x1000
    BUTTON3_CLICKED = 0x4000
    BUTTON3_DOUBLE_CLICKED = 0x8000
    BUTTON3_TRIPLE_CLICKED = 0x10000
    BUTTON4_PRESSED = 0x80000
    BUTTON4_RELEASED = 0x40000
    BUTTON4_CLICKED = 0x100000
    BUTTON4_DOUBLE_CLICKED = 0x200000
    BUTTON4_TRIPLE_CLICKED = 0x400000
    BUTTON_SHIFT = 0x4
    BUTTON_CTRL = 0x2
    BUTTON_ALT = 0x1
    ALL_MOUSE_EVENTS = 0x7ffffff
    REPORT_MOUSE_POSITION = 0x8000000

    # ACS characters (placeholders)
    ACS_ULCORNER = ord('+')
    ACS_URCORNER = ord('+')
    ACS_LLCORNER = ord('+')
    ACS_LRCORNER = ord('+')
    ACS_HLINE = ord('-')
    ACS_VLINE = ord('|')
    ACS_LTEE = ord('+')
    ACS_RTEE = ord('+')
    ACS_TTEE = ord('+')
    ACS_BTEE = ord('+')
    ACS_PLUS = ord('+')
    ACS_DIAMOND = ord('*')
    ACS_CKBOARD = ord('#')
    ACS_DEGREE = ord('o')
    ACS_PLMINUS = ord('+')
    ACS_BULLET = ord('*')
    ACS_LARROW = ord('<')
    ACS_RARROW = ord('>')
    ACS_UARROW = ord('^')
    ACS_DARROW = ord('v')
    ACS_BOARD = ord('#')
    ACS_LANTERN = ord('#')
    ACS_BLOCK = ord('#')
    ACS_S1 = ord('-')
    ACS_S3 = ord('-')
    ACS_S7 = ord('-')
    ACS_S9 = ord('-')
    ACS_LEQUAL = ord('<')
    ACS_GEQUAL = ord('>')
    ACS_NEQUAL = ord('!')
    ACS_PI = ord('p')
    ACS_STERLING = ord('L')

    # Module state
    LINES = 24
    COLS = 80
    _color_pairs: dict[int, tuple[int, int]] = {}
    _mouse_mask = 0
    _mouse_interval = 200
    _stdscr: MockCursesWindow | None = None
    _mouse_event: tuple[int, int, int, int, int] | None = None

    @classmethod
    def initscr(cls) -> MockCursesWindow:
        """Initialize the screen."""
        cls._stdscr = MockCursesWindow()
        return cls._stdscr

    @classmethod
    def endwin(cls) -> None:
        """End curses mode."""
        cls._stdscr = None

    @classmethod
    def noecho(cls) -> None:
        """Disable echo."""
        pass

    @classmethod
    def echo(cls) -> None:
        """Enable echo."""
        pass

    @classmethod
    def cbreak(cls) -> None:
        """Enable cbreak mode."""
        pass

    @classmethod
    def nocbreak(cls) -> None:
        """Disable cbreak mode."""
        pass

    @classmethod
    def raw(cls) -> None:
        """Enable raw mode."""
        pass

    @classmethod
    def noraw(cls) -> None:
        """Disable raw mode."""
        pass

    @classmethod
    def start_color(cls) -> None:
        """Initialize color support."""
        pass

    @classmethod
    def use_default_colors(cls) -> None:
        """Use default terminal colors."""
        pass

    @classmethod
    def has_colors(cls) -> bool:
        """Check if terminal supports colors."""
        return True

    @classmethod
    def can_change_color(cls) -> bool:
        """Check if colors can be changed."""
        return True

    @classmethod
    def init_pair(cls, pair_num: int, fg: int, bg: int) -> None:
        """Initialize a color pair."""
        cls._color_pairs[pair_num] = (fg, bg)

    @classmethod
    def color_pair(cls, pair_num: int) -> int:
        """Get the attribute for a color pair."""
        return pair_num << 8

    @classmethod
    def pair_content(cls, pair_num: int) -> tuple[int, int]:
        """Get the colors in a pair."""
        return cls._color_pairs.get(pair_num, (7, 0))

    @classmethod
    def mousemask(cls, mask: int) -> tuple[int, int]:
        """Set mouse event mask."""
        old_mask = cls._mouse_mask
        cls._mouse_mask = mask
        return (mask, old_mask)

    @classmethod
    def mouseinterval(cls, interval: int) -> int:
        """Set mouse click interval."""
        old = cls._mouse_interval
        cls._mouse_interval = interval
        return old

    @classmethod
    def getmouse(cls) -> tuple[int, int, int, int, int]:
        """Get mouse event."""
        if cls._mouse_event:
            event = cls._mouse_event
            cls._mouse_event = None
            return event
        raise Exception("No mouse event")

    @classmethod
    def queue_mouse_event(cls, id_: int, x: int, y: int, z: int, bstate: int) -> None:
        """Queue a mouse event for testing."""
        cls._mouse_event = (id_, x, y, z, bstate)

    @classmethod
    def update_lines_cols(cls) -> None:
        """Update LINES and COLS."""
        pass

    @classmethod
    def newwin(cls, height: int, width: int, y: int = 0, x: int = 0) -> MockCursesWindow:
        """Create a new window."""
        return MockCursesWindow(_height=height, _width=width)

    @classmethod
    def set_escdelay(cls, delay: int) -> None:
        """Set escape delay."""
        pass

    @classmethod
    def wrapper(cls, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Wrapper function for curses programs."""
        stdscr = cls.initscr()
        try:
            return func(stdscr, *args, **kwargs)
        finally:
            cls.endwin()

    # Error class
    class error(Exception):
        """Curses error exception."""
        pass


@pytest.fixture
def mock_curses():
    """Provide a mock curses module for testing.

    This fixture patches the curses module with a mock implementation
    that doesn't require a real terminal.
    """
    mock = MockCurses()
    # Reset state
    mock._color_pairs = {}
    mock._mouse_mask = 0
    mock._mouse_interval = 200
    mock._stdscr = None
    mock._mouse_event = None
    return mock


@pytest.fixture
def mock_stdscr():
    """Provide a MagicMock curses window (stdscr) for testing.

    This returns a MagicMock so tests can set return_value on methods.
    For tests needing the MockCursesWindow behavior, use mock_stdscr_window.
    """
    mock = MagicMock()
    mock.getmaxyx.return_value = (24, 80)
    mock.getch.return_value = -1  # curses.ERR
    return mock


@pytest.fixture
def mock_stdscr_window():
    """Provide a MockCursesWindow for testing with simulated behavior."""
    return MockCursesWindow()


@pytest.fixture
def mock_curses_module(mock_curses):
    """Patch the curses module with the mock for imports.

    Use this when testing modules that import curses directly.
    """
    with patch.dict('sys.modules', {'curses': mock_curses}):
        yield mock_curses


# =============================================================================
# Configuration Fixtures
# =============================================================================

@pytest.fixture
def sample_config():
    """Provide a sample configuration dictionary for testing."""
    return {
        "app_name": "TkCurses",
        "version": "0.1.0",
        "debug": False,
    }


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary directory for configuration files."""
    config_dir = tmp_path / "tkcurses"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def sample_ini_config(temp_config_dir):
    """Create a sample INI configuration file."""
    config_file = temp_config_dir / "tkcurses.ini"
    config_file.write_text("""\
[mouse]
click_interval = 250
enabled = true
report_motion = true

[display]
color_mode = auto
unicode_borders = true
refresh_interval = 16

[input]
poll_timeout = 50
keypad = true
escape_delay = 25

[accessibility]
high_contrast = false
min_click_interval = 0
screen_reader = false

[debug]
enabled = false
log_file =
log_level = WARNING
""")
    return config_file


# =============================================================================
# Geometry Fixtures
# =============================================================================

@pytest.fixture
def sample_rect():
    """Provide a sample rectangle for testing."""
    from tkcurses._core.geometry import Rect
    return Rect(10, 5, 40, 20)


@pytest.fixture
def sample_point():
    """Provide a sample point for testing."""
    from tkcurses._core.geometry import Point
    return Point(15, 10)


@pytest.fixture
def sample_size():
    """Provide a sample size for testing."""
    from tkcurses._core.geometry import Size
    return Size(80, 24)


# =============================================================================
# Event Fixtures
# =============================================================================

@pytest.fixture
def sample_key_event():
    """Provide a sample key event for testing."""
    from tkcurses._core.events import KeyEvent
    return KeyEvent(keycode=ord('a'), keysym='a', char='a', modifiers=0)


@pytest.fixture
def sample_mouse_event():
    """Provide a sample mouse event for testing."""
    from tkcurses._core.events import MouseEvent
    return MouseEvent(x=10, y=5, button=1, state='clicked', modifiers=0)


@pytest.fixture
def sample_resize_event():
    """Provide a sample resize event for testing."""
    from tkcurses._core.events import ResizeEvent
    return ResizeEvent(width=120, height=40)


# =============================================================================
# Environment Fixtures
# =============================================================================

@pytest.fixture
def clean_env():
    """Provide a clean environment without TKCURSES_* variables."""
    env_vars = [key for key in os.environ if key.startswith('TKCURSES_')]
    old_values = {key: os.environ.pop(key) for key in env_vars}
    yield
    os.environ.update(old_values)


@pytest.fixture
def mock_env(monkeypatch):
    """Provide a helper to set environment variables."""
    def _set_env(**kwargs):
        for key, value in kwargs.items():
            monkeypatch.setenv(key, value)
    return _set_env
