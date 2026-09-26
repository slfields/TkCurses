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

"""Tests for the Text widget."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Misc, TclError, Text
from tkcurses._core.events import MOD_CTRL, MOD_SHIFT, KeyEvent, MouseEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack
from tkcurses._core.textbuffer import Index


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def stack():
    return PanelStack(window_factory=stub_window, panel_factory=None)


@pytest.fixture
def root(stack):
    root = Misc()
    root.tk.panels = stack
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    return root


@pytest.fixture
def text(root):
    """A Text laid out 20 columns by 5 rows of usable area."""
    widget = Text(root, name="t", width=20, height=5, wrap="none")
    widget._allocate(Rect(0, 0, 22, 7))
    widget._map()
    return widget


def typed(widget, characters):
    for character in characters:
        widget._handle(KeyEvent(keysym=character, char=character))


# ------------------------------------------------------------------ contents


def test_a_new_text_is_empty_but_has_a_line(text):
    assert text.get("1.0", "end") == "\n"
    assert text.index("end") == "2.0"


def test_insert_and_get(text):
    text.insert("1.0", "hello")
    assert text.get("1.0", "1.end") == "hello"


def test_get_of_one_index_is_one_character(text):
    """tkinter's one-argument get, which is not "get everything"."""
    text.insert("1.0", "hello")
    assert text.get("1.1") == "e"


def test_insert_can_add_lines(text):
    text.insert("1.0", "one\ntwo")
    assert text.index("end") == "3.0"


def test_delete_a_range(text):
    text.insert("1.0", "hello world")
    text.delete("1.0", "1.6")
    assert text.get("1.0", "1.end") == "world"


def test_delete_one_character(text):
    text.insert("1.0", "hello")
    text.delete("1.0")
    assert text.get("1.0", "1.end") == "ello"


def test_insert_can_tag_what_it_inserted(text):
    text.insert("1.0", "hello", "greeting")
    assert text.tag_ranges("greeting") == ["1.0", "1.5"]


def test_an_edit_reports_itself(text):
    seen = []
    text.bind("<<Modified>>", lambda event: seen.append(1))
    text.insert("1.0", "x")
    assert seen == [1]


# ------------------------------------------------------------------- indices


def test_index_returns_a_string(text):
    """tkinter returns "line.char", and code compares and slices it."""
    text.insert("1.0", "hello")
    assert text.index("1.0") == "1.0"
    assert isinstance(text.index("end"), str)


def test_index_arithmetic(text):
    text.insert("1.0", "hello world\nsecond")
    assert text.index("1.0 +3c") == "1.3"
    assert text.index("1.end") == "1.11"
    assert text.index("2.0 -1c") == "1.11"
    assert text.index("1.0 +1l lineend") == "2.6"


def test_compare(text):
    assert text.compare("1.0", "<", "end")
    assert not text.compare("1.0", ">", "1.0")


def test_an_at_index_names_a_cell(text):
    """Cells within the widget, so the sunken border's cell counts."""
    text.insert("1.0", "hello world\nsecond line")
    area = text._text_area()
    assert text.index(f"@{area.x},{area.y}") == "1.0"
    assert text.index(f"@{area.x + 3},{area.y}") == "1.3"
    assert text.index(f"@{area.x},{area.y + 1}") == "2.0"


def test_an_at_index_takes_modifiers(text):
    text.insert("1.0", "hello world")
    area = text._text_area()
    assert text.index(f"@{area.x + 3},{area.y} linestart") == "1.0"


def test_a_bad_index_is_refused(text):
    with pytest.raises(ValueError):
        text.index("rubbish")


# --------------------------------------------------------------------- marks


def test_insert_starts_at_the_beginning(text):
    assert text.index("insert") == "1.0"


def test_the_cursor_follows_typing(text):
    text.insert("1.0", "abc")
    assert text.index("insert") == "1.3"


def test_marks_can_be_set_and_read(text):
    text.insert("1.0", "hello world")
    text.mark_set("here", "1.6")
    assert text.index("here") == "1.6"
    assert "here" in text.mark_names()


def test_a_mark_can_be_unset(text):
    text.mark_set("here", "1.0")
    text.mark_unset("here")
    assert "here" not in text.mark_names()


def test_mark_gravity(text):
    text.mark_set("here", "1.0")
    assert text.mark_gravity("here") == "right"
    text.mark_gravity("here", "left")
    assert text.mark_gravity("here") == "left"


def test_next_and_previous_marks(text):
    text.insert("1.0", "hello")
    text.mark_set("here", "1.3")
    assert text.mark_next("1.0") in ("here", "insert", "current")
    assert text.mark_previous("1.4") is not None


# ---------------------------------------------------------------------- tags


def test_a_tag_covers_a_range(text):
    text.insert("1.0", "hello world")
    text.tag_add("bold", "1.0", "1.5")
    assert text.tag_ranges("bold") == ["1.0", "1.5"]
    assert text.tag_names("1.2") == ("bold",)


def test_a_tag_can_be_removed_from_part_of_its_range(text):
    text.insert("1.0", "hello world")
    text.tag_add("bold", "1.0", "1.11")
    text.tag_remove("bold", "1.3", "1.6")
    assert text.tag_ranges("bold") == ["1.0", "1.3", "1.6", "1.11"]


