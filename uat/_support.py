"""Shared scaffolding for the acceptance scenarios.

Two things every scenario needs: text on the screen saying what to do, and a
teardown that gives the terminal back whatever happens. Neither is interesting
enough to repeat nine times.

The text is written straight to the screen buffer, which is internal API. That
is the honest position for now - there is no Label widget yet, so there is no
public way to put a character on the screen. When the widget set lands these
scenarios should be rewritten to use it, and doing so will exercise the real
thing rather than this.
"""

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, Any

import tkcurses

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

__all__ = ["Screen", "run"]


class Screen:
    """Somewhere to put text, until there are widgets that do it properly."""

    def __init__(self, root: tkcurses.Tk) -> None:
        self._root = root
        self._buffer = root.tk.screen.buffer

    @property
    def height(self) -> int:
        """Rows available."""
        return self._buffer.height

    @property
    def width(self) -> int:
        """Columns available."""
        return self._buffer.width

    def clear(self) -> None:
        """Blank the screen."""
        self._buffer.clear()

    def line(self, row: int, text: str, *, col: int = 0) -> None:
        """Write one line, padded so it overwrites whatever was there."""
        self._buffer.write(row, col, text.ljust(self.width - col)[: self.width - col])

    def lines(self, row: int, texts: Sequence[str]) -> None:
        """Write several lines from ``row`` down."""
        for offset, text in enumerate(texts):
            self.line(row + offset, text)

    def footer(self, text: str) -> None:
        """Write the last line, where the instructions live."""
        self.line(self.height - 1, text)

    def refresh(self) -> None:
        """Push everything written since the last call."""
        self._root.tk.screen.refresh()


def run(title: str, build: Callable[[tkcurses.Tk, Screen], Any]) -> int:
    """Run one scenario, and give the terminal back however it ends.

    Args:
        title: Shown on the first line.
        build: Sets the scenario up. Receives the root and a screen to write
            on; binding ``<Escape>`` to quit is done here so every scenario
            leaves the same way.

    Returns:
        0 if the scenario ran and exited normally, 1 if it raised. The exit
        code is what lets this be pointed at CI later, where nobody is
        watching the screen.

    SystemExit is left to propagate: a scenario that ends the application
    abruptly is testing exactly that, and catching it would turn the abrupt
    ending into an ordinary one. The terminal is still handed back, because
    that happens in the finally.
    """
    root = None
    try:
        root = tkcurses.Tk()
        root.title(title)
        screen = Screen(root)
        screen.line(0, f" {title} ")
        screen.footer(" Escape quits ")
        root.bind("<Escape>", lambda event: root.quit())
        build(root, screen)
        screen.refresh()
        root.mainloop()
    except KeyboardInterrupt:
        # Ctrl-C is one of the things being checked, not a failure.
        pass
    except Exception:
        if root is not None:
            root.destroy()
            root = None
        traceback.print_exc()
        return 1
    finally:
        if root is not None and root.winfo_exists():
            root.destroy()
    return 0
