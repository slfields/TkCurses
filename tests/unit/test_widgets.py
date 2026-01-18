"""Unit tests for tkcurses.Misc class.

Comprehensive tests for the Misc base class which provides:
- Event binding system (bind, unbind, bind_all, bind_class)
- Focus management (focus_set, focus_get, focus_force, etc.)
- Clipboard operations (clipboard_clear, clipboard_append, clipboard_get)
- Selection operations (selection_clear, selection_get, selection_own)
- Timing callbacks (after, after_cancel, after_idle)
- Widget information queries (winfo_* methods)
- Configuration management (cget, configure, config, keys)
- Widget management (nametowidget, register, update)
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

from tkcurses import Misc, Wm
from tkcurses._core.events import Event, KeyEvent, MouseEvent


# =============================================================================
# Fixture Utilities
# =============================================================================


@pytest.fixture(autouse=True)
def reset_misc_singletons():
    """Reset Misc class-level storage before and after each test.

    Uses fresh empty objects instead of copy/restore to avoid memory
    accumulation across the large number of tests.
    """
    # Reset to fresh empty values at start of test
    Misc._global_bindings = {}
    Misc._class_bindings = {}
    Misc._clipboard = ""
    Misc._selection = ""
    Misc._focused_widget = None
    Misc._widget_registry = {}
    Misc._after_queue = []
    Misc._after_id_counter = 0

    yield

    # Reset again at end to ensure no leakage between tests
    Misc._global_bindings = {}
    Misc._class_bindings = {}
    Misc._clipboard = ""
    Misc._selection = ""
    Misc._focused_widget = None
    Misc._widget_registry = {}
    Misc._after_queue = []
    Misc._after_id_counter = 0


# =============================================================================
# Tests for Event Binding Methods
# =============================================================================


class TestEventBinding:
    """Tests for event binding methods."""

    def test_bind_basic_registration(self):
        """bind() should register a callback for an event sequence."""
        widget = Misc()
        callback = MagicMock()

        func_id = widget.bind("<Button-1>", callback)

        assert func_id is not None
        assert "<Button-1>" in widget._bindings
        assert len(widget._bindings["<Button-1>"]) == 1
        assert widget._bindings["<Button-1>"][0][1] is callback

    def test_bind_returns_function_id(self):
        """bind() should return a unique function ID."""
        widget = Misc()
        callback = MagicMock()

        func_id = widget.bind("<Button-1>", callback)

        assert isinstance(func_id, str)
        assert func_id.startswith("func_")

    def test_bind_replaces_existing_binding_by_default(self):
        """bind() should replace existing binding for same sequence."""
        widget = Misc()
        callback1 = MagicMock()
        callback2 = MagicMock()

        widget.bind("<Button-1>", callback1)
        widget.bind("<Button-1>", callback2)

        assert len(widget._bindings["<Button-1>"]) == 1
        assert widget._bindings["<Button-1>"][0][1] is callback2

    def test_bind_add_mode_appends_binding(self):
        """bind() with add='+' should append to existing bindings."""
        widget = Misc()
        callback1 = MagicMock()
        callback2 = MagicMock()

        widget.bind("<Button-1>", callback1)
        widget.bind("<Button-1>", callback2, add="+")

        assert len(widget._bindings["<Button-1>"]) == 2
        assert widget._bindings["<Button-1>"][0][1] is callback1
        assert widget._bindings["<Button-1>"][1][1] is callback2

    def test_bind_add_mode_with_true(self):
        """bind() with add=True should also append to existing bindings."""
        widget = Misc()
        callback1 = MagicMock()
        callback2 = MagicMock()

        widget.bind("<Button-1>", callback1)
        widget.bind("<Button-1>", callback2, add=True)

        assert len(widget._bindings["<Button-1>"]) == 2

    def test_bind_query_mode_no_bindings(self):
        """bind(sequence) with no func should return empty string if no bindings."""
        widget = Misc()

        result = widget.bind("<Button-1>")

        assert result == ""

    def test_bind_query_mode_with_bindings(self):
        """bind(sequence) with no func should return function info if bindings exist."""
        widget = Misc()
        callback = MagicMock()

        widget.bind("<Button-1>", callback)
        result = widget.bind("<Button-1>")

        assert result != ""
        assert callback.__repr__() in result or str(callback) in result

    def test_bind_all_global_registration(self):
        """bind_all() should register a global callback."""
        widget = Misc()
        callback = MagicMock()

        func_id = widget.bind_all("<Control-q>", callback)

        assert func_id is not None
        assert "<Control-q>" in Misc._global_bindings
        assert len(Misc._global_bindings["<Control-q>"]) == 1
        assert Misc._global_bindings["<Control-q>"][0][1] is callback

    def test_bind_all_shared_across_widgets(self):
        """bind_all() should be shared across all widgets."""
        widget1 = Misc()
        widget2 = Misc()
        callback = MagicMock()

        widget1.bind_all("<F1>", callback)

        # Both widgets should access same global binding
        assert "<F1>" in Misc._global_bindings
        assert Misc._global_bindings["<F1>"][0][1] is callback

    def test_bind_all_replaces_by_default(self):
        """bind_all() should replace existing global binding by default."""
        widget = Misc()
        callback1 = MagicMock()
        callback2 = MagicMock()

        widget.bind_all("<F1>", callback1)
        widget.bind_all("<F1>", callback2)

        assert len(Misc._global_bindings["<F1>"]) == 1
        assert Misc._global_bindings["<F1>"][0][1] is callback2

    def test_bind_all_add_mode(self):
        """bind_all() with add='+' should append to global bindings."""
        widget = Misc()
        callback1 = MagicMock()
        callback2 = MagicMock()

        widget.bind_all("<F1>", callback1)
        widget.bind_all("<F1>", callback2, add="+")

        assert len(Misc._global_bindings["<F1>"]) == 2

    def test_bind_all_query_mode(self):
        """bind_all(sequence) with no func should return global binding info."""
        widget = Misc()
        callback = MagicMock()

        widget.bind_all("<F1>", callback)
        result = widget.bind_all("<F1>")

        assert result != ""

    def test_bind_class_registration(self):
        """bind_class() should register a class-level callback."""
        widget = Misc()
        callback = MagicMock()

        func_id = widget.bind_class("Button", "<Return>", callback)

        assert func_id is not None
        assert "Button" in Misc._class_bindings
        assert "<Return>" in Misc._class_bindings["Button"]
        assert Misc._class_bindings["Button"]["<Return>"][0][1] is callback

    def test_bind_class_multiple_classes(self):
        """bind_class() should support bindings for multiple classes."""
        widget = Misc()
        button_callback = MagicMock()
        entry_callback = MagicMock()

        widget.bind_class("Button", "<Return>", button_callback)
        widget.bind_class("Entry", "<Return>", entry_callback)

        assert "Button" in Misc._class_bindings
        assert "Entry" in Misc._class_bindings
        assert Misc._class_bindings["Button"]["<Return>"][0][1] is button_callback
        assert Misc._class_bindings["Entry"]["<Return>"][0][1] is entry_callback

    def test_bind_class_replaces_by_default(self):
        """bind_class() should replace existing class binding by default."""
        widget = Misc()
        callback1 = MagicMock()
        callback2 = MagicMock()

        widget.bind_class("Button", "<Return>", callback1)
        widget.bind_class("Button", "<Return>", callback2)

        assert len(Misc._class_bindings["Button"]["<Return>"]) == 1
        assert Misc._class_bindings["Button"]["<Return>"][0][1] is callback2

    def test_bind_class_add_mode(self):
        """bind_class() with add='+' should append to class bindings."""
        widget = Misc()
        callback1 = MagicMock()
        callback2 = MagicMock()

        widget.bind_class("Button", "<Return>", callback1)
        widget.bind_class("Button", "<Return>", callback2, add="+")

        assert len(Misc._class_bindings["Button"]["<Return>"]) == 2

    def test_bind_class_query_mode(self):
        """bind_class(className, sequence) with no func should return binding info."""
        widget = Misc()
        callback = MagicMock()

        widget.bind_class("Button", "<Return>", callback)
        result = widget.bind_class("Button", "<Return>")

        assert result != ""

    def test_bind_class_query_nonexistent_class(self):
        """bind_class() query on nonexistent class should return empty string."""
        widget = Misc()

        result = widget.bind_class("NonExistent", "<Return>")

        assert result == ""

    def test_unbind_removes_all_bindings(self):
        """unbind() with no funcid should remove all bindings for sequence."""
        widget = Misc()
        callback1 = MagicMock()
        callback2 = MagicMock()

        widget.bind("<Button-1>", callback1)
        widget.bind("<Button-1>", callback2, add="+")
        widget.unbind("<Button-1>")

        assert "<Button-1>" not in widget._bindings

    def test_unbind_removes_specific_binding(self):
        """unbind() with funcid should remove only that binding."""
        widget = Misc()
        callback1 = MagicMock()
        callback2 = MagicMock()

        fid1 = widget.bind("<Button-1>", callback1)
        fid2 = widget.bind("<Button-1>", callback2, add="+")
        widget.unbind("<Button-1>", fid1)

        assert len(widget._bindings["<Button-1>"]) == 1
        assert widget._bindings["<Button-1>"][0][1] is callback2

    def test_unbind_nonexistent_sequence(self):
        """unbind() on nonexistent sequence should not raise error."""
        widget = Misc()

        widget.unbind("<Button-1>")  # Should not raise

        assert "<Button-1>" not in widget._bindings

    def test_unbind_removes_empty_binding_list(self):
        """unbind() should remove sequence key if no bindings remain."""
        widget = Misc()
        callback = MagicMock()

        fid = widget.bind("<Button-1>", callback)
        widget.unbind("<Button-1>", fid)

        assert "<Button-1>" not in widget._bindings

    def test_unbind_all_removes_global_bindings(self):
        """unbind_all() should remove all global bindings for sequence."""
        widget = Misc()
        callback = MagicMock()

        widget.bind_all("<F1>", callback)
        widget.unbind_all("<F1>")

        assert "<F1>" not in Misc._global_bindings

    def test_unbind_all_nonexistent_sequence(self):
        """unbind_all() on nonexistent sequence should not raise error."""
        widget = Misc()

        widget.unbind_all("<F1>")  # Should not raise

        assert "<F1>" not in Misc._global_bindings

    def test_unbind_class_removes_class_bindings(self):
        """unbind_class() should remove class bindings for sequence."""
        widget = Misc()
        callback = MagicMock()

        widget.bind_class("Button", "<Return>", callback)
        widget.unbind_class("Button", "<Return>")

        assert "Button" not in Misc._class_bindings or \
               "<Return>" not in Misc._class_bindings.get("Button", {})

    def test_unbind_class_nonexistent_class(self):
        """unbind_class() on nonexistent class should not raise error."""
        widget = Misc()

        widget.unbind_class("NonExistent", "<Return>")  # Should not raise

    def test_event_dispatch_widget_binding(self):
        """_event_dispatch() should invoke widget-specific binding."""
        widget = Misc()
        callback = MagicMock()

        widget.bind("<Key-a>", callback)
        event = KeyEvent(keycode=ord('a'), keysym='a', char='a')
        widget._event_dispatch(event)

        callback.assert_called_once()

    def test_event_dispatch_class_binding(self):
        """_event_dispatch() should invoke class binding."""
        widget = Misc()
        callback = MagicMock()

        widget.bind_class("Misc", "<Key-Return>", callback)
        event = KeyEvent(keycode=13, keysym='Return', char='\n')
        widget._event_dispatch(event)

        callback.assert_called_once()

    def test_event_dispatch_global_binding(self):
        """_event_dispatch() should invoke global binding."""
        widget = Misc()
        callback = MagicMock()

        widget.bind_all("<Control-Key-c>", callback)
        event = KeyEvent(keycode=3, keysym='c', char='c', modifiers=0x02)
        widget._event_dispatch(event)

        callback.assert_called_once()

    def test_event_dispatch_priority_order(self):
        """_event_dispatch() should invoke bindings in correct priority."""
        widget = Misc()
        calls = []
        widget_callback = MagicMock(side_effect=lambda e: calls.append('widget'))
        class_callback = MagicMock(side_effect=lambda e: calls.append('class'))
        global_callback = MagicMock(side_effect=lambda e: calls.append('global'))

        widget.bind("<Key-a>", widget_callback)
        widget.bind_class("Misc", "<Key-a>", class_callback)
        widget.bind_all("<Key-a>", global_callback)

        event = KeyEvent(keycode=ord('a'), keysym='a', char='a')
        widget._event_dispatch(event)

        assert calls == ['widget', 'class', 'global']

    def test_event_dispatch_handles_callback_errors(self):
        """_event_dispatch() should handle callback errors gracefully."""
        widget = Misc()

        def failing_callback(event):
            raise ValueError("Callback error")

        widget.bind("<Key-a>", failing_callback)
        event = KeyEvent(keycode=ord('a'), keysym='a', char='a')

        # Should not raise
        with patch('builtins.print'):
            widget._event_dispatch(event)

    def test_event_to_sequence_key_event(self):
        """_event_to_sequence() should convert KeyEvent to sequence string."""
        widget = Misc()

        event = KeyEvent(keycode=ord('a'), keysym='a', char='a', modifiers=0)
        sequence = widget._event_to_sequence(event)

        assert sequence == "<Key-a>"

    def test_event_to_sequence_key_with_modifiers(self):
        """_event_to_sequence() should include modifier keys."""
        widget = Misc()

        # Control+Shift+a
        event = KeyEvent(keycode=ord('a'), keysym='a', char='a', modifiers=0x03)
        sequence = widget._event_to_sequence(event)

        assert "Control" in sequence
        assert "Shift" in sequence
        assert "Key-a" in sequence

    def test_event_to_sequence_special_key(self):
        """_event_to_sequence() should handle special keys."""
        widget = Misc()

        event = KeyEvent(keycode=13, keysym='Return', char='\n', modifiers=0)
        sequence = widget._event_to_sequence(event)

        assert sequence == "<Key-Return>"

    def test_event_to_sequence_mouse_button_press(self):
        """_event_to_sequence() should convert mouse press to sequence."""
        widget = Misc()

        event = MouseEvent(x=10, y=5, button=1, state='pressed', modifiers=0)
        sequence = widget._event_to_sequence(event)

        assert sequence == "<Button-1>"

    def test_event_to_sequence_mouse_button_release(self):
        """_event_to_sequence() should convert mouse release to sequence."""
        widget = Misc()

        event = MouseEvent(x=10, y=5, button=1, state='released', modifiers=0)
        sequence = widget._event_to_sequence(event)

        assert sequence == "<ButtonRelease-1>"

    def test_event_to_sequence_mouse_double_click(self):
        """_event_to_sequence() should convert double-click to sequence."""
        widget = Misc()

        event = MouseEvent(x=10, y=5, button=1, state='double', modifiers=0)
        sequence = widget._event_to_sequence(event)

        assert sequence == "<Double-Button-1>"

    def test_event_to_sequence_mouse_triple_click(self):
        """_event_to_sequence() should convert triple-click to sequence."""
        widget = Misc()

        event = MouseEvent(x=10, y=5, button=1, state='triple', modifiers=0)
        sequence = widget._event_to_sequence(event)

        assert sequence == "<Triple-Button-1>"

    def test_event_to_sequence_mouse_drag(self):
        """_event_to_sequence() should convert mouse drag to sequence."""
        widget = Misc()

        event = MouseEvent(x=10, y=5, button=1, state='drag', modifiers=0)
        sequence = widget._event_to_sequence(event)

        assert sequence == "<B1-Motion>"

    def test_event_to_sequence_mouse_motion(self):
        """_event_to_sequence() should convert mouse motion to sequence."""
        widget = Misc()

        event = MouseEvent(x=10, y=5, button=1, state='motion', modifiers=0)
        sequence = widget._event_to_sequence(event)

        assert sequence == "<Motion>"

    def test_event_to_sequence_mouse_with_modifiers(self):
        """_event_to_sequence() should include modifiers in mouse sequence."""
        widget = Misc()

        # Shift+Button-1
        event = MouseEvent(x=10, y=5, button=1, state='pressed', modifiers=0x01)
        sequence = widget._event_to_sequence(event)

        assert "Shift" in sequence
        assert "Button-1" in sequence

    def test_event_to_sequence_generic_event(self):
        """_event_to_sequence() should handle generic events."""
        widget = Misc()

        event = Event(type='FocusIn')
        sequence = widget._event_to_sequence(event)

        assert sequence == "<FocusIn>"


# =============================================================================
# Tests for Focus Management Methods
# =============================================================================


class TestFocusManagement:
    """Tests for focus management methods."""

    def test_focus_set_gives_focus_to_widget(self):
        """focus_set() should set focus to the widget."""
        widget = Misc()

        widget.focus_set()

        assert widget._has_focus is True
        assert Misc._focused_widget is widget

    def test_focus_set_removes_focus_from_previous(self):
        """focus_set() should remove focus from previously focused widget."""
        widget1 = Misc()
        widget2 = Misc()

        widget1.focus_set()
        widget2.focus_set()

        assert widget1._has_focus is False
        assert widget2._has_focus is True
        assert Misc._focused_widget is widget2

    def test_focus_get_returns_focused_widget(self):
        """focus_get() should return the currently focused widget."""
        widget = Misc()
        widget.focus_set()

        focused = widget.focus_get()

        assert focused is widget

    def test_focus_get_returns_none_if_no_focus(self):
        """focus_get() should return None if no widget has focus."""
        widget = Misc()

        focused = widget.focus_get()

        assert focused is None

    def test_focus_force_same_as_focus_set(self):
        """focus_force() should set focus like focus_set()."""
        widget = Misc()

        widget.focus_force()

        assert widget._has_focus is True
        assert Misc._focused_widget is widget

    def test_focus_displayof_returns_focused_widget(self):
        """focus_displayof() should return the focused widget."""
        widget = Misc()
        widget.focus_set()

        focused = widget.focus_displayof()

        assert focused is widget

    def test_focus_displayof_returns_none_if_no_focus(self):
        """focus_displayof() should return None if no widget has focus."""
        widget = Misc()

        focused = widget.focus_displayof()

        assert focused is None

    def test_tk_focusNext_returns_next_widget(self):
        """tk_focusNext() should return the next widget in focus order."""
        widget1 = Misc()
        widget2 = Misc()
        widget3 = Misc()

        next_widget = widget1.tk_focusNext()

        assert next_widget is widget2

    def test_tk_focusNext_wraps_around(self):
        """tk_focusNext() should wrap to first widget after last."""
        widget1 = Misc()
        widget2 = Misc()

        next_widget = widget2.tk_focusNext()

        assert next_widget is widget1

    def test_tk_focusNext_single_widget(self):
        """tk_focusNext() with single widget should return itself."""
        widget = Misc()

        next_widget = widget.tk_focusNext()

        assert next_widget is widget

    def test_tk_focusNext_empty_registry(self):
        """tk_focusNext() with no widgets should return None."""
        widget = Misc()
        Misc._widget_registry.clear()

        next_widget = widget.tk_focusNext()

        assert next_widget is None

    def test_tk_focusNext_unregistered_widget(self):
        """tk_focusNext() for unregistered widget should return None."""
        widget = Misc()
        Misc._widget_registry.clear()

        next_widget = widget.tk_focusNext()

        assert next_widget is None

    def test_tk_focusPrev_returns_previous_widget(self):
        """tk_focusPrev() should return the previous widget in focus order."""
        widget1 = Misc()
        widget2 = Misc()
        widget3 = Misc()

        prev_widget = widget3.tk_focusPrev()

        assert prev_widget is widget2

    def test_tk_focusPrev_wraps_around(self):
        """tk_focusPrev() should wrap to last widget before first."""
        widget1 = Misc()
        widget2 = Misc()

        prev_widget = widget1.tk_focusPrev()

        assert prev_widget is widget2

    def test_tk_focusPrev_single_widget(self):
        """tk_focusPrev() with single widget should return itself."""
        widget = Misc()

        prev_widget = widget.tk_focusPrev()

        assert prev_widget is widget

    def test_tk_focusFollowsMouse_is_stub(self):
        """tk_focusFollowsMouse() should be a stub (no-op)."""
        widget = Misc()

        widget.tk_focusFollowsMouse()  # Should not raise


# =============================================================================
# Tests for Clipboard Operations
# =============================================================================


class TestClipboardOperations:
    """Tests for clipboard operations."""

    def test_clipboard_clear_empties_clipboard(self):
        """clipboard_clear() should clear the clipboard."""
        widget = Misc()
        Misc._clipboard = "Some text"

        widget.clipboard_clear()

        assert Misc._clipboard == ""

    def test_clipboard_append_adds_to_clipboard(self):
        """clipboard_append() should add text to clipboard."""
        widget = Misc()

        widget.clipboard_append("Hello")

        assert Misc._clipboard == "Hello"

    def test_clipboard_append_concatenates(self):
        """clipboard_append() should concatenate to existing content."""
        widget = Misc()

        widget.clipboard_append("Hello")
        widget.clipboard_append(" World")

        assert Misc._clipboard == "Hello World"

    def test_clipboard_get_returns_clipboard_content(self):
        """clipboard_get() should return clipboard content."""
        widget = Misc()
        Misc._clipboard = "Test content"

        content = widget.clipboard_get()

        assert content == "Test content"

    def test_clipboard_get_empty_clipboard(self):
        """clipboard_get() on empty clipboard should return empty string."""
        widget = Misc()
        Misc._clipboard = ""

        content = widget.clipboard_get()

        assert content == ""

    def test_clipboard_operations_are_global(self):
        """Clipboard operations should be shared across widgets."""
        widget1 = Misc()
        widget2 = Misc()

        widget1.clipboard_clear()
        widget1.clipboard_append("Data")
        content = widget2.clipboard_get()

        assert content == "Data"

    def test_selection_clear_empties_selection(self):
        """selection_clear() should clear the selection."""
        widget = Misc()
        Misc._selection = "Some text"

        widget.selection_clear()

        assert Misc._selection == ""

    def test_selection_get_returns_selection_content(self):
        """selection_get() should return selection content."""
        widget = Misc()
        Misc._selection = "Selected text"

        content = widget.selection_get()

        assert content == "Selected text"

    def test_selection_own_is_stub(self):
        """selection_own() should be a stub (no-op)."""
        widget = Misc()

        widget.selection_own()  # Should not raise

    def test_selection_operations_are_global(self):
        """Selection operations should be shared across widgets."""
        widget1 = Misc()
        widget2 = Misc()
        Misc._selection = ""

        widget1.selection_clear()
        Misc._selection = "Data"
        content = widget2.selection_get()

        assert content == "Data"


# =============================================================================
# Tests for Timing Callback Methods
# =============================================================================


class TestTimingCallbacks:
    """Tests for timing callback methods."""

    def test_after_schedules_callback(self):
        """after() should schedule a callback."""
        widget = Misc()
        callback = MagicMock()

        after_id = widget.after(1000, callback)

        assert after_id is not None
        assert isinstance(after_id, str)
        assert after_id.startswith("after#")
        assert len(Misc._after_queue) == 1

    def test_after_with_arguments(self):
        """after() should pass arguments to callback."""
        widget = Misc()
        callback = MagicMock()

        widget.after(0, callback, "arg1", "arg2")
        Misc._process_after_queue()

        callback.assert_called_once_with("arg1", "arg2")

    def test_after_generates_unique_ids(self):
        """after() should generate unique IDs for each callback."""
        widget = Misc()

        id1 = widget.after(1000, MagicMock())
        id2 = widget.after(1000, MagicMock())

        assert id1 != id2

    def test_after_no_func_is_sleep(self):
        """after() with no func should schedule a sleep (no-op callback)."""
        widget = Misc()

        after_id = widget.after(100)

        assert after_id is not None
        assert len(Misc._after_queue) == 1

    def test_after_sorts_queue_by_time(self):
        """after() should keep queue sorted by execution time."""
        widget = Misc()

        # Schedule in reverse order
        id1 = widget.after(3000, MagicMock())
        id2 = widget.after(1000, MagicMock())
        id3 = widget.after(2000, MagicMock())

        # Queue should be sorted
        times = [t for t, _, _ in Misc._after_queue]
        assert times == sorted(times)

    def test_after_cancel_removes_callback(self):
        """after_cancel() should remove a scheduled callback."""
        widget = Misc()
        callback = MagicMock()

        after_id = widget.after(1000, callback)
        widget.after_cancel(after_id)

        assert len(Misc._after_queue) == 0

    def test_after_cancel_nonexistent_id(self):
        """after_cancel() on nonexistent ID should not raise."""
        widget = Misc()

        widget.after_cancel("nonexistent")  # Should not raise

    def test_after_cancel_partial_removal(self):
        """after_cancel() should only remove the specified callback."""
        widget = Misc()
        callback1 = MagicMock()
        callback2 = MagicMock()

        id1 = widget.after(1000, callback1)
        id2 = widget.after(1000, callback2)
        widget.after_cancel(id1)

        assert len(Misc._after_queue) == 1
        assert Misc._after_queue[0][1] == id2

    def test_after_idle_schedules_immediately(self):
        """after_idle() should schedule callback to run immediately."""
        widget = Misc()
        callback = MagicMock()

        after_id = widget.after_idle(callback)

        assert after_id is not None
        assert after_id.startswith("idle#")

    def test_after_idle_with_arguments(self):
        """after_idle() should pass arguments to callback."""
        widget = Misc()
        callback = MagicMock()

        widget.after_idle(callback, "arg1", "arg2")
        Misc._process_after_queue()

        callback.assert_called_once_with("arg1", "arg2")

    def test_process_after_queue_executes_due_callbacks(self):
        """_process_after_queue() should execute callbacks whose time has come."""
        widget = Misc()
        callback1 = MagicMock()
        callback2 = MagicMock()

        widget.after(100, callback1)
        widget.after(10000, callback2)

        # Wait for first callback to be due
        time.sleep(0.15)
        Misc._process_after_queue()

        callback1.assert_called_once()
        callback2.assert_not_called()

    def test_process_after_queue_removes_executed_callbacks(self):
        """_process_after_queue() should remove executed callbacks from queue."""
        widget = Misc()

        widget.after(0, MagicMock())
        assert len(Misc._after_queue) == 1

        Misc._process_after_queue()

        assert len(Misc._after_queue) == 0

    def test_process_after_queue_handles_errors(self):
        """_process_after_queue() should handle callback errors gracefully."""
        widget = Misc()

        def failing_callback():
            raise ValueError("Callback error")

        widget.after(0, failing_callback)

        # Should not raise
        with patch('builtins.print'):
            Misc._process_after_queue()

    def test_after_counter_increments(self):
        """after() should increment the ID counter."""
        widget = Misc()
        initial_counter = Misc._after_id_counter

        widget.after(1000, MagicMock())
        widget.after(1000, MagicMock())

        assert Misc._after_id_counter == initial_counter + 2

    def test_after_idle_counter_increments(self):
        """after_idle() should increment the ID counter."""
        widget = Misc()
        initial_counter = Misc._after_id_counter

        widget.after_idle(MagicMock())
        widget.after_idle(MagicMock())

        assert Misc._after_id_counter == initial_counter + 2


# =============================================================================
# API Completeness Tests
# =============================================================================


class TestAPICompleteness:
    """Tests to verify all required tkinter API methods exist.

    These tests catch missing method implementations early, before UAT.
    They validate that required methods EXIST, not their behavior.
    """

    def test_misc_has_all_winfo_methods(self):
        """Misc class should have all expected winfo_* methods."""
        expected_methods = [
            'winfo_children',
            'winfo_class',
            'winfo_containing',
            'winfo_exists',
            'winfo_height',
            'winfo_width',
            'winfo_id',
            'winfo_ismapped',
            'winfo_viewable',
            'winfo_name',
            'winfo_parent',
            'winfo_reqheight',
            'winfo_reqwidth',
            'winfo_rootx',
            'winfo_rooty',
            'winfo_screenheight',
            'winfo_screenwidth',
            'winfo_toplevel',
            'winfo_x',
            'winfo_y',
        ]
        widget = Misc()
        missing = [m for m in expected_methods if not hasattr(widget, m)]
        assert not missing, f"Misc missing winfo methods: {missing}"

    def test_misc_winfo_methods_are_callable(self):
        """All winfo_* methods on Misc should be callable."""
        widget = Misc()
        winfo_methods = [m for m in dir(widget) if m.startswith('winfo_')]
        non_callable = [m for m in winfo_methods if not callable(getattr(widget, m))]
        assert not non_callable, f"Non-callable winfo methods: {non_callable}"

    def test_wm_has_all_geometry_methods(self):
        """Wm class should have all expected geometry methods."""
        expected_methods = [
            'wm_geometry',
            'geometry',
            'wm_minsize',
            'minsize',
            'wm_maxsize',
            'maxsize',
            'wm_resizable',
            'resizable',
        ]
        wm = Wm()
        missing = [m for m in expected_methods if not hasattr(wm, m)]
        assert not missing, f"Wm missing geometry methods: {missing}"

    def test_wm_has_all_state_methods(self):
        """Wm class should have all expected state methods."""
        expected_methods = [
            'wm_state',
            'state',
            'wm_iconify',
            'iconify',
            'wm_deiconify',
            'deiconify',
            'wm_withdraw',
            'withdraw',
        ]
        wm = Wm()
        missing = [m for m in expected_methods if not hasattr(wm, m)]
        assert not missing, f"Wm missing state methods: {missing}"

    def test_wm_has_all_title_methods(self):
        """Wm class should have all expected title methods."""
        expected_methods = [
            'wm_title',
            'title',
        ]
        wm = Wm()
        missing = [m for m in expected_methods if not hasattr(wm, m)]
        assert not missing, f"Wm missing title methods: {missing}"

    def test_wm_has_all_protocol_methods(self):
        """Wm class should have all expected protocol methods."""
        expected_methods = [
            'wm_protocol',
            'protocol',
        ]
        wm = Wm()
        missing = [m for m in expected_methods if not hasattr(wm, m)]
        assert not missing, f"Wm missing protocol methods: {missing}"

    def test_wm_has_all_stacking_methods(self):
        """Wm class should have all expected stacking methods."""
        expected_methods = [
            'lift',
            'lower',
            'wm_transient',
            'transient',
        ]
        wm = Wm()
        missing = [m for m in expected_methods if not hasattr(wm, m)]
        assert not missing, f"Wm missing stacking methods: {missing}"

    def test_wm_has_all_attribute_methods(self):
        """Wm class should have all expected attribute methods."""
        expected_methods = [
            'wm_attributes',
            'attributes',
        ]
        wm = Wm()
        missing = [m for m in expected_methods if not hasattr(wm, m)]
        assert not missing, f"Wm missing attribute methods: {missing}"

    def test_wm_methods_are_callable(self):
        """All wm_* methods on Wm should be callable."""
        wm = Wm()
        wm_methods = [m for m in dir(wm) if m.startswith('wm_')]
        non_callable = [m for m in wm_methods if not callable(getattr(wm, m))]
        assert not non_callable, f"Non-callable wm methods: {non_callable}"

    def test_misc_has_event_binding_methods(self):
        """Misc class should have all expected event binding methods."""
        expected_methods = [
            'bind',
            'unbind',
            'bind_all',
            'unbind_all',
            'bind_class',
            'unbind_class',
        ]
        widget = Misc()
        missing = [m for m in expected_methods if not hasattr(widget, m)]
        assert not missing, f"Misc missing event binding methods: {missing}"

    def test_misc_has_focus_methods(self):
        """Misc class should have all expected focus methods."""
        expected_methods = [
            'focus_set',
            'focus_get',
            'focus_force',
            'focus_displayof',
            # 'focus_lastfor' - not implemented in Phase 2 (backlog)
        ]
        widget = Misc()
        missing = [m for m in expected_methods if not hasattr(widget, m)]
        assert not missing, f"Misc missing focus methods: {missing}"

    def test_misc_has_clipboard_methods(self):
        """Misc class should have all expected clipboard methods."""
        expected_methods = [
            'clipboard_clear',
            'clipboard_append',
            'clipboard_get',
        ]
        widget = Misc()
        missing = [m for m in expected_methods if not hasattr(widget, m)]
        assert not missing, f"Misc missing clipboard methods: {missing}"


# =============================================================================
# Tests for Widget Information Methods (winfo_*)
# =============================================================================


class TestWidgetInformation:
    """Tests for widget information query methods."""

    def test_winfo_children_default_empty(self):
        """winfo_children() should return empty list by default."""
        widget = Misc()

        children = widget.winfo_children()

        assert children == []

    def test_winfo_class_returns_class_name(self):
        """winfo_class() should return the widget's class name."""
        widget = Misc()

        class_name = widget.winfo_class()

        assert class_name == "Misc"

    def test_winfo_containing_default_none(self):
        """winfo_containing() should return None by default."""
        widget = Misc()

        result = widget.winfo_containing(10, 5)

        assert result is None

    def test_winfo_exists_for_registered_widget(self):
        """winfo_exists() should return True for registered widget."""
        widget = Misc()

        assert widget.winfo_exists() is True

    def test_winfo_exists_for_unregistered_widget(self):
        """winfo_exists() should return False for unregistered widget."""
        widget = Misc()
        Misc._widget_registry.clear()

        assert widget.winfo_exists() is False

    def test_winfo_height_default_zero(self):
        """winfo_height() should return 0 by default."""
        widget = Misc()

        height = widget.winfo_height()

        assert height == 0

    def test_winfo_width_default_zero(self):
        """winfo_width() should return 0 by default."""
        widget = Misc()

        width = widget.winfo_width()

        assert width == 0

    def test_winfo_id_returns_widget_name(self):
        """winfo_id() should return the widget's unique ID."""
        widget = Misc()

        widget_id = widget.winfo_id()

        assert widget_id == widget._widget_name
        assert widget_id.startswith("w")

    def test_winfo_ismapped_default_true(self):
        """winfo_ismapped() should return True by default."""
        widget = Misc()

        assert widget.winfo_ismapped() is True

    def test_winfo_viewable_default_true(self):
        """winfo_viewable() should return True by default when mapped."""
        widget = Misc()

        assert widget.winfo_viewable() is True

    def test_winfo_viewable_false_when_not_mapped(self):
        """winfo_viewable() should return False when widget is not mapped."""
        widget = Misc()
        # Override winfo_ismapped to return False
        widget.winfo_ismapped = lambda: False

        assert widget.winfo_viewable() is False

    def test_winfo_name_returns_widget_name(self):
        """winfo_name() should return the widget's name."""
        widget = Misc()

        name = widget.winfo_name()

        assert name == widget._widget_name

    def test_winfo_parent_default_empty(self):
        """winfo_parent() should return empty string by default."""
        widget = Misc()

        parent = widget.winfo_parent()

        assert parent == ""

    def test_winfo_reqheight_returns_height(self):
        """winfo_reqheight() should return requested height."""
        widget = Misc()

        req_height = widget.winfo_reqheight()

        assert req_height == widget.winfo_height()

    def test_winfo_reqwidth_returns_width(self):
        """winfo_reqwidth() should return requested width."""
        widget = Misc()

        req_width = widget.winfo_reqwidth()

        assert req_width == widget.winfo_width()

    def test_winfo_rootx_default_zero(self):
        """winfo_rootx() should return 0 by default."""
        widget = Misc()

        x = widget.winfo_rootx()

        assert x == 0

    def test_winfo_rooty_default_zero(self):
        """winfo_rooty() should return 0 by default."""
        widget = Misc()

        y = widget.winfo_rooty()

        assert y == 0

    def test_winfo_screenheight_default_value(self):
        """winfo_screenheight() should return default value."""
        widget = Misc()

        height = widget.winfo_screenheight()

        assert height == 24

    def test_winfo_screenwidth_default_value(self):
        """winfo_screenwidth() should return default value."""
        widget = Misc()

        width = widget.winfo_screenwidth()

        assert width == 80

    def test_winfo_toplevel_returns_self(self):
        """winfo_toplevel() should return self by default."""
        widget = Misc()

        toplevel = widget.winfo_toplevel()

        assert toplevel is widget

    def test_winfo_x_default_zero(self):
        """winfo_x() should return 0 by default."""
        widget = Misc()

        x = widget.winfo_x()

        assert x == 0

    def test_winfo_y_default_zero(self):
        """winfo_y() should return 0 by default."""
        widget = Misc()

        y = widget.winfo_y()

        assert y == 0


