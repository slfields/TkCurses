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

"""Tests for the Spinbox widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Entry, Misc, Spinbox, StringVar, TclError, ttk
from tkcurses._core.events import KeyEvent, MouseEvent
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
    root._rect = Rect(0, 0, 40, 12)
    root._mapped = True
    return root


def laid_out(widget, width=14, height=1):
    widget._allocate(Rect(0, 0, width, height))
    widget._map()
    return widget


SIZES = ("small", "medium", "large")


# ------------------------------------------------------------- starting out


def test_a_values_spinbox_starts_on_the_first_value(root):
    assert Spinbox(root, name="s", values=SIZES).get() == "small"


def test_a_numeric_spinbox_starts_at_from(root):
    assert Spinbox(root, name="s", from_=2, to=8).get() == "2"


def test_values_overwrite_a_textvariable(root):
    """Measured on Tk 9.0.2: the first value wins, and is written to the
    variable. This test asserted the opposite until TkCurses-fdl9."""
    variable = StringVar(root, "medium")
    spin = Spinbox(root, name="s", values=SIZES, textvariable=variable)
    assert spin.get() == "small"
    assert variable.get() == "small"


# ------------------------------------------------------------------ stepping


def test_the_arrows_walk_the_values(root):
    spin = Spinbox(root, name="s", values=SIZES)
    spin.invoke("buttonup")
    assert spin.get() == "medium"
    spin.invoke("buttonup")
    assert spin.get() == "large"
    spin.invoke("buttondown")
    assert spin.get() == "medium"


def test_the_values_stop_at_the_ends(root):
    spin = Spinbox(root, name="s", values=SIZES)
    for _ in range(5):
        spin.invoke("buttonup")
    assert spin.get() == "large"
    for _ in range(5):
        spin.invoke("buttondown")
    assert spin.get() == "small"


def test_the_values_wrap_when_asked_to(root):
    spin = Spinbox(root, name="s", values=SIZES, wrap=True)
    spin.invoke("buttondown")
    assert spin.get() == "large"
    spin.invoke("buttonup")
    assert spin.get() == "small"


def test_values_given_as_a_string_are_split(root):
    """A Tcl list arriving through the option database is one string."""
    spin = Spinbox(root, name="s", values="small medium large")
    spin.invoke("buttonup")
    assert spin.get() == "medium"


def test_contents_outside_the_values_step_to_an_end(root):
    """Either arrow has to be a way out of a value that is not on the list."""
    spin = Spinbox(root, name="s", values=SIZES)
    spin.delete(0, "end")
    spin.insert(0, "enormous")
    spin.invoke("buttonup")
    assert spin.get() == "small"
    spin.delete(0, "end")
    spin.insert(0, "enormous")
    spin.invoke("buttondown")
    assert spin.get() == "large"


def test_the_arrows_count_by_the_increment(root):
    spin = Spinbox(root, name="s", from_=0, to=10, increment=2)
    spin.invoke("buttonup")
    assert spin.get() == "2"


def test_a_number_stops_at_the_end_of_its_range(root):
    spin = Spinbox(root, name="s", from_=0, to=3)
    for _ in range(6):
        spin.invoke("buttonup")
    assert spin.get() == "3"


def test_a_number_wraps_when_asked_to(root):
    spin = Spinbox(root, name="s", from_=0, to=3, wrap=True)
    spin.invoke("buttondown")
    assert spin.get() == "3"
    spin.invoke("buttonup")
    assert spin.get() == "0"


def test_a_from_above_to_is_swapped_as_tk_swaps_it(root):
    """Measured on Tk 9.0.2: from 0.0, to 10.0, starting at 0, up to 1."""
    spin = Spinbox(root, name="s", from_=10, to=0)
    assert (float(spin.cget("from")), float(spin.cget("to"))) == (0.0, 10.0)
    assert spin.get() == "0"
    spin.invoke("buttonup")
    assert spin.get() == "1"


def test_configuring_from_above_to_swaps_and_clamps(root):
    spin = Spinbox(root, name="s", from_=0, to=10)
    spin.configure(from_=20)
    assert (float(spin.cget("from")), float(spin.cget("to"))) == (10.0, 20.0)
    assert spin.get() == "10"


#: (from, to, increment) and the text after none, one and two steps up,
#: measured on Tk 9.0.2's classic spinbox. tkEntry.c's ComputeFormat: as
#: many decimals as multiples of the increment need, %e when shorter, and
#: each step reads the text it shows - 1.5 from 0 shows 2, then 4.
CLASSIC_FORMATS = [
    ((1, 10, 0.5), ["1.0", "1.5", "2.0"]),
    ((0, 10, 0.25), ["0.0", "0.2", "0.5"]),
    ((0, 1000, 0.001), ["0.000", "0.001", "0.002"]),
    ((0, 10, 1), ["0", "1", "2"]),
    ((0, 100, 2.0), ["0", "2", "4"]),
    ((0, 1, 0.05), ["0.00", "0.05", "0.10"]),
    ((-5, 5, 0.5), ["-5.0", "-4.5", "-4.0"]),
    ((0, 1e6, 0.5), ["0.0", "0.5", "1.0"]),
    ((0, 10, 1.5), ["0", "2", "4"]),
    ((0, 0.001, 0.0001), ["0.0000", "0.0001", "0.0002"]),
    ((0, 1e-6, 1e-8), ["0.00e+00", "1.00e-08", "2.00e-08"]),
    ((0.5, 10, 1), ["0", "1", "2"]),
    ((0, 10, 0.125), ["0.0", "0.1", "0.2"]),
]


@pytest.mark.parametrize("arguments, expected", CLASSIC_FORMATS)
def test_numbers_are_shown_in_tks_computed_format(root, arguments, expected):
    low, high, increment = arguments
    spin = Spinbox(root, name="s", from_=low, to=high, increment=increment)
    seen = [spin.get()]
    for _ in range(2):
        spin.invoke("buttonup")
        seen.append(spin.get())
    assert seen == expected


#: (label, text, direction, options) and what one step gives, measured on Tk
#: 9.0.2 for the classic spinbox and for ttk's.
STEPS = [
    (
        "overshoot up",
        "9.9",
        1,
        {"from_": 0, "to": 10, "increment": 0.3},
        "10.0",
        "10.0",
    ),
    (
        "overshoot down",
        "0.1",
        -1,
        {"from_": 0, "to": 10, "increment": 0.3},
        "0.0",
        "0.0",
    ),
    ("at the top", "10", 1, {"from_": 0, "to": 10}, "10", "10"),
    ("wrap from the top", "10", 1, {"from_": 0, "to": 10, "wrap": True}, "0", "0"),
    (
        "overshoot wraps",
        "9.9",
        1,
        {"from_": 0, "to": 10, "increment": 0.3, "wrap": True},
        "0.0",
        "0.0",
    ),
    ("wrap from the bottom", "0", -1, {"from_": 0, "to": 10, "wrap": True}, "10", "10"),
    ("not a number", "abc", 1, {"from_": 2, "to": 10}, "2", "2"),
    ("not a number down", "abc", -1, {"from_": 2, "to": 10}, "2", "2"),
    ("empty", "", 1, {"from_": 2, "to": 10}, "2", "2"),
    ("below the range", "-5", 1, {"from_": 2, "to": 10}, "2", "2"),
    ("above the range", "50", -1, {"from_": 2, "to": 10}, "10", "10"),
    ("reversed, up", "5", 1, {"from_": 10, "to": 0}, "6", "10"),
    ("reversed, down", "5", -1, {"from_": 10, "to": 0}, "4", "10"),
    ("a leading number", "3abc", 1, {"from_": 0, "to": 10}, "4", "4"),
    ("an empty range", "5", 1, {"from_": 0, "to": 0}, "5", "0"),
]


def _holding(spin, text):
    spin.delete(0, "end")
    spin.insert(0, text)
    return spin


@pytest.mark.parametrize(
    "text, direction, options, classic",
    [pytest.param(*case[1:5], id=case[0]) for case in STEPS],
)
def test_a_classic_step_goes_where_tks_goes(root, text, direction, options, classic):
    spin = _holding(Spinbox(root, name="s", **options), text)
    spin.invoke("buttonup" if direction > 0 else "buttondown")
    assert spin.get() == classic


@pytest.mark.parametrize(
    "text, direction, options, themed",
    [pytest.param(*case[1:4], case[5], id=case[0]) for case in STEPS],
)
def test_a_themed_step_goes_where_ttks_goes(root, text, direction, options, themed):
    spin = _holding(ttk.Spinbox(root, name="s", **options), text)
    spin._step(direction)
    assert spin.get() == themed


#: ttk::spinbox::FormatValue: %.Nf from an increment below 1, %.0f above,
#: measured on Tk 9.0.2.
@pytest.mark.parametrize(
    "increment, expected",
    [
        (0.5, ["1", "1.5", "2.0"]),
        (0.25, ["1", "1.2", "1.4"]),
        (0.001, ["1", "1.001", "1.002"]),
        (2.0, ["1", "3", "5"]),
    ],
)
def test_a_themed_spinbox_formats_as_ttk_does(root, increment, expected):
    spin = _holding(
        ttk.Spinbox(root, name="s", from_=0, to=10, increment=increment), "1"
    )
    seen = [spin.get()]
    for _ in range(2):
        spin._step(1)
        seen.append(spin.get())
    assert seen == expected


def test_a_whole_increment_shows_no_decimal_point(root):
    spin = Spinbox(root, name="s", from_=0, to=5, increment=1)
    spin.invoke("buttonup")
    assert spin.get() == "1"


def test_a_format_is_honoured(root):
    spin = Spinbox(root, name="s", from_=0, to=5, format="%0.2f")
    spin.invoke("buttonup")
    assert spin.get() == "1.00"


def test_rubbish_typed_in_steps_back_onto_the_scale(root):
    spin = Spinbox(root, name="s", from_=4, to=9)
    spin.delete(0, "end")
    spin.insert(0, "hello")
    spin.invoke("buttonup")
    assert spin.get() == "4"


def test_a_range_of_no_width_does_not_move(root):
    """Tk's default from_ and to are both zero: it starts empty, and the
    arrows do nothing. Measured on Tk 9.0.2."""
    spin = Spinbox(root, name="s")
    spin.invoke("buttonup")
    assert spin.get() == ""


def test_an_unknown_element_is_refused(root):
    with pytest.raises(TclError, match="buttondown or buttonup"):
        Spinbox(root, name="s", values=SIZES).invoke("middle")


# ------------------------------------------------------------------ command


def test_the_command_runs_on_every_step(root):
    calls = []
    spin = Spinbox(root, name="s", values=SIZES, command=lambda: calls.append(1))
    spin.invoke("buttonup")
    spin.invoke("buttondown")
    assert calls == [1, 1]


# ----------------------------------------------------------------- variable


def test_stepping_writes_the_textvariable(root):
    variable = StringVar(root, "")
    spin = Spinbox(root, name="s", values=SIZES, textvariable=variable)
    spin.invoke("buttonup")
    assert variable.get() == "medium"


def test_writing_the_variable_moves_the_spinbox(root):
    variable = StringVar(root, "small")
    spin = Spinbox(root, name="s", values=SIZES, textvariable=variable)
    variable.set("large")
    assert spin.get() == "large"


# -------------------------------------------------------------------- state


def test_a_readonly_spinbox_still_steps(root):
    """The state that makes a spinbox a chooser: arrows yes, typing no."""
    spin = Spinbox(root, name="s", values=SIZES, state="readonly")
    spin.invoke("buttonup")
    assert spin.get() == "medium"
    spin._handle(KeyEvent(keysym="x", char="x"))
    assert spin.get() == "medium"


def test_a_disabled_spinbox_does_not_step(root):
    spin = Spinbox(root, name="s", values=SIZES, state="disabled")
    spin.invoke("buttonup")
    assert spin.get() == "small"


def test_a_validator_can_refuse_a_step(root):
    spin = Spinbox(
        root,
        name="s",
        values=SIZES,
        validate="key",
        validatecommand=lambda proposed: proposed != "medium",
    )
    spin.invoke("buttonup")
    assert spin.get() == "small"


# ----------------------------------------------------------------- keyboard


def test_up_and_down_step(root):
    spin = Spinbox(root, name="s", values=SIZES)
    spin._handle(KeyEvent(keysym="Up"))
    assert spin.get() == "medium"
    spin._handle(KeyEvent(keysym="Down"))
    assert spin.get() == "small"


def test_typing_still_reaches_the_field(root):
    spin = Spinbox(root, name="s", from_=0, to=9)
    spin.delete(0, "end")
    spin._handle(KeyEvent(keysym="7", char="7"))
    assert spin.get() == "7"


def test_the_entry_editing_keys_still_work(root):
    spin = Spinbox(root, name="s", values=SIZES)
    spin._handle(KeyEvent(keysym="End"))
    spin._handle(KeyEvent(keysym="BackSpace"))
    assert spin.get() == "smal"


def test_a_spinbox_takes_the_focus(root):
    assert Spinbox(root, name="s")._takefocus is True


# -------------------------------------------------------------------- mouse


def test_clicking_the_up_arrow_steps_up(root):
    spin = laid_out(Spinbox(root, name="s", values=SIZES, width=10))
    column = spin._arrow_columns()[0]
    spin._handle(MouseEvent(button=1, state="pressed", x=column, y=0))
    spin._handle(MouseEvent(button=1, state="released", x=column, y=0))
    assert spin.get() == "medium"


def test_clicking_the_down_arrow_steps_down(root):
    spin = laid_out(Spinbox(root, name="s", values=SIZES, width=10, wrap=True))
    column = spin._arrow_columns()[1]
    spin._handle(MouseEvent(button=1, state="pressed", x=column, y=0))
    spin._handle(MouseEvent(button=1, state="released", x=column, y=0))
    assert spin.get() == "large"


def test_clicking_the_field_places_the_cursor_instead(root):
    spin = laid_out(Spinbox(root, name="s", values=SIZES, width=10))
    # One row tall, so there is no room for a border and none is drawn:
    # the text starts at column 0 and column 2 is the third character.
    spin._handle(MouseEvent(button=1, state="pressed", x=2, y=0))
    assert spin.get() == "small"
    assert spin.index("insert") == 2


def test_identify_names_the_three_parts(root):
    spin = laid_out(Spinbox(root, name="s", values=SIZES, width=10))
    up, down = spin._arrow_columns()
    assert spin.identify(up, 0) == "buttonup"
    assert spin.identify(down, 0) == "buttondown"
    assert spin.identify(0, 0) == "entry"
    assert spin.identify(99, 0) == "none"


def test_identify_takes_coordinates_within_the_widget(root):
    spin = Spinbox(root, name="s", values=SIZES, width=10)
    spin._allocate(Rect(7, 5, 14, 1))
    spin._map()
    assert spin.identify(0, 0) == "entry"
    assert spin.identify(*[spin._arrow_columns()[0], 0]) == "buttonup"


# ----------------------------------------------------------------- geometry


def test_a_spinbox_asks_for_room_for_its_arrows(root):
    """Everything an Entry of the same width asks for, plus the two arrows."""
    entry = Entry(root, name="a", width=10)
    spin = Spinbox(root, name="b", width=10)
    assert spin._requested.width == entry._requested.width + Spinbox._ARROW_WIDTH


def test_the_text_area_stops_before_the_arrows(root):
    spin = laid_out(Spinbox(root, name="s", width=10), width=12)
    entry = laid_out(Entry(root, name="e", width=10), width=12)
    assert spin._text_area().width == entry._text_area().width - Spinbox._ARROW_WIDTH


# ------------------------------------------------- what values, from and to
#
# What configuring values, from or to puts in the field, which Tk's manual
# does not say. Every expectation below was measured with tkinter on Tk
# 9.0.2 - TkCurses-fdl9, which began as a Spinbox() showing 0 where Tk's is
# empty. Construction is the first configure, from no values and 0 to 0.


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({}, ""),
        ({"from_": 0, "to": 0}, ""),
        ({"from_": 0, "to": 10}, "0"),
        ({"to": 10}, "0"),
        ({"from_": -5, "to": 0}, "-5"),
        ({"from_": 2.5, "to": 10}, "2"),
        ({"from_": 0, "to": 10, "format": "%05.2f"}, "00.00"),
        ({"values": ()}, ""),
        ({"values": ("a", "b")}, "a"),
        ({"values": ("",)}, ""),
        ({"values": ("a",), "from_": 0, "to": 10}, "a"),
        ({"from_": 0, "to": 10, "state": "readonly"}, "0"),
        ({"from_": 0, "to": 10, "state": "disabled"}, "0"),
        (
            {"from_": 0, "to": 10, "validate": "all", "validatecommand": lambda: False},
            "0",
        ),
    ],
)
def test_a_new_spinbox_starts_as_tks_does(root, options, expected):
    assert Spinbox(root, **options).get() == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("x", "0"), ("", "0"), ("5", "5"), ("50", "10")],
)
def test_a_range_overwrites_a_textvariable(root, value, expected):
    """Its number clamped into the range, and the variable written too."""
    variable = StringVar(root, value)
    spin = Spinbox(root, textvariable=variable, from_=0, to=10)
    assert spin.get() == expected
    assert variable.get() == expected


def test_no_range_leaves_a_textvariable_alone(root):
    variable = StringVar(root, "")
    assert Spinbox(root, textvariable=variable).get() == ""


def configured(root, start, construct, change):
    spin = Spinbox(root, **construct)
    spin.delete(0, "end")
    spin.insert(0, start)
    spin.configure(**change)
    return spin.get()


@pytest.mark.parametrize(
    ("start", "construct", "change", "expected"),
    [
        ("5", {"from_": 0, "to": 10}, {"to": 20}, "5"),
        ("15", {"from_": 0, "to": 20}, {"to": 10}, "10"),
        ("abc", {"from_": 0, "to": 10}, {"to": 20}, "0"),
        ("5", {"from_": 0, "to": 10}, {"from_": 6}, "6"),
        ("5", {"from_": 0, "to": 10}, {"from_": 0}, "5"),
        ("abc", {"from_": 0, "to": 10}, {"from_": 0, "to": 10}, "abc"),
        ("5", {"from_": 0, "to": 10, "format": "%05.2f"}, {"to": 20}, "05.00"),
        ("5", {"from_": 0, "to": 10}, {"from_": 0, "to": 0}, "5"),
        ("", {}, {"from_": 0, "to": 10}, "0"),
        ("", {"from_": 0, "to": 10}, {"from_": 3, "to": 10}, "3"),
        ("5.7", {"from_": 0, "to": 10}, {"to": 20}, "6"),
        (" 5", {"from_": 0, "to": 10}, {"to": 20}, "5"),
        ("5abc", {"from_": 0, "to": 10}, {"to": 20}, "5"),
        ("05", {"from_": 0, "to": 10}, {"increment": 2}, "05"),
        ("b", {"values": ("a", "b")}, {"values": ("a", "b", "c")}, "a"),
        ("b", {"values": ("a", "b")}, {"values": ("a", "b")}, "a"),
        ("z", {"values": ("a", "b")}, {"from_": 1, "to": 9}, "z"),
        ("b", {"values": ("a", "b")}, {"values": ()}, "b"),
        ("b", {"values": ("a", "b")}, {"values": (), "from_": 0, "to": 10}, "0"),
        ("7", {"from_": 0, "to": 10}, {"values": ("",)}, ""),
        ("0", {"from_": 0, "to": 10}, {"values": ("c", "d")}, "c"),
    ],
)
def test_configure_sets_the_text_as_tks_does(root, start, construct, change, expected):
    assert configured(root, start, construct, change) == expected


def test_configure_through_cnf_counts_too(root):
    spin = Spinbox(root, values=("a", "b"))
    spin.delete(0, "end")
    spin.insert(0, "b")
    spin.configure({"values": ("c", "d")})
    assert spin.get() == "c"


@pytest.mark.parametrize(
    "options", [{}, {"from_": 0, "to": 10}, {"from_": 3, "to": 10}, {"values": SIZES}]
)
def test_a_ttk_spinbox_starts_empty(root, options):
    """Measured: ttk's never fills itself in, whatever it is given."""
    from tkcurses import ttk

    assert ttk.Spinbox(root, **options).get() == ""


