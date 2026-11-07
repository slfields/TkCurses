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

"""The ttk style database, which needs no terminal: a lookup is arithmetic.

Every rule here was measured against real ttk on Tk 9.0 before it was
written, and the two that are not what they look like say so where they are
asserted.
"""

from __future__ import annotations

import unicodedata

import pytest

from tkcurses import Frame, Misc, TclError
from tkcurses.ttk import (
    STATES,
    THEMES,
    Glyphs,
    Style,
    Widget,
    state_matches,
    style_chain,
)


@pytest.fixture
def style():
    """A style database over its own application."""
    return Style(Misc())


# ------------------------------------------------------------- the chain


def test_a_plain_name_inherits_from_nothing():
    assert style_chain("TButton") == ["TButton"]


def test_a_dotted_name_falls_back_to_its_base():
    assert style_chain("Danger.TButton") == ["Danger.TButton", "TButton"]


def test_the_chain_goes_all_the_way_down():
    """Measured: A.B.C.TDeep finds TDeep."""
    assert style_chain("A.B.C.TDeep") == [
        "A.B.C.TDeep",
        "B.C.TDeep",
        "C.TDeep",
        "TDeep",
    ]


# ------------------------------------------------------------ state specs


@pytest.mark.parametrize(
    ("spec", "states", "expected"),
    [
        ((), frozenset(), True),
        ((), frozenset({"disabled"}), True),
        (("disabled",), frozenset({"disabled"}), True),
        (("disabled",), frozenset(), False),
        (("!disabled",), frozenset(), True),
        (("!disabled",), frozenset({"disabled"}), False),
        (("disabled", "focus"), frozenset({"disabled", "focus"}), True),
        (("disabled", "focus"), frozenset({"disabled"}), False),
        (("disabled", "!focus"), frozenset({"disabled"}), True),
    ],
)
def test_every_element_of_a_spec_has_to_match(spec, states, expected):
    assert state_matches(spec, states) is expected


def test_an_empty_spec_is_a_default():
    """Which is how a map entry with no states acts as a catch-all."""
    assert state_matches((), frozenset({"anything"}))


# -------------------------------------------------------------- configure


def test_configure_sets_and_reads_back(style):
    style.configure("TThing", foreground="red")
    assert style.configure("TThing", "foreground") == "red"


def test_configure_with_nothing_returns_what_this_style_sets(style):
    style.configure("TThing", foreground="red", background="black")
    assert style.configure("TThing") == {"foreground": "red", "background": "black"}


def test_configure_reports_only_its_own_entries(style):
    """Not what it inherits - tkinter's configure() answers for the style
    itself, and lookup() is the one that walks the chain."""
    style.configure("TBase", padding=2)
    style.configure("Derived.TBase", foreground="red")
    assert style.configure("Derived.TBase") == {"foreground": "red"}


def test_an_unset_option_reads_as_the_empty_string(style):
    assert style.configure("TThing", "nosuch") == ""


# -------------------------------------------------------------- inheritance


def test_a_derived_style_inherits_what_it_does_not_set(style):
    style.configure("TBase", padding=2)
    style.configure("Derived.TBase", foreground="red")
    assert style.lookup("Derived.TBase", "padding") == 2
    assert style.lookup("Derived.TBase", "foreground") == "red"


def test_a_derived_style_overrides_what_it_does_set(style):
    style.configure("TBase", foreground="base")
    style.configure("Derived.TBase", foreground="derived")
    assert style.lookup("Derived.TBase", "foreground") == "derived"


# --------------------------------------------------------------- the maps


def test_a_map_entry_applies_in_its_state(style):
    style.configure("TThing", foreground="plain")
    style.map("TThing", foreground=[("disabled", "grey")])
    assert style.lookup("TThing", "foreground", ["disabled"]) == "grey"


def test_without_the_state_the_configure_value_stands(style):
    style.configure("TThing", foreground="plain")
    style.map("TThing", foreground=[("disabled", "grey")])
    assert style.lookup("TThing", "foreground", []) == "plain"


def test_map_entries_match_in_the_order_they_were_given(style):
    """Not most-specific-first. Measured against Tk 9.0: with
    [(disabled, focus, both), (disabled, plain)] and both states set, the
    answer is `both` because the first entry matched - and with only
    disabled set it is `plain`, because the first one did not."""
    style.map(
        "TThing", foreground=[("disabled", "focus", "both"), ("disabled", "plain")]
    )
    assert style.lookup("TThing", "foreground", ["disabled", "focus"]) == "both"
    assert style.lookup("TThing", "foreground", ["disabled"]) == "plain"


def test_a_negated_state_matches_when_it_is_absent(style):
    style.configure("TThing", foreground="plain")
    style.map("TThing", foreground=[("!disabled", "enabled-only")])
    assert style.lookup("TThing", "foreground", []) == "enabled-only"
    assert style.lookup("TThing", "foreground", ["disabled"]) == "plain"


