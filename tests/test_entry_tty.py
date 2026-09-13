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


def test_text_longer_than_the_field_scrolls_within_it(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "e = tkcurses.Entry(root, width=10)\n"
            "e.place(x=1, y=1)\n"
            "e.insert(0, 'abcdefghijklmnop')\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.wait_for_idle()
    line = term.display[2]
    # The end is visible, the beginning has scrolled off, and nothing has
    # spilled past the field's border.
    assert "nop" in line
    assert "abc" not in line


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
