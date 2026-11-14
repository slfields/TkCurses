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

"""A text editor: a Text with a scrollbar, a menu bar, files and a status line.

F10, or Alt and an underlined letter, opens the menus. Ctrl-O, Ctrl-S and
Ctrl-Q open, save and quit; Ctrl-Z undoes. The View menu recolours the
whole editor with ``tk_setPalette``. Give a file name to open it:
``python3 editor.py notes.txt``.
"""

import sys
from pathlib import Path

import tkcurses as tk
from tkcurses import filedialog, messagebox

root = tk.Tk()
current: Path | None = None

text = tk.Text(root, undo=True, wrap="word")
bar = tk.Scrollbar(root, command=text.yview)
text.config(yscrollcommand=bar.set)
status = tk.Label(root, anchor="w", relief="flat")
status.pack(side="bottom", fill="x")
bar.pack(side="right", fill="y")
text.pack(side="left", fill="both", expand=True)


def show_status(event=None):
    line, column = text.index("insert").split(".")
    name = current.name if current else "untitled"
    changed = " (changed)" if text.edit_modified() else ""
    status.config(text=f" {name}{changed}   line {line}, column {int(column) + 1}")
    root.title(f"{name} - Editor")


def load(path):
    global current
    text.delete("1.0", "end")
    text.insert("1.0", path.read_text())
    text.mark_set("insert", "1.0")
    text.edit_reset()
    text.edit_modified(False)
    current = path
    show_status()


def open_file():
    name = filedialog.askopenfilename(parent=root)
    if name:
        load(Path(name))


def save_as():
    global current
    name = filedialog.asksaveasfilename(parent=root)
    if name:
        current = Path(name)
        save()


def save():
    if current is None:
        save_as()
        return
    current.write_text(text.get("1.0", "end-1c"))
    text.edit_modified(False)
    show_status()


def quit_editor():
    if text.edit_modified() and not messagebox.askyesno(
        "Quit", "Quit without saving?", parent=root
    ):
        return
    root.destroy()


menubar = tk.Menu(root)
files = tk.Menu(menubar, tearoff=0)
files.add_command(label="Open...", underline=0, accelerator="Ctrl+O", command=open_file)
files.add_command(label="Save", underline=0, accelerator="Ctrl+S", command=save)
files.add_command(label="Save as...", underline=5, command=save_as)
files.add_separator()
files.add_command(label="Quit", underline=0, accelerator="Ctrl+Q", command=quit_editor)
menubar.add_cascade(label="File", underline=0, menu=files)
edit = tk.Menu(menubar, tearoff=0)
edit.add_command(
    label="Undo", underline=0, accelerator="Ctrl+Z", command=text.edit_undo
)
edit.add_separator()
edit.add_command(
    label="Cut", underline=2, command=lambda: text.event_generate("<<Cut>>")
)
edit.add_command(
    label="Copy", underline=0, command=lambda: text.event_generate("<<Copy>>")
)
edit.add_command(
    label="Paste", underline=0, command=lambda: text.event_generate("<<Paste>>")
)
menubar.add_cascade(label="Edit", underline=0, menu=edit)
# A palette recolours every widget from one background, as Tk's does.
view = tk.Menu(menubar, tearoff=0)
view.add_command(
    label="Dark", underline=0, command=lambda: root.tk_setPalette("#1e2430")
)
view.add_command(label="Bisque", underline=0, command=root.tk_bisque)
menubar.add_cascade(label="View", underline=0, menu=view)
root.config(menu=menubar)
files.bind_accelerators()
edit.bind_accelerators()

root.protocol("WM_DELETE_WINDOW", quit_editor)
# After the key has done its work, which is when the cursor has moved. A
# terminal sends no key releases, so <KeyRelease> would never come.
for sequence in ("<Key>", "<ButtonRelease-1>"):
    text.bind(sequence, lambda event: root.after_idle(show_status), add="+")
if len(sys.argv) > 1:
    load(Path(sys.argv[1]))
show_status()
text.focus_set()
root.mainloop()