def test_map_reads_back_in_tkinters_shape(style):
    style.map("TThing", foreground=[("disabled", "grey")])
    assert style.map("TThing") == {"foreground": [("disabled", "grey")]}
    assert style.map("TThing", "foreground") == [("disabled", "grey")]


# ------------------------------------------------- the rule that surprises


def test_a_base_styles_map_beats_a_derived_styles_configure(style):
    """The one that is not what it looks like, and the reason lookup makes
    two passes rather than walking the chain once.

    Measured against Tk 9.0: with TFrob configured `base-cfg`, mapped
    `base-map` for disabled, and Derived.TFrob configured `derived-cfg`,
    a disabled lookup on the derived style answers **base-map**. An
    interleaved walk would have answered derived-cfg.
    """
    style.configure("TFrob", foreground="base-cfg")
    style.map("TFrob", foreground=[("disabled", "base-map")])
    style.configure("Derived.TFrob", foreground="derived-cfg")
    assert style.lookup("Derived.TFrob", "foreground", ["disabled"]) == "base-map"


def test_but_without_the_state_the_derived_configure_wins(style):
    """The other half of the same rule: no map entry matches, so the second
    pass runs and the chain is walked most-specific-first."""
    style.configure("TFrob", foreground="base-cfg")
    style.map("TFrob", foreground=[("disabled", "base-map")])
    style.configure("Derived.TFrob", foreground="derived-cfg")
    assert style.lookup("Derived.TFrob", "foreground", []) == "derived-cfg"


# ---------------------------------------------------------------- lookup


def test_a_miss_is_the_empty_string(style):
    """tkinter answers with '' and callers test it for truth."""
    assert style.lookup("TNothing", "foreground") == ""


def test_a_named_default_is_used_on_a_miss(style):
    assert style.lookup("TNothing", "foreground", None, "fallback") == "fallback"


def test_a_named_default_does_not_override_a_hit(style):
    style.configure("TThing", foreground="real")
    assert style.lookup("TThing", "foreground", None, "fallback") == "real"


# ---------------------------------------------------------------- themes


def test_the_themes_are_the_terminals_not_tkinters(style):
    """A deliberate departure: clam, alt and classic describe bevels and
    shading a character grid cannot show. What varies here is glyphs."""
    assert style.theme_names() == tuple(THEMES)
    assert "clam" not in style.theme_names()
    assert "default" in style.theme_names(), "the one name in both lists"


def test_the_default_theme_is_in_use_to_begin_with(style):
    assert style.theme_use() == "default"


def test_theme_use_switches_and_reports(style):
    assert style.theme_use("ascii") == "ascii"
    assert style.theme_use() == "ascii"


def test_no_two_themes_draw_alike():
    """A theme with another's characters is a name that does nothing."""
    looks = [tuple(vars(glyphs).values()) for glyphs in THEMES.values()]
    assert len(set(looks)) == len(looks)


def test_dos_frames_double_across_and_single_down():
    """Code page 437's mixed pieces, which DOS programs framed windows
    with: every piece joins a double horizontal to a single vertical, so a
    tee and a cross meet the rails on either side of them."""
    dos = THEMES["dos"]
    assert (dos.top_left, dos.horizontal, dos.top_right) == ("╒", "═", "╕")
    assert (dos.bottom_left, dos.vertical, dos.bottom_right) == ("╘", "│", "╛")
    assert (dos.tee_down, dos.tee_up, dos.cross) == ("╤", "╧", "╪")
    for piece in (
        dos.top_left,
        dos.top_right,
        dos.bottom_left,
        dos.bottom_right,
        dos.tee_down,
        dos.tee_up,
        dos.cross,
    ):
        name = unicodedata.name(piece)
        assert "SINGLE" in name and "DOUBLE" in name, name


def test_switching_to_a_theme_that_does_not_exist_says_so(style):
    with pytest.raises(TclError, match="no such theme"):
        style.theme_use("clam")


def test_every_theme_draws_with_its_own_glyphs(style):
    seen = {}
    for name in style.theme_names():
        style.theme_use(name)
        seen[name] = style.glyphs()
    assert seen["default"].top_left == "┌"
    assert seen["ascii"].top_left == "+"
    assert seen["rounded"].top_left == "╭"
    assert seen["double"].horizontal == "═"
    assert seen["minimal"].vertical == " "


def test_a_style_set_in_one_theme_is_not_in_another(style):
    """Which is what makes a theme a theme rather than a glyph table."""
    style.configure("TThing", foreground="in-default")
    style.theme_use("ascii")
    assert style.lookup("TThing", "foreground") == ""
    style.theme_use("default")
    assert style.lookup("TThing", "foreground") == "in-default"