@pytest.mark.parametrize(
    ("start", "construct", "change"),
    [
        ("b", {"values": ("a", "b")}, {"values": ("c", "d")}),
        ("abc", {"from_": 0, "to": 10}, {"to": 20}),
        ("50", {"from_": 0, "to": 10}, {"to": 20}),
    ],
)
def test_a_ttk_spinbox_keeps_its_text_when_configured(root, start, construct, change):
    from tkcurses import ttk

    spin = ttk.Spinbox(root, **construct)
    spin.insert(0, start)
    spin.configure(**change)
    assert spin.get() == start


#: ttk.Spinbox's from, to and increment read back as written, measured on
#: Tk 9.0.2: an integer wherever the text is one, a float otherwise.
AS_GIVEN = [
    (10, 10), ("10", 10), (" 10", 10), ("0x10", 16),
    (2.5, 2.5), ("1e1", 10.0), (10.0, 10.0),
]  # fmt: skip


@pytest.mark.parametrize("option", ["from", "to", "increment"])
@pytest.mark.parametrize("value, expected", AS_GIVEN)
def test_a_themed_spinbox_reads_its_numbers_back_as_given(option, value, expected):
    import tkcurses
    from tkcurses import ttk

    key = "from_" if option == "from" else option
    got = ttk.Spinbox(tkcurses.Misc(), **{key: value}).cget(option)
    assert (got, type(got)) == (expected, type(expected))


