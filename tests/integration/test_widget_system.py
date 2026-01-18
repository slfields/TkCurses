"""Integration tests for TkCurses widget system.

These tests verify that the widget classes work together correctly:
- Tk + Toplevel window management
- Tk + Variable interaction
- Variable traces with multiple widgets
- Event binding across windows
- Window lifecycle management
- Panel z-ordering integration
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch, call

import pytest


# =============================================================================
# Fixtures for Widget Integration Tests
# =============================================================================


@pytest.fixture
def reset_all_singletons():
    """Reset all singleton instances before and after tests."""
    from tkcurses import Tk, Misc, Variable
    from tkcurses._core.dispatcher import CursesDispatcher
    from tkcurses._core.panels import PanelStack

    # Reset before test
    Tk._reset_singleton()
    CursesDispatcher._instance = None
    PanelStack._instance = None
    Misc._global_bindings = {}
    Misc._class_bindings = {}
    Misc._clipboard = ""
    Misc._selection = ""
    Misc._focused_widget = None
    Misc._widget_registry = {}
    Misc._after_queue = []
    Misc._after_id_counter = 0
    Variable._counter = 0

    yield

    # Reset after test
    Tk._reset_singleton()
    CursesDispatcher._instance = None
    PanelStack._instance = None
    Misc._global_bindings = {}
    Misc._class_bindings = {}
    Misc._clipboard = ""
    Misc._selection = ""
    Misc._focused_widget = None
    Misc._widget_registry = {}
    Misc._after_queue = []
    Misc._after_id_counter = 0
    Variable._counter = 0


@pytest.fixture
def mock_widget_environment(monkeypatch):
    """Mock the curses environment for widget integration tests."""
    # Mock curses module
    mock_curses = MagicMock()
    mock_curses.COLS = 80
    mock_curses.LINES = 24
    mock_curses.beep = MagicMock()
    mock_curses.error = Exception
    mock_curses.newwin = MagicMock(return_value=MagicMock())

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
    mock_dispatcher.call = MagicMock(side_effect=lambda f, *a, **k: f(*a, **k) if callable(f) else MagicMock())

    # Mock InputHandler
    mock_input_handler = MagicMock()
    mock_input_handler.wait_for_input = MagicMock(return_value=False)
    mock_input_handler.get_event = MagicMock(return_value=None)
    mock_input_handler.cleanup = MagicMock()

    # Mock PanelStack
    mock_panel_stack = MagicMock()
    mock_panel = MagicMock()
    mock_panel_stack.create_panel = MagicMock(return_value=mock_panel)
    mock_panel_stack.remove_panel = MagicMock()
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
# Tk and Toplevel Integration Tests
# =============================================================================


class TestTkToplevelIntegration:
    """Test Tk and Toplevel work together correctly."""

    def test_toplevel_uses_tk_screen(self, mock_widget_environment, reset_all_singletons):
        """Toplevel should share Tk's screen instance."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert top._screen is root._screen

    def test_toplevel_uses_tk_dispatcher(self, mock_widget_environment, reset_all_singletons):
        """Toplevel should share Tk's dispatcher instance."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert top._dispatcher is root._dispatcher

    def test_toplevel_uses_tk_panel_stack(self, mock_widget_environment, reset_all_singletons):
        """Toplevel should use Tk's panel stack for z-ordering."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        assert top._panel_stack is root._panel_stack

    def test_multiple_toplevels_share_resources(self, mock_widget_environment, reset_all_singletons):
        """Multiple Toplevels should share Tk resources."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top1 = Toplevel(root)
        top2 = Toplevel(root)
        top3 = Toplevel(root)

        # All share same screen
        assert top1._screen is root._screen
        assert top2._screen is root._screen
        assert top3._screen is root._screen

        # All share same dispatcher
        assert top1._dispatcher is root._dispatcher
        assert top2._dispatcher is root._dispatcher

    def test_nested_toplevel_finds_tk_root(self, mock_widget_environment, reset_all_singletons):
        """Nested Toplevel should find Tk root through hierarchy."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top1 = Toplevel(root)
        top2 = Toplevel(top1)
        top3 = Toplevel(top2)

        assert top1._tk_root is root
        assert top2._tk_root is root
        assert top3._tk_root is root

    def test_toplevel_creates_own_panel(self, mock_widget_environment, reset_all_singletons):
        """Each Toplevel should create its own panel."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top1 = Toplevel(root)
        top2 = Toplevel(root)

        # panel_stack.create_panel should be called for each Toplevel
        # (plus once for Tk itself potentially)
        assert mock_widget_environment['panel_stack'].create_panel.call_count >= 2

    def test_toplevel_destroy_removes_from_tk(self, mock_widget_environment, reset_all_singletons):
        """Destroying Toplevel should remove it from Tk's list."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)
        assert top in root._toplevels

        top.destroy()

        assert top not in root._toplevels


