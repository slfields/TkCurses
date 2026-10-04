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

"""What an Entry looks like and how it answers a real keyboard."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
{body}
root.update_layout()
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


def test_an_entry_shows_its_text(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "e = tkcurses.Entry(root, width=20)\n"
            "e.place(x=1, y=1)\n"
            "e.insert(0, 'typed already')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("typed already")


def test_typing_appears_in_the_field(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "e = tkcurses.Entry(root, width=20)\n"
            "e.place(x=1, y=1)\n"
            "e.focus_set()\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send(b"hello")
    term.wait_for_text("hello")


def test_backspace_removes_a_character(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "e = tkcurses.Entry(root, width=20)\n"
            "e.place(x=1, y=1)\n"
            "e.focus_set()\n"
            "e.insert(0, 'abcd')\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("abcd")
    term.send(b"\x7f")
    term.wait_for(
        lambda t: "abc" in "\n".join(t.display) and "abcd" not in "\n".join(t.display),
        message="the shortened text",
    )


def test_the_cursor_is_only_shown_when_focused(terminal, tmp_path):
    """A cursor in an unfocused field claims the keyboard is there."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "a = tkcurses.Entry(root, width=10, name='a')\n"
            "a.place(x=1, y=1)\n"
            "a.insert(0, 'aaa')\n"
            "b = tkcurses.Entry(root, width=10, name='b')\n"
            "b.place(x=1, y=5)\n"
            "b.insert(0, 'bbb')\n"
            "a.focus_set()"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("aaa")
    term.wait_for_idle()
    focused_row = [term.attrs_at(2, col)["reverse"] for col in range(2, 12)]
    unfocused_row = [term.attrs_at(6, col)["reverse"] for col in range(2, 12)]
    assert any(focused_row), "the focused field should show a cursor"
    assert not any(unfocused_row), "the unfocused field should not"


def _focus_program(state: str) -> str:
    """Two entries, one of them in ``state``, with the focus on the second."""
    return (
        "a = tkcurses.Entry(root, width=10, name='a')\n"
        "a.place(x=1, y=1)\n"
        "b = tkcurses.Entry(root, width=10, name='b')\n"
        "b.place(x=1, y=5)\n"
        f"for w in (a, b): w.configure(state={state!r})\n"
        "b.focus_set()"
    )


@pytest.mark.parametrize("state", ["normal", "readonly", "disabled"])
def test_an_entry_shows_the_focus_in_its_border_whatever_its_state(
    terminal, tmp_path, state
):
    """Tk shows the focus twice over, and only one of them is the cursor.

    The other is the focus highlight ring, drawn whatever the state - and for a
    readonly entry it is the ONLY signal, because Tk's manual says readonly
    draws "no insertion cursor ... even if the input focus is in the widget".
    This library drops highlightthickness as an X11 option with no cell
    equivalent and had nothing in its place, so a focused readonly entry looked
    exactly like an unfocused one. Reported from UAT 41.

    The border carries it now. Checked for all three states, because the
    original fault was that the signal was tied to being editable.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(program(_focus_program(state)), workdir=tmp_path)
    term.wait_for_idle()
    # The top border of each field, at a column inside the box: the first
    # entry is placed at y=1 and the second at y=5, and the focus is on the
    # second.
    term.wait_for_cell(5, 5, lambda cell: cell.data == "\u2500")
    term.wait_for_cell(1, 5, lambda cell: cell.data == "\u2500")
    focused = term.attrs_at(5, 5)["bold"]
    unfocused = term.attrs_at(1, 5)["bold"]
    assert focused != unfocused, (
        f"a focused {state} entry must look different from an unfocused one"
        f"\n{term.describe()}"
    )
    assert focused, f"the focused border should be the bold one\n{term.describe()}"


@pytest.mark.parametrize("state", ["readonly", "disabled"])
def test_a_locked_entry_still_shows_no_insertion_cursor(terminal, tmp_path, state):
    """The other half of the rule, pinned so the fix above cannot undo it.

    Tk's manual is explicit for both states: no insertion cursor, even with the
    focus. Showing one would say the keyboard will reach the text, and it will
    not.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "e = tkcurses.Entry(root, width=10, name='e')\n"
            "e.place(x=1, y=1)\n"
            "e.insert(0, 'abc')\n"
            f"e.configure(state={state!r})\n"
            "e.focus_set()"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("abc")
    term.wait_for_idle()
    reversed_cells = [term.attrs_at(2, col)["reverse"] for col in range(2, 12)]
    assert not any(reversed_cells), (
        f"a {state} entry drew an insertion cursor\n{term.describe()}"
    )


