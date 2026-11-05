# TkCurses - a tkinter-compatible API layer that renders to curses
# Copyright (C) 2026  Scott L. Fields
#
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for the Misc class and the Event object it delivers."""

from __future__ import annotations

import pytest

from tkcurses import Event, Misc, TclError
from tkcurses._core.colors import ColorDepth
from tkcurses._core.events import MOD_CTRL, KeyEvent, MouseEvent, ResizeEvent
from tkcurses._core.geometry import Rect, Size


class Frame(Misc):
    """A stand-in container, so widget class names read like real ones."""


class Button(Misc):
    """A stand-in leaf widget."""


@pytest.fixture
def root():
    """A root widget with its own application state."""
    return Misc()


@pytest.fixture
def tree(root):
    """A root with a frame holding two buttons."""
    frame = Frame(root, name="frame")
    return root, frame, Button(frame, name="ok"), Button(frame, name="cancel")


# ------------------------------------------------------------- construction


def test_the_root_is_named_for_itself(root):
    assert str(root) == "."
    assert root.winfo_name() == "."
    assert root.winfo_parent() == ""


def test_a_child_of_the_root_has_a_single_dot_path(root):
    child = Frame(root, name="frame")
    assert str(child) == ".frame"
    assert child.winfo_parent() == "."


def test_a_grandchild_path_joins_with_dots(tree):
    _, _, ok, _ = tree
    assert str(ok) == ".frame.ok"


def test_a_widget_registers_itself_with_its_parent(tree):
    root, frame, ok, cancel = tree
    assert root.winfo_children() == [frame]
    assert frame.winfo_children() == [ok, cancel]


def test_children_inherit_the_application_state(tree):
    root, frame, ok, _ = tree
    assert ok.tk is root.tk is frame.tk


def test_two_roots_do_not_share_state():
    first, second = Misc(), Misc()
    assert first.tk is not second.tk


def test_an_unnamed_widget_is_numbered_like_tkinter(root):
    assert str(Button(root)) == ".!button"
    assert str(Button(root)) == ".!button2"


def test_a_name_containing_a_dot_is_refused(root):
    with pytest.raises(ValueError):
        Frame(root, name="a.b")


def test_the_repr_names_the_class_and_the_path(tree):
    _, _, ok, _ = tree
    assert repr(ok) == "<Button object .frame.ok>"


# ------------------------------------------------------------------ binding


def test_a_binding_fires_on_a_generated_event(root):
    seen = []
    root.bind("<Key-a>", seen.append)
    root.event_generate("<Key-a>")
    assert len(seen) == 1
    assert seen[0].keysym == "a"


def test_a_binding_ignores_a_different_event(root):
    root.bind("<Key-a>", lambda event: pytest.fail("should not fire"))
    root.event_generate("<Key-b>")


def test_bind_with_no_callback_reports_what_is_bound(root):
    def handler(event):
        return None

    root.bind("<Key-a>", handler)
    assert root.bind("<Key-a>") == (handler,)


def test_bind_with_nothing_reports_the_bound_sequences(root):
    """A tuple, as tkinter's is - measured on Tk 9.0.2, ``('a',)``.

    This asserted a list until TkCurses-js9. Small, and the kind that breaks
    real code quietly: ``widget.bind() + ('x',)`` raises rather than going
    wrong somewhere later.
    """
    root.bind("<Key-a>", lambda event: None)
    assert root.bind() == ("<Key-a>",)


def test_rebinding_replaces_unless_add_is_given(root):
    calls = []
    root.bind("<Key-a>", lambda event: calls.append("first"))
    root.bind("<Key-a>", lambda event: calls.append("second"))
    root.event_generate("<Key-a>")
    assert calls == ["second"]


def test_add_keeps_the_earlier_callback(root):
    calls = []
    root.bind("<Key-a>", lambda event: calls.append("first"))
    root.bind("<Key-a>", lambda event: calls.append("second"), add="+")
    root.event_generate("<Key-a>")
    assert calls == ["first", "second"]


def test_unbind_removes_the_binding(root):
    root.bind("<Key-a>", lambda event: pytest.fail("should not fire"))
    root.unbind("<Key-a>")
    root.event_generate("<Key-a>")


def test_unbind_by_handle_removes_only_that_callback(root):
    calls = []
    first = root.bind("<Key-a>", lambda event: calls.append("first"))
    root.bind("<Key-a>", lambda event: calls.append("second"), add=True)
    root.unbind("<Key-a>", first)
    root.event_generate("<Key-a>")
    assert calls == ["second"]


def test_deletecommand_removes_a_binding_by_handle(root):
    handle = root.bind("<Key-a>", lambda event: pytest.fail("should not fire"))
    root.deletecommand(handle)
    root.event_generate("<Key-a>")


def test_a_class_binding_reaches_every_widget_of_that_class(tree):
    _, _, ok, cancel = tree
    calls = []
    ok.bind_class("Button", "<Key-a>", lambda event: calls.append(event.widget))
    ok.event_generate("<Key-a>")
    cancel.event_generate("<Key-a>")
    assert calls == [ok, cancel]


def test_a_class_binding_does_not_reach_another_class(tree):
    _, frame, ok, _ = tree
    ok.bind_class("Button", "<Key-a>", lambda event: pytest.fail("should not fire"))
    frame.event_generate("<Key-a>")


def test_an_all_binding_reaches_every_widget(tree):
    root, frame, ok, _ = tree
    calls = []
    root.bind_all("<Key-a>", lambda event: calls.append(event.widget))
    frame.event_generate("<Key-a>")
    ok.event_generate("<Key-a>")
    assert calls == [frame, ok]


def test_unbind_all_removes_the_application_binding(root):
    root.bind_all("<Key-a>", lambda event: pytest.fail("should not fire"))
    root.unbind_all("<Key-a>")
    root.event_generate("<Key-a>")


def test_unbind_class_removes_the_class_binding(tree):
    _, _, ok, _ = tree
    ok.bind_class("Button", "<Key-a>", lambda event: pytest.fail("should not fire"))
    ok.unbind_class("Button", "<Key-a>")
    ok.event_generate("<Key-a>")


# ----------------------------------------------------------------- bindtags


def test_the_default_tags_run_widget_then_class_then_toplevel_then_all(tree):
    _, _, ok, _ = tree
    assert ok.bindtags() == (".frame.ok", "Button", ".", "all")


def test_a_toplevel_does_not_list_itself_twice(root):
    assert root.bindtags() == (".", "Misc", "all")


def test_bindings_run_in_tag_order(tree):
    root, _, ok, _ = tree
    calls = []
    ok.bind("<Key-a>", lambda event: calls.append("widget"))
    ok.bind_class("Button", "<Key-a>", lambda event: calls.append("class"))
    root.bind_all("<Key-a>", lambda event: calls.append("all"))
    ok.event_generate("<Key-a>")
    assert calls == ["widget", "class", "all"]


def test_break_stops_the_later_tags(tree):
    root, _, ok, _ = tree
    ok.bind("<Key-a>", lambda event: "break")
    root.bind_all("<Key-a>", lambda event: pytest.fail("should not fire"))
    ok.event_generate("<Key-a>")


def test_reordering_tags_reorders_the_callbacks(tree):
    _, _, ok, _ = tree
    calls = []
    ok.bind("<Key-a>", lambda event: calls.append("widget"))
    ok.bind_class("Button", "<Key-a>", lambda event: calls.append("class"))
    ok.bindtags(["Button", str(ok)])
    ok.event_generate("<Key-a>")
    assert calls == ["class", "widget"]


def test_setting_tags_reports_them_back(root):
    assert root.bindtags(["a", "b"]) == ("a", "b")
    assert root.bindtags() == ("a", "b")


# ----------------------------------------------------------- virtual events


def test_a_physical_event_raises_its_virtual_event(root):
    calls = []
    root.event_add("<<Paste>>", "<Control-v>")
    root.bind("<<Paste>>", lambda event: calls.append("pasted"))
    root.event_generate("<Control-v>")
    assert calls == ["pasted"]


def test_a_virtual_event_can_be_generated_directly(root):
    calls = []
    root.bind("<<Paste>>", lambda event: calls.append("pasted"))
    root.event_generate("<<Paste>>")
    assert calls == ["pasted"]


def test_on_one_tag_the_physical_binding_beats_the_virtual_one(root):
    """Measured on Tk 9.0.2: one binding per tag, and a tie goes to the
    physical one. This used to run both. TkCurses-hkul."""
    calls = []
    root.event_add("<<Paste>>", "<Control-v>")
    root.bind("<Control-v>", lambda event: calls.append("physical"))
    root.bind("<<Paste>>", lambda event: calls.append("virtual"))
    root.event_generate("<Control-v>")
    assert calls == ["physical"]


@pytest.mark.parametrize(
    ("order", "rebound", "expected"),
    [
        (["<Shift-Key-Next>", "<Control-Key-Next>"], None, "<Control-Key-Next>"),
        (["<Control-Key-Next>", "<Shift-Key-Next>"], None, "<Shift-Key-Next>"),
        (
            ["<Shift-Key-Next>", "<Control-Key-Next>"],
            "<Shift-Key-Next>",
            "<Control-Key-Next>",
        ),
        (
            ["<Control-Key-Next>", "<Shift-Key-Next>"],
            "<Control-Key-Next>",
            "<Shift-Key-Next>",
        ),
    ],
)
def test_of_two_equal_bindings_the_one_registered_last_runs(
    root, order, rebound, expected
):
    """bind(n): "the most recently registered sequence is the winner" - and
    registered is when it was first bound, not bound again. Measured on Tk
    9.0.2 with Control-Shift-Next on one Frame. Both used to run.
    TkCurses-5co5."""
    calls = []
    for sequence in order:
        root.bind(sequence, lambda event, s=sequence: calls.append(s))
    if rebound:
        root.bind(rebound, lambda event, s=rebound: calls.append(s))
    root.event_generate("<Control-Shift-Key-Next>")
    assert calls == [expected]


@pytest.mark.parametrize(
    ("bound", "key", "expected"),
    [
        (["<Key>", "<<PrevLine>>"], "<Key-Up>", ["<<PrevLine>>"]),
        (
            ["<<PrevLine>>", "<<SelectPrevLine>>"],
            "<Shift-Key-Up>",
            ["<<SelectPrevLine>>"],
        ),
        (["<<PrevLine>>"], "<Shift-Key-Up>", ["<<PrevLine>>"]),
        (["<<PrevLine>>", "<<PrevPara>>"], "<Control-Key-Up>", ["<<PrevPara>>"]),
        (["<Up>", "<<SelectPrevLine>>"], "<Shift-Key-Up>", ["<<SelectPrevLine>>"]),
        (["<Shift-Up>", "<<PrevLine>>"], "<Shift-Key-Up>", ["<Shift-Up>"]),
    ],
)
def test_a_virtual_binding_ranks_as_the_key_that_raised_it(root, bound, key, expected):
    """Each measured on one Frame in Tk 9.0.2."""
    root.event_add("<<PrevLine>>", "<Up>")
    root.event_add("<<SelectPrevLine>>", "<Shift-Up>")
    root.event_add("<<PrevPara>>", "<Control-Up>")
    calls = []
    for sequence in bound:
        root.bind(sequence, lambda event, s=sequence: calls.append(s))
    root.event_generate(key)
    assert calls == expected


def test_a_tie_with_the_first_defined_virtual_still_goes_to_the_physical(root):
    """<<Copy>> is defined first, so the order cannot be what decides."""
    calls = []
    root.bind("<Control-Key-Insert>", lambda event: calls.append("physical"))
    root.bind("<<Copy>>", lambda event: calls.append("virtual"))
    root.event_generate("<Control-Key-Insert>")
    assert calls == ["physical"]


def test_a_virtual_ranks_as_its_most_particular_sequence_that_matched(root):
    """Measured on Tk 9.0.2: <<Mine>> on both Up and Shift-Up beats
    <<PrevLine>> for Shift-Up - it ranks as Shift-Up, not as Up."""
    root.event_add("<<PrevLine>>", "<Up>")
    root.event_add("<<Mine>>", "<Up>", "<Shift-Up>")
    calls = []
    root.bind("<<PrevLine>>", lambda event: calls.append("PrevLine"))
    root.bind("<<Mine>>", lambda event: calls.append("Mine"))
    root.event_generate("<Shift-Key-Up>")
    assert calls == ["Mine"]


def test_of_two_virtual_events_on_one_key_the_first_defined_runs(root):
    """Measured on Tk 9.0.2 in four orders of defining and binding."""
    root.event_add("<<Q>>", "<Key-F6>")
    root.event_add("<<P>>", "<Key-F6>")
    calls = []
    root.bind("<<P>>", lambda event: calls.append("P"))
    root.bind("<<Q>>", lambda event: calls.append("Q"))
    root.event_generate("<Key-F6>")
    assert calls == ["Q"]


def test_on_two_tags_the_physical_and_the_virtual_binding_both_run(root):
    from tkcurses import Frame

    frame = Frame(root)
    calls = []
    root.event_add("<<Paste>>", "<Control-v>")
    frame.bind("<Control-v>", lambda event: calls.append("widget"))
    frame.bind_class("Frame", "<<Paste>>", lambda event: calls.append("class"))
    frame.event_generate("<Control-v>")
    assert calls == ["widget", "class"]


def test_event_info_reports_a_virtual_events_sequences(root):
    root.event_add("<<Mine>>", "<Control-v>", "<Shift-Insert>")
    assert set(root.event_info("<<Mine>>")) == {
        "<Control-Key-v>",
        "<Shift-Key-Insert>",
    }


def test_event_info_with_no_name_lists_the_virtual_events(root):
    root.event_add("<<Mine>>", "<Control-v>")
    assert "<<Mine>>" in root.event_info()


def test_the_clipboard_virtual_events_are_defined_from_the_start(root):
    """Tk defines these at startup; so does this, less the keys measured not
    to reach a program in a terminal - Control-c above all, which is the
    close gesture and copies only when there is a selection. TkCurses-lw2."""
    assert set(root.event_info()) >= {
        "<<Copy>>",
        "<<Cut>>",
        "<<Paste>>",
        "<<PasteSelection>>",
        "<<SelectAll>>",
        "<<Clear>>",
    }
    assert set(root.event_info("<<Cut>>")) == {
        "<Control-Key-x>",
        "<Control-Key-w>",
        "<Shift-Key-Delete>",
    }
    assert set(root.event_info("<<Paste>>")) == {
        "<Control-Key-v>",
        "<Control-Key-y>",
        "<Shift-Key-Insert>",
    }
    assert "<Control-Key-c>" not in root.event_info("<<Copy>>")


def test_event_delete_stops_the_virtual_event(root):
    root.event_add("<<Paste>>", "<Control-v>")
    root.event_delete("<<Paste>>", "<Control-v>")
    root.bind("<<Paste>>", lambda event: pytest.fail("should not fire"))
    root.event_generate("<Control-v>")


# ------------------------------------------------------------------- events


def test_a_generated_event_carries_the_fields_it_was_given(root):
    seen = []
    root.bind("<Button-1>", seen.append)
    root.event_generate("<Button-1>", x=4, y=7)
    assert (seen[0].x, seen[0].y, seen[0].num) == (4, 7, 1)


def test_an_unknown_event_field_is_refused(root):
    with pytest.raises(TypeError):
        root.event_generate("<Key-a>", nonsense=1)


def test_a_key_event_becomes_a_tkinter_event(root):
    seen = []
    root.bind("<Control-Key-a>", seen.append)
    root._handle(KeyEvent(keycode=1, keysym="a", char="\x01", modifiers=MOD_CTRL))
    event = seen[0]
    # Tk's Control bit, 4, as tkinter reports it - not ours. TkCurses-vnmk.
    assert (event.keysym, event.keycode, event.state) == ("a", 1, 4)
    assert event.widget is root


def test_a_mouse_event_reports_a_position_relative_to_the_widget(tree):
    _, frame, ok, _ = tree
    frame._rect = Rect(2, 1, 20, 5)
    ok._rect = Rect(3, 1, 6, 1)
    seen = []
    ok.bind("<Button-1>", seen.append)
    ok._handle(MouseEvent(x=8, y=3, button=1, state="pressed"))
    assert (seen[0].x, seen[0].y) == (3, 1)
    assert (seen[0].x_root, seen[0].y_root) == (8, 3)


def test_the_wheel_becomes_a_delta(root):
    seen = []
    root.bind("<Button-4>", seen.append)
    root._handle(MouseEvent(x=0, y=0, button=4, state="pressed"))
    assert seen[0].delta == 1


def test_a_resize_becomes_a_configure_event(root):
    seen = []
    root.bind("<Configure>", seen.append)
    root._handle(ResizeEvent(width=100, height=40))
    assert (seen[0].width, seen[0].height) == (100, 40)


def test_handling_a_mouse_event_updates_the_pointer(root):
    root._handle(MouseEvent(x=11, y=5, button=1, state="motion"))
    assert root.winfo_pointerxy() == (11, 5)


def test_handle_reports_whether_a_callback_broke(root):
    root.bind("<Key-a>", lambda event: "break")
    assert root._handle(KeyEvent(keysym="a", char="a")) is True


def test_a_destroyed_widget_receives_nothing(root):
    child = Button(root, name="ok")
    child.bind("<Key-a>", lambda event: pytest.fail("should not fire"))
    child.destroy()
    assert child._handle(KeyEvent(keysym="a", char="a")) is False


def test_the_event_repr_names_the_type_and_the_fields():
    assert repr(Event(type="Key", keysym="a")) == "<Key event keysym='a'>"


# -------------------------------------------------------------------- focus


def test_focus_set_makes_a_widget_the_focused_one(tree):
    _, _, ok, _ = tree
    ok.focus_set()
    assert ok.focus_get() is ok
    assert ok.focus_displayof() is ok


def test_focus_moves_generate_focus_events(tree):
    _, _, ok, cancel = tree
    calls = []
    ok.bind("<FocusOut>", lambda event: calls.append("out"))
    cancel.bind("<FocusIn>", lambda event: calls.append("in"))
    ok.focus_set()
    cancel.focus_set()
    assert calls == ["out", "in"]


def test_focusing_the_already_focused_widget_changes_nothing(root):
    calls = []
    root.bind("<FocusIn>", lambda event: calls.append("in"))
    root.focus_set()
    root.focus_set()
    assert calls == ["in"]


def test_focus_force_focuses(tree):
    _, _, ok, _ = tree
    ok.focus_force()
    assert ok.focus_get() is ok


def test_nothing_is_focused_to_begin_with(root):
    assert root.focus_get() is None


def test_focus_lastfor_reports_the_toplevel_until_something_is_focused(tree):
    root, _, ok, _ = tree
    assert ok.focus_lastfor() is root


def test_focus_lastfor_remembers_the_last_focused_widget(tree):
    _, frame, ok, _ = tree
    ok.focus_set()
    assert frame.focus_lastfor() is ok


def test_focus_follows_mouse_is_recorded(root):
    root.tk_focusFollowsMouse()
    assert root.tk.focus_follows_mouse is True


def test_tab_order_follows_creation_order(tree):
    _, frame, ok, cancel = tree
    assert frame.tk_focusNext() is ok
    assert ok.tk_focusNext() is cancel


def test_tab_order_wraps_around(tree):
    _, frame, _, cancel = tree
    assert cancel.tk_focusNext() is frame


def test_tab_order_runs_backwards_too(tree):
    _, frame, ok, cancel = tree
    assert cancel.tk_focusPrev() is ok
    assert frame.tk_focusPrev() is cancel


def test_a_widget_that_refuses_focus_is_skipped(tree):
    _, frame, ok, cancel = tree
    ok._takefocus = False
    assert frame.tk_focusNext() is cancel


def test_focus_traversal_reports_nothing_when_no_widget_takes_focus(root):
    assert root.tk_focusNext() is None


# ----------------------------------------------------------------- timers


def test_after_schedules_a_callback(root):
    calls = []
    root.after(0, calls.append, "ran")
    root.update()
    assert calls == ["ran"]


def test_a_scheduled_callback_can_be_cancelled(root):
    handle = root.after(0, lambda: pytest.fail("should not run"))
    root.after_cancel(handle)
    root.update()


def test_cancelling_none_is_refused(root):
    with pytest.raises(ValueError):
        root.after_cancel(None)


def test_after_idle_runs_on_update_idletasks(root):
    calls = []
    root.after_idle(calls.append, "idle")
    root.update_idletasks()
    assert calls == ["idle"]


def test_after_info_describes_a_scheduled_callback(root):
    def handler():
        return None

    handle = root.after(10, handler)
    assert root.after_info(handle) == (handler, (), "timer")


def test_after_info_with_no_handle_lists_what_is_scheduled(root):
    handle = root.after(10, lambda: None)
    assert root.after_info() == (handle,)


def test_timers_are_shared_across_the_widget_tree(tree):
    root, _, ok, _ = tree
    calls = []
    ok.after(0, calls.append, "ran")
    root.update()
    assert calls == ["ran"]


def test_a_bare_delay_returns_no_handle(root):
    assert root.after(0) is None


# -------------------------------------------------------------- event loop


def test_quit_sets_the_flag_the_loop_watches(root):
    root.quit()
    assert root.tk.quit_requested is True


def test_a_tree_with_no_tk_root_has_no_main_loop(root):
    with pytest.raises(TclError):
        root.mainloop()


# --------------------------------------------------------------- clipboard


def test_an_empty_clipboard_raises(root):
    with pytest.raises(TclError):
        root.clipboard_get()


def test_appending_puts_text_on_the_clipboard(root):
    root.clipboard_clear()
    root.clipboard_append("copied")
    assert root.clipboard_get() == "copied"


def test_the_clipboard_is_shared_across_the_tree(tree):
    root, _, ok, _ = tree
    ok.clipboard_append("copied")
    assert root.clipboard_get() == "copied"


def test_clearing_empties_the_clipboard(root):
    root.clipboard_append("copied")
    root.clipboard_clear()
    with pytest.raises(TclError):
        root.clipboard_get()


def test_the_selection_is_separate_from_the_clipboard(root):
    root.clipboard_append("copied")
    root.selection_own()
    root.selection_handle(lambda offset, length: "selected")
    assert root.selection_get() == "selected"
    assert root.clipboard_get() == "copied"


def test_selection_own_get_reports_the_owner(tree):
    _, _, ok, _ = tree
    ok.selection_own()
    assert ok.selection_own_get() is ok


def test_selection_own_get_raises_when_unowned(root):
    with pytest.raises(TclError):
        root.selection_own_get()


def test_destroying_the_owner_releases_the_selection(tree):
    root, _, ok, _ = tree
    ok.selection_own()
    ok.destroy()
    with pytest.raises(TclError):
        root.selection_own_get()


# -------------------------------------------------------------------- grab


def test_no_widget_holds_a_grab_to_begin_with(root):
    assert root.grab_current() is None
    assert root.grab_status() is None


def test_grab_set_takes_a_local_grab(tree):
    _, _, ok, _ = tree
    ok.grab_set()
    assert ok.grab_current() is ok
    assert ok.grab_status() == "local"


def test_grab_set_global_is_reported_as_global(tree):
    _, _, ok, _ = tree
    ok.grab_set_global()
    assert ok.grab_status() == "global"


def test_grab_status_is_none_for_a_widget_without_the_grab(tree):
    _, frame, ok, _ = tree
    ok.grab_set()
    assert frame.grab_status() is None
    assert frame.grab_current() is ok


def test_grab_release_clears_the_grab(tree):
    _, _, ok, _ = tree
    ok.grab_set()
    ok.grab_release()
    assert ok.grab_current() is None


def test_releasing_a_grab_held_by_another_widget_does_nothing(tree):
    _, frame, ok, _ = tree
    ok.grab_set()
    frame.grab_release()
    assert ok.grab_current() is ok


def test_destroying_the_grab_holder_releases_it(tree):
    root, _, ok, _ = tree
    ok.grab_set()
    ok.destroy()
    assert root.grab_current() is None


# ---------------------------------------------------------------- stacking


def test_raising_moves_a_widget_to_the_end_of_its_siblings(tree):
    _, frame, ok, cancel = tree
    ok.tkraise()
    assert frame.winfo_children() == [cancel, ok]


def test_lowering_moves_a_widget_to_the_front(tree):
    _, frame, ok, cancel = tree
    cancel.lower()
    assert frame.winfo_children() == [cancel, ok]


def test_raising_above_a_named_sibling(tree):
    _, frame, ok, cancel = tree
    third = Button(frame, name="apply")
    ok.tkraise(cancel)
    assert frame.winfo_children() == [cancel, ok, third]


def test_lowering_below_a_named_sibling(tree):
    _, frame, ok, cancel = tree
    third = Button(frame, name="apply")
    third.lower(ok)
    assert frame.winfo_children() == [third, ok, cancel]


def test_lift_is_an_alias_for_tkraise(tree):
    _, frame, ok, cancel = tree
    ok.lift()
    assert frame.winfo_children() == [cancel, ok]


def test_raising_the_root_does_nothing(root):
    root.tkraise()
    assert root.winfo_children() == []


# ------------------------------------------------------------------- winfo


def test_winfo_class_is_the_python_class_name(tree):
    _, frame, ok, _ = tree
    assert frame.winfo_class() == "Frame"
    assert ok.winfo_class() == "Button"


def test_winfo_exists_until_destroyed(tree):
    _, _, ok, _ = tree
    assert ok.winfo_exists()
    ok.destroy()
    assert not ok.winfo_exists()


def test_winfo_id_is_stable_and_unique(tree):
    _, _, ok, cancel = tree
    assert ok.winfo_id() == ok.winfo_id()
    assert ok.winfo_id() != cancel.winfo_id()


def test_winfo_geometry_reports_cells(tree):
    _, _, ok, _ = tree
    ok._rect = Rect(3, 1, 10, 1)
    assert ok.winfo_geometry() == "10x1+3+1"
    assert (ok.winfo_x(), ok.winfo_y()) == (3, 1)
    assert (ok.winfo_width(), ok.winfo_height()) == (10, 1)


def test_requested_size_is_reported_separately(tree):
    _, _, ok, _ = tree
    ok._requested = Size(12, 3)
    assert (ok.winfo_reqwidth(), ok.winfo_reqheight()) == (12, 3)


def test_root_coordinates_accumulate_through_ancestors(tree):
    _, frame, ok, _ = tree
    frame._rect = Rect(2, 1, 20, 5)
    ok._rect = Rect(3, 2, 6, 1)
    assert (ok.winfo_rootx(), ok.winfo_rooty()) == (5, 3)


def test_a_widget_is_unmapped_until_a_manager_places_it(tree):
    _, _, ok, _ = tree
    assert not ok.winfo_ismapped()
    assert ok.winfo_manager() == ""


def test_viewability_requires_every_ancestor_to_be_mapped(tree):
    _, frame, ok, _ = tree
    ok._mapped = True
    assert not ok.winfo_viewable()
    frame._mapped = True
    assert ok.winfo_viewable()


def test_winfo_toplevel_is_the_root_for_an_ordinary_widget(tree):
    root, _, ok, _ = tree
    assert ok.winfo_toplevel() is root


def test_winfo_containing_finds_the_widget_under_a_cell(tree):
    root, frame, ok, _ = tree
    frame._rect, frame._mapped = Rect(0, 0, 20, 5), True
    ok._rect, ok._mapped = Rect(2, 1, 6, 1), True
    assert root.winfo_containing(3, 1) is ok
    assert root.winfo_containing(15, 4) is frame


def test_winfo_containing_reports_nothing_outside_every_widget(tree):
    root, frame, _, _ = tree
    frame._rect, frame._mapped = Rect(0, 0, 5, 2), True
    assert root.winfo_containing(50, 50) is None


def test_winfo_containing_ignores_unmapped_widgets(tree):
    root, frame, _, _ = tree
    frame._rect = Rect(0, 0, 20, 5)
    assert root.winfo_containing(1, 1) is None


def test_the_screen_size_is_reported_in_cells(root):
    assert root.winfo_screenwidth() > 0
    assert root.winfo_screenheight() > 0
    assert root.winfo_vrootwidth() == root.winfo_screenwidth()
    assert root.winfo_vrootheight() == root.winfo_screenheight()


def test_colour_depth_is_derived_from_the_colour_count(root):
    assert root.winfo_cells() == 8
    assert root.winfo_depth() == 3
    assert root.winfo_screendepth() == root.winfo_depth()


def test_winfo_rgb_reports_sixteen_bit_channels(root):
    assert root.winfo_rgb("#ff0000") == (65535, 0, 0)


def test_winfo_rgb_of_a_name_reports_what_the_terminal_shows(root):
    red = root.winfo_rgb("red")
    assert red[0] > red[1] and red[0] > red[2]


def test_the_colour_depth_is_the_eight_before_there_is_a_screen(root):
    """Nothing has been asked yet, so the answer is what colour resolution
    assumes when it has nothing to go on."""
    assert root.winfo_colordepth() is ColorDepth.BASIC


def test_a_bare_number_is_already_in_cells(root):
    assert root.winfo_pixels(5) == 5
    assert root.winfo_fpixels("2.5") == 2.5


def test_a_screen_distance_converts_to_cells(root):
    assert root.winfo_pixels("1i") == 10
    assert root.winfo_pixels("2i") == 20


def test_a_bad_screen_distance_is_refused(root):
    with pytest.raises(TclError):
        root.winfo_pixels("wide")


def test_the_pointer_position_starts_at_the_origin(root):
    assert root.winfo_pointerxy() == (0, 0)
    assert root.winfo_pointerx() == 0
    assert root.winfo_pointery() == 0


# ----------------------------------------------------------- configuration


def test_configure_sets_and_reports_options(root):
    root.configure(text="hello")
    assert root.cget("text") == "hello"
    assert root.configure() == {"text": "hello"}


def test_config_is_an_alias(root):
    root.config(text="hello")
    assert root["text"] == "hello"


def test_options_can_be_set_by_item_assignment(root):
    root["text"] = "hello"
    assert root.cget("text") == "hello"


def test_a_dictionary_of_options_is_accepted(root):
    root.configure({"text": "hello"}, width=4)
    assert root.keys() == ["text", "width"]


def test_an_unknown_option_is_refused(root):
    with pytest.raises(TclError):
        root.cget("nonsense")


# -------------------------------------------------------- option database


def test_an_option_default_reaches_a_matching_widget(tree):
    root, _, ok, _ = tree
    root.option_add("*Button.background", "blue")
    assert ok.option_get("background", "Button") == "blue"


def test_an_option_default_is_shared_across_the_tree(tree):
    _, frame, ok, _ = tree
    frame.option_add("*background", "blue")
    assert ok.option_get("background", "Button") == "blue"


def test_clearing_removes_option_defaults(root):
    root.option_add("*background", "blue")
    root.option_clear()
    assert root.option_get("background", "Misc") is None


def test_reading_a_tcl_resource_file_is_refused(root):
    with pytest.raises(TclError):
        root.option_readfile("x.rc")


# ----------------------------------------------------------------- utility


def test_nametowidget_resolves_an_absolute_path(tree):
    root, _, ok, _ = tree
    assert root.nametowidget(".frame.ok") is ok


def test_nametowidget_resolves_a_relative_path(tree):
    _, frame, ok, _ = tree
    assert frame.nametowidget("ok") is ok


def test_nametowidget_accepts_a_widget(tree):
    root, _, ok, _ = tree
    assert root.nametowidget(ok) is ok


def test_nametowidget_raises_for_an_unknown_path(root):
    with pytest.raises(KeyError):
        root.nametowidget(".nothing")


def test_variables_are_shared_across_the_tree(tree):
    root, _, ok, _ = tree
    ok.setvar("PY_VAR1", "value")
    assert root.getvar("PY_VAR1") == "value"


def test_an_unset_variable_reads_as_none(root):
    assert root.getvar("PY_VAR9") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [("42", 42), ("0x10", 16), ("0b101", 5), (7, 7)],
)
def test_getint_parses_tcl_integer_forms(root, text, expected):
    assert root.getint(text) == expected


def test_getdouble_parses_a_float(root):
    assert root.getdouble("2.5") == 2.5


@pytest.mark.parametrize("text", ["1", "yes", "true", "on", "TRUE", "Y", True, 3])
def test_getboolean_accepts_every_true_spelling(root, text):
    assert root.getboolean(text) is True


@pytest.mark.parametrize("text", ["0", "no", "false", "off", "FALSE", "N", False, 0])
def test_getboolean_accepts_every_false_spelling(root, text):
    assert root.getboolean(text) is False


def test_getboolean_refuses_anything_else(root):
    with pytest.raises(TclError):
        root.getboolean("maybe")


def test_the_bell_does_not_raise_without_a_screen(root):
    root.bell()


# ------------------------------------------------------------------ destroy


def test_destroying_removes_a_widget_from_its_parent(tree):
    _, frame, ok, cancel = tree
    ok.destroy()
    assert frame.winfo_children() == [cancel]


def test_destroying_takes_the_children_with_it(tree):
    root, frame, ok, _ = tree
    frame.destroy()
    assert root.winfo_children() == []
    assert not ok.winfo_exists()


def test_destroy_generates_a_destroy_event(tree):
    _, _, ok, _ = tree
    calls = []
    ok.bind("<Destroy>", lambda event: calls.append("destroyed"))
    ok.destroy()
    assert calls == ["destroyed"]


def test_children_are_destroyed_before_their_parent(tree):
    _, frame, ok, _cancel = tree
    calls = []
    frame.bind("<Destroy>", lambda event: calls.append("frame"))
    ok.bind("<Destroy>", lambda event: calls.append("ok"))
    frame.destroy()
    assert calls == ["ok", "frame"]


def test_destroying_twice_is_harmless(tree):
    _, _, ok, _ = tree
    ok.destroy()
    ok.destroy()


def test_a_destroyed_widget_leaves_the_registry(tree):
    root, _, ok, _ = tree
    ok.destroy()
    with pytest.raises(KeyError):
        root.nametowidget(".frame.ok")


def test_destroying_the_focused_widget_clears_the_focus(tree):
    root, _, ok, _ = tree
    ok.focus_set()
    ok.destroy()
    assert root.focus_get() is None


def test_a_destroyed_widgets_bindings_are_discarded(tree):
    root, _, ok, _ = tree
    ok.bind("<Key-a>", lambda event: None)
    ok.destroy()
    assert root.tk.bindings.sequences(".frame.ok") == ()
