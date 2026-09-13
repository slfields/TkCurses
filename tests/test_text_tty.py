"""What a Text looks like and how it answers a real terminal."""

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


PARAGRAPH = "the quick brown fox jumps over the lazy dog"


def test_a_text_shows_its_contents(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "t = tkcurses.Text(root, width=20, height=5)\n"
            "t.place(x=2, y=2)\n"
            "t.insert('1.0', 'hello\\nworld')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("hello")
    term.wait_for_text("world")


def test_the_cursor_shows_only_when_focused(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "t = tkcurses.Text(root, width=20, height=5)\n"
            "t.place(x=2, y=2)\n"
            "t.insert('1.0', 'abc')\n"
            "t.mark_set('insert', '1.1')\n"
            "buffer.write(11, 0, 'drawn')\n"
            "root.after(200, t.focus_set)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("abc")
    row = next(i for i, line in enumerate(term.display) if "abc" in line)
    column = term.display[row].index("abc") + 1
    term.wait_for(
        lambda t: t.attrs_at(row, column)["reverse"], message="the insert cursor"
    )


def test_typing_reaches_the_widget(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "t = tkcurses.Text(root, width=20, height=5)\n"
            "t.place(x=2, y=2)\n"
            "t.focus_set()"
        ),
        workdir=tmp_path,
    )
    term.wait_for_idle()
    term.send(b"hello")
    term.wait_for_text("hello")
    term.send_keys("<Return>")
    term.send(b"world")
    term.wait_for_text("world")


def test_backspace_joins_two_lines(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "t = tkcurses.Text(root, width=20, height=5)\n"
            "t.place(x=2, y=2)\n"
            "t.insert('1.0', 'ab\\ncd')\n"
            "t.mark_set('insert', '2.0')\n"
            "t.focus_set()"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("cd")
    term.send_keys("<BackSpace>")
    term.wait_for_text("abcd")


def test_the_view_follows_the_cursor_downwards(terminal, tmp_path):
    """Editing past the bottom of the window has to bring the window along."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "t = tkcurses.Text(root, width=20, height=4)\n"
            "t.place(x=2, y=2)\n"
            "t.insert('1.0', '\\n'.join('line %d' % n for n in range(20)))\n"
            "t.mark_set('insert', '1.0')\n"
            "t.see('1.0')\n"
            "t.focus_set()\n"
            "root.after(300, lambda: (t.mark_set('insert', 'end'), t.see('insert')))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("line 0")
    term.wait_for_text("line 19")
    term.wait_for_idle()
    assert "line 0\n" not in "\n".join(term.display)


def test_the_view_follows_the_cursor_sideways(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "t = tkcurses.Text(root, width=16, height=4, wrap='none')\n"
            "t.place(x=2, y=2)\n"
            "t.insert('1.0', 'START' + '.' * 40 + 'FINISH')\n"
            "t.focus_set()"
        ),
        workdir=tmp_path,
    )
    # Inserting leaves the cursor at the end, so the view is already there.
    term.wait_for_text("FINISH")
    term.wait_for_idle()
    assert "START" not in "\n".join(term.display)


def test_wrapping_can_be_changed_with_text_already_in_the_buffer(terminal, tmp_path):
    term = terminal(cols=40, rows=14)
    term.run_source(
        program(
            f"t = tkcurses.Text(root, width=16, height=8, wrap='none')\n"
            f"t.place(x=2, y=2)\n"
            f"t.insert('1.0', {PARAGRAPH!r})\n"
            f"t.mark_set('insert', '1.0')\n"
            f"t.see('1.0')\n"
            f"root.after(200, lambda: t.configure(wrap='word'))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("the quick brown")
    # Wrapped: the later words appear on their own rows rather than off-screen.
    term.wait_for_text("lazy dog")


def test_no_wrapped_row_overflows_the_widget(terminal, tmp_path):
    """A row one cell too wide draws over the border."""
    term = terminal(cols=40, rows=14)
    term.run_source(
        program(
            f"f = tkcurses.Frame(root, relief='solid')\n"
            f"f.place(x=1, y=1, width=22, height=10)\n"
            f"t = tkcurses.Text(f, width=16, height=6, wrap='word', relief='flat')\n"
            f"t.place(x=1, y=1)\n"
            f"t.insert('1.0', {PARAGRAPH!r})\n"
            f"t.mark_set('insert', '1.0')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("the quick")
    term.wait_for_idle()
    # The frame's right-hand border must be unbroken all the way down.
    for row in range(2, 10):
        assert term.display[row][22] == "│", term.describe()


def test_a_tag_changes_how_its_range_looks(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "t = tkcurses.Text(root, width=20, height=4)\n"
            "t.place(x=2, y=2)\n"
            "t.insert('1.0', 'plain bold plain')\n"
            "t.tag_configure('b', font='bold')\n"
            "t.tag_add('b', '1.6', '1.10')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("plain bold plain")
    row = next(i for i, line in enumerate(term.display) if "plain bold" in line)
    start = term.display[row].index("bold")
    assert term.attrs_at(row, start)["bold"]
    assert not term.attrs_at(row, start - 2)["bold"]


def test_a_selection_is_visible_without_being_configured(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "t = tkcurses.Text(root, width=20, height=4)\n"
            "t.place(x=2, y=2)\n"
            "t.insert('1.0', 'hello world')\n"
            "t.tag_add('sel', '1.0', '1.5')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("hello world")
    row = next(i for i, line in enumerate(term.display) if "hello" in line)
    column = term.display[row].index("hello")
    term.wait_for(lambda t: t.attrs_at(row, column)["reverse"], message="the selection")
    assert not term.attrs_at(row, column + 6)["reverse"]


def test_a_drag_selects_on_screen(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "t = tkcurses.Text(root, width=20, height=4)\n"
            "t.place(x=2, y=2)\n"
            "t.insert('1.0', 'hello world')\n"
            "t.mark_set('insert', '1.0')\n"
            "def report(event=None):\n"
            "    try:\n"
            "        got = t.get('sel.first', 'sel.last')\n"
            "    except Exception:\n"
            "        got = ''\n"
            "    buffer.write(11, 0, 'sel=%-14s' % got)\n"
            "    root.tk.screen.refresh()\n"
            "t.bind('<ButtonRelease-1>', report)\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.wait_for_text("hello world")
    row = next(i for i, line in enumerate(term.display) if "hello" in line)
    column = term.display[row].index("hello")
    term.send_mouse(column, row, action="press")
    term._drain(0.08)
    term.send_mouse(column + 5, row, action="move", button=1)
    term._drain(0.08)
    term.send_mouse(column + 5, row, action="release")
    term.wait_for_text("sel=hello")


def test_a_scrollbar_tracks_the_view(terminal, tmp_path):
    term = terminal(cols=40, rows=14)
    term.run_source(
        program(
            "row = tkcurses.Frame(root)\n"
            "row.pack(fill='both', expand=True)\n"
            "t = tkcurses.Text(row, width=20, height=6)\n"
            "t.pack(side='left', fill='y')\n"
            "bar = tkcurses.Scrollbar(row, command=t.yview)\n"
            "bar.pack(side='left', fill='y')\n"
            "t.configure(yscrollcommand=bar.set)\n"
            "t.insert('1.0', '\\n'.join('line %d' % n for n in range(40)))\n"
            "t.mark_set('insert', '1.0')\n"
            "t.see('1.0')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("line 0")
    term.wait_for_idle()
    before = "\n".join(term.display)
    assert "█" in before  # the thumb
    bar_column = next(i for i, cell in enumerate(term.display[3]) if cell in "█░")
    # In the trough below the thumb, which pages down by a screenful. The
    # size of that page depends on the widget, so what is checked is that
    # the view moved and the top line went with it.
    term.click(bar_column, 8)
    term.wait_for(
        lambda t: (
            "line 0 " not in "\n".join(t.display)
            and any("line 1" in line for line in t.display)
        ),
        message="the view to page down",
    )


def test_a_disabled_text_refuses_the_keyboard(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "t = tkcurses.Text(root, width=20, height=4, state='disabled')\n"
            "t.place(x=2, y=2)\n"
            "t.insert('1.0', 'fixed')\n"
            "t.focus_set()"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("fixed")
    term.send(b"zzz")
    term.wait_for_idle()
    assert "zzz" not in "\n".join(term.display)


def test_a_text_survives_the_terminal_shrinking(terminal, tmp_path):
    term = terminal(cols=40, rows=14)
    term.run_source(
        program(
            f"t = tkcurses.Text(root, width=16, height=6, wrap='word')\n"
            f"t.pack(fill='both', expand=True)\n"
            f"t.insert('1.0', {PARAGRAPH!r})\n"
            f"t.mark_set('insert', '1.0')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("the quick")
    term.resize(cols=24, rows=10)
    term.wait_for_text("the quick")
    assert "Traceback" not in term.stderr


def test_texts_pack_and_nest(terminal, tmp_path):
    term = terminal(cols=40, rows=14)
    term.run_source(
        program(
            "f = tkcurses.LabelFrame(root, text='Notes')\n"
            "f.pack(fill='both', expand=True, padx=1, pady=1)\n"
            "t = tkcurses.Text(f, width=10, height=3, wrap='word')\n"
            "t.pack(fill='both', expand=True)\n"
            "t.insert('1.0', 'packed inside a labelframe')\n"
            "t.mark_set('insert', '1.0')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("Notes")
    term.wait_for_text("packed")
