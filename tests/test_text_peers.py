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

"""Text peers, and the ``startline`` and ``endline`` options.

Each expectation was measured on Tcl/Tk 9.0.2, through ``peer create`` on a
Text holding ``line1`` to ``line10``, unless the test says otherwise.
TkCurses-gm66.13.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Misc, TclError, Text
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack

TEN = "\n".join(f"line{n}" for n in range(1, 11))


def stub_window(rect):
    return SimpleNamespace(rect=rect)


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(window_factory=stub_window, panel_factory=None)
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    return root


@pytest.fixture
def text(root):
    widget = Text(root, name="t")
    widget.insert("1.0", TEN)
    return widget


def peer(text, path=".p", **options):
    text.peer_create(path, **options)
    return text.nametowidget(path)


# --------------------------------------------------------------- making one


def test_a_peer_is_a_text_at_the_path_given(text):
    made = peer(text)
    assert isinstance(made, Text)
    assert made._w == ".p"
    assert made.winfo_class() == "Text"


def test_peer_create_returns_nothing(text):
    """As tkinter's: the path is all a program has of the peer."""
    assert text.peer_create(".p") is None


def test_a_peer_can_be_made_inside_another_widget(root, text):
    holder = Text(root, name="f")
    text.peer_create(".f.p")
    assert holder.nametowidget("p").get("1.0", "1.end") == "line1"


def test_peer_names_lists_the_others_and_not_itself(text):
    made = peer(text)
    second = peer(made, ".q")
    assert set(text.peer_names()) == {".p", ".q"}
    assert set(made.peer_names()) == {".t", ".q"}
    assert set(second.peer_names()) == {".t", ".p"}


def test_a_text_with_no_peers_names_none(text):
    assert text.peer_names() == ()


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("x", 'bad window path name "x"'),
        (".nope.x", 'bad window path name ".nope"'),
        (".", 'window name "" already exists in parent'),
        (".t", 'window name "t" already exists in parent'),
    ],
)
def test_a_path_tk_refuses_is_refused_with_its_message(text, path, message):
    with pytest.raises(TclError, match=f"^{message}$"):
        text.peer_create(path)


def test_a_refused_peer_leaves_nothing_behind(root, text):
    with pytest.raises(TclError, match="unknown option"):
        text.peer_create(".p", bogus=5)
    assert text.peer_names() == ()
    assert text._buffer.peers() == []
    assert "p" not in root.children


def test_a_peer_takes_its_creators_lines_and_undo_settings(root):
    made = Text(root, name="t", undo=True, maxundo=4, autoseparators=False, width=11)
    made.insert("1.0", TEN)
    made.configure(startline=2, endline=5)
    other = peer(made)
    assert other.cget("startline") == 2
    assert other.cget("endline") == 5
    assert other.cget("undo") is True
    assert other.cget("maxundo") == 4
    assert other.cget("autoseparators") is False
    # And nothing else: the rest are the defaults.
    assert other.cget("width") == 80


def test_options_given_to_peer_create_win(text):
    made = peer(text, endline=4, wrap="none")
    assert made.cget("endline") == 4
    assert made.cget("wrap") == "none"


def test_options_given_as_a_dictionary_win_too(text):
    text.configure(startline=2)
    text.peer_create(".p", {"startline": 4})
    assert text.nametowidget(".p").cget("startline") == 4


def test_a_peer_made_with_a_bad_line_pair_is_refused(text):
    with pytest.raises(TclError, match="-startline must be less than or equal"):
        text.peer_create(".p", startline=5, endline=2)
    assert text.peer_names() == ()


# ------------------------------------------------------------ what is shared


def test_the_text_is_shared(text):
    made = peer(text)
    made.insert("1.0", "new ")
    assert text.get("1.0", "1.end") == "new line1"
    text.delete("2.0", "3.0")
    assert made.get("2.0", "2.end") == "line3"


def test_insert_and_current_are_each_peers_own(text):
    made = peer(text)
    text.mark_set("insert", "10.6")
    text.mark_set("current", "5.0")
    made.mark_set("insert", "2.1")
    made.mark_set("current", "3.0")
    assert text.index("insert") == "10.6"
    assert made.index("insert") == "2.1"
    assert text.index("current") == "5.0"


def test_other_marks_are_shared(text):
    made = peer(text)
    text.mark_set("m", "4.1")
    assert made.index("m") == "4.1"
    made.mark_unset("m")
    assert "m" not in text.mark_names()


