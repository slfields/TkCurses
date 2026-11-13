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

"""A recipe card: a Text with widgets and a picture in it.

The bowl is an image embedded in the text with image_create, and the
Spinbox, the Checkbuttons and the button at the end are widgets embedded
with window_create. Each takes one index in the text and moves with it as
any character would. The Spinbox scales the quantities, which are tagged
ranges rewritten in place; ticking an ingredient greys its line.
"""

import tkcurses as tk

#: Each ingredient, as its quantity for four people, its unit and its name.
INGREDIENTS = (
    (300, "g", "plain flour"),
    (2, "", "eggs"),
    (500, "ml", "milk"),
    (1, "pinch", "salt"),
    (30, "g", "butter, melted"),
)
STEPS = (
    "Whisk the flour, eggs, milk and salt into a smooth batter.",
    "Stir in the butter and leave it to stand for half an hour.",
    "Fry thin ladlefuls in a hot pan, a minute or so a side.",
)
SERVES = 4

root = tk.Tk()
root.title("Recipe")
text = tk.Text(root, wrap="word", cursor="", padx=1)
text.pack(fill="both", expand=True)
text.tag_configure("title", font=("TkDefaultFont", 10, "bold"), foreground="gold")
text.tag_configure("heading", font=("TkDefaultFont", 10, "bold"))
text.tag_configure("done", foreground="gray")

# The bowl: a PhotoImage, a pixel to half a cell, so eight across and six
# down is eight cells by three rows. Its line grows to hold it, with the
# title beside it in the middle.
bowl = tk.PhotoImage(width=8, height=6)
bowl.put("LightYellow", to=(2, 0, 6, 1))
bowl.put("SteelBlue", to=(0, 2, 8, 4))
bowl.put("SteelBlue", to=(1, 4, 7, 5))
bowl.put("SteelBlue", to=(2, 5, 6, 6))
text.image_create("end", image=bowl, padx=1)
text.insert("end", "Pancakes\n", "title")

text.insert("end", "\nServes ")
serves = tk.IntVar(value=SERVES)
spinner = tk.Spinbox(text, from_=1, to=12, width=3, textvariable=serves, relief="flat")
text.window_create("end", window=spinner)
text.insert("end", " people\n\n")

text.insert("end", "Ingredients\n", "heading")
ticks = []
for number, (_amount, unit, name) in enumerate(INGREDIENTS):
    line = f"line{number}"
    ticked = tk.BooleanVar(value=False)
    ticks.append(ticked)
    box = tk.Checkbutton(
        text,
        variable=ticked,
        borderwidth=0,
        command=lambda tag=line, var=ticked: (
            text.tag_add("done", f"{tag}.first", f"{tag}.last")
            if var.get()
            else text.tag_remove("done", f"{tag}.first", f"{tag}.last")
        ),
    )
    start = text.index("end-1c")
    text.window_create("end", window=box)
    text.insert("end", f" {unit} {name}".replace("  ", " ") + "\n")
    text.tag_add(line, start, "end-1c")


def amounts(*_):
    """Write each quantity for the number of people the Spinbox says.

    The text is read-only, and a disabled Text refuses a program's edits as
    well as typing, so this turns it on while it writes.
    """
    try:
        people = max(1, int(serves.get()))
    except (tk.TclError, ValueError):
        return
    state = text.cget("state")
    text.configure(state="normal")
    for number, (amount, _unit, _name) in enumerate(INGREDIENTS):
        scaled = amount * people / SERVES
        shown = (
            f"{scaled:g}"
            if scaled >= 10 or scaled == int(scaled)
            else (f"{scaled:.1f}")
        )
        tag = f"qty{number}"
        ranges = text.tag_ranges(tag)
        if ranges:
            text.replace(ranges[0], ranges[1], shown, tag)
        else:
            # The first time: just after the line's Checkbutton.
            text.insert(f"line{number}.first+1c", shown, tag)
    text.configure(state=state)


amounts()
serves.trace_add("write", amounts)

text.insert("end", "\nMethod\n", "heading")
for number, step in enumerate(STEPS, start=1):
    text.insert("end", f"{number}. {step}\n")
text.insert("end", "\n")


def clear():
    for ticked in ticks:
        ticked.set(False)
    text.tag_remove("done", "1.0", "end")


# A flat button is one row, so its line stays one row tall; a raised one
# is three, and its line would grow to hold it.
clear_button = tk.Button(
    text,
    text="Clear the ticks",
    command=clear,
    borderwidth=0,
    background="gold",
    foreground="black",
)
text.window_create("end", window=clear_button)
# Read-only from here. Tags still change on a disabled Text, so ticking
# needs nothing more; amounts() turns it on while it writes.
text.configure(state="disabled")
spinner.focus_set()
root.mainloop()
