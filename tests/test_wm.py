"""Tests for the Wm window manager methods."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Misc, TclError, Toplevel
from tkcurses._core.panels import PanelStack


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def stack():
    return PanelStack(window_factory=stub_window, panel_factory=None)


@pytest.fixture
def root(stack, monkeypatch):
    root = Misc()
    root.tk.panels = stack
    monkeypatch.setattr(type(root), "_screen_size", lambda self: (80, 24))
    return root


@pytest.fixture
def window(root):
    return Toplevel(root, width=20, height=6)


# -------------------------------------------------------------------- title


def test_a_window_starts_untitled(window):
    assert window.title() == ""


def test_the_title_round_trips(window):
    window.title("Settings")
    assert window.title() == "Settings"
    assert window.wm_title() == "Settings"


# ----------------------------------------------------------------- geometry


def test_geometry_reports_the_current_size_and_position(window):
    assert window.geometry() == f"20x6+{window.winfo_x()}+{window.winfo_y()}"


def test_geometry_sets_size_and_position(window):
    window.geometry("30x8+4+2")
    assert window.geometry() == "30x8+4+2"


def test_geometry_accepts_a_size_alone(window):
    x, y = window.winfo_x(), window.winfo_y()
    window.geometry("24x7")
    assert window.geometry() == f"24x7+{x}+{y}"


def test_geometry_accepts_a_position_alone(window):
    window.geometry("+9+3")
    assert window.geometry() == "20x6+9+3"


def test_a_negative_offset_measures_from_the_far_edge(window):
    window.geometry("20x6-0-0")
    assert window.geometry() == f"20x6+{80 - 20}+{24 - 6}"


def test_a_negative_offset_leaves_room_beyond_the_window(window):
    window.geometry("20x6-5-2")
    assert window.geometry() == f"20x6+{80 - 20 - 5}+{24 - 6 - 2}"


def test_geometry_is_clamped_to_the_terminal(window):
    window.geometry("200x100+0+0")
    assert window.geometry() == "80x24+0+0"


def test_a_position_past_the_edge_is_pulled_back(window):
    window.geometry("20x6+200+200")
    assert window.geometry() == f"20x6+{80 - 20}+{24 - 6}"


@pytest.mark.parametrize("spec", ["", "nonsense", "20x", "x6", "20*6"])
def test_a_malformed_geometry_is_refused(window, spec):
    with pytest.raises(TclError):
        window.geometry(spec)


# ------------------------------------------------------------------- limits


def test_minsize_round_trips(window):
    window.minsize(10, 4)
    assert window.minsize() == (10, 4)


def test_a_window_cannot_be_made_smaller_than_its_minimum(window):
    window.minsize(15, 5)
    window.geometry("4x2")
    assert window.geometry().startswith("15x5")


def test_setting_a_minimum_grows_a_window_already_below_it(window):
    window.minsize(30, 10)
    assert window.geometry().startswith("30x10")


def test_maxsize_round_trips(window):
    window.maxsize(40, 12)
    assert window.maxsize() == (40, 12)


def test_a_window_cannot_be_made_larger_than_its_maximum(window):
    window.maxsize(24, 8)
    window.geometry("60x20")
    assert window.geometry().startswith("24x8")


def test_maxsize_defaults_to_the_screen(window):
    assert window.maxsize() == (80, 24)


def test_resizable_round_trips(window):
    window.resizable(False, True)
    assert window.resizable() == (False, True)


def test_a_locked_axis_is_left_alone(window):
    window.resizable(False, False)
    window.geometry("40x12")
    assert window.geometry().startswith("20x6")


def test_a_locked_axis_does_not_block_moving(window):
    window.resizable(False, False)
    window.geometry("+3+1")
    assert window.geometry() == "20x6+3+1"


def test_grid_records_the_increments(window):
    window.grid(10, 4, 2, 1)
    assert window.wm_grid() == (10, 4, 2, 1)


# -------------------------------------------------------------------- state


def test_a_window_starts_normal(window):
    assert window.state() == "normal"
    assert window.winfo_ismapped()


def test_withdraw_takes_the_window_off_screen(window):
    window.withdraw()
    assert window.state() == "withdrawn"
    assert not window.winfo_ismapped()


def test_iconify_takes_the_window_off_screen(window):
    window.iconify()
    assert window.state() == "iconic"
    assert not window.winfo_ismapped()


def test_deiconify_puts_it_back(window):
    window.withdraw()
    window.deiconify()
    assert window.state() == "normal"
    assert window.winfo_ismapped()


def test_state_can_be_set_by_name(window):
    window.state("withdrawn")
    assert not window.winfo_ismapped()
    window.state("normal")
    assert window.winfo_ismapped()


def test_an_unknown_state_is_refused(window):
    with pytest.raises(TclError):
        window.state("sideways")


def test_a_withdrawn_window_keeps_its_window_for_later(window, stack):
    window.withdraw()
    assert len(stack) == 1


# ---------------------------------------------------------------- protocols


def test_a_protocol_handler_round_trips(window):
    def handler():
        return None

    window.protocol("WM_DELETE_WINDOW", handler)
    assert window.protocol("WM_DELETE_WINDOW") is handler


def test_registered_protocols_can_be_listed(window):
    window.protocol("WM_DELETE_WINDOW", lambda: None)
    assert window.protocol() == ("WM_DELETE_WINDOW",)


def test_an_unregistered_protocol_reports_nothing(window):
    assert window.protocol("WM_DELETE_WINDOW") is None


def test_invoking_a_protocol_runs_its_handler(window):
    calls = []
    window.protocol("WM_DELETE_WINDOW", lambda: calls.append(1))
    assert window._invoke_protocol("WM_DELETE_WINDOW") is True
    assert calls == [1]


def test_invoking_an_unregistered_protocol_reports_that(window):
    assert window._invoke_protocol("WM_DELETE_WINDOW") is False


# ------------------------------------------------------------- relationships


def test_transient_records_its_owner(root):
    owner = Toplevel(root, name="owner")
    dialog = Toplevel(root, name="dialog")
    dialog.transient(owner)
    assert dialog.transient() is owner


def test_a_transient_window_sits_above_its_owner(root, stack):
    owner = Toplevel(root, name="owner")
    dialog = Toplevel(root, name="dialog")
    owner.tkraise()
    dialog.transient(owner)
    assert stack.top() is dialog._panel


def test_frame_reports_the_windows_own_id(window):
    assert window.frame() == str(window.winfo_id())


def test_focusmodel_round_trips(window):
    assert window.focusmodel() == "passive"
    window.focusmodel("active")
    assert window.focusmodel() == "active"


def test_an_unknown_focus_model_is_refused(window):
    with pytest.raises(TclError):
        window.focusmodel("telepathic")


# --------------------------------------------------------------- decoration


def test_overrideredirect_round_trips(window):
    assert window.overrideredirect() is False
    window.overrideredirect(True)
    assert window.overrideredirect() is True


def test_an_overridden_window_draws_no_border(window):
    window.overrideredirect(True)
    content = window._content_rect()
    assert (content.width, content.height) == (20, 6)


# --------------------------------------------------------------- attributes


def test_attributes_reports_what_is_supported(window):
    assert window.attributes() == ("-topmost", False, "-fullscreen", False)


def test_topmost_round_trips(window):
    window.attributes("-topmost", True)
    assert window.attributes("-topmost") is True


def test_topmost_raises_the_window(root, stack):
    first = Toplevel(root, name="a")
    second = Toplevel(root, name="b")
    first.attributes("-topmost", True)
    assert stack.top() is first._panel
    assert second._panel is not stack.top()


def test_fullscreen_fills_the_terminal(window):
    window.attributes("-fullscreen", True)
    assert window.geometry() == "80x24+0+0"


def test_an_unknown_attribute_is_refused(window):
    with pytest.raises(TclError):
        window.attributes("-transparency", 0.5)


# --------------------------------------------------------------- unsupported


def test_wm_manage_explains_what_it_needs(window):
    with pytest.raises(TclError, match="geometry managers"):
        window.wm_manage(window)


def test_wm_forget_explains_what_it_needs(window):
    with pytest.raises(TclError, match="geometry managers"):
        window.wm_forget(window)
