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

"""Actions: doing something when an item of a treemap is chosen - any
item, the items with a tag, or one item alone - and zooming into a group.

A TkCurses widget: neither tkinter nor Tk has a treemap. Click a tile,
or move with the arrows and press Space. Return on a group, or a
double-click, zooms in; Escape zooms out.
"""

import tkcurses as tk
from tkcurses.treemap import TreeMap

root = tk.Tk()
root.title("Actions")
status = tk.Label(root, anchor="w", text="Click a tile, or the arrows and Space")
status.pack(side="bottom", fill="x")
tree = TreeMap(root, legend="hide")
tree.pack(fill="both", expand=True)
tree.focus_set()

tree.insert("", "end", "web", text="web")
tree.insert("web", "end", "nginx", text="nginx", value=330)
tree.insert("web", "end", "apache", text="apache", value=170)
tree.insert("", "end", "db", text="db")
# Tags group items for tag_bind, as in a Treeview.
tree.insert("db", "end", "postgres", text="postgres", value=140, tags="disk")
tree.insert("db", "end", "mysql", text="mysql", value=60, tags="disk")
tree.insert("", "end", "cache", text="cache", value=100, tags="cache")


def chosen(event: tk.Event) -> None:
    """Every selection: say what was chosen, a group or an item."""
    item = tree.selection()[0] if tree.selection() else ""
    if not item:
        return
    kind = "group" if tree.get_children(item) else "item"
    value = tree.item(item, "value")
    if tree.get_children(item):
        value = sum(tree.item(child, "value") for child in tree.get_children(item))
    status.configure(text=f"{kind} {tree.item(item, 'text')}: {value:g}")


def check_disk(event: tk.Event) -> None:
    """Only the items tagged disk."""
    status.configure(text=status.cget("text") + "   (checking its disk)")


def flush(event: tk.Event) -> None:
    """Only cache, the one item with that tag."""
    status.configure(text=status.cget("text") + "   (flushed)")


tree.bind("<<TreeMapSelect>>", chosen)
# A tag binding runs after the widget's own, so chosen() has written first.
tree.tag_bind("disk", "<<TreeMapSelect>>", check_disk)
tree.tag_bind("cache", "<<TreeMapSelect>>", flush)
tree.bind(
    "<<TreeMapZoom>>",
    lambda event: status.configure(
        text=f"zoomed into {tree.zoom()}" if tree.zoom() else "zoomed out"
    ),
)
root.mainloop()
