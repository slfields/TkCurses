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

"""The themed core widgets, and whether they answer at all.

What to do: use every widget on the left. Click the button. Tick the box.
Pick a radio. Open the menubutton. Type in the entry. Step the spinbox with
its arrows and with Up/Down. **Drag the sash between the two panes.** Drag
the scrollbar. Then press Ctrl-T for another theme and do it again, and
Ctrl-R to restyle every themed class while they are on screen.

What to look for: the line at the bottom names the last widget that
responded. **A widget that draws correctly and reports nothing when you use
it is the failure this scenario exists to catch.**

That is not hypothetical. ttk.Panedwindow shipped from this very epic with
its sash dragging, motion, release and key handling registered under the
CLASSIC widget's name while it reported ``TPanedwindow`` - so the sash drew
perfectly and could not be moved. Its option surface was right, its pane()
and sashpos() methods worked when called, and four thousand tests passed,
because nothing in the suite ever delivered a gesture to it. A hand on the
sash would have found it in seconds, which is the whole argument for running
a scenario like this one EARLY in a cycle rather than at the end of it.

The cause was a class of fault worth knowing, because it has now happened
five times here. Binding tags name one class and not a chain: a widget whose
``winfo_class()`` answers ``TButton`` is offered what is bound to ``TButton``
and nothing bound to ``Button``. So a themed widget must install its own
bindings under its own name, and a classic widget that hardcodes its name
instead of asking leaves every subclass with none. Both directions have bitten
this project - Spinbox/Entry, OptionMenu/Menubutton and ScrolledText/Text from
the subclass side, Button and then eight more from the base side.

The classic counterparts stand beside each themed one on purpose. They are
the control: a theme change or a restyle must move the left column and leave
the right alone. If both move, the style is not scoped to the themed classes;
if neither does, nothing is reaching the style database at all.
"""

from __future__ import annotations

import tkcurses
from tkcurses import ttk
from uat import _support

TITLE = "40 - ttk: the themed core widgets"

#: What Ctrl-R restyles, so a person can see the scoping. Each is a themed
#: class name, and nothing here names a classic one - which is the point.
RESTYLED = (
    "TButton",
    "TCheckbutton",
    "TRadiobutton",
    "TMenubutton",
    "TEntry",
    "TSpinbox",
    "TScrollbar",
    "TFrame",
    "TLabelframe",
    "TPanedwindow",
)