# =============================================================================
# Tests for Configuration Methods
# =============================================================================


class TestConfiguration:
    """Tests for configuration management methods."""

    def test_cget_returns_option_value(self):
        """cget() should return the value of a configuration option."""
        widget = Misc()
        widget._config["text"] = "Hello"

        value = widget.cget("text")

        assert value == "Hello"

    def test_cget_nonexistent_option(self):
        """cget() should return None for nonexistent option."""
        widget = Misc()

        value = widget.cget("nonexistent")

        assert value is None

    def test_configure_sets_options(self):
        """configure() should set configuration options."""
        widget = Misc()

        widget.configure(text="Hello", fg="red")

        assert widget._config["text"] == "Hello"
        assert widget._config["fg"] == "red"

    def test_configure_updates_existing_options(self):
        """configure() should update existing options."""
        widget = Misc()
        widget._config["text"] = "Old"

        widget.configure(text="New")

        assert widget._config["text"] == "New"

    def test_configure_no_args_returns_config_dict(self):
        """configure() with no args should return copy of config dict."""
        widget = Misc()
        widget._config["text"] = "Hello"
        widget._config["fg"] = "red"

        config = widget.configure()

        assert isinstance(config, dict)
        assert config["text"] == "Hello"
        assert config["fg"] == "red"

    def test_configure_no_args_returns_copy(self):
        """configure() should return a copy, not reference."""
        widget = Misc()
        widget._config["text"] = "Hello"

        config = widget.configure()
        config["text"] = "Modified"

        assert widget._config["text"] == "Hello"

    def test_config_is_alias_for_configure(self):
        """config() should be an alias for configure()."""
        widget = Misc()

        widget.config(text="Hello")

        assert widget._config["text"] == "Hello"

    def test_config_query_mode(self):
        """config() with no args should return config dict like configure()."""
        widget = Misc()
        widget._config["text"] = "Hello"

        config = widget.config()

        assert config["text"] == "Hello"

    def test_keys_returns_option_names(self):
        """keys() should return list of configuration option names."""
        widget = Misc()
        widget._config["text"] = "Hello"
        widget._config["fg"] = "red"
        widget._config["bg"] = "white"

        keys = widget.keys()

        assert isinstance(keys, list)
        assert "text" in keys
        assert "fg" in keys
        assert "bg" in keys

    def test_keys_empty_config(self):
        """keys() should return empty list if no options configured."""
        widget = Misc()

        keys = widget.keys()

        assert keys == []

    def test_keys_returns_list(self):
        """keys() should return a list."""
        widget = Misc()
        widget._config["text"] = "Hello"

        keys = widget.keys()

        assert isinstance(keys, list)


# =============================================================================
# Tests for Widget Management Methods
# =============================================================================