def test_tag_delete_forgets_the_options_too(text):
    text.tag_configure("bold", font="bold")
    text.tag_add("bold", "1.0", "1.0")
    text.tag_delete("bold")
    assert "bold" not in text.tag_names()
    with pytest.raises(TclError):
        text.tag_cget("bold", "font")


def test_tag_configure_reads_back(text):
    text.tag_configure("bold", foreground="red")
    assert text.tag_cget("bold", "foreground") == "red"


def test_an_unknown_tag_option_is_refused(text):
    with pytest.raises(TclError, match="unknown option"):
        text.tag_configure("bold", bitmap="x")


def test_tag_options_accept_the_usual_aliases(text):
    text.tag_configure("bold", fg="red", bg="blue")
    assert text.tag_cget("bold", "foreground") == "red"
    assert text.tag_cget("bold", "background") == "blue"


def test_tag_priority_follows_creation_then_raise_and_lower(text):
    text.tag_configure("a")
    text.tag_configure("b")
    assert text.tag_names() == ("sel", "a", "b")
    text.tag_raise("a")
    assert text.tag_names()[-1] == "a"
    text.tag_lower("a")
    assert text.tag_names()[0] == "a"


def test_tag_raise_above_a_named_tag(text):
    for name in ("a", "b", "c"):
        text.tag_configure(name)
    text.tag_raise("a", "b")
    assert text.tag_names().index("a") == text.tag_names().index("b") + 1


def test_tag_nextrange_and_prevrange(text):
    text.insert("1.0", "hello world")
    text.tag_add("bold", "1.0", "1.3")
    text.tag_add("bold", "1.6", "1.9")
    assert text.tag_nextrange("bold", "1.3") == ("1.6", "1.9")
    assert text.tag_prevrange("bold", "1.6") == ("1.0", "1.3")
    assert text.tag_nextrange("bold", "end") == ()


def test_sel_exists_from_the_start(text):
    """So that sel.first works as an index without configuring anything."""
    assert "sel" in text.tag_names()


# ---------------------------------------------------------------- the cursor


def test_arrows_move_the_cursor(text):
    text.insert("1.0", "hello\nworld")
    text.mark_set("insert", "1.0")
    text._handle(KeyEvent(keysym="Right"))
    assert text.index("insert") == "1.1"
    text._handle(KeyEvent(keysym="Left"))
    assert text.index("insert") == "1.0"


def test_down_moves_a_display_row(text):
    text.insert("1.0", "hello\nworld")
    text.mark_set("insert", "1.2")
    text._handle(KeyEvent(keysym="Down"))
    assert text.index("insert") == "2.2"


def test_down_keeps_the_column_where_it_can(text):
    text.insert("1.0", "hello world\nab")
    text.mark_set("insert", "1.9")
    text._handle(KeyEvent(keysym="Down"))
    assert text.index("insert") == "2.2"


def test_up_from_the_first_line_stays_put(text):
    text.insert("1.0", "hello")
    text.mark_set("insert", "1.2")
    text._handle(KeyEvent(keysym="Up"))
    assert text.index("insert") == "1.2"


def test_home_and_end(text):
    text.insert("1.0", "hello world")
    text.mark_set("insert", "1.4")
    text._handle(KeyEvent(keysym="Home"))
    assert text.index("insert") == "1.0"
    text._handle(KeyEvent(keysym="End"))
    assert text.index("insert") == "1.11"


def test_page_keys_move_a_screenful(text):
    text.insert("1.0", "\n".join(f"line {n}" for n in range(20)))
    text.mark_set("insert", "1.0")
    text._handle(KeyEvent(keysym="Next"))
    assert text.index("insert") == "6.0"
    text._handle(KeyEvent(keysym="Prior"))
    assert text.index("insert") == "1.0"


def test_up_moves_by_display_row_when_wrapping(root):
    """With wrapping on, Up goes to the row above on screen, not the line."""
    widget = Text(root, name="w", width=10, height=6, wrap="char")
    widget._allocate(Rect(0, 0, 12, 8))
    widget._map()
    widget.insert("1.0", "abcdefghijklmnopqrstuvwxyz")
    widget.mark_set("insert", "1.22")
    widget._handle(KeyEvent(keysym="Up"))
    assert widget.index("insert") == "1.12"


# ------------------------------------------------------------------- editing


def test_typing_inserts_at_the_cursor(text):
    typed(text, "abc")
    assert text.get("1.0", "1.end") == "abc"
    assert text.index("insert") == "1.3"


def test_return_starts_a_line(text):
    typed(text, "ab")
    text._handle(KeyEvent(keysym="Return"))
    typed(text, "cd")
    assert text.get("1.0", "end") == "ab\ncd\n"


def test_backspace_deletes_backwards(text):
    typed(text, "abc")
    text._handle(KeyEvent(keysym="BackSpace"))
    assert text.get("1.0", "1.end") == "ab"


def test_backspace_at_the_very_start_does_nothing(text):
    text._handle(KeyEvent(keysym="BackSpace"))
    assert text.get("1.0", "end") == "\n"


