"""What a Frame actually puts on the terminal."""

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


def test_a_frame_with_a_relief_draws_a_box(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, relief='solid', width=20, height=5)\n"
            "f.place(x=2, y=2)"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "┌" in "\n".join(t.display), message="a bordered frame")
    assert term.display[2][2] == "┌"
    assert term.display[2][2 + 19] == "┐"
    assert term.display[2 + 4][2] == "└"
    assert term.display[2 + 4][2 + 19] == "┘"


def test_an_unbordered_frame_draws_no_box(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, width=20, height=5)\n"
            "f.place(x=2, y=2)\n"
            'buffer.write(11, 0, "no border")'
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("no border")
    term.wait_for_idle()
    assert not any("┌" in line for line in term.display)


def test_a_flat_border_reserves_cells_without_drawing_anything(terminal, tmp_path):
    """tkinter draws a flat border in the background colour: invisible.

    borderwidth alone therefore costs a widget its outermost cells and shows
    nothing for them, which is surprising until you know it is Tk's rule too.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, borderwidth=1, width=20, height=5)\n"
            "f.place(x=2, y=2)\n"
            'buffer.write(11, 0, "flat border")'
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("flat border")
    term.wait_for_idle()
    assert not any("┌" in line for line in term.display)


def test_a_raised_frame_draws_a_different_line_style(terminal, tmp_path):
    """A relief is a choice of line style, which is all a terminal can offer."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "a = tkcurses.Frame(root, relief='ridge', width=16, height=4)\n"
            "a.place(x=1, y=1)\n"
            "b = tkcurses.Frame(root, relief='solid', width=16, height=4)\n"
            "b.place(x=20, y=1)"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: t.display[1].strip() != "", message="both frames")
    term.wait_for_idle()
    # ridge is drawn in double lines, solid in single ones.
    assert term.display[1][1] == "╔"
    assert term.display[1][20] == "┌"


def test_a_frame_is_redrawn_after_it_is_resized(terminal, tmp_path):
    """A resize builds a new curses window; the old one's contents are gone."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, relief='solid', width=10, height=3)\n"
            "f.place(x=0, y=0)\n"
            "def grow():\n"
            "    f.configure(width=30, height=8)\n"
            "    root.update_layout()\n"
            '    buffer.write(11, 0, "grown")\n'
            "    root.tk.screen.refresh()\n"
            "root.after(100, grow)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("grown")
    term.wait_for_idle()
    assert term.display[0][29] == "┐", "the wider frame must have repainted"
    assert term.display[7][0] == "└"


def test_a_nested_frame_draws_inside_its_parent(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "outer = tkcurses.Frame(root, relief='solid', width=24, height=8)\n"
            "outer.place(x=1, y=1)\n"
            # Without this the children decide the frame's size and it
            # shrinks to fit them, as in Tk.
            "outer.pack_propagate(False)\n"
            "inner = tkcurses.Frame(outer, relief='solid')\n"
            "inner.pack(fill='both', expand=True, padx=1, pady=1)"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "┌" in "\n".join(t.display), message="the frames")
    term.wait_for_idle()
    # The outer frame's corner, then the inner one's, one cell in from the
    # outer frame's own border plus its padding.
    assert term.display[1][1] == "┌"
    assert term.display[3][3] == "┌"


def test_packed_frames_tile_the_screen(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "for name in 'abc':\n"
            "    f = tkcurses.Frame(root, relief='solid', name=name)\n"
            "    f._requested = tkcurses._core.geometry.Size(10, 4)\n"
            "    f.pack(side='left', fill='both', expand=True)"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: t.display[0].count("┌") == 3, message="three frames")
    corners = [i for i, char in enumerate(term.display[0]) if char == "┌"]
    assert corners[0] == 0
    # Evenly divided: each frame gets a third of forty columns.
    assert corners[1] - corners[0] in (13, 14)
