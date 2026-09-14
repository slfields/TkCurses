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

"""Tests for tkcurses._core.bindings."""

from __future__ import annotations

import pytest

from tkcurses._core.bindings import (
    BREAK,
    MOD_ANY,
    BindingTable,
    EventPattern,
    VirtualEvents,
    parse_sequence,
    pattern_for_event,
)
from tkcurses._core.events import (
    MOD_ALT,
    MOD_CTRL,
    MOD_SHIFT,
    Event,
    KeyEvent,
    MouseEvent,
    ResizeEvent,
)

# ----------------------------------------------------------------- parsing


def test_parses_a_plain_key_sequence():
    assert parse_sequence("<Key-a>") == EventPattern(type="Key", detail="a")


def test_key_press_is_an_alias_for_key():
    assert parse_sequence("<KeyPress-a>") == parse_sequence("<Key-a>")
    assert parse_sequence("<ButtonPress-1>") == parse_sequence("<Button-1>")


def test_parses_modifiers():
    pattern = parse_sequence("<Control-Alt-Key-x>")
    assert pattern.modifiers == MOD_CTRL | MOD_ALT
    assert pattern.detail == "x"


def test_modifier_aliases_agree_with_their_canonical_names():
    assert parse_sequence("<Ctrl-a>") == parse_sequence("<Control-a>")
    assert parse_sequence("<Command-a>") == parse_sequence("<Meta-a>")
    assert parse_sequence("<Option-a>") == parse_sequence("<Alt-a>")


def test_omitted_type_means_a_key_press():
    assert parse_sequence("<Control-c>") == EventPattern(
        type="Key", detail="c", modifiers=MOD_CTRL
    )
    assert parse_sequence("<F1>") == EventPattern(type="Key", detail="F1")


def test_parses_click_counts():
    assert parse_sequence("<Double-Button-1>").repeat == 2
    assert parse_sequence("<Triple-Button-1>").repeat == 3
    assert parse_sequence("<Button-1>").repeat == 1


def test_parses_a_bare_character_as_a_key():
    assert parse_sequence("a") == EventPattern(type="Key", detail="a")


def test_a_bare_space_uses_the_space_keysym():
    assert parse_sequence(" ") == EventPattern(type="Key", detail="space")


def test_parses_a_virtual_event():
    pattern = parse_sequence("<<Paste>>")
    assert pattern.is_virtual
    assert pattern.detail == "Paste"


def test_trailing_separator_is_the_minus_key():
    assert parse_sequence("<Control-->") == EventPattern(
        type="Key", detail="-", modifiers=MOD_CTRL
    )


def test_the_minus_key_can_be_bound_on_its_own():
    assert parse_sequence("<->") == EventPattern(type="Key", detail="-")


def test_a_type_with_no_detail_matches_anything_of_that_type():
    pattern = parse_sequence("<Key>")
    assert pattern.detail == ""
    assert pattern.matches(EventPattern(type="Key", detail="q"))


@pytest.mark.parametrize(
    "sequence",
    [
        "",
        "<>",
        "ab",
        "<Control-x><Control-s>",
        "<Control-Nonsense-a>",
        "<Control>",
        "<Key--a>",
    ],
)
def test_rejects_sequences_it_cannot_represent(sequence):
    with pytest.raises(ValueError):
        parse_sequence(sequence)


# ------------------------------------------------------------- round trips


@pytest.mark.parametrize(
    "sequence",
    [
        "<Key-a>",
        "<Control-Key-a>",
        "<Control-Alt-Shift-Key-a>",
        "<Double-Button-1>",
        "<ButtonRelease-2>",
        "<Motion>",
        "<Configure>",
        "<<Paste>>",
    ],
)
def test_a_canonical_sequence_survives_a_round_trip(sequence):
    assert str(parse_sequence(sequence)) == sequence


# ---------------------------------------------------------------- matching


