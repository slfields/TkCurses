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

"""Double-, triple- and shift-click selection, and autoscroll, in Entry and Text.

Every expectation was MEASURED on Tk 9.0.2 by calling Tk's own procedures
(tk::EntryMouseSelect, ttk::entry::Select and DragTo, tk::TextSelectTo and
the rest) with the pointer just inside a character's left edge, which is
where a terminal cell puts it. Driven here through real mouse events, so the
binding engine's choice between <Button-1>, <Double-Button-1> and
<Shift-Button-1> is under test too. TkCurses-svtr.
"""

from __future__ import annotations

import unicodedata
from types import SimpleNamespace

import pytest

from tkcurses import Entry, Misc, Spinbox, Text, ttk
from tkcurses._core.editing import is_word_char, run_end, run_start
from tkcurses._core.events import MOD_ALT, MOD_CTRL, MOD_SHIFT, KeyEvent, MouseEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(window_factory=stub_window, panel_factory=None)
    root._rect = Rect(0, 0, 80, 24)
    root._mapped = True
    return root


@pytest.fixture(params=[MOD_SHIFT, MOD_ALT], ids=["shift", "alt"])
def extend(request):
    """Shift-click is Tk's; Alt-click is ours too, because VTE terminals never
    send a Shift-click at all (measured). Every extend test runs with both."""
    return request.param


def placed(widget, rect=None):
    widget._allocate(rect or Rect(0, 0, 42, 3))
    widget._map()
    return widget


def mouse(widget, state, x, y=1, modifiers=0, button=1):
    widget._handle(
        MouseEvent(button=button, state=state, x=x, y=y, modifiers=modifiers)
    )


def column(entry, index):
    """The widget column of the character at ``index`` in an entry."""
    return entry._text_area().x + index


def double(entry, index, modifiers=0):
    """A first click, then the second one - as the decoder reports them."""
    x = column(entry, index)
    mouse(entry, "pressed", x, modifiers=modifiers)
    mouse(entry, "released", x, modifiers=modifiers)
    mouse(entry, "double", x, modifiers=modifiers)


def triple(entry, index):
    double(entry, index)
    x = column(entry, index)
    mouse(entry, "released", x)
    mouse(entry, "triple", x)


def state(entry):
    return entry._field.selection, entry.index("insert")


# ------------------------------------------------------------------- words

SAMPLE = "hello, world  foo_bar-baz 42.5 é!"

#: What Tk selects double-clicking each character of SAMPLE, measured.
SAMPLE_WORDS = (
    ["hello"] * 5
    + [", "] * 2
    + ["world"] * 5
    + ["  "] * 2
    + ["foo_bar"] * 7
    + ["-"]
    + ["baz"] * 3
    + [" "]
    + ["42"] * 2
    + ["."]
    + ["5"]
    + [" "]
    + ["é"]
    + ["!"]
)


def test_a_run_is_word_characters_or_anything_else():
    got = [
        SAMPLE[run_start(SAMPLE, i) : run_end(SAMPLE, i)] for i in range(len(SAMPLE))
    ]
    assert got == SAMPLE_WORDS


def test_past_either_end_a_run_is_the_nearest_one():
    """As Tcl's string range clamps: past the end means the last run."""
    assert (run_start("one two", 99), run_end("one two", 99)) == (4, 7)
    assert (run_start("one two", -1), run_end("one two", -1)) == (0, 3)
    assert (run_start("", 0), run_end("", 0)) == (0, 0)


@pytest.mark.parametrize(
    ("char", "word"),
    [
        ("a", True),
        ("_", True),
        ("9", True),
        ("é", True),
        ("中", True),
        ("٣", True),  # an Arabic-Indic digit: a decimal digit, Nd
        ("‿", True),  # connector punctuation, Pc - Python's isalnum says no
        ("²", False),  # a number but not a decimal digit - isalnum says yes
        ("½", False),
        ("-", False),
        ("'", False),
        (" ", False),
        ("\n", False),
    ],
)
def test_a_word_character_is_what_tcl_says(char, word):
    """Checked against Tcl 9.0.2's regexp \\w for every code point."""
    assert is_word_char(char) is word, unicodedata.category(char)