def test_a_classic_spinbox_reads_them_back_as_floats():
    import tkcurses

    got = tkcurses.Spinbox(tkcurses.Misc(), from_=1, to=10).cget("to")
    assert (got, type(got)) == (10.0, float)


def test_a_themed_spinbox_steps_on_increment_and_decrement():
    import tkcurses
    from tkcurses import ttk

    spin = ttk.Spinbox(tkcurses.Misc(), from_=0, to=5)
    spin.set(1)
    spin.event_generate("<<Increment>>")
    assert spin.get() == "2"
    spin.event_generate("<<Decrement>>")
    spin.event_generate("<<Decrement>>")
    spin.event_generate("<<Decrement>>")
    assert spin.get() == "0"


def test_the_up_key_steps_through_increment():
    """So a program's own ``<<Increment>>`` binding sees the key, and can stop it."""
    import tkcurses
    from tkcurses import ttk

    spin = ttk.Spinbox(tkcurses.Misc(), from_=0, to=5)
    spin.set(1)
    heard = []
    spin.bind("<<Increment>>", lambda event: heard.append(event) or "break")
    spin.event_generate("<Key-Up>")
    assert len(heard) == 1
    assert spin.get() == "1"
    spin.unbind("<<Increment>>")
    spin.event_generate("<Key-Up>")
    assert spin.get() == "2"


