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


"""Record what real Tk does with the navigation keys in its text widgets.

Run with a display and the system tkinter, from the repository root::

    DISPLAY=:0 /usr/bin/python3 tests/support/record_navigation_keys.py

It writes ``navigation_keys.json`` beside itself, which
``tests/test_navigation_keys.py`` replays against tkcurses. A step is one of:

=========  ==========================================================
``k K M``  key ``K`` with modifiers ``M`` (``S`` Shift, ``C`` Control)
``v V``    the virtual event ``<<V>>``
``j i``    ``icursor``/``mark_set("insert")`` to ``i``
``r a b``  ``selection_range``/``tag_add("sel")`` from ``a`` to ``b``
=========  ==========================================================

After every step it records the insertion cursor and the selection, as
indices: an Entry's ``[insert, first, last]`` with ``null`` for no
selection, a Text's ``[insert, ranges]``. The keys are the ones entry.tcl,
ttk/entry.tcl, spinbox.tcl and text.tcl bind through tk.tcl's navigation
virtual events, and the physical ones bound beside them. TkCurses-wmaq.
"""

from __future__ import annotations

import json
import random
import tkinter
import tkinter.font
import tkinter.ttk
from pathlib import Path
from typing import Any, Literal

#: Words, runs of spaces, underscores and punctuation, for the word motions.
LINE = "hello world  foo_bar-baz, 42 x"
#: Paragraphs split by an empty line and a line of spaces, a line indented,
#: and lines of different lengths for Up and Down to keep the column across.
TEXT = (
    "first line of text\n"
    "  second, shorter\n"
    "\n"
    "third paragraph here\n"
    "fourth_word-joined end\n"
    "   \n"
    "x\n"
    "last paragraph, line one\n"
    "and two"
)
MODIFIERS = {"": 0, "S": 1, "C": 4, "CS": 5}
ARROWS = ["Left", "Right", "Home", "End"]
KEYS = [(key, mods) for key in ARROWS for mods in MODIFIERS]
UP_DOWN = [(key, mods) for key in ("Up", "Down") for mods in MODIFIERS]
VIRTUAL = [
    "PrevChar", "NextChar", "PrevWord", "NextWord", "LineStart", "LineEnd",
    "SelectPrevChar", "SelectNextChar", "SelectPrevWord", "SelectNextWord",
    "SelectLineStart", "SelectLineEnd", "SelectAll", "SelectNone",
]  # fmt: skip
TEXT_VIRTUAL = [
    *VIRTUAL,
    "PrevLine", "NextLine", "SelectPrevLine", "SelectNextLine",
    "PrevPara", "NextPara", "SelectPrevPara", "SelectNextPara",
]  # fmt: skip

#: Each widget, and the keys sent to it. Not Up and Down to the spinboxes,
#: whose bindings step the value, nor to the Combobox, where Down posts the
#: list: those replace the text and are not navigation. Nor Prior and Next to
#: the Text, which are bound as themselves and go by the view.
WIDGETS: dict[str, list[tuple[str, str]]] = {
    "Entry": KEYS + UP_DOWN,
    "Spinbox": KEYS,
    "TEntry": KEYS + UP_DOWN,
    "TCombobox": KEYS,
    "TSpinbox": KEYS,
    "Text": KEYS + UP_DOWN,
    # Wrapped at a word, 16 columns: Up, Down, Home and End go by the rows
    # on screen, which in a monospaced font are the same in both.
    "WrappedText": KEYS + UP_DOWN,
}


def make(root: tkinter.Tk, kind: str, font: tkinter.font.Font) -> Any:
    if kind == "Entry":
        # Any: Entry, Spinbox, the ttk ones and Text share these methods by
        # name, not through a common base the stubs know of.
        widget: Any = tkinter.Entry(root, font=font, width=12)
    elif kind == "Spinbox":
        widget = tkinter.Spinbox(root, font=font, width=12, values=())
    elif kind == "TEntry":
        widget = tkinter.ttk.Entry(root, font=font, width=12)
    elif kind == "TCombobox":
        widget = tkinter.ttk.Combobox(root, font=font, width=12)
    elif kind == "TSpinbox":
        widget = tkinter.ttk.Spinbox(root, font=font, width=12)
    else:
        wrap: Literal["word", "none"] = "word" if kind == "WrappedText" else "none"
        widget = tkinter.Text(root, font=font, width=16, height=4, wrap=wrap)
    widget.configure(exportselection=False)
    widget.pack()
    if kind.endswith("Text"):
        widget.insert("1.0", TEXT)
    else:
        widget.insert(0, LINE)
    return widget