def test_mark_names_shows_only_this_peers_own_marks_and_them_first(text):
    """A mark set before the peer existed is older than the peer's own, and
    still comes after them, as in the widget it was made from."""
    text.mark_set("m", "1.2")
    made = peer(text)
    assert made.mark_names() == ("insert", "current", "m")


def test_sel_is_each_peers_own(text):
    made = peer(text)
    made.tag_add("sel", "1.0", "1.2")
    assert text.tag_ranges("sel") == []
    assert made.tag_ranges("sel") == ["1.0", "1.2"]


def test_other_tags_are_shared(text):
    made = peer(text)
    text.tag_add("t", "1.0", "2.0")
    assert made.tag_ranges("t") == ["1.0", "2.0"]
    assert made.tag_names() == ("sel", "t")


def test_a_tags_style_is_shared_but_sels_is_not(text):
    made = peer(text)
    text.tag_configure("t", foreground="blue")
    text.tag_configure("sel", background="red")
    assert made.tag_cget("t", "foreground") == "blue"
    assert made.tag_cget("sel", "background") != "red"
    assert text.tag_cget("sel", "background") == "red"


def test_deleting_a_tag_deletes_it_for_every_peer(text):
    made = peer(text)
    text.tag_add("t", "1.0", "2.0")
    made.tag_delete("t")
    assert "t" not in text.tag_names()
    assert text.tag_ranges("t") == []


def test_a_peers_edit_is_on_the_one_undo_stack(root):
    made = Text(root, name="t", undo=True)
    made.insert("1.0", "base")
    made.edit_separator()
    other = peer(made)
    other.insert("end", "P")
    made.edit_undo()
    assert made.get("1.0", "end-1c") == "base"


def test_whichever_peer_set_undo_last_decides(root):
    """Off in the peer made last, so nothing is recorded - though the first
    still reads back ``undo`` true."""
    made = Text(root, name="t", undo=True)
    made.insert("1.0", "base")
    made.edit_reset()
    other = peer(made, undo=False)
    made.insert("end", "A")
    other.insert("end", "P")
    assert made.cget("undo") is True
    made.configure(undo=True)
    with pytest.raises(TclError, match="nothing to undo"):
        made.edit_undo()


def test_the_modified_flag_is_shared(text):
    made = peer(text)
    text.edit_modified(False)
    made.insert("1.0", "x")
    assert text.edit_modified() == 1
    text.edit_modified(False)
    assert made.edit_modified() == 0


def test_every_peer_hears_modified_the_edited_one_first(text):
    made = peer(text)
    text.edit_modified(False)
    heard = []
    text.bind("<<Modified>>", lambda _: heard.append("t"))
    made.bind("<<Modified>>", lambda _: heard.append("p"))
    made.insert("1.0", "x")
    assert heard == ["p", "t"]


def test_destroying_the_creator_leaves_the_peer(text):
    made = peer(text)
    text.mark_set("m", "2.0")
    text.destroy()
    assert made.get("1.0", "1.end") == "line1"
    assert made.index("m") == "2.0"
    assert made.peer_names() == ()


def test_a_destroyed_peer_takes_its_own_marks_and_sel_with_it(text):
    made = peer(text)
    made.tag_add("sel", "1.0", "1.2")
    made.destroy()
    assert text.peer_names() == ()
    key = made._buffer._key
    store = text._buffer._store
    assert not [name for name in [*store.marks, *store.tags] if name.endswith(key)]


def test_an_edit_repaints_and_reports_every_peer(text, monkeypatch):
    seen = []
    made = peer(text, yscrollcommand=lambda *f: seen.append(f))
    painted = []
    monkeypatch.setattr(made, "_paint", lambda: painted.append(1))
    seen.clear()
    text.insert("1.0", "x")
    assert painted
    assert seen


# --------------------------------------------------- startline and endline


def test_the_line_options_default_to_no_limit(text):
    assert text.cget("startline") == ""
    assert text.cget("endline") == ""
    assert text.index("end") == "11.0"


def test_startline_makes_that_line_1_0(text):
    made = peer(text, startline=3, endline=6)
    assert made.get("1.0", "end") == "line3\nline4\nline5\n"
    assert made.index("end") == "4.0"


def test_endline_is_the_first_line_not_shown(text):
    text.configure(endline=10)
    assert text.index("end") == "10.0"
    assert text.get("9.0", "9.end") == "line9"


@pytest.mark.parametrize(
    ("value", "kept"),
    [(1, 1), (10, 10), (11, 11), (" 3", 3), (0, ""), (-1, ""), (12, ""), ("", "")],
)
def test_a_line_is_kept_only_from_1_to_one_past_the_last(text, value, kept):
    text.configure(startline=value)
    assert text.cget("startline") == kept