# ----------------------------------------- selection, element and scan, Tk's


def test_the_selection_element_is_none_until_one_is_named(root):
    spin = Spinbox(root, from_=0, to=9)
    assert spin.selection_element() == "none"
    assert spin.selection("element") == "none"
    spin.selection_element("buttonup")
    assert spin.selection_element() == "buttonup"
    assert spin._arrow_relief("buttonup") == "sunken"
    assert spin._arrow_relief("buttondown") == "raised"


@pytest.mark.parametrize(
    "name, message",
    [
        ("nonsense", 'bad selection element "nonsense": must be buttondown, buttonup, or none'),
        ("", 'ambiguous selection element "": must be buttondown, buttonup, or none'),
    ],
)  # fmt: skip
def test_a_selection_element_tk_lacks_is_refused(root, name, message):
    with pytest.raises(TclError) as caught:
        Spinbox(root).selection_element(name)
    assert str(caught.value) == message


def test_pressing_an_arrow_makes_it_the_selection_element(root):
    """tk::spinbox::ArrowPress names it; ButtonUp names none."""
    spin = laid_out(Spinbox(root, from_=0, to=9), width=14)
    up = spin._arrow_columns()[0]
    spin._handle(MouseEvent(button=1, state="pressed", x=up, y=0))
    assert spin.selection_element() == "buttonup"
    spin._handle(MouseEvent(button=1, state="released", x=up, y=0))
    assert spin.selection_element() == "none"