# ------------------------------------------------------------ classic Entry


@pytest.fixture
def entry(root):
    widget = placed(Entry(root, name="e", width=40))
    widget.insert(0, SAMPLE)
    widget.focus_set()
    return widget


@pytest.mark.parametrize("index", range(len(SAMPLE)))
def test_a_double_click_selects_the_run_and_puts_the_cursor_after_it(entry, index):
    double(entry, index)
    (first, last), cursor = state(entry)
    assert SAMPLE[first:last] == SAMPLE_WORDS[index]
    assert cursor == last


@pytest.fixture
def words(root):
    widget = placed(Entry(root, name="w", width=40))
    widget.insert(0, "one two three four")
    widget.focus_set()
    return widget


def test_a_drag_after_a_double_click_extends_by_words(words):
    double(words, 5)
    assert state(words) == ((4, 7), 7)
    mouse(words, "drag", column(words, 10))
    assert state(words) == ((4, 13), 10)
    mouse(words, "drag", column(words, 1))
    assert state(words) == ((0, 7), 1)


def test_a_classic_word_drag_onto_a_words_first_letter_stops_before_it(words):
    """Where classic and ttk part company, measured: classic measures to the
    character BEFORE the pointer, so landing on the 't' of 'three' reaches
    only the space. ttk takes the whole word - see the ttk test."""
    double(words, 5)
    mouse(words, "drag", column(words, 8))
    assert state(words) == ((4, 8), 8)
    mouse(words, "drag", column(words, 4))
    assert state(words) == ((4, 7), 4)


def test_a_triple_click_selects_everything(words):
    triple(words, 5)
    assert state(words) == ((0, 18), 18)


def test_a_shift_click_adjusts_the_nearer_end_and_leaves_the_cursor(words, extend):
    """Classic Tk: selection adjust. Measured, from a drag over 'two'."""
    mouse(words, "pressed", column(words, 4))
    mouse(words, "drag", column(words, 7))
    mouse(words, "released", column(words, 7))
    assert state(words) == ((4, 7), 7)
    mouse(words, "pressed", column(words, 14), modifiers=extend)
    assert state(words) == ((4, 14), 7)
    mouse(words, "released", column(words, 14))
    mouse(words, "pressed", column(words, 1), modifiers=extend)
    assert state(words) == ((1, 14), 7)


def test_a_click_then_a_shift_click_selects_between_them(words, extend):
    mouse(words, "pressed", column(words, 2))
    mouse(words, "released", column(words, 2))
    mouse(words, "pressed", column(words, 9), modifiers=extend)
    assert state(words) == ((2, 9), 2)


def test_a_double_shift_click_extends_by_words(words, extend):
    mouse(words, "pressed", column(words, 4))
    mouse(words, "drag", column(words, 7))
    mouse(words, "released", column(words, 7))
    # Both presses of a double-click, as the decoder reports them: the first
    # is a single extend-click, which is what moves the selection's end.
    mouse(words, "pressed", column(words, 10), modifiers=extend)
    mouse(words, "released", column(words, 10), modifiers=extend)
    mouse(words, "double", column(words, 10), modifiers=extend)
    assert words._field.selection == (4, 13)


def test_a_disabled_entry_does_not_select(words):
    words.configure(state="disabled")
    double(words, 5)
    assert words._field.selection is None


def test_a_masked_entry_breaks_words_on_what_it_holds(root):
    """Tk breaks on [$w get], the real text, not the stars it shows."""
    widget = placed(Entry(root, name="m", width=20, show="*"))
    widget.insert(0, "ab cd")
    double(widget, 4)
    assert widget._field.selection == (3, 5)


# ----------------------------------------------------------------- ttk Entry


