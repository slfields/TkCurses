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

"""The configuration settings that change what the terminal is sent.

Each is measured through the terminal rather than read back off the
configuration: twelve settings were once read, validated and tested while
nothing used them, and a test of the parsing alone passed for every one.
"""

from __future__ import annotations

import re
from dataclasses import astuple

import pytest

from tkcurses._core.attributes import ASCII_GLYPHS

pytestmark = pytest.mark.tty

DEPTH = """
import tkcurses as tk
root = tk.Tk()
tk.Label(root, text=f"depth={root.winfo_colordepth()};",
         fg="#d75f00", bg="#5f87af").pack()
root.mainloop()
"""

BOXES = """
import tkcurses as tk
from tkcurses import ttk
root = tk.Tk()
tk.Entry(root, relief="ridge").pack()
ttk.LabelFrame(root, text="lf", width=12, height=3).pack()
tk.Scale(root, orient="horizontal", length=12).pack()
tk.Label(root, text="drawn").pack()
root.mainloop()
"""

PICTURE = """
import tkcurses as tk
root = tk.Tk()
image = tk.PhotoImage(width=4, height=4)
image.put("#123456", to=(0, 0, 4, 4))
tk.Label(root, image=image).pack()
tk.Label(root, text="drawn").pack()
root.mainloop()
"""

QUIT_SOON = """
import tkcurses as tk
root = tk.Tk()
tk.Label(root, text="drawn").pack()
root.after(300, root.destroy)
root.mainloop()
"""

#: Every way of asking the terminal to report the mouse: ncurses' own
#: 1000 and 1006, and the 1002 and 1003 motion modes asked for past it.
MOUSE_MODES = re.compile(rb"\x1b\[\?[0-9;]*100[0236][;0-9]*h")


def depth_with(terminal, tmp_path, term_name, mode):
    env = {"TERM": term_name}
    if mode is not None:
        env["TKCURSES_DISPLAY_COLOR_MODE"] = mode
    term = terminal(cols=30, rows=4, env=env)
    term.run_source(DEPTH, workdir=tmp_path)
    term.wait_for_text("depth=")
    return term


@pytest.mark.parametrize(
    ("mode", "depth"),
    [(None, 256), ("auto", 256), ("8", 8), ("16", 16), ("256", 256)],
)
def test_the_colour_mode_lowers_the_depth(terminal, tmp_path, mode, depth):
    term = depth_with(terminal, tmp_path, "xterm-256color", mode)
    term.wait_for_text(f"depth={depth};")


def test_the_colour_mode_never_raises_the_depth(terminal, tmp_path):
    """curses refuses a colour number past the COLORS it started with, so a
    number above what the terminal reports is a ceiling that changes
    nothing."""
    term = depth_with(terminal, tmp_path, "xterm", "256")
    term.wait_for_text("depth=8;")


@pytest.mark.parametrize(("mode", "sent"), [(None, True), ("8", False), ("16", False)])
def test_below_256_no_palette_colour_is_sent(terminal, tmp_path, mode, sent):
    term = depth_with(terminal, tmp_path, "xterm-256color", mode)
    term.send(b"\x03")
    term.wait_for_exit()
    assert (re.search(rb"\x1b\[[34]8;5;", term.received) is not None) is sent


@pytest.mark.parametrize(("mode", "direct"), [(None, False), ("truecolor", True)])
def test_truecolor_sends_pictures_in_24_bit(terminal, tmp_path, mode, direct):
    """What COLORTERM=truecolor does, for a terminal that does not say so."""
    env = {"TERM": "xterm-256color"}
    if mode is not None:
        env["TKCURSES_DISPLAY_COLOR_MODE"] = mode
    term = terminal(cols=30, rows=6, env=env)
    term.run_source(PICTURE, workdir=tmp_path)
    term.wait_for_text("drawn")
    term.send(b"\x03")
    term.wait_for_exit()
    assert (b"8;2;18;52;86m" in term.received) is direct


@pytest.mark.parametrize(("mode", "direct"), [(None, True), ("8", False)])
def test_a_lower_colour_mode_outranks_colorterm(terminal, tmp_path, mode, direct):
    """COLORTERM=truecolor sends pictures in 24-bit only when nothing asked
    for fewer colours."""
    env = {"TERM": "xterm-256color", "COLORTERM": "truecolor"}
    if mode is not None:
        env["TKCURSES_DISPLAY_COLOR_MODE"] = mode
    term = terminal(cols=30, rows=6, env=env)
    term.run_source(PICTURE, workdir=tmp_path)
    term.wait_for_text("drawn")
    term.send(b"\x03")
    term.wait_for_exit()
    assert (b"8;2;18;52;86m" in term.received) is direct


def drawn(term):
    return "\n".join(term.display)