def entry_state(widget: Any) -> list[object]:
    insert = widget.index("insert")
    if widget.selection_present():
        return [insert, widget.index("sel.first"), widget.index("sel.last")]
    return [insert, None, None]


def text_state(widget: Any) -> list[object]:
    return [widget.index("insert"), [str(i) for i in widget.tag_ranges("sel")]]


def random_index(rng: random.Random, kind: str) -> str | int:
    if not kind.endswith("Text"):
        return rng.randrange(len(LINE) + 1)
    lines = TEXT.split("\n")
    row = rng.randrange(len(lines))
    return f"{row + 1}.{rng.randrange(len(lines[row]) + 1)}"


def random_steps(rng: random.Random, kind: str) -> list[list[Any]]:
    steps: list[list[Any]] = [["j", random_index(rng, kind)]]
    virtual = TEXT_VIRTUAL if kind.endswith("Text") else VIRTUAL
    for _ in range(rng.randint(1, 8)):
        choice = rng.choice("kkkkkkvvjr")
        if choice == "k":
            key, mods = rng.choice(WIDGETS[kind])
            steps.append(["k", key, mods])
        elif choice == "v":
            steps.append(["v", rng.choice(virtual)])
        elif choice == "j":
            steps.append(["j", random_index(rng, kind)])
        else:
            a, b = sorted(
                (random_index(rng, kind), random_index(rng, kind)),
                key=lambda i: tuple(map(int, str(i).split("."))),
            )
            steps.append(["r", a, b])
    return steps


def run(
    root: tkinter.Tk, font: tkinter.font.Font, kind: str, steps: list[list[Any]]
) -> list[list[Any]]:
    widget = make(root, kind, font)
    widget.focus_force()
    root.update()
    # tk::TextUpDownLine's column memory is global, so one case would carry
    # it into the next; this is the value text.tcl starts it at.
    root.tk.eval("set ::tk::Priv(prevPos) {}")
    root.tk.eval("unset -nocomplain ::tk::Priv(textPosOrig)")
    state = text_state if kind.endswith("Text") else entry_state
    after = []
    for step in steps:
        if step[0] == "k":
            widget.event_generate(
                "<KeyPress>", keysym=str(step[1]), state=MODIFIERS[str(step[2])]
            )
        elif step[0] == "v":
            widget.event_generate(f"<<{step[1]}>>")
        elif step[0] == "j":
            if kind.endswith("Text"):
                widget.mark_set("insert", step[1])
            else:
                widget.icursor(step[1])
        elif kind.endswith("Text"):
            widget.tag_remove("sel", "1.0", "end")
            widget.tag_add("sel", step[1], step[2])
        else:
            widget.selection_range(step[1], step[2])
        root.update()
        after.append(state(widget))
    widget.destroy()
    return after


def record(count: int = 150, seed: int = 20261104) -> dict[str, list[object]]:
    rng = random.Random(seed)
    root = tkinter.Tk()
    font = tkinter.font.nametofont("TkFixedFont")
    assert len({font.measure(c) for c in "iW0-"}) == 1, "not monospaced"
    cases: dict[str, list[object]] = {}
    for kind in WIDGETS:
        plans = [random_steps(rng, kind) for _ in range(count)]
        cases[kind] = [
            {"steps": steps, "after": run(root, font, kind, steps)} for steps in plans
        ]
    root.destroy()
    return cases


if __name__ == "__main__":
    out = Path(__file__).with_name("navigation_keys.json")
    data: dict[str, Any] = {
        "measured": "tkinter on Python 3.14 over Tk 9.0.2",
        "line": LINE,
        "text": TEXT,
        "cases": record(),
    }
    out.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(sum(map(len, data["cases"].values())), "cases ->", out)
