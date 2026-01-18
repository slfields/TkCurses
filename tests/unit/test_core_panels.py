"""Unit tests for tkcurses._core.panels module."""

from unittest.mock import MagicMock, patch, call
import threading

import pytest

from tkcurses._core.panels import PanelError, Panel, PanelStack
from tkcurses._core.dispatcher import CursesDispatcher


# =============================================================================
# Tests for PanelError Exception
# =============================================================================


class TestPanelError:
    """Tests for PanelError exception class."""

    def test_is_exception_subclass(self):
        """PanelError should be a subclass of Exception."""
        assert issubclass(PanelError, Exception)

    def test_message_handling(self):
        """PanelError should handle error messages."""
        msg = "Test error message"
        error = PanelError(msg)
        assert str(error) == msg

    def test_with_chained_exception(self):
        """PanelError should support exception chaining."""
        original = ValueError("Original error")
        try:
            raise PanelError("Wrapped error") from original
        except PanelError as e:
            assert str(e) == "Wrapped error"
            assert e.__cause__ is original


# =============================================================================
# Tests for Panel Class
# =============================================================================


class TestPanel:
    """Tests for Panel class."""

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        """Reset dispatcher and panel stack singletons before each test."""
        CursesDispatcher._instance = None
        PanelStack.reset_singleton()
        yield
        CursesDispatcher._instance = None
        PanelStack.reset_singleton()

    @pytest.fixture
    def mock_window(self):
        """Create a mock curses window."""
        window = MagicMock()
        window.getmaxyx.return_value = (10, 20)
        return window

    @pytest.fixture
    def mock_curses_panel(self):
        """Create a mock curses.panel.Panel object."""
        panel = MagicMock()
        panel.hidden.return_value = False
        panel.above.return_value = None
        panel.below.return_value = None
        return panel

    @pytest.fixture
    def panel_instance(self, mock_window):
        """Create a Panel instance with mocked curses."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            dispatcher = CursesDispatcher.get()
            panel = Panel(mock_window)
            return panel

    def test_panel_init_stores_window(self, mock_window):
        """Panel.__init__() should store the window."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel = Panel(mock_window)
            assert panel.window is mock_window

    def test_panel_init_creates_curses_panel(self, mock_window):
        """Panel.__init__() should create a curses panel."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_panel_obj = MagicMock()
            mock_curses_panel_module.new_panel.return_value = mock_panel_obj

            panel = Panel(mock_window)

            mock_curses_panel_module.new_panel.assert_called_once()

    def test_panel_init_visible_by_default(self, mock_window):
        """Panel should be visible after initialization."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel = Panel(mock_window)
            # Panel starts with _visible = True
            assert panel._visible is True

    def test_panel_init_handles_creation_failure(self, mock_window):
        """Panel.__init__() should raise PanelError on creation failure."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.side_effect = RuntimeError("Panel creation failed")

            with pytest.raises(PanelError, match="Failed to create panel"):
                Panel(mock_window)

    def test_window_property(self, panel_instance, mock_window):
        """window property should return the underlying curses window."""
        assert panel_instance.window is mock_window

    def test_show_makes_panel_visible(self, panel_instance):
        """show() should make the panel visible."""
        panel_instance._visible = False
        panel_instance.show()
        assert panel_instance._visible is True

    def test_show_is_noop_when_already_visible(self, panel_instance):
        """show() should be a no-op if already visible."""
        panel_instance._visible = True
        # Should not call dispatcher
        panel_instance.show()
        # Verify _visible is still True
        assert panel_instance._visible is True

    def test_show_calls_dispatcher(self, panel_instance):
        """show() should call dispatcher for panel show operation."""
        panel_instance._visible = False
        with patch.object(panel_instance._dispatcher, 'call') as mock_call:
            panel_instance.show()
            mock_call.assert_called_once()

    def test_show_handles_error(self, panel_instance):
        """show() should raise PanelError on dispatcher failure."""
        panel_instance._visible = False
        with patch.object(panel_instance._dispatcher, 'call', side_effect=RuntimeError("Show failed")):
            with pytest.raises(PanelError, match="Failed to show panel"):
                panel_instance.show()

    def test_hide_hides_panel(self, panel_instance):
        """hide() should hide the panel."""
        panel_instance._visible = True
        panel_instance.hide()
        assert panel_instance._visible is False

    def test_hide_is_noop_when_already_hidden(self, panel_instance):
        """hide() should be a no-op if already hidden."""
        panel_instance._visible = False
        panel_instance.hide()
        assert panel_instance._visible is False

    def test_hide_calls_dispatcher(self, panel_instance):
        """hide() should call dispatcher for panel hide operation."""
        panel_instance._visible = True
        with patch.object(panel_instance._dispatcher, 'call') as mock_call:
            panel_instance.hide()
            mock_call.assert_called_once()

    def test_hide_handles_error(self, panel_instance):
        """hide() should raise PanelError on dispatcher failure."""
        panel_instance._visible = True
        with patch.object(panel_instance._dispatcher, 'call', side_effect=RuntimeError("Hide failed")):
            with pytest.raises(PanelError, match="Failed to hide panel"):
                panel_instance.hide()

    def test_hidden_returns_visibility_state(self, panel_instance):
        """hidden() should return the panel's hidden state."""
        with patch.object(panel_instance._dispatcher, 'call', return_value=True):
            result = panel_instance.hidden()
            assert result is True

    def test_hidden_calls_dispatcher(self, panel_instance):
        """hidden() should call dispatcher."""
        with patch.object(panel_instance._dispatcher, 'call', return_value=False) as mock_call:
            panel_instance.hidden()
            mock_call.assert_called_once_with(panel_instance._panel.hidden)

    def test_hidden_handles_error(self, panel_instance):
        """hidden() should raise PanelError on dispatcher failure."""
        with patch.object(panel_instance._dispatcher, 'call', side_effect=RuntimeError("Hidden check failed")):
            with pytest.raises(PanelError, match="Failed to check panel visibility"):
                panel_instance.hidden()

    def test_top_calls_dispatcher(self, panel_instance):
        """top() should call dispatcher to move panel to top."""
        with patch.object(panel_instance._dispatcher, 'call') as mock_call:
            panel_instance.top()
            mock_call.assert_called_once_with(panel_instance._panel.top)

    def test_top_handles_error(self, panel_instance):
        """top() should raise PanelError on dispatcher failure."""
        with patch.object(panel_instance._dispatcher, 'call', side_effect=RuntimeError("Top failed")):
            with pytest.raises(PanelError, match="Failed to move panel to top"):
                panel_instance.top()

    def test_bottom_calls_dispatcher(self, panel_instance):
        """bottom() should call dispatcher to move panel to bottom."""
        with patch.object(panel_instance._dispatcher, 'call') as mock_call:
            panel_instance.bottom()
            mock_call.assert_called_once_with(panel_instance._panel.bottom)

    def test_bottom_handles_error(self, panel_instance):
        """bottom() should raise PanelError on dispatcher failure."""
        with patch.object(panel_instance._dispatcher, 'call', side_effect=RuntimeError("Bottom failed")):
            with pytest.raises(PanelError, match="Failed to move panel to bottom"):
                panel_instance.bottom()

    def test_move_calls_dispatcher_with_coordinates(self, panel_instance):
        """move() should call dispatcher with y and x coordinates."""
        with patch.object(panel_instance._dispatcher, 'call') as mock_call:
            panel_instance.move(5, 10)
            mock_call.assert_called_once_with(panel_instance._panel.move, 5, 10)

    def test_move_handles_error(self, panel_instance):
        """move() should raise PanelError on dispatcher failure."""
        with patch.object(panel_instance._dispatcher, 'call', side_effect=RuntimeError("Move failed")):
            with pytest.raises(PanelError, match="Failed to move panel to"):
                panel_instance.move(5, 10)

    def test_replace_window_calls_dispatcher(self, panel_instance, mock_window):
        """replace() should call dispatcher with new window."""
        new_window = MagicMock()
        with patch.object(panel_instance._dispatcher, 'call') as mock_call:
            panel_instance.replace(new_window)
            mock_call.assert_called_once_with(panel_instance._panel.replace, new_window)

    def test_replace_window_updates_internal_window(self, panel_instance, mock_window):
        """replace() should update internal window reference."""
        new_window = MagicMock()
        with patch.object(panel_instance._dispatcher, 'call'):
            panel_instance.replace(new_window)
            assert panel_instance.window is new_window

    def test_replace_handles_error(self, panel_instance):
        """replace() should raise PanelError on dispatcher failure."""
        new_window = MagicMock()
        with patch.object(panel_instance._dispatcher, 'call', side_effect=RuntimeError("Replace failed")):
            with pytest.raises(PanelError, match="Failed to replace panel window"):
                panel_instance.replace(new_window)

    def test_set_userptr_stores_object(self, panel_instance):
        """set_userptr() should store arbitrary user data."""
        obj = {"key": "value"}
        panel_instance.set_userptr(obj)
        assert panel_instance.userptr() is obj

    def test_userptr_returns_none_by_default(self, panel_instance):
        """userptr() should return None by default."""
        assert panel_instance.userptr() is None

    def test_userptr_returns_stored_object(self, panel_instance):
        """userptr() should return previously set user object."""
        obj = [1, 2, 3]
        panel_instance.set_userptr(obj)
        assert panel_instance.userptr() == obj

    def test_userptr_can_store_none(self, panel_instance):
        """userptr() should handle None as a valid value."""
        panel_instance.set_userptr("something")
        panel_instance.set_userptr(None)
        assert panel_instance.userptr() is None

    def test_above_returns_none_when_top(self, panel_instance):
        """above() should return None when this is the top panel."""
        with patch.object(panel_instance._dispatcher, 'call', return_value=None):
            result = panel_instance.above()
            assert result is None

    def test_above_returns_panel_wrapper(self, panel_instance):
        """above() should return Panel wrapper for above panel."""
        # Create another panel to get the wrapper for
        mock_above_panel = MagicMock()
        above_window = MagicMock()

        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = mock_above_panel
            above_panel = Panel(above_window)

        # Make the dispatcher return the mock above panel
        with patch.object(panel_instance._dispatcher, 'call', return_value=mock_above_panel):
            with patch('tkcurses._core.panels.PanelStack') as mock_stack_class:
                mock_stack = MagicMock()
                mock_stack._get_panel_wrapper.return_value = above_panel
                mock_stack_class.get.return_value = mock_stack

                result = panel_instance.above()
                assert result is above_panel

    def test_above_handles_error(self, panel_instance):
        """above() should raise PanelError on dispatcher failure."""
        with patch.object(panel_instance._dispatcher, 'call', side_effect=RuntimeError("Above failed")):
            with pytest.raises(PanelError, match="Failed to get panel above"):
                panel_instance.above()

    def test_below_returns_none_when_bottom(self, panel_instance):
        """below() should return None when this is the bottom panel."""
        with patch.object(panel_instance._dispatcher, 'call', return_value=None):
            result = panel_instance.below()
            assert result is None

    def test_below_returns_panel_wrapper(self, panel_instance):
        """below() should return Panel wrapper for below panel."""
        mock_below_panel = MagicMock()
        below_window = MagicMock()

        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = mock_below_panel
            below_panel = Panel(below_window)

        with patch.object(panel_instance._dispatcher, 'call', return_value=mock_below_panel):
            with patch('tkcurses._core.panels.PanelStack') as mock_stack_class:
                mock_stack = MagicMock()
                mock_stack._get_panel_wrapper.return_value = below_panel
                mock_stack_class.get.return_value = mock_stack

                result = panel_instance.below()
                assert result is below_panel

    def test_below_handles_error(self, panel_instance):
        """below() should raise PanelError on dispatcher failure."""
        with patch.object(panel_instance._dispatcher, 'call', side_effect=RuntimeError("Below failed")):
            with pytest.raises(PanelError, match="Failed to get panel below"):
                panel_instance.below()