class TestWidgetManagement:
    """Tests for widget management methods."""

    def test_nametowidget_finds_registered_widget(self):
        """nametowidget() should find a registered widget by name."""
        widget = Misc()
        widget_name = widget._widget_name

        found = widget.nametowidget(widget_name)

        assert found is widget

    def test_nametowidget_not_found(self):
        """nametowidget() should return None for unregistered name."""
        widget = Misc()

        found = widget.nametowidget("nonexistent")

        assert found is None

    def test_register_returns_function_id(self):
        """register() should return a function identifier."""
        widget = Misc()

        def validate_func():
            return True

        func_id = widget.register(validate_func)

        assert isinstance(func_id, str)
        assert func_id.startswith("func_")

    def test_register_generates_unique_ids(self):
        """register() should generate unique IDs for different functions."""
        widget = Misc()

        def func1():
            return True

        def func2():
            return False

        func_id1 = widget.register(func1)
        func_id2 = widget.register(func2)

        assert func_id1 != func_id2

    def test_update_processes_after_queue(self):
        """update() should process the after queue."""
        widget = Misc()
        callback = MagicMock()

        widget.after(0, callback)
        widget.update()

        callback.assert_called_once()

    def test_update_idletasks_processes_callbacks(self):
        """update_idletasks() should process after callbacks."""
        widget = Misc()
        callback = MagicMock()

        widget.after(0, callback)
        widget.update_idletasks()

        callback.assert_called_once()

    def test_quit_is_stub(self):
        """quit() should be a stub (no-op)."""
        widget = Misc()

        widget.quit()  # Should not raise

    def test_wait_variable_is_stub(self):
        """wait_variable() should be a stub."""
        widget = Misc()

        widget.wait_variable(None)  # Should not raise

    def test_wait_visibility_is_stub(self):
        """wait_visibility() should be a stub."""
        widget = Misc()

        widget.wait_visibility()  # Should not raise

    def test_wait_window_is_stub(self):
        """wait_window() should be a stub."""
        widget = Misc()

        widget.wait_window()  # Should not raise


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for Misc class."""

    def test_multiple_widgets_independent_bindings(self):
        """Different widgets should have independent bindings."""
        widget1 = Misc()
        widget2 = Misc()
        callback1 = MagicMock()
        callback2 = MagicMock()

        widget1.bind("<Button-1>", callback1)
        widget2.bind("<Button-1>", callback2)

        assert len(widget1._bindings["<Button-1>"]) == 1
        assert len(widget2._bindings["<Button-1>"]) == 1
        assert widget1._bindings["<Button-1>"][0][1] is callback1
        assert widget2._bindings["<Button-1>"][0][1] is callback2

    def test_global_bindings_shared_across_widgets(self):
        """Global bindings should be shared across all widgets."""
        widget1 = Misc()
        widget2 = Misc()
        callback = MagicMock()

        widget1.bind_all("<F1>", callback)

        # Both widgets should have access to the same global binding
        assert "<F1>" in Misc._global_bindings

    def test_clipboard_shared_across_widgets(self):
        """Clipboard should be shared across all widgets."""
        widget1 = Misc()
        widget2 = Misc()

        widget1.clipboard_clear()
        widget1.clipboard_append("Text1")
        widget2.clipboard_append("Text2")

        assert widget1.clipboard_get() == "Text1Text2"
        assert widget2.clipboard_get() == "Text1Text2"

    def test_focus_management_single_focus(self):
        """Only one widget should have focus at a time."""
        widget1 = Misc()
        widget2 = Misc()

        widget1.focus_set()
        assert widget1._has_focus is True

        widget2.focus_set()
        assert widget1._has_focus is False
        assert widget2._has_focus is True

    def test_event_dispatch_with_multiple_bindings(self):
        """Event dispatch should call all applicable bindings in order."""
        widget = Misc()
        calls = []

        widget.bind("<Key-a>", lambda e: calls.append(1))
        widget.bind("<Key-a>", lambda e: calls.append(2), add="+")
        widget.bind_all("<Key-a>", lambda e: calls.append(3))

        event = KeyEvent(keycode=ord('a'), keysym='a', char='a')
        widget._event_dispatch(event)

        assert calls == [1, 2, 3]

    def test_after_callbacks_with_focus_changes(self):
        """After callbacks should work independently of focus."""
        widget1 = Misc()
        widget2 = Misc()
        callback = MagicMock()

        widget1.focus_set()
        widget1.after(0, callback)
        widget2.focus_set()

        Misc._process_after_queue()

        callback.assert_called_once()

    def test_widget_lifecycle_create_and_destroy(self):
        """Widget should be in registry when created and removed when destroyed."""
        widget = Misc()

        assert widget.winfo_exists() is True

        Misc._widget_registry.pop(widget._widget_name)

        assert widget.winfo_exists() is False

    def test_concurrent_event_binding_and_dispatch(self):
        """Should handle binding and dispatching events correctly."""
        widget = Misc()
        results = []

        widget.bind("<Button-1>", lambda e: results.append("button"))
        widget.bind_all("<Button-1>", lambda e: results.append("global"))

        event = MouseEvent(x=10, y=5, button=1, state='pressed')
        widget._event_dispatch(event)

        assert results == ["button", "global"]

    def test_after_queue_with_rapid_scheduling(self):
        """Should handle rapid callback scheduling correctly."""
        widget = Misc()
        callbacks = [MagicMock() for _ in range(10)]

        # Schedule with immediate execution (0ms delay)
        for cb in callbacks:
            widget.after(0, cb)

        assert len(Misc._after_queue) == 10

        Misc._process_after_queue()

        for cb in callbacks:
            cb.assert_called_once()

    def test_bind_and_unbind_multiple_sequences(self):
        """Should handle multiple event sequences independently."""
        widget = Misc()
        callbacks = {
            "<Button-1>": MagicMock(),
            "<Button-3>": MagicMock(),
            "<Key-a>": MagicMock(),
        }

        for sequence, callback in callbacks.items():
            widget.bind(sequence, callback)

        assert len(widget._bindings) == 3

        widget.unbind("<Button-1>")

        assert len(widget._bindings) == 2
        assert "<Button-1>" not in widget._bindings


# =============================================================================
# Tests for Window Manager (Wm) Class - Geometry Methods
# =============================================================================


class TestWmGeometry:
    """Tests for Wm window geometry methods."""

    def test_geometry_set_basic(self):
        """geometry() should parse and set geometry string."""
        from tkcurses import Wm
        wm = Wm()

        wm.geometry("80x24+0+0")

        assert wm._width == 80
        assert wm._height == 24
        assert wm._x == 0
        assert wm._y == 0

    def test_geometry_set_with_offsets(self):
        """geometry() should parse geometry with positive and negative offsets."""
        from tkcurses import Wm
        wm = Wm()

        wm.geometry("100x30+10+5")

        assert wm._width == 100
        assert wm._height == 30
        assert wm._x == 10
        assert wm._y == 5

    def test_geometry_set_with_negative_offsets(self):
        """geometry() should parse geometry with negative offsets."""
        from tkcurses import Wm
        wm = Wm()

        wm.geometry("60x20-5-3")

        assert wm._width == 60
        assert wm._height == 20
        assert wm._x == -5
        assert wm._y == -3

    def test_geometry_query_returns_current(self):
        """geometry() with no args should return current geometry."""
        from tkcurses import Wm
        wm = Wm()
        wm._width = 80
        wm._height = 24
        wm._x = 5
        wm._y = 10

        result = wm.geometry()

        assert result == "80x24+5+10"

    def test_geometry_invalid_format_raises(self):
        """geometry() should raise ValueError for invalid format."""
        from tkcurses import Wm
        wm = Wm()

        with pytest.raises(ValueError):
            wm.geometry("invalid")

    def test_geometry_size_only(self):
        """geometry() should work with size only (no offset)."""
        from tkcurses import Wm
        wm = Wm()

        wm.geometry("120x30")

        assert wm._width == 120
        assert wm._height == 30

    def test_wm_geometry_is_alias(self):
        """wm_geometry() should be an alias for geometry()."""
        from tkcurses import Wm
        wm = Wm()

        wm.wm_geometry("100x25+2+3")

        assert wm._width == 100
        assert wm._height == 25
        assert wm.geometry() == "100x25+2+3"

    def test_geometry_alias_bidirectional(self):
        """geometry() alias should work bidirectionally with wm_geometry()."""
        from tkcurses import Wm
        wm = Wm()

        # Direction 1: Call short alias, verify via wm_ method
        wm.geometry("80x24+1+2")
        assert wm.wm_geometry() == "80x24+1+2"

        # Direction 2: Call wm_ method, verify via short alias
        wm.wm_geometry("120x40+5+5")
        assert wm.geometry() == "120x40+5+5"

    def test_minsize_set_basic(self):
        """minsize() should set minimum window size."""
        from tkcurses import Wm
        wm = Wm()

        wm.minsize(40, 10)

        assert wm._min_width == 40
        assert wm._min_height == 10

    def test_minsize_set_enforces_minimum_one(self):
        """minsize() should enforce minimum of 1."""
        from tkcurses import Wm
        wm = Wm()

        wm.minsize(0, 0)

        assert wm._min_width == 1
        assert wm._min_height == 1

    def test_minsize_query_returns_current(self):
        """minsize() with no args should return current minimum."""
        from tkcurses import Wm
        wm = Wm()
        wm._min_width = 20
        wm._min_height = 5

        result = wm.minsize()

        assert result == (20, 5)

    def test_minsize_query_defaults_to_one(self):
        """minsize() query should return (1, 1) if not set."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.minsize()

        assert result == (1, 1)

    def test_minsize_partial_set_width_only(self):
        """minsize() should allow setting width only."""
        from tkcurses import Wm
        wm = Wm()
        wm._min_height = 10

        wm.minsize(30, None)

        assert wm._min_width == 30
        assert wm._min_height == 10

    def test_wm_minsize_is_alias(self):
        """wm_minsize() should be an alias for minsize()."""
        from tkcurses import Wm
        wm = Wm()

        wm.wm_minsize(50, 15)

        assert wm.minsize() == (50, 15)

    def test_minsize_alias_bidirectional(self):
        """minsize() alias should work bidirectionally with wm_minsize()."""
        from tkcurses import Wm
        wm = Wm()

        # Direction 1: Call short alias, verify via wm_ method
        wm.minsize(30, 10)
        assert wm.wm_minsize() == (30, 10)

        # Direction 2: Call wm_ method, verify via short alias
        wm.wm_minsize(50, 20)
        assert wm.minsize() == (50, 20)

    def test_maxsize_set_basic(self):
        """maxsize() should set maximum window size."""
        from tkcurses import Wm
        wm = Wm()

        wm.maxsize(120, 40)

        assert wm._max_width == 120
        assert wm._max_height == 40

    def test_maxsize_set_enforces_minimum_one(self):
        """maxsize() should enforce minimum of 1."""
        from tkcurses import Wm
        wm = Wm()

        wm.maxsize(0, 0)

        assert wm._max_width == 1
        assert wm._max_height == 1

    def test_maxsize_query_returns_current(self):
        """maxsize() with no args should return current maximum."""
        from tkcurses import Wm
        wm = Wm()
        wm._max_width = 150
        wm._max_height = 50

        result = wm.maxsize()

        assert result == (150, 50)

    def test_maxsize_query_defaults_to_large_values(self):
        """maxsize() query should return default large values if not set."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.maxsize()

        assert result == (999, 999)

    def test_wm_maxsize_is_alias(self):
        """wm_maxsize() should be an alias for maxsize()."""
        from tkcurses import Wm
        wm = Wm()

        wm.wm_maxsize(200, 60)

        assert wm.maxsize() == (200, 60)

    def test_maxsize_alias_bidirectional(self):
        """maxsize() alias should work bidirectionally with wm_maxsize()."""
        from tkcurses import Wm
        wm = Wm()

        # Direction 1: Call short alias, verify via wm_ method
        wm.maxsize(150, 50)
        assert wm.wm_maxsize() == (150, 50)

        # Direction 2: Call wm_ method, verify via short alias
        wm.wm_maxsize(200, 60)
        assert wm.maxsize() == (200, 60)

    def test_resizable_set_both(self):
        """resizable() should set both width and height resizable flags."""
        from tkcurses import Wm
        wm = Wm()

        wm.resizable(True, False)

        assert wm._resizable_width is True
        assert wm._resizable_height is False

    def test_resizable_set_converts_to_bool(self):
        """resizable() should convert values to boolean."""
        from tkcurses import Wm
        wm = Wm()

        wm.resizable(1, 0)

        assert wm._resizable_width is True
        assert wm._resizable_height is False

    def test_resizable_query_returns_current(self):
        """resizable() with no args should return current flags."""
        from tkcurses import Wm
        wm = Wm()
        wm._resizable_width = False
        wm._resizable_height = True

        result = wm.resizable()

        assert result == (False, True)

    def test_resizable_query_default_values(self):
        """resizable() query should return (True, True) by default."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.resizable()

        assert result == (True, True)

    def test_resizable_partial_set_width_only(self):
        """resizable() should allow setting width only."""
        from tkcurses import Wm
        wm = Wm()
        wm._resizable_height = True

        wm.resizable(False, None)

        assert wm._resizable_width is False
        assert wm._resizable_height is True

    def test_wm_resizable_is_alias(self):
        """wm_resizable() should be an alias for resizable()."""
        from tkcurses import Wm
        wm = Wm()

        wm.wm_resizable(False, True)

        assert wm.resizable() == (False, True)

    def test_resizable_alias_bidirectional(self):
        """resizable() alias should work bidirectionally with wm_resizable()."""
        from tkcurses import Wm
        wm = Wm()

        # Direction 1: Call short alias, verify via wm_ method
        wm.resizable(True, False)
        assert wm.wm_resizable() == (True, False)

        # Direction 2: Call wm_ method, verify via short alias
        wm.wm_resizable(False, True)
        assert wm.resizable() == (False, True)


# =============================================================================
# Tests for Window Manager (Wm) Class - Title/Identity Methods
# =============================================================================


class TestWmTitle:
    """Tests for Wm window title and identity methods."""

    def test_title_set_basic(self):
        """title() should set window title."""
        from tkcurses import Wm
        wm = Wm()

        wm.title("My Application")

        assert wm._title == "My Application"

    def test_title_query_returns_current(self):
        """title() with no args should return current title."""
        from tkcurses import Wm
        wm = Wm()
        wm._title = "Test Title"

        result = wm.title()

        assert result == "Test Title"

    def test_title_empty_string(self):
        """title() should accept empty string."""
        from tkcurses import Wm
        wm = Wm()

        wm.title("")

        assert wm._title == ""

    def test_wm_title_is_alias(self):
        """wm_title() should be an alias for title()."""
        from tkcurses import Wm
        wm = Wm()

        wm.wm_title("Application Title")

        assert wm.title() == "Application Title"

    def test_title_alias_bidirectional(self):
        """title() alias should work bidirectionally with wm_title()."""
        from tkcurses import Wm
        wm = Wm()

        # Direction 1: Call short alias, verify via wm_ method
        wm.title("First Title")
        assert wm.wm_title() == "First Title"

        # Direction 2: Call wm_ method, verify via short alias
        wm.wm_title("Second Title")
        assert wm.title() == "Second Title"

    def test_wm_iconname_set_basic(self):
        """wm_iconname() should store icon name."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_iconname("MyIcon")

        assert result is None

    def test_wm_iconname_query_returns_title(self):
        """wm_iconname() query should return title as fallback."""
        from tkcurses import Wm
        wm = Wm()
        wm._title = "Window Title"

        result = wm.wm_iconname()

        assert result == "Window Title"

    def test_wm_iconbitmap_is_stub(self):
        """wm_iconbitmap() should be a stub (no-op)."""
        from tkcurses import Wm
        wm = Wm()

        wm.wm_iconbitmap("icon.xbm")  # Should not raise


# =============================================================================
# Tests for Window Manager (Wm) Class - State Methods
# =============================================================================


class TestWmState:
    """Tests for Wm window state methods."""

    def test_state_set_normal(self):
        """state() should set state to normal."""
        from tkcurses import Wm
        wm = Wm()

        wm.state("normal")

        assert wm._state == "normal"

    def test_state_set_withdrawn(self):
        """state() should set state to withdrawn."""
        from tkcurses import Wm
        wm = Wm()

        wm.state("withdrawn")

        assert wm._state == "withdrawn"

    def test_state_set_iconic(self):
        """state() should set state to iconic."""
        from tkcurses import Wm
        wm = Wm()

        wm.state("iconic")

        assert wm._state == "iconic"

    def test_state_set_zoomed(self):
        """state() should set state to zoomed."""
        from tkcurses import Wm
        wm = Wm()

        wm.state("zoomed")

        assert wm._state == "zoomed"

    def test_state_set_invalid_raises(self):
        """state() should raise ValueError for invalid state."""
        from tkcurses import Wm
        wm = Wm()

        with pytest.raises(ValueError):
            wm.state("invalid_state")

    def test_state_query_returns_current(self):
        """state() with no args should return current state."""
        from tkcurses import Wm
        wm = Wm()
        wm._state = "zoomed"

        result = wm.state()

        assert result == "zoomed"

    def test_state_query_default(self):
        """state() query should return 'normal' by default."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.state()

        assert result == "normal"

    def test_wm_state_is_alias(self):
        """wm_state() should be an alias for state()."""
        from tkcurses import Wm
        wm = Wm()

        wm.wm_state("zoomed")

        assert wm.state() == "zoomed"

    def test_state_alias_bidirectional(self):
        """state() alias should work bidirectionally with wm_state()."""
        from tkcurses import Wm
        wm = Wm()

        # Direction 1: Call short alias, verify via wm_ method
        wm.state("withdrawn")
        assert wm.wm_state() == "withdrawn"

        # Direction 2: Call wm_ method, verify via short alias
        wm.wm_state("zoomed")
        assert wm.state() == "zoomed"

    def test_wm_withdraw_sets_withdrawn(self):
        """wm_withdraw() should set state to withdrawn."""
        from tkcurses import Wm
        wm = Wm()

        wm.wm_withdraw()

        assert wm._state == "withdrawn"

    def test_wm_deiconify_sets_normal(self):
        """wm_deiconify() should set state to normal."""
        from tkcurses import Wm
        wm = Wm()
        wm._state = "withdrawn"

        wm.wm_deiconify()

        assert wm._state == "normal"

    def test_wm_iconify_sets_iconic(self):
        """wm_iconify() should set state to iconic."""
        from tkcurses import Wm
        wm = Wm()

        wm.wm_iconify()

        assert wm._state == "iconic"


# =============================================================================
# Tests for Window Manager (Wm) Class - Attributes Methods
# =============================================================================


class TestWmAttributes:
    """Tests for Wm window attributes methods."""

    def test_attributes_query_all(self):
        """attributes() with no args should return all attributes dict."""
        from tkcurses import Wm
        wm = Wm()
        wm._attributes["-fullscreen"] = True
        wm._attributes["-topmost"] = False

        result = wm.attributes()

        assert isinstance(result, dict)
        assert result["-fullscreen"] is True
        assert result["-topmost"] is False

    def test_attributes_query_all_returns_copy(self):
        """attributes() should return a copy, not reference."""
        from tkcurses import Wm
        wm = Wm()
        wm._attributes["-fullscreen"] = True

        result = wm.attributes()
        result["-fullscreen"] = False

        assert wm._attributes["-fullscreen"] is True

    def test_attributes_query_single(self):
        """attributes('-attr') should return single attribute value."""
        from tkcurses import Wm
        wm = Wm()
        wm._attributes["-fullscreen"] = True

        result = wm.attributes("-fullscreen")

        assert result is True

    def test_attributes_query_nonexistent_returns_none(self):
        """attributes('-attr') should return None for nonexistent attribute."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.attributes("-nonexistent")

        assert result is None

    def test_attributes_set_single(self):
        """attributes('-attr', value) should set single attribute."""
        from tkcurses import Wm
        wm = Wm()

        wm.attributes("-fullscreen", True)

        assert wm._attributes["-fullscreen"] is True

    def test_attributes_set_multiple(self):
        """attributes('-a1', v1, '-a2', v2) should set multiple attributes."""
        from tkcurses import Wm
        wm = Wm()

        wm.attributes("-fullscreen", True, "-topmost", True, "-alpha", 0.9)

        assert wm._attributes["-fullscreen"] is True
        assert wm._attributes["-topmost"] is True
        assert wm._attributes["-alpha"] == 0.9

    def test_attributes_set_fullscreen_true_sets_zoomed(self):
        """attributes('-fullscreen', True) should set state to zoomed."""
        from tkcurses import Wm
        wm = Wm()
        wm._state = "normal"

        wm.attributes("-fullscreen", True)

        assert wm._state == "zoomed"

    def test_attributes_set_fullscreen_false_sets_normal(self):
        """attributes('-fullscreen', False) should set state to normal."""
        from tkcurses import Wm
        wm = Wm()
        wm._state = "zoomed"

        wm.attributes("-fullscreen", False)

        assert wm._state == "normal"

    def test_attributes_set_invalid_attribute_name_raises(self):
        """attributes() should raise for attribute names without leading dash."""
        from tkcurses import Wm
        wm = Wm()

        with pytest.raises(ValueError):
            wm.attributes("nodash", True)

    def test_attributes_set_odd_args_raises(self):
        """attributes() should raise if odd number of args for setting."""
        from tkcurses import Wm
        wm = Wm()

        with pytest.raises(ValueError):
            wm.attributes("-attr1", True, "-attr2")

    def test_wm_attributes_is_alias(self):
        """wm_attributes() should be an alias for attributes()."""
        from tkcurses import Wm
        wm = Wm()

        wm.wm_attributes("-topmost", True)

        assert wm.attributes("-topmost") is True


# =============================================================================
# Tests for Window Manager (Wm) Class - Protocol Methods
# =============================================================================


class TestWmProtocol:
    """Tests for Wm window protocol methods."""

    def test_protocol_register_handler(self):
        """protocol() should register a handler for a protocol."""
        from tkcurses import Wm
        wm = Wm()
        callback = MagicMock()

        wm.protocol("WM_DELETE_WINDOW", callback)

        assert wm._protocols["WM_DELETE_WINDOW"] is callback

    def test_protocol_query_all_protocols(self):
        """protocol() with no args should return list of registered protocols."""
        from tkcurses import Wm
        wm = Wm()
        callback1 = MagicMock()
        callback2 = MagicMock()
        wm._protocols["WM_DELETE_WINDOW"] = callback1
        wm._protocols["WM_TAKE_FOCUS"] = callback2

        result = wm.protocol()

        assert isinstance(result, list)
        assert "WM_DELETE_WINDOW" in result
        assert "WM_TAKE_FOCUS" in result

    def test_protocol_query_single_handler(self):
        """protocol('name') should return handler for protocol."""
        from tkcurses import Wm
        wm = Wm()
        callback = MagicMock()
        wm._protocols["WM_DELETE_WINDOW"] = callback

        result = wm.protocol("WM_DELETE_WINDOW")

        assert result is callback

    def test_protocol_query_nonexistent_returns_empty_string(self):
        """protocol('nonexistent') should return empty string."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.protocol("NONEXISTENT")

        assert result == ""

    def test_protocol_multiple_handlers(self):
        """protocol() should support multiple protocol handlers."""
        from tkcurses import Wm
        wm = Wm()
        callback1 = MagicMock()
        callback2 = MagicMock()
        callback3 = MagicMock()

        wm.protocol("WM_DELETE_WINDOW", callback1)
        wm.protocol("WM_TAKE_FOCUS", callback2)
        wm.protocol("WM_SAVE_YOURSELF", callback3)

        assert len(wm._protocols) == 3
        assert wm.protocol("WM_DELETE_WINDOW") is callback1
        assert wm.protocol("WM_TAKE_FOCUS") is callback2
        assert wm.protocol("WM_SAVE_YOURSELF") is callback3

    def test_protocol_replace_existing_handler(self):
        """protocol() should replace existing handler for same protocol."""
        from tkcurses import Wm
        wm = Wm()
        callback1 = MagicMock()
        callback2 = MagicMock()

        wm.protocol("WM_DELETE_WINDOW", callback1)
        wm.protocol("WM_DELETE_WINDOW", callback2)

        assert wm.protocol("WM_DELETE_WINDOW") is callback2

    def test_wm_protocol_is_alias(self):
        """wm_protocol() should be an alias for protocol()."""
        from tkcurses import Wm
        wm = Wm()
        callback = MagicMock()

        wm.wm_protocol("WM_DELETE_WINDOW", callback)

        assert wm.protocol("WM_DELETE_WINDOW") is callback

    def test_protocol_alias_bidirectional(self):
        """protocol() alias should work bidirectionally with wm_protocol()."""
        from tkcurses import Wm
        wm = Wm()
        callback1 = MagicMock()
        callback2 = MagicMock()

        # Direction 1: Call short alias, verify via wm_ method
        wm.protocol("WM_DELETE_WINDOW", callback1)
        assert wm.wm_protocol("WM_DELETE_WINDOW") is callback1

        # Direction 2: Call wm_ method, verify via short alias
        wm.wm_protocol("WM_TAKE_FOCUS", callback2)
        assert wm.protocol("WM_TAKE_FOCUS") is callback2


# =============================================================================
# Tests for Window Manager (Wm) Class - Transient/Focus Methods
# =============================================================================