def test_a_patterns_modifiers_need_only_be_a_subset():
    """Tk's rule, and not an obvious one.

    A binding fires when everything it asks for is held, whatever else is
    held alongside. Requiring equality - which this did - meant <Key> never
    fired for a key held with Shift, so the obvious binding for "tell me
    about every key" stopped working the moment a modifier was involved.
    """
    bound = parse_sequence("<Control-a>")
    assert bound.matches(EventPattern(type="Key", detail="a", modifiers=MOD_CTRL))
    assert bound.matches(
        EventPattern(type="Key", detail="a", modifiers=MOD_CTRL | MOD_SHIFT)
    )
    assert not bound.matches(EventPattern(type="Key", detail="a"))
    assert not bound.matches(EventPattern(type="Key", detail="a", modifiers=MOD_SHIFT))


def test_a_bare_pattern_matches_a_modified_event():
    bound = parse_sequence("<Key>")
    assert bound.matches(EventPattern(type="Key", detail="Down"))
    assert bound.matches(EventPattern(type="Key", detail="Down", modifiers=MOD_SHIFT))


def test_a_bare_button_matches_a_modified_click():
    bound = parse_sequence("<Button-1>")
    assert bound.matches(EventPattern(type="Button", detail="1", modifiers=MOD_SHIFT))


# ------------------------------------------------------------- specificity
#
# The order below is Tk 9.0.2's, read off a real tkinter.Frame with several
# patterns bound at once and event_generate driving it. Recorded rather than
# reasoned about: "more specific" is a phrase, and this is what it means.


def test_a_detail_outranks_any_number_of_modifiers():
    """<Key-A> beats <Shift-Key> for a shifted A."""
    assert (
        parse_sequence("<Key-A>").specificity
        > parse_sequence("<Shift-Key>").specificity
    )


def test_more_modifiers_wins_when_the_detail_is_the_same():
    assert (
        parse_sequence("<Shift-Key-A>").specificity
        > parse_sequence("<Key-A>").specificity
    )
    assert (
        parse_sequence("<Shift-Key>").specificity > parse_sequence("<Key>").specificity
    )


def test_any_is_not_counted_as_a_modifier():
    """It waives the comparison rather than demanding anything."""
    assert (
        parse_sequence("<Any-Key-a>").specificity
        == parse_sequence("<Key-a>").specificity
    )


def test_any_modifier_waives_the_comparison():
    bound = parse_sequence("<Any-Key-a>")
    assert bound.modifiers & MOD_ANY
    assert bound.matches(EventPattern(type="Key", detail="a"))
    assert bound.matches(
        EventPattern(type="Key", detail="a", modifiers=MOD_CTRL | MOD_ALT)
    )


def test_a_single_click_binding_also_fires_on_a_double_click():
    single = parse_sequence("<Button-1>")
    assert single.matches(EventPattern(type="Button", detail="1", repeat=2))


def test_a_double_click_binding_ignores_a_single_click():
    double = parse_sequence("<Double-Button-1>")
    assert not double.matches(EventPattern(type="Button", detail="1"))
    assert double.matches(EventPattern(type="Button", detail="1", repeat=2))


def test_different_types_never_match():
    assert not parse_sequence("<Button-1>").matches(
        EventPattern(type="ButtonRelease", detail="1")
    )


# ------------------------------------------------------- events to patterns


def test_key_event_becomes_a_key_pattern():
    event = KeyEvent(keysym="a", char="a", modifiers=MOD_CTRL)
    assert pattern_for_event(event) == EventPattern(
        type="Key", detail="a", modifiers=MOD_CTRL
    )


@pytest.mark.parametrize(
    ("state", "expected_type", "repeat"),
    [
        ("pressed", "Button", 1),
        ("clicked", "Button", 1),
        ("double", "Button", 2),
        ("triple", "Button", 3),
        ("released", "ButtonRelease", 1),
        ("drag", "Motion", 1),
        ("motion", "Motion", 1),
    ],
)
def test_mouse_states_become_the_matching_pattern(state, expected_type, repeat):
    pattern = pattern_for_event(MouseEvent(button=1, state=state))
    assert pattern.type == expected_type
    assert pattern.repeat == repeat


