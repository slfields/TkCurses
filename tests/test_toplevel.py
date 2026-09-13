"""Tests for the Toplevel window.

The parts that need no terminal are here; what a toplevel actually puts on
screen is in test_toplevel_tty.py.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Misc, Toplevel, Widget
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


def stub_window(rect: Rect) -> SimpleNamespace:
    return SimpleNamespace(rect=rect)


@pytest.fixture
def stack():
    return PanelStack(window_factory=stub_window, panel_factory=None)


@pytest.fixture
def root(stack, monkeypatch):
    """A root whose screen size is fixed, so geometry assertions are stable."""
    root = Misc()
    root.tk.panels = stack
    monkeypatch.setattr(type(root), "_screen_size", lambda self: (80, 24))
    return root


# ------------------------------------------------------------- toplevelness


def test_a_toplevel_is_its_own_toplevel(root):
    window = Toplevel(root)
    assert window.winfo_toplevel() is window


def test_a_child_of_a_toplevel_reports_that_toplevel(root):
    window = Toplevel(root)
    child = Widget(window, name="child")
    assert child.winfo_toplevel() is window


def test_a_toplevel_does_not_list_itself_twice_in_its_bindtags(root):
    window = Toplevel(root, name="dlg")
    assert window.bindtags() == (".dlg", "Toplevel", "all")


def test_a_childs_bindtags_name_its_toplevel(root):
    window = Toplevel(root, name="dlg")
    child = Widget(window, name="child")
    assert child.bindtags() == (".dlg.child", "Widget", ".dlg", "all")


def test_the_class_can_be_set_at_construction(root):
    window = Toplevel(root, class_="Dialog")
    assert window.winfo_class() == "Dialog"
    assert window.bindtags()[1] == "Dialog"


# ------------------------------------------------------------------ mapping


def test_a_toplevel_maps_itself_without_a_geometry_manager(root):
    window = Toplevel(root)
    assert window.winfo_ismapped()
    assert window._window is not None


def test_a_toplevel_is_viewable_immediately(root):
    assert Toplevel(root).winfo_viewable()


def test_a_toplevel_takes_a_panel_of_its_own(root, stack):
    Toplevel(root)
    assert len(stack) == 1


# ----------------------------------------------------------------- geometry


def test_a_toplevel_defaults_to_a_size_that_fits(root):
    window = Toplevel(root)
    assert (window.winfo_width(), window.winfo_height()) == (30, 10)


def test_a_toplevel_is_centred_by_default(root):
    window = Toplevel(root)
    assert (window.winfo_x(), window.winfo_y()) == ((80 - 30) // 2, (24 - 10) // 2)


def test_an_explicit_size_is_honoured(root):
    window = Toplevel(root, width=20, height=6)
    assert window.winfo_geometry().startswith("20x6+")


def test_resizing_by_configure_moves_the_window(root):
    window = Toplevel(root, width=20, height=6)
    window.configure(width=40, height=12)
    assert (window.winfo_width(), window.winfo_height()) == (40, 12)


def test_a_toplevel_larger_than_the_screen_is_clamped(root):
    window = Toplevel(root, width=200, height=100)
    assert (window.winfo_width(), window.winfo_height()) == (80, 24)
    assert (window.winfo_x(), window.winfo_y()) == (0, 0)


# ------------------------------------------------------------- coordinates


def test_a_toplevels_screen_position_is_its_own(root):
    window = Toplevel(root, width=20, height=6)
    assert (window.winfo_rootx(), window.winfo_rooty()) == (
        window.winfo_x(),
        window.winfo_y(),
    )


def test_a_child_is_offset_from_its_toplevel_not_from_the_root(root):
    window = Toplevel(root, width=20, height=6)
    child = Widget(window, name="child")
    child._rect = Rect(2, 1, 5, 1)
    assert child.winfo_rootx() == window.winfo_x() + 2
    assert child.winfo_rooty() == window.winfo_y() + 1


def test_two_toplevels_do_not_accumulate_each_others_positions(root):
    first = Toplevel(root, name="a", width=20, height=6)
    second = Toplevel(first, name="b", width=20, height=6)
    assert second.winfo_rootx() == second.winfo_x()


# -------------------------------------------------------------- content area


def test_a_bordered_toplevel_loses_a_cell_on_each_edge(root):
    window = Toplevel(root, width=30, height=8)
    content = window._content_rect()
    assert (content.width, content.height) == (28, 6)


def test_the_content_area_starts_inside_the_border(root):
    window = Toplevel(root, width=30, height=8)
    content = window._content_rect()
    assert content.x == window.winfo_x() + 1
    assert content.y == window.winfo_y() + 1


def test_a_borderless_toplevel_offers_every_cell(root):
    window = Toplevel(root, width=30, height=8, borderwidth=0)
    content = window._content_rect()
    assert (content.width, content.height) == (30, 8)


def test_padding_comes_out_of_the_content_area(root):
    window = Toplevel(root, width=30, height=8, padx=2, pady=1)
    content = window._content_rect()
    assert (content.width, content.height) == (24, 4)


def test_a_relief_gives_a_border_even_without_a_borderwidth(root):
    window = Toplevel(root, width=30, height=8, borderwidth=0, relief="raised")
    assert (window._content_rect().width, window._content_rect().height) == (28, 6)


# ------------------------------------------------------------------ stacking


def test_raising_a_toplevel_puts_its_panel_on_top(root, stack):
    first = Toplevel(root, name="a")
    second = Toplevel(root, name="b")
    assert stack.top() is second._panel
    first.tkraise()
    assert stack.top() is first._panel


def test_lowering_a_toplevel_puts_its_panel_at_the_bottom(root, stack):
    first = Toplevel(root, name="a")
    second = Toplevel(root, name="b")
    second.lower()
    assert stack.bottom() is second._panel
    assert stack.top() is first._panel


def test_raising_above_a_named_window(root, stack):
    first = Toplevel(root, name="a")
    Toplevel(root, name="b")
    third = Toplevel(root, name="c")
    first.tkraise(third)
    assert stack.top() is first._panel


def test_stacking_order_and_sibling_order_agree(root):
    first = Toplevel(root, name="a")
    Toplevel(root, name="b")
    first.tkraise()
    assert root.winfo_children()[-1] is first


# ------------------------------------------------------------------- destroy


def test_destroying_a_toplevel_releases_its_panel(root, stack):
    window = Toplevel(root)
    window.destroy()
    assert len(stack) == 0
    assert not window.winfo_exists()


def test_destroying_a_toplevel_takes_its_children(root):
    window = Toplevel(root)
    child = Widget(window, name="child")
    window.destroy()
    assert not child.winfo_exists()


def test_destroying_a_toplevel_leaves_the_others(root, stack):
    first = Toplevel(root, name="a")
    second = Toplevel(root, name="b")
    first.destroy()
    assert len(stack) == 1
    assert second.winfo_exists()
