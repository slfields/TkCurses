"""Tests for the window manager methods that change what is on the terminal."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
{body}
root.after(4000, root.quit)
root.mainloop()
"""


def test_a_title_appears_on_the_top_border(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            'win = tkcurses.Toplevel(root, width=24, height=6)\nwin.title("Settings")'
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("Settings")
    row = next(i for i, line in enumerate(term.display) if "Settings" in line)
    # The title sits in the border row, between the corners.
    assert "┌" in term.display[row]
    assert "┐" in term.display[row]


def test_a_long_title_is_cut_rather_than_running_over_the_corner(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "win = tkcurses.Toplevel(root, width=14, height=5)\n"
            'win.title("a title far too long for this window")'
        ),
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: any("┌" in line for line in t.display), message="the window"
    )
    term.wait_for_idle()
    row = next(i for i, line in enumerate(term.display) if "┌" in line)
    left = term.display[row].index("┌")
    assert term.display[row][left + 13] == "┐"


def test_geometry_moves_a_window_on_screen(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "win = tkcurses.Toplevel(root, width=12, height=4)\n"
            'win.geometry("12x4+0+0")'
        ),
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: any("┌" in line for line in t.display), message="the window"
    )
    term.wait_for_idle()
    assert term.display[0].startswith("┌")


def test_withdraw_takes_a_window_off_the_screen(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "win = tkcurses.Toplevel(root, width=20, height=6)\n"
            "def hide():\n"
            "    win.withdraw()\n"
            '    buffer.write(0, 0, "hidden")\n'
            "    root.tk.screen.refresh()\n"
            "root.after(150, hide)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("hidden")
    term.wait_for_idle()
    assert not any("┌" in line for line in term.display)


def test_deiconify_brings_it_back(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "win = tkcurses.Toplevel(root, width=20, height=6)\n"
            'win.title("back")\n'
            "root.after(100, win.withdraw)\n"
            "root.after(250, win.deiconify)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("back")


def test_overrideredirect_removes_the_border(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "win = tkcurses.Toplevel(root, width=20, height=6)\n"
            "def strip():\n"
            "    win.overrideredirect(True)\n"
            '    buffer.write(0, 0, "stripped")\n'
            "    root.tk.screen.refresh()\n"
            "root.after(150, strip)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("stripped")
    term.wait_for_idle()
    assert not any("┌" in line for line in term.display)


def test_fullscreen_fills_the_terminal(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "win = tkcurses.Toplevel(root, width=10, height=4)\n"
            'win.attributes("-fullscreen", True)'
        ),
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: any("┌" in line for line in t.display), message="the window"
    )
    term.wait_for_idle()
    assert term.display[0].startswith("┌")
    assert term.display[0].rstrip().endswith("┐")


def test_the_roots_geometry_is_the_terminals(terminal, tmp_path):
    """Setting it is accepted and ignored: nothing here can resize a terminal."""
    term = terminal(cols=44, rows=13)
    term.run_source(
        program(
            'root.geometry("10x3+5+5")\n'
            'buffer.write(0, 0, "root is %s" % root.geometry())\n'
            "root.tk.screen.refresh()"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("root is 44x13+0+0")
