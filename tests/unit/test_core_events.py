"""Unit tests for tkcurses._core.events module."""

import time

import pytest

from tkcurses._core.events import (
    Event,
    KeyEvent,
    MouseEvent,
    ResizeEvent,
    MOD_SHIFT,
    MOD_CTRL,
    MOD_ALT,
    MOD_META,
    has_modifier,
)


class TestModifierConstants:
    """Tests for modifier key constants."""

    def test_modifier_values_are_distinct(self):
        """Modifier constants should have distinct bit values."""
        modifiers = [MOD_SHIFT, MOD_CTRL, MOD_ALT, MOD_META]
        # Each modifier should be a power of 2
        for mod in modifiers:
            assert mod > 0
            assert (mod & (mod - 1)) == 0  # Power of 2 check

        # All should be distinct
        assert len(set(modifiers)) == len(modifiers)

    def test_modifiers_can_be_combined(self):
        """Modifiers should be combinable with bitwise OR."""
        combined = MOD_SHIFT | MOD_CTRL
        assert combined & MOD_SHIFT
        assert combined & MOD_CTRL
        assert not (combined & MOD_ALT)


class TestEvent:
    """Tests for base Event class."""

    def test_event_creation(self):
        """Event should be created with type and timestamp."""
        event = Event(type='test')
        assert event.type == 'test'
        assert isinstance(event.time, float)

    def test_event_time_default(self):
        """Event time should default to current time."""
        before = time.time()
        event = Event(type='test')
        after = time.time()
        assert before <= event.time <= after

    def test_event_time_custom(self):
        """Event time can be set explicitly."""
        event = Event(type='test', time=12345.0)
        assert event.time == 12345.0


class TestKeyEvent:
    """Tests for KeyEvent class."""

    def test_key_event_defaults(self):
        """KeyEvent should have sensible defaults."""
        event = KeyEvent()
        assert event.type == 'key'
        assert event.keycode == 0
        assert event.keysym == ''
        assert event.char == ''
        assert event.modifiers == 0

    def test_key_event_creation(self):
        """KeyEvent should store all attributes."""
        event = KeyEvent(
            keycode=65,
            keysym='a',
            char='a',
            modifiers=MOD_SHIFT,
        )
        assert event.type == 'key'
        assert event.keycode == 65
        assert event.keysym == 'a'
        assert event.char == 'a'
        assert event.modifiers == MOD_SHIFT

    def test_key_event_special_key(self):
        """KeyEvent should work with special keys."""
        event = KeyEvent(
            keycode=259,  # KEY_UP
            keysym='Up',
            char='',
            modifiers=0,
        )
        assert event.keysym == 'Up'
        assert event.char == ''

    def test_key_event_with_ctrl(self):
        """KeyEvent should handle Ctrl modifier."""
        event = KeyEvent(
            keycode=1,  # Ctrl+A
            keysym='Control-a',
            char='',
            modifiers=MOD_CTRL,
        )
        assert has_modifier(event.modifiers, MOD_CTRL)
        assert not has_modifier(event.modifiers, MOD_SHIFT)


