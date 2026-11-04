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
    with pytest.raises(TclError, match=r'^bad text index "rubbish"$'):
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


def test_up_from_the_first_line_goes_to_its_start(text):
    """tk::TextUpDownLine, measured on Tk 9.0.2: there is no line above, so
    the cursor goes to the start of this one. TkCurses-wmaq."""
    text.insert("1.0", "hello")
    text.mark_set("insert", "1.2")
    text._handle(KeyEvent(keysym="Up"))
    assert text.index("insert") == "1.0"


def test_home_and_end(text):
    text.insert("1.0", "hello world")
    text.mark_set("insert", "1.4")
    text._handle(KeyEvent(keysym="Home"))
    assert text.index("insert") == "1.0"
    text._handle(KeyEvent(keysym="End"))
    assert text.index("insert") == "1.11"


def test_page_keys_move_a_screenful(text):
    """A page of five rows is three, as Tk's: measured on Tk 9.0.2, Next
    from 1.0 in a Text five rows tall goes to 4.0. TkCurses-5co5."""
    text.insert("1.0", "\n".join(f"line {n}" for n in range(20)))
    text.mark_set("insert", "1.0")
    text._handle(KeyEvent(keysym="Next"))
    assert text.index("insert") == "4.0"
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


def test_a_disabled_text_ignores_insert_and_delete_from_code(text):
    """Measured on Tk 9.0.2, and the manual: with -state disabled "no
    insertions or deletions are allowed", and nothing is raised either. This
    test used to assert the opposite, unmeasured. TkCurses-aah."""
    text.insert("1.0", "hello")
    text.edit_modified(False)
    text.configure(state="disabled")
    text.insert("1.0", "X")
    text.delete("1.0", "1.2")
    assert text.get("1.0", "end-1c") == "hello"
    assert not text.edit_modified(), "a refused edit marked the text modified"


def test_the_read_only_idiom_still_works(text):
    """How tkinter programs fill a read-only display: enable, write, disable."""
    text.configure(state="disabled")
    text.configure(state="normal")
    text.insert("1.0", "set by code")
    text.configure(state="disabled")
    assert text.get("1.0", "end-1c") == "set by code"


def test_a_disabled_text_still_takes_tags_and_marks(text):
    """Measured: only the contents are frozen."""
    text.insert("1.0", "hello")
    text.configure(state="disabled")
    text.tag_add("sel", "1.0", "1.2")
    text.mark_set("insert", "1.3")
    assert [str(i) for i in text.tag_ranges("sel")] == ["1.0", "1.2"]
    assert text.index("insert") == "1.3"


@pytest.fixture
def history(root):
    t = Text(root, name="h", undo=True)
    t.insert("1.0", "hello")
    t.edit_separator()
    t.insert("end", " world")
    return t


def test_a_disabled_undo_changes_nothing_and_keeps_the_history(history):
    """Deliberately unlike Tk 9.0.2, whose disabled undo pops the group while
    refusing its edits - the history then no longer describes the text, and
    a later redo applied ' world' twice: 'hello world world'. Here nothing
    moves, so undo after re-enabling takes back ' world', as it should."""
    history.configure(state="disabled")
    history.edit_undo()
    assert history.get("1.0", "end-1c") == "hello world"
    with pytest.raises(TclError, match="nothing to redo"):
        history.edit_redo()  # the undo did not move anything onto it
    history.configure(state="normal")
    history.edit_undo()
    assert history.get("1.0", "end-1c") == "hello"
    history.edit_redo()
    assert history.get("1.0", "end-1c") == "hello world"


@pytest.mark.parametrize("method", ["edit_undo", "edit_redo"])
def test_a_disabled_text_still_says_when_there_is_nothing_to_undo(root, method):
    """Measured: Tk raises on an empty stack whatever the state."""
    t = Text(root, name="e", undo=True, state="disabled")
    with pytest.raises(TclError, match="nothing to"):
        getattr(t, method)()


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
    assert text._top == 6  # Tk 9.0.2: 4.0, then 7.0


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


