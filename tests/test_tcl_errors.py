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

"""A bad value is a TclError, with Tk's words, and a good one is taken.

A program written against tkinter catches ``TclError``; anything else raised
for a bad index or a bad option crashes it instead. Every expectation here was
measured through tkinter on Python 3.14 over Tk 9.0.2. TkCurses-g7nf (Text
indices), TkCurses-vgkb (option values).
"""

from __future__ import annotations

import contextlib
import math

import pytest

import tkcurses
from tkcurses import Misc, TclError, Text, ttk
from tkcurses._core.geometry import Rect


@contextlib.contextmanager
def refused(message):
    """Raises a TclError saying exactly this - compared, not matched."""
    with pytest.raises(TclError) as caught:
        yield
    assert str(caught.value) == message


@pytest.fixture
def root():
    root = Misc()
    root._rect = Rect(0, 0, 40, 10)
    root._mapped = True
    return root


@pytest.fixture
def text(root):
    widget = Text(root, name="t")
    widget.insert("1.0", "abc\ndef")
    return widget


# ------------------------------------------------------------ Text indices


def test_a_good_modifier_after_a_cell_still_applies(text):
    assert text.index("@0,0 +1c") == "1.1"


@pytest.mark.parametrize(
    "index",
    [
        "nomark",
        "",
        "1.0 +3 bogus",
        "1.0+xc",
        "t.first",
        "nomark+1c",
        "zz lineend",
        "5.x",
        "1.0 + 2 lines bogus",
        "insert wordstart bogus",
        "end-1c+",
        "@a,b",
        "@3",
        "@3,",
        "@0,0 bogus",
        "@0,0 +zc",
    ],
)
def test_a_bad_index_is_quoted_whole_whatever_part_is_wrong(text, index):
    with refused(f'bad text index "{index}"'):
        text.index(index)


def test_a_tag_that_covers_nothing_says_so(text):
    text.tag_configure("t")
    with refused('text doesn\'t contain any characters tagged with "t"'):
        text.index("t.first")


def test_a_tag_emptied_by_removal_says_so_too(text):
    text.tag_add("t", "1.0", "1.2")
    text.tag_remove("t", "1.0", "end")
    with pytest.raises(TclError, match="doesn't contain any characters tagged"):
        text.index("t.last")


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (
            lambda t: t.compare("1.0", "<>", "2.0"),
            'bad comparison operator "<>": must be <, <=, ==, >=, >, or !=',
        ),
        (lambda t: t.mark_gravity("nomark"), 'there is no mark named "nomark"'),
        (
            lambda t: (t.mark_set("m", "1.0"), t.mark_gravity("m", "up")),
            'bad mark gravity "up": must be left or right',
        ),
    ],
)
def test_the_other_text_errors_use_tks_words(text, call, message):
    with refused(message):
        call(text)


@pytest.mark.parametrize(
    "call",
    [
        lambda t: t.get("zz"),
        lambda t: t.insert("zz", "a"),
        lambda t: t.delete("zz"),
        lambda t: t.tag_add("t", "zz"),
        lambda t: t.mark_set("m", "zz"),
        lambda t: t.see("zz"),
        lambda t: t.search("a", "zz"),
    ],
)
def test_every_method_taking_an_index_refuses_it_as_a_tclerror(text, call):
    with refused('bad text index "zz"'):
        call(text)


# ------------------------------------------------------- Tcl's number syntax


@pytest.mark.parametrize(
    ("value", "number"),
    [
        ("1_0", 10),
        ("1__0", 10),
        ("0x10", 16),
        ("0x1_0", 16),
        ("-0x10", -16),
        ("0o17", 15),
        ("0b11", 3),
        (" 7 ", 7),
        ("+3", 3),
        ("1e2", 100.0),
        ("3.", 3.0),
        (".5", 0.5),
        ("inf", math.inf),
        ("-inf", -math.inf),
        ("0X10", 16),
        ("0B11", 3),
        ("0O17", 15),
        ("1E2", 100.0),
        ("INF", math.inf),
        ("Infinity", math.inf),
        (True, 1),
        (False, 0),
        ("_1", None),
        ("1_", None),
        (chr(0x661), None),  # ARABIC-INDIC DIGIT ONE: a digit to Python's \d
        ("abc", None),
        ("", None),
    ],
)
def test_a_number_is_read_as_tcl_9_reads_one(value, number):
    assert tkcurses._tcl_number(value) == number
    assert type(tkcurses._tcl_number(value)) is type(number)


def test_nan_is_a_number_each_caller_names(root):
    assert math.isnan(tkcurses._tcl_number("nan"))
    with refused("floating point value is Not a Number"):
        tkcurses.Scale(root, from_="nan")
    with refused("floating point value is Not a Number"):
        Text(root, undo="nan")
    with refused('expected screen distance but got "nan"'):
        tkcurses.Frame(root, width="nan")


@pytest.mark.parametrize(
    ("make", "option", "value", "read_back"),
    [
        (tkcurses.Button, "width", "0x10", 16),
        (tkcurses.Button, "width", "1_0", 10),
        (tkcurses.Scale, "from", "1e2", 100.0),
        (tkcurses.Scale, "from", "0x10", 16.0),
        (tkcurses.Frame, "width", "1e2", 100),
        (tkcurses.Frame, "width", "inf", 0),
        (tkcurses.Button, "width", True, 1),
        (tkcurses.Frame, "width", True, 1),
        (Text, "undo", "2.5", 1),
        (Text, "undo", "0x10", 1),
        (Text, "undo", "0.0", 0),
        (ttk.Treeview, "striped", "2.5", 1),
    ],
)
def test_what_tcl_reads_as_a_number_is_taken(root, make, option, value, read_back):
    keyword = "from_" if option == "from" else option
    got = make(root, **{keyword: value}).cget(option)
    assert got == read_back
    assert type(got) is type(read_back)  # True reads back 1, as in Tk