def test_backspace_joins_lines(text):
    text.insert("1.0", "ab\ncd")
    text.mark_set("insert", "2.0")
    text._handle(KeyEvent(keysym="BackSpace"))
    assert text.get("1.0", "end") == "abcd\n"


def test_delete_removes_forwards(text):
    text.insert("1.0", "abc")
    text.mark_set("insert", "1.0")
    text._handle(KeyEvent(keysym="Delete"))
    assert text.get("1.0", "1.end") == "bc"


def test_tab_is_left_alone_so_the_focus_can_move(text):
    """A widget that swallowed Tab would trap a keyboard-only user."""
    assert text._handle(KeyEvent(keysym="Tab")) != "break"


def test_a_disabled_text_refuses_the_keyboard(text):
    text.insert("1.0", "fixed")
    text.configure(state="disabled")
    typed(text, "x")
    text._handle(KeyEvent(keysym="BackSpace"))
    assert text.get("1.0", "1.end") == "fixed"


def test_a_disabled_text_can_still_be_changed_from_code(text):
    """Disabling refuses the user, not the program."""
    text.configure(state="disabled")
    text.insert("1.0", "set by code")
    assert text.get("1.0", "1.end") == "set by code"


# ----------------------------------------------------------------- selection


def test_a_shifted_arrow_selects(text):
    text.insert("1.0", "hello")
    text.mark_set("insert", "1.0")
    for _ in range(3):
        text._handle(KeyEvent(keysym="Right", modifiers=MOD_SHIFT))
    assert text.get("sel.first", "sel.last") == "hel"


def test_a_plain_arrow_drops_the_selection(text):
    text.insert("1.0", "hello")
    text.mark_set("insert", "1.0")
    text._handle(KeyEvent(keysym="Right", modifiers=MOD_SHIFT))
    text._handle(KeyEvent(keysym="Right"))
    assert text.tag_ranges("sel") == []


def test_typing_replaces_the_selection(text):
    text.insert("1.0", "hello")
    text.mark_set("insert", "1.0")
    for _ in range(5):
        text._handle(KeyEvent(keysym="Right", modifiers=MOD_SHIFT))
    typed(text, "X")
    assert text.get("1.0", "1.end") == "X"


def test_backspace_deletes_the_selection(text):
    text.insert("1.0", "hello")
    text.mark_set("insert", "1.0")
    for _ in range(3):
        text._handle(KeyEvent(keysym="Right", modifiers=MOD_SHIFT))
    text._handle(KeyEvent(keysym="BackSpace"))
    assert text.get("1.0", "1.end") == "lo"


# --------------------------------------------------------------------- mouse


def test_a_click_moves_the_cursor(text):
    text.insert("1.0", "hello world\nsecond line")
    area = text._text_area()
    text._handle(MouseEvent(button=1, state="pressed", x=area.x + 3, y=area.y + 1))
    assert text.index("insert") == "2.3"


def test_a_click_takes_the_focus(text):
    text._handle(MouseEvent(button=1, state="pressed", x=1, y=1))
    assert text.focus_get() is text


def test_a_drag_selects(text):
    text.insert("1.0", "hello world")
    area = text._text_area()
    text._handle(MouseEvent(button=1, state="pressed", x=area.x, y=area.y))
    text._handle(MouseEvent(button=0, state="drag", x=area.x + 5, y=area.y))
    assert text.get("sel.first", "sel.last") == "hello"


def test_motion_without_a_press_selects_nothing(text):
    text.insert("1.0", "hello world")
    text._handle(MouseEvent(button=0, state="motion", x=6, y=2))
    assert text.tag_ranges("sel") == []


def test_the_wheel_scrolls_without_moving_the_cursor(text):
    text.insert("1.0", "\n".join(f"line {n}" for n in range(30)))
    text.mark_set("insert", "1.0")
    top = text._top
    text._handle(MouseEvent(button=5, state="pressed", x=1, y=1))
    assert text._top > top
    assert text.index("insert") == "1.0"


# --------------------------------------------------------------- the view


def test_yview_reports_fractions(text):
    text.insert("1.0", "\n".join(f"line {n}" for n in range(20)))
    first, last = text.yview()
    assert 0.0 <= first < last <= 1.0


def test_yview_moveto_scrolls(text):
    text.insert("1.0", "\n".join(f"line {n}" for n in range(40)))
    text.yview_moveto(0.5)
    assert text._top == 20


def test_yview_scroll_by_units_and_pages(text):
    text.insert("1.0", "\n".join(f"line {n}" for n in range(40)))
    text.yview_moveto(0.0)
    text.yview_scroll(3, "units")
    assert text._top == 3
    text.yview_scroll(1, "pages")
    assert text._top == 8


def test_the_view_never_scrolls_past_the_end(text):
    text.insert("1.0", "one\ntwo")
    text.yview_moveto(1.0)
    assert text._top <= 2


def test_a_bad_scroll_command_is_refused(text):
    with pytest.raises(TclError, match="moveto or scroll"):
        text.yview("sideways", 1)


