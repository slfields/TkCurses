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

"""Menus in columns, and shortcuts bound from the accelerator text.

What to do: open Colours (click it, or F3) and choose from its columns, by
mouse and with the arrows. Then use the File menu's shortcuts without opening
it - every one was bound by a single bind_accelerators() call, from the text
the menu shows.

What to look for: **the readout**, which names the last thing chosen and how.
TkCurses-aj1.13.1.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "46 - Menu columns and shortcuts"

COLOURS = (
    "Black",
    "Maroon",
    "Green",
    "Olive",
    "Navy",
    "Purple",
    "Teal",
    "Silver",
    "Grey",
    "Red",
    "Lime",
    "Yellow",
    "Blue",
    "Fuchsia",
    "Aqua",
)


def build(root, screen):
    area = _support.content_area(root, top=6)
    state = {"last": "-", "bound": ""}

    def chose(what):
        def run():
            state["last"] = what
            report()

        return run

    bar = tkcurses.Menu(root)
    files = tkcurses.Menu(bar)
    files.add_command(label="Open...", accelerator="Ctrl+O", command=chose("Open"))
    files.add_command(label="Save", accelerator="Ctrl+X Ctrl+S", command=chose("Save"))
    files.add_command(
        label="Print", accelerator="Ctrl+P", state="disabled", command=chose("Print")
    )
    recent = tkcurses.Menu(files)
    recent.add_command(label="Last file", accelerator="F5", command=chose("Last file"))
    recent.add_command(
        label="One before", accelerator="F6", command=chose("One before")
    )
    files.add_cascade(label="Recent", menu=recent)
    files.add_separator()
    files.add_command(label="Quit", accelerator="Ctrl+Q", command=root.quit)
    bar.add_cascade(label="File", menu=files, underline=0)

    colours = tkcurses.Menu(bar)
    for number, name in enumerate(COLOURS):
        colours.add_command(
            label=name,
            # A new column every five: Black, Purple and Lime head them.
            columnbreak=1 if number and number % 5 == 0 else 0,
            command=chose(f"colour {name}"),
        )
    bar.add_cascade(label="Colours", menu=colours, underline=0)
    root.configure(menu=bar)

    # The whole point: one call, from the text the menu shows.
    state["bound"] = ", ".join(files.bind_accelerators())

    tkcurses.Label(area, text="", name="spacer").pack()

    def report(*_):
        screen.line(0, f" {TITLE} ")
        screen.line(1, f"  last chosen: {state['last']}")
        screen.line(2, "  F2 opens File, F3 opens Colours. Arrows move, Escape closes.")
        screen.line(
            3, "  Shortcuts work with File closed: Ctrl+O, Ctrl+X Ctrl+S, F5, F6."
        )
        screen.line(4, f"  bound: {state['bound'][:72]}")
        screen.footer(" Ctrl+Q or Escape quits ")
        screen.refresh()

    def open_menu(index):
        def post(_event):
            bar.activate(index)
            bar.invoke(index)
            return "break"

        return post

    root.bind_all("<Key-F2>", open_menu(0))
    root.bind_all("<Key-F3>", open_menu(1))
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
