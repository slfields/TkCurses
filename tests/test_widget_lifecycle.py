"""Tests for the widget window lifecycle: allocation, mapping, destruction."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Misc, Widget
from tkcurses._core.geometry import Rect, Size
from tkcurses._core.panels import PanelStack


class Frame(Widget):
    """A stand-in widget; the lifecycle is the same for all of them."""


def stub_window(rect: Rect) -> SimpleNamespace:
    """A window that records its region and touches no terminal."""
    return SimpleNamespace(rect=rect)


@pytest.fixture
def stack():
    """A panel stack with no curses behind it.

    ``panel_factory=None`` leaves PanelStack as a pure ordering model, which
    is exactly the half of it the widget layer drives.
    """
    return PanelStack(window_factory=stub_window, panel_factory=None)


@pytest.fixture
def root(stack):
    root = Misc()
    root.tk.panels = stack
    return root


@pytest.fixture
def widget(root):
    return Frame(root, name="w")


# ------------------------------------------------------------- allocation


def test_a_new_widget_has_no_window(widget):
    assert widget._window is None
    assert not widget.winfo_ismapped()


def test_allocation_records_the_region_without_mapping(widget):
    widget._allocate(Rect(2, 1, 10, 3))
    assert widget.winfo_geometry() == "10x3+2+1"
    assert widget._window is None


def test_mapping_an_allocated_widget_creates_its_window(widget, stack):
    widget._allocate(Rect(2, 1, 10, 3))
    widget._map()
    assert widget._window is not None
    assert len(stack) == 1


def test_allocating_after_mapping_also_creates_the_window(widget):
    widget._map()
    assert widget._window is None  # nothing to build on yet
    widget._allocate(Rect(0, 0, 4, 2))
    assert widget._window is not None


def test_the_window_covers_the_allocated_region(widget):
    widget._allocate(Rect(3, 2, 8, 4))
    widget._map()
    assert widget._panel.rect == Rect(3, 2, 8, 4)


def test_the_panel_points_back_at_its_widget(widget):
    widget._allocate(Rect(0, 0, 4, 2))
    widget._map()
    # userptr() is a call, mirroring curses' own panel API.
    assert widget._panel.userptr() is widget


# ----------------------------------------------------------------- resize


def test_growing_replaces_the_window(widget):
    widget._allocate(Rect(0, 0, 4, 2))
    widget._map()
    first = widget._window
    widget._allocate(Rect(0, 0, 10, 5))
    assert widget._window is not first
    assert widget._panel.rect == Rect(0, 0, 10, 5)


def test_shrinking_replaces_the_window_too(widget):
    widget._allocate(Rect(0, 0, 20, 5))
    widget._map()
    first = widget._window
    widget._allocate(Rect(0, 0, 10, 3))
    # Replacing rather than resizing is what stops the vacated cells keeping
    # the old contents.
    assert widget._window is not first
    assert widget._panel.rect == Rect(0, 0, 10, 3)


def test_moving_without_resizing_keeps_the_window(widget):
    widget._allocate(Rect(0, 0, 6, 2))
    widget._map()
    first = widget._window
    widget._allocate(Rect(5, 3, 6, 2))
    assert widget._window is first
    assert widget._panel.rect == Rect(5, 3, 6, 2)


def test_reallocating_the_same_region_changes_nothing(widget):
    widget._allocate(Rect(1, 1, 6, 2))
    widget._map()
    first = widget._window
    widget._allocate(Rect(1, 1, 6, 2))
    assert widget._window is first


def test_an_empty_allocation_drops_the_window(widget, stack):
    widget._allocate(Rect(0, 0, 6, 2))
    widget._map()
    widget._allocate(Rect(0, 0, 0, 0))
    assert widget._window is None
    assert len(stack) == 0


def test_an_empty_allocation_on_an_unmapped_widget_is_harmless(widget):
    widget._allocate(Rect(0, 0, 0, 0))
    assert widget._window is None


# ------------------------------------------------------------ map / unmap


def test_mapping_reports_the_widget_as_mapped(widget):
    widget._allocate(Rect(0, 0, 4, 2))
    widget._map()
    assert widget.winfo_ismapped()


def test_mapping_raises_a_map_event(widget):
    seen = []
    widget.bind("<Map>", lambda event: seen.append(event.widget))
    widget._allocate(Rect(0, 0, 4, 2))
    widget._map()
    assert seen == [widget]


def test_mapping_twice_raises_one_event(widget):
    seen = []
    widget.bind("<Map>", lambda event: seen.append(1))
    widget._map()
    widget._map()
    assert seen == [1]


def test_unmapping_hides_the_window_without_destroying_it(widget, stack):
    widget._allocate(Rect(0, 0, 4, 2))
    widget._map()
    widget._unmap()
    assert not widget.winfo_ismapped()
    assert widget._window is not None
    assert widget._panel.hidden
    assert len(stack) == 1


def test_unmapping_raises_an_unmap_event(widget):
    seen = []
    widget.bind("<Unmap>", lambda event: seen.append(1))
    widget._allocate(Rect(0, 0, 4, 2))
    widget._map()
    widget._unmap()
    assert seen == [1]


def test_unmapping_an_unmapped_widget_raises_nothing(widget):
    widget.bind("<Unmap>", lambda event: pytest.fail("should not fire"))
    widget._unmap()


def test_remapping_shows_the_same_window(widget):
    widget._allocate(Rect(0, 0, 4, 2))
    widget._map()
    first = widget._window
    widget._unmap()
    widget._map()
    assert widget._window is first
    assert not widget._panel.hidden


# ---------------------------------------------------------------- destroy


def test_destroying_releases_the_window(widget, stack):
    widget._allocate(Rect(0, 0, 4, 2))
    widget._map()
    widget.destroy()
    assert widget._window is None
    assert len(stack) == 0


def test_destroying_a_widget_with_no_window_is_harmless(widget):
    widget.destroy()
    assert not widget.winfo_exists()


def test_destroying_twice_is_harmless(widget):
    widget._allocate(Rect(0, 0, 4, 2))
    widget._map()
    widget.destroy()
    widget.destroy()


def test_a_childs_window_goes_before_its_parents(root, stack):
    parent = Frame(root, name="parent")
    child = Frame(parent, name="child")
    for each in (parent, child):
        each._allocate(Rect(0, 0, 4, 2))
        each._map()
    order = []
    parent.bind("<Destroy>", lambda event: order.append(("parent", len(stack))))
    child.bind("<Destroy>", lambda event: order.append(("child", len(stack))))
    parent.destroy()
    # The child's Destroy runs first, and by the time the parent's does, the
    # child's panel is already gone.
    assert [name for name, _ in order] == ["child", "parent"]
    assert len(stack) == 0


def test_destroying_a_subtree_releases_every_window(root, stack):
    parent = Frame(root, name="parent")
    for name in ("a", "b"):
        child = Frame(parent, name=name)
        child._allocate(Rect(0, 0, 4, 2))
        child._map()
    parent.destroy()
    assert len(stack) == 0


# ------------------------------------------------- before curses is running


def test_a_widget_without_a_panel_stack_still_tracks_its_layout():
    """Layout is decided before curses exists; the window follows later."""
    root = Misc()
    assert root.tk.panels is None
    widget = Frame(root, name="w")
    widget._allocate(Rect(2, 1, 10, 3))
    widget._map()
    assert widget.winfo_ismapped()
    assert widget.winfo_geometry() == "10x3+2+1"
    assert widget._window is None


def test_a_widget_without_a_panel_stack_can_be_destroyed():
    root = Misc()
    widget = Frame(root, name="w")
    widget._allocate(Rect(0, 0, 4, 2))
    widget._map()
    widget.destroy()
    assert not widget.winfo_exists()


# ------------------------------------------------------ nested containers

# Three bugs found by rendering a layout on a real terminal rather than
# reading coordinates back. Every winfo_* query was already correct in each
# case, which is why the geometry tests passed throughout.


def test_a_panel_is_positioned_in_screen_coordinates(root, stack):
    """A rect is an offset from the master; a panel is placed absolutely."""
    parent = Frame(root, name="parent")
    parent._allocate(Rect(4, 3, 20, 6))
    parent._map()
    child = Frame(parent, name="child")
    child._allocate(Rect(2, 1, 6, 2))
    child._map()
    assert child._panel.rect == Rect(6, 4, 6, 2)


def test_moving_a_parent_moves_its_childs_panel(root):
    parent = Frame(root, name="parent")
    parent._allocate(Rect(0, 0, 20, 6))
    parent._map()
    child = Frame(parent, name="child")
    child._allocate(Rect(1, 1, 6, 2))
    child._map()

    parent._allocate(Rect(10, 5, 20, 6))
    # The child's own rect is unchanged; only the screen position moved.
    child._allocate(child._rect)
    assert child._panel.rect == Rect(11, 6, 6, 2)


def test_a_child_panel_is_always_above_its_container(root, stack):
    """Panels are created in layout order, which is not tree order."""
    parent = Frame(root, name="parent")
    child = Frame(parent, name="child")
    # Child first, as a container laid out before its own parent would do.
    child._allocate(Rect(1, 1, 6, 2))
    child._map()
    parent._allocate(Rect(0, 0, 20, 6))
    parent._map()
    assert stack.top() is child._panel


def test_a_widget_is_redrawn_when_its_window_is_replaced(root):
    widget = Frame(root, name="w")
    widget._allocate(Rect(0, 0, 6, 2))
    widget._map()
    redraws = []
    widget._redraw = lambda: redraws.append(widget._window)
    widget._allocate(Rect(0, 0, 10, 4))
    assert redraws, "a resize builds a new window and must repaint it"


def test_a_widget_is_redrawn_when_it_is_moved(root):
    widget = Frame(root, name="w")
    widget._allocate(Rect(0, 0, 6, 2))
    widget._map()
    redraws = []
    widget._redraw = lambda: redraws.append(1)
    widget._allocate(Rect(3, 2, 6, 2))
    assert redraws


def test_resizing_a_container_relays_out_its_children(root):
    """Propagation travels up; allocation has to travel back down."""
    from tkcurses._core.pack import PackLayout

    parent = Frame(root, name="parent")
    parent._layout_manager = PackLayout()
    child = Frame(parent, name="child")
    child._requested = Size(4, 1)
    child.pack(fill="both")
    root.update_layout()

    parent._allocate(Rect(0, 0, 30, 8))
    root.update_layout()
    assert child.winfo_width() == 30
