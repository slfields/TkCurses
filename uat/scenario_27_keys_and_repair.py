"""Which binding wins, what a key is called, and what a crash leaves behind.

What to do: type across the whole keyboard - letters, the number row plain
and with Shift, punctuation, Tab, Return, the function keys - and hold Shift
and Control over the same keys. Then press the button that raises, and
finally shrink the terminal to a few columns and grow it back.
What to look for: one press fires exactly one binding, and the line says
which of the overlapping ones it was; the key's name matches the key you
pressed; a traceback leaves the display exactly as it was; and a hard resize
leaves nothing of the old layout behind.

The four bindings below overlap on purpose. Tk runs the most specific match
per binding tag and no other: a press with Shift held has to reach
<Shift-Key> rather than <Key>, and a named key has to reach its own binding
rather than either. Escape is the working example - it quits from
<Key-Escape> while <Key> is bound over the whole keyboard.

Punctuation is bound both ways round: the semicolon by its X11 name and the
comma by the character itself. Tk takes either spelling for the same key and
reports the character, so both lines must name the key you pressed.

A terminal cannot say that Shift was held over a printable key - it sends the
capital and nothing else - so <Shift-Key> is reachable only through the keys
that have their own shifted code: Shift with an arrow, Home, End, Page Up or
Page Down, Delete or Insert.

Three keys never arrive at all, and their absence from the history is the
correct result rather than a fault. A tty turns Ctrl-C, Ctrl-\\ and Ctrl-Z
into signals - interrupt, quit and suspend - before any byte reaches the
application, so no binding can see them. Ctrl-C ending this scenario is
exactly that, and is what scenario 09 checks on purpose. Ctrl-S and Ctrl-Q
would have gone the same way as flow control; the library asks the tty for
those two back, which is why they *do* appear.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "27 - bindings, key names and repair after a crash"

#: Every binding this scenario installs, in the order the list is printed.
#: Each one records its own pattern, so the line of history says which of
#: them the press actually reached.
PATTERNS = [
    "<Key>",
    "<Shift-Key>",
    "<Control-Key>",
    "<Control-Shift-Key>",
    "<Key-Tab>",
    "<Key-Return>",
    "<Key-F1>",
    "<Key-semicolon>",
    "<Key-,>",
]

MODIFIERS = [(0x01, "Shift"), (0x02, "Control"), (0x04, "Alt"), (0x08, "Meta")]


def modifier_names(state: int) -> str:
    """The modifiers in an event's state, named."""
    held = [name for bit, name in MODIFIERS if state & bit]
    return "+".join(held) if held else "-"


def build(root, screen):
    history: list[str] = []
    top = 8

    def record(text: str) -> None:
        history.append(text)
        del history[: max(0, len(history) - (screen.height - top - 1))]
        for offset in range(screen.height - top - 1):
            line = history[offset] if offset < len(history) else ""
            screen.line(top + offset, f"  {line}")
        screen.refresh()

    def fired(pattern: str):
        def handler(event):
            record(
                f"{pattern:<20} keysym={event.keysym!r:<12} "
                f"char={event.char!r:<6} modifiers={modifier_names(event.state)}"
            )

        return handler

    for pattern in PATTERNS:
        root.bind(pattern, fired(pattern))

    # A fixed strip rather than _support.content_area, whose height is a
    # fraction of the terminal: this one has to stay three rows whatever the
    # terminal does, so that the resize check has something of a known size
    # to look at.
    area = tkcurses.Frame(root, name="area")
    area.place(x=0, y=4, relwidth=1.0, height=3)

    def crash():
        raise RuntimeError("this button was supposed to fail")

    button = tkcurses.Button(area, text=" Raise an exception ", command=crash)
    button.pack(side="left")
    # Focus stays on the root so every key press goes through the bindings
    # above; the button is for the mouse. Tab would move the focus into it
    # and a Tab press is one of the things being watched.
    button.configure(takefocus=False)

    screen.lines(
        1,
        [
            "  Overlapping: " + "  ".join(PATTERNS[:4]),
            "  Named: " + "  ".join(PATTERNS[4:]),
        ],
    )
    screen.line(
        7,
        "  Click to raise, then resize hard.  Ctrl-C, Ctrl-\\ and Ctrl-Z are"
        " signals, not keys.",
    )
    record("press a key")


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
