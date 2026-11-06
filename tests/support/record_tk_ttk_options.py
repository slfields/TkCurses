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

"""The options Tk's own themed widgets take, asked of Tk itself.

TkCurses's ttk widgets accept more than Tk's - the classic widget's
options, inherited - so the API reference cannot read a ttk widget's
options from TkCurses. It documents the set Tk has, recorded here from
real tkinter with ``keys()`` (TkCurses-imii.6, TkCurses-jo7l).

Needs tkinter and a display; the root is withdrawn, so no window shows.
Run from the repository root, with a Tk of the version the reference is
written against (9.0.2 when this was recorded)::

    python3 tests/support/record_tk_ttk_options.py
"""

from __future__ import annotations

import json
import tkinter
from pathlib import Path
from tkinter import ttk

OUT = Path(__file__).with_name("tk_ttk_options.json")

WIDGETS = [
    "Button",
    "Checkbutton",
    "Combobox",
    "Entry",
    "Frame",
    "Label",
    "Labelframe",
    "LabeledScale",
    "Menubutton",
    "Notebook",
    "OptionMenu",
    "Panedwindow",
    "Progressbar",
    "Radiobutton",
    "Scale",
    "Scrollbar",
    "Separator",
    "Sizegrip",
    "Spinbox",
    "Treeview",
]


def main() -> None:
    root = tkinter.Tk()
    root.withdraw()
    found = {}
    for name in WIDGETS:
        cls = getattr(ttk, name)
        widget = (
            cls(root, tkinter.StringVar(root)) if name == "OptionMenu" else cls(root)
        )
        found[name] = sorted(set(widget.keys()))
    root.destroy()
    OUT.write_text(json.dumps(found, indent=1) + "\n")
    print(f"Tk {tkinter.TkVersion}:", {name: len(keys) for name, keys in found.items()})


if __name__ == "__main__":
    main()
