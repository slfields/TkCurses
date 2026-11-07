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

"""Three geometry managers in one window, and how each follows a resize.

The window is packed: a title along the top, a status bar along the
bottom, and between them a PanedWindow whose sash can be dragged with the
mouse, or moved with the arrows once Tab has given it the focus. Its left
pane is packed, its right pane gridded, and the status bar uses place,
which positions by fractions of its master. Each pane shows its own size,
so dragging the sash or resizing the terminal shows who takes the room.
"""

import tkcurses as tk

root = tk.Tk()
root.title("Layout")

# pack: whole edges of the window, in the order they are packed. The
# PanedWindow is packed last so that it gets what the other two leave.
title = tk.Label(
    root, text="pack, grid and place", background="navy", foreground="white"
)
title.pack(side="top", fill="x")
status = tk.Frame(root, background="gray25", height=1)
status.pack(side="bottom", fill="x")
panes = tk.PanedWindow(root, orient="horizontal", sashrelief="raised", showhandle=True)
panes.pack(fill="both", expand=True)

# The left pane is packed: a heading and buttons along the top, and a
# Listbox that expands into the rest.
left = tk.Frame(panes)
left_heading = tk.Label(left, background="dark green", foreground="white")
left_heading.pack(side="top", fill="x")
for name in ("New", "Open"):
    tk.Button(left, text=name).pack(side="top", fill="x")
folders = tk.Listbox(left, height=1)
folders.pack(side="top", fill="both", expand=True)
for folder in ("Inbox", "Drafts", "Sent", "Archive", "Spam", "Trash"):
    folders.insert("end", folder)

# The right pane is gridded: labels in a column of their own size, fields
# in a column with weight 1 that takes every extra cell, and a Text in a
# row with weight 1 that takes every extra row.
right = tk.Frame(panes)
right_heading = tk.Label(right, background="dark red", foreground="white")
right_heading.grid(row=0, column=0, columnspan=2, sticky="ew")
for row, field in enumerate(("To", "Subject"), start=1):
    tk.Label(right, text=field).grid(row=row, column=0, sticky="w", padx=(1, 1))
    tk.Entry(right, width=1).grid(row=row, column=1, sticky="ew", padx=(0, 1))
message = tk.Text(right, width=1, height=1, wrap="word")
message.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=1)
message.insert("1.0", "The fields widen with the pane, and this grows both ways.")
right.columnconfigure(1, weight=1)
right.rowconfigure(3, weight=1)

# The left pane starts 20 cells wide and the right takes the rest. Growth
# goes to the last pane too, as Tk's "stretch last" default gives it, so the
# left keeps its width until the sash is moved.
panes.add(left, minsize=12, width=20)
panes.add(right, minsize=20)

# place: by fraction of the status bar, so these stay at its left, middle
# and right edge however wide it becomes.
size = tk.Label(status, background="gray25", foreground="white")
size.place(relx=0, rely=0, x=1, anchor="nw")
hint = tk.Label(status, text="Tab, then the arrows: move the sash", background="gray25")
hint.place(relx=0.5, rely=0, anchor="n")
badge = tk.Label(status, text="relx=1", background="gold", foreground="black")
badge.place(relx=1, rely=0, x=-1, anchor="ne")


def measure(event=None):
    """Write each pane's size into its heading, and the window's below."""
    left_heading.configure(text=f"pack {left.winfo_width()}x{left.winfo_height()}")
    right_heading.configure(text=f"grid {right.winfo_width()}x{right.winfo_height()}")
    size.configure(text=f"{root.winfo_width()}x{root.winfo_height()}")


for widget in (left, right, root):
    widget.bind("<Configure>", measure, add=True)
root.after_idle(measure)
root.mainloop()
