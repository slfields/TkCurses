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

"""Services: what a server's memory goes to, as a treemap - groups and
the items in them, a legend with descriptions, and how values are
written.

A TkCurses widget: neither tkinter nor Tk has a treemap. Press v to step
the values through percentages, megabytes and none, p to move the
legend round the treemap, and n to list each group's items in it.
"""

import tkcurses as tk
from tkcurses.treemap import TreeMap

# Each group, what it is, and its items in megabytes; or an item alone.
MEMORY = {
    "web": ("the front end", {"nginx": 330, "apache": 170, "php": 50}),
    "db": ("primary and replica", {"postgres": 140, "mysql": 60}),
    "cache": ("redis, in memory", 100),
}

root = tk.Tk()
root.title("Services")
status = tk.Label(root, anchor="w")
status.pack(side="bottom", fill="x")
tree = TreeMap(root, units="MB", unitspace=True)
tree.pack(fill="both", expand=True)

for group, (about, content) in MEMORY.items():
    if isinstance(content, dict):
        # A group: its size is its items' sum.
        tree.insert("", "end", group, text=group, description=about)
        for name, megabytes in content.items():
            tree.insert(group, "end", name, text=name, value=megabytes)
    else:
        tree.insert("", "end", group, text=group, value=content, description=about)


def show() -> None:
    status.configure(
        text=f"{tree.cget('values')} | {tree.cget('legendposition')}"
        "  v: values  p: legend  n: nested  ^C: quit"
    )


def step(option: str, choices: tuple[str, ...]) -> None:
    now = choices.index(str(tree.cget(option)))
    tree.configure(**{option: choices[(now + 1) % len(choices)]})
    show()


root.bind("v", lambda event: step("values", ("percent", "value", "none")))
root.bind("p", lambda event: step("legendposition", ("right", "bottom", "left", "top")))


def nest() -> None:
    tree.configure(nestedlegend=not tree.cget("nestedlegend"))
    show()


root.bind("n", lambda event: nest())
show()
root.mainloop()