@pytest.fixture
def tword(root):
    widget = placed(ttk.Entry(root, name="tw", width=40))
    widget.insert(0, "one two three four")
    widget.focus_set()
    return widget


def test_ttk_extends_by_words_from_the_anchor_and_moves_the_cursor_to_the_end(tword):
    """ttk's WordSelect measures from the anchor, classic from the character
    before it - and the cursor goes to the leading end. Measured."""
    double(tword, 5)
    assert state(tword) == ((4, 7), 7)
    mouse(tword, "drag", column(tword, 10))
    assert state(tword) == ((4, 13), 13)
    mouse(tword, "drag", column(tword, 1))
    assert state(tword) == ((0, 7), 0)


def test_ttk_word_drag_onto_a_words_first_letter_takes_the_word(tword):
    double(tword, 5)
    mouse(tword, "drag", column(tword, 8))
    assert state(tword) == ((4, 13), 13)
    mouse(tword, "drag", column(tword, 4))
    assert state(tword) == ((4, 7), 4)


def test_ttk_word_drag_back_from_a_words_first_letter_keeps_that_word(tword):
    """Measured: double-click the 't' of 'two', drag back to 'n' - ttk's
    WordSelect ends at the anchor's own word, classic's at the one before."""
    double(tword, 4)
    mouse(tword, "drag", column(tword, 1))
    assert state(tword) == ((0, 7), 0)


def test_ttk_triple_selects_everything(tword):
    triple(tword, 5)
    assert state(tword) == ((0, 18), 18)


def test_ttk_shift_click_extends_and_moves_the_cursor(tword, extend):
    """ttk::entry::ExtendTo, measured: from the far end, cursor to the click."""
    mouse(tword, "pressed", column(tword, 4))
    mouse(tword, "drag", column(tword, 7))
    mouse(tword, "released", column(tword, 7))
    mouse(tword, "pressed", column(tword, 14), modifiers=extend)
    assert state(tword) == ((4, 14), 14)
    mouse(tword, "released", column(tword, 14))
    mouse(tword, "pressed", column(tword, 1), modifiers=extend)
    assert state(tword) == ((1, 14), 1)


def test_ttk_click_then_shift_click_extends_from_the_cursor(tword, extend):
    mouse(tword, "pressed", column(tword, 2))
    mouse(tword, "released", column(tword, 2))
    mouse(tword, "pressed", column(tword, 9), modifiers=extend)
    assert state(tword) == ((2, 9), 9)


def test_a_combobox_keeps_its_clicks(root):
    """An open-the-list click must not become a word selection. Combobox
    installs its own class bindings, not Entry's; in Tk an editable
    combobox's text takes these clicks as an entry would, which is its own
    issue."""
    box = placed(ttk.Combobox(root, name="cb", values=["one", "two"]))
    box.insert(0, "one two")
    double(box, 5)
    assert box._field.selection is None


# ------------------------------------------------------------------ Spinbox


@pytest.fixture
def spin(root):
    widget = placed(Spinbox(root, name="sp", width=30, from_=0, to=10))
    widget.delete(0, "end")
    widget.insert(0, "hello, world 42")
    widget.focus_set()
    return widget


@pytest.mark.parametrize("index", [0, 5, 6, 7, 8, 12, 13, 14])
def test_a_spinbox_double_click_selects_the_run_with_the_cursor_at_its_start(
    spin, index
):
    """Classic Spinbox puts the cursor at sel.first (measured). Its own copy
    of the word code selects NOTHING on the first character of a run - at
    5, 7, 12 and 13 here, measured - which is a Tk defect and not copied:
    this uses Entry's rule. TkCurses-svtr."""
    text = "hello, world 42"
    double(spin, index)
    (first, last), cursor = state(spin)
    assert text[first:last] == text[run_start(text, index) : run_end(text, index)]
    assert cursor == first


def test_a_spinbox_triple_click_selects_everything_with_the_cursor_at_0(spin):
    triple(spin, 8)
    assert state(spin) == ((0, 15), 0)