def test_unicode_borders_off_draws_boxes_in_ascii(terminal, tmp_path):
    term = terminal(cols=30, rows=12, env={"TKCURSES_DISPLAY_UNICODE": "0"})
    term.run_source(BOXES, workdir=tmp_path)
    term.wait_for(lambda t: "+ lf ---" in drawn(t) and "drawn" in drawn(t))
    term.wait_for_idle()
    screen = drawn(term)
    assert screen.isascii(), sorted({c for c in screen if not c.isascii()})
    assert "+--------------------+" in screen  # the Entry's ridge
    assert "#..........." in screen  # the Scale's trough and slider


def test_unicode_borders_on_is_the_default(terminal, tmp_path):
    term = terminal(cols=30, rows=12)
    term.run_source(BOXES, workdir=tmp_path)
    term.wait_for(lambda t: "┌ lf ───" in drawn(t) and "╔═══" in drawn(t))


CURSES_BOX = """
import tkcurses as tk
from tkcurses import curses
root = tk.Tk()
tk.Label(root, text="drawn").pack()
def box():
    curses.initscr()
    window = curses.newwin(3, 10, 3, 2)
    window.border()
    window.addstr(1, 1, "boxed")
    window.refresh()
root.after(100, box)
root.mainloop()
"""


def test_unicode_borders_off_reaches_a_curses_window(terminal, tmp_path):
    """A curses window in a running application paints through the
    application's screen, not through a widget."""
    term = terminal(cols=30, rows=8, env={"TKCURSES_DISPLAY_UNICODE": "0"})
    term.run_source(CURSES_BOX, workdir=tmp_path)
    box = ["+--------+", "|boxed   |", "+--------+"]
    term.wait_for(lambda t: [line[2:12] for line in t.display[3:6]] == box)


@pytest.mark.parametrize(("enabled", "asked"), [(None, True), ("0", False)])
def test_mouse_off_never_asks_for_the_mouse(terminal, tmp_path, enabled, asked):
    """Turned off, the terminal keeps the mouse, and its own selection works
    without Shift."""
    env = {} if enabled is None else {"TKCURSES_MOUSE_ENABLED": enabled}
    term = terminal(cols=30, rows=4, env=env)
    term.run_source(QUIT_SOON, workdir=tmp_path)
    assert term.wait_for_exit() == 0
    assert (MOUSE_MODES.search(term.received) is not None) is asked


def test_configuration_warnings_are_printed_on_the_way_out(terminal, tmp_path):
    """Nowhere to say them while the screen is up, so they wait for it to go."""
    env = {"TKCURSES_DEBUG": "1", "TKCURSES_MOUSE_CLICK_INTERVAL": "soon"}
    term = terminal(cols=30, rows=4, env=env)
    term.run_source(QUIT_SOON, workdir=tmp_path)
    assert term.wait_for_exit() == 0
    assert term.stderr.splitlines() == [
        "tkcurses: [mouse] click_interval in $TKCURSES_MOUSE_CLICK_INTERVAL:"
        " 'soon' is not a number, using 200",
        "tkcurses: $TKCURSES_DEBUG no longer has any effect",
    ]


def test_a_clean_configuration_prints_nothing(terminal, tmp_path):
    term = terminal(cols=30, rows=4)
    term.run_source(QUIT_SOON, workdir=tmp_path)
    assert term.wait_for_exit() == 0
    assert term.stderr == ""


# ------------------------------------------------------- the ASCII table


@pytest.mark.parametrize("code", sorted(ASCII_GLYPHS))
def test_every_stand_in_is_one_ascii_character(code):
    """One for one, so nothing a widget measured moves."""
    stand_in = ASCII_GLYPHS[code]
    assert len(stand_in) == 1
    assert stand_in.isascii() and stand_in.isprintable()


@pytest.mark.parametrize(
    ("drawn", "ascii"),
    [
        ("┌─┬─┐", "+-+-+"),
        ("│ ┃ ║", "| | |"),
        ("╒═╤╕", "+-++"),
        ("╭╮╰╯", "++++"),
        ("╔╦╬╝", "++++"),
        ("╴╶╵╷", "--||"),
        ("┄┅┆┇", "--||"),
        ("\u2571\u2572\u2573", "/\\X"),  # the diagonals
    ],
)
def test_box_pieces_go_by_the_way_they_reach(drawn, ascii):
    assert drawn.translate(ASCII_GLYPHS) == ascii


def test_every_character_a_theme_or_relief_draws_has_a_stand_in():
    from tkcurses import ttk
    from tkcurses._core import attributes

    used = {c for glyphs in ttk.THEMES.values() for c in astuple(glyphs)}
    for relief in ("raised", "sunken", "solid", "ridge", "groove"):
        style = attributes.style_for_relief(relief)
        used |= {c for c in astuple(style) if isinstance(c, str)}
    assert "".join(sorted(used)).translate(ASCII_GLYPHS).isascii()