def test_motion_carries_no_button_detail():
    assert pattern_for_event(MouseEvent(button=1, state="drag")).detail == ""


def test_resize_event_becomes_configure():
    assert pattern_for_event(ResizeEvent(width=80, height=24)) == EventPattern(
        type="Configure"
    )


def test_an_event_with_no_pattern_is_refused():
    with pytest.raises(TypeError):
        pattern_for_event(Event())


# ----------------------------------------------------------- binding table


@pytest.fixture
def table():
    return BindingTable()


def test_bind_returns_a_handle_and_records_the_sequence(table):
    funcid = table.bind(".w", parse_sequence("<Key-a>"), lambda event: None)
    assert funcid
    assert table.sequences(".w") == ["<Key-a>"]


def test_rebinding_replaces_by_default(table):
    pattern = parse_sequence("<Key-a>")
    table.bind(".w", pattern, lambda event: None)
    table.bind(".w", pattern, lambda event: None)
    assert len(table.bindings(".w", pattern)) == 1


def test_add_keeps_the_existing_callback(table):
    pattern = parse_sequence("<Key-a>")
    table.bind(".w", pattern, lambda event: None)
    table.bind(".w", pattern, lambda event: None, add=True)
    assert len(table.bindings(".w", pattern)) == 2


def test_added_callbacks_run_in_the_order_they_were_added(table):
    pattern = parse_sequence("<Key-a>")
    calls = []
    table.bind(".w", pattern, lambda event: calls.append("first"))
    table.bind(".w", pattern, lambda event: calls.append("second"), add=True)
    table.dispatch([".w"], object(), [pattern])
    assert calls == ["first", "second"]


def test_unbind_by_handle_leaves_the_others(table):
    pattern = parse_sequence("<Key-a>")
    first = table.bind(".w", pattern, lambda event: None)
    table.bind(".w", pattern, lambda event: None, add=True)
    table.unbind(".w", funcid=first)
    remaining = table.bindings(".w", pattern)
    assert [b.funcid for b in remaining] != [first]
    assert len(remaining) == 1


def test_unbind_by_pattern_clears_every_callback_on_it(table):
    pattern = parse_sequence("<Key-a>")
    table.bind(".w", pattern, lambda event: None)
    table.bind(".w", pattern, lambda event: None, add=True)
    table.unbind(".w", pattern)
    assert table.bindings(".w", pattern) == []


def test_unbind_with_no_pattern_clears_the_tag(table):
    table.bind(".w", parse_sequence("<Key-a>"), lambda event: None)
    table.bind(".w", parse_sequence("<Key-b>"), lambda event: None)
    table.unbind(".w")
    assert table.sequences(".w") == []


def test_unbinding_something_absent_is_not_an_error(table):
    table.unbind(".w")
    table.unbind(".w", parse_sequence("<Key-a>"))
    table.unbind(".w", funcid="bind#999")


def test_a_reused_handle_is_forgotten_after_a_replacing_bind(table):
    pattern = parse_sequence("<Key-a>")
    first = table.bind(".w", pattern, lambda event: None)
    table.bind(".w", pattern, lambda event: None)
    table.unbind(".w", funcid=first)
    # The replacement must survive removing the handle it replaced.
    assert len(table.bindings(".w", pattern)) == 1


def test_tags_lists_only_tags_holding_bindings(table):
    table.bind("all", parse_sequence("<Key-a>"), lambda event: None)
    assert table.tags() == ["all"]
    table.unbind("all")
    assert table.tags() == []


# -------------------------------------------------------------- dispatching


def test_dispatch_walks_tags_in_order(table):
    pattern = parse_sequence("<Key-a>")
    calls = []
    table.bind(".w", pattern, lambda event: calls.append("widget"))
    table.bind("Button", pattern, lambda event: calls.append("class"))
    table.bind("all", pattern, lambda event: calls.append("all"))
    table.dispatch([".w", "Button", "all"], object(), [pattern])
    assert calls == ["widget", "class", "all"]