def test_the_scrollcommand_is_told_where_the_view_is(text):
    seen = []
    text.configure(yscrollcommand=lambda first, last: seen.append((first, last)))
    text.insert("1.0", "\n".join(f"line {n}" for n in range(20)))
    assert seen
    assert seen[-1][1] <= 1.0


def test_see_scrolls_the_least_it_can(text):
    text.insert("1.0", "\n".join(f"line {n}" for n in range(40)))
    text.yview_moveto(0.0)
    text.see("20.0")
    # Scrolled exactly enough to put row 20 on the last visible line.
    assert text._top == 19 - text._view_size()[1] + 1


def test_see_scrolls_sideways_when_not_wrapping(text):
    text.insert("1.0", "x" * 100)
    text.see("1.90")
    assert text._left > 0


def test_wrapping_pins_the_horizontal_view(root):
    widget = Text(root, name="w", width=10, height=4, wrap="word")
    widget._allocate(Rect(0, 0, 12, 6))
    widget._map()
    widget.insert("1.0", "a very long line that will certainly wrap")
    widget.see("1.39")
    assert widget._left == 0


def test_xview_reports_fractions(text):
    text.insert("1.0", "x" * 100)
    # Inserting left the cursor at the end, and see() followed it sideways.
    first, last = text.xview()
    assert 0.0 < first < last <= 1.0
    text.xview_moveto(0.0)
    assert text.xview()[0] == 0.0


# ------------------------------------------------------------------ wrapping


def test_wrap_none_is_one_display_row_per_line(text):
    text.insert("1.0", "x" * 100)
    assert len(text._display_lines()) == 1


def test_no_display_row_is_wider_than_the_area(root):
    """A row one cell too wide draws over the border, in a character grid."""
    widget = Text(root, name="w", width=10, height=4, wrap="word")
    widget._allocate(Rect(0, 0, 12, 6))
    widget._map()
    widget.insert("1.0", "alpha beta gamma delta epsilon zeta")
    width = widget._view_size()[0]
    assert all(stop - start <= width for _, start, stop in widget._display_lines())


def test_wrap_char_breaks_at_the_width(root):
    widget = Text(root, name="w", width=10, height=4, wrap="char")
    widget._allocate(Rect(0, 0, 12, 6))
    widget._map()
    widget.insert("1.0", "x" * 25)
    assert len(widget._display_lines()) == 3


def test_wrap_word_breaks_at_spaces(root):
    widget = Text(root, name="w", width=10, height=4, wrap="word")
    widget._allocate(Rect(0, 0, 12, 6))
    widget._map()
    widget.insert("1.0", "alpha beta gamma")
    line = widget.get("1.0", "1.end")
    rows = widget._display_lines()
    assert [line[start:stop] for _, start, stop in rows] == ["alpha ", "beta gamma"]


def test_the_view_is_sane_before_the_widget_is_laid_out(root):
    """Otherwise every line wraps to one cell: a row per character."""
    widget = Text(root, name="w", width=20, height=5)
    widget.insert("1.0", "hello world\nsecond line")
    assert len(widget._display_lines()) == 2
    assert widget.yview() == (0.0, 1.0)


# ------------------------------------------------------------------ geometry


def test_a_text_asks_for_its_rows_and_columns(root):
    widget = Text(root, name="w", width=40, height=10)
    assert widget.winfo_reqwidth() >= 40
    assert widget.winfo_reqheight() >= 10


def test_the_cursor_at_end_does_not_land_on_the_first_column(text):
    """`end` is past every display row, so it has none of its own.

    Falling back to the last row put the cursor at column 0 and blanked the
    first character of the bottom line on screen.
    """
    text.insert("1.0", "\n".join(f"line {n}" for n in range(10)))
    text.mark_set("insert", "end")
    rows = text._display_lines()
    row, column = text._display_position(text._buffer.mark_index("insert"), rows)
    assert row == len(rows) - 1
    assert column == len("line 9")


def test_a_text_takes_the_focus(root):
    assert Text(root, name="w")._takefocus is True


def test_see_tells_the_scrollbar_where_the_view_went(text):
    """The one thing a scrollbar exists to report.

    see() moves the view without going through _scroll, so nothing reported
    it: the thumb sat at the bottom of its trough while the text showed
    line 1.
    """
    seen = []
    text.insert("1.0", "\n".join(f"line {n}" for n in range(40)))
    text.configure(yscrollcommand=lambda first, last: seen.append(first))
    text.see("end")
    assert seen and seen[-1] > 0.0
    text.see("1.0")
    assert seen[-1] == 0.0


def test_an_index_at_a_wrap_boundary_belongs_to_the_later_row(root):
    """Reported from UAT 23: Down from the start of a wrapped line.

    A wrap boundary is the end of one display row and the start of the next,
    and resolving it to the earlier one drew the cursor a cell past the end
    of that row - painting the first character of the next row there too.
    """
    widget = Text(root, name="w", width=10, height=6, wrap="char")
    widget._allocate(Rect(0, 0, 12, 8))
    widget._map()
    widget.insert("1.0", "abcdefghijklmnopqrst")
    rows = widget._display_lines()
    assert rows[0][2] == 10  # the first row ends at character 10
    row, column = widget._display_position(Index(1, 10), rows)
    assert (row, column) == (1, 0)


