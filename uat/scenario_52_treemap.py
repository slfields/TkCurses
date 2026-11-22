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

"""Treemaps: square to the eye, shades, outlines, labels and small tiles.

What to do: look at the services; press n for 24 items and n again to
come back; o to step outline through auto, on and off; v to step values
through percent, value and none; l to turn labels off and on; + and - to
grow and shrink nginx; t to add a tiny item and take it away. Run it
again under TERM=xterm and TERM=vt100.

What to look for: **tiles look near square in your font**, neighbours
are told apart by shade, lines appear where shades cannot be, labels fit
their tiles or are left out, and the readout counts what is too small to
show. TkCurses-i1rh.10.
"""

from __future__ import annotations

from tkcurses.treemap import Treemap
from uat import _support

TITLE = "52 - Treemaps"

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

OUTLINES = ("auto", "on", "off")
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


def build(root, screen):
    area = _support.content_area(root, top=5)
    tree = Treemap(area)
    tree.pack(fill="both", expand=True)
    state = {"data": "services"}
    fill(tree, SERVICES)

    def report():
        colors = root.tk.colors
        depth = int(colors.depth) if colors is not None and colors.has_colors else 0
        screen.line(0, f" {TITLE} ")
        screen.line(1, "n: 24 items   o: outline   v: values   l: labels")
        screen.line(2, "+/-: grow/shrink nginx   t: a tiny item")
        screen.line(
            3,
            f"colours {DEPTHS.get(depth, depth)}   outline={tree.cget('outline')}"
            f"   values={tree.cget('values')}   labels={int(tree.cget('labels'))}"
            f"   data={state['data']}",
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
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
