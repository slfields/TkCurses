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

"""A wallpaper picker: a frame's background image, tiled or centred.

The desktop is a Frame whose backgroundimage is a small pattern drawn into
a PhotoImage with put. With tile on, copies of it cover the inside of the
frame's border from the top left; with it off, one copy sits in the
middle. The label in its corner is the frame's child, so it is drawn in
front of the pattern. Colours repaints the same image in place, and the
desktop follows it.
"""

import tkcurses as tk

#: Each pattern as rows of pixels: "a" is one colour and "b" the other.
#: A pixel is one column wide and half a row tall.
PATTERNS = {
    "Bricks": ("aaaaaaab", "aaaaaaab", "bbbbbbbb", "aaabaaaa", "aaabaaaa", "bbbbbbbb"),
    "Checks": ("aaaabbbb", "aaaabbbb", "bbbbaaaa", "bbbbaaaa"),
    "Stripes": ("abbbbbbb", "bbabbbbb", "bbbbabbb", "bbbbbbab"),
    "Diamonds": ("bbbabbbb", "bbaaabbb", "baaaaabb", "bbaaabbb", "bbbabbbb", "bbbbbbbb"),
}  # fmt: skip
#: Pairs of colours the Colours button steps through.
SCHEMES = (
    ("#b5523b", "#e8d8c3"),
    ("#2f5d8a", "#9cc3e6"),
    ("#3c7a4a", "#cfe3b8"),
)

root = tk.Tk()
root.title("Wallpaper")
pattern = tk.StringVar(root, "Bricks")
tiled = tk.BooleanVar(root, True)
scheme = {"index": 0}
picture = tk.PhotoImage(width=8, height=6)

panel = tk.Frame(root, padx=1)
panel.pack(side="left", fill="y")
desktop = tk.Frame(
    root,
    backgroundimage=picture,
    tile=True,
    background="black",
    relief="solid",
    borderwidth=1,
)
desktop.pack(side="left", fill="both", expand=True)
# A child of the desktop, so it is drawn in front of the pattern.
tk.Label(desktop, text=" Desktop ").place(relx=1, rely=1, x=-1, y=-1, anchor="se")


def paint():
    """Draw the chosen pattern, in the chosen colours, into the picture."""
    rows = PATTERNS[pattern.get()]
    first, second = SCHEMES[scheme["index"]]
    picture.configure(width=len(rows[0]), height=len(rows))
    picture.put([[first if pixel == "a" else second for pixel in row] for row in rows])
    size = f"{len(rows[0])}x{len(rows)} pixels"
    status.configure(
        text=f"{pattern.get()}, {size}, {'tiled' if tiled.get() else 'centred'}"
    )


def next_colours():
    scheme["index"] = (scheme["index"] + 1) % len(SCHEMES)
    paint()


def set_tile():
    desktop.configure(tile=tiled.get())
    paint()


tk.Label(panel, text="Wallpaper", font="TkHeadingFont").pack(anchor="w")
for name in PATTERNS:
    tk.Radiobutton(panel, text=name, value=name, variable=pattern, command=paint).pack(
        anchor="w"
    )
tk.Checkbutton(panel, text="Tile", variable=tiled, command=set_tile).pack(anchor="w")
buttons = tk.Frame(panel)
buttons.pack(anchor="w", pady=(1, 0))
tk.Button(buttons, text="Colours", command=next_colours).pack(side="left")
tk.Button(buttons, text="Quit", command=root.destroy).pack(side="left", padx=(1, 0))
status = tk.Label(panel, anchor="w", width=20, wraplength=20, justify="left")
status.pack(anchor="w")

paint()
root.mainloop()