def test_a_double_click_on_a_spinbox_arrow_still_steps(root):
    """Tk's double-click binding presses the arrow again: a second step."""
    widget = placed(Spinbox(root, name="st", width=10, from_=0, to=10))
    up, _down = widget._arrow_columns()
    mouse(widget, "pressed", up)
    mouse(widget, "released", up)
    mouse(widget, "double", up)
    assert widget.get() == "2"
    assert widget._field.selection is None


def test_a_ttk_spinbox_double_click_selects_everything(root):
    """ttk::spinbox::DoubleClick calls SelectAll in the text area. Measured."""
    widget = placed(ttk.Spinbox(root, name="ts", width=30, from_=0, to=9))
    widget.delete(0, "end")
    widget.insert(0, "one two three")
    double(widget, 5)
    assert state(widget) == ((0, 13), 13)
    mouse(widget, "released", column(widget, 5))
    mouse(widget, "triple", column(widget, 5))
    assert state(widget) == ((0, 13), 13), "a third click is the double's again"


# --------------------------------------------------------------------- Text


@pytest.fixture
def text(root):
    widget = Text(root, name="t", width=40, height=6, wrap="none")
    placed(widget, Rect(0, 0, 42, 8))
    widget.focus_set()
    return widget


def cell(text, index):
    """The widget cell of a ``line.char`` index in a Text, top-left view."""
    line, char = (int(part) for part in index.split("."))
    area = text._text_area()
    return area.x + char, area.y + line - 1


def tclick(text, index, state="pressed", modifiers=0):
    x, y = cell(text, index)
    mouse(text, state, x, y, modifiers=modifiers)


def tdouble(text, index):
    tclick(text, index)
    tclick(text, index, "released")
    tclick(text, index, "double")


def tsel(text):
    found = text.tag_ranges("sel")
    selected = text.get(found[0], found[1]) if found else None
    return selected, text.index("insert")


def load(text, contents):
    text.delete("1.0", "end")
    text.insert("1.0", contents)


@pytest.mark.parametrize("index", range(len(SAMPLE)))
def test_a_text_double_click_selects_the_run_with_the_cursor_at_its_start(text, index):
    load(text, SAMPLE + "\nsecond line here")
    tdouble(text, f"1.{index}")
    selected, cursor = tsel(text)
    want = SAMPLE_WORDS[index] + ("\n" if index == len(SAMPLE) - 1 else "")
    assert selected == want  # the '!' at the end runs into the newline
    assert cursor == f"1.{run_start(SAMPLE, index)}"


@pytest.mark.parametrize(
    ("index", "want"),
    [
        ("1.3", ("  \n  ", "1.3")),
        ("1.4", ("  \n  ", "1.3")),
        ("2.0", ("  \n  ", "1.3")),
        ("3.0", ("\n\n", "2.5")),
        ("4.1", ("baz", "4.0")),
    ],
)
def test_a_run_crosses_lines_in_a_text(text, index, want):
    """A newline is not a word character, measured on Tk's Text."""
    load(text, "foo  \n  bar\n\nbaz")
    tdouble(text, index)
    assert tsel(text) == want


@pytest.mark.parametrize(
    ("index", "want"),
    [
        ("1.1", ("foo  \n", "1.0")),
        ("2.3", ("  bar\n", "2.0")),
        ("3.0", ("\n", "3.0")),
        ("4.1", ("baz\n", "4.0")),
    ],
)
def test_a_text_triple_click_selects_the_line_and_its_newline(text, index, want):
    load(text, "foo  \n  bar\n\nbaz")
    tdouble(text, index)
    tclick(text, index, "released")
    tclick(text, index, "triple")
    assert tsel(text) == want


def test_a_text_drag_after_a_double_click_extends_by_words(text):
    load(text, "one two three four")
    tdouble(text, "1.5")
    tclick(text, "1.10", "drag")
    assert tsel(text) == ("two three", "1.10")
    tclick(text, "1.1", "drag")
    assert tsel(text) == ("one two", "1.1")