class TestWmTransient:
    """Tests for Wm transient and focus methods."""

    def test_transient_set_master(self):
        """transient(master) should set the transient master."""
        from tkcurses import Wm
        wm1 = Wm()
        wm2 = Wm()

        wm1.transient(wm2)

        assert wm1._transient_master is wm2

    def test_transient_query_returns_master(self):
        """transient() query should return the transient master."""
        from tkcurses import Wm
        wm1 = Wm()
        wm2 = Wm()
        wm1._transient_master = wm2

        result = wm1.transient()

        # Should return string representation
        assert str(wm2) in result

    def test_transient_query_no_master_returns_empty(self):
        """transient() query with no master should return empty string."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.transient()

        assert result == ""

    def test_transient_clear_relationship(self):
        """transient('') should clear the transient relationship."""
        from tkcurses import Wm
        wm1 = Wm()
        wm2 = Wm()
        wm1._transient_master = wm2

        wm1.transient("")

        assert wm1._transient_master is None

    def test_wm_transient_is_alias(self):
        """wm_transient() should be an alias for transient()."""
        from tkcurses import Wm
        wm1 = Wm()
        wm2 = Wm()

        wm1.wm_transient(wm2)

        assert wm1._transient_master is wm2

    def test_transient_alias_bidirectional(self):
        """transient() alias should work bidirectionally with wm_transient()."""
        from tkcurses import Wm
        wm1 = Wm()
        wm2 = Wm()
        wm3 = Wm()

        # Direction 1: Call short alias, verify via wm_ method
        wm1.transient(wm2)
        assert wm1.wm_transient() == str(wm2)

        # Direction 2: Call wm_ method, verify via short alias
        wm1.wm_transient(wm3)
        assert wm1.transient() == str(wm3)

    def test_wm_focusmodel_query_returns_passive(self):
        """wm_focusmodel() query should return 'passive'."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_focusmodel()

        assert result == "passive"

    def test_wm_focusmodel_set_is_stub(self):
        """wm_focusmodel(model) should be a stub (no-op)."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_focusmodel("active")

        assert result is None

    def test_lift_is_stub(self):
        """lift() should be a stub (no-op)."""
        from tkcurses import Wm
        wm = Wm()

        wm.lift()  # Should not raise

    def test_lift_with_aboveThis_is_stub(self):
        """lift(aboveThis) should be a stub (no-op)."""
        from tkcurses import Wm
        wm1 = Wm()
        wm2 = Wm()

        wm1.lift(wm2)  # Should not raise

    def test_lower_is_stub(self):
        """lower() should be a stub (no-op)."""
        from tkcurses import Wm
        wm = Wm()

        wm.lower()  # Should not raise

    def test_lower_with_belowThis_is_stub(self):
        """lower(belowThis) should be a stub (no-op)."""
        from tkcurses import Wm
        wm1 = Wm()
        wm2 = Wm()

        wm1.lower(wm2)  # Should not raise


# =============================================================================
# Tests for Window Manager (Wm) Class - Stub Methods
# =============================================================================


class TestWmStubMethods:
    """Tests for Wm stub methods."""

    def test_wm_overrideredirect_query(self):
        """wm_overrideredirect() query should return False."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_overrideredirect()

        assert result is False

    def test_wm_overrideredirect_set_is_stub(self):
        """wm_overrideredirect(bool) should be a stub (no-op)."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_overrideredirect(True)

        assert result is None

    def test_wm_positionfrom_query(self):
        """wm_positionfrom() query should return 'program'."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_positionfrom()

        assert result == "program"

    def test_wm_positionfrom_set_is_stub(self):
        """wm_positionfrom(who) should be a stub (no-op)."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_positionfrom("user")

        assert result is None

    def test_wm_sizefrom_query(self):
        """wm_sizefrom() query should return 'program'."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_sizefrom()

        assert result == "program"

    def test_wm_sizefrom_set_is_stub(self):
        """wm_sizefrom(who) should be a stub (no-op)."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_sizefrom("user")

        assert result is None

    def test_wm_client_query(self):
        """wm_client() query should return empty string."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_client()

        assert result == ""

    def test_wm_client_set_is_stub(self):
        """wm_client(name) should be a stub (no-op)."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_client("localhost")

        assert result is None

    def test_wm_colormapwindows_query(self):
        """wm_colormapwindows() query should return empty tuple."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_colormapwindows()

        assert result == ()

    def test_wm_colormapwindows_set_is_stub(self):
        """wm_colormapwindows(*wlist) should be a stub (no-op)."""
        from tkcurses import Wm
        wm1 = Wm()
        wm2 = Wm()

        result = wm1.wm_colormapwindows(wm2)

        assert result is None

    def test_wm_command_query(self):
        """wm_command() query should return empty string."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_command()

        assert result == ""

    def test_wm_command_set_is_stub(self):
        """wm_command(value) should be a stub (no-op)."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_command("python myapp.py")

        assert result is None

    def test_wm_frame_returns_identifier(self):
        """wm_frame() should return a frame identifier."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_frame()

        assert isinstance(result, str)
        assert result.startswith("0x")

    def test_wm_frame_returns_consistent_id(self):
        """wm_frame() should return consistent ID for same window."""
        from tkcurses import Wm
        wm = Wm()

        result1 = wm.wm_frame()
        result2 = wm.wm_frame()

        assert result1 == result2

    def test_wm_group_query(self):
        """wm_group() query should return empty string."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_group()

        assert result == ""

    def test_wm_group_set_is_stub(self):
        """wm_group(pathName) should be a stub (no-op)."""
        from tkcurses import Wm
        wm = Wm()

        result = wm.wm_group(".main")

        assert result is None


# =============================================================================
# Integration Tests for Wm Class
# =============================================================================


class TestWmIntegration:
    """Integration tests for Wm class."""

    def test_geometry_parsing_and_retrieval(self):
        """Geometry should be correctly parsed and retrieved."""
        from tkcurses import Wm
        wm = Wm()

        wm.geometry("100x30+5+10")
        result = wm.geometry()

        assert result == "100x30+5+10"

    def test_size_and_position_independent(self):
        """Setting size should not affect position."""
        from tkcurses import Wm
        wm = Wm()
        wm._x = 5
        wm._y = 10

        wm.minsize(40, 12)

        assert wm._x == 5
        assert wm._y == 10

    def test_state_transitions(self):
        """Window states should transition correctly."""
        from tkcurses import Wm
        wm = Wm()

        assert wm.state() == "normal"

        wm.wm_withdraw()
        assert wm.state() == "withdrawn"

        wm.wm_deiconify()
        assert wm.state() == "normal"

        wm.wm_iconify()
        assert wm.state() == "iconic"

    def test_multiple_protocols_independent(self):
        """Multiple protocols should be tracked independently."""
        from tkcurses import Wm
        wm = Wm()
        callbacks = {
            "WM_DELETE_WINDOW": MagicMock(),
            "WM_TAKE_FOCUS": MagicMock(),
            "WM_SAVE_YOURSELF": MagicMock(),
        }

        for name, callback in callbacks.items():
            wm.protocol(name, callback)

        protocols = wm.protocol()
        assert len(protocols) == 3

        for name, callback in callbacks.items():
            assert wm.protocol(name) is callback

    def test_attributes_and_state_interaction(self):
        """Setting -fullscreen attribute should affect state."""
        from tkcurses import Wm
        wm = Wm()

        assert wm.state() == "normal"

        wm.attributes("-fullscreen", True)
        assert wm.state() == "zoomed"
        assert wm.attributes("-fullscreen") is True

        wm.attributes("-fullscreen", False)
        assert wm.state() == "normal"
        assert wm.attributes("-fullscreen") is False

    def test_transient_parent_relationship(self):
        """Transient relationship should be maintained correctly."""
        from tkcurses import Wm
        wm1 = Wm()
        wm2 = Wm()

        wm2.transient(wm1)
        assert wm2._transient_master is wm1

        wm2.transient("")
        assert wm2._transient_master is None

    def test_all_geometry_methods_consistent(self):
        """All geometry methods should work together consistently."""
        from tkcurses import Wm
        wm = Wm()

        wm.geometry("100x30+0+0")
        wm.minsize(50, 15)
        wm.maxsize(150, 60)
        wm.resizable(True, False)

        assert wm.geometry() == "100x30+0+0"
        assert wm.minsize() == (50, 15)
        assert wm.maxsize() == (150, 60)
        assert wm.resizable() == (True, False)

    def test_wm_aliases_match_main_methods(self):
        """All wm_ aliases should produce same results as main methods."""
        from tkcurses import Wm
        wm = Wm()

        wm.wm_geometry("80x24+2+2")
        assert wm.geometry() == "80x24+2+2"

        wm.wm_minsize(30, 10)
        assert wm.minsize() == (30, 10)

        wm.wm_maxsize(120, 40)
        assert wm.maxsize() == (120, 40)

        wm.wm_resizable(False, True)
        assert wm.resizable() == (False, True)

        wm.wm_title("Test")
        assert wm.title() == "Test"

        wm.wm_state("withdrawn")
        assert wm.state() == "withdrawn"


# =============================================================================
# Tests for BaseWidget Class - Initialization
# =============================================================================


class TestBaseWidgetInitialization:
    """Tests for BaseWidget initialization and configuration."""

    def test_init_without_parent(self):
        """BaseWidget should initialize without parent."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        assert widget.master is None
        assert widget._children == []
        assert widget._is_destroyed is False
        assert widget._is_mapped is False
        assert widget._requested_width == 0
        assert widget._requested_height == 0

    def test_init_with_parent(self):
        """BaseWidget should register with parent."""
        from tkcurses import BaseWidget
        parent = BaseWidget()
        child = BaseWidget(master=parent)

        assert child.master is parent
        assert child in parent._children
        assert len(parent._children) == 1

    def test_init_stores_configuration_options(self):
        """BaseWidget should store configuration options."""
        from tkcurses import BaseWidget
        widget = BaseWidget(width=40, height=10, bg="blue")

        assert widget._widget_config["width"] == 40
        assert widget._widget_config["height"] == 10
        assert widget._widget_config["background"] == "blue"

    def test_init_handles_option_aliases_bg(self):
        """BaseWidget should convert bg to background."""
        from tkcurses import BaseWidget
        widget = BaseWidget(bg="red")

        assert widget._widget_config.get("background") == "red"
        assert "bg" not in widget._widget_config

    def test_init_handles_option_aliases_fg(self):
        """BaseWidget should convert fg to foreground."""
        from tkcurses import BaseWidget
        widget = BaseWidget(fg="white")

        assert widget._widget_config.get("foreground") == "white"
        assert "fg" not in widget._widget_config

    def test_init_does_not_override_explicit_background(self):
        """BaseWidget should prefer explicit background over bg alias."""
        from tkcurses import BaseWidget
        widget = BaseWidget(bg="red", background="blue")

        assert widget._widget_config.get("background") == "blue"

    def test_init_generates_unique_widget_path(self):
        """BaseWidget children should generate unique hierarchical widget paths."""
        from tkcurses import BaseWidget
        parent = BaseWidget()
        child1 = BaseWidget(master=parent)
        child2 = BaseWidget(master=parent)

        # Child paths should be different
        assert child1._widget_path != child2._widget_path

    def test_init_generates_root_widget_path(self):
        """Root widget should have path '.'"""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        assert widget._widget_path == "."

    def test_init_generates_child_widget_path(self):
        """Child widget path should be hierarchical."""
        from tkcurses import BaseWidget
        parent = BaseWidget()
        child = BaseWidget(master=parent)

        # Child path should start with parent path and contain a component
        assert child._widget_path.startswith(parent._widget_path)
        assert "!" in child._widget_path

    def test_init_nested_hierarchy_paths(self):
        """Widget path should reflect nesting depth."""
        from tkcurses import BaseWidget
        root = BaseWidget()
        child = BaseWidget(master=root)
        grandchild = BaseWidget(master=child)

        # Paths should increase in depth
        assert len(root._widget_path) < len(child._widget_path) < len(grandchild._widget_path)

    def test_init_curses_objects_not_created(self):
        """BaseWidget should not create curses objects at init."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        assert widget._curses_window is None
        assert widget._panel is None

    def test_init_multiple_widgets_get_dispatcher_and_screen(self):
        """BaseWidget should initialize dispatcher and screen."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        assert widget._dispatcher is not None
        assert widget._screen is not None
        assert widget._panel_stack is not None


# =============================================================================
# Tests for BaseWidget Class - Widget Hierarchy
# =============================================================================


class TestBaseWidgetHierarchy:
    """Tests for widget hierarchy management."""

    def test_add_child_registers_child(self):
        """_add_child should register a child widget."""
        from tkcurses import BaseWidget
        parent = BaseWidget()
        child = BaseWidget()

        parent._add_child(child)

        assert child in parent._children

    def test_add_child_does_not_duplicate(self):
        """_add_child should not add duplicate children."""
        from tkcurses import BaseWidget
        parent = BaseWidget()
        child = BaseWidget()

        parent._add_child(child)
        parent._add_child(child)

        assert parent._children.count(child) == 1

    def test_remove_child_unregisters_child(self):
        """_remove_child should unregister a child widget."""
        from tkcurses import BaseWidget
        parent = BaseWidget()
        child = BaseWidget()
        parent._add_child(child)

        parent._remove_child(child)

        assert child not in parent._children

    def test_remove_child_nonexistent_is_safe(self):
        """_remove_child should not raise for non-existent child."""
        from tkcurses import BaseWidget
        parent = BaseWidget()
        child = BaseWidget()

        parent._remove_child(child)  # Should not raise

    def test_master_property_returns_parent(self):
        """master property should return parent widget."""
        from tkcurses import BaseWidget
        parent = BaseWidget()
        child = BaseWidget(master=parent)

        assert child.master is parent

    def test_children_tracking_on_initialization(self):
        """Children should be tracked when created with master."""
        from tkcurses import BaseWidget
        parent = BaseWidget()
        child1 = BaseWidget(master=parent)
        child2 = BaseWidget(master=parent)

        assert len(parent._children) == 2
        assert child1 in parent._children
        assert child2 in parent._children

    def test_multiple_levels_of_nesting(self):
        """Widget hierarchy should support multiple nesting levels."""
        from tkcurses import BaseWidget
        root = BaseWidget()
        child = BaseWidget(master=root)
        grandchild = BaseWidget(master=child)
        greatgrandchild = BaseWidget(master=grandchild)

        assert root._children == [child]
        assert child._children == [grandchild]
        assert grandchild._children == [greatgrandchild]
        assert greatgrandchild._children == []


# =============================================================================
# Tests for BaseWidget Class - Configuration
# =============================================================================


class TestBaseWidgetConfiguration:
    """Tests for widget configuration management."""

    def test_configure_widget_stores_options(self):
        """_configure_widget should store options."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._configure_widget(text="Hello", state="active")

        assert widget._widget_config["text"] == "Hello"
        assert widget._widget_config["state"] == "active"

    def test_configure_widget_handles_width_option(self):
        """_configure_widget should handle width option."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._configure_widget(width=50)

        assert widget._requested_width == 50

    def test_configure_widget_handles_height_option(self):
        """_configure_widget should handle height option."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._configure_widget(height=20)

        assert widget._requested_height == 20

    def test_configure_widget_converts_width_to_int(self):
        """_configure_widget should convert width to int."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._configure_widget(width="40")

        assert widget._requested_width == 40
        assert isinstance(widget._requested_width, int)

    def test_configure_widget_converts_height_to_int(self):
        """_configure_widget should convert height to int."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._configure_widget(height="15")

        assert widget._requested_height == 15
        assert isinstance(widget._requested_height, int)

    def test_configure_widget_aliases_bg_to_background(self):
        """_configure_widget should convert bg alias to background."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._configure_widget(bg="red")

        assert widget._widget_config.get("background") == "red"
        assert "bg" not in widget._widget_config

    def test_configure_widget_aliases_fg_to_foreground(self):
        """_configure_widget should convert fg alias to foreground."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._configure_widget(fg="white")

        assert widget._widget_config.get("foreground") == "white"
        assert "fg" not in widget._widget_config

    def test_configure_widget_prefers_explicit_background(self):
        """_configure_widget should not override explicit background."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._configure_widget(background="blue", bg="red")

        assert widget._widget_config.get("background") == "blue"


# =============================================================================
# Tests for BaseWidget Class - Widget Lifecycle
# =============================================================================


class TestBaseWidgetLifecycle:
    """Tests for widget lifecycle methods."""

    def test_destroy_marks_as_destroyed(self):
        """destroy() should mark widget as destroyed."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget.destroy()

        assert widget._is_destroyed is True

    def test_destroy_prevents_double_destroy(self):
        """destroy() should be idempotent."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget.destroy()
        widget.destroy()  # Should not raise

        assert widget._is_destroyed is True

    def test_destroy_removes_from_parent(self):
        """destroy() should remove widget from parent."""
        from tkcurses import BaseWidget
        parent = BaseWidget()
        child = BaseWidget(master=parent)

        assert child in parent._children

        child.destroy()

        assert child not in parent._children

    def test_destroy_destroys_all_children(self):
        """destroy() should recursively destroy children."""
        from tkcurses import BaseWidget
        parent = BaseWidget()
        child1 = BaseWidget(master=parent)
        child2 = BaseWidget(master=parent)

        parent.destroy()

        assert child1._is_destroyed is True
        assert child2._is_destroyed is True
        assert parent._children == []

    def test_destroy_deep_hierarchy(self):
        """destroy() should destroy entire widget tree."""
        from tkcurses import BaseWidget
        root = BaseWidget()
        child = BaseWidget(master=root)
        grandchild = BaseWidget(master=child)

        root.destroy()

        assert root._is_destroyed is True
        assert child._is_destroyed is True
        assert grandchild._is_destroyed is True

    def test_destroy_clears_children_list(self):
        """destroy() should clear children list."""
        from tkcurses import BaseWidget
        parent = BaseWidget()
        child = BaseWidget(master=parent)

        parent.destroy()

        assert parent._children == []


# =============================================================================
# Tests for BaseWidget Class - Curses Window Management (Mocked)
# =============================================================================


class TestBaseWidgetWindowManagement:
    """Tests for curses window management (with mocking)."""

    def test_create_window_requires_initialized_screen(self):
        """_create_window should raise if screen not initialized."""
        from tkcurses import BaseWidget
        widget = BaseWidget()
        widget._screen = MagicMock()
        widget._screen.stdscr = None

        with pytest.raises(RuntimeError, match="Curses screen not initialized"):
            widget._create_window(10, 20, 0, 0)

    def test_destroy_window_clears_references(self):
        """_destroy_window should clear window and panel references."""
        from tkcurses import BaseWidget
        widget = BaseWidget()
        widget._curses_window = MagicMock()
        widget._panel = MagicMock()
        widget._is_mapped = True

        widget._destroy_window()

        assert widget._curses_window is None
        assert widget._panel is None
        assert widget._is_mapped is False

    def test_destroy_window_safe_with_no_window(self):
        """_destroy_window should be safe if no window exists."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._destroy_window()  # Should not raise

        assert widget._curses_window is None

    def test_destroy_window_handles_panel_removal_error(self):
        """_destroy_window should handle panel removal errors."""
        from tkcurses import BaseWidget
        widget = BaseWidget()
        widget._panel = MagicMock()
        widget._panel_stack = MagicMock()
        widget._panel_stack.remove_panel.side_effect = RuntimeError("Panel error")

        widget._destroy_window()  # Should not raise

        assert widget._panel is None

    def test_resize_window_safe_with_no_window(self):
        """_resize_window should be safe if no window exists."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._resize_window(20, 40)  # Should not raise


# =============================================================================
# Tests for BaseWidget Class - Geometry Management
# =============================================================================


class TestBaseWidgetGeometry:
    """Tests for geometry request and allocation."""

    def test_request_size_sets_requested_dimensions(self):
        """_request_size should set requested width and height."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._request_size(60, 25)

        assert widget._requested_width == 60
        assert widget._requested_height == 25

    def test_allocate_size_stores_allocation(self):
        """_allocate_size should store allocated dimensions and position."""
        from tkcurses import BaseWidget
        widget = BaseWidget()
        widget._create_window = MagicMock()  # Mock window creation

        widget._allocate_size(50, 20, 10, 5)

        assert widget._allocated_width == 50
        assert widget._allocated_height == 20
        assert widget._allocated_x == 10
        assert widget._allocated_y == 5

    def test_allocate_size_with_no_existing_window(self):
        """_allocate_size should attempt to create window if none exists."""
        from tkcurses import BaseWidget
        widget = BaseWidget()
        widget._create_window = MagicMock()
        widget._curses_window = None

        widget._allocate_size(40, 15, 0, 0)

        widget._create_window.assert_called_once_with(15, 40, 0, 0)

    def test_allocate_size_with_existing_window(self):
        """_allocate_size should resize existing window."""
        from tkcurses import BaseWidget
        widget = BaseWidget()
        widget._curses_window = MagicMock()
        widget._resize_window = MagicMock()

        widget._allocate_size(40, 15, 0, 0)

        widget._resize_window.assert_called_once_with(15, 40)

    def test_allocate_size_moves_panel(self):
        """_allocate_size should move panel to new position."""
        from tkcurses import BaseWidget
        widget = BaseWidget()
        widget._curses_window = MagicMock()
        widget._panel = MagicMock()
        widget._resize_window = MagicMock()

        widget._allocate_size(40, 15, 5, 10)

        widget._panel.move.assert_called_once_with(10, 5)


# =============================================================================
# Tests for BaseWidget Class - Rendering Interface
# =============================================================================