def test_the_end_of_a_line_belongs_to_its_last_row(root):
    widget = Text(root, name="w", width=10, height=6, wrap="char")
    widget._allocate(Rect(0, 0, 12, 8))
    widget._map()
    widget.insert("1.0", "abcdefghijklmno")
    rows = widget._display_lines()
    row, column = widget._display_position(Index(1, 15), rows)
    assert (row, column) == (1, 5)


def test_down_from_the_start_of_a_wrapped_line_lands_on_the_next_row(root):
    widget = Text(root, name="w", width=10, height=6, wrap="char")
    widget._allocate(Rect(0, 0, 12, 8))
    widget._map()
    widget.insert("1.0", "abcdefghijklmnopqrst")
    widget.mark_set("insert", "1.0")
    widget._handle(KeyEvent(keysym="Down"))
    assert widget.index("insert") == "1.10"
    assert widget._display_position(Index(1, 10))[0] == 1


# ------------------------------------------------------- parity with real Tk
#
# The expected values below were taken from Tk 9.0.2 itself, driving a real
# tkinter.Text of the same width and wrap mode with event_generate. They are
# recorded rather than derived, so that "this is what Tk does" is a fact in
# the suite instead of a claim in a comment.

TK_PARAGRAPH = "alpha beta gamma delta epsilon zeta eta theta\nSECOND\nTHIRD\n"


@pytest.fixture
def tk_alike(root):
    """A Text matching the tkinter.Text the expectations were taken from."""
    widget = Text(root, name="p", width=20, height=4, wrap="word", relief="flat")
    widget._allocate(Rect(0, 0, 20, 4))
    widget._map()
    widget.insert("1.0", TK_PARAGRAPH)
    return widget


def press(widget, keysym, **kw):
    widget._handle(KeyEvent(keysym=keysym, **kw))
    return widget.index("insert")


def test_the_paragraph_wraps_where_tk_wraps_it(tk_alike):
    """Three display rows, the second starting at character 17."""
    rows = [
        (start, stop) for line, start, stop in tk_alike._display_lines() if line == 1
    ]
    assert len(rows) == 3
    assert rows[1][0] == 17


@pytest.mark.parametrize(
    ("start", "keysym", "expected"),
    [
        ("1.0", "Down", "1.17"),
        ("1.17", "Down", "1.36"),
        ("1.17", "Up", "1.0"),
        ("1.20", "Home", "1.17"),
        ("1.2", "End", "1.16"),
    ],
)
def test_motion_matches_tk(tk_alike, start, keysym, expected):
    tk_alike.mark_set("insert", start)
    assert press(tk_alike, keysym) == expected


@pytest.mark.parametrize(
    ("start", "keysym", "expected"),
    [
        ("1.20", "Home", "1.0"),
        ("1.0", "End", "4.0"),
        ("1.20", "Right", "1.23"),
        ("1.0", "Left", "1.0"),
    ],
)
def test_control_motion_matches_tk(tk_alike, start, keysym, expected):
    tk_alike.mark_set("insert", start)
    assert press(tk_alike, keysym, modifiers=MOD_CTRL) == expected


def test_shift_home_selects_to_the_display_line_start(tk_alike):
    """Tk answers 1.17 for Shift-Home pressed at 1.20."""
    tk_alike.mark_set("insert", "1.20")
    assert press(tk_alike, "Home", modifiers=MOD_SHIFT) == "1.17"
    assert tk_alike.get("sel.first", "sel.last") == tk_alike.get("1.17", "1.20")


def test_control_right_walks_word_by_word(tk_alike):
    """Each press reaches the next word's start, not this word's end."""
    tk_alike.mark_set("insert", "1.0")
    assert press(tk_alike, "Right", modifiers=MOD_CTRL) == "1.6"
    assert press(tk_alike, "Right", modifiers=MOD_CTRL) == "1.11"
    assert press(tk_alike, "Right", modifiers=MOD_CTRL) == "1.17"


def test_control_left_walks_back_word_by_word(tk_alike):
    tk_alike.mark_set("insert", "1.17")
    assert press(tk_alike, "Left", modifiers=MOD_CTRL) == "1.11"
    assert press(tk_alike, "Left", modifiers=MOD_CTRL) == "1.6"


# --------------------------------------------------------------------- undo
#
# Every expectation below was measured against real tkinter (Tk 9.0) before
# it was written, because the corner cases are not guessable: which edits
# group together, when the redo stack is dropped, and which of the two ways
# of having nothing to undo is an error.


@pytest.fixture
def undoable(root):
    """A Text with undo on, otherwise the same as ``text``."""
    widget = Text(root, name="u", width=20, height=5, wrap="none", undo=True)
    widget._allocate(Rect(0, 0, 22, 7))
    widget._map()
    return widget


def test_undo_is_off_unless_asked_for(text):
    """Tk's default, and it means edit_undo does nothing rather than fail."""
    text.insert("1.0", "x")
    assert text.edit_undo() is None
    assert text.get("1.0", "end-1c") == "x"


