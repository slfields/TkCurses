"""A root window that opens and closes cleanly.

What to do: watch the screen come up, then press Escape.
What to look for: the terminal clears, the title line is readable, and after
Escape your shell prompt is back with the cursor visible and typing works.
"""

from __future__ import annotations

from uat import _support

TITLE = "01 - root window"


def build(root, screen):
    screen.lines(
        2,
        [
            "The screen below this line is the root window.",
            "",
            "It should fill the terminal, and leave no stray output behind",
            "when it closes. After Escape, check that:",
            "",
            "  * your prompt is back",
            "  * the cursor is visible again",
            "  * what you type appears",
        ],
    )


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