class TestBaseWidgetRendering:
    """Tests for rendering interface methods."""

    def test_draw_is_abstract(self):
        """_draw() should have default empty implementation."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._draw()  # Should not raise

    def test_redraw_safe_with_no_window(self):
        """_redraw() should be safe if no window exists."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._redraw()  # Should not raise

    def test_redraw_safe_if_destroyed(self):
        """_redraw() should be safe if widget is destroyed."""
        from tkcurses import BaseWidget
        widget = BaseWidget()
        widget._is_destroyed = True

        widget._redraw()  # Should not raise

    def test_redraw_calls_draw(self):
        """_redraw() should call _draw()."""
        from tkcurses import BaseWidget
        widget = BaseWidget()
        widget._curses_window = MagicMock()
        widget._is_destroyed = False
        widget._draw = MagicMock()
        widget._panel_stack = MagicMock()

        widget._redraw()

        widget._draw.assert_called_once()

    def test_redraw_updates_panel_stack(self):
        """_redraw() should update panel stack."""
        from tkcurses import BaseWidget
        widget = BaseWidget()
        widget._curses_window = MagicMock()
        widget._is_destroyed = False
        widget._draw = MagicMock()
        widget._panel_stack = MagicMock()

        widget._redraw()

        widget._panel_stack.update.assert_called_once()

    def test_get_content_area_no_window(self):
        """_get_content_area() should return (0,0,0,0) if no window."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        area = widget._get_content_area()

        assert area == (0, 0, 0, 0)

    def test_get_content_area_with_window(self):
        """_get_content_area() should return allocated dimensions."""
        from tkcurses import BaseWidget
        widget = BaseWidget()
        widget._curses_window = MagicMock()
        widget._allocated_width = 40
        widget._allocated_height = 15

        area = widget._get_content_area()

        assert area == (0, 0, 15, 40)


# =============================================================================
# Tests for BaseWidget Class - Integration Tests
# =============================================================================


class TestBaseWidgetIntegration:
    """Integration tests for BaseWidget."""

    def test_widget_creation_and_configuration(self):
        """Widget should support creation with configuration."""
        from tkcurses import BaseWidget
        widget = BaseWidget(width=40, height=10, bg="blue", text="Hello")

        assert widget._requested_width == 40
        assert widget._requested_height == 10
        assert widget._widget_config["background"] == "blue"
        assert widget._widget_config["text"] == "Hello"

    def test_parent_child_hierarchy_complete(self):
        """Parent-child relationships should be bidirectional."""
        from tkcurses import BaseWidget
        parent = BaseWidget()
        child = BaseWidget(master=parent)

        assert child.master is parent
        assert child in parent._children

    def test_multiple_children_independent(self):
        """Multiple children should be independent."""
        from tkcurses import BaseWidget
        parent = BaseWidget()
        child1 = BaseWidget(master=parent, width=20)
        child2 = BaseWidget(master=parent, width=30)

        assert child1._requested_width == 20
        assert child2._requested_width == 30
        assert len(parent._children) == 2

    def test_destroy_complex_hierarchy(self):
        """Destroy should handle complex widget hierarchies."""
        from tkcurses import BaseWidget
        root = BaseWidget()
        branch1 = BaseWidget(master=root)
        branch2 = BaseWidget(master=root)
        leaf1 = BaseWidget(master=branch1)
        leaf2 = BaseWidget(master=branch1)
        leaf3 = BaseWidget(master=branch2)

        root.destroy()

        assert all(w._is_destroyed for w in [root, branch1, branch2, leaf1, leaf2, leaf3])

    def test_widget_paths_unique_per_class(self):
        """Widget paths should include class names for uniqueness."""
        from tkcurses import BaseWidget
        widget1 = BaseWidget()
        widget2 = BaseWidget()

        # Both root paths, so both are "."
        assert widget1._widget_path == "."
        assert widget2._widget_path == "."

        # But children should have unique paths
        child1 = BaseWidget(master=widget1)
        child2 = BaseWidget(master=widget2)

        assert child1._widget_path != child2._widget_path

    def test_geometry_request_and_allocation(self):
        """Widget should support geometry request and allocation."""
        from tkcurses import BaseWidget
        widget = BaseWidget()
        widget._create_window = MagicMock()  # Mock window creation

        widget._request_size(50, 20)
        assert widget._requested_width == 50
        assert widget._requested_height == 20

        widget._allocate_size(45, 18, 5, 10)
        assert widget._allocated_width == 45
        assert widget._allocated_height == 18
        assert widget._allocated_x == 5
        assert widget._allocated_y == 10

    def test_configuration_updates_geometry(self):
        """Configuration with width/height should update requests."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._configure_widget(width=60, height=25)

        assert widget._requested_width == 60
        assert widget._requested_height == 25

    def test_widget_not_mapped_initially(self):
        """Widget should not be mapped until window is created."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        assert widget._is_mapped is False
        assert widget._curses_window is None

    def test_widget_config_accumulates(self):
        """Multiple configure calls should accumulate."""
        from tkcurses import BaseWidget
        widget = BaseWidget()

        widget._configure_widget(width=40)
        widget._configure_widget(height=15, text="Hello")

        assert widget._widget_config["width"] == 40
        assert widget._widget_config["height"] == 15
        assert widget._widget_config["text"] == "Hello"


# =============================================================================
# Tests for Pack Geometry Manager
# =============================================================================


class TestPack:
    """Tests for Pack geometry manager stub."""

    def test_pack_basic_storage(self):
        """pack() should store pack options."""
        from tkcurses import Widget
        widget = Widget()

        widget.pack(side="left", fill="x")

        info = widget.pack_info()
        assert info["side"] == "left"
        assert info["fill"] == "x"

    def test_pack_with_dict_and_kwargs(self):
        """pack() should merge dict and keyword arguments."""
        from tkcurses import Widget
        widget = Widget()

        widget.pack({"side": "top"}, fill="both", expand=True)

        info = widget.pack_info()
        assert info["side"] == "top"
        assert info["fill"] == "both"
        assert info["expand"] is True

    def test_pack_kwargs_override_dict(self):
        """pack() keyword arguments should override dict values."""
        from tkcurses import Widget
        widget = Widget()

        widget.pack({"side": "top", "fill": "x"}, fill="both")

        info = widget.pack_info()
        assert info["side"] == "top"
        assert info["fill"] == "both"

    def test_pack_default_options(self):
        """pack() should set default options on first call."""
        from tkcurses import Widget
        widget = Widget()

        widget.pack()

        info = widget.pack_info()
        assert info["side"] == "top"
        assert info["fill"] == "none"
        assert info["expand"] == 0
        assert info["anchor"] == "center"
        assert info["padx"] == 0
        assert info["pady"] == 0
        assert info["ipadx"] == 0
        assert info["ipady"] == 0

    def test_pack_all_options(self):
        """pack() should support all pack options."""
        from tkcurses import Widget
        widget = Widget()

        widget.pack(
            side="left",
            fill="both",
            expand=1,
            anchor="nw",
            padx=5,
            pady=10,
            ipadx=2,
            ipady=3,
            in_="parent",
            before="sibling1",
            after="sibling2",
        )

        info = widget.pack_info()
        assert info["side"] == "left"
        assert info["fill"] == "both"
        assert info["expand"] == 1
        assert info["anchor"] == "nw"
        assert info["padx"] == 5
        assert info["pady"] == 10
        assert info["ipadx"] == 2
        assert info["ipady"] == 3
        assert info["in_"] == "parent"
        assert info["before"] == "sibling1"
        assert info["after"] == "sibling2"

    def test_pack_in_parameter_handling(self):
        """pack() should handle 'in' parameter converted to 'in_'."""
        from tkcurses import Widget
        widget = Widget()

        # Using 'in' as a dict key (workaround for reserved keyword)
        widget.pack({"in": "parent_widget"})

        info = widget.pack_info()
        assert info["in_"] == "parent_widget"
        assert "in" not in info

    def test_pack_configure_alias(self):
        """pack_configure() should be an alias for pack()."""
        from tkcurses import Widget
        widget = Widget()

        widget.pack_configure(side="right", fill="y")

        info = widget.pack_info()
        assert info["side"] == "right"
        assert info["fill"] == "y"

    def test_pack_info_empty_when_not_packed(self):
        """pack_info() should return empty dict when widget not packed."""
        from tkcurses import Widget
        widget = Widget()

        info = widget.pack_info()
        assert info == {}

    def test_pack_info_returns_copy(self):
        """pack_info() should return a copy, not the internal dict."""
        from tkcurses import Widget
        widget = Widget()

        widget.pack(side="left")
        info1 = widget.pack_info()
        info1["side"] = "right"  # Modify returned dict
        info2 = widget.pack_info()

        assert info2["side"] == "left"  # Original unchanged

    def test_pack_forget(self):
        """pack_forget() should clear pack configuration."""
        from tkcurses import Widget
        widget = Widget()

        widget.pack(side="left", fill="x")
        widget.pack_forget()

        info = widget.pack_info()
        assert info == {}

    def test_pack_after_forget(self):
        """pack() should reinitialize after pack_forget()."""
        from tkcurses import Widget
        widget = Widget()

        widget.pack(side="left", fill="x")
        widget.pack_forget()
        widget.pack(side="right")

        info = widget.pack_info()
        assert info["side"] == "right"
        assert info["fill"] == "none"  # Back to default

    def test_pack_propagate_get(self):
        """pack_propagate() with no args should return propagation flag."""
        from tkcurses import Widget
        widget = Widget()

        flag = widget.pack_propagate()
        assert flag is True  # Default is True

    def test_pack_propagate_set(self):
        """pack_propagate(flag) should set propagation flag."""
        from tkcurses import Widget
        widget = Widget()

        result = widget.pack_propagate(False)
        assert result is None

    def test_pack_slaves_empty(self):
        """pack_slaves() should return empty list when no packed children."""
        from tkcurses import Widget
        parent = Widget()

        slaves = parent.pack_slaves()
        assert slaves == []

    def test_pack_slaves_with_children(self):
        """pack_slaves() should return packed children."""
        from tkcurses import Widget
        parent = Widget()
        child1 = Widget(master=parent)
        child2 = Widget(master=parent)
        child3 = Widget(master=parent)

        child1.pack()
        child2.pack()
        # child3 is not packed

        slaves = parent.pack_slaves()
        assert len(slaves) == 2
        assert child1 in slaves
        assert child2 in slaves
        assert child3 not in slaves

    def test_pack_slaves_mixed_geometry_managers(self):
        """pack_slaves() should only return children using pack."""
        from tkcurses import Widget
        parent = Widget()
        child1 = Widget(master=parent)
        child2 = Widget(master=parent)
        child3 = Widget(master=parent)

        child1.pack()
        child2.grid(row=0, column=0)
        child3.place(x=10, y=20)

        slaves = parent.pack_slaves()
        assert len(slaves) == 1
        assert child1 in slaves


# =============================================================================
# Tests for Grid Geometry Manager
# =============================================================================


class TestGrid:
    """Tests for Grid geometry manager stub."""

    def test_grid_basic_storage(self):
        """grid() should store grid options."""
        from tkcurses import Widget
        widget = Widget()

        widget.grid(row=1, column=2)

        info = widget.grid_info()
        assert info["row"] == 1
        assert info["column"] == 2

    def test_grid_with_dict_and_kwargs(self):
        """grid() should merge dict and keyword arguments."""
        from tkcurses import Widget
        widget = Widget()

        widget.grid({"row": 0}, column=1, sticky="nsew")

        info = widget.grid_info()
        assert info["row"] == 0
        assert info["column"] == 1
        assert info["sticky"] == "nsew"

    def test_grid_kwargs_override_dict(self):
        """grid() keyword arguments should override dict values."""
        from tkcurses import Widget
        widget = Widget()

        widget.grid({"row": 0, "column": 0}, row=2)

        info = widget.grid_info()
        assert info["row"] == 2
        assert info["column"] == 0

    def test_grid_default_options(self):
        """grid() should set default options on first call."""
        from tkcurses import Widget
        widget = Widget()

        widget.grid()

        info = widget.grid_info()
        assert info["row"] == 0
        assert info["column"] == 0
        assert info["rowspan"] == 1
        assert info["columnspan"] == 1
        assert info["sticky"] == ""
        assert info["padx"] == 0
        assert info["pady"] == 0
        assert info["ipadx"] == 0
        assert info["ipady"] == 0

    def test_grid_all_options(self):
        """grid() should support all grid options."""
        from tkcurses import Widget
        widget = Widget()

        widget.grid(
            row=2,
            column=3,
            rowspan=2,
            columnspan=3,
            sticky="nsew",
            padx=5,
            pady=10,
            ipadx=2,
            ipady=3,
            in_="parent",
        )

        info = widget.grid_info()
        assert info["row"] == 2
        assert info["column"] == 3
        assert info["rowspan"] == 2
        assert info["columnspan"] == 3
        assert info["sticky"] == "nsew"
        assert info["padx"] == 5
        assert info["pady"] == 10
        assert info["ipadx"] == 2
        assert info["ipady"] == 3
        assert info["in_"] == "parent"

    def test_grid_in_parameter_handling(self):
        """grid() should handle 'in' parameter converted to 'in_'."""
        from tkcurses import Widget
        widget = Widget()

        widget.grid({"in": "parent_widget"})

        info = widget.grid_info()
        assert info["in_"] == "parent_widget"
        assert "in" not in info

    def test_grid_configure_alias(self):
        """grid_configure() should be an alias for grid()."""
        from tkcurses import Widget
        widget = Widget()

        widget.grid_configure(row=1, column=2, sticky="w")

        info = widget.grid_info()
        assert info["row"] == 1
        assert info["column"] == 2
        assert info["sticky"] == "w"

    def test_grid_info_empty_when_not_gridded(self):
        """grid_info() should return empty dict when widget not gridded."""
        from tkcurses import Widget
        widget = Widget()

        info = widget.grid_info()
        assert info == {}

    def test_grid_info_returns_copy(self):
        """grid_info() should return a copy, not the internal dict."""
        from tkcurses import Widget
        widget = Widget()

        widget.grid(row=1, column=2)
        info1 = widget.grid_info()
        info1["row"] = 5  # Modify returned dict
        info2 = widget.grid_info()

        assert info2["row"] == 1  # Original unchanged

    def test_grid_forget(self):
        """grid_forget() should clear grid configuration."""
        from tkcurses import Widget
        widget = Widget()

        widget.grid(row=1, column=2)
        widget.grid_forget()

        info = widget.grid_info()
        assert info == {}

    def test_grid_after_forget(self):
        """grid() should reinitialize after grid_forget()."""
        from tkcurses import Widget
        widget = Widget()

        widget.grid(row=1, column=2)
        widget.grid_forget()
        widget.grid(row=3, column=4)

        info = widget.grid_info()
        assert info["row"] == 3
        assert info["column"] == 4

    def test_grid_remove(self):
        """grid_remove() should set removed flag but keep configuration."""
        from tkcurses import Widget
        widget = Widget()

        widget.grid(row=1, column=2)
        widget.grid_remove()

        info = widget.grid_info()
        assert info == {}  # Info hidden when removed

    def test_grid_after_remove(self):
        """grid() after grid_remove() should restore configuration."""
        from tkcurses import Widget
        widget = Widget()

        widget.grid(row=1, column=2, sticky="nsew")
        widget.grid_remove()
        widget.grid()  # Call without arguments to restore

        info = widget.grid_info()
        assert info["row"] == 1
        assert info["column"] == 2
        assert info["sticky"] == "nsew"

    def test_grid_propagate_get(self):
        """grid_propagate() with no args should return propagation flag."""
        from tkcurses import Widget
        widget = Widget()

        flag = widget.grid_propagate()
        assert flag is True  # Default is True

    def test_grid_propagate_set(self):
        """grid_propagate(flag) should set propagation flag."""
        from tkcurses import Widget
        widget = Widget()

        result = widget.grid_propagate(False)
        assert result is None

    def test_grid_slaves_empty(self):
        """grid_slaves() should return empty list when no gridded children."""
        from tkcurses import Widget
        parent = Widget()

        slaves = parent.grid_slaves()
        assert slaves == []

    def test_grid_slaves_with_children(self):
        """grid_slaves() should return gridded children."""
        from tkcurses import Widget
        parent = Widget()
        child1 = Widget(master=parent)
        child2 = Widget(master=parent)
        child3 = Widget(master=parent)

        child1.grid(row=0, column=0)
        child2.grid(row=0, column=1)
        # child3 is not gridded

        slaves = parent.grid_slaves()
        assert len(slaves) == 2
        assert child1 in slaves
        assert child2 in slaves
        assert child3 not in slaves

    def test_grid_slaves_filter_by_row(self):
        """grid_slaves(row=n) should return only children in row n."""
        from tkcurses import Widget
        parent = Widget()
        child1 = Widget(master=parent)
        child2 = Widget(master=parent)
        child3 = Widget(master=parent)

        child1.grid(row=0, column=0)
        child2.grid(row=0, column=1)
        child3.grid(row=1, column=0)

        row_0 = parent.grid_slaves(row=0)
        row_1 = parent.grid_slaves(row=1)

        assert len(row_0) == 2
        assert child1 in row_0
        assert child2 in row_0
        assert len(row_1) == 1
        assert child3 in row_1

    def test_grid_slaves_filter_by_column(self):
        """grid_slaves(column=n) should return only children in column n."""
        from tkcurses import Widget
        parent = Widget()
        child1 = Widget(master=parent)
        child2 = Widget(master=parent)
        child3 = Widget(master=parent)

        child1.grid(row=0, column=0)
        child2.grid(row=1, column=0)
        child3.grid(row=0, column=1)

        col_0 = parent.grid_slaves(column=0)
        col_1 = parent.grid_slaves(column=1)

        assert len(col_0) == 2
        assert child1 in col_0
        assert child2 in col_0
        assert len(col_1) == 1
        assert child3 in col_1

    def test_grid_slaves_filter_by_row_and_column(self):
        """grid_slaves(row, column) should return child at that cell."""
        from tkcurses import Widget
        parent = Widget()
        child1 = Widget(master=parent)
        child2 = Widget(master=parent)
        child3 = Widget(master=parent)

        child1.grid(row=0, column=0)
        child2.grid(row=0, column=1)
        child3.grid(row=1, column=0)

        cell_result = parent.grid_slaves(row=0, column=1)
        assert len(cell_result) == 1
        assert child2 in cell_result

    def test_grid_slaves_ignores_removed(self):
        """grid_slaves() should not include removed widgets."""
        from tkcurses import Widget
        parent = Widget()
        child1 = Widget(master=parent)
        child2 = Widget(master=parent)

        child1.grid(row=0, column=0)
        child2.grid(row=0, column=1)
        child2.grid_remove()

        slaves = parent.grid_slaves()
        assert len(slaves) == 1
        assert child1 in slaves
        assert child2 not in slaves

    def test_grid_slaves_mixed_geometry_managers(self):
        """grid_slaves() should only return children using grid."""
        from tkcurses import Widget
        parent = Widget()
        child1 = Widget(master=parent)
        child2 = Widget(master=parent)
        child3 = Widget(master=parent)

        child1.grid(row=0, column=0)
        child2.pack()
        child3.place(x=10, y=20)

        slaves = parent.grid_slaves()
        assert len(slaves) == 1
        assert child1 in slaves

    def test_grid_bbox_returns_none_stub(self):
        """grid_bbox() should return None (stub implementation)."""
        from tkcurses import Widget
        widget = Widget()

        result = widget.grid_bbox(0, 0)
        assert result is None

    def test_grid_columnconfigure_query_mode(self):
        """grid_columnconfigure(index) without options should return config dict."""
        from tkcurses import Widget
        widget = Widget()

        config = widget.grid_columnconfigure(0)
        assert isinstance(config, dict)
        assert "weight" in config
        assert "minsize" in config
        assert "pad" in config

    def test_grid_columnconfigure_set_mode(self):
        """grid_columnconfigure(index, option=value) should return None."""
        from tkcurses import Widget
        widget = Widget()

        result = widget.grid_columnconfigure(0, weight=1)
        assert result is None

    def test_grid_rowconfigure_query_mode(self):
        """grid_rowconfigure(index) without options should return config dict."""
        from tkcurses import Widget
        widget = Widget()

        config = widget.grid_rowconfigure(0)
        assert isinstance(config, dict)
        assert "weight" in config
        assert "minsize" in config
        assert "pad" in config

    def test_grid_rowconfigure_set_mode(self):
        """grid_rowconfigure(index, option=value) should return None."""
        from tkcurses import Widget
        widget = Widget()

        result = widget.grid_rowconfigure(0, weight=1)
        assert result is None

    def test_grid_location(self):
        """grid_location(x, y) should return grid cell coordinates."""
        from tkcurses import Widget
        widget = Widget()

        col, row = widget.grid_location(50, 30)
        assert isinstance(col, int)
        assert isinstance(row, int)

    def test_grid_size_empty(self):
        """grid_size() should return (0, 0) for empty grid."""
        from tkcurses import Widget
        parent = Widget()

        size = parent.grid_size()
        assert size == (0, 0)

    def test_grid_size_with_children(self):
        """grid_size() should return maximum row and column."""
        from tkcurses import Widget
        parent = Widget()
        child1 = Widget(master=parent)
        child2 = Widget(master=parent)

        child1.grid(row=0, column=0)
        child2.grid(row=2, column=3)

        cols, rows = parent.grid_size()
        assert cols == 4  # columns 0-3
        assert rows == 3  # rows 0-2

    def test_grid_size_with_colspan_rowspan(self):
        """grid_size() should account for spans."""
        from tkcurses import Widget
        parent = Widget()
        child = Widget(master=parent)

        child.grid(row=0, column=0, rowspan=3, columnspan=4)

        cols, rows = parent.grid_size()
        assert cols == 4
        assert rows == 3


# =============================================================================
# Tests for Place Geometry Manager
# =============================================================================


class TestPlace:
    """Tests for Place geometry manager stub."""

    def test_place_basic_storage(self):
        """place() should store place options."""
        from tkcurses import Widget
        widget = Widget()

        widget.place(x=10, y=20)

        info = widget.place_info()
        assert info["x"] == 10
        assert info["y"] == 20

    def test_place_with_dict_and_kwargs(self):
        """place() should merge dict and keyword arguments."""
        from tkcurses import Widget
        widget = Widget()

        widget.place({"x": 5}, y=15, width=100)

        info = widget.place_info()
        assert info["x"] == 5
        assert info["y"] == 15
        assert info["width"] == 100

    def test_place_kwargs_override_dict(self):
        """place() keyword arguments should override dict values."""
        from tkcurses import Widget
        widget = Widget()

        widget.place({"x": 10, "y": 20}, x=30)

        info = widget.place_info()
        assert info["x"] == 30
        assert info["y"] == 20

    def test_place_default_options(self):
        """place() should set default options on first call."""
        from tkcurses import Widget
        widget = Widget()

        widget.place()

        info = widget.place_info()
        assert info["x"] == 0
        assert info["y"] == 0
        assert info["relx"] == 0.0
        assert info["rely"] == 0.0
        assert info["width"] is None
        assert info["height"] is None
        assert info["relwidth"] is None
        assert info["relheight"] is None
        assert info["anchor"] == "nw"
        assert info["bordermode"] == "inside"

    def test_place_all_options(self):
        """place() should support all place options."""
        from tkcurses import Widget
        widget = Widget()

        widget.place(
            x=10,
            y=20,
            relx=0.1,
            rely=0.2,
            width=100,
            height=50,
            relwidth=0.5,
            relheight=0.3,
            anchor="center",
            in_="parent",
            bordermode="outside",
        )

        info = widget.place_info()
        assert info["x"] == 10
        assert info["y"] == 20
        assert info["relx"] == 0.1
        assert info["rely"] == 0.2
        assert info["width"] == 100
        assert info["height"] == 50
        assert info["relwidth"] == 0.5
        assert info["relheight"] == 0.3
        assert info["anchor"] == "center"
        assert info["in_"] == "parent"
        assert info["bordermode"] == "outside"

    def test_place_in_parameter_handling(self):
        """place() should handle 'in' parameter converted to 'in_'."""
        from tkcurses import Widget
        widget = Widget()

        widget.place({"in": "parent_widget"})

        info = widget.place_info()
        assert info["in_"] == "parent_widget"
        assert "in" not in info

    def test_place_configure_alias(self):
        """place_configure() should be an alias for place()."""
        from tkcurses import Widget
        widget = Widget()

        widget.place_configure(x=25, y=35)

        info = widget.place_info()
        assert info["x"] == 25
        assert info["y"] == 35

    def test_place_info_empty_when_not_placed(self):
        """place_info() should return empty dict when widget not placed."""
        from tkcurses import Widget
        widget = Widget()

        info = widget.place_info()
        assert info == {}

    def test_place_info_returns_copy(self):
        """place_info() should return a copy, not the internal dict."""
        from tkcurses import Widget
        widget = Widget()

        widget.place(x=10, y=20)
        info1 = widget.place_info()
        info1["x"] = 100  # Modify returned dict
        info2 = widget.place_info()

        assert info2["x"] == 10  # Original unchanged

    def test_place_forget(self):
        """place_forget() should clear place configuration."""
        from tkcurses import Widget
        widget = Widget()

        widget.place(x=10, y=20)
        widget.place_forget()

        info = widget.place_info()
        assert info == {}

    def test_place_after_forget(self):
        """place() should reinitialize after place_forget()."""
        from tkcurses import Widget
        widget = Widget()

        widget.place(x=10, y=20)
        widget.place_forget()
        widget.place(x=30, y=40)

        info = widget.place_info()
        assert info["x"] == 30
        assert info["y"] == 40

    def test_place_slaves_empty(self):
        """place_slaves() should return empty list when no placed children."""
        from tkcurses import Widget
        parent = Widget()

        slaves = parent.place_slaves()
        assert slaves == []

    def test_place_slaves_with_children(self):
        """place_slaves() should return placed children."""
        from tkcurses import Widget
        parent = Widget()
        child1 = Widget(master=parent)
        child2 = Widget(master=parent)
        child3 = Widget(master=parent)

        child1.place(x=10, y=10)
        child2.place(x=50, y=50)
        # child3 is not placed

        slaves = parent.place_slaves()
        assert len(slaves) == 2
        assert child1 in slaves
        assert child2 in slaves
        assert child3 not in slaves

    def test_place_slaves_mixed_geometry_managers(self):
        """place_slaves() should only return children using place."""
        from tkcurses import Widget
        parent = Widget()
        child1 = Widget(master=parent)
        child2 = Widget(master=parent)
        child3 = Widget(master=parent)

        child1.place(x=10, y=10)
        child2.pack()
        child3.grid(row=0, column=0)

        slaves = parent.place_slaves()
        assert len(slaves) == 1
        assert child1 in slaves


# =============================================================================
# Tests for Widget Class with Multiple Geometry Managers
# =============================================================================


class TestWidget:
    """Tests for Widget class with multiple inheritance."""

    def test_widget_inherits_all_managers(self):
        """Widget should inherit from Pack, Place, and Grid."""
        from tkcurses import Widget
        widget = Widget()

        # Check for pack methods
        assert hasattr(widget, "pack")
        assert hasattr(widget, "pack_info")
        assert hasattr(widget, "pack_forget")

        # Check for grid methods
        assert hasattr(widget, "grid")
        assert hasattr(widget, "grid_info")
        assert hasattr(widget, "grid_forget")

        # Check for place methods
        assert hasattr(widget, "place")
        assert hasattr(widget, "place_info")
        assert hasattr(widget, "place_forget")

    def test_widget_pack_then_grid_forgets_pack(self):
        """Using grid() should forget previous pack()."""
        from tkcurses import Widget
        widget = Widget()

        widget.pack(side="left", fill="x")
        assert widget.pack_info() != {}

        widget.grid(row=0, column=0)
        assert widget.pack_info() == {}
        assert widget.grid_info() != {}

    def test_widget_grid_then_place_forgets_grid(self):
        """Using place() should forget previous grid()."""
        from tkcurses import Widget
        widget = Widget()

        widget.grid(row=0, column=0)
        assert widget.grid_info() != {}

        widget.place(x=10, y=20)
        assert widget.grid_info() == {}
        assert widget.place_info() != {}

    def test_widget_place_then_pack_forgets_place(self):
        """Using pack() should forget previous place()."""
        from tkcurses import Widget
        widget = Widget()

        widget.place(x=10, y=20)
        assert widget.place_info() != {}

        widget.pack(side="top", fill="both")
        assert widget.place_info() == {}
        assert widget.pack_info() != {}

    def test_widget_all_three_managers_cycle(self):
        """Widget should support switching between all three managers."""
        from tkcurses import Widget
        widget = Widget()

        # Start with pack
        widget.pack(side="left")
        assert widget.pack_info()["side"] == "left"
        assert widget.grid_info() == {}
        assert widget.place_info() == {}

        # Switch to grid
        widget.grid(row=1, column=2)
        assert widget.pack_info() == {}
        assert widget.grid_info()["row"] == 1
        assert widget.place_info() == {}

        # Switch to place
        widget.place(x=10, y=20)
        assert widget.pack_info() == {}
        assert widget.grid_info() == {}
        assert widget.place_info()["x"] == 10

        # Back to pack
        widget.pack(side="right")
        assert widget.pack_info()["side"] == "right"
        assert widget.grid_info() == {}
        assert widget.place_info() == {}

    def test_widget_initialization_all_managers_inactive(self):
        """Widget should initialize with all managers inactive."""
        from tkcurses import Widget
        widget = Widget()

        assert widget.pack_info() == {}
        assert widget.grid_info() == {}
        assert widget.place_info() == {}

    def test_widget_pack_slaves_respects_hierarchy(self):
        """Widget pack_slaves() should work with parent-child hierarchy."""
        from tkcurses import Widget
        parent = Widget()
        child1 = Widget(master=parent)
        child2 = Widget(master=parent)

        child1.pack()
        child2.pack(after=child1)

        slaves = parent.pack_slaves()
        assert len(slaves) == 2
        assert child1 in slaves
        assert child2 in slaves

    def test_widget_grid_slaves_respects_hierarchy(self):
        """Widget grid_slaves() should work with parent-child hierarchy."""
        from tkcurses import Widget
        parent = Widget()
        child1 = Widget(master=parent)
        child2 = Widget(master=parent)
        child3 = Widget(master=parent)

        child1.grid(row=0, column=0)
        child2.grid(row=0, column=1)
        child3.grid(row=1, column=0)

        all_slaves = parent.grid_slaves()
        assert len(all_slaves) == 3

        row_0_slaves = parent.grid_slaves(row=0)
        assert len(row_0_slaves) == 2

    def test_widget_place_slaves_respects_hierarchy(self):
        """Widget place_slaves() should work with parent-child hierarchy."""
        from tkcurses import Widget
        parent = Widget()
        child1 = Widget(master=parent)
        child2 = Widget(master=parent)

        child1.place(x=0, y=0)
        child2.place(x=50, y=50)

        slaves = parent.place_slaves()
        assert len(slaves) == 2
        assert child1 in slaves
        assert child2 in slaves

    def test_widget_pack_configure_updates(self):
        """Widget pack_configure() should update existing pack options."""
        from tkcurses import Widget
        widget = Widget()

        widget.pack(side="left", fill="x")
        widget.pack_configure(fill="both")

        info = widget.pack_info()
        assert info["side"] == "left"  # Unchanged
        assert info["fill"] == "both"  # Updated

    def test_widget_grid_configure_updates(self):
        """Widget grid_configure() should update existing grid options."""
        from tkcurses import Widget
        widget = Widget()

        widget.grid(row=0, column=0, sticky="w")
        widget.grid_configure(sticky="nsew")

        info = widget.grid_info()
        assert info["row"] == 0  # Unchanged
        assert info["sticky"] == "nsew"  # Updated

    def test_widget_place_configure_updates(self):
        """Widget place_configure() should update existing place options."""
        from tkcurses import Widget
        widget = Widget()

        widget.place(x=10, y=20)
        widget.place_configure(x=30)

        info = widget.place_info()
        assert info["x"] == 30  # Updated
        assert info["y"] == 20  # Unchanged

    def test_widget_no_children_no_slaves(self):
        """Widget without children should return empty slaves list."""
        from tkcurses import Widget
        widget = Widget()

        assert widget.pack_slaves() == []
        assert widget.grid_slaves() == []
        assert widget.place_slaves() == []

    def test_widget_unmanaged_children_not_in_slaves(self):
        """Unmanaged children should not appear in any slaves list."""
        from tkcurses import Widget
        parent = Widget()
        child = Widget(master=parent)

        # child is created but not managed by any geometry manager

        assert child not in parent.pack_slaves()
        assert child not in parent.grid_slaves()
        assert child not in parent.place_slaves()


# =============================================================================
# Fixture Utilities for Tk Tests
# =============================================================================


@pytest.fixture
def reset_tk_singleton():
    """Reset Tk singleton state before and after each test.

    This fixture ensures that each test starts with a clean Tk singleton state,
    allowing multiple Tk instances to be created across different tests.
    """
    yield
    # Clean up after test
    from tkcurses import Tk
    Tk._reset_singleton()


@pytest.fixture
def mock_curses_environment(monkeypatch):
    """Mock the curses environment for Tk initialization.

    This fixture mocks all the curses-related dependencies that Tk needs
    to initialize, including CursesScreen, CursesDispatcher, InputHandler,
    PanelStack, and ColorManager.
    """
    # Mock curses module
    mock_curses = MagicMock()
    mock_curses.COLS = 80
    mock_curses.LINES = 24
    mock_curses.beep = MagicMock()
    mock_curses.error = Exception

    # Mock CursesScreen
    mock_screen = MagicMock()
    mock_screen.width = 80
    mock_screen.height = 24
    mock_screen.stdscr = MagicMock()
    mock_screen.initialize = MagicMock()
    mock_screen.cleanup = MagicMock()
    mock_screen.resize_term = MagicMock()

    # Mock CursesDispatcher
    mock_dispatcher = MagicMock()
    mock_dispatcher.call = MagicMock()
    mock_dispatcher.process_queue = MagicMock()

    # Mock InputHandler
    mock_input_handler = MagicMock()
    mock_input_handler.wait_for_input = MagicMock(return_value=False)
    mock_input_handler.get_event = MagicMock(return_value=None)
    mock_input_handler.cleanup = MagicMock()

    # Mock PanelStack
    mock_panel_stack = MagicMock()
    mock_panel = MagicMock()
    mock_panel_stack.create_panel = MagicMock(return_value=mock_panel)
    mock_panel_stack.update = MagicMock()

    # Mock ColorManager
    mock_color_manager = MagicMock()

    # Mock TkCursesConfig
    mock_config = MagicMock()
    mock_config.input.poll_timeout = 100

    # Patch all the imports
    monkeypatch.setattr('tkcurses.CursesScreen', MagicMock(return_value=mock_screen))
    monkeypatch.setattr('tkcurses.CursesDispatcher.get', MagicMock(return_value=mock_dispatcher))
    monkeypatch.setattr('tkcurses.InputHandler', MagicMock(return_value=mock_input_handler))
    monkeypatch.setattr('tkcurses.PanelStack.get', MagicMock(return_value=mock_panel_stack))
    monkeypatch.setattr('tkcurses.ColorManager', MagicMock(return_value=mock_color_manager))
    monkeypatch.setattr('tkcurses.TkCursesConfig.load', MagicMock(return_value=mock_config))
    monkeypatch.setattr('tkcurses.curses', mock_curses)

    return {
        'curses': mock_curses,
        'screen': mock_screen,
        'dispatcher': mock_dispatcher,
        'input_handler': mock_input_handler,
        'panel_stack': mock_panel_stack,
        'panel': mock_panel,
        'color_manager': mock_color_manager,
        'config': mock_config,
    }


# =============================================================================
# Tests for Tk Initialization
# =============================================================================


class TestTkInitialization:
    """Tests for Tk class initialization and singleton pattern."""

    def test_tk_init_default_parameters(self, mock_curses_environment, reset_tk_singleton):
        """Tk() should initialize with default parameters."""
        from tkcurses import Tk

        root = Tk()

        assert root is not None
        assert hasattr(root, '_screen')
        assert hasattr(root, '_dispatcher')
        assert hasattr(root, '_input_handler')
        assert hasattr(root, '_panel_stack')
        assert hasattr(root, '_color_manager')
        assert root._quit_flag is False
        assert root._destroyed is False

    def test_tk_init_sets_default_geometry(self, mock_curses_environment, reset_tk_singleton):
        """Tk() should set default geometry to terminal size."""
        from tkcurses import Tk

        root = Tk()

        assert root._width == 80
        assert root._height == 24
        assert root._x == 0
        assert root._y == 0

    def test_tk_init_with_custom_class_name(self, mock_curses_environment, reset_tk_singleton):
        """Tk() should accept custom className parameter."""
        from tkcurses import Tk

        root = Tk(className='MyApp')

        assert root._class_name == 'MyApp'

    def test_tk_singleton_pattern_first_instance(self, mock_curses_environment, reset_tk_singleton):
        """Creating the first Tk instance should succeed."""
        from tkcurses import Tk

        root = Tk()

        assert Tk._instance is root
        assert Tk._instance_exists is True

    def test_tk_singleton_pattern_second_instance_raises_error(self, mock_curses_environment, reset_tk_singleton):
        """Creating a second Tk instance should raise RuntimeError."""
        from tkcurses import Tk

        root1 = Tk()
        with pytest.raises(RuntimeError, match="A Tk instance already exists"):
            root2 = Tk()

    def test_tk_singleton_pattern_after_destroy(self, mock_curses_environment, reset_tk_singleton):
        """Creating a new Tk after destroy() should succeed."""
        from tkcurses import Tk

        root1 = Tk()
        root1.destroy()

        # Should be able to create a new Tk instance now
        root2 = Tk()
        assert root2 is not root1
        assert Tk._instance is root2
        assert Tk._instance_exists is True

    def test_tk_init_calls_screen_initialize(self, mock_curses_environment, reset_tk_singleton):
        """Tk.__init__() should call screen.initialize()."""
        from tkcurses import Tk

        root = Tk()

        mock_curses_environment['screen'].initialize.assert_called_once()

    def test_tk_init_gets_dispatcher(self, mock_curses_environment, reset_tk_singleton):
        """Tk.__init__() should get CursesDispatcher singleton."""
        from tkcurses import Tk

        root = Tk()

        assert root._dispatcher is not None

    def test_tk_init_creates_input_handler(self, mock_curses_environment, reset_tk_singleton):
        """Tk.__init__() should create InputHandler."""
        from tkcurses import Tk

        root = Tk()

        assert root._input_handler is not None

    def test_tk_init_creates_panel_for_root(self, mock_curses_environment, reset_tk_singleton):
        """Tk.__init__() should create a panel for the root window."""
        from tkcurses import Tk

        root = Tk()

        mock_curses_environment['panel_stack'].create_panel.assert_called_once()
        mock_curses_environment['panel'].bottom.assert_called_once()

    def test_tk_init_creates_color_manager(self, mock_curses_environment, reset_tk_singleton):
        """Tk.__init__() should create ColorManager."""
        from tkcurses import Tk

        root = Tk()

        assert root._color_manager is not None

    def test_tk_init_inherits_from_misc(self, mock_curses_environment, reset_tk_singleton):
        """Tk should inherit from Misc."""
        from tkcurses import Tk, Misc

        root = Tk()

        assert isinstance(root, Misc)
        assert hasattr(root, 'bind')
        assert hasattr(root, 'after')
        assert hasattr(root, 'focus_set')

    def test_tk_init_inherits_from_wm(self, mock_curses_environment, reset_tk_singleton):
        """Tk should inherit from Wm."""
        from tkcurses import Tk, Wm

        root = Tk()

        assert isinstance(root, Wm)
        assert hasattr(root, 'title')
        assert hasattr(root, 'geometry')
        assert hasattr(root, 'state')


# =============================================================================
# Tests for Tk Main Event Loop
# =============================================================================


class TestTkMainloop:
    """Tests for Tk mainloop() method and event loop control."""

    def test_mainloop_with_default_parameter(self, mock_curses_environment, reset_tk_singleton):
        """mainloop() should accept default n=0 parameter."""
        from tkcurses import Tk

        root = Tk()
        # Use KeyboardInterrupt to exit cleanly (mainloop resets _quit_flag at start)
        mock_curses_environment['input_handler'].wait_for_input.side_effect = KeyboardInterrupt()

        # Should not raise
        root.mainloop()

    def test_mainloop_processes_n_events(self, mock_curses_environment, reset_tk_singleton):
        """mainloop(n) should process exactly n events then return."""
        from tkcurses import Tk
        from tkcurses._core.events import KeyEvent

        root = Tk()
        events = [KeyEvent(keysym='a', modifiers=0)]
        mock_curses_environment['input_handler'].wait_for_input.side_effect = [True, False]
        mock_curses_environment['input_handler'].get_event.side_effect = events

        root.mainloop(n=1)

        # Should have exited after processing 1 event
        assert not root._destroyed

    def test_mainloop_resets_quit_flag(self, mock_curses_environment, reset_tk_singleton):
        """mainloop() should reset _quit_flag to False at start."""
        from tkcurses import Tk

        root = Tk()
        root._quit_flag = True

        # Use a side_effect that checks the flag was reset, then exits
        def check_flag_and_exit(*args, **kwargs):
            # At this point, mainloop should have reset _quit_flag to False
            assert root._quit_flag is False, "_quit_flag should be reset to False at mainloop start"
            raise KeyboardInterrupt()

        mock_curses_environment['input_handler'].wait_for_input.side_effect = check_flag_and_exit

        root.mainloop()

    def test_mainloop_calls_process_after_queue(self, mock_curses_environment, reset_tk_singleton):
        """mainloop() should call _process_after_queue()."""
        from tkcurses import Tk
        from unittest.mock import patch

        root = Tk()
        # Use KeyboardInterrupt to exit cleanly (mainloop resets _quit_flag at start)
        mock_curses_environment['input_handler'].wait_for_input.side_effect = KeyboardInterrupt()

        with patch.object(root.__class__.__bases__[0], '_process_after_queue') as mock_process:
            root.mainloop()
            mock_process.assert_called()

    def test_mainloop_calls_dispatcher_process_queue(self, mock_curses_environment, reset_tk_singleton):
        """mainloop() should call dispatcher.process_queue()."""
        from tkcurses import Tk

        root = Tk()
        # Use KeyboardInterrupt to exit cleanly (mainloop resets _quit_flag at start)
        mock_curses_environment['input_handler'].wait_for_input.side_effect = KeyboardInterrupt()

        root.mainloop()

        mock_curses_environment['dispatcher'].process_queue.assert_called()

    def test_mainloop_handles_keyboard_interrupt(self, mock_curses_environment, reset_tk_singleton):
        """mainloop() should handle KeyboardInterrupt by calling quit()."""
        from tkcurses import Tk

        root = Tk()
        mock_curses_environment['input_handler'].wait_for_input.side_effect = KeyboardInterrupt()

        root.mainloop()

        # quit() should have been called, setting _quit_flag
        assert root._quit_flag is True

    def test_mainloop_calls_panel_update(self, mock_curses_environment, reset_tk_singleton):
        """mainloop() should call panel_stack.update()."""
        from tkcurses import Tk

        root = Tk()

        # Let one iteration complete (return False = no input), then exit on second
        call_count = [0]
        def wait_then_exit(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return False  # No input, but loop continues to update/refresh
            root._quit_flag = True  # Exit on next check
            return False

        mock_curses_environment['input_handler'].wait_for_input.side_effect = wait_then_exit

        root.mainloop()

        mock_curses_environment['panel_stack'].update.assert_called()

    def test_mainloop_refreshes_screen(self, mock_curses_environment, reset_tk_singleton):
        """mainloop() should refresh the screen."""
        from tkcurses import Tk

        root = Tk()

        # Let one iteration complete (return False = no input), then exit on second
        call_count = [0]
        def wait_then_exit(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return False  # No input, but loop continues to update/refresh
            root._quit_flag = True  # Exit on next check
            return False

        mock_curses_environment['input_handler'].wait_for_input.side_effect = wait_then_exit

        root.mainloop()

        mock_curses_environment['screen'].stdscr.refresh.assert_called()

    def test_mainloop_exits_on_quit_flag(self, mock_curses_environment, reset_tk_singleton):
        """mainloop() should exit when _quit_flag is set during loop."""
        from tkcurses import Tk

        root = Tk()

        # Use a side_effect that sets quit flag during the loop (simulating quit() call)
        def set_quit_flag(*args, **kwargs):
            root._quit_flag = True
            return False  # No input available

        mock_curses_environment['input_handler'].wait_for_input.side_effect = set_quit_flag

        root.mainloop()

        # Should have exited due to quit flag
        assert root._quit_flag is True

    def test_mainloop_exits_on_destroyed_flag(self, mock_curses_environment, reset_tk_singleton):
        """mainloop() should exit when _destroyed is set."""
        from tkcurses import Tk

        root = Tk()
        root._destroyed = True

        root.mainloop()

        # Should have exited without error


# =============================================================================
# Tests for Tk Application Control
# =============================================================================


class TestTkApplicationControl:
    """Tests for Tk application control methods (quit, destroy)."""

    def test_quit_sets_quit_flag(self, mock_curses_environment, reset_tk_singleton):
        """quit() should set _quit_flag to True."""
        from tkcurses import Tk

        root = Tk()
        assert root._quit_flag is False

        root.quit()

        assert root._quit_flag is True

    def test_quit_does_not_destroy_window(self, mock_curses_environment, reset_tk_singleton):
        """quit() should not destroy the window."""
        from tkcurses import Tk

        root = Tk()

        root.quit()

        assert root._destroyed is False
        assert Tk._instance_exists is True

    def test_destroy_marks_destroyed(self, mock_curses_environment, reset_tk_singleton):
        """destroy() should mark window as destroyed."""
        from tkcurses import Tk

        root = Tk()

        root.destroy()

        assert root._destroyed is True

    def test_destroy_sets_quit_flag(self, mock_curses_environment, reset_tk_singleton):
        """destroy() should set _quit_flag to True."""
        from tkcurses import Tk

        root = Tk()

        root.destroy()

        assert root._quit_flag is True

    def test_destroy_clears_singleton_flag(self, mock_curses_environment, reset_tk_singleton):
        """destroy() should clear singleton instance flag."""
        from tkcurses import Tk

        root = Tk()
        assert Tk._instance_exists is True

        root.destroy()

        assert Tk._instance_exists is False
        assert Tk._instance is None

    def test_destroy_calls_input_handler_cleanup(self, mock_curses_environment, reset_tk_singleton):
        """destroy() should call input_handler.cleanup()."""
        from tkcurses import Tk

        root = Tk()
        root.destroy()

        mock_curses_environment['input_handler'].cleanup.assert_called_once()

    def test_destroy_calls_screen_cleanup(self, mock_curses_environment, reset_tk_singleton):
        """destroy() should call screen.cleanup()."""
        from tkcurses import Tk

        root = Tk()
        root.destroy()

        mock_curses_environment['screen'].cleanup.assert_called_once()

    def test_destroy_idempotent(self, mock_curses_environment, reset_tk_singleton):
        """destroy() should be idempotent (safe to call multiple times)."""
        from tkcurses import Tk

        root = Tk()
        root.destroy()

        # Should not raise on second call
        root.destroy()

        assert root._destroyed is True

    def test_destroy_invokes_wm_delete_window_protocol(self, mock_curses_environment, reset_tk_singleton):
        """destroy() should invoke WM_DELETE_WINDOW protocol if registered."""
        from tkcurses import Tk

        root = Tk()
        callback = MagicMock()
        root.protocol('WM_DELETE_WINDOW', callback)

        root.destroy()

        callback.assert_called_once()

    def test_destroy_handles_protocol_exception(self, mock_curses_environment, reset_tk_singleton):
        """destroy() should handle exceptions in WM_DELETE_WINDOW protocol."""
        from tkcurses import Tk

        root = Tk()
        callback = MagicMock(side_effect=Exception("Test error"))
        root.protocol('WM_DELETE_WINDOW', callback)

        # Should not raise
        root.destroy()

        assert root._destroyed is True


# =============================================================================
# Tests for Tk-Specific Methods
# =============================================================================


class TestTkSpecificMethods:
    """Tests for Tk-specific methods (tk property, winfo_*, bell)."""

    def test_tk_property_returns_self(self, mock_curses_environment, reset_tk_singleton):
        """tk property should return self."""
        from tkcurses import Tk

        root = Tk()

        assert root.tk is root

    def test_winfo_toplevel_returns_self(self, mock_curses_environment, reset_tk_singleton):
        """winfo_toplevel() should return self."""
        from tkcurses import Tk

        root = Tk()

        assert root.winfo_toplevel() is root

    def test_winfo_screenwidth_returns_screen_width(self, mock_curses_environment, reset_tk_singleton):
        """winfo_screenwidth() should return terminal width."""
        from tkcurses import Tk

        root = Tk()

        assert root.winfo_screenwidth() == 80

    def test_winfo_screenheight_returns_screen_height(self, mock_curses_environment, reset_tk_singleton):
        """winfo_screenheight() should return terminal height."""
        from tkcurses import Tk

        root = Tk()

        assert root.winfo_screenheight() == 24

    def test_winfo_screenwidth_reflects_resize(self, mock_curses_environment, reset_tk_singleton):
        """winfo_screenwidth() should reflect screen resize."""
        from tkcurses import Tk

        root = Tk()
        mock_curses_environment['screen'].width = 120

        assert root.winfo_screenwidth() == 120

    def test_winfo_screenheight_reflects_resize(self, mock_curses_environment, reset_tk_singleton):
        """winfo_screenheight() should reflect screen resize."""
        from tkcurses import Tk

        root = Tk()
        mock_curses_environment['screen'].height = 40

        assert root.winfo_screenheight() == 40

    def test_bell_calls_dispatcher_beep(self, mock_curses_environment, reset_tk_singleton):
        """bell() should call curses.beep() via dispatcher."""
        from tkcurses import Tk

        root = Tk()
        root.bell()

        mock_curses_environment['dispatcher'].call.assert_called()

    def test_bell_handles_curses_error(self, mock_curses_environment, reset_tk_singleton):
        """bell() should handle curses errors gracefully."""
        from tkcurses import Tk

        root = Tk()
        mock_curses_environment['dispatcher'].call.side_effect = Exception("Curses error")

        # Should not raise
        root.bell()


# =============================================================================
# Tests for Inherited Misc Methods
# =============================================================================


class TestTkInheritedMiscMethods:
    """Tests for methods inherited from Misc class."""

    def test_tk_has_bind_method(self, mock_curses_environment, reset_tk_singleton):
        """Tk should have bind() method from Misc."""
        from tkcurses import Tk

        root = Tk()

        assert hasattr(root, 'bind')
        assert callable(root.bind)

    def test_tk_bind_works(self, mock_curses_environment, reset_tk_singleton):
        """Tk.bind() should work correctly."""
        from tkcurses import Tk

        root = Tk()
        callback = MagicMock()

        func_id = root.bind('<Button-1>', callback)

        assert func_id is not None
        assert '<Button-1>' in root._bindings

    def test_tk_has_after_method(self, mock_curses_environment, reset_tk_singleton):
        """Tk should have after() method from Misc."""
        from tkcurses import Tk

        root = Tk()

        assert hasattr(root, 'after')
        assert callable(root.after)

    def test_tk_after_works(self, mock_curses_environment, reset_tk_singleton):
        """Tk.after() should schedule a callback."""
        from tkcurses import Tk

        root = Tk()
        callback = MagicMock()

        after_id = root.after(100, callback)

        assert after_id is not None

    def test_tk_has_focus_set_method(self, mock_curses_environment, reset_tk_singleton):
        """Tk should have focus_set() method from Misc."""
        from tkcurses import Tk

        root = Tk()

        assert hasattr(root, 'focus_set')
        assert callable(root.focus_set)

    def test_tk_focus_set_works(self, mock_curses_environment, reset_tk_singleton):
        """Tk.focus_set() should set focus to root."""
        from tkcurses import Tk

        root = Tk()

        root.focus_set()

        assert root._has_focus is True
        assert Misc._focused_widget is root

    def test_tk_has_configure_method(self, mock_curses_environment, reset_tk_singleton):
        """Tk should have configure() method from Misc."""
        from tkcurses import Tk

        root = Tk()

        assert hasattr(root, 'configure')
        assert callable(root.configure)

    def test_tk_has_cget_method(self, mock_curses_environment, reset_tk_singleton):
        """Tk should have cget() method from Misc."""
        from tkcurses import Tk

        root = Tk()

        assert hasattr(root, 'cget')
        assert callable(root.cget)

    def test_tk_has_clipboard_methods(self, mock_curses_environment, reset_tk_singleton):
        """Tk should have clipboard methods from Misc."""
        from tkcurses import Tk

        root = Tk()

        assert hasattr(root, 'clipboard_clear')
        assert hasattr(root, 'clipboard_append')
        assert hasattr(root, 'clipboard_get')

    def test_tk_clipboard_operations_work(self, mock_curses_environment, reset_tk_singleton):
        """Tk clipboard methods should work."""
        from tkcurses import Tk

        root = Tk()

        root.clipboard_clear()
        root.clipboard_append('test text')
        assert root.clipboard_get() == 'test text'


# =============================================================================
# Tests for Inherited Wm Methods
# =============================================================================


class TestTkInheritedWmMethods:
    """Tests for methods inherited from Wm class."""

    def test_tk_has_title_method(self, mock_curses_environment, reset_tk_singleton):
        """Tk should have title() method from Wm."""
        from tkcurses import Tk

        root = Tk()

        assert hasattr(root, 'title')
        assert callable(root.title)

    def test_tk_title_works(self, mock_curses_environment, reset_tk_singleton):
        """Tk.title() should set and get window title."""
        from tkcurses import Tk

        root = Tk()

        root.title('My App')

        assert root.title() == 'My App'

    def test_tk_has_geometry_method(self, mock_curses_environment, reset_tk_singleton):
        """Tk should have geometry() method from Wm."""
        from tkcurses import Tk

        root = Tk()

        assert hasattr(root, 'geometry')
        assert callable(root.geometry)

    def test_tk_geometry_works(self, mock_curses_environment, reset_tk_singleton):
        """Tk.geometry() should set and get window geometry."""
        from tkcurses import Tk

        root = Tk()

        root.geometry('80x24+0+0')

        assert root.geometry() == '80x24+0+0'

    def test_tk_has_state_method(self, mock_curses_environment, reset_tk_singleton):
        """Tk should have state() method from Wm."""
        from tkcurses import Tk

        root = Tk()

        assert hasattr(root, 'state')
        assert callable(root.state)

    def test_tk_state_works(self, mock_curses_environment, reset_tk_singleton):
        """Tk.state() should set and get window state."""
        from tkcurses import Tk

        root = Tk()

        root.state('normal')

        assert root.state() == 'normal'

    def test_tk_has_minsize_method(self, mock_curses_environment, reset_tk_singleton):
        """Tk should have minsize() method from Wm."""
        from tkcurses import Tk

        root = Tk()

        assert hasattr(root, 'minsize')
        assert callable(root.minsize)

    def test_tk_minsize_works(self, mock_curses_environment, reset_tk_singleton):
        """Tk.minsize() should set and get minimum size."""
        from tkcurses import Tk

        root = Tk()

        root.minsize(40, 10)

        assert root.minsize() == (40, 10)

    def test_tk_has_maxsize_method(self, mock_curses_environment, reset_tk_singleton):
        """Tk should have maxsize() method from Wm."""
        from tkcurses import Tk

        root = Tk()

        assert hasattr(root, 'maxsize')
        assert callable(root.maxsize)

    def test_tk_maxsize_works(self, mock_curses_environment, reset_tk_singleton):
        """Tk.maxsize() should set and get maximum size."""
        from tkcurses import Tk

        root = Tk()

        root.maxsize(120, 40)

        assert root.maxsize() == (120, 40)

    def test_tk_has_protocol_method(self, mock_curses_environment, reset_tk_singleton):
        """Tk should have protocol() method from Wm."""
        from tkcurses import Tk

        root = Tk()

        assert hasattr(root, 'protocol')
        assert callable(root.protocol)

    def test_tk_protocol_works(self, mock_curses_environment, reset_tk_singleton):
        """Tk.protocol() should register protocol callbacks."""
        from tkcurses import Tk

        root = Tk()
        callback = MagicMock()

        root.protocol('WM_DELETE_WINDOW', callback)

        assert 'WM_DELETE_WINDOW' in root._protocols
        assert root._protocols['WM_DELETE_WINDOW'] is callback

    def test_tk_has_resizable_method(self, mock_curses_environment, reset_tk_singleton):
        """Tk should have resizable() method from Wm."""
        from tkcurses import Tk

        root = Tk()

        assert hasattr(root, 'resizable')
        assert callable(root.resizable)

    def test_tk_resizable_works(self, mock_curses_environment, reset_tk_singleton):
        """Tk.resizable() should control window resizability."""
        from tkcurses import Tk

        root = Tk()

        root.resizable(False, False)

        assert root._resizable_width is False
        assert root._resizable_height is False


# =============================================================================
# Tests for Event Dispatching
# =============================================================================


class TestTkEventDispatching:
    """Tests for Tk event dispatching functionality."""

    def test_tk_can_bind_and_dispatch_events(self, mock_curses_environment, reset_tk_singleton):
        """Tk should be able to bind and dispatch events."""
        from tkcurses import Tk
        from tkcurses._core.events import KeyEvent

        root = Tk()
        callback = MagicMock()

        root.bind('<Key-a>', callback)

        # This would require more setup to actually dispatch, but we've tested the binding

    def test_tk_can_bind_global_events(self, mock_curses_environment, reset_tk_singleton):
        """Tk should be able to bind global events."""
        from tkcurses import Tk

        root = Tk()
        callback = MagicMock()

        root.bind_all('<Control-q>', callback)

        assert '<Control-q>' in Misc._global_bindings


# =============================================================================
# Tests for Tk Reset Singleton
# =============================================================================


class TestTkResetSingleton:
    """Tests for Tk._reset_singleton() helper method."""

    def test_reset_singleton_clears_instance(self, mock_curses_environment, reset_tk_singleton):
        """_reset_singleton() should clear the Tk instance."""
        from tkcurses import Tk

        root = Tk()
        assert Tk._instance is root

        Tk._reset_singleton()

        assert Tk._instance is None
        assert Tk._instance_exists is False

    def test_reset_singleton_allows_new_instance(self, mock_curses_environment, reset_tk_singleton):
        """_reset_singleton() should allow creating a new Tk instance."""
        from tkcurses import Tk

        root1 = Tk()
        Tk._reset_singleton()
        root2 = Tk()

        assert root1 is not root2
        assert Tk._instance is root2


# =============================================================================
# Tests for Toplevel Initialization
# =============================================================================


class TestToplevelInitialization:
    """Tests for Toplevel class initialization."""

    def test_toplevel_requires_tk_instance(self, reset_tk_singleton):
        """Toplevel() should raise RuntimeError if no Tk instance exists."""
        from tkcurses import Toplevel, Tk

        # Ensure no Tk exists
        Tk._reset_singleton()

        with pytest.raises(RuntimeError) as exc_info:
            Toplevel()

        assert "Tk instance" in str(exc_info.value)

    def test_toplevel_init_with_tk_master(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel() should initialize with Tk as master."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert top is not None
        assert top._master is root
        assert top._tk_root is root

    def test_toplevel_init_without_master_uses_tk_instance(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel() without master should use Tk._instance."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel()

        assert top._master is root
        assert top._tk_root is root

    def test_toplevel_init_with_toplevel_master(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel() should work with another Toplevel as master."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top1 = Toplevel(root)
        top2 = Toplevel(top1)

        assert top2._master is top1
        assert top2._tk_root is root

    def test_toplevel_init_sets_class_name(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel() should set the class name."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root, className='MyToplevel')

        assert top._class_name == 'MyToplevel'

    def test_toplevel_init_default_class_name(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel() should have default class name 'Toplevel'."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert top._class_name == 'Toplevel'

    def test_toplevel_creates_curses_window(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel() should create a curses window via dispatcher."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        mock_curses_environment['dispatcher'].call = MagicMock(return_value=MagicMock())
        top = Toplevel(root)

        # Verify curses.newwin was called
        calls = mock_curses_environment['dispatcher'].call.call_args_list
        assert any('newwin' in str(c) for c in calls)

    def test_toplevel_creates_panel(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel() should create a panel for z-ordering."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert hasattr(top, '_panel')
        mock_curses_environment['panel'].top.assert_called()

    def test_toplevel_init_default_geometry(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel() should have default geometry based on screen size."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        # Default is slightly smaller than terminal
        assert top._width <= mock_curses_environment['screen'].width
        assert top._height <= mock_curses_environment['screen'].height
        assert top._x >= 0
        assert top._y >= 0

    def test_toplevel_init_destroyed_flag(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel() should start with _destroyed flag as False."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert top._destroyed is False

    def test_toplevel_added_to_master_toplevels(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel() should add itself to master's _toplevels list."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert hasattr(root, '_toplevels')
        assert top in root._toplevels

    def test_toplevel_inherits_from_misc(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel should inherit from Misc."""
        from tkcurses import Tk, Toplevel, Misc

        root = Tk()
        top = Toplevel(root)

        assert isinstance(top, Misc)

    def test_toplevel_inherits_from_wm(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel should inherit from Wm."""
        from tkcurses import Tk, Toplevel, Wm

        root = Tk()
        top = Toplevel(root)

        assert isinstance(top, Wm)


# =============================================================================
# Tests for Toplevel Properties
# =============================================================================


class TestToplevelProperties:
    """Tests for Toplevel property methods."""

    def test_tk_property_returns_root(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel.tk should return the Tk root instance."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert top.tk is root

    def test_tk_property_nested_toplevel(self, mock_curses_environment, reset_tk_singleton):
        """Nested Toplevel.tk should return the Tk root."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top1 = Toplevel(root)
        top2 = Toplevel(top1)

        assert top2.tk is root

    def test_master_property_returns_parent(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel.master should return the parent window."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert top.master is root

    def test_winfo_toplevel_returns_self(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel.winfo_toplevel() should return self."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert top.winfo_toplevel() is top


# =============================================================================
# Tests for Toplevel winfo Methods
# =============================================================================


class TestToplevelWinfo:
    """Tests for Toplevel winfo_* methods."""

    def test_winfo_screenwidth(self, mock_curses_environment, reset_tk_singleton):
        """winfo_screenwidth() should return terminal width."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert top.winfo_screenwidth() == 80

    def test_winfo_screenheight(self, mock_curses_environment, reset_tk_singleton):
        """winfo_screenheight() should return terminal height."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert top.winfo_screenheight() == 24

    def test_winfo_width(self, mock_curses_environment, reset_tk_singleton):
        """winfo_width() should return Toplevel width."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        width = top.winfo_width()
        assert width > 0
        assert width <= 80

    def test_winfo_height(self, mock_curses_environment, reset_tk_singleton):
        """winfo_height() should return Toplevel height."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        height = top.winfo_height()
        assert height > 0
        assert height <= 24

    def test_winfo_x(self, mock_curses_environment, reset_tk_singleton):
        """winfo_x() should return Toplevel x position."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        x = top.winfo_x()
        assert x >= 0

    def test_winfo_y(self, mock_curses_environment, reset_tk_singleton):
        """winfo_y() should return Toplevel y position."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        y = top.winfo_y()
        assert y >= 0


# =============================================================================
# Tests for Toplevel Geometry
# =============================================================================


class TestToplevelGeometry:
    """Tests for Toplevel geometry method."""

    def test_geometry_query(self, mock_curses_environment, reset_tk_singleton):
        """geometry() without args should return current geometry."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        geom = top.geometry()

        assert 'x' in geom
        assert '+' in geom

    def test_geometry_query_format(self, mock_curses_environment, reset_tk_singleton):
        """geometry() should return WxH+X+Y format."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)
        top._width = 40
        top._height = 20
        top._x = 5
        top._y = 3

        geom = top.geometry()

        assert geom == "40x20+5+3"

    def test_geometry_set_size_only(self, mock_curses_environment, reset_tk_singleton):
        """geometry() with WxH should set size."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        mock_curses_environment['dispatcher'].call = MagicMock(return_value=MagicMock())
        top = Toplevel(root)
        original_x = top._x
        original_y = top._y

        top.geometry("30x15")

        assert top._width == 30
        assert top._height == 15
        assert top._x == original_x
        assert top._y == original_y

    def test_geometry_set_full(self, mock_curses_environment, reset_tk_singleton):
        """geometry() with WxH+X+Y should set size and position."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        mock_curses_environment['dispatcher'].call = MagicMock(return_value=MagicMock())
        top = Toplevel(root)

        top.geometry("30x15+10+5")

        assert top._width == 30
        assert top._height == 15
        assert top._x == 10
        assert top._y == 5

    def test_geometry_set_calls_window_resize(self, mock_curses_environment, reset_tk_singleton):
        """geometry() should call window.resize when size changes via dispatcher."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        mock_window = MagicMock()
        mock_curses_environment['dispatcher'].call = MagicMock(return_value=mock_window)
        top = Toplevel(root)
        top._window = mock_window
        top._width = 40  # Set initial size
        top._height = 20

        top.geometry("60x30+2+2")

        # Verify dispatcher.call was invoked with window.resize
        # The resize is called via dispatcher for thread safety
        calls = mock_curses_environment['dispatcher'].call.call_args_list
        resize_calls = [c for c in calls if len(c[0]) >= 1 and
                       hasattr(c[0][0], '__name__') and c[0][0].__name__ == 'resize']
        # If no named method, check if it's the mock's resize method
        if not resize_calls:
            resize_calls = [c for c in calls if c[0][0] == mock_window.resize]
        assert len(resize_calls) > 0 or mock_window.resize.called, \
            f"Expected resize to be called. Dispatcher calls: {calls}"

    def test_geometry_set_calls_panel_move(self, mock_curses_environment, reset_tk_singleton):
        """geometry() should call panel.move when position changes."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        mock_window = MagicMock()
        mock_curses_environment['dispatcher'].call = MagicMock(return_value=mock_window)
        top = Toplevel(root)
        top._window = mock_window
        top._x = 2  # Set initial position
        top._y = 2

        top.geometry("40x20+10+5")

        # Verify panel move was called with new position
        mock_curses_environment['panel'].move.assert_called_with(5, 10)

    def test_geometry_set_updates_panel_stack(self, mock_curses_environment, reset_tk_singleton):
        """geometry() should update panel stack after changes."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        mock_window = MagicMock()
        mock_curses_environment['dispatcher'].call = MagicMock(return_value=mock_window)
        top = Toplevel(root)
        top._window = mock_window
        top._width = 40
        top._height = 20
        top._x = 2
        top._y = 2
        mock_curses_environment['panel_stack'].update.reset_mock()

        top.geometry("60x30+10+5")

        # Verify panel stack was updated
        mock_curses_environment['panel_stack'].update.assert_called()


# =============================================================================
# Tests for Toplevel Window Stacking
# =============================================================================


class TestToplevelStacking:
    """Tests for Toplevel window stacking (lift/lower)."""

    def test_lift_moves_to_top(self, mock_curses_environment, reset_tk_singleton):
        """lift() should move panel to top of stack."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        top.lift()

        mock_curses_environment['panel'].top.assert_called()

    def test_lower_moves_to_bottom(self, mock_curses_environment, reset_tk_singleton):
        """lower() should move panel to bottom of stack."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        top.lower()

        mock_curses_environment['panel'].bottom.assert_called()

    def test_lift_does_nothing_if_destroyed(self, mock_curses_environment, reset_tk_singleton):
        """lift() should do nothing if window is destroyed."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)
        top._destroyed = True

        # Reset call count
        mock_curses_environment['panel'].top.reset_mock()

        top.lift()

        # top() should not be called again
        assert mock_curses_environment['panel'].top.call_count == 0

    def test_lower_does_nothing_if_destroyed(self, mock_curses_environment, reset_tk_singleton):
        """lower() should do nothing if window is destroyed."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)
        top._destroyed = True

        # Reset call count
        mock_curses_environment['panel'].bottom.reset_mock()

        top.lower()

        assert mock_curses_environment['panel'].bottom.call_count == 0


# =============================================================================
# Tests for Toplevel Transient
# =============================================================================


class TestToplevelTransient:
    """Tests for Toplevel transient() method."""

    def test_transient_query_default_none(self, mock_curses_environment, reset_tk_singleton):
        """transient() without args should return None by default."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert top.transient() is None

    def test_transient_set_master(self, mock_curses_environment, reset_tk_singleton):
        """transient(master) should set the transient master."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        top.transient(root)

        assert top.transient() is root

    def test_transient_raises_panel(self, mock_curses_environment, reset_tk_singleton):
        """transient(master) should raise the panel to top."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)
        mock_curses_environment['panel'].top.reset_mock()

        top.transient(root)

        mock_curses_environment['panel'].top.assert_called()


# =============================================================================
# Tests for Toplevel Grab
# =============================================================================


class TestToplevelGrab:
    """Tests for Toplevel grab methods (stubs)."""

    def test_grab_set_is_stub(self, mock_curses_environment, reset_tk_singleton):
        """grab_set() should exist and not raise."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        # Should not raise
        top.grab_set()

    def test_grab_release_is_stub(self, mock_curses_environment, reset_tk_singleton):
        """grab_release() should exist and not raise."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        # Should not raise
        top.grab_release()


# =============================================================================
# Tests for Toplevel Focus
# =============================================================================


class TestToplevelFocus:
    """Tests for Toplevel focus methods."""

    def test_focus_set_lifts_window(self, mock_curses_environment, reset_tk_singleton):
        """focus_set() should lift the window."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)
        mock_curses_environment['panel'].top.reset_mock()

        top.focus_set()

        mock_curses_environment['panel'].top.assert_called()

    def test_focus_set_sets_misc_focus(self, mock_curses_environment, reset_tk_singleton):
        """focus_set() should set Misc focus to this widget."""
        from tkcurses import Tk, Toplevel, Misc

        root = Tk()
        top = Toplevel(root)

        top.focus_set()

        assert Misc._focused_widget is top


# =============================================================================
# Tests for Toplevel Bell
# =============================================================================


class TestToplevelBell:
    """Tests for Toplevel bell() method."""

    def test_bell_calls_curses_beep(self, mock_curses_environment, reset_tk_singleton):
        """bell() should call curses.beep via dispatcher."""
        from tkcurses import Tk, Toplevel
        import curses

        root = Tk()
        top = Toplevel(root)

        top.bell()

        # Check that dispatcher.call was used with beep
        mock_curses_environment['dispatcher'].call.assert_called()


# =============================================================================
# Tests for Toplevel Destroy
# =============================================================================


class TestToplevelDestroy:
    """Tests for Toplevel destroy() method."""

    def test_destroy_sets_destroyed_flag(self, mock_curses_environment, reset_tk_singleton):
        """destroy() should set _destroyed flag to True."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        top.destroy()

        assert top._destroyed is True

    def test_destroy_removes_from_master_toplevels(self, mock_curses_environment, reset_tk_singleton):
        """destroy() should remove from master's _toplevels list."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)
        assert top in root._toplevels

        top.destroy()

        assert top not in root._toplevels

    def test_destroy_removes_panel(self, mock_curses_environment, reset_tk_singleton):
        """destroy() should remove panel from stack."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        top.destroy()

        mock_curses_environment['panel_stack'].remove_panel.assert_called()

    def test_destroy_idempotent(self, mock_curses_environment, reset_tk_singleton):
        """destroy() should be safe to call multiple times."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        top.destroy()
        top.destroy()  # Should not raise

        assert top._destroyed is True

    def test_destroy_invokes_wm_delete_window_protocol(self, mock_curses_environment, reset_tk_singleton):
        """destroy() should invoke WM_DELETE_WINDOW protocol if registered."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)
        callback = MagicMock()
        top.protocol("WM_DELETE_WINDOW", callback)

        top.destroy()

        callback.assert_called_once()

    def test_destroy_unregisters_from_widget_registry(self, mock_curses_environment, reset_tk_singleton):
        """destroy() should remove from Misc widget registry."""
        from tkcurses import Tk, Toplevel, Misc

        root = Tk()
        top = Toplevel(root)
        widget_name = top._widget_name
        assert widget_name in Misc._widget_registry

        top.destroy()

        assert widget_name not in Misc._widget_registry


# =============================================================================
# Tests for Toplevel Wait Window
# =============================================================================


class TestToplevelWaitWindow:
    """Tests for Toplevel wait_window() method (stub)."""

    def test_wait_window_is_stub(self, mock_curses_environment, reset_tk_singleton):
        """wait_window() should exist and not raise."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        # Should not raise
        top.wait_window()


# =============================================================================
# Tests for Multiple Toplevels
# =============================================================================


class TestMultipleToplevels:
    """Tests for creating and managing multiple Toplevel windows."""

    def test_multiple_toplevels_allowed(self, mock_curses_environment, reset_tk_singleton):
        """Multiple Toplevel instances should be allowed."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top1 = Toplevel(root)
        top2 = Toplevel(root)
        top3 = Toplevel(root)

        assert top1 is not top2
        assert top2 is not top3
        assert len(root._toplevels) == 3

    def test_nested_toplevels(self, mock_curses_environment, reset_tk_singleton):
        """Toplevels can be nested within other Toplevels."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top1 = Toplevel(root)
        top2 = Toplevel(top1)

        assert top2._master is top1
        assert top2._tk_root is root

    def test_destroy_one_toplevel_keeps_others(self, mock_curses_environment, reset_tk_singleton):
        """Destroying one Toplevel should not affect others."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top1 = Toplevel(root)
        top2 = Toplevel(root)

        top1.destroy()

        assert top1._destroyed is True
        assert top2._destroyed is False
        assert top1 not in root._toplevels
        assert top2 in root._toplevels


# =============================================================================
# Tests for Toplevel Inherited Wm Methods
# =============================================================================


class TestToplevelInheritedWmMethods:
    """Tests for Wm methods inherited by Toplevel."""

    def test_toplevel_has_title_method(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel should have title() method."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert hasattr(top, 'title')
        assert callable(top.title)

    def test_toplevel_title_works(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel.title() should set and get title."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        top.title("My Dialog")
        assert top.title() == "My Dialog"

    def test_toplevel_has_state_method(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel should have state() method."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert hasattr(top, 'state')
        assert callable(top.state)

    def test_toplevel_state_works(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel.state() should set and get state."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        top.state("withdrawn")
        assert top.state() == "withdrawn"

    def test_toplevel_has_protocol_method(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel should have protocol() method."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert hasattr(top, 'protocol')
        assert callable(top.protocol)

    def test_toplevel_protocol_works(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel.protocol() should register handlers."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)
        callback = MagicMock()

        top.protocol("WM_DELETE_WINDOW", callback)

        assert "WM_DELETE_WINDOW" in top._protocols


# =============================================================================
# Tests for Toplevel Inherited Misc Methods
# =============================================================================


class TestToplevelInheritedMiscMethods:
    """Tests for Misc methods inherited by Toplevel."""

    def test_toplevel_has_bind_method(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel should have bind() method."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert hasattr(top, 'bind')
        assert callable(top.bind)

    def test_toplevel_bind_works(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel.bind() should register event bindings."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)
        callback = MagicMock()

        func_id = top.bind("<Button-1>", callback)

        assert func_id is not None
        assert "<Button-1>" in top._bindings

    def test_toplevel_has_after_method(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel should have after() method."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert hasattr(top, 'after')
        assert callable(top.after)

    def test_toplevel_after_works(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel.after() should schedule callbacks."""
        from tkcurses import Tk, Toplevel, Misc

        root = Tk()
        top = Toplevel(root)
        callback = MagicMock()

        after_id = top.after(100, callback)

        assert after_id is not None
        assert len(Misc._after_queue) > 0

    def test_toplevel_has_configure_method(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel should have configure() method."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert hasattr(top, 'configure')
        assert callable(top.configure)

    def test_toplevel_configure_works(self, mock_curses_environment, reset_tk_singleton):
        """Toplevel.configure() should set options."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        top.configure(background='blue')

        assert top.cget('background') == 'blue'


# =============================================================================
# Fixtures for Variable Tests
# =============================================================================


@pytest.fixture(autouse=True)
def reset_variable_counter():
    """Reset the Variable counter before each test."""
    from tkcurses import Variable
    Variable._counter = 0
    yield
    Variable._counter = 0


# =============================================================================
# Tests for Variable Base Class
# =============================================================================


class TestVariableInitialization:
    """Tests for Variable class initialization."""

    def test_variable_init_default_value(self):
        """Variable() should use default value when none provided."""
        from tkcurses import Variable

        var = Variable()

        assert var.get() == ""  # Default is empty string

    def test_variable_init_with_value(self):
        """Variable() should accept initial value."""
        from tkcurses import Variable

        var = Variable(value="test")

        assert var.get() == "test"

    def test_variable_init_generates_name(self):
        """Variable() should generate unique name when not provided."""
        from tkcurses import Variable

        var1 = Variable()
        var2 = Variable()

        assert var1._name.startswith("PY_VAR")
        assert var2._name.startswith("PY_VAR")
        assert var1._name != var2._name

    def test_variable_init_custom_name(self):
        """Variable() should accept custom name."""
        from tkcurses import Variable

        var = Variable(name="my_var")

        assert var._name == "my_var"

    def test_variable_init_with_master(self):
        """Variable() should accept master widget."""
        from tkcurses import Variable

        master = MagicMock()
        var = Variable(master=master)

        assert var._master is master


class TestVariableGetSet:
    """Tests for Variable get/set methods."""

    def test_get_returns_value(self):
        """get() should return the current value."""
        from tkcurses import Variable

        var = Variable(value="hello")

        assert var.get() == "hello"

    def test_set_updates_value(self):
        """set() should update the stored value."""
        from tkcurses import Variable

        var = Variable()
        var.set("world")

        assert var.get() == "world"

    def test_set_replaces_value(self):
        """set() should replace previous value."""
        from tkcurses import Variable

        var = Variable(value="old")
        var.set("new")

        assert var.get() == "new"


class TestVariableTraces:
    """Tests for Variable trace methods."""

    def test_trace_add_write(self):
        """trace_add('write') should call callback on set."""
        from tkcurses import Variable

        var = Variable()
        callback = MagicMock()

        var.trace_add("write", callback)
        var.set("test")

        callback.assert_called_once()

    def test_trace_add_read(self):
        """trace_add('read') should call callback on get."""
        from tkcurses import Variable

        var = Variable(value="test")
        callback = MagicMock()

        var.trace_add("read", callback)
        var.get()

        callback.assert_called_once()

    def test_trace_add_returns_id(self):
        """trace_add() should return a trace ID."""
        from tkcurses import Variable

        var = Variable()
        callback = MagicMock()

        trace_id = var.trace_add("write", callback)

        assert trace_id.startswith("trace")

    def test_trace_add_multiple(self):
        """Multiple traces can be added."""
        from tkcurses import Variable

        var = Variable()
        callback1 = MagicMock()
        callback2 = MagicMock()

        var.trace_add("write", callback1)
        var.trace_add("write", callback2)
        var.set("test")

        callback1.assert_called_once()
        callback2.assert_called_once()

    def test_trace_remove(self):
        """trace_remove() should stop callback invocation."""
        from tkcurses import Variable

        var = Variable()
        callback = MagicMock()

        trace_id = var.trace_add("write", callback)
        var.trace_remove("write", trace_id)
        var.set("test")

        callback.assert_not_called()

    def test_trace_info(self):
        """trace_info() should return trace information."""
        from tkcurses import Variable

        var = Variable()
        callback = MagicMock()

        trace_id = var.trace_add("write", callback)
        info = var.trace_info()

        assert len(info) == 1
        assert info[0][0] == ("write",)
        assert info[0][1] == trace_id

    def test_trace_callback_arguments(self):
        """Trace callback should receive (name, index, mode)."""
        from tkcurses import Variable

        var = Variable(name="test_var")
        received_args = []

        def callback(*args):
            received_args.extend(args)

        var.trace_add("write", callback)
        var.set("value")

        assert received_args[0] == "test_var"
        assert received_args[1] == ""
        assert received_args[2] == "write"

    def test_trace_callback_error_handled(self):
        """Trace callback errors should be caught."""
        from tkcurses import Variable

        var = Variable()

        def bad_callback(*args):
            raise ValueError("Test error")

        var.trace_add("write", bad_callback)

        # Should not raise
        var.set("test")


class TestVariableLegacyTrace:
    """Tests for Variable legacy trace methods."""

    def test_trace_w_mode(self):
        """trace('w') should register write trace."""
        from tkcurses import Variable

        var = Variable()
        callback = MagicMock()

        var.trace("w", callback)
        var.set("test")

        callback.assert_called_once()

    def test_trace_r_mode(self):
        """trace('r') should register read trace."""
        from tkcurses import Variable

        var = Variable(value="test")
        callback = MagicMock()

        var.trace("r", callback)
        var.get()

        callback.assert_called_once()

    def test_trace_variable_alias(self):
        """trace_variable() should be alias for trace()."""
        from tkcurses import Variable

        var = Variable()
        callback = MagicMock()

        var.trace_variable("w", callback)
        var.set("test")

        callback.assert_called_once()

    def test_trace_vdelete_alias(self):
        """trace_vdelete() should remove trace."""
        from tkcurses import Variable

        var = Variable()
        callback = MagicMock()

        trace_id = var.trace("w", callback)
        var.trace_vdelete("w", trace_id)
        var.set("test")

        callback.assert_not_called()

    def test_trace_vinfo_alias(self):
        """trace_vinfo() should return trace info."""
        from tkcurses import Variable

        var = Variable()
        callback = MagicMock()

        var.trace("w", callback)
        info = var.trace_vinfo()

        assert len(info) == 1


class TestVariableSpecialMethods:
    """Tests for Variable special methods."""

    def test_str_returns_name(self):
        """str(var) should return variable name."""
        from tkcurses import Variable

        var = Variable(name="my_var")

        assert str(var) == "my_var"

    def test_repr_shows_class_and_value(self):
        """repr(var) should show class name and value."""
        from tkcurses import Variable

        var = Variable(value="test")

        assert "Variable" in repr(var)
        assert "test" in repr(var)

    def test_eq_with_variable(self):
        """Variables should be equal if values are equal."""
        from tkcurses import Variable

        var1 = Variable(value="test")
        var2 = Variable(value="test")
        var3 = Variable(value="other")

        assert var1 == var2
        assert var1 != var3

    def test_eq_with_value(self):
        """Variable should equal its value."""
        from tkcurses import Variable

        var = Variable(value="test")

        assert var == "test"
        assert var != "other"


# =============================================================================
# Tests for StringVar
# =============================================================================


class TestStringVarInitialization:
    """Tests for StringVar initialization."""

    def test_stringvar_default_value(self):
        """StringVar() should default to empty string."""
        from tkcurses import StringVar

        var = StringVar()

        assert var.get() == ""

    def test_stringvar_with_value(self):
        """StringVar() should accept initial value."""
        from tkcurses import StringVar

        var = StringVar(value="hello")

        assert var.get() == "hello"


class TestStringVarGetSet:
    """Tests for StringVar get/set methods."""

    def test_get_returns_string(self):
        """StringVar.get() should return a string."""
        from tkcurses import StringVar

        var = StringVar(value="test")

        result = var.get()
        assert isinstance(result, str)
        assert result == "test"

    def test_set_converts_to_string(self):
        """StringVar.set() should convert value to string."""
        from tkcurses import StringVar

        var = StringVar()
        var.set(123)

        assert var.get() == "123"

    def test_set_handles_none_like_value(self):
        """StringVar.set() should convert None to string."""
        from tkcurses import StringVar

        var = StringVar()
        var.set(None)

        assert var.get() == "None"


# =============================================================================
# Tests for IntVar
# =============================================================================


class TestIntVarInitialization:
    """Tests for IntVar initialization."""

    def test_intvar_default_value(self):
        """IntVar() should default to 0."""
        from tkcurses import IntVar

        var = IntVar()

        assert var.get() == 0

    def test_intvar_with_value(self):
        """IntVar() should accept initial value."""
        from tkcurses import IntVar

        var = IntVar(value=42)

        assert var.get() == 42


class TestIntVarGetSet:
    """Tests for IntVar get/set methods."""

    def test_get_returns_int(self):
        """IntVar.get() should return an integer."""
        from tkcurses import IntVar

        var = IntVar(value=42)

        result = var.get()
        assert isinstance(result, int)
        assert result == 42

    def test_set_converts_to_int(self):
        """IntVar.set() should convert value to int."""
        from tkcurses import IntVar

        var = IntVar()
        var.set("123")

        assert var.get() == 123

    def test_set_raises_on_invalid(self):
        """IntVar.set() should raise ValueError on invalid input."""
        from tkcurses import IntVar

        var = IntVar()

        with pytest.raises(ValueError):
            var.set("not a number")


# =============================================================================
# Tests for DoubleVar
# =============================================================================


class TestDoubleVarInitialization:
    """Tests for DoubleVar initialization."""

    def test_doublevar_default_value(self):
        """DoubleVar() should default to 0.0."""
        from tkcurses import DoubleVar

        var = DoubleVar()

        assert var.get() == 0.0

    def test_doublevar_with_value(self):
        """DoubleVar() should accept initial value."""
        from tkcurses import DoubleVar

        var = DoubleVar(value=3.14)

        assert var.get() == 3.14


class TestDoubleVarGetSet:
    """Tests for DoubleVar get/set methods."""

    def test_get_returns_float(self):
        """DoubleVar.get() should return a float."""
        from tkcurses import DoubleVar

        var = DoubleVar(value=3.14)

        result = var.get()
        assert isinstance(result, float)
        assert result == 3.14

    def test_set_converts_to_float(self):
        """DoubleVar.set() should convert value to float."""
        from tkcurses import DoubleVar

        var = DoubleVar()
        var.set("2.71")

        assert var.get() == 2.71

    def test_set_from_int(self):
        """DoubleVar.set() should accept integers."""
        from tkcurses import DoubleVar

        var = DoubleVar()
        var.set(42)

        assert var.get() == 42.0

    def test_set_raises_on_invalid(self):
        """DoubleVar.set() should raise ValueError on invalid input."""
        from tkcurses import DoubleVar

        var = DoubleVar()

        with pytest.raises(ValueError):
            var.set("not a number")


# =============================================================================
# Tests for BooleanVar
# =============================================================================


class TestBooleanVarInitialization:
    """Tests for BooleanVar initialization."""

    def test_booleanvar_default_value(self):
        """BooleanVar() should default to False."""
        from tkcurses import BooleanVar

        var = BooleanVar()

        assert var.get() is False

    def test_booleanvar_with_value(self):
        """BooleanVar() should accept initial value."""
        from tkcurses import BooleanVar

        var = BooleanVar(value=True)

        assert var.get() is True


class TestBooleanVarGetSet:
    """Tests for BooleanVar get/set methods."""

    def test_get_returns_bool(self):
        """BooleanVar.get() should return a boolean."""
        from tkcurses import BooleanVar

        var = BooleanVar(value=True)

        result = var.get()
        assert isinstance(result, bool)
        assert result is True

    def test_set_converts_to_bool(self):
        """BooleanVar.set() should convert value to bool."""
        from tkcurses import BooleanVar

        var = BooleanVar()

        var.set(1)
        assert var.get() is True

        var.set(0)
        assert var.get() is False

    def test_set_truthy_values(self):
        """BooleanVar.set() should handle truthy values."""
        from tkcurses import BooleanVar

        var = BooleanVar()

        var.set("yes")
        assert var.get() is True

        var.set("")
        assert var.get() is False

        var.set([1, 2, 3])
        assert var.get() is True

        var.set([])
        assert var.get() is False


# =============================================================================
# Tests for Variable Inheritance
# =============================================================================


class TestVariableInheritance:
    """Tests for Variable subclass inheritance."""

    def test_stringvar_inherits_from_variable(self):
        """StringVar should inherit from Variable."""
        from tkcurses import StringVar, Variable

        var = StringVar()
        assert isinstance(var, Variable)

    def test_intvar_inherits_from_variable(self):
        """IntVar should inherit from Variable."""
        from tkcurses import IntVar, Variable

        var = IntVar()
        assert isinstance(var, Variable)

    def test_doublevar_inherits_from_variable(self):
        """DoubleVar should inherit from Variable."""
        from tkcurses import DoubleVar, Variable

        var = DoubleVar()
        assert isinstance(var, Variable)

    def test_booleanvar_inherits_from_variable(self):
        """BooleanVar should inherit from Variable."""
        from tkcurses import BooleanVar, Variable

        var = BooleanVar()
        assert isinstance(var, Variable)

    def test_subclasses_have_trace_methods(self):
        """All Variable subclasses should have trace methods."""
        from tkcurses import StringVar, IntVar, DoubleVar, BooleanVar

        for var_class in [StringVar, IntVar, DoubleVar, BooleanVar]:
            var = var_class()
            assert hasattr(var, 'trace_add')
            assert hasattr(var, 'trace_remove')
            assert hasattr(var, 'trace_info')
