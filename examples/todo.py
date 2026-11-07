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

"""A to-do list: a Listbox, an Entry, and keys that work on both.

Type a task and press Return to add it. Tab to the list, choose a task
with the arrows, and press Delete to remove it, or space to mark it done.
"""

import tkcurses as tk

root = tk.Tk()
root.title("To do")

entry = tk.Entry(root)
entry.pack(fill="x", padx=1, pady=(1, 0))
# Packed before the list, so that in a short terminal the list gives up rows
# and the count stays: pack takes space from whatever was packed last.
count = tk.Label(root, text="", anchor="w")
count.pack(side="bottom", fill="x", padx=1)
tasks = tk.Listbox(root, height=6)
tasks.pack(fill="both", expand=True, padx=1, pady=1)


def recount():
    done = sum(tasks.get(i).startswith("[x]") for i in range(tasks.size()))
    count.config(text=f"{tasks.size()} tasks, {done} done")


def add(event):
    text = entry.get().strip()
    if text:
        tasks.insert("end", f"[ ] {text}")
        entry.delete(0, "end")
        recount()


def remove(event):
    tasks.delete("active")
    recount()


def toggle(event):
    # The active task, the one the arrows have reached: this runs before the
    # Listbox's own binding for space, which would select it.
    index = tasks.index("active")
    text = tasks.get(index)
    mark = "[ ]" if text.startswith("[x]") else "[x]"
    tasks.delete(index)
    tasks.insert(index, mark + text[3:])
    tasks.selection_clear(0, "end")
    tasks.selection_set(index)
    tasks.activate(index)
    recount()


entry.bind("<Return>", add)
tasks.bind("<Delete>", remove)
tasks.bind("<space>", toggle)
for task in ("Water the plants", "Write the report"):
    tasks.insert("end", f"[ ] {task}")
recount()
entry.focus_set()
root.mainloop()
