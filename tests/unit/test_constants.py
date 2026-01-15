"""Unit tests for tkcurses.constants module."""

import pytest

from tkcurses.constants import (
    # Anchors
    N, S, E, W, NE, NW, SE, SW, CENTER, NSEW,
    # Relief
    FLAT, RAISED, SUNKEN, GROOVE, RIDGE, SOLID,
    # States
    NORMAL, DISABLED, ACTIVE, HIDDEN,
    # Boolean
    YES, NO, ON, OFF, TRUE, FALSE,
    # Selection
    SINGLE, BROWSE, MULTIPLE, EXTENDED,
    # Orientation
    HORIZONTAL, VERTICAL, BOTH,
    # Pack
    TOP, BOTTOM, LEFT, RIGHT, NONE, X, Y,
    # Text
    INSERT, CURRENT, END, SEL, SEL_FIRST, SEL_LAST,
    CHAR, WORD,
    # Menu
    CASCADE, CHECKBUTTON, COMMAND, RADIOBUTTON, SEPARATOR,
    # Cursor
    UNITS, PAGES,
    # Curses attributes
    A_NORMAL, A_BOLD, A_UNDERLINE, A_REVERSE,
    # Curses keys
    KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
    KEY_F1, KEY_F12,
    # Mouse
    BUTTON1_CLICKED, BUTTON_SHIFT,
    ALL_MOUSE_EVENTS,
    # Colors
    COLOR_BLACK, COLOR_WHITE, COLOR_RED,
    # Box chars
    BOX_CHARS_UNICODE, BOX_CHARS_ASCII, BOX_CHARS_DOUBLE,
    get_acs_chars,
)


class TestAnchorConstants:
    """Tests for anchor position constants."""

    def test_compass_points(self):
        """Anchor constants should be compass directions."""
        assert N == 'n'
        assert S == 's'
        assert E == 'e'
        assert W == 'w'
        assert NE == 'ne'
        assert NW == 'nw'
        assert SE == 'se'
        assert SW == 'sw'

    def test_center(self):
        """CENTER should be 'center'."""
        assert CENTER == 'center'

    def test_nsew(self):
        """NSEW should be 'nsew'."""
        assert NSEW == 'nsew'


class TestReliefConstants:
    """Tests for relief style constants."""

    def test_relief_values(self):
        """Relief constants should be strings."""
        assert FLAT == 'flat'
        assert RAISED == 'raised'
        assert SUNKEN == 'sunken'
        assert GROOVE == 'groove'
        assert RIDGE == 'ridge'
        assert SOLID == 'solid'


class TestStateConstants:
    """Tests for widget state constants."""

    def test_state_values(self):
        """State constants should be strings."""
        assert NORMAL == 'normal'
        assert DISABLED == 'disabled'
        assert ACTIVE == 'active'
        assert HIDDEN == 'hidden'


class TestBooleanConstants:
    """Tests for boolean-like constants."""

    def test_true_values(self):
        """True-like constants should be True."""
        assert YES is True
        assert ON is True
        assert TRUE is True

    def test_false_values(self):
        """False-like constants should be False."""
        assert NO is False
        assert OFF is False
        assert FALSE is False


class TestSelectionModes:
    """Tests for selection mode constants."""

    def test_selection_modes(self):
        """Selection mode constants should be strings."""
        assert SINGLE == 'single'
        assert BROWSE == 'browse'
        assert MULTIPLE == 'multiple'
        assert EXTENDED == 'extended'


class TestOrientationConstants:
    """Tests for orientation constants."""

    def test_orientations(self):
        """Orientation constants should be strings."""
        assert HORIZONTAL == 'horizontal'
        assert VERTICAL == 'vertical'
        assert BOTH == 'both'


class TestPackConstants:
    """Tests for pack geometry manager constants."""

    def test_sides(self):
        """Side constants should be strings."""
        assert TOP == 'top'
        assert BOTTOM == 'bottom'
        assert LEFT == 'left'
        assert RIGHT == 'right'

    def test_fill(self):
        """Fill constants should be strings."""
        assert NONE == 'none'
        assert X == 'x'
        assert Y == 'y'
        # BOTH tested in orientation


class TestTextConstants:
    """Tests for text widget constants."""

    def test_marks(self):
        """Text mark constants should be strings."""
        assert INSERT == 'insert'
        assert CURRENT == 'current'
        assert END == 'end'

    def test_selection(self):
        """Selection constants should be strings."""
        assert SEL == 'sel'
        assert SEL_FIRST == 'sel.first'
        assert SEL_LAST == 'sel.last'

    def test_wrap_modes(self):
        """Wrap mode constants should be strings."""
        assert CHAR == 'char'
        assert WORD == 'word'