@pytest.mark.parametrize(
    ("target", "top"), [("7.0", "3.0"), ("9.0", "6.0"), ("20.0", "17.0")]
)
def test_see_scrolls_the_least_near_the_view_and_centres_further(text, target, top):
    """Measured on Tk 9.0.2 from the top of a Text five rows tall: two rows
    below the view is scrolled to the bottom row, four is centred, on the
    fourth row. TkCurses-5co5."""
    text.insert("1.0", "\n".join(f"line {n}" for n in range(40)))
    text.yview_moveto(0.0)
    text.see(target)
    assert text.index("@0,0") == top


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
    # Not by the insert, which leaves the view alone, as Tk's does.
    text.see("1.end")
    first, last = text.xview()
    assert 0.0 < first < last <= 1.0
    text.xview_moveto(0.0)
    assert text.xview()[0] == 0.0


# ------------------------------------------------------------------ wrapping


def test_wrap_none_is_one_display_row_per_line(text):
    text.insert("1.0", "x" * 100)
    assert len(text._display_lines()) == 1


def test_no_display_row_is_wider_than_the_area(root):
    """A row one cell too wide draws over the border, in a character grid -
    but for the spaces after a word that reaches the edge, which hang past
    it as Tk's do, where nothing draws them."""
    widget = Text(root, name="w", width=10, height=4, wrap="word")
    widget._allocate(Rect(0, 0, 12, 6))
    widget._map()
    widget.insert("1.0", "alpha beta gamma delta epsilon zeta")
    width = widget._view_size()[0]
    line = widget.get("1.0", "1.end")
    rows = widget._display_lines()
    assert all(len(line[start:stop].rstrip(" ")) <= width for _, start, stop in rows)


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
    # "alpha beta" fills the ten columns, and the space after it hangs:
    # Tk 9.0.2 ends the first row at 1.10.
    assert [line[start:stop] for _, start, stop in rows] == ["alpha beta ", "gamma"]


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
    # The newline, which Tk boxes to the right edge: (3, 3, 160, 19) in a
    # Text twenty columns wide, measured on Tk 9.0.2.
    assert text.bbox("1.0") == (1, 1, 20, 1)
    info = text.dlineinfo("1.0")
    assert info is not None and info[2] == 0, "no text on it yet"


# --------------------------------------------------------------- tab stops
#
# The layout arithmetic is tested in test_core_textlayout.py against
# measurements of real tkinter. What is checked here is the WIRING: that the
# options reach it, and that the widget's own three answers - where a
# character is drawn, which character a click lands on, and what is painted -
# all agree with each other on a line containing tabs.


@pytest.fixture
def tabbed(root):
    widget = Text(root, name="tb", width=30, height=5, wrap="none")
    widget._allocate(Rect(0, 0, 32, 7))
    widget._map()
    return widget


def test_tabs_default_to_every_eight_columns(tabbed):
    """Tk's default. Exact here rather than an average character width."""
    tabbed.insert("1.0", "a\tb")
    assert tabbed.bbox("1.2") is not None
    assert tabbed.bbox("1.2")[0] - tabbed.bbox("1.0")[0] == 8


def test_the_tabs_option_moves_the_stops(tabbed):
    tabbed.configure(tabs=4)
    tabbed.insert("1.0", "a\tb")
    assert tabbed.bbox("1.2")[0] - tabbed.bbox("1.0")[0] == 4


def test_tabs_takes_tk_s_list_with_alignments(tabbed):
    """'10 right' is one stop, not two."""
    tabbed.configure(tabs="10 right")
    tabbed.insert("1.0", "a\tXY")
    # Right-aligned: the run ends AT the stop, so it starts two before it.
    assert tabbed.bbox("1.2")[0] - tabbed.bbox("1.0")[0] == 8


def test_a_screen_distance_is_converted_like_every_other(tabbed):
    """The project's existing rule - ten cells to the inch."""
    tabbed.configure(tabs="1i")
    tabbed.insert("1.0", "a\tb")
    assert tabbed.bbox("1.2")[0] - tabbed.bbox("1.0")[0] == 10


