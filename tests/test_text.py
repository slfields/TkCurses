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
