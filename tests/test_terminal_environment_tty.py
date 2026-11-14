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

"""What a program is told when the terminal it runs in cannot do the job.

Each condition here used to fail silently or degrade quietly: the program
started, ran, and showed nothing or showed it wrong, with nothing saying
why. Every test sets the environment of a real child process and reads what
reached the screen, stderr and the exit status.
"""

from __future__ import annotations

import base64

import pytest

pytestmark = pytest.mark.tty

SHOW_AND_QUIT = """
import tkcurses as tk
root = tk.Tk()
tk.Label(root, text="drawn").pack()
root.after(300, root.destroy)
root.mainloop()
"""

CATCH_DUMB = """
import sys, termios
import tkcurses as tk
try:
    tk.Tk()
except tk.TclError as error:
    echo = bool(termios.tcgetattr(0)[3] & termios.ECHO)
    print(f"caught: {error} echo={echo}", flush=True)
"""


def test_a_terminal_that_cannot_address_the_cursor_is_refused(terminal, tmp_path):
    """TERM=dumb has no cursor addressing, so nothing could ever be drawn.
    It used to start, run its main loop and show nothing, then exit 0."""
    term = terminal(cols=60, rows=6, env={"TERM": "dumb"})
    term.run_source(SHOW_AND_QUIT, workdir=tmp_path)
    assert term.wait_for_exit() == 1
    assert "TclError" in term.stderr
    assert "cannot position the cursor (TERM=dumb)" in term.stderr


def test_the_refusal_is_a_tclerror_and_gives_the_terminal_back(terminal, tmp_path):
    """As Tk's 'couldn't connect to display' is: a program can catch it,
    and the terminal is in the mode it was in before Tk() was called."""
    term = terminal(cols=100, rows=6, env={"TERM": "dumb"})
    term.run_source(CATCH_DUMB, workdir=tmp_path)
    assert term.wait_for_exit() == 0
    term.wait_for_text("echo=True")
    assert "caught: this terminal cannot position the cursor" in "\n".join(term.display)


def test_a_terminal_that_can_address_the_cursor_starts(terminal, tmp_path):
    term = terminal(cols=30, rows=4, env={"TERM": "vt100"})
    term.run_source(SHOW_AND_QUIT, workdir=tmp_path)
    term.wait_for_text("drawn")
    assert term.wait_for_exit() == 0
    assert term.stderr == ""


# ------------------------------------------------------------- the locale

ACCENTED = """
import tkcurses as tk
root = tk.Tk()
tk.Label(root, text="caf\\u00e9").pack()
tk.Label(root, text="drawn").pack()
root.after(300, root.destroy)
root.mainloop()
"""


@pytest.mark.parametrize(
    ("env", "named", "advice"),
    [
        ({"LANG": "C", "LC_ALL": "C"}, "LC_ALL=C", "Set LC_ALL=C.UTF-8"),
        # PYTHONCOERCECLOCALE=0, because Python otherwise turns a C
        # LC_CTYPE into C.UTF-8 itself - see the next test.
        (
            {"LC_ALL": "", "LC_CTYPE": "C", "PYTHONCOERCECLOCALE": "0"},
            "LC_CTYPE=C",
            "Set LC_CTYPE=C.UTF-8",
        ),
    ],
)
def test_a_locale_that_is_not_utf8_is_said_on_the_way_out(
    terminal, tmp_path, env, named, advice
):
    """Under LC_ALL=C an accented letter and a box line come out wrong, and
    nothing used to say why. The setting named is the one that decided."""
    term = terminal(cols=30, rows=4, env=env)
    term.run_source(ACCENTED, workdir=tmp_path)
    term.wait_for_text("drawn")
    assert term.wait_for_exit() == 0
    assert term.stderr.splitlines() == [
        f"tkcurses: the locale is not UTF-8 ({named}), so letters outside "
        f"ASCII and the lines of boxes were drawn wrong. {advice}, or another "
        "UTF-8 locale."
    ]


@pytest.mark.parametrize(
    "env", [{}, {"LANG": "C", "LC_ALL": "", "LC_CTYPE": ""}], ids=["utf8", "LANG=C"]
)
def test_a_utf8_locale_says_nothing(terminal, tmp_path, env):
    """LANG=C alone is a UTF-8 locale by the time curses starts: Python
    coerces a C LC_CTYPE to C.UTF-8 (PEP 538) unless LC_ALL overrides it."""
    term = terminal(cols=30, rows=4, env=env)
    term.run_source(ACCENTED, workdir=tmp_path)
    term.wait_for_text("café")
    assert term.wait_for_exit() == 0
    assert term.stderr == ""


def test_the_report_names_lang_when_nothing_is_set():
    from tkcurses import _not_utf8_report

    report = _not_utf8_report({})
    assert "(no LANG set)" in report
    assert "Set LANG=C.UTF-8" in report


# ------------------------------------------------- pictures and colour pairs

