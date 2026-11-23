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

"""TreeMaps: tiles, shades, outlines, labels, the legend, keys and size.

What to do, pass 1: look at the services; press n for 24 items and n
again to come back; o to step outline through auto, on and off; v to step
values through percent, value and none; l to turn labels off and on; +
and - to grow and shrink nginx; t to add a tiny item and take it away.
Run it again under TERM=xterm and TERM=vt100.

Pass 2: g steps legend through auto, show and hide; p moves it right,
left, top and bottom; s steps legendsize; e turns nestedlegend on and
off; w steps legendlines 1 to 5; d turns the items' descriptions on and
off; z steps the size through filling the area, 50% by 50% of the
screen, 60 columns by 50%, and 30 columns alone. The arrows, Space,
Return, Escape and the mouse focus, select and zoom.

What to look for: **tiles look near square in your font**, neighbours
are told apart by shade, lines appear where shades cannot be, labels fit
their tiles or are left out, and the readout counts what is too small to
show; the legend never covers a tile, descriptions appear in it and
nowhere else, and a percentage size follows the terminal when it is
resized. TkCurses-i1rh.10, TkCurses-i1rh.11.
"""

from __future__ import annotations

from tkcurses.treemap import TreeMap
from uat import _support

TITLE = "52 - TreeMaps"

SERVICES = (
    ("web", (("nginx", 330), ("apache", 170), ("php", 50))),
    ("db", (("postgres", 140), ("mysql", 60))),
    ("cache", 100),
)

#: Twenty-four items in four groups: sizes spread from large to small,
#: never random, so two runs draw the same.
MANY = tuple(
    (
        group,
        tuple((f"{group}{n}", size) for n, size in enumerate(sizes, start=1)),
    )
    for group, sizes in (
        ("a", (90, 70, 55, 40, 30, 22, 15)),
        ("b", (80, 50, 35, 20, 12, 8)),
        ("c", (60, 45, 25, 18, 9)),
        ("d", (40, 30, 20, 10, 5, 3)),
    )
)

#: Said in the legend under each name, with d: long enough to wrap.
DESCRIPTIONS = {
    "web": "front end: the proxy and the app servers",
    "db": "primary and replica",
    "cache": "redis, in memory",
    "nginx": "reverse proxy",
    "a": "the largest group, seven items",
    "b": "six items",
    "c": "five items",
    "d": "six items, the smallest",
}

#: z steps through these: a name, then width and height, or None to fill.
SIZES = (
    ("fill", None),
    ("50% x 50%", ("50%", "50%")),
    ("60 x 50%", (60, "50%")),
    ("width 30", (30, 0)),
)

OUTLINES = ("auto", "on", "off")
LEGENDS = ("auto", "show", "hide")
POSITIONS = ("right", "left", "top", "bottom")
LEGEND_SIZES = ("auto", "small", "medium", "large", "xlarge")
LINES = ("1", "2", "3", "4", "5")
VALUES = ("percent", "value", "none")
DEPTHS = {0: "none", 8: "8", 16: "16", 256: "256", 1 << 24: "truecolor"}


def fill(tree, data):
    """Replace ``tree``'s items with ``data``: ``(name, value)`` for an
    item, ``(name, ((child, value), ...))`` for a group."""
    tree.delete(*tree.get_children())
    for name, content in data:
        if isinstance(content, tuple):
            tree.insert("", "end", name, text=name)
            for child, value in content:
                tree.insert(name, "end", child, text=child, value=value)
        else:
            tree.insert("", "end", name, text=name, value=content)


def describe(tree, on):
    """Give every item in :data:`DESCRIPTIONS` its description, or none."""
    for iid, text in DESCRIPTIONS.items():
        if tree.exists(iid):
            tree.item(iid, description=text if on else "")


