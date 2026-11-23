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

"""Disk usage: what fills a directory, as a treemap - each directory in
it a group, and in each the files, or the kinds of file, below it;
scanned again every few seconds so the picture follows the disk.

A TkCurses widget: neither tkinter nor Tk has a treemap. Run it with a
directory to look at; with none, it looks at TkCurses itself. Return on
a directory, or a double-click, zooms into it; Escape zooms out; k
switches between the files and their kinds.
Caches and version control - __pycache__, .git - are left out: they come
and go, and are rarely what fills a disk.
"""

import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import tkcurses as tk
from tkcurses.treemap import TreeMap

TOP = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tk.__file__).parent
#: How often the directory is scanned again, in milliseconds.
EVERY = 3000
#: Files counted at most, so a vast directory does not hang the program.
MOST = 20_000
#: Where the files directly in TOP are counted.
HERE = "(here)"
#: Directories not looked into.
SKIP = {"__pycache__", ".git"}
#: "files" names each file in a group, "kinds" each suffix.
by = ["files"]


def scan(top: Path, by: str) -> dict[str, tuple[Counter[str], int]]:
    """For each directory in ``top``, the bytes of each file below it, or
    of each kind of file with ``by="kinds"``, and how many files there
    were."""
    found: dict[str, tuple[Counter[str], int]] = {}
    sizes: dict[str, Counter[str]] = defaultdict(Counter)
    files: Counter[str] = Counter()
    seen = 0
    for folder, dirs, names in os.walk(top):
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        where = Path(folder).relative_to(top).parts
        group = where[0] if where else HERE
        for name in names:
            try:
                size = (Path(folder) / name).stat().st_size
            except OSError:
                continue  # gone, or not ours to read
            if by == "kinds":
                label = Path(name).suffix or "(none)"
            else:
                label = "/".join((*where[1:], name))  # its path in the group
            sizes[group][label] += size
            files[group] += 1
            seen += 1
            if seen >= MOST:
                break
        if seen >= MOST:
            break
    for group, kinds in sizes.items():
        found[group] = (kinds, files[group])
    return found


root = tk.Tk()
root.title("Disk usage")
status = tk.Label(root, anchor="w")
status.pack(side="bottom", fill="x")
tree = TreeMap(
    root, values="value", units="B", unitscale="binary", digits=3, legendsize="small"
)
tree.pack(fill="both", expand=True)
tree.focus_set()


def refresh() -> None:
    """Scan again and change only what changed, so nothing flickers."""
    found = scan(TOP, by[0])
    for group in tree.get_children():
        if group not in found:
            tree.delete(group)
    for group, (kinds, count) in found.items():
        about = f"{count} file{'s' if count != 1 else ''}"
        if not tree.exists(group):
            tree.insert("", "end", group, text=group)
        tree.item(group, description=about)
        for kind in tree.get_children(group):
            if kind.split("/", 1)[1] not in kinds:
                tree.delete(kind)
        for suffix, size in kinds.items():
            iid = f"{group}/{suffix}"
            if tree.exists(iid):
                tree.item(iid, value=size)
            else:
                tree.insert(group, "end", iid, text=suffix, value=size)
    status.configure(
        text=f"{TOP.name}/ by {by[0]}   Return/Escape: zoom  k: files/kinds  ^C: quit"
    )


def again() -> None:
    refresh()
    root.after(EVERY, again)


def switch() -> None:
    by[0] = "kinds" if by[0] == "files" else "files"
    refresh()


root.bind("k", lambda event: switch())
again()
root.mainloop()