#: A photograph's worth of colour: 60x40 random pixels want 1179 colour
#: pairs at 256 colours, against 255. Under it, Labels in colours of their
#: own - exact entries of the 256-colour palette, so the terminal shows
#: them exactly as asked.
BUSY_PICTURE = """
import random
import tkcurses as tk
root = tk.Tk()
rng = random.Random(7)
image = tk.PhotoImage(width=60, height=40)
for y in range(40):
    row = " ".join(
        "#%02x%02x%02x" % (rng.randrange(256), rng.randrange(256), rng.randrange(256))
        for _ in range(60)
    )
    image.put("{" + row + "}", to=(0, y))
tk.Label(root, image=image).pack()
for i in range(3):
    tk.Label(root, text=f"after{i}", fg="#d70000", bg="#0000d7").pack()
root.after(300, lambda: tk.Label(root, text="settled").pack())
root.mainloop()
"""


@pytest.mark.parametrize("direct", ["1", "0"], ids=["direct", "through-curses"])
def test_a_busy_picture_leaves_other_widgets_their_colours(terminal, tmp_path, direct):
    """A picture drawn as it is fills the colour pair table, and every
    colour asked for after it falls back to whichever pair came first: the
    Labels under it drew in #87005f on #0000ff. That held with the picture
    written past curses too, because what goes through curses under it is
    the fallback for a terminal that ignores those writes."""
    env = {"TKCURSES_DISPLAY_DIRECT_IMAGES": direct}
    term = terminal(cols=70, rows=28, env=env)
    term.run_source(BUSY_PICTURE, workdir=tmp_path)
    term.wait_for_text("settled")
    for i in range(3):
        row, column = term.find_text(f"after{i}")
        term.wait_for_cell(
            row, column, lambda cell: (cell.fg, cell.bg) == ("d70000", "0000d7")
        )


#: The same picture shown each other way a picture can be: on a Canvas, in
#: a Text, and as a window's background. Each draws its own way, and each
#: used to fill the table as a Label's picture did.
ELSEWHERE = {
    "canvas": (
        "c = tk.Canvas(root, width=60, height=20, highlightthickness=0)\n"
        "c.create_image(0, 0, image=image, anchor='nw')\n"
        "c.pack()"
    ),
    "text": (
        "t = tk.Text(root, width=62, height=21)\n"
        "t.image_create('1.0', image=image)\n"
        "t.pack()"
    ),
    "background": "tk.Frame(root, width=60, height=20, backgroundimage=image).pack()",
}


@pytest.mark.parametrize("shown", sorted(ELSEWHERE))
def test_a_busy_picture_anywhere_leaves_other_widgets_their_colours(
    terminal, tmp_path, shown
):
    """Measured before the fix: all three left the Labels in #87005f on
    #0000ff, the picture holding 252 of the pairs."""
    source = BUSY_PICTURE.replace(
        "tk.Label(root, image=image).pack()", ELSEWHERE[shown]
    )
    assert source != BUSY_PICTURE
    term = terminal(cols=70, rows=30, env={"TKCURSES_DISPLAY_DIRECT_IMAGES": "0"})
    term.run_source(source, workdir=tmp_path)
    term.wait_for_text("settled")
    for i in range(3):
        row, column = term.find_text(f"after{i}")
        term.wait_for_cell(
            row, column, lambda cell: (cell.fg, cell.bg) == ("d70000", "0000d7")
        )


# ------------------------------------------- PRIMARY to other applications

SELECTS = """
import tkcurses as tk
root = tk.Tk()
entry = tk.Entry(root)
entry.insert(0, "hello world")
entry.pack()
entry.focus_set()
entry.selection_range(0, 5)
def later(event):
    entry.selection_range(6, 11)
    root.after(800, lambda: tk.Label(root, text="settled").pack())
root.bind("<F5>", later)
tk.Label(root, text="ready").pack()
root.mainloop()
"""


def _osc52(selection, text):
    return b"\x1b]52;" + selection + b";" + base64.b64encode(text.encode()) + b"\x07"


def test_a_selection_reaches_the_systems_primary_once_it_settles(terminal, tmp_path):
    """What a middle click in another application pastes, as on X11. Sent
    once per settled selection, by the clipboard's route - OSC 52 here,
    with its 'p' target - and never to the clipboard itself."""
    env = {"TKCURSES_CLIPBOARD_SYSTEM": "osc52"}
    term = terminal(cols=30, rows=6, env=env)
    term.run_source(SELECTS, workdir=tmp_path)
    term.wait_for(lambda t: _osc52(b"p", "hello") in t.received)
    term.send_keys("<F5>")
    term.wait_for_text("settled")
    term.wait_for(lambda t: _osc52(b"p", "world") in t.received)
    assert term.received.count(_osc52(b"p", "hello")) == 1
    assert term.received.count(_osc52(b"p", "world")) == 1
    assert b"\x1b]52;c;" not in term.received


def test_primary_can_be_kept_inside(terminal, tmp_path):
    env = {"TKCURSES_CLIPBOARD_SYSTEM": "osc52", "TKCURSES_CLIPBOARD_PRIMARY": "0"}
    term = terminal(cols=30, rows=6, env=env)
    term.run_source(SELECTS, workdir=tmp_path)
    term.wait_for_text("ready")
    term.send_keys("<F5>")
    term.wait_for_text("settled")
    assert b"\x1b]52;p;" not in term.received