def build(root, screen):
    area = _support.content_area(root, top=7)
    tree = TreeMap(area)
    tree.pack(fill="both", expand=True)
    state = {
        "data": "services",
        "selects": 0,
        "zooms": 0,
        "descriptions": False,
        "size": 0,
    }
    fill(tree, SERVICES)
    tree.focus_set()

    def report():
        colors = root.tk.colors
        depth = int(colors.depth) if colors is not None and colors.has_colors else 0
        screen.line(0, f" {TITLE} ")
        screen.line(
            1, "n: 24 items   o: outline   v: values   l: labels   +/-: nginx   t: tiny"
        )
        screen.line(
            2,
            "g: legend   p: position   s: legendsize   e: nested   w: lines"
            "   d: descriptions",
        )
        screen.line(3, "z: size   arrows, Space, Return, Escape, mouse: select/zoom")
        screen.line(
            4,
            f"colours {DEPTHS.get(depth, depth)}   outline={tree.cget('outline')}"
            f"   values={tree.cget('values')}   labels={int(tree.cget('labels'))}"
            f"   data={state['data']}",
        )
        screen.line(
            5,
            f"legend={tree.cget('legend')} {tree.cget('legendposition')}"
            f" size={tree.cget('legendsize')}"
            f" nested={int(tree.cget('nestedlegend'))}"
            f" lines={tree.cget('legendlines')}"
            f" desc={int(state['descriptions'])}"
            f"   size: {SIZES[state['size']][0]}",
        )
        chosen = tree.selection()[0] if tree.selection() else "-"
        screen.line(
            6,
            f"selected {chosen} ({state['selects']} TreeMapSelect)"
            f"   zoom {tree.zoom() or '-'} ({state['zooms']} TreeMapZoom)",
        )
        screen.footer(" Escape quits ")
        screen.refresh()

    def step(option, choices):
        now = str(tree.cget(option))
        tree.configure(**{option: choices[(choices.index(now) + 1) % len(choices)]})
        report()

    def data():
        state["data"] = "24 items" if state["data"] == "services" else "services"
        fill(tree, MANY if state["data"] == "24 items" else SERVICES)
        describe(tree, state["descriptions"])
        report()

    def descriptions():
        state["descriptions"] = not state["descriptions"]
        describe(tree, state["descriptions"])
        report()

    def size():
        state["size"] = (state["size"] + 1) % len(SIZES)
        given = SIZES[state["size"]][1]
        tree.pack_forget()
        if given is None:
            tree.configure(width=0, height=0)
            tree.pack(fill="both", expand=True)
        else:
            tree.configure(width=given[0], height=given[1])
            tree.pack(anchor="nw")
        report()

    def grow(by):
        if tree.exists("nginx"):
            tree.item("nginx", value=max(0, tree.item("nginx", "value") + by))
        report()

    def tiny():
        if tree.exists("tiny"):
            tree.delete("tiny")
        else:
            tree.insert("", "end", "tiny", text="tiny", value=0.5)
        report()

    root.bind_all("n", lambda _event: data())
    root.bind_all("o", lambda _event: step("outline", OUTLINES))
    root.bind_all("v", lambda _event: step("values", VALUES))
    root.bind_all(
        "l", lambda _event: (tree.configure(labels=not tree.cget("labels")), report())
    )
    root.bind_all("+", lambda _event: grow(50))
    root.bind_all("=", lambda _event: grow(50))
    root.bind_all("-", lambda _event: grow(-50))
    root.bind_all("t", lambda _event: tiny())
    root.bind_all("g", lambda _event: step("legend", LEGENDS))
    root.bind_all("p", lambda _event: step("legendposition", POSITIONS))
    root.bind_all("s", lambda _event: step("legendsize", LEGEND_SIZES))
    root.bind_all(
        "e",
        lambda _event: (
            tree.configure(nestedlegend=not tree.cget("nestedlegend")),
            report(),
        ),
    )
    root.bind_all("w", lambda _event: step("legendlines", LINES))
    root.bind_all("d", lambda _event: descriptions())
    root.bind_all("z", lambda _event: size())
    # A resize changes what a percentage asks for: show the size it got.
    root.bind(
        "<Configure>",
        lambda event: root.after_idle(report) if event.widget is root else None,
        add="+",
    )

    def counted(name):
        state[name] += 1
        report()

    tree.bind("<<TreeMapSelect>>", lambda _event: counted("selects"))
    tree.bind("<<TreeMapZoom>>", lambda _event: counted("zooms"))
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