def test_a_text_drag_after_a_triple_click_extends_by_lines(text):
    load(text, "l1\nl2\nl3\nl4")
    tdouble(text, "2.1")
    tclick(text, "2.1", "released")
    tclick(text, "2.1", "triple")
    tclick(text, "3.0", "drag")
    assert tsel(text) == ("l2\nl3\n", "3.0")


def test_a_text_shift_click_moves_the_end_tk_picks(text, extend):
    load(text, "one two three four")
    tclick(text, "1.4")
    tclick(text, "1.7", "drag")
    tclick(text, "1.7", "released")
    assert tsel(text) == ("two", "1.7")
    tclick(text, "1.14", modifiers=extend)
    assert tsel(text) == ("two three ", "1.14")
    tclick(text, "1.14", "released")
    tclick(text, "1.1", modifiers=extend)
    assert tsel(text) == ("ne two three ", "1.1")


def test_a_text_click_then_shift_click_selects_between_them(text, extend):
    load(text, "one two three four")
    tclick(text, "1.2")
    tclick(text, "1.2", "released")
    assert tsel(text) == (None, "1.2")
    tclick(text, "1.9", modifiers=extend)
    assert tsel(text) == ("e two t", "1.9")


def test_a_text_double_shift_click_extends_by_words(text, extend):
    load(text, "one two three four")
    tclick(text, "1.4")
    tclick(text, "1.7", "drag")
    tclick(text, "1.7", "released")
    tclick(text, "1.14", modifiers=extend)
    tclick(text, "1.14", "released", modifiers=extend)
    tclick(text, "1.14", "double", modifiers=extend)
    assert tsel(text)[0] == "two three "


def test_a_shift_click_inside_moves_the_nearer_end(text, extend):
    """tk::TextResetAnchor by character count: 'two three' (9), clicked 2 in."""
    load(text, "one two three four")
    text.tag_add("sel", "1.4", "1.13")
    tclick(text, "1.6", modifiers=extend)
    assert tsel(text) == ("o three", "1.6")


def test_a_disabled_text_still_selects(text):
    """Tk's Text bindings select in a disabled Text; only edits are refused."""
    load(text, "one two")
    text.configure(state="disabled")
    tdouble(text, "1.5")
    assert tsel(text)[0] == "two"


# ------------------------------------------------------------- autoscroll


@pytest.fixture
def clock(root):
    """Move the timer queue's clock by hand."""
    now = [0.0]
    root.tk.timers._clock = lambda: now[0]

    def advance(seconds):
        now[0] += seconds
        root.tk.timers.run_due()

    return advance


def test_a_drag_past_the_right_edge_keeps_scrolling_and_selecting(root, clock):
    widget = placed(Entry(root, name="as", width=10), Rect(0, 0, 12, 3))
    widget.insert(0, "abcdefghijklmnopqrstuvwxyz")
    widget.icursor(0)
    widget.xview("moveto", 0)
    x = widget._text_area().x
    mouse(widget, "pressed", x + 1)
    mouse(widget, "drag", widget.winfo_width() + 1)
    start = widget._field.view
    clock(0.06)
    assert widget._field.view == start + 2, "one tick, two characters"
    clock(0.06)
    assert widget._field.view == start + 4, "and again, with no motion"
    assert widget._field.selection[0] == 1
    assert widget._field.selection[1] > 10
    mouse(widget, "released", widget.winfo_width() + 1)
    assert not len(root.tk.timers), "the release cancels the repeat"
    stopped = widget._field.view
    clock(0.2)
    assert widget._field.view == stopped, "the release stops it"