def test_break_stops_the_remaining_tags(table):
    pattern = parse_sequence("<Key-a>")
    calls = []
    table.bind(".w", pattern, lambda event: BREAK)
    table.bind("all", pattern, lambda event: calls.append("all"))
    assert table.dispatch([".w", "all"], object(), [pattern]) is True
    assert calls == []


def test_dispatch_reports_no_break_when_every_callback_returns_none(table):
    pattern = parse_sequence("<Key-a>")
    table.bind(".w", pattern, lambda event: None)
    assert table.dispatch([".w"], object(), [pattern]) is False


def test_dispatch_passes_the_event_through(table):
    pattern = parse_sequence("<Key-a>")
    seen = []
    event = KeyEvent(keysym="a", char="a")
    table.bind(".w", pattern, seen.append)
    table.dispatch([".w"], event, [pattern])
    assert seen == [event]


def test_dispatch_matches_by_pattern_not_identity(table):
    table.bind(".w", parse_sequence("<Key>"), lambda event: None)
    fired = []
    table.bind(".w", parse_sequence("<Key-a>"), lambda event: fired.append(True))
    table.dispatch([".w"], object(), [EventPattern(type="Key", detail="a")])
    assert fired == [True]


def test_an_unmatched_event_runs_nothing(table):
    table.bind(".w", parse_sequence("<Key-a>"), lambda event: pytest.fail("ran"))
    assert table.dispatch([".w"], object(), [EventPattern(type="Key", detail="b")]) is (
        False
    )


def test_a_callback_may_unbind_itself_during_dispatch(table):
    pattern = parse_sequence("<Key-a>")

    def handler(event):
        table.unbind(".w", pattern)

    table.bind(".w", pattern, handler)
    table.dispatch([".w"], object(), [pattern])
    assert table.bindings(".w", pattern) == []


# ----------------------------------------------------------- virtual events


@pytest.fixture
def virtuals():
    return VirtualEvents()


def test_a_virtual_event_reports_its_physical_sequences(virtuals):
    virtuals.add("<<Paste>>", parse_sequence("<Control-v>"))
    assert virtuals.info("<<Paste>>") == (parse_sequence("<Control-v>"),)


def test_a_virtual_name_may_be_given_with_or_without_brackets(virtuals):
    virtuals.add("Paste", parse_sequence("<Control-v>"))
    assert virtuals.info("<<Paste>>") == virtuals.info("Paste")


def test_adding_accumulates_sequences_without_duplicating(virtuals):
    virtuals.add("<<Paste>>", parse_sequence("<Control-v>"))
    virtuals.add("<<Paste>>", parse_sequence("<Shift-Insert>"))
    virtuals.add("<<Paste>>", parse_sequence("<Control-v>"))
    assert len(virtuals.info("<<Paste>>")) == 2


def test_delete_removes_one_sequence(virtuals):
    virtuals.add(
        "<<Paste>>", parse_sequence("<Control-v>"), parse_sequence("<Shift-Insert>")
    )
    virtuals.delete("<<Paste>>", parse_sequence("<Control-v>"))
    assert virtuals.info("<<Paste>>") == (parse_sequence("<Shift-Insert>"),)


def test_delete_with_no_sequence_removes_the_event(virtuals):
    virtuals.add("<<Paste>>", parse_sequence("<Control-v>"))
    virtuals.delete("<<Paste>>")
    assert virtuals.info("<<Paste>>") == ()
    assert virtuals.names() == []


def test_names_are_reported_in_bracketed_form(virtuals):
    virtuals.add("<<Paste>>", parse_sequence("<Control-v>"))
    assert virtuals.names() == ["<<Paste>>"]