# ---------------------------------------------- what an option's value means


@pytest.mark.parametrize(
    "make",
    [
        tkcurses.Button,
        tkcurses.Checkbutton,
        tkcurses.Entry,
        tkcurses.Label,
        tkcurses.Listbox,
        tkcurses.Menubutton,
        tkcurses.Radiobutton,
        tkcurses.Spinbox,
        Text,
        ttk.Combobox,
        ttk.Entry,
        ttk.Spinbox,
        ttk.Panedwindow,
    ],
)
@pytest.mark.parametrize("value", ["abc", "2.5"])
def test_a_width_in_characters_is_an_integer(root, make, value):
    with refused(f'expected integer but got "{value}"'):
        make(root, width=value)


@pytest.mark.parametrize(
    "make",
    [
        tkcurses.Canvas,
        tkcurses.Frame,
        tkcurses.LabelFrame,
        tkcurses.Message,
        tkcurses.Scale,
        tkcurses.Scrollbar,
        tkcurses.Toplevel,
        ttk.Frame,
        ttk.Labelframe,
        ttk.Notebook,
    ],
)
def test_a_width_in_pixels_is_a_screen_distance(root, make):
    with refused('expected screen distance but got "abc"'):
        make(root, width="abc")
    make(root, width="2.5")


@pytest.mark.parametrize(
    ("make", "option"),
    [
        (tkcurses.Text, "height"),
        (ttk.Treeview, "height"),
        (tkcurses.Scale, "length"),
        (ttk.Progressbar, "length"),
        (ttk.Scale, "length"),
        (tkcurses.Label, "padx"),
        (tkcurses.Text, "pady"),
        (tkcurses.Button, "wraplength"),
    ],
)
def test_the_other_pixel_sizes_are_screen_distances(root, make, option):
    with refused('expected screen distance but got "abc"'):
        make(root, **{option: "abc"})
    make(root, **{option: "2.5"})


@pytest.mark.parametrize(
    ("make", "option"),
    [
        (tkcurses.Message, "padx"),
        (tkcurses.Message, "pady"),
        (ttk.Label, "wraplength"),
        (tkcurses.Scrollbar, "elementborderwidth"),
    ],
)
def test_some_sizes_may_also_be_empty(root, make, option):
    with refused('expected screen distance or "" but got "abc"'):
        make(root, **{option: "abc"})
    make(root, **{option: ""})


@pytest.mark.parametrize(
    ("make", "option"),
    [
        (tkcurses.Scale, "from"),
        (tkcurses.Scale, "to"),
        (tkcurses.Scale, "resolution"),
        (tkcurses.Scale, "tickinterval"),
        (tkcurses.Spinbox, "from"),
        (tkcurses.Spinbox, "increment"),
        (ttk.Scale, "to"),
        (ttk.Spinbox, "from"),
    ],
)
def test_a_range_is_floating_point(root, make, option):
    keyword = "from_" if option == "from" else option
    with refused('expected floating-point number but got "abc"'):
        make(root, **{keyword: "abc"})


def test_scale_digits_is_an_integer(root):
    with refused('expected integer but got "2.5"'):
        tkcurses.Scale(root, digits="2.5")


@pytest.mark.parametrize(
    "make", [ttk.Button, ttk.Checkbutton, ttk.Label, ttk.Menubutton, ttk.Radiobutton]
)
def test_a_ttk_labels_width_is_not_checked_at_all(root, make):
    """Tk keeps ``abc`` and reads it back; the label is sized by its text."""
    widget = make(root, text="hello", width="abc")
    assert widget.cget("width") == "abc"
    assert widget.winfo_reqwidth() > 0


@pytest.mark.parametrize(
    ("make", "option"),
    [
        (tkcurses.Label, "textvariable"),
        (tkcurses.Entry, "textvariable"),
        (tkcurses.Checkbutton, "variable"),
        (tkcurses.Scale, "variable"),
        (ttk.Label, "textvariable"),
        (ttk.Progressbar, "variable"),
    ],
)
@pytest.mark.parametrize("name", [5, "g"])
def test_a_variable_named_rather_than_given_is_bound(root, make, option, name):
    """Measured on Tk 9.0.2: a name is accepted, binds to the variable of
    that name, and reads back as given."""
    widget = make(root, **{option: name})
    assert widget.cget(option) == str(name)


def test_no_variable_at_all_is_still_none(root):
    assert tkcurses.Label(root, textvariable="").cget("textvariable") is None


# -------------------------------------------------------------------- tabs


@pytest.mark.parametrize(
    ("tabs", "message"),
    [
        ("abc", 'expected screen distance but got "abc"'),
        ("left", 'expected screen distance but got "left"'),
        ("1x", 'expected screen distance but got "1x"'),
        ("-3", 'tab stop "-3" is not at a positive distance'),
        ("0", 'tab stop "0" is not at a positive distance'),
        (
            "5 3",
            'tabs must be monotonically increasing, but "3" is smaller than or'
            " equal to the previous tab",
        ),
        (
            "5 bogus",
            'bad tab alignment "bogus": must be left, right, center, or numeric',
        ),
    ],
)
def test_a_bad_tab_list_is_refused_in_tks_words(text, tabs, message):
    with pytest.raises(TclError) as caught:
        text.configure(tabs=tabs)
    assert str(caught.value) == message


@pytest.mark.parametrize("value", ["abc", "1x", ""])
def test_winfo_fpixels_refuses_in_tks_words(root, value):
    with pytest.raises(TclError) as caught:
        root.winfo_fpixels(value)
    assert str(caught.value) == f'expected screen distance or "" but got "{value}"'