def test_coming_back_inside_stops_the_scroll(root, clock):
    widget = placed(Entry(root, name="ab", width=10), Rect(0, 0, 12, 3))
    widget.insert(0, "abcdefghijklmnopqrstuvwxyz")
    widget.icursor(0)
    widget.xview("moveto", 0)
    x = widget._text_area().x
    mouse(widget, "pressed", x + 1)
    mouse(widget, "drag", widget.winfo_width() + 1)
    clock(0.06)
    mouse(widget, "drag", x + 3)
    assert not len(root.tk.timers), "coming back cancels the repeat"
    held = widget._field.view
    clock(0.2)
    assert widget._field.view == held


def test_a_text_drag_below_the_bottom_scrolls_by_how_far_past(root, clock):
    widget = Text(root, name="ts", width=20, height=4, wrap="none")
    placed(widget, Rect(0, 0, 22, 6))
    widget.insert("1.0", "\n".join(f"line {n}" for n in range(1, 41)))
    widget.yview("moveto", 0)
    area = widget._text_area()
    top = f"@{area.x},{area.y}"  # the first visible line; @0,0 is the border
    mouse(widget, "pressed", area.x, area.y)
    mouse(widget, "drag", area.x, widget.winfo_height())
    clock(0.06)
    assert widget.index(top) == "2.0", "one row past: one line"
    mouse(widget, "drag", area.x, widget.winfo_height() + 2)
    clock(0.06)
    assert widget.index(top) == "5.0", "three rows past: three lines"
    assert widget.tag_ranges("sel"), "selecting as it goes"
    mouse(widget, "released", area.x, widget.winfo_height() + 2)
    clock(0.2)
    assert widget.index(top) == "5.0"


def test_a_text_drag_above_and_to_the_left_scrolls_back(root, clock):
    """Tk's tk::TextAutoScan: above the top, -1 + y lines; past either side,
    two columns, checked only once the rows are inside."""
    widget = Text(root, name="tl", width=20, height=4, wrap="none")
    placed(widget, Rect(0, 0, 22, 6))
    widget.insert("1.0", "\n".join(f"{n:02} " + "x" * 60 for n in range(1, 41)))
    widget.yview("moveto", 0.5)
    widget.xview("moveto", 0.5)
    area = widget._text_area()
    top, left = widget.yview()[0], widget.xview()[0]
    mouse(widget, "pressed", area.x + 2, area.y + 1)
    mouse(widget, "drag", area.x + 2, -1)  # one row above the widget
    clock(0.06)
    assert widget.yview()[0] < top, "scrolled up"
    up_by = top - widget.yview()[0]
    mouse(widget, "drag", -1, area.y + 1)  # back in the rows, left of it
    clock(0.06)
    assert widget.xview()[0] < left, "scrolled left"
    assert widget.yview()[0] == pytest.approx(top - up_by), "and only sideways"
    mouse(widget, "released", -1, area.y + 1)


# --------------------------------------------------------------- Ctrl-click
#
# Tk's classic Entry and Spinbox bind <Control-Button-1> to "icursor @x" and
# Text to "mark set insert @x,y" with an undo separator: the cursor moves, and
# the selection, its anchor and the focus stay. ttk binds nothing, so there a
# Ctrl-click is a plain click. Read from Tk 9.0.2's bindings. TkCurses-mndh.


@pytest.fixture
def elsewhere(root):
    """Something else to hold the focus, so a move of it would show."""
    widget = placed(Entry(root, name="other"), Rect(0, 10, 22, 3))
    widget.focus_set()
    return widget


def test_a_ctrl_click_moves_the_cursor_and_keeps_the_selection(words, elsewhere):
    words.selection_range(4, 7)
    elsewhere.focus_set()
    mouse(words, "pressed", column(words, 10), modifiers=MOD_CTRL)
    mouse(words, "released", column(words, 10), modifiers=MOD_CTRL)
    assert state(words) == ((4, 7), 10)
    assert words.focus_get() is elsewhere, "Tk's binding does not take the focus"