# --------------------------------------------------------- theme creation


def test_a_new_theme_starts_empty(style):
    style.theme_create("plain")
    style.theme_use("plain")
    assert style.lookup("TButton", "foreground") == ""


def test_a_theme_can_start_as_a_copy_of_another(style):
    style.configure("TThing", foreground="inherited")
    style.theme_create("child", parent="default")
    style.theme_use("child")
    assert style.lookup("TThing", "foreground") == "inherited"


def test_the_copy_is_taken_once_and_does_not_track_its_parent(style):
    """tkinter's themes behave this way too, and a live view would put a
    second dimension into every lookup for something nothing asks for."""
    style.theme_create("child", parent="default")
    style.configure("TThing", foreground="added-after")
    style.theme_use("child")
    assert style.lookup("TThing", "foreground") == ""


def test_a_duplicate_theme_name_is_refused(style):
    with pytest.raises(TclError, match="already exists"):
        style.theme_create("default")


def test_an_unknown_parent_is_refused(style):
    with pytest.raises(TclError, match="no such theme"):
        style.theme_create("child", parent="clam")


def test_theme_settings_applies_a_batch(style):
    style.theme_create("batched")
    style.theme_settings(
        "batched",
        {
            "TThing": {
                "configure": {"foreground": "red"},
                "map": {"foreground": [("disabled", "grey")]},
            }
        },
    )
    style.theme_use("batched")
    assert style.lookup("TThing", "foreground") == "red"
    assert style.lookup("TThing", "foreground", ["disabled"]) == "grey"


def test_theme_settings_does_not_change_which_theme_is_in_use(style):
    style.theme_create("batched")
    style.theme_settings("batched", {"TThing": {"configure": {"foreground": "red"}}})
    assert style.theme_use() == "default"


# -------------------------------------------------------------- elements


def test_the_elements_are_the_parts_of_a_box(style):
    assert "top_left" in style.element_names()
    assert "horizontal" in style.element_names()


def test_an_element_takes_a_character(style):
    assert style.element_options("top_left") == ("character",)


def test_an_unknown_element_says_so(style):
    with pytest.raises(TclError, match="no such element"):
        style.element_options("thumb")


@pytest.mark.parametrize("method", ["layout", "element_create"])
def test_the_geometry_methods_say_why_they_are_not_there(style, method):
    """Refused with a reason rather than silently doing nothing: a terminal
    widget is characters in a grid and has no element assembly to describe."""
    with pytest.raises(TclError, match="not available"):
        getattr(style, method)("TThing", "x")


# ------------------------------------------------------ one database each


def test_every_style_in_one_application_shares_a_database():
    """Which is what makes ttk.Style().configure(...) in one place change
    widgets made in another - tkinter gets it by talking to the interpreter."""
    root = Misc()
    Style(root).configure("TThing", foreground="set-elsewhere")
    assert Style(root).lookup("TThing", "foreground") == "set-elsewhere"


def test_two_applications_do_not_share_one():
    assert Style(Misc()).lookup("TThing", "foreground") == ""


def test_the_database_is_not_built_until_a_style_asks_for_one():
    """An application using none of ttk should not pay for six themes."""
    root = Misc()
    assert root.tk.themes is None
    Style(root)
    assert root.tk.themes is not None


def test_glyphs_are_the_shape_a_widget_will_ask_for(style):
    assert isinstance(style.glyphs(), Glyphs)


# ---------------------------------------------------------- the shadowing


def test_importing_ttk_does_not_break_the_package():
    """The trap tkcurses.curses fell into, checked before it could happen.

    A submodule is bound as an attribute of its package, which for
    tkcurses/__init__.py is that module's own global namespace. `curses`
    was a name it used fifty-one times, so importing tkcurses.curses
    replaced the standard library with the facade. `ttk` is not a name that
    module uses, so nothing is clobbered - and this says so, rather than
    leaving the next submodule to find out the hard way.
    """
    import sys

    import tkcurses.ttk  # noqa: F401

    namespace = sys.modules["tkcurses"].__dict__
    assert namespace["_curses"].__name__ == "curses", "the stdlib is still there"
    root = Misc()
    assert root.winfo_rgb("red") == (52685, 0, 0)


# ==========================================================================
# The themed widget base
# ==========================================================================


class Themed(Widget, Frame):
    """A themed widget, which is what the mixin is for: an ordinary widget
    plus the state flags and the style lookup."""

    _ttk_class = "TThemed"


@pytest.fixture
def themed():
    return Themed(Misc(), name="w")


# ---------------------------------------------------------------- the class


def test_a_themed_widget_reports_its_themed_class(themed):
    """TButton, not Button - which is what puts its bindings and its default
    style under the ttk name."""
    assert themed.winfo_class() == "TThemed"