def test_a_physical_pattern_reports_the_virtuals_it_raises(virtuals):
    virtuals.add("<<Paste>>", parse_sequence("<Control-v>"))
    raised = virtuals.raised_by(
        EventPattern(type="Key", detail="v", modifiers=MOD_CTRL)
    )
    assert raised == [EventPattern(type="Virtual", detail="Paste")]


def test_an_unrelated_pattern_raises_nothing(virtuals):
    virtuals.add("<<Paste>>", parse_sequence("<Control-v>"))
    assert virtuals.raised_by(EventPattern(type="Key", detail="q")) == []


def test_a_malformed_virtual_name_is_refused(virtuals):
    with pytest.raises(ValueError):
        virtuals.add("<Paste>", parse_sequence("<Control-v>"))


# --------------------------------------------------- choosing between matches
#
# Also recorded from Tk 9.0.2: with several patterns bound at once, which one
# actually runs. Tk picks the most specific match within each binding tag and
# then moves on to the next tag, so a widget binding and a class binding both
# get their turn even when one is more specific than the other.


def _table_firing(patterns: list[str], tags: list[str] | None = None):
    """A table with one recording callback per pattern, and what fires."""
    table = BindingTable()
    fired: list[str] = []
    for index, sequence in enumerate(patterns):
        tag = (tags or ["w"] * len(patterns))[index]
        table.bind(
            tag,
            parse_sequence(sequence),
            (lambda name: lambda event: fired.append(name))(sequence),
        )
    return table, fired


def test_the_most_specific_pattern_on_a_tag_wins():
    table, fired = _table_firing(["<Key>", "<Shift-Key>"])
    table.dispatch(
        ["w"], None, [EventPattern(type="Key", detail="Down", modifiers=MOD_SHIFT)]
    )
    assert fired == ["<Shift-Key>"]


def test_the_bare_pattern_runs_when_nothing_more_specific_matches():
    table, fired = _table_firing(["<Key>", "<Shift-Key>"])
    table.dispatch(["w"], None, [EventPattern(type="Key", detail="Down")])
    assert fired == ["<Key>"]


def test_a_detail_beats_a_modifier_on_the_same_tag():
    table, fired = _table_firing(["<Key-A>", "<Shift-Key>"])
    table.dispatch(
        ["w"], None, [EventPattern(type="Key", detail="A", modifiers=MOD_SHIFT)]
    )
    assert fired == ["<Key-A>"]


def test_a_shifted_button_binding_beats_the_plain_one():
    table, fired = _table_firing(["<Button-1>", "<Shift-Button-1>"])
    table.dispatch(
        ["w"], None, [EventPattern(type="Button", detail="1", modifiers=MOD_SHIFT)]
    )
    assert fired == ["<Shift-Button-1>"]


def test_every_tag_gets_its_own_turn():
    """A widget's <Key> and a class's <Shift-Key> both fire, in tag order."""
    table, fired = _table_firing(["<Key>", "<Shift-Key>"], tags=["w", "Class"])
    table.dispatch(
        ["w", "Class"],
        None,
        [EventPattern(type="Key", detail="Down", modifiers=MOD_SHIFT)],
    )
    assert fired == ["<Key>", "<Shift-Key>"]


def test_a_virtual_event_still_fires_beside_the_physical_one():
    """They are two events, not two patterns competing for one."""
    table = BindingTable()
    fired: list[str] = []
    table.bind("w", parse_sequence("<Key-v>"), lambda event: fired.append("physical"))
    table.bind("w", parse_sequence("<<Paste>>"), lambda event: fired.append("virtual"))
    table.dispatch(
        ["w"],
        None,
        [
            EventPattern(type="Key", detail="v"),
            EventPattern(type="Virtual", detail="Paste"),
        ],
    )
    assert sorted(fired) == ["physical", "virtual"]


def test_handlers_added_to_one_pattern_all_run_in_order():
    table = BindingTable()
    fired: list[str] = []
    table.bind("w", parse_sequence("<Key>"), lambda event: fired.append("first"))
    table.bind(
        "w", parse_sequence("<Key>"), lambda event: fired.append("second"), add=True
    )
    table.dispatch(["w"], None, [EventPattern(type="Key", detail="q")])
    assert fired == ["first", "second"]