# =============================================================================
# Tests for PanelStack Class
# =============================================================================


class TestPanelStack:
    """Tests for PanelStack singleton manager."""

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        """Reset dispatcher and panel stack singletons before each test."""
        CursesDispatcher._instance = None
        PanelStack.reset_singleton()
        yield
        CursesDispatcher._instance = None
        PanelStack.reset_singleton()

    @pytest.fixture
    def mock_window(self):
        """Create a mock curses window."""
        window = MagicMock()
        window.getmaxyx.return_value = (10, 20)
        return window

    @pytest.fixture
    def panel_stack(self):
        """Create a PanelStack instance."""
        return PanelStack.get()

    def test_get_returns_singleton_instance(self):
        """PanelStack.get() should return the same instance."""
        stack1 = PanelStack.get()
        stack2 = PanelStack.get()
        assert stack1 is stack2

    def test_get_creates_instance_on_first_call(self):
        """PanelStack.get() should create instance on first call."""
        assert PanelStack._instance is None
        stack = PanelStack.get()
        assert PanelStack._instance is stack

    def test_init_creates_empty_panel_list(self):
        """PanelStack.__init__() should initialize empty panel list."""
        stack = PanelStack()
        assert stack.get_panels() == []

    def test_init_stores_dispatcher_reference(self):
        """PanelStack.__init__() should store dispatcher reference."""
        stack = PanelStack()
        assert stack._dispatcher is CursesDispatcher.get()

    def test_create_panel_returns_panel(self, panel_stack, mock_window):
        """create_panel() should return a Panel object."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel = panel_stack.create_panel(mock_window)
            assert isinstance(panel, Panel)

    def test_create_panel_adds_to_stack(self, panel_stack, mock_window):
        """create_panel() should add panel to internal list."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel = panel_stack.create_panel(mock_window)
            assert panel in panel_stack.get_panels()

    def test_create_panel_multiple_panels(self, panel_stack, mock_window):
        """create_panel() should support multiple panels."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel1 = panel_stack.create_panel(mock_window)
            panel2 = panel_stack.create_panel(mock_window)

            panels = panel_stack.get_panels()
            assert len(panels) == 2
            assert panel1 in panels
            assert panel2 in panels

    def test_create_panel_propagates_panel_error(self, panel_stack, mock_window):
        """create_panel() should propagate PanelError from Panel."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.side_effect = RuntimeError("Creation failed")

            with pytest.raises(PanelError):
                panel_stack.create_panel(mock_window)

    def test_remove_panel_removes_from_stack(self, panel_stack, mock_window):
        """remove_panel() should remove panel from stack."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel = panel_stack.create_panel(mock_window)
            panel_stack.remove_panel(panel)
            assert panel not in panel_stack.get_panels()

    def test_remove_panel_hides_panel(self, panel_stack, mock_window):
        """remove_panel() should hide the panel."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel = panel_stack.create_panel(mock_window)

            with patch.object(panel, 'hide') as mock_hide:
                panel_stack.remove_panel(panel)
                mock_hide.assert_called_once()

    def test_remove_panel_raises_error_if_not_in_stack(self, panel_stack, mock_window):
        """remove_panel() should raise PanelError if panel not in stack."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel = Panel(mock_window)

            with pytest.raises(PanelError, match="Panel is not in the stack"):
                panel_stack.remove_panel(panel)

    def test_update_calls_dispatcher(self, panel_stack):
        """update() should call dispatcher for update_panels and doupdate."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            with patch('tkcurses._core.panels.curses.doupdate') as mock_doupdate:
                with patch.object(panel_stack._dispatcher, 'call') as mock_call:
                    panel_stack.update()
                    # Should call dispatcher twice: update_panels + doupdate
                    assert mock_call.call_count == 2

    def test_update_handles_error(self, panel_stack):
        """update() should raise PanelError on dispatcher failure."""
        with patch.object(panel_stack._dispatcher, 'call', side_effect=RuntimeError("Update failed")):
            with pytest.raises(PanelError, match="Failed to update panels"):
                panel_stack.update()

    def test_top_panel_returns_none_when_empty(self, panel_stack):
        """top_panel() should return None when stack is empty."""
        result = panel_stack.top_panel()
        assert result is None

    def test_top_panel_calls_dispatcher(self, panel_stack, mock_window):
        """top_panel() should call dispatcher to get top panel."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_panel_obj = MagicMock()
            mock_curses_panel_module.new_panel.return_value = mock_panel_obj
            panel_stack.create_panel(mock_window)

            with patch('tkcurses._core.panels.curses.panel.top_panel') as mock_top:
                mock_top.return_value = mock_panel_obj
                with patch.object(panel_stack._dispatcher, 'call', return_value=mock_panel_obj):
                    result = panel_stack.top_panel()
                    # Should have called dispatcher.call with curses.panel.top_panel
                    panel_stack._dispatcher.call.assert_called()

    def test_top_panel_returns_panel_wrapper(self, panel_stack, mock_window):
        """top_panel() should return the Panel wrapper for the top panel."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_panel_obj = MagicMock()
            mock_curses_panel_module.new_panel.return_value = mock_panel_obj
            panel = panel_stack.create_panel(mock_window)

            with patch.object(panel_stack._dispatcher, 'call', return_value=mock_panel_obj):
                result = panel_stack.top_panel()
                # Should return the panel we created
                assert result is panel

    def test_top_panel_handles_error(self, panel_stack, mock_window):
        """top_panel() should raise PanelError on dispatcher failure."""
        # Need to add a panel first, otherwise it returns None early
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel_stack.create_panel(mock_window)

        with patch.object(panel_stack._dispatcher, 'call', side_effect=RuntimeError("Top panel failed")):
            with pytest.raises(PanelError, match="Failed to get top panel"):
                panel_stack.top_panel()

    def test_bottom_panel_returns_none_when_empty(self, panel_stack):
        """bottom_panel() should return None when stack is empty."""
        result = panel_stack.bottom_panel()
        assert result is None

    def test_bottom_panel_calls_dispatcher(self, panel_stack, mock_window):
        """bottom_panel() should call dispatcher to get bottom panel."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_panel_obj = MagicMock()
            mock_curses_panel_module.new_panel.return_value = mock_panel_obj
            panel_stack.create_panel(mock_window)

            with patch.object(panel_stack._dispatcher, 'call', return_value=mock_panel_obj):
                result = panel_stack.bottom_panel()
                # Should have called dispatcher
                panel_stack._dispatcher.call.assert_called()

    def test_bottom_panel_returns_panel_wrapper(self, panel_stack, mock_window):
        """bottom_panel() should return the Panel wrapper for the bottom panel."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_panel_obj = MagicMock()
            mock_curses_panel_module.new_panel.return_value = mock_panel_obj
            panel = panel_stack.create_panel(mock_window)

            with patch.object(panel_stack._dispatcher, 'call', return_value=mock_panel_obj):
                result = panel_stack.bottom_panel()
                assert result is panel

    def test_bottom_panel_handles_error(self, panel_stack, mock_window):
        """bottom_panel() should raise PanelError on dispatcher failure."""
        # Need to add a panel first, otherwise it returns None early
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel_stack.create_panel(mock_window)

        with patch.object(panel_stack._dispatcher, 'call', side_effect=RuntimeError("Bottom panel failed")):
            with pytest.raises(PanelError, match="Failed to get bottom panel"):
                panel_stack.bottom_panel()

    def test_get_panels_returns_list(self, panel_stack):
        """get_panels() should return a list."""
        result = panel_stack.get_panels()
        assert isinstance(result, list)

    def test_get_panels_returns_copy(self, panel_stack, mock_window):
        """get_panels() should return a copy of the panel list."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel_stack.create_panel(mock_window)

            panels1 = panel_stack.get_panels()
            panels2 = panel_stack.get_panels()

            # Should be equal but not the same object
            assert panels1 == panels2
            assert panels1 is not panels2

    def test_get_panels_contains_created_panels(self, panel_stack, mock_window):
        """get_panels() should contain all created panels."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel1 = panel_stack.create_panel(mock_window)
            panel2 = panel_stack.create_panel(mock_window)

            panels = panel_stack.get_panels()
            assert panel1 in panels
            assert panel2 in panels

    def test_clear_removes_all_panels(self, panel_stack, mock_window):
        """clear() should remove all panels from stack."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel_stack.create_panel(mock_window)
            panel_stack.create_panel(mock_window)

            panel_stack.clear()

            assert panel_stack.get_panels() == []

    def test_clear_hides_all_panels(self, panel_stack, mock_window):
        """clear() should hide all panels."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel1 = panel_stack.create_panel(mock_window)
            panel2 = panel_stack.create_panel(mock_window)

            with patch.object(panel1, 'hide') as mock_hide1:
                with patch.object(panel2, 'hide') as mock_hide2:
                    panel_stack.clear()
                    mock_hide1.assert_called_once()
                    mock_hide2.assert_called_once()

    def test_get_panel_wrapper_returns_matching_panel(self, panel_stack, mock_window):
        """_get_panel_wrapper() should return Panel for matching curses panel."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_panel_obj = MagicMock()
            mock_curses_panel_module.new_panel.return_value = mock_panel_obj
            panel = panel_stack.create_panel(mock_window)

            result = panel_stack._get_panel_wrapper(mock_panel_obj)
            assert result is panel

    def test_get_panel_wrapper_returns_none_when_not_found(self, panel_stack):
        """_get_panel_wrapper() should return None if panel not found."""
        mock_panel = MagicMock()
        result = panel_stack._get_panel_wrapper(mock_panel)
        assert result is None

    def test_reset_singleton_clears_instance(self, panel_stack, mock_window):
        """reset_singleton() should clear the singleton instance."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel_stack.create_panel(mock_window)

        PanelStack.reset_singleton()

        assert PanelStack._instance is None

    def test_reset_singleton_clears_panels(self, panel_stack, mock_window):
        """reset_singleton() should hide and clear all panels."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()
            panel = panel_stack.create_panel(mock_window)

            with patch.object(panel, 'hide') as mock_hide:
                PanelStack.reset_singleton()
                mock_hide.assert_called_once()

    def test_reset_singleton_creates_new_instance_on_get(self):
        """After reset_singleton(), get() should create a new instance."""
        stack1 = PanelStack.get()
        stack1_id = id(stack1)

        PanelStack.reset_singleton()
        stack2 = PanelStack.get()
        stack2_id = id(stack2)

        # Should be different instances
        assert stack1_id != stack2_id


# =============================================================================
# Integration Tests
# =============================================================================


class TestPanelIntegration:
    """Integration tests for Panel and PanelStack."""

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        """Reset singletons before each test."""
        CursesDispatcher._instance = None
        PanelStack.reset_singleton()
        yield
        CursesDispatcher._instance = None
        PanelStack.reset_singleton()

    @pytest.fixture
    def mock_window(self):
        """Create a mock curses window."""
        window = MagicMock()
        window.getmaxyx.return_value = (10, 20)
        return window

    def test_panel_stack_workflow(self, mock_window):
        """Test typical PanelStack workflow."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_panel_obj = MagicMock()
            mock_curses_panel_module.new_panel.return_value = mock_panel_obj
            mock_curses_panel_module.update_panels = MagicMock()

            stack = PanelStack.get()

            # Create panels
            panel1 = stack.create_panel(mock_window)
            panel2 = stack.create_panel(mock_window)

            assert len(stack.get_panels()) == 2

            # Show/hide operations
            panel1.hide()
            assert panel1.hidden() or not panel1._visible

            # Z-order operations
            panel1.top()
            panel2.bottom()

            # Update stack
            with patch.object(stack._dispatcher, 'call'):
                stack.update()

            # Remove a panel
            stack.remove_panel(panel1)
            assert len(stack.get_panels()) == 1

    def test_multiple_panels_in_stack(self, mock_window):
        """Test managing multiple panels in the stack."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()

            stack = PanelStack.get()
            panels = [stack.create_panel(mock_window) for _ in range(5)]

            assert len(stack.get_panels()) == 5

            # Remove middle panel
            stack.remove_panel(panels[2])

            assert len(stack.get_panels()) == 4
            assert panels[2] not in stack.get_panels()

    def test_panel_userptr_workflow(self, mock_window):
        """Test setting and getting user data on panels."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()

            stack = PanelStack.get()
            panel = stack.create_panel(mock_window)

            # Store user data
            user_data = {"widget": "label", "id": 42}
            panel.set_userptr(user_data)

            # Retrieve user data
            retrieved = panel.userptr()
            assert retrieved == user_data
            assert retrieved["id"] == 42

    def test_panel_window_replacement(self, mock_window):
        """Test replacing a panel's window."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()

            stack = PanelStack.get()
            panel = stack.create_panel(mock_window)

            assert panel.window is mock_window

            # Replace with new window
            new_window = MagicMock()
            with patch.object(panel._dispatcher, 'call'):
                panel.replace(new_window)

            assert panel.window is new_window

    def test_singleton_persistence_across_operations(self, mock_window):
        """Test that singleton persists across operations."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()

            stack1 = PanelStack.get()
            panel1 = stack1.create_panel(mock_window)

            stack2 = PanelStack.get()
            panels2 = stack2.get_panels()

            # Should be the same stack with the same panel
            assert stack1 is stack2
            assert panel1 in panels2


