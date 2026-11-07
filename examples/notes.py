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

"""Notes: a list of notes on the left, and the chosen one on the right.

The notes are kept in a JSON file, ``notes.json`` beside this program
unless another is named: ``python3 notes.py ~/notes.json``. Each is saved
a moment after you stop typing. Ctrl-N starts a note, and typing in the
search field shows only the notes that contain what was typed.
"""

import json
import sys
from pathlib import Path

import tkcurses as tk
from tkcurses import messagebox

# The data: a list of notes, each a title and a text, read from the file and
# written back to it whole.
STORE = (
    Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("notes.json")
)
notes: list[dict[str, str]] = json.loads(STORE.read_text()) if STORE.exists() else []
shown: list[int] = []  # which notes the list shows, by position in notes
current: int | None = None  # the note in the editor
loading = False  # True while the editor is being filled, which is not an edit
pending: str | None = None  # a save that has been scheduled and not yet made

# The window: a menu bar, a status line along the bottom, and two panes.
root = tk.Tk()
root.title("Notes")

status = tk.Label(root, anchor="w", bg="gray25", fg="white")
status.pack(side="bottom", fill="x")
panes = tk.PanedWindow(root, orient="horizontal", sashrelief="raised")
panes.pack(fill="both", expand=True)

# The left pane, packed: a search field, the list, and two buttons. The
# list is made before the buttons, because Tab visits widgets in the order
# they were made; the buttons are packed before the list, because a short
# terminal squeezes whatever was packed last.
left = tk.Frame(panes)
search = tk.StringVar()
tk.Label(left, text="Search", anchor="w").pack(fill="x")
search_field = tk.Entry(left, textvariable=search, width=1)
search_field.pack(fill="x")
titles = tk.Listbox(left, exportselection=False, width=1)
buttons = tk.Frame(left)
buttons.pack(side="bottom", fill="x")
titles.pack(fill="both", expand=True)
panes.add(left, minsize=14, width=22)

# The right pane, gridded: the title beside its label, the text below both.
right = tk.Frame(panes)
title = tk.StringVar()
tk.Label(right, text="Title ").grid(row=0, column=0, sticky="w")
title_field = tk.Entry(right, textvariable=title, width=1)
title_field.grid(row=0, column=1, columnspan=2, sticky="ew")
body = tk.Text(right, wrap="word", undo=True, width=1, height=1)
body.grid(row=1, column=0, columnspan=2, sticky="nsew")
bar = tk.Scrollbar(right, command=body.yview)
bar.grid(row=1, column=2, sticky="ns")
body.configure(yscrollcommand=bar.set)
right.columnconfigure(1, weight=1)
right.rowconfigure(1, weight=1)
panes.add(right, minsize=20)


# Showing the notes: the list holds the ones the search matches, and
# shown says which note each of its lines is.
def label(note):
    return note["title"].strip() or "(untitled)"


def fill_list():
    """Show the notes that match the search, and keep the current one chosen."""
    wanted = search.get().lower()
    shown[:] = [
        index
        for index, note in enumerate(notes)
        if wanted in (note["title"] + "\n" + note["text"]).lower()
    ]
    titles.delete(0, "end")
    for index in shown:
        titles.insert("end", label(notes[index]))
    if current in shown:
        titles.selection_set(shown.index(current))
    status.configure(text=f" {len(shown)} of {len(notes)} notes")


# Editing: the editor shows one note. Filling it is not an edit, so loading
# tells edited() to ignore the changes that filling it makes.
def open_note(index):
    """Put a note in the editor."""
    global current, loading
    current = index
    loading = True
    title.set(notes[index]["title"])
    body.delete("1.0", "end")
    body.insert("1.0", notes[index]["text"])
    body.edit_reset()
    body.edit_modified(False)
    loading = False


def clear_editor():
    global current, loading
    current = None
    loading = True
    title.set("")
    body.delete("1.0", "end")
    loading = False


def edited(*args):
    """Copy the editor back into the note, and save a little later."""
    global pending
    if loading or current is None:
        return
    notes[current] = {"title": title.get(), "text": body.get("1.0", "end-1c")}
    if current in shown:
        line = shown.index(current)
        titles.delete(line)
        titles.insert(line, label(notes[current]))
        titles.selection_set(line)
    if pending is not None:
        root.after_cancel(pending)
    pending = root.after(500, save)
    status.configure(text=" Editing...")


def save():
    global pending
    pending = None
    STORE.write_text(json.dumps(notes, indent=2))
    status.configure(text=f" Saved {len(notes)} notes to {STORE.name}")


def text_modified(event):
    # <<Modified>> comes when the flag changes, so clear it to hear the next.
    if body.edit_modified():
        edited()
        body.edit_modified(False)


# The commands: what the list, the buttons, the menu and the keys run.
def chosen(event):
    selection = titles.curselection()
    if selection:
        open_note(shown[selection[0]])


def new_note(event=None):
    notes.append({"title": "", "text": ""})
    search.set("")
    open_note(len(notes) - 1)
    fill_list()
    title_field.focus_set()


def delete_note():
    if current is None:
        return
    name = label(notes[current])
    if not messagebox.askyesno("Delete", f"Delete {name}?", parent=root):
        return
    del notes[current]
    clear_editor()
    fill_list()
    save()


def quit_notes(event=None):
    if pending is not None:
        root.after_cancel(pending)
        save()
    root.destroy()


# The buttons and the menu, made now that their commands exist.
tk.Button(buttons, text="New", command=new_note).pack(side="left")
tk.Button(buttons, text="Delete", command=delete_note).pack(side="right")

menubar = tk.Menu(root)
menu = tk.Menu(menubar, tearoff=0)
menu.add_command(label="New note", underline=0, accelerator="Ctrl+N", command=new_note)
menu.add_command(label="Delete note", underline=0, command=delete_note)
menu.add_separator()
menu.add_command(label="Quit", underline=0, accelerator="Ctrl+Q", command=quit_notes)
menubar.add_cascade(label="Notes", underline=0, menu=menu)
root.configure(menu=menubar)

# The connections: every change the user can make, and what it runs.
search.trace_add("write", lambda *args: fill_list())
title.trace_add("write", edited)
body.bind("<<Modified>>", text_modified)
titles.bind("<<ListboxSelect>>", chosen)
root.bind("<Control-n>", new_note)
root.bind("<Control-q>", quit_notes)
root.protocol("WM_DELETE_WINDOW", quit_notes)

# Start with the first note, or a new one if there are none, and run.
if notes:
    open_note(0)
    fill_list()
    titles.focus_set()
else:
    new_note()
root.mainloop()
