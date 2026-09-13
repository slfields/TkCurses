"""What a Button looks like and how it answers a real terminal."""

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


def test_a_button_shows_its_text_in_a_box(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("tkcurses.Button(root, text='OK').place(x=2, y=2)"),
        workdir=tmp_path,
    )
    term.wait_for_text("OK")
    row = next(i for i, line in enumerate(term.display) if "OK" in line)
    assert "┌" in term.display[row - 1]
    assert "└" in term.display[row + 1]


def test_focus_is_visible(terminal, tmp_path):
    """A button nobody can see the focus on cannot be used from the keyboard."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "b = tkcurses.Button(root, text='OK')\n"
            "b.place(x=2, y=2)\n"
            "root.after(100, b.focus_set)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("OK")
    term.wait_for(lambda t: "▶" in "\n".join(t.display), message="the focus marker")
    assert "◀" in "\n".join(term.display)


def test_an_unfocused_button_shows_no_markers(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tkcurses.Button(root, text='OK').place(x=2, y=2)\n"
            "buffer.write(11, 0, 'drawn')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("drawn")
    term.wait_for_idle()
    assert "▶" not in "\n".join(term.display)


def test_a_button_does_not_change_width_when_focused(terminal, tmp_path):
    """Room for the markers is reserved whether or not they are showing."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "b = tkcurses.Button(root, text='OK')\n"
            "b.place(x=2, y=2)\n"
            "def report(row):\n"
            "    root.update_layout()\n"
            "    buffer.write(row, 0, 'w%s=%s' % (row, b.winfo_width()))\n"
            "    root.tk.screen.refresh()\n"
            "report(9)\n"
            "root.after(100, lambda: (b.focus_set(), report(10)))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("w9=8")
    term.wait_for_text("w10=8")


def test_a_click_invokes_the_button(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "def pressed():\n"
            "    buffer.write(11, 0, 'invoked')\n"
            "    root.tk.screen.refresh()\n"
            "b = tkcurses.Button(root, text='Press', command=pressed)\n"
            "b.place(x=2, y=2)\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.click(5, 3)
    term.wait_for_text("invoked")


def test_return_invokes_the_focused_button(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "def pressed():\n"
            "    buffer.write(11, 0, 'invoked by key')\n"
            "    root.tk.screen.refresh()\n"
            "b = tkcurses.Button(root, text='Press', command=pressed)\n"
            "b.place(x=2, y=2)\n"
            "b.focus_set()\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send(b"\r")
    term.wait_for_text("invoked by key")


def test_a_disabled_button_does_not_answer_a_click(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "def pressed():\n"
            "    buffer.write(11, 0, 'should not happen')\n"
            "    root.tk.screen.refresh()\n"
            "b = tkcurses.Button(root, text='No', command=pressed, state='disabled')\n"
            "b.place(x=2, y=2)\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.click(4, 3)
    term.wait_for_idle()
    assert "should not happen" not in "\n".join(term.display)


def test_buttons_pack_into_a_frame(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, relief='solid')\n"
            "f.pack(fill='both', expand=True)\n"
            "for word in ('Yes', 'No'):\n"
            "    tkcurses.Button(f, text=word).pack(side='left', padx=1)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("Yes")
    term.wait_for_text("No")