# ------------------------------------------------------ punctuation keysyms
#
# X11's names are what every piece of tkinter documentation uses to bind a
# punctuation key: <Key-period>, not <Key-.>. Tk resolves the name when it
# parses the binding - verified against Tk 9.0.2, where a binding written
# <Key-period> fires and the event that reaches it reports keysym '.'.


@pytest.mark.parametrize(
    ("name", "character"),
    [
        ("period", "."),
        ("comma", ","),
        ("minus", "-"),
        ("plus", "+"),
        ("slash", "/"),
        ("backslash", "\\"),
        ("semicolon", ";"),
        ("colon", ":"),
        ("question", "?"),
        ("exclam", "!"),
        ("bracketleft", "["),
        ("braceright", "}"),
        ("underscore", "_"),
        ("asciitilde", "~"),
        ("at", "@"),
        ("numbersign", "#"),
    ],
)
def test_an_x11_name_and_its_character_are_the_same_binding(name, character):
    assert parse_sequence(f"<Key-{name}>") == parse_sequence(f"<Key-{character}>")


def test_a_named_punctuation_binding_fires_for_the_key():
    """The whole point: without this the binding could never match.

    The event carries the character, so a pattern holding the name went
    looking for a keysym nothing would ever report.
    """
    bound = parse_sequence("<Key-period>")
    assert bound.matches(EventPattern(type="Key", detail="."))


def test_a_modified_punctuation_binding_works_too():
    assert parse_sequence("<Control-period>") == EventPattern(
        type="Key", detail=".", modifiers=MOD_CTRL
    )


def test_space_keeps_its_name():
    """Tk's own exception: a bare space cannot be told from a separator."""
    assert parse_sequence("<Key-space>").detail == "space"
    assert parse_sequence(" ").detail == "space"


def test_letters_and_digits_are_left_alone():
    assert parse_sequence("<Key-a>").detail == "a"
    assert parse_sequence("<Key-Z>").detail == "Z"
    assert parse_sequence("<Key-5>").detail == "5"


def test_named_keys_are_left_alone():
    assert parse_sequence("<Key-Return>").detail == "Return"
    assert parse_sequence("<Key-F1>").detail == "F1"


# ------------------------------------------------- what is bound, not what fires


def test_details_bound_with_finds_patterns_needing_exactly_those_modifiers():
    """Asks what is waiting for a key, which is not the same as what fires.

    The terminal has to know whether anything anywhere wants Control-C
    before it will stop turning it into an interrupt, and that is a question
    about the table's contents rather than about any one event.
    """
    table = BindingTable()
    table.bind("all", parse_sequence("<Control-c>"), lambda event: None)
    table.bind(".b", parse_sequence("<Control-z>"), lambda event: None)
    table.bind(".b", parse_sequence("<Key-c>"), lambda event: None)
    table.bind(".b", parse_sequence("<Control-Shift-q>"), lambda event: None)
    table.bind(".b", parse_sequence("<Control-Button-1>"), lambda event: None)
    assert table.details_bound_with(MOD_CTRL) == {"c", "z"}


def test_details_bound_with_forgets_what_has_been_unbound():
    table = BindingTable()
    funcid = table.bind(".b", parse_sequence("<Control-c>"), lambda event: None)
    assert table.details_bound_with(MOD_CTRL) == {"c"}
    table.unbind(".b", funcid=funcid)
    assert table.details_bound_with(MOD_CTRL) == set()


def test_binding_and_unbinding_report_a_change():
    changes = []
    table = BindingTable(on_change=lambda: changes.append(1))
    funcid = table.bind(".b", parse_sequence("<Control-c>"), lambda event: None)
    assert len(changes) == 1
    table.unbind(".b", funcid=funcid)
    assert len(changes) == 2
    table.unbind(".b")
    assert len(changes) == 3
