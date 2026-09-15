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
different TERM and compare. The three worth trying are all on this machine::

    TERM=xterm            python3 -m uat 31
    TERM=xterm-16color    python3 -m uat 31
    TERM=xterm-256color   python3 -m uat 31

What to look for: the tier on line 2 should match what ``tput colors`` says in
the same shell - that line is the library's answer, and if it is wrong then
everything below it is wrong for the same reason. Then the ramps: at 256 they
are close to smooth, at 16 they are four or five bands, at 8 they are two.
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

import tkcurses
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


def _blocks(parent, row: int, name: str, colors: list[str], width: int = 1) -> None:
    """One labelled row of solid colour."""
    tkcurses.Label(parent, text=name, width=11, anchor="e").grid(row=row, column=0)
    strip = tkcurses.Frame(parent)
    strip.grid(row=row, column=1, sticky="w")
    for color in colors:
        tkcurses.Label(strip, text=" " * width, background=color).pack(side="left")


def build(root, screen):
    depth = root.winfo_colordepth()
    reported = curses.tigetnum("colors")
    # > 0, not bool(): tigetflag answers -1 for a capability the
    # terminal does not have listed at all, and bool(-1) is True.
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

    area = _support.content_area(root, top=5, bottom=2)
    _blocks(area, 0, "grey", _ramp(None))
    _blocks(area, 1, "red", _ramp(0))
    _blocks(area, 2, "green", _ramp(1))
    _blocks(area, 3, "blue", _ramp(2))

    tkcurses.Label(area, text="").grid(row=4, column=0)
    _blocks(area, 5, "dark bg", [dark for dark, _ in HUES], width=4)
    _blocks(area, 6, "bright bg", [bright for _, bright in HUES], width=4)

    answer = tkcurses.Label(area, text="  press c for the colour chooser", anchor="w")
    answer.grid(row=8, column=0, columnspan=2, sticky="w")

    def choose(event):
        rgb, name = colorchooser.askcolor(parent=root, title=" Colour ")
        answer.configure(text=f"  chooser answered {rgb} {name}")
        return "break"

    root.bind("<Key-c>", choose)
    root.update_layout()
    screen.footer(" c chooser   Escape quits ")


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
