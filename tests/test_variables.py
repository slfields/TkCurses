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

"""Tests for the Variable classes and the wait operations."""

from __future__ import annotations

import pytest

import tkcurses
from tkcurses import (
    BooleanVar,
    DoubleVar,
    IntVar,
    Misc,
    StringVar,
    TclError,
    Variable,
    Widget,
)


@pytest.fixture
def root():
    return Misc()


@pytest.fixture(autouse=True)
def _no_leaked_default_root():
    previous = tkcurses._default_root
    yield
    tkcurses._default_root = previous


# ------------------------------------------------------------------ basics


def test_a_variable_starts_at_its_class_default(root):
    assert StringVar(root).get() == ""
    assert IntVar(root).get() == 0
    assert DoubleVar(root).get() == 0.0
    assert BooleanVar(root).get() is False


def test_the_base_variable_stores_a_value_unconverted(root):
    marker = object()
    var = Variable(root)
    var.set(marker)
    assert var.get() is marker


def test_the_base_variable_defaults_to_an_empty_string(root):
    assert Variable(root).get() == ""


def test_an_initial_value_is_honoured(root):
    assert StringVar(root, value="hello").get() == "hello"
    assert IntVar(root, value=42).get() == 42


def test_a_value_round_trips(root):
    var = StringVar(root)
    var.set("written")
    assert var.get() == "written"


def test_initialize_is_set(root):
    var = StringVar(root)
    var.initialize("started")
    assert var.get() == "started"


def test_a_variable_is_named_automatically(root):
    assert str(StringVar(root)).startswith("PY_VAR")


def test_an_explicit_name_is_used(root):
    assert str(StringVar(root, name="chosen")) == "chosen"


def test_two_variables_sharing_a_name_share_a_value(root):
    first = StringVar(root, name="shared", value="one")
    second = StringVar(root, name="shared")
    assert second.get() == "one"
    second.set("two")
    assert first.get() == "two"


def test_variables_are_shared_across_the_widget_tree(root):
    child = Widget(root, name="child")
    var = StringVar(root, name="v", value="set on the root")
    seen_from_child = StringVar(child, name="v")
    assert seen_from_child.get() == "set on the root"
    assert var.get() == "set on the root"


def test_dropping_a_variable_unsets_the_name_for_everyone(root):
    """tkinter's behaviour, and a trap: a temporary sharing a name clears it.

    Variable.__del__ unsets the name, whichever instance is collected, so a
    throwaway StringVar(root, name="v") takes the value with it. Recorded
    because it is surprising, not because it is wanted.
    """
    var = StringVar(root, name="v", value="held")
    StringVar(root, name="v")  # collected immediately
    assert var.get() == ""


def test_two_applications_keep_separate_variables():
    first, second = Misc(), Misc()
    StringVar(first, name="v", value="first")
    assert StringVar(second, name="v").get() == ""


def test_a_variable_reaches_getvar_and_setvar(root):
    var = StringVar(root, name="v", value="through the variable")
    assert root.getvar("v") == "through the variable"
    root.setvar("v", "through the widget")
    assert var.get() == "through the widget"


def test_a_variable_needs_a_root():
    tkcurses._default_root = None
    with pytest.raises(TclError, match="create a variable"):
        StringVar()


def test_a_variable_uses_the_default_root(root):
    tkcurses._default_root = root
    assert StringVar(value="x").get() == "x"


# ---------------------------------------------------------------- equality


def test_variables_of_the_same_class_and_name_are_equal(root):
    assert StringVar(root, name="v") == StringVar(root, name="v")


def test_different_names_are_different_variables(root):
    assert StringVar(root, name="a") != StringVar(root, name="b")


def test_different_classes_are_different_variables(root):
    assert StringVar(root, name="v") != IntVar(root, name="v")


def test_a_variable_is_not_equal_to_its_value(root):
    assert StringVar(root, value="x") != "x"


def test_equal_variables_hash_together(root):
    assert len({StringVar(root, name="v"), StringVar(root, name="v")}) == 1


def test_the_repr_shows_the_name_and_value(root):
    assert "v=" in repr(StringVar(root, name="v", value="shown"))


# -------------------------------------------------------------- conversion


@pytest.mark.parametrize(("stored", "expected"), [("7", 7), (7, 7), ("0x10", 16)])
def test_intvar_parses_its_value(root, stored, expected):
    var = IntVar(root)
    var.set(stored)
    assert var.get() == expected


def test_intvar_refuses_a_value_that_is_not_a_number(root):
    var = IntVar(root)
    var.set("seven")
    with pytest.raises(TclError, match="integer"):
        var.get()


@pytest.mark.parametrize(("stored", "expected"), [("2.5", 2.5), (3, 3.0)])
def test_doublevar_parses_its_value(root, stored, expected):
    var = DoubleVar(root)
    var.set(stored)
    assert var.get() == expected


def test_doublevar_refuses_a_value_that_is_not_a_number(root):
    var = DoubleVar(root)
    var.set("two and a half")
    with pytest.raises(TclError, match="floating-point"):
        var.get()


