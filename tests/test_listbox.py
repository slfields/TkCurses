"""Tests for the Listbox widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Listbox, Misc, TclError
from tkcurses._core.events import MOD_SHIFT, KeyEvent, MouseEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def stack():
    return PanelStack(window_factory=stub_window, panel_factory=None)


@pytest.fixture
def root(stack):
    root = Misc()
    root.tk.panels = stack
    root._rect = Rect(0, 0, 40, 20)
    root._mapped = True
    return root


@pytest.fixture
def listbox(root):
    box = Listbox(root, name="lb", height=4, width=16)
    box._allocate(Rect(0, 0, 18, 6))
    box._map()
    box.insert("end", *[f"item {n}" for n in range(8)])
    return box


def press(widget, keysym, state=0):
    widget._handle(KeyEvent(keysym=keysym, char="", modifiers=state))


# ------------------------------------------------------------------ contents


def test_a_new_listbox_is_empty(root):
    assert Listbox(root, name="lb").size() == 0


def test_inserting_at_the_end(listbox):
    listbox.insert("end", "last")
    assert listbox.get("end") == ""
    assert listbox.size() == 9
    assert listbox.get(8) == "last"


def test_inserting_in_the_middle(listbox):
    listbox.insert(1, "wedged")
    assert listbox.get(1) == "wedged"
    assert listbox.size() == 9


def test_getting_a_range(listbox):
    assert listbox.get(1, 3) == ("item 1", "item 2", "item 3")


def test_deleting_one_item(listbox):
    listbox.delete(0)
    assert listbox.get(0) == "item 1"
    assert listbox.size() == 7


def test_deleting_a_range_is_inclusive(listbox):
    """Tk's listbox ranges include the last index, unlike an entry's."""
    listbox.delete(0, 2)
    assert listbox.size() == 5
    assert listbox.get(0) == "item 3"


def test_deleting_everything(listbox):
    listbox.delete(0, "end")
    assert listbox.size() == 0


# ------------------------------------------------------------------ indices


def test_end_is_the_count(listbox):
    assert listbox.index("end") == 8


def test_active_is_the_active_item(listbox):
    listbox.activate(3)
    assert listbox.index("active") == 3


def test_a_bad_index_is_refused(listbox):
    with pytest.raises(TclError, match="bad listbox index"):
        listbox.index("sideways")


# ---------------------------------------------------------------- selection


def test_nothing_is_selected_to_begin_with(listbox):
    assert listbox.curselection() == ()


def test_selecting_one_item(listbox):
    listbox.selection_set(2)
    assert listbox.curselection() == (2,)
    assert listbox.selection_includes(2)


def test_clearing_the_selection(listbox):
    listbox.selection_set(2)
    listbox.selection_clear(0, "end")
    assert listbox.curselection() == ()


def test_browse_mode_keeps_one_selection(listbox):
    listbox.selection_set(1)
    listbox.selection_set(3)
    assert listbox.curselection() == (3,)


def test_multiple_mode_keeps_several(listbox):
    listbox.configure(selectmode="multiple")
    listbox.selection_set(1)
    listbox.selection_set(3)
    assert listbox.curselection() == (1, 3)


def test_extended_mode_selects_a_range(listbox):
    listbox.configure(selectmode="extended")
    listbox.selection_set(1, 3)
    assert listbox.curselection() == (1, 2, 3)


def test_selecting_fires_the_virtual_event(listbox):
    seen = []
    listbox.bind("<<ListboxSelect>>", lambda event: seen.append(1))
    listbox.selection_set(1)
    assert seen == [1]


def test_the_selection_follows_deleted_items(listbox):
    listbox.configure(selectmode="multiple")
    listbox.selection_set(4)
    listbox.delete(0, 1)
    assert listbox.curselection() == (2,)


def test_deleting_a_selected_item_deselects_it(listbox):
    listbox.selection_set(2)
    listbox.delete(2)
    assert listbox.curselection() == ()


def test_inserting_moves_the_selection_along(listbox):
    listbox.selection_set(3)
    listbox.insert(0, "new")
    assert listbox.curselection() == (4,)


# ------------------------------------------------------------------ keyboard


def test_the_arrows_move_the_active_item(listbox):
    listbox.activate(0)
    press(listbox, "Down")
    assert listbox.index("active") == 1
    press(listbox, "Up")
    assert listbox.index("active") == 0


def test_browse_mode_drags_the_selection_with_the_arrows(listbox):
    listbox.activate(0)
    press(listbox, "Down")
    assert listbox.curselection() == (1,)


def test_single_mode_moves_without_selecting(listbox):
    """The active item and the selection are different things."""
    listbox.configure(selectmode="single")
    listbox.activate(0)
    press(listbox, "Down")
    assert listbox.index("active") == 1
    assert listbox.curselection() == ()


def test_space_selects_the_active_item(listbox):
    listbox.configure(selectmode="multiple")
    listbox.activate(2)
    press(listbox, "space")
    assert listbox.curselection() == (2,)


def test_space_toggles_in_multiple_mode(listbox):
    listbox.configure(selectmode="multiple")
    listbox.activate(2)
    press(listbox, "space")
    press(listbox, "space")
    assert listbox.curselection() == ()


def test_home_and_end_jump(listbox):
    listbox.activate(3)
    press(listbox, "Home")
    assert listbox.index("active") == 0
    press(listbox, "End")
    assert listbox.index("active") == 7


def test_an_unhandled_key_is_left_alone(listbox):
    assert listbox._handle(KeyEvent(keysym="F1", char="")) is False


def test_a_handled_key_stops_there(listbox):
    assert listbox._handle(KeyEvent(keysym="Down", char="")) is True


# --------------------------------------------------------------------- mouse


def test_clicking_selects_a_row(listbox):
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=2))
    assert listbox.curselection() == (1,)


def test_clicking_takes_the_focus(listbox):
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=1))
    assert listbox.focus_get() is listbox


def test_clicking_past_the_last_item_selects_nothing(listbox):
    listbox.delete(0, "end")
    listbox.insert("end", "only")
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=4))
    assert listbox.curselection() == ()


def test_shift_clicking_extends_in_extended_mode(listbox):
    listbox.configure(selectmode="extended")
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=1))
    listbox._handle(
        MouseEvent(button=1, state="pressed", x=2, y=3, modifiers=MOD_SHIFT)
    )
    assert listbox.curselection() == (0, 1, 2)


def test_the_wheel_scrolls_without_selecting(listbox):
    listbox.selection_set(0)
    listbox._handle(MouseEvent(button=5, state="pressed", x=2, y=2))
    assert listbox.yview() == 1
    assert listbox.curselection() == (0,)


# ------------------------------------------------------------------ scrolling


def test_a_short_list_does_not_scroll(listbox):
    listbox.delete(0, "end")
    listbox.insert("end", "one", "two")
    assert listbox.yview() == 0


def test_see_scrolls_an_item_into_view(listbox):
    listbox.see(7)
    assert listbox.yview() == 7 - 4 + 1


def test_see_only_moves_as_far_as_it_must(listbox):
    listbox.see(7)
    before = listbox.yview()
    listbox.see(5)
    assert listbox.yview() == before


def test_activating_scrolls_into_view(listbox):
    listbox.activate(7)
    assert listbox.yview() > 0


def test_the_view_is_clamped_to_the_list(listbox):
    listbox.yview(99)
    assert listbox.yview() == 8 - 4


def test_bbox_reports_a_visible_row(listbox):
    assert listbox.bbox(0) is not None


def test_bbox_of_a_scrolled_out_row_is_nothing(listbox):
    assert listbox.bbox(7) is None


def test_nearest_finds_the_row_under_a_screen_position(listbox):
    assert listbox.nearest(listbox.winfo_rooty() + 2) == 1


# -------------------------------------------------------------------- state


def test_a_disabled_listbox_ignores_keys(listbox):
    listbox.configure(state="disabled")
    listbox.activate(0)
    press(listbox, "Down")
    assert listbox.index("active") == 0


def test_a_disabled_listbox_ignores_clicks(listbox):
    listbox.configure(state="disabled")
    listbox._handle(MouseEvent(button=1, state="pressed", x=2, y=2))
    assert listbox.curselection() == ()


def test_a_listbox_asks_for_its_rows_and_columns(root):
    box = Listbox(root, name="lb", width=30, height=5)
    assert box.winfo_reqwidth() == 30 + 2
    assert box.winfo_reqheight() == 5 + 2
