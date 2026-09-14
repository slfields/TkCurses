"""Text: editing past the edges, wrapping, tags, attributes and selection.

What to do: type. Use the arrows, Home, End, Page Up and Page Down. Select
with Shift and the arrows, and by dragging with the mouse. Press F2 to cycle
the wrap mode, F3 to add a very long line, F4 to highlight the word under the
cursor, F5 to clear the highlights.
What to look for: the first paragraph is tagged to show what a tag can do -
bold, underline, italic, a colour, and a highlight. Those are ranges, not
characters: type in front of one and it moves with the text under it.

The cursor is visible only while the widget has the focus, and the view
follows it in both directions - down past the last visible line, and sideways
when wrapping is off. Up and Down move by what is on *screen*, so on a
wrapped paragraph they go to the row above or below rather than to the next
paragraph. Two lines report the mouse, and between them they say where any fault is.
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
            4, "  italic, colour, highlight.  F2 wrap  F3 long line  F4 tag  F5 clear"
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
        state["mouse"] = f"{event.type} at {event.x},{event.y}"
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

    # <Any-Key> rather than <Key>: a pattern with no modifier does not match
    # a key held with one, so a shifted arrow would never reach this and the
    # line above would stop reporting exactly when it mattered most.
    text.bind("<Any-Key>", lambda event: root.after_idle(report), add=True)
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
