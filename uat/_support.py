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

"""Shared scaffolding for the acceptance scenarios.

Two things every scenario needs: text on the screen saying what to do, and a
teardown that gives the terminal back whatever happens. Neither is interesting
enough to repeat nine times.

Instruction text is still written straight to the screen buffer, which is
internal API: a Label would need laying out, and the instructions have to stay
put while the scenario rearranges everything else around them. What the
scenarios *demonstrate* is built from real widgets.
"""

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, Any

import tkcurses

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

__all__ = ["Screen", "run"]


class Screen:
    """Somewhere to put text, until there are widgets that do it properly.

    It writes straight to the screen buffer, which curses draws UNDER no
    panel: a line written while a menu is open paints over the menu. A widget
    would not - its panel stacks - and a real program draws with widgets, so
    this is a limit of the readout, not of the library. A scenario should not
    update its readout while one of its menus is open. Found in UAT 46,
    where a shortcut that should not have fired did (TkCurses-aj1.13.1).
    """

    def __init__(self, root: tkcurses.Tk) -> None:
        self._root = root
        self._buffer = root.tk.screen.buffer
        #: Every line written, so a resize can put them back. A widget lays
        #: itself out again when the terminal changes size; text written
        #: straight to the buffer has nobody to do that for it, so the last
        #: thing written to each row is kept here and written again. The row
        #: is None for the footer, whose row depends on the height and so
        #: cannot be worked out until it is written.
        self._writes: list[tuple[int | None, int, str]] = []
        root.bind("<Configure>", self._resized, add="+")

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
        self._writes.clear()
        self._buffer.clear()

    def line(self, row: int, text: str, *, col: int = 0) -> None:
        """Write one line, padded so it overwrites whatever was there."""
        self._remember(row, col, text)
        self._write(row, col, text)

    def lines(self, row: int, texts: Sequence[str]) -> None:
        """Write several lines from ``row`` down."""
        for offset, text in enumerate(texts):
            self.line(row + offset, text)

    def footer(self, text: str) -> None:
        """Write the last line, where the instructions live."""
        self._remember(None, 0, text)
        self._write(self.height - 1, 0, text)

    def _remember(self, row: int | None, col: int, text: str) -> None:
        """Keep one write, in the order it was made, for a later replay.

        An earlier write to the same row is dropped rather than kept, so a
        scenario that rewrites a status line on every keypress does not
        accumulate a copy of each - and the survivor keeps its place in the
        order, which is what decides who wins where two writes overlap.
        """
        self._writes = [write for write in self._writes if write[0] != row]
        self._writes.append((row, col, text))

    def _write(self, row: int, col: int, text: str) -> None:
        """Put one line in the buffer, clipped and padded to the width."""
        if not 0 <= row < self.height or col >= self.width:
            return
        self._buffer.write(row, col, text.ljust(self.width - col)[: self.width - col])

    def _resized(self, event: Any = None) -> None:
        """Write the instruction text again for the size the terminal now is.

        Both halves matter. Text written when the terminal was narrow was
        clipped as it went in, so it has to be written again from the
        original string rather than left as the stub it became; and the
        footer belongs on the last row, which is not the row it was on.
        """
        self._buffer = self._root.tk.screen.buffer
        self._buffer.clear()
        for row, col, text in self._writes:
            self._write(self.height - 1 if row is None else row, col, text)
        self.refresh()

    def refresh(self) -> None:
        """Push everything written since the last call."""
        self._root.tk.screen.refresh()


def content_area(root: tkcurses.Tk, *, top: int = 3, bottom: int = 1):
    """A container filling the screen except the instruction lines.

    Scenarios lay out inside this rather than in the root, because a widget's
    panel is opaque and would otherwise cover the very text telling you what
    to look at.
    """
    area = tkcurses.Frame(root, name="area")
    area.place(x=0, y=top, relwidth=1.0, relheight=1.0, height=-(top + bottom))
    return area


def labelled_box(parent, letter: str, **options):
    """A bordered frame with its name in the corner.

    The frame is what the geometry managers arrange; the label inside names
    it. Both use pack, because a container may have only one manager and the
    scenarios nest further frames inside these.
    """
    options.setdefault("relief", "solid")
    frame = tkcurses.Frame(parent, **options)
    # Packed, not placed. A container may have only one geometry manager, so a
    # placed label would make the frame a place container and nothing could
    # ever be packed into it - which is what happened the first time, and is
    # why the nesting scenario silently refused to nest.
    tkcurses.Label(frame, text=letter, anchor="nw").pack(side="top", anchor="nw")
    # The label would otherwise shrink the frame to fit itself.
    frame.pack_propagate(False)
    return frame


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
