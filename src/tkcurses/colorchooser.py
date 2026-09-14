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

"""Choosing a colour, from the ones a terminal actually has.

tkinter's chooser is the platform's, and the platform offers a mixer: three
sliders, sixteen million colours, a magnifier. A terminal has sixteen - eight
and their bright forms - so a mixer here would be a lie told in three
dimensions. What this shows instead is the sixteen, drawn in themselves, and
a box for typing any colour name or ``#rrggbb`` at all.

Anything typed is accepted, and a *name* is then resolved to what the
terminal will really show: ``red`` comes back as ``#cd0000`` rather than
``#ff0000``, because that is the red anything drawn in it will be. This is
``winfo_rgb``'s own behaviour and the reason is the same - reporting the
request back would hide the approximation until somebody wondered why their
orange looked like mustard. A colour given as ``#rrggbb`` is its own answer,
as it is there: the caller has already said exactly what it meant, and the
approximation happens when it is drawn rather than when it is named.

The return value is tkinter's, and it is a pair::

    rgb, name = askcolor()

``((r, g, b), "#rrggbb")`` when something was chosen, and ``(None, None)``
when the dialog was cancelled - not None, which is what callers unpacking two
values would trip over.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import tkcurses
from tkcurses._core.colors import _PALETTE_RGB
from tkcurses.commondialog import Dialog

if TYPE_CHECKING:
    from tkcurses import Misc, Toplevel

__all__ = ["Chooser", "askcolor"]


def _hex(rgb: tuple[int, int, int]) -> str:
    """One RGB triplet as the ``#rrggbb`` tkinter speaks."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


#: The colours a terminal has, as ``#rrggbb``. Taken from the palette the
#: renderer approximates against, so the swatches cannot drift away from what
#: is really available.
PALETTE: tuple[str, ...] = tuple(_hex(rgb) for rgb, _ in _PALETTE_RGB)

#: Swatches per row. Eight, so the base colours line up above their bright
#: forms and the pair can be compared.
COLUMNS = 8

#: What a swatch is drawn with. Three cells of solid colour, wide enough to
#: tell one from another and narrow enough that sixteen fit a small terminal.
SWATCH = "   "


class Chooser(Dialog):
    """The colour chooser. tkinter's ``tk_chooseColor``, drawn from widgets."""

    command: ClassVar[str | None] = "tk_chooseColor"

    def _fixoptions(self) -> None:
        """Turn an RGB triplet ``initialcolor`` into a colour string."""
        color = self.options.get("initialcolor")
        if isinstance(color, tuple):
            self.options["initialcolor"] = _hex(color)

    def _fixresult(self, widget: Misc, result: Any) -> Any:
        """Report the colour chosen, and the one the terminal will show.

        Returns:
            ``((r, g, b), "#rrggbb")``, or ``(None, None)`` if cancelled.
        """
        if not result or not str(result):
            return None, None
        red, green, blue = widget.winfo_rgb(str(result))
        rgb = (red // 256, green // 256, blue // 256)
        return rgb, _hex(rgb)

    def body(self, window: Toplevel) -> Misc | None:
        initial = str(self.options.get("initialcolor") or "")

        swatches = tkcurses.Frame(window)
        swatches.pack(padx=1, pady=1)
        for index, color in enumerate(PALETTE):
            # No border: a bordered swatch is three rows tall for one row
            # of colour, and sixteen of those do not fit a small terminal
            # alongside the box and the buttons. Blocks of colour side by
            # side read better anyway.
            swatch = tkcurses.Label(swatches, text=SWATCH, background=color)
            swatch.grid(row=index // COLUMNS, column=index % COLUMNS)
            swatch.bind("<Button-1>", _picker(self, color))

        tkcurses.Label(window, text="or type a colour:").pack()
        self.entry = tkcurses.Entry(window, name="color")
        self.entry.pack(padx=1, fill="x")
        if initial:
            self.entry.insert(0, initial)
        self.entry.bind("<Return>", lambda event: self.ok())  # noqa: ARG005

        buttons = tkcurses.Frame(window)
        buttons.pack(pady=1)
        tkcurses.Button(buttons, text="OK", command=self.ok).pack(side="left", padx=1)
        tkcurses.Button(buttons, text="Cancel", command=lambda: self.finish(None)).pack(
            side="left", padx=1
        )
        return self.entry

    def ok(self) -> None:
        """Answer with whatever the box holds, if it is a colour at all."""
        text = self.entry.get().strip()
        if not text:
            return
        try:
            self.entry.winfo_rgb(text)
        except (tkcurses.TclError, ValueError):
            # An unknown name raises ValueError rather than TclError, and a
            # dialog that let it out would take the application down for a
            # typo in a text box.
            return
        self.finish(text)


def _picker(chooser: Chooser, color: str) -> Any:
    """A handler that answers the chooser with one swatch's colour."""

    def handler(event: Any) -> None:  # noqa: ARG001
        chooser.finish(color)

    return handler


def askcolor(
    color: str | tuple[int, int, int] | None = None, **options: Any
) -> tuple[tuple[int, int, int] | None, str | None]:
    """Ask for a colour.

    Args:
        color: What to start on, as a name, ``#rrggbb`` or an RGB triplet.
        **options: ``parent`` and ``title``, as the other dialogs take.

    Returns:
        ``((r, g, b), "#rrggbb")``, or ``(None, None)`` if cancelled.
    """
    if color:
        options = options.copy()
        options["initialcolor"] = color
    chosen: tuple[tuple[int, int, int] | None, str | None] = Chooser(**options).show()
    return chosen
