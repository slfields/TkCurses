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

"""Text's edit, count, dump, replace, tag bindings, scan and the rest.

Every expectation was measured on Tk 9.0.2 through tkinter, or read in
Tk's C where a comment says so.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from tkcurses import Misc, TclError, Text
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    return root


def make(root, **kw):
    options = {"width": 20, "height": 5, "wrap": "none", **kw}
    widget = Text(root, **options)
    widget._allocate(Rect(0, 0, 22, 7))
    widget._map()
    return widget


@pytest.fixture
def text(root):
    return make(root)


# ----------------------------------------------------------------- insert


def test_insert_takes_text_and_tag_list_pairs(text):
    text.insert("1.0", "a", "t1", "b", "t2")
    assert text.get("1.0", "end") == "ab\n"
    assert text.tag_ranges("t1") == ["1.0", "1.1"]
    assert text.tag_ranges("t2") == ["1.1", "1.2"]


@pytest.mark.parametrize(
    ("tags", "expected"), [("my tag", ("my", "tag")), (("p", "q"), ("p", "q"))]
)
def test_a_tag_list_is_a_tuple_or_names_with_spaces(text, tags, expected):
    text.insert("1.0", "x", tags)
    assert text.tag_names("1.0") == expected


def test_text_after_the_last_tag_list_has_none(text):
    text.insert("1.0", "x", "p", "y")
    assert text.get("1.0", "end") == "xy\n"
    assert text.tag_names("1.1") == ()


def test_a_given_tag_list_replaces_the_tags_around(text):
    text.insert("1.0", "ab")
    text.tag_add("k", "1.0", "1.2")
    text.insert("1.1", "Z")
    assert text.tag_names("1.1") == ("k",)
    text.insert("1.1", "W", ())
    assert text.tag_names("1.1") == ()
    text.insert("1.1", "V", "q")
    assert text.tag_names("1.1") == ("q",)


def test_tags_go_on_text_inserted_at_the_end(text):
    text.insert("1.0", "ab")
    text.insert("end", "cd", "t")
    assert text.tag_ranges("t") == ["1.2", "1.4"]


# ---------------------------------------------------------------- replace


@pytest.fixture
def undoable(root):
    widget = make(root, undo=True)
    widget.insert("1.0", "hello world")
    widget.edit_separator()
    return widget


def test_replace_moves_marks_as_a_delete_and_an_insert(undoable):
    undoable.mark_set("insert", "1.8")
    undoable.mark_set("m", "1.2")
    undoable.mark_set("n", "1.1")
    undoable.mark_gravity("n", "left")
    undoable.replace("1.0", "1.5", "HI")
    assert undoable.get("1.0", "1.end") == "HI world"
    assert undoable.index("insert") == "1.5"
    assert undoable.index("m") == "1.2"
    assert undoable.index("n") == "1.0"


def test_a_cursor_inside_the_replaced_text_keeps_its_place(undoable):
    undoable.mark_set("insert", "1.1")
    undoable.replace("1.0", "1.2", "XYZW")
    assert undoable.get("1.0", "1.end") == "XYZWllo world"
    assert undoable.index("insert") == "1.1"


def test_a_cursor_inside_goes_no_further_than_the_new_text(undoable):
    undoable.mark_set("insert", "1.4")
    undoable.replace("1.0", "1.5", "ab")
    assert undoable.index("insert") == "1.2"


def test_replace_undoes_in_one_step(undoable):
    undoable.replace("1.0", "1.5", "HI")
    undoable.edit_undo()
    assert undoable.get("1.0", "1.end") == "hello world"


def test_replace_takes_tag_lists(undoable):
    undoable.replace("1.0", "1.5", "a", "t1", "b", "t2")
    assert undoable.get("1.0", "1.end") == "ab world"
    assert undoable.tag_ranges("t1") == ["1.0", "1.1"]
    assert undoable.tag_ranges("t2") == ["1.1", "1.2"]


def test_replace_backwards_is_refused_in_tks_words(undoable):
    with pytest.raises(
        TclError, match=re.escape('index "1.0" before "1.3" in the text')
    ):
        undoable.replace("1.3", "1.0", "z")


def test_a_disabled_text_replaces_nothing(undoable):
    undoable.configure(state="disabled")
    undoable.replace("1.0", "1.2", "QQ")
    assert undoable.get("1.0", "1.end") == "hello world"


# ------------------------------------------------------------------- edit


def test_edit_answers_and_acts_as_tk(undoable):
    assert undoable.edit("modified") == 1
    assert undoable.edit("canundo") == 1
    assert undoable.edit("canredo") == 0
    assert undoable.edit("undo")
    assert undoable.get("1.0", "end") == "\n"
    assert undoable.edit("canredo") == 1
    assert undoable.edit("redo")
    assert undoable.edit("separator") == ""
    assert undoable.edit("reset") == ""
    assert undoable.edit("canundo") == 0
    assert undoable.edit("modified", 0) == ""
    assert undoable.edit_modified() == 0


def test_edit_cannot_undo_while_undo_is_off(text):
    text.insert("1.0", "x")
    assert text.edit("canundo") == 0


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ("bogus",),
            'bad edit option "bogus": must be canundo, canredo, modified, redo,'
            " reset, separator, or undo",
        ),
        ((), 'wrong # args: should be ".!text edit option ?arg ...?"'),
    ],
)
def test_a_bad_edit_is_refused_in_tks_words(root, args, message):
    widget = make(root)
    with pytest.raises(TclError) as caught:
        widget.edit(*args)
    assert str(caught.value) == message.replace(".!text", widget._w)


# ------------------------------------------------------------------ count


@pytest.fixture
def three(text):
    text.insert("1.0", "hello world\nsecond line\nthird 中文 x")
    return text


@pytest.mark.parametrize(
    ("first", "last", "options", "kw", "expected"),
    [
        ("1.0", "2.0", (), {}, (12,)),
        ("1.0", "2.0", ("chars",), {}, (12,)),
        ("1.0", "3.0", ("lines",), {}, (2,)),
        ("1.0", "3.0", ("chars", "lines"), {}, (24, 2)),
        ("2.0", "1.0", (), {}, (-12,)),
        ("1.0", "1.0", (), {}, None),
        ("1.0", "1.0", ("lines",), {}, None),
        ("1.0", "1.0", ("lines", "chars"), {}, (0, 0)),
        ("1.0", "2.0", ("indices",), {}, (12,)),
        ("1.0", "2.0", ("displaychars",), {}, (12,)),
        ("1.0", "3.0", ("update", "lines"), {}, 2),
        ("1.0", "3.0", ("lines",), {"return_ints": True}, 2),
        ("1.0", "2.0", (), {"return_ints": True}, 12),
        ("1.0", "1.0", (), {"return_ints": True}, 0),
        ("3.0", "3.end", (), {}, (10,)),
    ],
)
def test_count_as_tkinter_shapes_it(three, first, last, options, kw, expected):
    assert three.count(first, last, *options, **kw) == expected


def test_count_in_cells(three):
    assert three.count("1.0", "1.5", "xpixels") == (5,)
    assert three.count("1.0", "3.0", "ypixels") == (2,)
    assert three.count("1.0", "3.0", "displaylines") == (2,)


def test_count_display_lines_counts_wrapped_rows(root):
    widget = make(root, wrap="char")
    widget.insert("1.0", "x" * 45 + "\nend")
    assert widget.count("1.0", "2.0", "displaylines") == (3,)
    assert widget.count("1.0", "2.0", "lines") == (1,)


def test_count_takes_an_unambiguous_abbreviation(three):
    assert three.count("1.0", "3.0", "li") == (2,)


def test_a_bad_count_option_is_refused_in_tks_words(three):
    with pytest.raises(TclError) as caught:
        three.count("1.0", "2.0", "bogus")
    assert str(caught.value) == (
        'bad option "-bogus": must be -chars, -displaychars, -displayindices,'
        " -displaylines, -indices, -lines, -update, -xpixels, or -ypixels"
    )


def test_count_refuses_a_bad_index(three):
    with pytest.raises(TclError, match='bad text index "zz"'):
        three.count("zz", "1.0")


# ------------------------------------------------------------------- dump


@pytest.fixture
def marked(text):
    text.insert("1.0", "hello world\nsecond line\nthird")
    text.tag_add("b", "1.2", "1.5")
    text.tag_add("i", "1.4", "2.2")
    text.mark_set("m", "1.3")
    text.mark_set("insert", "2.1")
    text.mark_set("current", "3.5")
    return text


def test_dump_everything_in_tks_order(marked):
    assert marked.dump("1.0", "end") == [
        ("text", "he", "1.0"),
        ("tagon", "b", "1.2"),
        ("text", "l", "1.2"),
        ("mark", "m", "1.3"),
        ("text", "l", "1.3"),
        ("tagon", "i", "1.4"),
        ("text", "o", "1.4"),
        ("tagoff", "b", "1.5"),
        ("text", " world\n", "1.5"),
        ("text", "s", "2.0"),
        ("mark", "insert", "2.1"),
        ("text", "e", "2.1"),
        ("tagoff", "i", "2.2"),
        ("text", "cond line\n", "2.2"),
        ("text", "third", "3.0"),
        ("mark", "current", "3.5"),
        ("text", "\n", "3.5"),
    ]


def test_dump_one_kind(marked):
    assert marked.dump("1.0", "end", tag=True) == [
        ("tagon", "b", "1.2"),
        ("tagon", "i", "1.4"),
        ("tagoff", "b", "1.5"),
        ("tagoff", "i", "2.2"),
    ]
    assert marked.dump("1.0", "3.0", text=True) == [
        ("text", "hello world\n", "1.0"),
        ("text", "second line\n", "2.0"),
    ]


def test_dump_stops_before_its_second_index(marked):
    assert marked.dump("1.0", "1.3", mark=True) == []
    assert marked.dump("1.3", mark=True) == [("mark", "m", "1.3")]


def test_a_tag_already_on_at_the_start_is_not_reported(marked):
    assert marked.dump("1.3", "1.4") == [("mark", "m", "1.3"), ("text", "l", "1.3")]


def test_at_one_index_offs_then_ons_then_marks(text):
    text.insert("1.0", "abcdefgh")
    text.tag_add("b", "1.2", "1.5")
    text.mark_set("m", "1.5")
    text.tag_add("c", "1.5", "1.6")
    assert text.dump("1.5", "1.7") == [
        ("tagoff", "b", "1.5"),
        ("tagon", "c", "1.5"),
        ("mark", "m", "1.5"),
        ("text", "f", "1.5"),
        ("tagoff", "c", "1.6"),
        ("text", "g", "1.6"),
    ]


def test_toggles_at_one_index_in_tks_order(text):
    text.insert("1.0", "abcdef")
    text.tag_add("x", "1.0", "1.3")
    text.tag_add("y", "1.3", "1.5")
    text.tag_add("w", "1.3", "1.4")
    text.tag_add("v", "1.0", "1.3")
    assert text.dump("1.0", "end", tag=True) == [
        ("tagon", "v", "1.0"),
        ("tagon", "x", "1.0"),
        ("tagoff", "x", "1.3"),
        ("tagoff", "v", "1.3"),
        ("tagon", "w", "1.3"),
        ("tagon", "y", "1.3"),
        ("tagoff", "w", "1.4"),
        ("tagoff", "y", "1.5"),
    ]


def test_marks_at_one_index_newest_first(text):
    text.insert("1.0", "abcdef")
    for name in ("a", "b", "z"):
        text.mark_set(name, "1.6")
    assert [value for _, value, _ in text.dump("1.6", mark=True)] == [
        "z",
        "b",
        "a",
        "insert",
        "current",
    ]


def test_a_fresh_text_dumps_its_two_marks_and_newline(text):
    assert text.dump("1.0", "end") == [
        ("mark", "insert", "1.0"),
        ("mark", "current", "1.0"),
        ("text", "\n", "1.0"),
    ]


def test_a_tag_stopping_at_the_end_is_reported_only_there(text):
    text.insert("1.0", "ab\nxy")
    text.tag_add("d", "1.0", "end")
    assert text.dump("2.0", "end", tag=True) == [("tagoff", "d", "3.0")]
    assert text.dump("end") == []
    assert text.dump("2.0", "1.0") == []


def test_dump_calls_a_command_with_each_triple(marked):
    seen = []
    assert (
        marked.dump("1.0", "1.2", command=lambda *triple: seen.append(triple)) is None
    )
    assert seen == [("text", "he", "1.0")]


def test_a_bad_dump_keyword_is_refused_in_tks_words(marked):
    with pytest.raises(TclError) as caught:
        marked.dump("1.0", "1.2", bogus=True)
    assert str(caught.value) == (
        'bad option "-bogus": must be -all, -command, -image, -mark, -tag,'
        " -text, or -window"
    )


# ------------------------------------------------------------ tag binding


@pytest.fixture
def linked(text):
    text.insert("1.0", "plain LINK plain\nsecond")
    text.tag_add("link", "1.6", "1.10")
    return text


def cell_of(widget, index):
    """The window cell an index is drawn at."""
    area = widget._text_area()
    line, char = map(int, widget.index(index).split("."))
    return area.x + char, area.y + line - 1


def test_the_pointer_crossing_a_tag_enters_and_leaves_it(linked):
    log = []
    for sequence in ("<Enter>", "<Leave>", "<Motion>"):
        linked.tag_bind(
            "link",
            sequence,
            lambda e, s=sequence: log.append((s, linked.index("current"))),
        )
    x, y = cell_of(linked, "1.7")
    linked.event_generate("<Motion>", x=1, y=y)
    linked.event_generate("<Motion>", x=x, y=y)
    linked.event_generate("<Motion>", x=x + 1, y=y)
    linked.event_generate("<Motion>", x=1, y=y)
    assert log == [
        ("<Enter>", "1.7"),
        ("<Motion>", "1.7"),
        ("<Motion>", "1.8"),
        ("<Leave>", "1.8"),
    ]
    assert linked.index("current") == "1.0"


def test_a_tag_binding_runs_before_the_widgets(linked):
    log = []
    linked.tag_bind("link", "<Button-1>", lambda e: log.append("tag"))
    linked.bind("<Button-1>", lambda e: log.append("widget"))
    x, y = cell_of(linked, "1.7")
    linked.event_generate("<Motion>", x=x, y=y)
    linked.event_generate("<Button-1>", x=x, y=y)
    assert log == ["tag", "widget"]


def test_nothing_is_picked_while_a_button_is_held(linked):
    log = []
    linked.tag_bind("link", "<Enter>", lambda e: log.append("enter"))
    x, y = cell_of(linked, "1.7")
    linked.event_generate("<Button-1>", x=1, y=y)
    linked.event_generate("<Motion>", x=x, y=y)
    assert log == []
    linked.event_generate("<ButtonRelease-1>", x=x, y=y)
    assert log == ["enter"]


def test_past_the_end_of_a_line_is_on_no_tag(text):
    text.insert("1.0", "ab")
    text.tag_add("all", "1.0", "end")
    log = []
    text.tag_bind("all", "<Enter>", lambda e: log.append("enter"))
    x, y = cell_of(text, "1.0")
    text.event_generate("<Motion>", x=x + 10, y=y)
    assert log == []
    text.event_generate("<Motion>", x=x, y=y)
    assert log == ["enter"]


@pytest.mark.parametrize(
    ("insert", "current", "fires"),
    [("1.7", "1.0", True), ("1.0", "1.7", False), ("1.0", "1.0", False)],
)
def test_with_nothing_picked_a_key_goes_to_the_tags_at_insert(
    linked, insert, current, fires
):
    log = []
    linked.tag_bind("link", "<Key>", lambda e: log.append(1))
    linked.mark_set("insert", insert)
    linked.mark_set("current", current)
    linked.event_generate("<Key>", keysym="F5")
    assert bool(log) == fires


def test_a_key_goes_to_the_tags_under_the_pointer_once_picked(linked):
    log = []
    linked.tag_bind("link", "<Key>", lambda e: log.append(1))
    x, y = cell_of(linked, "1.7")
    linked.event_generate("<Motion>", x=x, y=y)
    linked.mark_set("insert", "1.0")
    linked.event_generate("<Key>", keysym="F5")
    assert log == [1]


def test_tag_bindings_run_lowest_priority_first(linked):
    linked.tag_add("over", "1.6", "1.10")
    log = []
    linked.tag_bind("over", "<Button-1>", lambda e: log.append("over"))
    linked.tag_bind("link", "<Button-1>", lambda e: log.append("link"))
    x, y = cell_of(linked, "1.7")
    linked.event_generate("<Motion>", x=x, y=y)
    linked.event_generate("<Button-1>", x=x, y=y)
    assert log == ["link", "over"]
    # The order is taken when the pointer is picked, as tkTextTag.c's
    # TagBindEvent does not sort again: a raise shows at the next pick.
    linked.tag_raise("link")
    log.clear()
    linked.event_generate("<Button-1>", x=x, y=y)
    assert log == ["link", "over"]
    linked.event_generate("<ButtonRelease-1>", x=1, y=y)
    linked.event_generate("<Motion>", x=x, y=y)
    log.clear()
    linked.event_generate("<Button-1>", x=x, y=y)
    assert log == ["over", "link"]


def test_tag_bind_reads_back_and_unbinds(linked):
    def handler(event):
        return None

    funcid = linked.tag_bind("link", "<Button-2>", handler)
    assert linked.tag_bind("link") == ("<Button-2>",)
    assert linked.tag_bind("link", "<Button-2>") == (handler,)
    linked.tag_unbind("link", "<Button-2>", funcid)
    assert linked.tag_bind("link") == ()


def test_binding_an_unknown_tag_makes_it(linked):
    linked.tag_bind("nosuch", "<Button-1>", lambda e: None)
    assert "nosuch" in linked.tag_names()


def test_an_event_tk_will_not_bind_on_a_tag_is_refused(linked):
    with pytest.raises(TclError) as caught:
        linked.tag_bind("link", "<Configure>", lambda e: None)
    assert str(caught.value) == (
        "requested illegal events; only key, button, motion, enter, leave,"
        " and virtual events may be used"
    )


def test_deleting_a_tag_forgets_its_bindings(linked):
    linked.tag_bind("link", "<Button-1>", lambda e: None)
    linked.tag_delete("link")
    assert linked.tag_bind("link") == ()


def test_peers_share_tag_bindings(linked):
    linked.peer_create(".peer")
    peer = linked.nametowidget(".peer")
    linked.tag_bind("link", "<Button-1>", lambda e: None)
    assert peer.tag_bind("link") == ("<Button-1>",)


# --------------------------------------------------------- scan, the rest


def test_scan_dragto_scrolls_gain_times_the_drag(root):
    widget = make(root)
    widget.insert("1.0", "\n".join("x" * 60 for _ in range(40)))
    widget.scan_mark(10, 3)
    widget.scan_dragto(9, 2)
    assert widget._left == 10
    assert widget.index("@0,0").startswith("11.")


def test_a_scan_that_hits_an_edge_starts_again_from_there(root):
    widget = make(root)
    widget.insert("1.0", "\n".join("x" * 60 for _ in range(40)))
    widget.scan_mark(10, 3)
    widget.scan_dragto(20, 3)
    assert widget._left == 0
    widget.scan_dragto(19, 3)
    assert widget._left == 10


def test_scan_wants_integers(text):
    with pytest.raises(TclError, match=re.escape('expected integer but got "1.5"')):
        text.scan_mark(1.5, 2)


def test_debug_is_one_flag_for_every_text(root):
    first, second = make(root), make(root)
    assert first.debug() is False
    first.debug(1)
    assert second.debug() is True
    second.debug(0)


def test_yview_pickplace_brings_an_index_into_view(root):
    widget = make(root)
    widget.insert("1.0", "\n".join(str(n) for n in range(1, 41)))
    widget.yview_pickplace("30.0")
    assert widget.index("@0,1").split(".")[0] != "1"
    with pytest.raises(TclError, match=re.escape("yview -pickplace lineNum|index")):
        widget.yview_pickplace()