@pytest.mark.parametrize("value", ["3.0", "x"])
def test_a_line_that_is_not_an_integer_is_refused(text, value):
    with pytest.raises(TclError, match=f'^expected integer but got "{value}"$'):
        text.configure(endline=value)


def test_startline_after_endline_is_refused_and_changes_nothing(text):
    text.configure(startline=5)
    with pytest.raises(TclError, match=r"^-startline must be less than or equal"):
        text.configure(endline=3)
    assert text.cget("startline") == 5
    assert text.cget("endline") == ""


def test_startline_after_an_existing_endline_is_refused(text):
    text.configure(endline=3)
    with pytest.raises(TclError, match=r"^-startline must be less than or equal"):
        text.configure(startline=5)


@pytest.mark.parametrize(("start", "end"), [(6, 6), (11, "")])
def test_a_window_of_no_lines_holds_nothing_at_all(text, start, end):
    text.configure(startline=start, endline=end)
    assert text.index("end") == "1.0"
    assert text.get("1.0", "end") == ""


def test_the_lines_shown_follow_edits_inside_them(text):
    made = peer(text, startline=3, endline=6)
    text.insert("4.0", "X\n")
    assert made.get("1.0", "end") == "line3\nX\nline4\nline5\n"
    assert (made.cget("startline"), made.cget("endline")) == (3, 7)
    text.delete("4.0", "5.0")
    assert (made.cget("startline"), made.cget("endline")) == (3, 6)


def test_a_line_inserted_at_the_start_edge_is_inside(text):
    made = peer(text, startline=3, endline=6)
    text.insert("3.0", "N\n")
    assert made.get("1.0", "end") == "N\nline3\nline4\nline5\n"
    assert (made.cget("startline"), made.cget("endline")) == (3, 7)


@pytest.mark.parametrize("inserted", ["X\n", "X"])
def test_text_inserted_at_the_end_edge_is_outside(text, inserted):
    made = peer(text, startline=3, endline=6)
    text.insert("6.0", inserted)
    assert made.get("1.0", "end") == "line3\nline4\nline5\n"
    assert made.cget("endline") == 6


def test_text_at_the_end_of_the_last_line_is_inside(text):
    made = peer(text, startline=3, endline=6)
    text.insert("5.end", "Y")
    assert made.get("3.0", "3.end") == "line5Y"


def test_a_start_edge_left_part_way_along_a_line_takes_the_whole_line(text):
    made = peer(text, startline=3, endline=6)
    text.delete("2.2", "3.0")
    assert made.get("1.0", "end") == "liline3\nline4\nline5\n"
    assert (made.cget("startline"), made.cget("endline")) == (2, 5)


def test_an_end_edge_left_part_way_along_a_line_leaves_the_whole_line(text):
    made = peer(text, startline=3, endline=6)
    text.delete("5.2", "6.0")
    assert made.get("1.0", "end") == "line3\nline4\n"
    assert (made.cget("startline"), made.cget("endline")) == (3, 5)


def test_configure_with_no_options_reports_where_the_lines_moved(text):
    made = peer(text, startline=3, endline=6)
    text.insert("1.0", "zero\n")
    assert made.configure()["startline"] == 4


def test_a_peer_cannot_delete_its_last_newline(text):
    made = peer(text, startline=3, endline=6)
    made.delete("1.0", "end")
    assert made.get("1.0", "end") == "\n"
    assert (
        text.get("1.0", "end") == "line1\nline2\n\nline6\nline7\nline8\nline9\nline10\n"
    )
    made.insert("1.0", "hello")
    assert text.get("3.0", "3.end") == "hello"


def test_a_peer_whose_lines_are_deleted_elsewhere_is_an_empty_shell(text):
    made = peer(text, startline=3, endline=6)
    text.delete("3.0", "6.0")
    assert made.index("end") == "1.0"
    assert made.get("1.0", "end") == ""


def test_an_empty_shell_takes_no_text(text):
    """A departure: Tk puts the text into the store at the shell's place,
    where the shell itself cannot show it. See ARCHITECTURE.md."""
    made = peer(text, startline=5, endline=5)
    made.insert("1.0", "zz")
    made.delete("1.0", "end")
    assert text.get("1.0", "end-1c") == TEN


def test_insert_at_end_goes_before_the_windows_last_newline(text):
    made = peer(text, startline=3, endline=6)
    made.insert("end", "Z")
    assert text.get("5.0", "5.end") == "line5Z"