def test_nothing_to_undo_is_an_error_only_when_undo_is_on(undoable, text):
    """The two ways of having nothing to undo are not the same thing.

    Measured: with -undo true an empty stack raises, with -undo false the
    call is a no-op. Treating them alike would either make a plain Text
    raise on a keystroke or make a real empty stack silently succeed.
    """
    with pytest.raises(TclError, match="nothing to undo"):
        undoable.edit_undo()
    with pytest.raises(TclError, match="nothing to redo"):
        undoable.edit_redo()
    assert text.edit_undo() is None


def test_programmatic_edits_group_together(undoable):
    """Three insert() calls are ONE undo, even with autoseparators on.

    Measured against Tk, and the opposite of what the option name suggests:
    separators come from the key bindings, not from the widget command. A
    program that wants them apart calls edit_separator itself.
    """
    undoable.insert("1.0", "one")
    undoable.insert("end-1c", " two")
    undoable.insert("end-1c", " three")
    undoable.edit_undo()
    assert undoable.get("1.0", "end-1c") == ""


def test_a_separator_splits_the_group(undoable):
    undoable.insert("1.0", "one")
    undoable.edit_separator()
    undoable.insert("end-1c", " two")
    undoable.edit_undo()
    assert undoable.get("1.0", "end-1c") == "one"
    undoable.edit_undo()
    assert undoable.get("1.0", "end-1c") == ""


def test_redo_puts_back_one_group_at_a_time(undoable):
    undoable.insert("1.0", "one")
    undoable.edit_separator()
    undoable.insert("end-1c", " two")
    undoable.edit_undo()
    undoable.edit_undo()
    undoable.edit_redo()
    assert undoable.get("1.0", "end-1c") == "one"
    undoable.edit_redo()
    assert undoable.get("1.0", "end-1c") == "one two"


def test_a_new_edit_drops_the_redo_stack(undoable):
    """Measured against Tk, and easy to miss.

    Keeping what was undone would let redo reapply an edit to text that has
    since changed under it.
    """
    undoable.insert("1.0", "a")
    undoable.edit_separator()
    undoable.insert("end-1c", "b")
    undoable.edit_undo()
    undoable.insert("end-1c", "Z")
    with pytest.raises(TclError, match="nothing to redo"):
        undoable.edit_redo()


def test_undo_takes_back_a_deletion(undoable):
    undoable.insert("1.0", "abc")
    undoable.edit_separator()
    undoable.delete("1.0", "1.1")
    assert undoable.get("1.0", "end-1c") == "bc"
    undoable.edit_undo()
    assert undoable.get("1.0", "end-1c") == "abc"


def test_edit_reset_forgets_both_stacks(undoable):
    undoable.insert("1.0", "q")
    undoable.edit_reset()
    with pytest.raises(TclError, match="nothing to undo"):
        undoable.edit_undo()


def test_turning_undo_off_keeps_the_history(undoable):
    """Tk keeps the stack across the option, so off-then-on is not a reset."""
    undoable.insert("1.0", "kept")
    undoable.configure(undo=False)
    undoable.configure(undo=True)
    undoable.edit_undo()
    assert undoable.get("1.0", "end-1c") == ""


def test_typing_undoes_as_a_run_not_a_letter(undoable):
    """What autoseparators is actually for.

    Without grouping, undo is backspace with extra steps - the thing that
    makes an editor feel broken while every individual edit is correct.
    """
    typed(undoable, "hello")
    undoable.edit_undo()
    assert undoable.get("1.0", "end-1c") == ""


def test_moving_the_cursor_ends_the_run(undoable):
    """Two runs typed in different places undo separately."""
    typed(undoable, "ab")
    undoable._handle(KeyEvent(keysym="Left", char=""))
    typed(undoable, "XY")
    undoable.edit_undo()
    assert undoable.get("1.0", "end-1c") == "ab"


def test_switching_from_typing_to_deleting_ends_the_run(undoable):
    typed(undoable, "abc")
    undoable._backspace()
    undoable.edit_undo()
    assert undoable.get("1.0", "end-1c") == "abc"


def test_autoseparators_off_keeps_it_all_in_one_group(root):
    widget = Text(root, name="w", width=20, height=5, undo=True, autoseparators=False)
    widget._allocate(Rect(0, 0, 22, 7))
    widget._map()
    typed(widget, "ab")
    widget._handle(KeyEvent(keysym="Left", char=""))
    typed(widget, "XY")
    widget.edit_undo()
    assert widget.get("1.0", "end-1c") == ""


def test_autoseparators_can_be_turned_off_and_on_again(undoable):
    """The option is read per edit, not captured when the widget is built.

    The acceptance scenario toggles it at runtime to show what it does, so
    a version that only honoured the constructor would make that scenario
    lie while every other test still passed.
    """
    typed(undoable, "ab")
    undoable._handle(KeyEvent(keysym="Left", char=""))
    typed(undoable, "cd")
    assert undoable._buffer.undo_depth == 2, "two runs while it is on"

    undoable.configure(autoseparators=False)
    undoable._handle(KeyEvent(keysym="Left", char=""))
    typed(undoable, "ef")
    assert undoable._buffer.undo_depth == 2, "off: no new group, whatever happens"

    undoable.configure(autoseparators=True)
    undoable._handle(KeyEvent(keysym="Left", char=""))
    typed(undoable, "gh")
    assert undoable._buffer.undo_depth == 3, "and back on again"