class TestTkToplevelFocus:
    """Test focus management between Tk and Toplevel."""

    def test_toplevel_focus_updates_global_focus(self, mock_widget_environment, reset_all_singletons):
        """Toplevel.focus_set() should update global focus."""
        from tkcurses import Tk, Toplevel, Misc

        root = Tk()
        top = Toplevel(root)

        top.focus_set()

        assert Misc._focused_widget is top

    def test_focus_can_move_between_windows(self, mock_widget_environment, reset_all_singletons):
        """Focus should be movable between Tk and Toplevel."""
        from tkcurses import Tk, Toplevel, Misc

        root = Tk()
        top1 = Toplevel(root)
        top2 = Toplevel(root)

        root.focus_set()
        assert Misc._focused_widget is root

        top1.focus_set()
        assert Misc._focused_widget is top1

        top2.focus_set()
        assert Misc._focused_widget is top2

    def test_focus_get_works_across_windows(self, mock_widget_environment, reset_all_singletons):
        """focus_get() should work from any window."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        top.focus_set()

        # Both should report the same focused widget
        assert root.focus_get() is top
        assert top.focus_get() is top


# =============================================================================
# Variable Integration Tests
# =============================================================================


class TestVariableWithWidgets:
    """Test Variable integration with widget hierarchy."""

    def test_variable_trace_fires_on_set(self, reset_all_singletons):
        """Variable trace should fire when value is set."""
        from tkcurses import StringVar

        var = StringVar()
        trace_calls = []

        def on_change(name, index, mode):
            trace_calls.append((name, mode, var.get()))

        var.trace_add("write", on_change)
        var.set("Hello")
        var.set("World")

        assert len(trace_calls) == 2
        assert trace_calls[0][2] == "Hello"
        assert trace_calls[1][2] == "World"

    def test_multiple_variables_independent_traces(self, reset_all_singletons):
        """Multiple variables should have independent traces."""
        from tkcurses import StringVar, IntVar

        str_var = StringVar()
        int_var = IntVar()

        str_calls = []
        int_calls = []

        str_var.trace_add("write", lambda *a: str_calls.append(str_var.get()))
        int_var.trace_add("write", lambda *a: int_calls.append(int_var.get()))

        str_var.set("test")
        int_var.set(42)
        str_var.set("again")

        assert str_calls == ["test", "again"]
        assert int_calls == [42]

    def test_variable_trace_with_widget_simulation(self, mock_widget_environment, reset_all_singletons):
        """Simulate variable-widget binding pattern."""
        from tkcurses import Tk, StringVar

        root = Tk()
        var = StringVar(value="initial")

        # Simulate widget update on variable change
        widget_state = {"text": "initial"}

        def update_widget(name, index, mode):
            widget_state["text"] = var.get()

        var.trace_add("write", update_widget)

        var.set("updated")

        assert widget_state["text"] == "updated"

    def test_variable_read_trace(self, reset_all_singletons):
        """Read traces should fire when getting value."""
        from tkcurses import IntVar

        var = IntVar(value=10)
        read_count = [0]

        def on_read(*args):
            read_count[0] += 1

        var.trace_add("read", on_read)

        var.get()
        var.get()
        var.get()

        assert read_count[0] == 3


class TestVariableTypeConversions:
    """Test Variable type conversion across boundaries."""

    def test_intvar_stringvar_conversion(self, reset_all_singletons):
        """Test converting between IntVar and StringVar values."""
        from tkcurses import IntVar, StringVar

        int_var = IntVar(value=42)
        str_var = StringVar()

        # Simulate syncing int to string
        str_var.set(str(int_var.get()))
        assert str_var.get() == "42"

        # Simulate syncing string to int
        str_var.set("100")
        int_var.set(int(str_var.get()))
        assert int_var.get() == 100

    def test_booleanvar_checkbox_pattern(self, reset_all_singletons):
        """Test BooleanVar pattern for checkbox widgets."""
        from tkcurses import BooleanVar

        checked = BooleanVar(value=False)
        checkbox_state = {"checked": False}

        def update_checkbox(*args):
            checkbox_state["checked"] = checked.get()

        checked.trace_add("write", update_checkbox)

        # Simulate checkbox toggle
        checked.set(True)
        assert checkbox_state["checked"] is True

        checked.set(False)
        assert checkbox_state["checked"] is False

    def test_doublevar_scale_pattern(self, reset_all_singletons):
        """Test DoubleVar pattern for scale widgets."""
        from tkcurses import DoubleVar

        scale_value = DoubleVar(value=0.0)
        display_label = {"text": "0.0"}

        def update_label(*args):
            display_label["text"] = f"{scale_value.get():.1f}"

        scale_value.trace_add("write", update_label)

        scale_value.set(0.5)
        assert display_label["text"] == "0.5"

        scale_value.set(1.0)
        assert display_label["text"] == "1.0"


# =============================================================================
# Event Binding Integration Tests
# =============================================================================


class TestEventBindingAcrossWindows:
    """Test event binding works across window hierarchy."""

    def test_bind_all_affects_all_windows(self, mock_widget_environment, reset_all_singletons):
        """bind_all() on Tk should affect all Toplevels."""
        from tkcurses import Tk, Toplevel, Misc

        root = Tk()
        top1 = Toplevel(root)
        top2 = Toplevel(root)

        callback = MagicMock()
        root.bind_all("<Control-q>", callback)

        # All windows should see the global binding
        assert "<Control-q>" in Misc._global_bindings

    def test_bind_class_works_for_toplevels(self, mock_widget_environment, reset_all_singletons):
        """bind_class() should work for Toplevel class."""
        from tkcurses import Tk, Toplevel, Misc

        root = Tk()

        callback = MagicMock()
        root.bind_class("Toplevel", "<Escape>", callback)

        # Class binding should be registered
        assert "Toplevel" in Misc._class_bindings
        assert "<Escape>" in Misc._class_bindings["Toplevel"]

    def test_widget_specific_bindings_isolated(self, mock_widget_environment, reset_all_singletons):
        """Widget-specific bindings should not affect other widgets."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top1 = Toplevel(root)
        top2 = Toplevel(root)

        callback1 = MagicMock()
        callback2 = MagicMock()

        top1.bind("<Button-1>", callback1)
        top2.bind("<Button-1>", callback2)

        # Each should have its own binding
        assert "<Button-1>" in top1._bindings
        assert "<Button-1>" in top2._bindings
        assert top1._bindings["<Button-1>"] != top2._bindings["<Button-1>"]