def test_indices_are_held_inside_the_window(text):
    made = peer(text, startline=3, endline=6)
    assert made.index("99.0") == "4.0"
    assert made.index("end+5l") == "4.0"
    assert made.index("2.0+20c") == "4.0"
    assert made.index("1.0-1c") == "1.0"


def test_a_shared_mark_outside_the_window_is_listed_but_not_an_index(text):
    made = peer(text, startline=3, endline=6)
    text.mark_set("m", "1.2")
    assert "m" in made.mark_names()
    # ValueError, where tkinter's is a TclError: TkCurses-g7nf.
    with pytest.raises(ValueError, match='bad text index "m"'):
        made.index("m")


def test_a_shared_mark_inside_is_renumbered(text):
    made = peer(text, startline=3, endline=6)
    text.mark_set("m2", "4.1")
    assert made.index("m2") == "2.1"


def test_tag_ranges_are_cut_to_the_window(text):
    made = peer(text, startline=3, endline=6)
    text.tag_add("t", "1.0", "end")
    text.tag_add("u", "1.0", "2.0")
    assert made.tag_ranges("t") == ["1.0", "4.0"]
    assert made.tag_ranges("u") == []
    assert made.tag_names("1.0") == ("t",)


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [("1.0", "end", ("1.0", "4.0")), ("5.1", "8.0", ("3.1", "4.0"))],
)
def test_a_tag_crossing_an_edge_answers_as_its_ranges_do(text, first, last, expected):
    """A departure: Tk's ``.last`` and ``nextrange`` disagree with its own
    ``tag ranges`` here. See ARCHITECTURE.md."""
    made = peer(text, startline=3, endline=6)
    text.tag_add("x", first, last)
    assert tuple(made.tag_ranges("x")) == expected
    assert (made.index("x.first"), made.index("x.last")) == expected
    assert made.tag_nextrange("x", "1.0") == expected
    assert made.tag_prevrange("x", "end") == expected


def test_search_stays_inside_the_window(text):
    made = peer(text, startline=3, endline=6)
    assert made.search("line1", "1.0") == ""
    assert made.search("line4", "1.0") == "2.0"


def test_insert_is_held_at_the_end_of_a_window_moved_above_it(text):
    made = peer(text, startline=3, endline=6)
    made.mark_set("insert", "1.2")
    made.configure(startline=1, endline=2)
    assert made.index("insert") == "1.5"


def test_insert_is_moved_not_only_hidden(text):
    """Back over where it was, it stays where the window put it."""
    made = peer(text, startline=3, endline=6)
    made.mark_set("insert", "1.2")
    made.configure(startline=1, endline=2)
    made.configure(startline=3, endline=6)
    assert made.index("insert") == "1.0"


def test_insert_is_held_at_the_start_of_a_window_moved_below_it(text):
    made = peer(text, startline=3, endline=6)
    made.mark_set("insert", "1.2")
    made.configure(startline=7, endline=9)
    assert made.index("insert") == "1.0"
    # And it is there now, which is past the end of the lines moved back to.
    made.configure(startline=3, endline=6)
    assert made.index("insert") == "3.5"


def test_tagging_in_a_peer_tags_the_lines_it_shows(text):
    made = peer(text, startline=3, endline=6)
    made.tag_add("t", "1.0", "2.0")
    assert text.tag_ranges("t") == ["3.0", "4.0"]
    made.tag_remove("t", "1.2", "1.4")
    assert text.tag_ranges("t") == ["3.0", "3.2", "3.4", "4.0"]


def test_a_peer_scrolled_past_what_is_left_is_brought_back(text):
    made = peer(text)
    made._allocate(Rect(0, 0, 22, 5))
    made._map()
    made.yview("scroll", 8, "units")
    assert made._top > 0
    text.delete("2.0", "end")
    # Two lines are left - line1 and the one the final newline ends - and
    # the view may start on the last of them, as it may anywhere.
    assert made._top == 1


def test_insert_set_at_end_stays_before_the_final_newline(root):
    """``current`` may sit at end and ``insert`` may not, in Tk too."""
    made = Text(root, name="t")
    made.insert("1.0", "abc\ndef")
    made.mark_set("insert", "end")
    made.mark_set("current", "end")
    assert made.index("insert") == "2.3"
    assert made.index("current") == "3.0"


def test_a_window_draws_only_its_own_lines(root, text):
    made = peer(text, startline=3, endline=6)
    assert made._buffer.lines == ["line3", "line4", "line5"]
    assert len(made._display_lines()) == 3