def test_selection_is_the_command_behind_the_named_forms(root):
    spin = Spinbox(root)
    spin.insert(0, "12345")
    assert spin.selection("range", 1, 3) == ()
    assert spin.selection("present") == (1,)
    assert spin.selection_get() == "23"
    spin.selection("clear")
    assert spin.selection("present") == (0,)
    with pytest.raises(TclError, match='bad selection option "nonsense": must be'):
        spin.selection("nonsense")


def test_scan_drags_the_view_ten_times_as_far(root):
    """Measured on Tk 9.0.2, a field five wide holding a-z: a mark at 10 and
    drags to 9, 12, -100 and -99 show 10, 0, 21 and 11 first - the mark
    moving with the pointer at either end, as EntryScanTo moves it."""
    entry = Entry(root, width=5)
    entry._allocate(Rect(0, 0, 5, 1))
    entry._map()
    entry.insert(0, "abcdefghijklmnopqrstuvwxyz")
    entry.xview(0)
    entry.scan_mark(10)
    seen = []
    for x in (9, 12, -100, -99):
        entry.scan_dragto(x)
        seen.append(entry.index("@0"))
    assert seen == [10, 0, 21, 11]
    spin = Spinbox(root)
    assert spin.scan("mark", 3) == ()
    with pytest.raises(TclError, match='bad scan option "x": must be dragto or mark'):
        spin.scan("x", 1)
