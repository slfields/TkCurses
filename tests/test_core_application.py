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

"""Tests for tkcurses._core.application and tkcurses._core.clipboard."""

from __future__ import annotations

import pytest

from tkcurses._core.application import Application, OptionDatabase, WidgetRegistry
from tkcurses._core.clipboard import CLIPBOARD, PRIMARY, Selections
from tkcurses._core.errors import TclError, TkCursesError

# -------------------------------------------------------------- application


def test_each_application_has_its_own_state():
    first, second = Application(), Application()
    first.variables["x"] = 1
    assert second.variables == {}
    assert first.bindings is not second.bindings
    assert first.timers is not second.timers


def test_automatic_names_follow_tkinter_numbering():
    app = Application()
    assert app.next_name("Button") == "!button"
    assert app.next_name("Button") == "!button2"
    assert app.next_name("Label") == "!label"


def test_an_application_starts_with_nothing_focused_or_grabbed():
    app = Application()
    assert app.focus is None
    assert app.grab is None
    assert app.quit_requested is False


# ---------------------------------------------------------------- registry


def test_the_registry_finds_a_widget_by_path():
    registry = WidgetRegistry()
    widget = object()
    registry.add(".frame", widget)
    assert registry.get(".frame") is widget
    assert ".frame" in registry
    assert len(registry) == 1


def test_removing_an_unknown_path_is_not_an_error():
    registry = WidgetRegistry()
    registry.remove(".missing")
    assert registry.get(".missing") is None


def test_the_registry_iterates_over_paths():
    registry = WidgetRegistry()
    registry.add(".a", object())
    registry.add(".b", object())
    assert list(registry) == [".a", ".b"]


# ----------------------------------------------------------------- options


@pytest.fixture
def options():
    return OptionDatabase()


def test_a_wildcard_pattern_applies_to_every_widget(options):
    options.add("*background", "blue")
    assert options.get(".frame.ok", "Button", "background") == "blue"


def test_a_class_pattern_applies_only_to_that_class(options):
    options.add("*Button.background", "blue")
    assert options.get(".ok", "Button", "background") == "blue"
    assert options.get(".title", "Label", "background") is None


def test_a_path_pattern_applies_only_to_that_widget(options):
    options.add(".dialog.ok.background", "blue")
    assert options.get(".dialog.ok", "Button", "background") == "blue"
    assert options.get(".dialog.cancel", "Button", "background") is None


def test_an_unmatched_option_reports_nothing(options):
    options.add("*Button.background", "blue")
    assert options.get(".ok", "Button", "foreground") is None


def test_a_higher_priority_wins(options):
    options.add("*background", "blue", "widgetDefault")
    options.add("*background", "red", "interactive")
    assert options.get(".ok", "Button", "background") == "red"


def test_priority_order_does_not_depend_on_insertion_order(options):
    options.add("*background", "red", "interactive")
    options.add("*background", "blue", "widgetDefault")
    assert options.get(".ok", "Button", "background") == "red"


def test_the_later_of_two_equal_priorities_wins(options):
    options.add("*background", "blue")
    options.add("*background", "red")
    assert options.get(".ok", "Button", "background") == "red"


def test_a_numeric_priority_is_accepted(options):
    options.add("*background", "blue", 10)
    options.add("*background", "red", 90)
    assert options.get(".ok", "Button", "background") == "red"


def test_an_unknown_priority_name_is_refused(options):
    with pytest.raises(ValueError):
        options.add("*background", "blue", "urgent")


def test_clear_discards_everything(options):
    options.add("*background", "blue")
    options.clear()
    assert len(options) == 0
    assert options.get(".ok", "Button", "background") is None


# -------------------------------------------------------------- selections


@pytest.fixture
def selections():
    return Selections()


def test_an_empty_selection_raises_rather_than_returning_nothing(selections):
    with pytest.raises(TclError):
        selections.get(CLIPBOARD)


def test_appending_starts_an_empty_selection(selections):
    selections.append("hello", CLIPBOARD)
    assert selections.get(CLIPBOARD) == "hello"


def test_appending_accumulates(selections):
    selections.append("hello ", CLIPBOARD)
    selections.append("world", CLIPBOARD)
    assert selections.get(CLIPBOARD) == "hello world"


def test_setting_replaces(selections):
    selections.append("old", CLIPBOARD)
    selections.set("new", CLIPBOARD)
    assert selections.get(CLIPBOARD) == "new"


def test_clearing_an_empty_selection_is_not_an_error(selections):
    selections.clear(CLIPBOARD)
    assert CLIPBOARD not in selections


def test_the_clipboard_and_the_primary_selection_are_separate(selections):
    selections.set("copied", CLIPBOARD)
    selections.set("selected", PRIMARY)
    assert selections.get(CLIPBOARD) == "copied"
    assert selections.get(PRIMARY) == "selected"


def test_an_empty_string_is_distinguishable_from_nothing(selections):
    selections.set("", CLIPBOARD)
    assert selections.get(CLIPBOARD) == ""
    assert CLIPBOARD in selections


def test_ownership_is_recorded_per_selection(selections):
    owner = object()
    selections.own(owner, PRIMARY)
    assert selections.owner(PRIMARY) is owner
    assert selections.owner(CLIPBOARD) is None


def test_disowning_releases_every_selection_that_widget_held(selections):
    owner = object()
    selections.own(owner, PRIMARY)
    selections.own(owner, CLIPBOARD)
    selections.disown(owner)
    assert selections.owner(PRIMARY) is None
    assert selections.owner(CLIPBOARD) is None


def test_disowning_leaves_another_widgets_claim_alone(selections):
    mine, theirs = object(), object()
    selections.own(mine, PRIMARY)
    selections.own(theirs, CLIPBOARD)
    selections.disown(mine)
    assert selections.owner(CLIPBOARD) is theirs


def test_a_handler_supplies_the_selection_on_demand(selections):
    owner = object()
    selections.own(owner, PRIMARY)
    selections.handle(owner, lambda offset, length: "from handler", PRIMARY)
    assert selections.resolve(PRIMARY) == "from handler"


def test_resolve_falls_back_to_the_stored_contents(selections):
    selections.set("stored", PRIMARY)
    assert selections.resolve(PRIMARY) == "stored"


def test_a_handler_belonging_to_a_former_owner_is_not_consulted(selections):
    old, new = object(), object()
    selections.handle(old, lambda offset, length: "stale", PRIMARY)
    selections.own(new, PRIMARY)
    selections.set("current", PRIMARY)
    assert selections.resolve(PRIMARY) == "current"


def test_disowning_removes_the_handler_too(selections):
    owner = object()
    selections.own(owner, PRIMARY)
    selections.handle(owner, lambda offset, length: "gone", PRIMARY)
    selections.disown(owner)
    with pytest.raises(TclError):
        selections.resolve(PRIMARY)


# -------------------------------------------------------------------- errors


def test_tcl_error_is_the_tkinter_name_for_a_tkcurses_error():
    assert TclError is TkCursesError
    assert issubclass(TclError, Exception)