@pytest.mark.parametrize("stored", ["1", "yes", "true", "on", True, 3])
def test_booleanvar_accepts_every_true_spelling(root, stored):
    var = BooleanVar(root)
    var.set(stored)
    assert var.get() is True


@pytest.mark.parametrize("stored", ["0", "no", "false", "off", False, 0])
def test_booleanvar_accepts_every_false_spelling(root, stored):
    var = BooleanVar(root)
    var.set(stored)
    assert var.get() is False


def test_booleanvar_refuses_anything_else(root):
    var = BooleanVar(root)
    var.set("maybe")
    with pytest.raises(TclError, match="boolean"):
        var.get()


def test_stringvar_renders_whatever_it_holds(root):
    var = StringVar(root)
    var.set(42)
    assert var.get() == "42"


# ------------------------------------------------------------------ traces


def test_a_write_trace_fires_on_set(root):
    var = StringVar(root, name="v")
    seen = []
    var.trace_add("write", lambda *args: seen.append(args))
    var.set("written")
    assert seen == [("v", "", "write")]


def test_a_read_trace_fires_on_get(root):
    var = StringVar(root)
    seen = []
    var.trace_add("read", lambda *args: seen.append(args[2]))
    var.get()
    assert seen == ["read"]


def test_a_write_trace_does_not_fire_on_read(root):
    var = StringVar(root)
    var.trace_add("write", lambda *args: pytest.fail("should not fire"))
    var.get()


def test_several_modes_can_share_a_callback(root):
    var = StringVar(root)
    seen = []
    var.trace_add(["read", "write"], lambda *args: seen.append(args[2]))
    var.set("x")
    var.get()
    assert seen == ["write", "read"]


def test_traces_fire_in_the_order_they_were_added(root):
    var = StringVar(root)
    seen = []
    var.trace_add("write", lambda *args: seen.append("first"))
    var.trace_add("write", lambda *args: seen.append("second"))
    var.set("x")
    assert seen == ["first", "second"]


def test_a_trace_can_be_removed(root):
    var = StringVar(root)
    handle = var.trace_add("write", lambda *args: pytest.fail("should not fire"))
    var.trace_remove("write", handle)
    var.set("x")


def test_trace_info_lists_the_traces(root):
    var = StringVar(root)
    handle = var.trace_add("write", lambda *args: None)
    assert var.trace_info() == [(("write",), handle)]


def test_removing_an_unknown_trace_is_harmless(root):
    StringVar(root).trace_remove("write", "nonexistent")


def test_an_unknown_trace_mode_is_refused(root):
    with pytest.raises(TclError, match="operation"):
        StringVar(root).trace_add("sideways", lambda *args: None)


def test_a_trace_may_remove_itself_while_firing(root):
    var = StringVar(root)
    handles = []

    def remove_self(*args):
        var.trace_remove("write", handles[0])

    handles.append(var.trace_add("write", remove_self))
    var.set("x")
    assert var.trace_info() == []


def test_a_trace_sees_the_new_value(root):
    var = StringVar(root)
    seen = []
    var.trace_add("write", lambda *args: seen.append(var.get()))
    var.set("new")
    assert seen == ["new"]


# ----------------------------------------------------------- legacy traces


def test_a_legacy_trace_fires(root):
    var = StringVar(root)
    seen = []
    var.trace_variable("w", lambda *args: seen.append(args[2]))
    var.set("x")
    assert seen == ["write"]


def test_trace_is_the_legacy_trace_by_another_name(root):
    """tkinter's ``trace = trace_variable``; pre-3.6 programs still call it."""
    assert Variable.trace is Variable.trace_variable
    var = StringVar(root)
    seen = []
    var.trace("w", lambda *args: seen.append(args[2]))
    var.set("x")
    assert seen == ["write"]


def test_a_legacy_trace_can_be_removed(root):
    var = StringVar(root)
    handle = var.trace_variable("w", lambda *args: pytest.fail("should not fire"))
    var.trace_vdelete("w", handle)
    var.set("x")


def test_legacy_info_reports_single_letter_modes(root):
    var = StringVar(root)
    handle = var.trace_variable("w", lambda *args: None)
    assert var.trace_vinfo() == [("w", handle)]


def test_an_unknown_legacy_mode_is_refused(root):
    with pytest.raises(TclError, match="operation"):
        StringVar(root).trace_variable("z", lambda *args: None)


# ------------------------------------------------------------------- waits


def test_wait_window_returns_at_once_for_a_destroyed_window(root):
    child = Widget(root, name="child")
    child.destroy()
    root.wait_window(child)


def test_wait_visibility_returns_at_once_for_a_viewable_widget(root):
    child = Widget(root, name="child")
    child._mapped = True
    root.wait_visibility(child)


def test_a_wait_gives_up_when_the_root_is_destroyed(root):
    """Without this the loop would spin on a tree that no longer exists."""
    child = Widget(root, name="child")
    root.destroy()
    root.wait_window(child)


def test_the_wait_helper_stops_as_soon_as_the_condition_holds(root):
    calls = []
    root._wait_until(lambda: calls.append(1) or len(calls) >= 3)
    assert len(calls) == 3