# =============================================================================
# Window Lifecycle Integration Tests
# =============================================================================


class TestWindowLifecycle:
    """Test window creation and destruction lifecycle."""

    def test_toplevel_protocol_integration(self, mock_widget_environment, reset_all_singletons):
        """WM_DELETE_WINDOW protocol should work with destroy."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        close_called = [False]

        def on_close():
            close_called[0] = True

        top.protocol("WM_DELETE_WINDOW", on_close)
        top.destroy()

        assert close_called[0] is True

    def test_destroying_tk_with_toplevels(self, mock_widget_environment, reset_all_singletons):
        """Destroying Tk should handle existing Toplevels gracefully."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top1 = Toplevel(root)
        top2 = Toplevel(root)

        # Should not raise even with open Toplevels
        root.destroy()

        assert root._destroyed is True

    def test_widget_registry_cleanup(self, mock_widget_environment, reset_all_singletons):
        """Widget registry should be cleaned up on destroy."""
        from tkcurses import Tk, Toplevel, Misc

        root = Tk()
        top = Toplevel(root)
        top_name = top._widget_name

        assert top_name in Misc._widget_registry

        top.destroy()

        assert top_name not in Misc._widget_registry

    def test_after_callbacks_across_windows(self, mock_widget_environment, reset_all_singletons):
        """after() callbacks should work from any window."""
        from tkcurses import Tk, Toplevel, Misc

        root = Tk()
        top = Toplevel(root)

        callback1 = MagicMock()
        callback2 = MagicMock()

        root.after(100, callback1)
        top.after(200, callback2)

        # Both should be in the global queue
        assert len(Misc._after_queue) == 2


# =============================================================================
# Clipboard and Selection Integration Tests
# =============================================================================