def test_tab_stops_must_increase(tabbed):
    with pytest.raises(
        TclError, match=r'^tabs must be monotonically increasing, but "4"'
    ):
        tabbed.configure(tabs=(10, 4))


def test_a_tab_stop_must_be_positive(tabbed):
    with pytest.raises(TclError, match="positive"):
        tabbed.configure(tabs=0)


def test_numeric_alignment_is_accepted(tabbed):
    """It used to raise, naming TkCurses-eq2. The rules it now follows are
    pinned in tests/test_core_textlayout.py against measurements of real Tk."""
    tabbed.configure(tabs=(10, "numeric"))
    assert tabbed.cget("tabs") == (10, "numeric")


def test_numeric_alignment_puts_the_decimal_point_on_the_stop(tabbed):
    """The whole point of the alignment, through a real widget rather than the
    layout function - so the option, the parse and the drawing are all in it."""
    tabbed.configure(tabs=(10, "numeric"))
    tabbed.insert("1.0", "a\t1.5")
    # The '.' is the second character of the run, so it lands on the stop.
    left = tabbed.bbox("1.0")[0]
    assert tabbed.bbox("1.3")[0] - left == 10


def test_tabstyle_wordprocessor_takes_the_next_stop_to_the_right(tabbed):
    tabbed.configure(tabs=(4, 20), tabstyle="wordprocessor")
    tabbed.insert("1.0", "abcdefgh\tX")
    assert tabbed.bbox("1.9")[0] - tabbed.bbox("1.0")[0] == 20


def test_tabstyle_tabular_falls_back_to_one_space(tabbed):
    """The same line, the default style: one space rather than a jump."""
    tabbed.configure(tabs=(4, 20))
    tabbed.insert("1.0", "abcdefgh\tX")
    assert tabbed.bbox("1.9")[0] - tabbed.bbox("1.0")[0] == 9


def test_a_click_in_a_tab_lands_on_the_tab(tabbed):
    """Measured from tkinter: every column the tab spans answers with it."""
    tabbed.configure(tabs=10)
    tabbed.insert("1.0", "ab\tcd")
    left = tabbed.bbox("1.0")[0]
    for column in range(2, 10):
        assert str(tabbed._index_at_cell(left + column, 1)) == "1.2", column
    assert str(tabbed._index_at_cell(left + 10, 1)) == "1.3"


def test_bbox_and_a_click_agree_on_a_tabbed_line(tabbed):
    """The property the whole epic rests on, at widget level.

    If these drift, clicking a character selects a different one from the
    one drawn under the pointer, and neither side looks wrong alone.
    """
    tabbed.configure(tabs=(6, 14))
    tabbed.insert("1.0", "a\tbb\tccc")
    for offset in range(len("a\tbb\tccc")):
        box = tabbed.bbox(f"1.{offset}")
        assert box is not None, offset
        assert str(tabbed._index_at_cell(box[0], box[1])) == f"1.{offset}"


def test_a_tab_is_drawn_as_the_gap_it_spans(tabbed):
    """Not as a raw tab handed to curses - that is TkCurses-zrm."""
    from tkcurses._core.textlayout import TabStops, render

    assert render("ab\tcd", stops=TabStops((10,))) == "ab        cd"


def test_turning_tabs_back_to_the_default(tabbed):
    tabbed.configure(tabs=4)
    tabbed.configure(tabs="")
    tabbed.insert("1.0", "a\tb")
    assert tabbed.bbox("1.2")[0] - tabbed.bbox("1.0")[0] == 8


# ---------------------------------------------------------------- margins
#
# Indentation in Tk is a TAG feature rather than a tab feature, which is why
# it was missing: the tag option list excluded margins as having "no meaning
# in a character grid". A pixel has no meaning in a character grid; a margin
# in cells does. TkCurses-wy7.
#
# The wrap points below were compared against real tkinter - all four margin
# shapes, every row breaking at the same character.


