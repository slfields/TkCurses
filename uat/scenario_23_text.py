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

"""Text: editing past the edges, wrapping, tags, attributes and selection.

What to do: type. Use the arrows, Home, End, Page Up and Page Down, and the
same keys with Control held. Select with Shift and the arrows, and by
dragging with the mouse. Press F2 to cycle the wrap mode, F3 to add a very
long line, F4 to highlight the word under the cursor, F5 to clear the
highlights.
What to look for: the first paragraph is tagged to show what a tag can do -
bold, underline, italic, a colour, and a highlight. Those are ranges, not
characters: type in front of one and it moves with the text under it.

The cursor is visible only while the widget has the focus, and the view
follows it in both directions - down past the last visible line, and sideways
when wrapping is off.

Up, Down, Home and End all work on the line *as it appears on screen*, not on
the paragraph. On a wrapped paragraph, Down goes to the row below rather than
to the next paragraph, and Home goes to the start of the row rather than of
the paragraph. That is what Tk does - the behaviour here was checked against
Tk 9.0.2 and the same numbers are asserted in the test suite - and Control
with those keys is what reaches further: Control-Home and Control-End for the
whole document, Control-Left and Control-Right by word. Two lines report the mouse, and between them they say where any fault is.
`curses:` is the raw report ncurses produced and what this library decoded it
to; `mouse:` is what actually reached the widget. While you drag, `curses:`
should keep changing and end in `->drag`. If it never changes, the terminal
is not reporting motion at all. If it changes but says `->pressed`, the
terminal is reporting and the library is misreading it.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "23 - text: editing, wrapping, tags and selection"

WRAPS = ("word", "char", "none")

PARAGRAPH = (
    "A Text widget is a window onto something bigger than itself. "
    "Everything is addressed by index, written line.char with lines counting "
    "from 1. Marks survive editing; tags describe ranges that move with the "
    "text under them.\n"
    "This is a second paragraph, so that Up and Down have somewhere to go.\n"
)

#: Tag name, what it does, and the words in the first paragraph to put it on.
SAMPLES = (
    ("bold", {"font": "bold"}, "Text widget"),
    ("underline", {"underline": True}, "window"),
    ("italic", {"font": "italic"}, "bigger than itself"),
    ("coloured", {"foreground": "cyan"}, "line.char"),
    ("highlight", {"background": "yellow", "foreground": "black"}, "Marks"),
)


def build(root, screen):
    area = _support.content_area(root, top=5)
    state = {"wrap": 0, "mouse": "-", "raw": "-"}

    row = tkcurses.Frame(area)
    row.pack(side="top", fill="both", expand=True, padx=1)
    text = tkcurses.Text(row, width=40, height=10, wrap=WRAPS[0])
    text.pack(side="left", fill="both", expand=True)
    bar = tkcurses.Scrollbar(row, command=text.yview)
    bar.pack(side="left", fill="y")
    text.configure(yscrollcommand=bar.set)

    text.insert("1.0", PARAGRAPH * 3)

    # Tag the sample words where they first appear, so the attributes are
    # visible without anyone having to do anything first.
    whole = text.get("1.0", "end")
    for name, options, phrase in SAMPLES:
        text.tag_configure(name, **options)
        at = whole.find(phrase)
        if at >= 0:
            start = text.index(f"1.0 +{at}c")
            text.tag_add(name, start, f"{start} +{len(phrase)}c")

    text.mark_set("insert", "1.0")
    text.see("1.0")

    def report(*_):
        try:
            selection = text.get("sel.first", "sel.last")
        except Exception:
            selection = ""
        marked = len(text.tag_ranges("highlight")) // 2
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  insert={text.index('insert')}  end={text.index('end')}  "
            f"wrap={WRAPS[state['wrap']]!r}  selected={len(selection)} chars",
        )
        screen.line(
            2,
            f"  mouse: {state['mouse']}   curses: {state['raw']}   "
            f"highlights: {marked}",
        )
        screen.line(3, "  Type. Shift+arrows or drag to select. Tags: bold, underline,")
        screen.line(
            4, "  italic, colour, highlight.  Ctrl+arrows by word.  F2 F3 F4 F5"
        )
        screen.footer(" Escape quits ")
        screen.refresh()

    def next_wrap(event):
        state["wrap"] = (state["wrap"] + 1) % len(WRAPS)
        text.configure(wrap=WRAPS[state["wrap"]])
        text.see("insert")
        report()
        return "break"

    def add_long_line(event):
        text.insert("insert lineend", "\n" + "long " * 30)
        text.see("insert")
        report()
        return "break"

    def tag_word(event):
        text.tag_add("highlight", "insert wordstart", "insert wordend")
        report()
        return "break"

    def clear_tags(event):
        text.tag_remove("highlight", "1.0", "end")
        report()
        return "break"

    def note_mouse(event):
        state["mouse"] = f"{event.type.name} at {event.x},{event.y}"
        root.after_idle(report)

    def tap_the_decoder():
        """Record what curses reported, not only what the widget made of it.

        If dragging does nothing, this is the line that says why: no report
        at all means the terminal is not sending motion, and a report that
        decodes to `pressed` rather than `drag` means it is the library.
        """
        handler = getattr(root, "_input", None)
        if handler is None:
            return
        mode = handler.motion_mode
        state["raw"] = f"asked for {mode.decode('ascii', 'replace')!r}"
        decoder = handler.decoder
        original = decoder.decode

        def tap(x, y, bstate):
            events = original(x, y, bstate)
            kinds = ",".join(event.state for event in events) or "-"
            state["raw"] = f"0x{bstate:x}@{x},{y}->{kinds}"
            root.after_idle(report)
            return events

        decoder.decode = tap

    tap_the_decoder()

    # <Key> is enough: a pattern's modifiers need only be a subset of the
    # event's, so this sees a shifted arrow too. It did not always - which is
    # why this line once used <Any-Key> and stopped reporting exactly when it
    # mattered most.
    text.bind("<Key>", lambda event: root.after_idle(report), add=True)
    text.bind("<Button-1>", note_mouse, add=True)
    text.bind("<Motion>", note_mouse, add=True)
    text.bind("<ButtonRelease-1>", note_mouse, add=True)
    root.bind_all("<Key-F2>", next_wrap)
    root.bind_all("<Key-F3>", add_long_line)
    root.bind_all("<Key-F4>", tag_word)
    root.bind_all("<Key-F5>", clear_tags)
    text.focus_set()
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