def test_a_ctrl_click_keeps_the_anchor(words):
    """A shift-click after it still extends from where the selection began."""
    mouse(words, "pressed", column(words, 4))
    mouse(words, "drag", column(words, 7))
    mouse(words, "released", column(words, 7))
    mouse(words, "pressed", column(words, 1), modifiers=MOD_CTRL)
    mouse(words, "released", column(words, 1), modifiers=MOD_CTRL)
    mouse(words, "pressed", column(words, 12), modifiers=MOD_SHIFT)
    assert words._field.selection == (4, 12)


def test_no_drag_follows_a_ctrl_click(words):
    words.selection_range(4, 7)
    mouse(words, "pressed", column(words, 1), modifiers=MOD_CTRL)
    mouse(words, "drag", column(words, 14), modifiers=MOD_CTRL)
    assert state(words) == ((4, 7), 1)


def test_a_ctrl_double_click_extends_by_words_from_the_last_plain_click(words):
    """Measured, by running the two binding scripts as Tk fires them: the
    double-click outranks the Ctrl-click, and since the Ctrl press set no
    anchor, the words run from where the last plain click left it - a
    plain click at 1, then a Ctrl-double-click at 9, reads (0, 13)."""
    mouse(words, "pressed", column(words, 1))
    mouse(words, "released", column(words, 1))
    x = column(words, 9)
    mouse(words, "pressed", x, modifiers=MOD_CTRL)
    mouse(words, "released", x, modifiers=MOD_CTRL)
    mouse(words, "double", x, modifiers=MOD_CTRL)
    assert state(words) == ((0, 13), 13)


def test_a_spinbox_ctrl_click_moves_the_cursor_only(spin):
    spin.selection_range(0, 5)
    mouse(spin, "pressed", column(spin, 9), modifiers=MOD_CTRL)
    assert state(spin) == ((0, 5), 9)


@pytest.mark.parametrize(
    "make", [ttk.Entry, ttk.Spinbox], ids=["ttk.Entry", "ttk.Spinbox"]
)
def test_a_ttk_ctrl_click_is_a_plain_click(root, elsewhere, make):
    """ttk binds no Ctrl-click, so the press binding has it."""
    widget = placed(make(root, name="tc"))
    widget.delete(0, "end")
    widget.insert(0, "one two three")
    widget.selection_range(0, 3)
    elsewhere.focus_set()
    mouse(widget, "pressed", column(widget, 6), modifiers=MOD_CTRL)
    assert state(widget) == (None, 6)
    assert widget.focus_get() is widget


def test_a_text_ctrl_click_moves_the_insert_mark_and_keeps_the_selection(
    text, elsewhere
):
    load(text, "one two three four")
    text.tag_add("sel", "1.4", "1.7")
    elsewhere.focus_set()
    tclick(text, "1.14", modifiers=MOD_CTRL)
    tclick(text, "1.14", "released", modifiers=MOD_CTRL)
    assert tsel(text) == ("two", "1.14")
    assert text.focus_get() is elsewhere


def test_a_text_ctrl_double_click_does_nothing(text):
    """Tk binds <Control-Double-Button-1> to nothing, on purpose."""
    load(text, "one two three four")
    tclick(text, "1.5", modifiers=MOD_CTRL)
    tclick(text, "1.5", "released", modifiers=MOD_CTRL)
    tclick(text, "1.5", "double", modifiers=MOD_CTRL)
    assert tsel(text) == (None, "1.5")


def test_a_text_ctrl_click_ends_the_undo_group(root):
    """Tk's comment: moving the insert mark without making it one end of the
    selection must insert an autoseparator."""
    widget = Text(root, name="tu", width=20, height=3, undo=True)
    placed(widget, Rect(0, 0, 22, 5))
    widget.focus_set()
    for char in "ab":
        widget._handle(KeyEvent(keysym=char, char=char))
    x, y = cell(widget, "1.0")
    mouse(widget, "pressed", x, y, modifiers=MOD_CTRL)
    for char in "cd":
        widget._handle(KeyEvent(keysym=char, char=char))
    assert widget.get("1.0", "end-1c") == "cdab"
    widget.edit_undo()
    assert widget.get("1.0", "end-1c") == "ab"