@pytest.fixture
def wrapped(root):
    """40 usable columns, wrapping on words. The border takes the other two."""
    widget = Text(root, name="wr", width=40, height=12, wrap="word")
    widget._allocate(Rect(0, 0, 42, 14))
    widget._map()
    assert widget._view_size()[0] == 40
    return widget


PARAGRAPH = (
    "alpha bravo charlie delta echo foxtrot golf hotel india juliet "
    "kilo lima mike november oscar papa quebec romeo sierra tango"
)


def starts(widget):
    return [start for _, start, _ in widget._display_lines()]


def test_margins_are_accepted_as_tag_options(wrapped):
    """They were rejected before - the omission this epic exists for."""
    wrapped.tag_configure("m", lmargin1=4, lmargin2=2, rmargin=1, lmargincolor="blue")
    assert wrapped.tag_cget("m", "lmargin1") == 4


def test_an_option_with_no_cell_meaning_is_still_refused(wrapped):
    """offset is a sub-cell baseline shift. Correcting the margin decision
    does not mean accepting everything."""
    with pytest.raises(TclError):
        wrapped.tag_configure("m", offset=3)


def test_without_margins_the_wrap_points_are_unchanged(wrapped):
    wrapped.insert("1.0", PARAGRAPH)
    assert starts(wrapped) == [0, 39, 78, 118], "measured from tkinter"


def test_lmargin1_indents_and_narrows_only_the_first_row(wrapped):
    wrapped.tag_configure("m", lmargin1=8)
    wrapped.insert("1.0", PARAGRAPH, "m")
    assert starts(wrapped) == [0, 31, 68, 105], "measured from tkinter"


def test_lmargin2_is_the_hanging_indent(wrapped):
    """The first row keeps the full width and the rest are narrower - which
    is why the second row starts where it does."""
    wrapped.tag_configure("m", lmargin2=8)
    wrapped.insert("1.0", PARAGRAPH, "m")
    assert starts(wrapped) == [0, 39, 68, 98], "measured from tkinter"


def test_both_margins_is_a_block_indent(wrapped):
    wrapped.tag_configure("m", lmargin1=8, lmargin2=8)
    wrapped.insert("1.0", PARAGRAPH, "m")
    assert starts(wrapped) == [0, 31, 63, 93], "measured from tkinter"


def test_rmargin_narrows_every_row_without_moving_it(wrapped):
    wrapped.tag_configure("m", rmargin=8)
    wrapped.insert("1.0", PARAGRAPH, "m")
    assert starts(wrapped) == [0, 31, 63, 93], "measured from tkinter"


def test_a_hanging_indent_wraps_earlier_than_none(wrapped):
    """Stated as its own test because it is the whole point.

    The rows under a hanging indent are narrower, so the paragraph breaks
    sooner. A version that merely shifted the text without narrowing it
    would pass every other test here and fail this one.
    """
    wrapped.insert("1.0", PARAGRAPH)
    plain = starts(wrapped)
    wrapped.delete("1.0", "end")
    wrapped.tag_configure("m", lmargin2=8)
    wrapped.insert("1.0", PARAGRAPH, "m")
    assert starts(wrapped)[2] < plain[2]


def test_an_indented_row_is_drawn_at_its_margin(wrapped):
    wrapped.tag_configure("m", lmargin1=6)
    wrapped.insert("1.0", "hello", "m")
    box = wrapped.bbox("1.0")
    assert box is not None
    assert box[0] == wrapped._text_area().x + 6


def test_dlineinfo_reports_the_indent_in_x(wrapped):
    """Tk does: an eight-column margin came back in x, with the text's own
    width beside it rather than the indent folded into it."""
    wrapped.tag_configure("m", lmargin1=6)
    wrapped.insert("1.0", "hello", "m")
    info = wrapped.dlineinfo("1.0")
    assert info is not None
    assert info[0] == wrapped._text_area().x + 6
    assert info[2] == 5, "the text, not the text plus the indent"


