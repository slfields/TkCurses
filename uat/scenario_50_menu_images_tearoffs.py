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
"""Menu entries with images, and menus that tear off.

What to do: open Tools (F2) and look at each entry's picture against its
label; tick Magnet and open Tools again. Open Icons (F4), which is taller
than the screen, and run down it with the arrows. Tear off Tools, Colours
and the Pens button's menu by choosing each one's dashed top line, then
choose from the copies.

What to look for: **where each picture sits**, and **the readout**, which
names the last thing chosen and every menu torn off. TkCurses-53hb.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "50 - Menu images and tear-offs"

#: Twelve icons for the long menu, each a colour.
ICONS = (
    "red",
    "orange",
    "yellow",
    "green",
    "cyan",
    "blue",
    "purple",
    "magenta",
    "white",
    "grey",
    "brown",
    "pink",
)


def square(colour, size):
    """A picture ``size`` pixels square: ``size`` cells wide, half as tall."""
    image = tkcurses.PhotoImage(width=size, height=size)
    image.put(colour, to=(0, 0, size, size))
    return image


def build(root, screen):
    area = _support.content_area(root, top=6)
    state = {"last": "-", "torn": []}

    def chose(what):
        def run():
            state["last"] = what
            report()

        return run

    def torn(menu, copy):
        state["torn"].append(copy)
        report()

    pictures = {
        "hammer": square("orange", 4),
        "saw": square("cyan", 4),
        "drill": square("yellow", 4),
        "level": square("green", 4),
        "off": square("grey", 4),
        "on": square("red", 4),
    }
    swatches = {name: square(name, 2) for name in ICONS}
    icons = {name: square(name, 4) for name in ICONS}
    # The pictures must outlive build(); a PhotoImage nobody holds is deleted.
    root.pictures = (pictures, swatches, icons)

    bar = tkcurses.Menu(root)
    tools = tkcurses.Menu(bar, tearoff=1, tearoffcommand=torn)
    tools.add_command(
        label="Hammer",
        image=pictures["hammer"],
        compound="left",
        command=chose("Hammer"),
    )
    tools.add_command(
        label="Saw", image=pictures["saw"], compound="top", command=chose("Saw")
    )
    tools.add_command(label="Drill", image=pictures["drill"], command=chose("Drill"))
    tools.add_command(
        label="Level",
        image=pictures["level"],
        compound="right",
        accelerator="F9",
        command=chose("Level"),
    )
    magnet = tkcurses.IntVar(root, value=0)
    tools.add_checkbutton(
        label="Magnet",
        image=pictures["off"],
        selectimage=pictures["on"],
        compound="left",
        variable=magnet,
        command=lambda: chose(f"Magnet {'on' if magnet.get() else 'off'}")(),
    )
    bar.add_cascade(label="Tools", menu=tools, underline=0)

    colours = tkcurses.Menu(bar, tearoff=1, tearoffcommand=torn)
    for name in ICONS[:6]:
        colours.add_command(
            label=name.title(),
            image=swatches[name],
            compound="left",
            command=chose(f"colour {name}"),
        )
    bar.add_cascade(label="Colours", menu=colours, underline=0)

    long = tkcurses.Menu(bar)
    for name in ICONS:
        long.add_command(
            label=name.title(),
            image=icons[name],
            compound="left",
            command=chose(f"icon {name}"),
        )
    bar.add_cascade(label="Icons", menu=long, underline=0)
    root.configure(menu=bar)

    pens = tkcurses.Menubutton(area, text="Pens", relief="raised")
    pens_menu = tkcurses.Menu(pens, tearoff=1, tearoffcommand=torn)
    for name in ("Fine", "Medium", "Broad"):
        pens_menu.add_command(label=name, command=chose(f"pen {name}"))
    pens["menu"] = pens_menu
    # On the right, clear of where Tools and its torn-off copy appear.
    pens.pack(anchor="e", padx=4)

    def report(*_):
        # From column 26, right of the Tools menu and the copy torn from it,
        # which would otherwise cover the readout.
        screen.line(0, f" {TITLE} ")
        screen.line(1, f"last chosen: {state['last']}", col=26)
        screen.line(2, f"torn off: {', '.join(state['torn']) or '-'}", col=26)
        screen.line(3, "F2 Tools, F3 Colours, F4 Icons.", col=26)
        screen.line(4, "The dashed line tears a menu off.", col=26)
        screen.line(5, "Escape closes a menu, or a copy.", col=26)
        screen.footer(" Ctrl+Q quits ")
        screen.refresh()

    def open_menu(index):
        def post(_event):
            bar.activate(index)
            bar.invoke(index)
            return "break"

        return post

    root.bind_all("<Key-F2>", open_menu(0))
    root.bind_all("<Key-F3>", open_menu(1))
    root.bind_all("<Key-F4>", open_menu(2))
    root.bind_all("<Control-q>", lambda _event: root.quit())
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