def test_undo_depth_counts_groups_not_edits(undoable):
    """What the scenario's status line shows, so it cannot drift."""
    assert undoable._buffer.undo_depth == 0
    undoable.insert("1.0", "one")
    undoable.insert("end-1c", " two")
    assert undoable._buffer.undo_depth == 1, "one group, two edits"
    undoable.edit_separator()
    undoable.insert("end-1c", " three")
    assert undoable._buffer.undo_depth == 2
    undoable.edit_undo()
    assert undoable._buffer.undo_depth == 1


def test_undo_restores_text_but_not_tags(undoable):
    """Tk does the same, measured: only the characters are recorded.

    Asserted rather than left as an accident, so that a later change which
    starts restoring tags is a deliberate divergence and not a surprise.
    """
    undoable.insert("1.0", "hello world")
    undoable.tag_add("t", "1.0", "1.5")
    undoable.edit_separator()
    undoable.delete("1.0", "1.6")
    undoable.edit_undo()
    assert undoable.get("1.0", "end-1c") == "hello world"
    assert undoable.tag_ranges("t") == []


def test_marks_come_back_where_they_were(undoable):
    undoable.insert("1.0", "hello world")
    undoable.mark_set("here", "1.6")
    undoable.edit_separator()
    undoable.delete("1.0", "1.6")
    undoable.edit_undo()
    assert undoable.index("here") == "1.6"


# ----------------------------------------------------------- modified flag


def test_the_modified_flag_starts_clear_and_is_an_int(text):
    """tkinter returns 0 or 1, and code written against it compares to them."""
    assert text.edit_modified() == 0
    text.insert("1.0", "x")
    assert text.edit_modified() == 1


def test_the_modified_flag_can_be_cleared(text):
    text.insert("1.0", "x")
    text.edit_modified(False)
    assert text.edit_modified() == 0


def test_modified_fires_on_the_change_not_on_the_edit(text):
    """Measured against Tk: it is an event about the FLAG, not the text.

    Two inserts give one event. Clearing the flag gives another, because
    that is a change too. This used to fire on every edit, so a handler
    that saved on it saved far more often than tkinter would.
    """
    seen = []
    text.bind("<<Modified>>", lambda event: seen.append(text.edit_modified()))
    text.insert("1.0", "a")
    assert seen == [1]
    text.insert("end-1c", "b")
    assert seen == [1], "a second edit does not change the flag"
    text.edit_modified(False)
    assert seen == [1, 0], "clearing it is a change, and is announced"
    text.insert("end-1c", "c")
    assert seen == [1, 0, 1]


def test_the_modified_flag_works_without_undo(text):
    """It is not part of the undo machinery, though it looks like it."""
    assert text.cget("undo") is False
    text.insert("1.0", "x")
    assert text.edit_modified() == 1


# ------------------------------------------------------------------- search
#
# Every case here was run against real tkinter (Tk 9.0) first and matched
# before it was written down - including the ones that look wrong, like an
# empty pattern returning the index it started at.


@pytest.fixture
def haystack(text):
    text.insert("1.0", "Hello hello\nworld HELLO\n")
    return text


def test_search_finds_the_next_match(haystack):
    assert haystack.search("hello", "1.0") == "1.6"


def test_a_match_at_the_start_index_counts(haystack):
    """Not "after the index": Tk reports a match that begins exactly there."""
    assert haystack.search("hello", "1.6") == "1.6"


def test_search_returns_empty_string_when_absent(haystack):
    """tkinter returns "", not None, and callers test it as a string."""
    assert haystack.search("zz", "1.0") == ""


def test_search_wraps_round_the_end(haystack):
    """Surprising, and what Tk does: without a stopindex there is no end."""
    assert haystack.search("Hello", "end") == "1.0"


def test_stopindex_is_how_a_caller_asks_for_no_wrapping(haystack):
    assert haystack.search("world", "1.0", stopindex="1.5") == ""


def test_search_backwards_finds_the_previous_match(haystack):
    assert haystack.search("hello", "end", backwards=True) == "1.6"


def test_nocase_applies_in_both_directions(haystack):
    assert haystack.search("hello", "end", backwards=True, nocase=True) == "2.6"


def test_an_empty_pattern_matches_where_it_started(haystack):
    """Measured. Not "no match", and not "everything"."""
    assert haystack.search("", "2.0") == "2.0"


def test_count_reports_the_match_length(haystack):
    counter = SimpleNamespace(value=None, set=lambda n: None)
    seen = []
    counter.set = seen.append
    assert haystack.search("Hello", "1.0", count=counter) == "1.0"
    assert seen == [5]


def test_an_exact_search_matches_across_a_newline(text):
    """The difference from a regular expression, and it is measured.

    Tk's exact search runs over the text as one string; only -regexp is
    confined to a line.
    """
    text.insert("1.0", "abc\ndef\nghi")
    counter = []
    assert text.search("abc\ndef", "1.0", count=SimpleNamespace(set=counter.append))
    assert counter == [7]