def test_the_classic_class_is_not_among_its_bindtags(themed):
    """Measured against Tk 9.0: ttk.Button's bindtags are
    ('.!button2', 'TButton', '.', 'all') - Button is not there. A themed
    widget therefore gets none of the classic widget's class bindings, and
    installs its own."""
    assert "TThemed" in themed.bindtags()
    assert "Frame" not in themed.bindtags()


# ---------------------------------------------------------------- state()


def test_a_widget_starts_with_no_states(themed):
    assert themed.state() == ()


def test_setting_a_state_reports_what_it_was(themed):
    """Measured: setting `disabled` on an enabled widget answers
    ('!disabled',) - the previous value, as a spec that would undo it."""
    assert themed.state(["disabled"]) == ("!disabled",)
    assert themed.state() == ("disabled",)


def test_setting_a_state_that_is_already_set_changes_nothing(themed):
    themed.state(["disabled"])
    assert themed.state(["disabled"]) == ()


def test_clearing_a_state_reports_what_it_was(themed):
    themed.state(["disabled"])
    assert themed.state(["!disabled"]) == ("disabled",)
    assert themed.state() == ()


def test_several_flags_report_in_the_order_they_were_given(themed):
    assert themed.state(["disabled", "focus"]) == ("!disabled", "!focus")
    assert themed.state() == ("disabled", "focus")


def test_only_the_flags_that_changed_are_reported(themed):
    themed.state(["disabled"])
    assert themed.state(["disabled", "focus"]) == ("!focus",)


def test_the_answer_undoes_the_change(themed):
    """The idiom the return value exists for."""
    previous = themed.state(["disabled", "focus"])
    themed.state(previous)
    assert themed.state() == ()


def test_a_state_ttk_does_not_define_is_refused(themed):
    """As Tk does - 'Invalid state name nonsense' - rather than storing a
    flag nothing will ever look at."""
    with pytest.raises(TclError, match="Invalid state name"):
        themed.state(["nonsense"])


def test_every_state_ttk_defines_is_accepted(themed):
    for name in sorted(STATES):
        themed.state([name])
        themed.state([f"!{name}"])
    assert themed.state() == ()


# --------------------------------------------------------------- instate()


def test_instate_without_a_callback_answers_a_boolean(themed):
    assert themed.instate(["!disabled"]) is True
    assert themed.instate(["disabled"]) is False


def test_instate_runs_the_callback_when_it_matches(themed):
    calls = []
    themed.instate(["!disabled"], calls.append, "ran")
    assert calls == ["ran"]


def test_instate_returns_what_the_callback_returned(themed):
    """Measured: a matching call answered the callback's own None, not True."""
    assert themed.instate(["!disabled"], lambda: None) is None
    assert themed.instate(["!disabled"], lambda: "value") == "value"


def test_instate_answers_false_and_runs_nothing_when_it_does_not_match(themed):
    calls = []
    assert themed.instate(["disabled"], calls.append, "ran") is False
    assert calls == []


def test_instate_takes_a_negated_spec(themed):
    themed.state(["disabled"])
    assert themed.instate(["disabled"]) is True
    assert themed.instate(["!disabled"]) is False


# ------------------------------------------------------- the style lookup


def test_a_widget_with_no_style_option_uses_its_class(themed):
    Style(themed).configure("TThemed", foreground="from-the-class")
    assert themed._styled("foreground") == "from-the-class"


def test_an_explicit_style_option_wins(themed):
    Style(themed).configure("TThemed", foreground="from-the-class")
    Style(themed).configure("Loud.TThemed", foreground="from-the-style")
    themed.configure(style="Loud.TThemed")
    assert themed._styled("foreground") == "from-the-style"


def test_an_explicit_style_still_inherits_from_the_class(themed):
    Style(themed).configure("TThemed", padding=3)
    Style(themed).configure("Loud.TThemed", foreground="loud")
    themed.configure(style="Loud.TThemed")
    assert themed._styled("padding") == 3


def test_the_lookup_follows_the_widgets_state(themed):
    style = Style(themed)
    style.configure("TThemed", foreground="plain")
    style.map("TThemed", foreground=[("disabled", "grey")])
    assert themed._styled("foreground") == "plain"
    themed.state(["disabled"])
    assert themed._styled("foreground") == "grey"


def test_an_unstyled_option_falls_back_to_the_default_given(themed):
    assert themed._styled("nosuch", "fallback") == "fallback"


def test_configuring_the_class_reaches_every_widget_of_it():
    """The whole point of a style database: change one place, and every
    widget that did not ask for something else follows."""
    root = Misc()
    widgets = [Themed(root, name=f"w{index}") for index in range(3)]
    Style(root).configure("TThemed", foreground="all-of-them")
    assert [w._styled("foreground") for w in widgets] == ["all-of-them"] * 3
