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

"""A calculator: coloured buttons in a grid, worked by mouse or keyboard.

Each button has its own background and foreground, and another colour
while the mouse is over it. The grid's rows and columns all have weight,
so the keys grow with the window. Type the digits and + - * /, Return or
= for the answer, Escape to clear and BackSpace to take back a digit.
"""

from decimal import Decimal, DivisionByZero, InvalidOperation

import tkcurses as tk

# What each key does, as the keyboard types it, and what its button says.
KEYS = (
    ("C", "negate", "%", "/"),
    ("7", "8", "9", "*"),
    ("4", "5", "6", "-"),
    ("1", "2", "3", "+"),
    ("0", ".", "back", "="),
)
LABELS = {
    "negate": "\N{PLUS-MINUS SIGN}",
    "/": "\N{DIVISION SIGN}",
    "*": "\N{MULTIPLICATION SIGN}",
    "-": "\N{MINUS SIGN}",
    "back": "\N{ERASE TO THE LEFT}",
}
OPERATIONS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b,
}
# Background, foreground, and the background under the mouse.
COLOURS = {
    "digit": ("gray25", "white", "gray40"),
    "operator": ("dark orange", "black", "orange"),
    "function": ("gray60", "black", "gray75"),
    "equals": ("sea green", "white", "medium sea green"),
    "clear": ("firebrick", "white", "indian red"),
}

root = tk.Tk()
root.title("Calculator")
# The window's own colour shows between the keys, and its padding is the
# margin round them.
root.configure(background="gray15", padx=1, pady=1)
# Anchored east, so a number too long for the screen shows its end.
screen = {"background": "black", "anchor": "e", "padx": 1}
history = tk.Label(root, foreground="gray60", **screen)
history.grid(row=0, column=0, columnspan=4, sticky="nsew")
display = tk.Label(root, text="0", foreground="lime green", **screen)
display.grid(row=1, column=0, columnspan=4, sticky="nsew")

# The number being typed, the total so far, and the operation waiting for
# the next number. "fresh" is true when the next digit starts a new number.
state = {"entry": "0", "total": None, "operation": None, "fresh": True}


def kind(key):
    if key in OPERATIONS:
        return "operator"
    if key in ("=", "C"):
        return {"=": "equals", "C": "clear"}[key]
    if key in ("negate", "%", "back"):
        return "function"
    return "digit"


def number(value):
    """A Decimal to twelve figures, without trailing zeros, as a person
    writes it - and with an exponent only when it is too big or small."""
    rounded = f"{value:.12g}"
    if "e" not in rounded:
        return f"{Decimal(rounded).normalize():f}"
    mantissa, exponent = rounded.split("e")
    if "." in mantissa:
        mantissa = mantissa.rstrip("0").rstrip(".")
    return f"{mantissa}e{exponent}"


def show(above=None):
    display.configure(text=state["entry"])
    if above is not None:
        history.configure(text=above)


def clear():
    state.update(entry="0", total=None, operation=None, fresh=True)
    show("")


def type_digit(key):
    if state["fresh"]:
        state.update(entry="0", fresh=False)
    if key == "." and "." in state["entry"]:
        return
    if state["entry"] == "0" and key != ".":
        state["entry"] = key
    else:
        state["entry"] += key
    show()


def operate(key):
    """An operator, or =: finish the sum waiting for this number, if any."""
    operation, entry = state["operation"], Decimal(state["entry"])
    above = ""
    if operation is not None and not state["fresh"]:
        sign = LABELS.get(operation, operation)
        above = f"{number(state['total'])} {sign} {state['entry']} ="
        state["total"] = OPERATIONS[operation](state["total"], entry)
    elif not state["fresh"] or state["total"] is None:
        state["total"] = entry
    state.update(
        entry=number(state["total"]),
        operation=None if key == "=" else key,
        fresh=True,
    )
    show(above if key == "=" else f"{state['entry']} {LABELS.get(key, key)}")


def press(key):
    try:
        if key.isdigit() or key == ".":
            type_digit(key)
        elif key == "C":
            clear()
        elif key == "back":
            if not state["fresh"]:  # an answer is not typed, so not untyped
                state["entry"] = state["entry"][:-1] or "0"
                show()
        elif key == "negate":
            state["entry"] = number(-Decimal(state["entry"]))
            show()
        elif key == "%":
            state["entry"] = number(Decimal(state["entry"]) / 100)
            show()
        else:
            operate(key)
    except (DivisionByZero, InvalidOperation):
        clear()
        display.configure(text="Division by zero")


for row, keys in enumerate(KEYS, start=2):
    for column, key in enumerate(keys):
        background, foreground, under_mouse = COLOURS[kind(key)]
        tk.Button(
            root,
            text=LABELS.get(key, key),
            command=lambda key=key: press(key),
            background=background,
            foreground=foreground,
            activebackground=under_mouse,
            activeforeground=foreground,
            relief="flat",
            takefocus=False,
        ).grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=(0, 1 if column < 3 else 0),
            pady=(1, 0),
        )
# One uniform group: the four columns stay the same width, even while a
# long number asks the grid for more room than the window has.
for column in range(4):
    root.columnconfigure(column, weight=1, uniform="key")
for row in range(2, len(KEYS) + 2):
    root.rowconfigure(row, weight=1)


def typed(event):
    if event.char and (event.char.isdigit() or event.char in ".%=+-*/"):
        press(event.char)


root.bind("<Key>", typed)
root.bind("<Return>", lambda e: press("="))
root.bind("<KP_Enter>", lambda e: press("="))
root.bind("<Escape>", lambda e: press("C"))
root.bind("<BackSpace>", lambda e: press("back"))
root.mainloop()
