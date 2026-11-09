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

"""Text's embedded windows and images.

Every expectation was measured on Tk 9.0.2 through tkinter unless a comment
says otherwise.
"""

from __future__ import annotations

import contextlib
import re
from types import SimpleNamespace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tkcurses import Button, Frame, Label, Misc, PhotoImage, TclError, Text, Toplevel
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


@pytest.fixture
def text(root):
    widget = Text(root, width=30, height=8)
    widget.insert("1.0", "abcdef")
    return widget


@pytest.fixture
def photo(root):
    return PhotoImage(master=root, width=4, height=4)


# --------------------------------------------------------------- creating


def test_window_create_answers_nothing_and_takes_one_index(text):
    button = Button(text, text="OK")
    assert text.window_create("1.3", window=button) is None
    assert text.index("1.end") == "1.7"
    assert text.get("1.0", "end") == "abcdef\n"
    assert text.get("1.3") == ""


def test_image_create_answers_the_images_name_made_unique(text, photo):
    assert text.image_create("1.0", image=photo) == str(photo)
    assert text.image_create("1.0", image=photo) == f"{photo}#1"
    assert text.image_create("1.0", image=photo, name="pic") == "pic"
    assert text.image_create("1.0", image=photo, name="pic") == "pic#1"
    # Tk keeps them in a hash table, so the order is not something to rely on.
    assert set(text.image_names()) == {str(photo), f"{photo}#1", "pic", "pic#1"}


def test_window_names_lists_the_embedded_windows(text):
    first, second = Button(text), Label(text)
    text.window_create("1.1", window=first)
    text.window_create("1.0", window=second)
    assert set(text.window_names()) == {str(first), str(second)}


def test_creating_at_end_puts_it_before_the_last_newline(text):
    button = Button(text)
    text.window_create("end", window=button)
    assert text.index(str(button)) == "1.6"


def test_a_window_annotation_may_be_empty(text):
    text.window_create("1.0")
    assert text.dump("1.0", window=True) == [("window", "", "1.0")]
    assert text.window_names() == ()


# ---------------------------------------------------------------- options


def test_window_options_read_back_as_tk_reads_them(text):
    button = Button(text)
    text.window_create("1.0", window=button, padx=2, pady="1", stretch="yes")
    assert text.window_cget("1.0", "window") == str(button)
    assert text.window_cget("1.0", "padx") == 2
    assert text.window_cget("1.0", "pady") == 1
    assert text.window_cget("1.0", "stretch") == 1
    assert text.window_cget("1.0", "-align") == "center"
    assert set(text.window_configure("1.0")) == {
        "align",
        "create",
        "padx",
        "pady",
        "stretch",
        "window",
    }


def test_image_options_read_back_as_tk_reads_them(text, photo):
    text.image_create("1.0", image=photo, align="top", padx=1)
    assert text.image_cget("1.0", "image") == str(photo)
    assert text.image_cget("1.0", "align") == "top"
    assert text.image_cget("1.0", "padx") == 1
    assert set(text.image_configure("1.0")) == {
        "align",
        "image",
        "name",
        "padx",
        "pady",
    }
    text.image_configure("1.0", align="bottom")
    assert text.image_cget("1.0", "align") == "bottom"


def test_window_config_is_window_configure(text):
    text.window_create("1.0", window=Button(text))
    text.window_config("1.0", align="top")
    assert text.window_cget("1.0", "align") == "top"


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"align": "x"}, 'bad align "x": must be baseline, bottom, center, or top'),
        ({"padx": "q"}, 'expected screen distance but got "q"'),
        ({"window": ".nosuch"}, 'bad window path name ".nosuch"'),
        ({"stretch": "maybe"}, 'expected boolean value but got "maybe"'),
        ({"bogus": 1}, 'unknown option "-bogus"'),
    ],
)
def test_bad_window_options_are_refused_in_tks_words(text, options, message):
    with pytest.raises(TclError, match=re.escape(message)):
        text.window_create("1.0", **options)
    assert text.get("1.0", "end") == "abcdef\n"
    assert text.index("1.end") == "1.6"


def test_a_missing_image_is_refused(text):
    with pytest.raises(TclError, match=re.escape('image "nosuch" does not exist')):
        text.image_create("1.0", image="nosuch")