def test_a_click_on_an_indented_line_lands_on_the_right_character(wrapped):
    """The inverse again, now with a margin in the way."""
    wrapped.tag_configure("m", lmargin1=6)
    wrapped.insert("1.0", "hello", "m")
    for offset in range(5):
        box = wrapped.bbox(f"1.{offset}")
        assert box is not None
        assert str(wrapped._index_at_cell(box[0], box[1])) == f"1.{offset}"


def test_the_tag_at_the_start_of_each_display_row_decides(wrapped):
    """Tk's rule: "the first non-elided character of the display line".

    Measured: a tag added part way through the first row still indents the
    wrapped row below, because that row's first character is inside it.
    """
    wrapped.insert("1.0", PARAGRAPH)
    wrapped.tag_configure("m", lmargin2=8)
    wrapped.tag_add("m", "1.20", "end")
    assert starts(wrapped) == [0, 39, 68, 98]


def test_a_text_with_no_margins_does_not_pay_for_them(wrapped):
    """The fast path, asserted so it cannot quietly become the slow one.

    Resolving margins means asking which tags cover a row and walking the
    raise order, per row, inside wrapping. Measured: doing that
    unconditionally took a Text repaint from under 25ms to 31.6ms and failed
    the redraw budget in test_redraw_cost_tty.
    """
    wrapped.insert("1.0", PARAGRAPH)
    assert wrapped._margined is False
    assert wrapped._row_margins(1, 0) == (0, 0)


def test_setting_a_margin_turns_the_slow_path_on(wrapped):
    """And the flag must latch, or the feature silently stops working."""
    wrapped.tag_configure("m", lmargin1=4)
    assert wrapped._margined is True
    wrapped.insert("1.0", "hi", "m")
    assert wrapped._row_margins(1, 0) == (4, 0)


def test_a_colour_only_tag_leaves_the_fast_path_alone(wrapped):
    """Colours move nothing, so they must not cost the margin scan."""
    wrapped.tag_configure("c", foreground="red")
    assert wrapped._margined is False


def test_a_blank_line_inside_a_tag_is_indented(wrapped):
    """Measured against Tk, because the natural expectation is the opposite.

    An empty line has no characters to hang a margin on, so it looks as
    though it should collapse to the left edge. It does not: Tk reported
    bbox.x and dlineinfo.x of exactly the margin on an empty line and on a
    whitespace-only line, the same as on lines with text. Compared side by
    side, 5/5.

    The margin applies where the TAG applies. That is the whole rule, and it
    is why a blank line between two indented paragraphs stays indented.
    """
    wrapped.tag_configure("m", lmargin1=6, lmargin2=6)
    wrapped.insert("1.0", "first\n\nthird\n   \nfifth\n", "m")
    area = wrapped._text_area().x
    for line in range(1, 6):
        box = wrapped.bbox(f"{line}.0")
        assert box is not None, line
        assert box[0] - area == 6, f"line {line} should be indented like the rest"


def test_a_line_outside_the_tag_is_not_indented(wrapped):
    """The other half, and the real explanation for a line at the left edge.

    Measured in Tk: pressing Return at the end of a tagged paragraph gives a
    new line the tag does NOT cover, so it sits at x=0 - and it stays there
    when text is typed into it, because the tag still does not cover it.
    There is no moment where the text "pops" rightwards.
    """
    wrapped.tag_configure("m", lmargin1=6)
    wrapped.insert("1.0", "tagged\n", "m")
    wrapped.insert("end", "untagged\n")
    area = wrapped._text_area().x
    assert wrapped.bbox("1.0")[0] - area == 6
    assert wrapped.bbox("2.0")[0] - area == 0, "no tag, no margin"


