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


# ======================================================================
# Dragging a window
# ======================================================================
#
# There is no window manager here, so moving a decorated window is the
# library's own job rather than something it is merely told about. See
# ARCHITECTURE.md, "Window Management".

DRAGGABLE = """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer

win = tkcurses.Toplevel(root, width=24, height=6)
win.title("Drag me")
win.geometry("24x6+10+3")

bare = tkcurses.Toplevel(root, width=10, height=3)
bare.overrideredirect(True)
bare.geometry("10x3+40+10")

behind = tkcurses.Toplevel(root, width=12, height=4)
behind.title("Behind")
behind.geometry("12x4+12+4")


def report():
    buffer.write(
        0,
        0,
        ("win=+%d+%d bare=+%d+%d top=%s" % (
            win.winfo_x(),
            win.winfo_y(),
            bare.winfo_x(),
            bare.winfo_y(),
            root.winfo_children()[-1].title() or "-",
        )).ljust(44),
    )
    root.tk.screen.refresh()
    root.after(40, report)


root.update_layout()
report()
root.after(6000, root.quit)
root.mainloop()
"""


def drag(term, from_x, from_y, to_x, to_y, settle=0.06):
    """Press, move, release - the three reports a real drag sends.

    Each is drained separately for the reason ``click`` documents: ncurses
    drops mouse reports that arrive faster than the application takes them.
    """
    term.send_mouse(from_x, from_y, action="press")
    term._drain(settle)
    term.send_mouse(to_x, to_y, action="move")
    term._drain(settle)
    term.send_mouse(to_x, to_y, action="release")
    term._drain(settle)
    term.wait_for_idle()


@pytest.fixture
def windows(terminal, tmp_path):
    term = terminal(cols=70, rows=20)
    term.run_source(DRAGGABLE, workdir=tmp_path)
    term.wait_for_text("win=+10+3")
    term.wait_for_idle()
    return term


def test_dragging_the_title_row_moves_the_window(windows):
    """By the distance travelled, so the grabbed column stays under the
    pointer - not to the position arrived at."""
    drag(windows, 14, 3, 20, 8)
    windows.wait_for_text("win=+16+8")


def test_dragging_the_body_does_not_move_the_window(windows):
    """The title row is the handle. A press anywhere else belongs to
    whatever widget is there."""
    drag(windows, 20, 6, 30, 12)
    windows.wait_for_idle()
    assert "win=+10+3" in windows.display[0], windows.describe()


def test_an_overrideredirect_window_is_left_to_the_application(windows):
    """No decoration, so nothing to grab - exactly as on a desktop, where
    such a window is the program's own to move."""
    drag(windows, 42, 10, 50, 14)
    windows.wait_for_idle()
    assert "bare=+40+10" in windows.display[0], windows.describe()


def test_a_window_dragged_past_the_edge_stops_at_it(windows):
    """geometry() clamps, and dragging goes through geometry()."""
    drag(windows, 14, 3, 69, 19)
    # 70x20 terminal, 24x6 window: the last position that fits.
    windows.wait_for_text("win=+46+14")


def test_pressing_the_title_raises_the_window(windows):
    """Clicking a window to move it and having it stay behind another would
    be surprising, and there is no window manager here to do the raising."""
    assert "top=Behind" in windows.display[0], windows.describe()
    drag(windows, 14, 3, 14, 3)
    windows.wait_for_text("top=Drag me")


CARRIES = """
import tkcurses

root = tkcurses.Tk()
win = tkcurses.Toplevel(root, width=24, height=6)
win.title("title")
win.geometry("24x6+4+2")
tkcurses.Label(win, text="BODYTEXT", anchor="w").place(x=2, y=1)
# A second child, in the far corner: one label could travel by luck, and
# the corner is where a child is most likely to be clipped or left behind.
tkcurses.Label(win, text="◢", name="g").place(relx=1.0, x=-1, rely=1.0, y=-1)
root.update_layout()
root.tk.screen.refresh()
root.after(6000, root.quit)
root.mainloop()
"""


def test_a_dragged_window_carries_its_contents(terminal, tmp_path):
    """Regression, TkCurses-bk8.

    A child draws on its own panel above its container's, so raising only
    the container's panel put the window's blank interior in front of
    everything in it: the window arrived at the new position with a border,
    a title, and nothing else. Both the label and the grip have to make the
    journey.
    """
    term = terminal(cols=50, rows=16)
    term.run_source(CARRIES, workdir=tmp_path)
    term.wait_for_text("BODYTEXT")
    term.wait_for_idle()
    assert "BODYTEXT" in term.display[4]

    drag(term, 8, 2, 20, 7)
    term.wait_for_idle()
    # +12+5 from +4+2, so the label that was on row 4 is now on row 9.
    assert "BODYTEXT" in term.display[9], term.describe()
    assert "◢" in term.display[11], term.describe()
    # And nothing of it was left at the old position.
    assert not any("BODYTEXT" in row for row in term.display[:9]), term.describe()
