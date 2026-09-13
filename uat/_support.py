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

import contextlib
import curses
import traceback
from typing import TYPE_CHECKING, Any

import tkcurses
from tkcurses._core.dispatcher import CursesDispatcher

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

    def outline(self, widget, label: str = "") -> None:
        """Draw a box around where a widget has been laid out.

        Drawn into the widget's *own* curses window rather than onto the
        screen behind it. A managed widget owns a panel, and that panel is
        opaque: anything drawn on the screen underneath is covered the moment
        the panels are pushed. Drawing here is also what Frame will do when it
        exists, so the scenario is a stand-in rather than a trick.
        """
        window = widget._window
        width, height = widget.winfo_width(), widget.winfo_height()
        if window is None or width <= 0 or height <= 0:
            return
        dispatcher = CursesDispatcher.get()
        with contextlib.suppress(curses.error):
            dispatcher.call(window.erase)
            if width >= 2 and height >= 2:
                dispatcher.call(window.border)
                if label:
                    dispatcher.call(window.addstr, 0, 1, label[: width - 2])
            else:
                for row in range(height):
                    dispatcher.call(window.addstr, row, 0, "\u2588" * (width - 1))

    def outline_all(self, widgets, labels: str = "ABCDEFGH") -> None:
        """Outline several widgets, lettering them in order."""
        for index, widget in enumerate(widgets):
            self.outline(widget, labels[index % len(labels)])

    def outline_on_redraw(self, widgets, labels: str = "ABCDEFGH") -> None:
        """Repaint each widget's outline whenever its window changes.

        A resize builds the widget a new curses window, so drawing once is not
        enough: anything painted into the old one goes with it. Hooking
        _redraw is what a real widget does, and what Frame will do.
        """
        for index, widget in enumerate(widgets):
            label = labels[index % len(labels)]
            widget._redraw = lambda widget=widget, label=label: self.outline(
                widget, label
            )
            widget._redraw()

    def refresh(self) -> None:
        """Push everything written since the last call."""
        self._root.tk.screen.refresh()


def content_area(root: tkcurses.Tk, *, top: int = 3, bottom: int = 1):
    """A container filling the screen except the instruction lines.

    Scenarios lay out inside this rather than in the root, because a managed
    widget's panel would otherwise cover the very text telling you what to
    look at.
    """
    area = tkcurses.Widget(root, name="area")
    area.place(x=0, y=top, relwidth=1.0, relheight=1.0, height=-(top + bottom))
    return area


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
