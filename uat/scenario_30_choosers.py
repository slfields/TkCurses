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

"""Picking a file, a directory or a colour out of what there is.

What to do: press a key to open a chooser and find something with it. Use
the mouse and the keyboard both - click a name, type one, double-click a
directory, press Filter. Walk up with `..` and back down again.
What to look for: the listing matches what is really in the directory; the
pattern hides files but never directories; `..` gets you out of anywhere; a
save asks before overwriting; and the answer at the top is the path you
actually picked.

These open on the directory this was started from, so they show a real tree
with real names in it - a chooser tested against three files in a temporary
folder is a chooser that has not been tested.

The colour chooser is here for the same reason the file ones are: it offers
what the device actually has rather than what a caller might ask for. Its
bars have as many steps as this terminal has intensities, and a name typed
into `Selection:` is answered with the colour the terminal will really draw -
`red` comes back as #cd0000, not #ff0000. There is more of it, across three
terminals, in UAT 31.
"""

from __future__ import annotations

import os

from tkcurses import colorchooser, filedialog
from uat import _support

TITLE = "30 - choosers: files, directories and colours"

#: Each key, what it opens, and what a person should try with it.
CHOOSERS: list[tuple[str, str, str]] = [
    ("o", "askopenfilename", "pick a file that exists"),
    ("s", "asksaveasfilename", "name one that does, and one that does not"),
    ("d", "askdirectory", "pick a directory, not a file"),
    ("l", "LoadFileDialog", "refuses a name that is not there"),
    ("w", "SaveFileDialog", "asks before overwriting"),
    ("c", "askcolor", "three bars, or type one in"),
]


def build(root, screen):
    here = os.getcwd()

    def report(name, value):
        shown = value
        if isinstance(value, str) and os.sep in value:
            shown = "..." + value[-(screen.width - 30) :]
        screen.line(1, f"  {name} returned {shown!r}")
        screen.refresh()

    calls = {
        "askopenfilename": lambda: filedialog.askopenfilename(
            parent=root, initialdir=here
        ),
        "asksaveasfilename": lambda: filedialog.asksaveasfilename(
            parent=root, initialdir=here
        ),
        "askdirectory": lambda: filedialog.askdirectory(parent=root, initialdir=here),
        "LoadFileDialog": lambda: filedialog.LoadFileDialog(root).go(here, "*"),
        "SaveFileDialog": lambda: filedialog.SaveFileDialog(root).go(here, "*"),
        "askcolor": lambda: colorchooser.askcolor(parent=root),
    }

    def open_chooser(name, call):
        def handler(event):
            report(name, call())
            return "break"

        return handler

    for key, name, _ in CHOOSERS:
        root.bind(f"<Key-{key}>", open_chooser(name, calls[name]))

    screen.line(0, f" {TITLE} ")
    screen.line(1, "  press a key")
    screen.line(2, "  " + "   ".join(f"{key} {name}" for key, name, _ in CHOOSERS[:3]))
    screen.line(3, "  " + "   ".join(f"{key} {name}" for key, name, _ in CHOOSERS[3:]))
    screen.line(5, f"  browsing from {here}")
    screen.footer(" Escape quits ")


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