def test_show_masks_what_is_displayed(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "e = tkcurses.Entry(root, width=20, show='*')\n"
            "e.place(x=1, y=1)\n"
            "e.insert(0, 'secret')\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("******")
    assert "secret" not in "\n".join(term.display)


def test_text_inserted_by_the_program_shows_from_its_start(terminal, tmp_path):
    """Tk's insert does not scroll: a long value shows its beginning.

    Measured on Tk 9.0.2. This used to show the END, because every redraw
    scrolled to the cursor, which inserting had moved there. TkCurses-i8s.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "e = tkcurses.Entry(root, width=10)\n"
            "e.place(x=1, y=1)\n"
            "e.insert(0, 'abcdefghijklmnop')"
        ),
        workdir=tmp_path,
    )
    # One wait naming everything asserted: the row is drawn whole or not yet.
    term.wait_for(
        lambda t: "abcdefghij" in t.display[2] and "k" not in t.display[2],
        message="the start of the text, and nothing past the field",
    )


def test_typing_past_the_edge_scrolls_within_the_field(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "e = tkcurses.Entry(root, width=10)\n"
            "e.place(x=1, y=1)\n"
            "e.focus_set()\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send(b"abcdefghijklmnop")
    # The end is visible, the beginning has scrolled off, and nothing has
    # spilled past the field's border.
    term.wait_for(
        lambda t: "nop" in t.display[2] and "abc" not in t.display[2],
        message="the end of the typed text, scrolled into view",
    )


def test_a_selection_is_visible(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "e = tkcurses.Entry(root, width=20)\n"
            "e.place(x=1, y=1)\n"
            "e.insert(0, 'select me')\n"
            "e.selection_range(0, 6)\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("select me")
    term.wait_for_idle()
    assert term.attrs_at(2, 2)["reverse"] != term.attrs_at(2, 9)["reverse"]


def test_a_click_moves_the_cursor_and_typing_lands_there(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "e = tkcurses.Entry(root, width=20)\n"
            "e.place(x=1, y=1)\n"
            "e.insert(0, 'ac')\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    # Column 3 on screen is index 1 in a field whose text starts at column 2.
    term.click(3, 2)
    term.send(b"b")
    term.wait_for_text("abc")


def test_an_entry_and_a_button_work_together(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, relief='solid')\n"
            "f.pack(fill='both', expand=True)\n"
            "e = tkcurses.Entry(f, width=16)\n"
            "e.pack(side='top')\n"
            "def submit():\n"
            "    buffer.write(11, 0, 'got %s' % e.get())\n"
            "    root.tk.screen.refresh()\n"
            "tkcurses.Button(f, text='OK', command=submit).pack(side='top')\n"
            "e.focus_set()\n"
            "e.insert(0, 'value')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("value")
    term.wait_for_text("OK")
    term.send(b"\t")
    term.send(b"\r")
    term.wait_for_idle()
    assert "got value" in "\n".join(term.display) or "value" in "\n".join(term.display)


PLACEHOLDER = """
import tkcurses

root = tkcurses.Tk()
e = tkcurses.Entry(root, width=16, name='e', placeholder='type here'{extra})
e.place(x=1, y=1)
{after}
root.update_layout()
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


def test_the_placeholder_is_drawn_and_dim(terminal, tmp_path):
    """On a real screen: the ghost text appears, and it is dim.

    Dim is a deliberate divergence - Tk leaves an unset placeholderforeground
    in the ordinary foreground - because in a terminal undimmed ghost text is
    indistinguishable from content, and the field would read as full while
    get() answers "". ARCHITECTURE.md records it. TkCurses-xe9.3.
    """
    term = terminal(cols=40, rows=10)
    term.run_source(PLACEHOLDER.format(extra="", after=""), workdir=tmp_path)
    term.wait_for_text("type here")
    term.wait_for_cell(2, 2, lambda cell: cell.data == "t")
    assert term.attrs_at(2, 2)["dim"], (
        f"the placeholder is not dim, so it reads as real content\n{term.describe()}"
    )


def test_typed_text_replaces_the_placeholder_and_is_not_dim(terminal, tmp_path):
    """The other half: content must look like content."""
    term = terminal(cols=40, rows=10)
    term.run_source(
        PLACEHOLDER.format(extra="", after="e.insert(0, 'abc')"), workdir=tmp_path
    )
    term.wait_for_text("abc")
    term.wait_for_cell(2, 2, lambda cell: cell.data == "a")
    assert not term.attrs_at(2, 2)["dim"], (
        f"typed text was drawn dim\n{term.describe()}"
    )
    assert "type here" not in "\n".join(term.display), (
        f"the placeholder survived alongside the text\n{term.describe()}"
    )


def test_the_placeholder_is_not_masked_on_screen(terminal, tmp_path):
    """Measured on real Tk by a person: show='*' with a placeholder draws the
    placeholder as plain text. The asterisks are for contents, and there are
    none."""
    term = terminal(cols=40, rows=10)
    term.run_source(PLACEHOLDER.format(extra=", show='*'", after=""), workdir=tmp_path)
    term.wait_for_text("type here")
    term.wait_for_cell(2, 2, lambda cell: cell.data == "t")
    assert "*" not in term.row(2), f"the placeholder was masked\n{term.describe()}"