def build(root, screen):
    style = ttk.Style(root)
    themes = list(style.theme_names())
    state = {"theme": 0, "styled": False}

    screen.line(0, f" {TITLE} ")
    screen.line(1, "  themed              list+bar     classic (control)")
    screen.footer(" ^T theme   ^R restyle themed classes   ^B default   Escape quits ")

    area = _support.content_area(root, top=2, bottom=3)

    answered = tkcurses.Label(area, name="answered", anchor="w")

    def responded(what):
        """Called by every widget here, so silence is visible."""

        def handler(*_args):
            answered.configure(text=f"responded: {what}")

        return handler

    # ------------------------------------------------- button and checkbutton
    ttk.Button(area, name="tb", text="Button", command=responded("ttk.Button")).place(
        x=2, y=0, width=14
    )
    tkcurses.Button(
        area, name="cb", text="Button", command=responded("classic Button")
    ).place(x=36, y=0, width=14)

    ticked = tkcurses.IntVar(root, 0)
    ttk.Checkbutton(
        area,
        name="tc",
        text="Checkbutton",
        variable=ticked,
        command=responded("ttk.Checkbutton"),
    ).place(x=2, y=3, width=16)
    tkcurses.Checkbutton(
        area, name="cc", text="Checkbutton", command=responded("classic Checkbutton")
    ).place(x=36, y=3, width=16)

    # ------------------------------------------------------------ radiobuttons
    chosen = tkcurses.StringVar(root, "one")
    for offset, value in enumerate(("one", "two")):
        ttk.Radiobutton(
            area,
            name=f"tr{offset}",
            text=f"Radio {value}",
            value=value,
            variable=chosen,
            command=responded(f"ttk.Radiobutton {value}"),
        ).place(x=2, y=4 + offset, width=16)
    tkcurses.Radiobutton(
        area,
        name="cr",
        text="Radio one",
        value="one",
        command=responded("classic Radio"),
    ).place(x=36, y=4, width=16)

    # ------------------------------------------------------------- menubutton
    menubutton = ttk.Menubutton(area, name="tm", text="Menubutton")
    menubutton.place(x=2, y=6, width=16)
    menu = tkcurses.Menu(menubutton, name="menu", tearoff=0)
    for word in ("first", "second"):
        menu.add_command(label=word, command=responded(f"ttk.Menubutton {word}"))
    menubutton.configure(menu=menu)

    # ------------------------------------------------------- entry and spinbox
    entry = ttk.Entry(area, name="te")
    entry.place(x=2, y=9, width=16)
    entry.bind("<KeyRelease>", responded("ttk.Entry"))
    classic_entry = tkcurses.Entry(area, name="ce")
    classic_entry.place(x=36, y=9, width=16)
    classic_entry.bind("<KeyRelease>", responded("classic Entry"))

    spin = ttk.Spinbox(
        area, name="ts", from_=0, to=10, command=responded("ttk.Spinbox")
    )
    spin.place(x=2, y=12, width=16)

    # -------------------------------------------------------------- scrollbar
    #
    # Wired to something that actually scrolls, because a scrollbar is a remote
    # control and not a slider: it asks its command to scroll, and the thing
    # scrolled calls set() back to say where it ended up. Measured on real ttk -
    # a scrollbar whose command ignores the request does NOT move its own thumb,
    # get() still answers (0.2, 0.6) after a drag.
    #
    # The first version of this scenario wired the command to the report line
    # and nothing else, so dragging reported a response and the thumb never
    # moved. That read as a broken widget and was a broken demonstration.
    scrolled = tkcurses.Listbox(area, name="list", height=9)
    scrolled.place(x=19, y=0, width=12, height=9)
    for number in range(1, 31):
        scrolled.insert("end", f"item {number}")
    bar = ttk.Scrollbar(area, name="tbar", orient="vertical")
    bar.place(x=32, y=0, width=1, height=9)

    def scroll(*args):
        responded("ttk.Scrollbar")()
        scrolled.yview(*args)

    bar.configure(command=scroll)
    scrolled.configure(yscrollcommand=bar.set)

    # --------------------------------------------------- frame and labelframe
    ttk.Frame(area, name="tf", relief="solid").place(x=56, y=0, width=16, height=3)
    tkcurses.Label(area, text="ttk.Frame", anchor="w").place(x=57, y=1, width=12)
    box = ttk.Labelframe(area, name="tlf", text="Labelframe")
    box.place(x=56, y=4, width=16, height=4)
    tkcurses.Label(box, text="in a frame", anchor="w").place(x=1, y=1, width=12)

    # ----------------------------------- panedwindow: the sash that was dead
    panes = ttk.Panedwindow(area, name="tp", orient="horizontal")
    panes.place(x=56, y=9, width=16, height=6)
    for side in ("left", "right"):
        pane = ttk.Frame(panes, name=side)
        tkcurses.Label(pane, text=side, anchor="w").place(x=0, y=1, width=6)
        panes.add(pane, weight=1)
    panes.bind("<B1-Motion>", responded("ttk.Panedwindow sash"))

    answered.place(x=2, y=15, relwidth=1.0, width=-4)
    answered.configure(text="responded: nothing yet - use something")

    showing = tkcurses.Label(area, name="showing", anchor="w")
    showing.place(x=2, y=16, relwidth=1.0, width=-4)

    def describe():
        name = themes[state["theme"]]
        restyled = "restyled" if state["styled"] else "default styling"
        showing.configure(text=f"theme {name}   {restyled}")

    def next_theme(event=None):
        del event
        state["theme"] = (state["theme"] + 1) % len(themes)
        style.theme_use(themes[state["theme"]])
        describe()
        return "break"

    def restyle(event=None):
        del event
        for name in RESTYLED:
            style.configure(name, foreground="yellow", background="blue")
        state["styled"] = True
        describe()
        return "break"

    def default(event=None):
        del event
        for name in RESTYLED:
            style.configure(name, foreground="", background="")
        state["styled"] = False
        describe()
        return "break"

    root.bind("<Control-t>", next_theme)
    root.bind("<Control-r>", restyle)
    root.bind("<Control-b>", default)
    describe()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