# =============================================================================
# Thread Safety Tests
# =============================================================================


class TestPanelThreadSafety:
    """Tests for thread safety of Panel operations."""

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        """Reset singletons before each test."""
        CursesDispatcher._instance = None
        PanelStack.reset_singleton()
        yield
        CursesDispatcher._instance = None
        PanelStack.reset_singleton()

    @pytest.fixture
    def mock_window(self):
        """Create a mock curses window."""
        window = MagicMock()
        window.getmaxyx.return_value = (10, 20)
        return window

    def test_panel_operations_through_dispatcher(self, mock_window):
        """Panel operations should use dispatcher for thread safety."""
        with patch('tkcurses._core.panels.curses.panel') as mock_curses_panel_module:
            mock_curses_panel_module.new_panel.return_value = MagicMock()

            dispatcher = CursesDispatcher.get()
            panel = Panel(mock_window)

            # All operations should go through dispatcher
            with patch.object(dispatcher, 'call', wraps=dispatcher.call) as mock_call:
                panel.hide()
                panel.show()
                panel.top()
                panel.bottom()
                panel.move(5, 10)

                # Each should have called dispatcher.call (at least 5 times for these operations)
                # hide, show, top, bottom, move = 5 calls
                assert mock_call.call_count >= 5

    def test_panel_stack_singleton_thread_safety(self, mock_window):
        """PanelStack.get() should be thread-safe."""
        instances = []
        lock = threading.Lock()

        def get_instance():
            with patch('tkcurses._core.panels.curses.panel'):
                instance = PanelStack.get()
                with lock:
                    instances.append(instance)

        threads = [threading.Thread(target=get_instance) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should be the same instance
        if instances:
            first_id = id(instances[0])
            assert all(id(i) == first_id for i in instances)