def test_nothing_embedded_at_an_index_is_refused(text, photo):
    with pytest.raises(TclError, match=re.escape('no embedded window at index "1.0"')):
        text.window_cget("1.0", "align")
    text.image_create("1.0", image=photo)
    with pytest.raises(TclError, match=re.escape('no embedded window at index "1.0"')):
        text.window_configure("1.0", align="top")
    with pytest.raises(TclError, match=re.escape('no embedded image at index "1.1"')):
        text.image_cget("1.1", "align")


def test_only_a_window_inside_the_texts_master_may_be_embedded(root, text):
    elsewhere = Frame(Frame(root))
    for window in (Toplevel(root), text, elsewhere):
        with pytest.raises(TclError, match=re.escape(f"can't embed {window} in")):
            text.window_create("1.0", window=window)
    # A sibling - a child of the text's master - is allowed.
    text.window_create("1.0", window=Button(root))


# ------------------------------------------------------------ as an index


def test_a_windows_path_and_an_images_name_are_indices(text, photo):
    button = Button(text)
    text.window_create("1.2", window=button)
    text.image_create("1.5", image=photo, name="pic")
    assert text.index(str(button)) == "1.2"
    assert text.index("pic") == "1.5"
    assert text.index("pic+1c") == "1.6"


def test_count_indices_counts_it_and_chars_does_not(text):
    text.window_create("1.3", window=Button(text))
    assert text.count("1.0", "1.end", "chars") == (6,)
    assert text.count("1.0", "1.end", "indices") == (7,)


def test_search_passes_over_it_and_a_regexp_does_not_cross_it(text):
    text.window_create("1.3", window=Button(text))
    assert text.search("cd", "1.0") == "1.2"
    assert text.search("c.d", "1.0", regexp=True) == ""
    assert text.search("de", "1.0") == "1.4"


def test_dump_reports_it_between_the_text_round_it(text, photo):
    button = Button(text)
    text.window_create("1.3", window=button)
    text.image_create("1.5", image=photo)
    assert text.dump("1.0", "1.end", text=True, window=True, image=True) == [
        ("text", "abc", "1.0"),
        ("window", str(button), "1.3"),
        ("text", "d", "1.4"),
        ("image", str(photo), "1.5"),
        ("text", "ef", "1.6"),
    ]
    assert text.dump("1.0", "1.end", text=True) == [
        ("text", "abc", "1.0"),
        ("text", "d", "1.4"),
        ("text", "ef", "1.6"),
    ]


# ------------------------------------------------------ delete and undo


def test_deleting_a_windows_index_destroys_the_window(text):
    button = Button(text)
    text.window_create("1.3", window=button)
    text.delete("1.2", "1.5")
    assert not button.winfo_exists()
    assert text.window_names() == ()
    assert text.get("1.0", "end") == "abef\n"


def test_deleting_an_images_index_frees_its_name(text, photo):
    text.image_create("1.3", image=photo)
    text.delete("1.3")
    assert text.image_names() == ()
    assert text.image_create("1.0", image=photo) == str(photo)


def test_creating_one_is_not_an_undo_step(root):
    text = Text(root, undo=True)
    text.insert("1.0", "abc")
    text.edit_separator()
    text.window_create("1.1", window=Button(text))
    text.edit_undo()
    assert text.get("1.0", "end") == "\n"


def test_undoing_a_delete_brings_back_the_text_and_not_the_window(root):
    text = Text(root, undo=True)
    text.insert("1.0", "abcdef")
    text.edit_separator()
    button = Button(text)
    text.window_create("1.3", window=button)
    text.delete("1.2", "1.5")
    text.edit_undo()
    assert text.get("1.0", "end") == "abcdef\n"
    assert text.index("1.end") == "1.6"
    assert text.window_names() == ()


def test_undoing_the_insert_it_landed_in_takes_it_too(root):
    text = Text(root, undo=True)
    text.insert("1.0", "abcdef")
    text.edit_separator()
    button = Button(text)
    text.window_create("1.3", window=button)
    text.edit_undo()
    assert text.get("1.0", "end") == "\n"
    assert not button.winfo_exists()
    text.edit_redo()
    assert text.get("1.0", "end") == "abcdef\n"
    assert text.index("1.end") == "1.6"


def test_undo_before_it_still_lines_up(root, photo):
    text = Text(root, undo=True)
    text.insert("1.0", "hello")
    text.edit_separator()
    text.insert("1.5", " world")
    text.edit_separator()
    text.image_create("1.0", image=photo)
    text.edit_undo()
    assert text.get("1.0", "end") == "hello\n"
    assert text.index("1.end") == "1.6"
    text.edit_redo()
    assert text.get("1.0", "end") == "hello world\n"