class TestMouseEvent:
    """Tests for MouseEvent class."""

    def test_mouse_event_defaults(self):
        """MouseEvent should have sensible defaults."""
        event = MouseEvent()
        assert event.type == 'mouse'
        assert event.x == 0
        assert event.y == 0
        assert event.button == 0
        assert event.state == 'pressed'
        assert event.modifiers == 0
        assert event.drag_start is None
        assert event.drag_end is None

    def test_mouse_event_click(self):
        """MouseEvent should store click information."""
        event = MouseEvent(
            x=10,
            y=5,
            button=1,
            state='clicked',
            modifiers=0,
        )
        assert event.x == 10
        assert event.y == 5
        assert event.button == 1
        assert event.state == 'clicked'

    def test_mouse_event_drag(self):
        """MouseEvent should store drag information."""
        event = MouseEvent(
            x=20,
            y=15,
            button=1,
            state='drag',
            drag_start=(10, 5),
            modifiers=0,
        )
        assert event.state == 'drag'
        assert event.drag_start == (10, 5)
        assert event.drag_end is None

    def test_mouse_event_drag_complete(self):
        """MouseEvent should store complete drag with start and end."""
        event = MouseEvent(
            x=30,
            y=20,
            button=1,
            state='released',
            drag_start=(10, 5),
            drag_end=(30, 20),
            modifiers=0,
        )
        assert event.drag_start == (10, 5)
        assert event.drag_end == (30, 20)

    def test_mouse_event_with_modifiers(self):
        """MouseEvent should handle modifier keys."""
        event = MouseEvent(
            x=10,
            y=5,
            button=1,
            state='clicked',
            modifiers=MOD_SHIFT | MOD_CTRL,
        )
        assert has_modifier(event.modifiers, MOD_SHIFT)
        assert has_modifier(event.modifiers, MOD_CTRL)
        assert not has_modifier(event.modifiers, MOD_ALT)

    def test_mouse_event_all_states(self):
        """MouseEvent should accept all valid states."""
        states = ['pressed', 'released', 'clicked', 'double', 'triple', 'drag', 'motion']
        for state in states:
            event = MouseEvent(x=0, y=0, button=1, state=state)
            assert event.state == state

    def test_mouse_event_all_buttons(self):
        """MouseEvent should handle all button numbers."""
        for button in range(0, 6):  # 0=none, 1-5=buttons
            event = MouseEvent(x=0, y=0, button=button, state='clicked')
            assert event.button == button


class TestResizeEvent:
    """Tests for ResizeEvent class."""

    def test_resize_event_defaults(self):
        """ResizeEvent should have sensible defaults."""
        event = ResizeEvent()
        assert event.type == 'resize'
        assert event.width == 0
        assert event.height == 0

    def test_resize_event_creation(self):
        """ResizeEvent should store dimensions."""
        event = ResizeEvent(width=120, height=40)
        assert event.type == 'resize'
        assert event.width == 120
        assert event.height == 40

    def test_resize_event_typical_sizes(self):
        """ResizeEvent should handle typical terminal sizes."""
        sizes = [(80, 24), (120, 40), (132, 43), (200, 60)]
        for width, height in sizes:
            event = ResizeEvent(width=width, height=height)
            assert event.width == width
            assert event.height == height


class TestHasModifier:
    """Tests for has_modifier helper function."""

    def test_has_modifier_single(self):
        """has_modifier should detect single modifier."""
        assert has_modifier(MOD_SHIFT, MOD_SHIFT)
        assert has_modifier(MOD_CTRL, MOD_CTRL)
        assert has_modifier(MOD_ALT, MOD_ALT)
        assert has_modifier(MOD_META, MOD_META)

    def test_has_modifier_combined(self):
        """has_modifier should detect modifiers in combination."""
        combined = MOD_SHIFT | MOD_CTRL | MOD_ALT
        assert has_modifier(combined, MOD_SHIFT)
        assert has_modifier(combined, MOD_CTRL)
        assert has_modifier(combined, MOD_ALT)
        assert not has_modifier(combined, MOD_META)

    def test_has_modifier_none(self):
        """has_modifier should return False for no modifiers."""
        assert not has_modifier(0, MOD_SHIFT)
        assert not has_modifier(0, MOD_CTRL)
        assert not has_modifier(0, MOD_ALT)
        assert not has_modifier(0, MOD_META)

    def test_has_modifier_wrong(self):
        """has_modifier should return False for wrong modifier."""
        assert not has_modifier(MOD_SHIFT, MOD_CTRL)
        assert not has_modifier(MOD_CTRL, MOD_ALT)
        assert not has_modifier(MOD_ALT, MOD_META)