def test_a_regexp_is_matched_line_by_line(text):
    """So ^ and $ are the edges of a line, and . never crosses a newline."""
    text.insert("1.0", "abc\ndef\nghi")
    assert text.search("c$", "1.0", regexp=True) == "1.2"
    assert text.search("^d", "1.0", regexp=True) == "2.0"
    assert text.search("c.d", "1.0", regexp=True) == "", "must not cross a newline"
    assert text.search("a.*i", "1.0", regexp=True) == "", "nor span three lines"


def test_a_regexp_anchored_to_the_line_end_still_wraps(haystack):
    assert haystack.search("hello$", "1.0", regexp=True, nocase=True) == "1.6"


def test_regexp_wins_over_exact_when_both_are_given(text):
    """Not an error, measured: Tk takes the later option."""
    text.insert("1.0", "abc")
    assert text.search("b+", "1.0", exact=True, regexp=True) == "1.1"


def test_search_backwards_with_a_regexp(text):
    text.insert("1.0", "abc\ndef\nghi")
    assert text.search("b|e", "end", regexp=True, backwards=True) == "2.1"


def test_elide_is_accepted_and_does_nothing(haystack):
    """Nothing is elided here, so there is nothing for it to skip.

    Accepted rather than rejected, so a call that works in tkinter does not
    fail here for the sake of an option with no meaning.
    """
    assert haystack.search("hello", "1.0", elide=True) == "1.6"


# ----------------------------------------------------------------- geometry


def test_bbox_is_one_cell(text):
    text.insert("1.0", "hello")
    assert text.bbox("1.0") == (1, 1, 1, 1)
    assert text.bbox("1.3") == (4, 1, 1, 1)


def test_dlineinfo_reports_the_line_width_not_the_widget_width(text):
    text.insert("1.0", "hello")
    info = text.dlineinfo("1.0")
    assert info is not None
    x, y, width, height, baseline = info
    assert (x, y) == (1, 1)
    assert width == 5, "the text on that line, not the 20 columns available"
    assert (height, baseline) == (1, 0), "one cell tall, nothing below it"


def test_geometry_of_a_later_line(text):
    text.insert("1.0", "one\ntwo\nthree")
    assert text.bbox("3.0") == (1, 3, 1, 1)
    info = text.dlineinfo("3.0")
    assert info is not None and info[1] == 3


def test_an_index_scrolled_out_of_view_has_no_geometry(text):
    """What makes this worth asking rather than calculating.

    The widget shows 5 rows; line 9 is below them until the view moves.
    """
    text.insert("1.0", "\n".join(str(n) for n in range(1, 12)))
    text.see("1.0")
    assert text.bbox("9.0") is None
    assert text.dlineinfo("9.0") is None
    text.see("9.0")
    assert text.bbox("9.0") is not None
    assert text.dlineinfo("9.0") is not None


def test_a_character_scrolled_sideways_has_no_bbox(root):
    """Horizontally too, and only bbox notices: the LINE is still shown."""
    widget = Text(root, name="h", width=10, height=3, wrap="none")
    widget._allocate(Rect(0, 0, 12, 5))
    widget._map()
    widget.insert("1.0", "abcdefghijklmnopqrstuvwxyz")
    widget.see("1.0")
    assert widget.bbox("1.0") is not None
    widget.see("1.25")
    assert widget.bbox("1.0") is None, "scrolled off to the left"
    info = widget.dlineinfo("1.0")
    assert info is not None, "but its line is still on screen"
    # tkinter does this too, measured: with the view scrolled right it
    # answered x=-125 rather than clamping to the widget or giving up.
    assert info[0] < 0, "and the line now starts left of the widget"


def test_bbox_agrees_with_where_a_click_lands(text):
    """The two are inverses, and a disagreement is a real bug.

    A click resolves a cell to an index; bbox resolves an index to a cell.
    If they drift apart, clicking a character selects a different one from
    the one drawn there.
    """
    text.insert("1.0", "one\ntwo\nthree")
    for spec in ("1.0", "1.2", "2.1", "3.4"):
        box = text.bbox(spec)
        assert box is not None, spec
        x, y, _, _ = box
        assert str(text._index_at_cell(x, y)) == text.index(spec)


def test_geometry_follows_a_wrapped_line(root):
    """Display lines, not logical ones: row 2 on screen is still line 1."""
    widget = Text(root, name="w2", width=5, height=4, wrap="char")
    widget._allocate(Rect(0, 0, 7, 6))
    widget._map()
    widget.insert("1.0", "abcdefgh")
    first, second = widget.bbox("1.0"), widget.bbox("1.5")
    assert first is not None and second is not None
    assert second[1] == first[1] + 1, "the wrap put it on the next row"
    assert second[0] == first[0], "and back at the left edge"


def test_geometry_of_an_empty_widget(text):
    """There is always one line, so there is always somewhere to point."""
    assert text.bbox("1.0") == (1, 1, 1, 1)
    info = text.dlineinfo("1.0")
    assert info is not None and info[2] == 0, "no text on it yet"