# --------------------------------------------------------------- managing


def test_the_text_manages_the_window(text):
    button = Button(text)
    text.window_create("1.0", window=button)
    assert button.winfo_manager() == "text"


def test_packing_the_window_elsewhere_empties_its_annotation(root, text):
    button = Button(root)
    text.window_create("1.0", window=button)
    button.pack()
    assert button.winfo_manager() == "pack"
    assert text.window_cget("1.0", "window") == ""
    assert text.window_names() == ()


def test_embedding_a_window_again_empties_its_old_annotation(text):
    button = Button(text)
    text.window_create("1.0", window=button)
    text.window_create("1.5", window=button)
    assert text.window_cget("1.0", "window") == ""
    assert text.window_cget("1.5", "window") == str(button)
    assert text.window_names() == (str(button),)


def test_destroying_the_window_empties_its_annotation(text):
    button = Button(text)
    text.window_create("1.0", window=button)
    button.destroy()
    assert text.window_cget("1.0", "window") == ""
    assert text.index("1.end") == "1.7"


def test_create_makes_the_window_when_it_is_first_shown(root, text):
    made = []

    def create():
        made.append(Button(text, text="made"))
        return made[-1]

    text.window_create("1.0", create=create)
    assert made == []
    text.pack()
    root.update_layout()
    text._redraw()
    root.update_layout()
    assert len(made) == 1
    assert text.window_cget("1.0", "window") == str(made[0])
    assert made[0].winfo_manager() == "text"
    assert made[0].winfo_ismapped()


def test_a_disabled_text_still_embeds(root, photo):
    """As Tk's does: the manual's "no insertions or deletions" is about text."""
    text = Text(root, state="disabled")
    text.window_create("1.0", window=Button(text))
    text.image_create("1.0", image=photo)
    assert text.index("end") == "2.0"
    assert text.index("1.end") == "1.2"


def test_a_peer_shares_the_index_and_lays_out_no_window(root, text):
    """A difference from Tk, which shows the window in one peer at a time:
    here only the text that made it lays it out."""
    button = Button(text)
    text.window_create("1.3", window=button)
    text.peer_create(".peer")
    peer = text.nametowidget(".peer")
    assert peer.index(str(button)) == "1.3"
    assert peer.get("1.0", "end") == "abcdef\n"
    assert peer.window_names() == (str(button),)
    assert peer._embedded_windows == {}
    assert button.winfo_manager() == "text"


def test_the_width_of_its_character_is_the_windows(text):
    button = Button(text, text="OK")
    text.window_create("1.3", window=button, padx=1)
    text.pack()
    text.master.update_layout()
    assert text.count("1.3", "1.4", "xpixels") == (button.winfo_reqwidth() + 2,)


# ------------------------------------------------- the history, rebased

#: An edit: insert some text at a fraction of the way through, or delete a
#: span from a fraction of the way through.
EDITS = st.lists(
    st.tuples(
        st.booleans(),
        st.floats(0, 1),
        st.text(alphabet="ab\n", min_size=1, max_size=4),
        st.integers(1, 3),
    ),
    min_size=1,
    max_size=8,
)


def offset(text, fraction):
    size = len(text.get("1.0", "end-1c")) + len(text.window_names())
    return f"1.0+{int(fraction * size)}c"


@settings(max_examples=150, deadline=None)
@given(edits=EDITS, where=st.floats(0, 1), separate=st.booleans())
def test_undo_and_redo_still_line_up_after_an_embed(edits, where, separate):
    """Whatever the history, an embed anywhere leaves it whole: undoing
    everything empties the text and redoing everything gives back the text
    there was before the embed - the window having gone with an insertion
    it fell inside, or stayed between two."""
    root = Misc()
    text = Text(root, undo=True, autoseparators=False)
    for inserting, fraction, chars, length in edits:
        at = offset(text, fraction)
        if inserting:
            text.insert(at, chars)
        else:
            text.delete(at, f"{at}+{length}c")
        if separate:
            text.edit_separator()
    before = text.get("1.0", "end")
    text.window_create(offset(text, where), window=Button(text))
    with contextlib.suppress(TclError):
        while True:
            text.edit_undo()
    assert text.get("1.0", "end") == "\n"
    with contextlib.suppress(TclError):
        while True:
            text.edit_redo()
    assert text.get("1.0", "end") == before