class TestClipboardIntegration:
    """Test clipboard operations across windows."""

    def test_clipboard_shared_between_windows(self, mock_widget_environment, reset_all_singletons):
        """Clipboard should be shared between Tk and Toplevels."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        # Set clipboard from root
        root.clipboard_clear()
        root.clipboard_append("shared data")

        # Read from Toplevel
        assert top.clipboard_get() == "shared data"

    def test_selection_shared_between_windows(self, mock_widget_environment, reset_all_singletons):
        """Selection should be shared between windows."""
        from tkcurses import Tk, Toplevel, Misc

        root = Tk()
        top = Toplevel(root)

        # Own selection from Toplevel
        top.selection_own()

        # Check selection owner
        assert Misc._selection == ""  # Selection text not set yet


# =============================================================================
# Panel Z-Order Integration Tests
# =============================================================================


class TestPanelZOrderIntegration:
    """Test panel z-ordering with multiple windows."""

    def test_toplevel_lift_calls_panel_top(self, mock_widget_environment, reset_all_singletons):
        """Toplevel.lift() should call panel.top()."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        mock_widget_environment['panel'].top.reset_mock()
        top.lift()

        mock_widget_environment['panel'].top.assert_called()

    def test_toplevel_lower_calls_panel_bottom(self, mock_widget_environment, reset_all_singletons):
        """Toplevel.lower() should call panel.bottom()."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        top.lower()

        mock_widget_environment['panel'].bottom.assert_called()

    def test_transient_raises_to_top(self, mock_widget_environment, reset_all_singletons):
        """Setting transient should raise window."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        dialog = Toplevel(root)

        mock_widget_environment['panel'].top.reset_mock()
        dialog.transient(root)

        mock_widget_environment['panel'].top.assert_called()


# =============================================================================
# Geometry Integration Tests
# =============================================================================


class TestGeometryIntegration:
    """Test geometry management integration."""

    def test_toplevel_geometry_independent(self, mock_widget_environment, reset_all_singletons):
        """Each Toplevel should have independent geometry."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top1 = Toplevel(root)
        top2 = Toplevel(root)

        top1._width = 40
        top1._height = 20
        top2._width = 30
        top2._height = 15

        assert top1.geometry() != top2.geometry()
        assert "40x20" in top1.geometry()
        assert "30x15" in top2.geometry()

    def test_winfo_methods_consistent(self, mock_widget_environment, reset_all_singletons):
        """winfo_* methods should be consistent across windows."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        # Screen size should be same for all
        assert root.winfo_screenwidth() == top.winfo_screenwidth()
        assert root.winfo_screenheight() == top.winfo_screenheight()


# =============================================================================
# Title and State Integration Tests
# =============================================================================


class TestTitleStateIntegration:
    """Test title and state management."""

    def test_each_window_has_own_title(self, mock_widget_environment, reset_all_singletons):
        """Each window should have its own title."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        root.title("Main Window")

        top1 = Toplevel(root)
        top1.title("Dialog 1")

        top2 = Toplevel(root)
        top2.title("Dialog 2")

        assert root.title() == "Main Window"
        assert top1.title() == "Dialog 1"
        assert top2.title() == "Dialog 2"

    def test_each_window_has_own_state(self, mock_widget_environment, reset_all_singletons):
        """Each window should have its own state."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)

        root.state("normal")
        top.state("withdrawn")

        assert root.state() == "normal"
        assert top.state() == "withdrawn"


# =============================================================================
# Error Handling Integration Tests
# =============================================================================


class TestErrorHandlingIntegration:
    """Test error handling across components."""

    def test_toplevel_without_tk_raises(self, reset_all_singletons):
        """Creating Toplevel without Tk should raise RuntimeError."""
        from tkcurses import Toplevel, Tk

        Tk._reset_singleton()

        with pytest.raises(RuntimeError) as exc_info:
            Toplevel()

        assert "Tk instance" in str(exc_info.value)

    def test_variable_trace_error_caught(self, reset_all_singletons):
        """Variable trace errors should be caught, not propagated."""
        from tkcurses import StringVar

        var = StringVar()

        def bad_callback(*args):
            raise ValueError("Intentional error")

        var.trace_add("write", bad_callback)

        # Should not raise
        var.set("test")

    def test_destroyed_toplevel_operations_safe(self, mock_widget_environment, reset_all_singletons):
        """Operations on destroyed Toplevel should be safe."""
        from tkcurses import Tk, Toplevel

        root = Tk()
        top = Toplevel(root)
        top.destroy()

        # These should not raise
        top.lift()
        top.lower()
        top.destroy()  # Second destroy should be safe