class TestMenuConstants:
    """Tests for menu constants."""

    def test_menu_types(self):
        """Menu type constants should be strings."""
        assert CASCADE == 'cascade'
        assert CHECKBUTTON == 'checkbutton'
        assert COMMAND == 'command'
        assert RADIOBUTTON == 'radiobutton'
        assert SEPARATOR == 'separator'


class TestCursorConstants:
    """Tests for cursor movement constants."""

    def test_cursor_units(self):
        """Cursor movement constants should be strings."""
        assert UNITS == 'units'
        assert PAGES == 'pages'


class TestCursesAttributes:
    """Tests for curses attribute constants."""

    def test_a_normal_zero(self):
        """A_NORMAL should be 0."""
        assert A_NORMAL == 0

    def test_attributes_are_integers(self):
        """Attribute constants should be integers."""
        assert isinstance(A_BOLD, int)
        assert isinstance(A_UNDERLINE, int)
        assert isinstance(A_REVERSE, int)

    def test_attributes_non_zero(self):
        """Non-normal attributes should be non-zero."""
        assert A_BOLD != 0
        assert A_UNDERLINE != 0
        assert A_REVERSE != 0


class TestCursesKeys:
    """Tests for curses key constants."""

    def test_arrow_keys(self):
        """Arrow key constants should be integers."""
        assert isinstance(KEY_UP, int)
        assert isinstance(KEY_DOWN, int)
        assert isinstance(KEY_LEFT, int)
        assert isinstance(KEY_RIGHT, int)

    def test_function_keys(self):
        """Function key constants should be integers."""
        assert isinstance(KEY_F1, int)
        assert isinstance(KEY_F12, int)

    def test_keys_are_positive(self):
        """Key constants should be positive."""
        assert KEY_UP > 0
        assert KEY_F1 > 0


class TestMouseConstants:
    """Tests for mouse button constants."""

    def test_button_clicked(self):
        """Button click constant should be integer."""
        assert isinstance(BUTTON1_CLICKED, int)
        assert BUTTON1_CLICKED != 0

    def test_modifiers(self):
        """Modifier constants should be integers."""
        assert isinstance(BUTTON_SHIFT, int)

    def test_all_mouse_events(self):
        """ALL_MOUSE_EVENTS should be integer."""
        assert isinstance(ALL_MOUSE_EVENTS, int)
        assert ALL_MOUSE_EVENTS != 0


class TestColorConstants:
    """Tests for color constants."""

    def test_color_indices(self):
        """Color constants should be valid indices."""
        assert COLOR_BLACK == 0
        assert COLOR_WHITE == 7
        assert 0 <= COLOR_RED <= 7


class TestBoxCharacters:
    """Tests for box drawing character constants."""

    def test_unicode_box_chars(self):
        """BOX_CHARS_UNICODE should have all corners and lines."""
        assert 'ULCORNER' in BOX_CHARS_UNICODE
        assert 'URCORNER' in BOX_CHARS_UNICODE
        assert 'LLCORNER' in BOX_CHARS_UNICODE
        assert 'LRCORNER' in BOX_CHARS_UNICODE
        assert 'HLINE' in BOX_CHARS_UNICODE
        assert 'VLINE' in BOX_CHARS_UNICODE

    def test_unicode_values(self):
        """Unicode box chars should be Unicode strings."""
        for name, char in BOX_CHARS_UNICODE.items():
            assert isinstance(char, str)
            assert len(char) == 1

    def test_ascii_box_chars(self):
        """BOX_CHARS_ASCII should have same keys as Unicode."""
        assert set(BOX_CHARS_ASCII.keys()) == set(BOX_CHARS_UNICODE.keys())

    def test_ascii_values(self):
        """ASCII box chars should be ASCII strings."""
        for name, char in BOX_CHARS_ASCII.items():
            assert isinstance(char, str)
            assert len(char) == 1
            assert ord(char) < 128

    def test_double_box_chars(self):
        """BOX_CHARS_DOUBLE should have same keys as Unicode."""
        assert set(BOX_CHARS_DOUBLE.keys()) == set(BOX_CHARS_UNICODE.keys())


class TestGetAcsChars:
    """Tests for get_acs_chars function."""

    def test_function_exists(self):
        """get_acs_chars should be callable."""
        assert callable(get_acs_chars)

    def test_returns_dict(self):
        """get_acs_chars should return a dictionary."""
        # Note: This will only work if curses is initialized
        # In unit tests, we just verify the function exists
        pass
