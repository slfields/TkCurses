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

"""Colour, at whatever depth this particular terminal has.

What to do: read the top two lines, then run the same scenario again under a
different TERM and compare. The four worth trying are all on this machine::

    TERM=xterm            python3 -m uat 31
    TERM=xterm-16color    python3 -m uat 31
    TERM=xterm-256color   python3 -m uat 31
    TERM=xterm-direct     python3 -m uat 31

What to look for: the tier on line 2 should match what ``tput colors`` says in
the same shell - that line is the library's answer, and if it is wrong then
everything below it is wrong for the same reason. Then the ramps: in direct
colour they are smooth, at 256 close to it, at 16 they are four or five
bands, at 8 they are two.
Then the two rows of backgrounds, which are the bug this cycle began with: at
8 colours the bright row is identical to the dark one, because the only way
to be bright there is an attribute and no attribute has ever brightened a
background. At 16 and above the two rows differ.

Press ``c`` for the colour chooser, which is the same question asked as a
dialog: its bars have as many steps as the terminal has intensities, so they
grow as the terminal gets better.
"""

from __future__ import annotations

import curses
import os

from tkcurses import colorchooser
from tkcurses._core.colors import TRUECOLOR_ENV
from uat import _support

TITLE = "31 - colour: what this terminal really has"

#: The eight hues, and the name each one's bright form goes by here.
HUES: list[tuple[str, str]] = [
    ("black", "darkgray"),
    ("red", "#ff0000"),
    ("green", "lime"),
    ("yellow", "#ffff00"),
    ("blue", "#5c5cff"),
    ("magenta", "fuchsia"),
    ("cyan", "#00ffff"),
    ("white", "#ffffff"),
]

#: Cells in a ramp. Wide enough that banding is obvious and narrow enough to
#: fit a terminal nobody has widened.
RAMP = 32

#: Columns given to the name at the start of each row of colour.
LABEL = 10


def _ramp(channel: int | None) -> list[str]:
    """One ramp of ``#rrggbb``, either a grey or a single channel."""
    colors = []
    for step in range(RAMP):
        level = round(step * 255 / (RAMP - 1))
        rgb = [level, level, level] if channel is None else [0, 0, 0]
        if channel is not None:
            rgb[channel] = level
        colors.append(f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}")
    return colors


def build(root, screen):
    depth = root.winfo_colordepth()
    reported = curses.tigetnum("colors")
    # > 0, not bool(): tigetflag answers -1 for a capability the terminal does
    # not have listed at all, and bool(-1) is True.
    direct = curses.tigetflag("RGB") > 0
    colorterm = os.environ.get("COLORTERM", "")

    screen.line(0, f" {TITLE} ")
    screen.line(
        1,
        f"  detected {depth.name} ({int(depth)} colours)"
        f"     <- compare this with: tput colors",
    )
    screen.line(
        2,
        f"  TERM={os.environ.get('TERM', '?')}"
        f"  terminfo colors={reported}  RGB={'yes' if direct else 'no'}"
        f"  curses.COLORS={getattr(curses, 'COLORS', '?')}",
    )
    screen.line(
        3,
        f"  COLORTERM={colorterm or '(unset)'}"
        + (
            "  - a promise about escape sequences, not about curses"
            if colorterm in TRUECOLOR_ENV
            else ""
        ),
    )

    #: Each labelled row of colour: the row it goes on, its name, the colours
    #: along it, and how many cells each colour gets.
    rows: list[tuple[int, str, list[str], int]] = [
        (5, "grey", _ramp(None), 1),
        (6, "red", _ramp(0), 1),
        (7, "green", _ramp(1), 1),
        (8, "blue", _ramp(2), 1),
        (10, "dark bg", [dark for dark, _ in HUES], 4),
        (11, "bright bg", [bright for _, bright in HUES], 4),
    ]
    for row, name, _, _ in rows:
        screen.line(row, name.rjust(LABEL))
    screen.line(13, "  press c for the colour chooser")
    screen.footer(" c chooser   Escape quits ")

    def paint(event=None):
        """Put the colour back on the screen.

        Written straight into the buffer rather than built out of Labels.
        A Label holds one background, so these six rows are 144 of them -
        enough widgets that laying them out took a second before the title
        appeared, which is a long time to look at nothing and long enough
        that the scenario smoke test timed out on a slow machine.

        The instruction text is written to the buffer for its own reasons and
        is replayed on a resize by the Screen; this has to do the same, and
        must run after it, since that replay clears the buffer first.
        """
        buffer = root.tk.screen.buffer
        for row, _, colors, width in rows:
            for index, color in enumerate(colors):
                column = LABEL + 1 + index * width
                if column + width <= buffer.width and row < buffer.height:
                    buffer.write(row, column, " " * width, fg="white", bg=color)
        screen.refresh()

    def choose(event):
        rgb, name = colorchooser.askcolor(parent=root, title=" Colour ")
        screen.line(13, f"  chooser answered {rgb} {name}")
        paint()
        return "break"

    root.bind("<Key-c>", choose)
    # add="+" and after the Screen's own handler, which clears the buffer.
    root.bind("<Configure>", paint, add="+")
    paint()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