def test_plain_lines_skip_the_tab_arithmetic(wrapped):
    """The fast path, and it is a repair rather than an optimisation.

    With no margins and no tab, a character is a cell and every row is the
    same width, which is what wrap_spans already assumes - so the layout
    walk is not needed and must not be paid for. Measured: doing it for
    every line cost a string slice, a list allocation and a Python loop
    each, and the redraw-cost test holds 5000 lines. On Python 3.14 that was
    +1.5% and invisible; on 3.10 and 3.11 it took the repaint past its
    budget and CI failed on exactly those two versions.

    Asserted through the wrap points rather than by timing, because a timing
    test here would be the flaky kind. If the fast path and the slow path
    ever disagree, this is what notices.
    """
    wrapped.insert("1.0", PARAGRAPH)
    plain = starts(wrapped)
    assert not wrapped._margined, "the fast path should be live"

    # Force the slow path with a margin of zero: same geometry, different code.
    wrapped.tag_configure("z", lmargin1=0)
    wrapped._margined = True
    assert starts(wrapped) == plain, "the two paths must agree on where rows break"


def test_a_line_with_a_tab_takes_the_slow_path_even_without_margins(wrapped):
    """A tab is wider than a cell, so the fast path cannot handle it."""
    wrapped.configure(tabs=10)
    wrapped.insert("1.0", "a\tb")
    assert wrapped.bbox("1.2")[0] - wrapped.bbox("1.0")[0] == 10


def test_a_disabled_redo_changes_nothing_and_keeps_the_history(history):
    history.edit_undo()
    history.configure(state="disabled")
    history.edit_redo()
    assert history.get("1.0", "end-1c") == "hello"
    history.configure(state="normal")
    history.edit_redo()
    assert history.get("1.0", "end-1c") == "hello world"


#: Index expressions and what Tk 9.0.2 makes of them in ``aaa bb``,
#: ``bbb-cc dd``, ``ccc``, ``ddd eee``, with insert at 2.1, a mark called
#: my-mark at 2.5 and 1.2-2.2 selected; None for ``bad text index``. Tk
#: applies the modifiers left to right, and tries the whole string as a mark
#: before splitting it. TkCurses-wmaq.
TK_INDICES = [
    ("1.1 linee", "1.6"),
    ("1.1 lines", "1.0"),
    ("1.1 line", None),
    ("3.0 lineend + 1c", "4.0"),
    ("3.0 lineend +1c", "4.0"),
    ("3.0 lineend+1c", "4.0"),
    ("3.2 +1c lineend", "3.3"),
    ("3.2 lineend -1c", "3.2"),
    ("3.0 linestart - 1c", "2.9"),
    ("insert linestart + 1 line", "3.0"),
    ("insert lineend - 2 chars linestart", "2.0"),
    ("insert +1c", "2.2"),
    ("insert+1c", "2.2"),
    ("insert + 1 chars", "2.2"),
    ("insert -1line", "1.1"),
    ("insert - 1 l", "1.1"),
    ("insert +2 ch", "2.3"),
    ("insert + 1 indices", "2.2"),
    ("end - 1 indices", "5.0"),
    ("end-1c", "5.0"),
    ("end -1 i", "5.0"),
    ("insert + 1 any lines", "3.1"),
    ("insert wordstart", "2.0"),
    ("insert wordend +1c", "2.4"),
    ("insert wordend + 1c wordend", "2.6"),
    ("2.1 wordstart - 1c", "1.6"),
    ("my-mark", "2.5"),
    ("my-mark +1c", None),
    ("my-mark lineend", None),
    ("sel.first", "1.2"),
    ("sel.first +1c lineend", "1.6"),
    ("1.0 + 1 c", "1.1"),
    ("1.0 +1 cha", "1.1"),
    ("3.0  +  1c", "3.1"),
    ("insert + x c", None),
    ("insert + 1 q", None),
    ("insert +", None),
    ("insert lineend junk", None),
    ("insert linestartx", None),
]


@pytest.mark.parametrize(("spec", "expected"), TK_INDICES)
def test_an_index_expression_resolves_as_in_tk(text, spec, expected):
    text.insert("1.0", "aaa bb\nbbb-cc dd\nccc\nddd eee\n")
    text.mark_set("insert", "2.1")
    text.mark_set("my-mark", "2.5")
    text.tag_add("sel", "1.2", "2.2")
    if expected is None:
        with pytest.raises(TclError, match="bad text index"):
            text.index(spec)
    else:
        assert text.index(spec) == expected
