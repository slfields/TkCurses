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
#
# Portions follow logic in the Tcl and Tk library scripts, each named beside
# the code that follows it. Tcl and Tk are copyright the Regents of the
# University of California, Sun Microsystems, Inc., Scriptics Corporation,
# ActiveState Corporation, Apple Inc. and other parties, and are used under
# the Tcl/Tk licence; see THIRD_PARTY_NOTICES.md.

"""Choosing a colour, as ``tkinter.colorchooser``.

Sample output:
    # size: 60x20
    from tkcurses import colorchooser
    colorchooser.askcolor("#3366cc", title="Highlight colour")

:func:`askcolor` answers a pair, ``((r, g, b), "#rrggbb")``, or
``(None, None)`` if cancelled - so ``rgb, name = askcolor()`` works
either way.

The dialog is laid out as Tk's: a bar for each of red, green and blue,
an entry beside each taking 0 to 255, a ``Selection:`` entry holding the
colour as ``#rrggbb`` or a name, a swatch of the result, and OK and
Cancel.

Differences from tkinter:
    Each bar shows its own channel alone, from none to full, and does
    not change. Tk's bars show the colour as their channel varies with
    the other two held, which on a terminal with few colours can make a
    whole bar one colour.

    A bar has as many steps as the terminal can tell apart - two with
    eight colours, six with 256, sixteen with direct colour - where Tk
    draws sixteen. Any value can still be typed.
"""
# Read out of Tk's own clrpick.tcl. There is no colour-name lookup in it
# beyond what winfo_rgb does, as in Tk. The fixed scales were measured against
# Tk 9.0.2, where raising green from 0 to 255 turned the red strip from a
# black-to-red ramp into a green-to-yellow one; here, with the other channels
# at mid intensity, the red bar collapsed to one colour at eight and sixteen
# colours.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import tkcurses
from tkcurses._core.colors import CUBE_LEVELS, ColorDepth
from tkcurses.commondialog import Dialog

if TYPE_CHECKING:
    from tkcurses import Entry, Frame, Label, Misc, Toplevel

__all__ = ["Chooser", "askcolor"]

#: The three channels, in Tk's order.
CHANNELS: tuple[str, ...] = ("Red", "Green", "Blue")

#: The intensities a bar offers at each depth. Every one of them has to be a
#: colour the terminal can tell from the one beside it, so the levels are the
#: palette's own wherever the palette has any: the 256-colour cube really is
#: six levels per channel, and eight colours really is off and on.
#:
#: Direct colour is the only tier that can show a smooth ramp, and there the
#: count is Tk's sixteen. The levels are not quite Tk's: it steps by 16 from
#: zero and so stops at 240, which means pure white cannot be reached from
#: the bars at all. These reach it.
#:
#: The sixteen-colour tier has one gap, and it is the palette's rather than
#: this table's: its blue is #0000ee and its bright blue is #5c5cff, so pure
#: blue at any intensity lands on the first and never reaches the second.
#: The blue bar there shows two appearances for its three steps. Red and
#: green have no such gap, and every value is still reachable by typing it.
BAR_LEVELS: dict[ColorDepth, tuple[int, ...]] = {
    ColorDepth.NONE: (0, 255),
    ColorDepth.BASIC: (0, 255),
    ColorDepth.BRIGHT: (0, 128, 255),
    ColorDepth.EXTENDED: CUBE_LEVELS,
    ColorDepth.DIRECT: tuple(round(step * 255 / 15) for step in range(16)),
}

#: How wide each channel's numeric entry is. Four, which holds "255".
CHANNEL_WIDTH = 4

#: Roughly how wide a bar should be, in cells. The cells per step divide into
#: it, so a bar with few steps has fat ones rather than a short bar.
BAR_WIDTH = 18

#: What marks the step a channel is on, drawn beneath the bar the way Tk
#: draws its selector polygon beneath the color strip.
MARKER = "▲"

#: The panel showing the colour chosen, in cells. Tk's is a 100x68 pixel
#: frame, which is a block rather than a line - the point of it is to be big
#: enough to judge a colour by, so this is a block too.
PANEL_WIDTH = 9
PANEL_HEIGHT = 3


def _hex(rgb: tuple[int, int, int]) -> str:
    """One RGB triplet as the ``#rrggbb`` tkinter speaks."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _nearest_step(levels: tuple[int, ...], value: int) -> int:
    """Which step of a bar an arbitrary intensity sits closest to."""
    return min(range(len(levels)), key=lambda index: abs(levels[index] - value))


class Chooser(Dialog):
    """The colour dialog behind :func:`askcolor`.

    ``Chooser(color=..., title=...).show()`` answers the same pair.
    """

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

    # ------------------------------------------------------------- building

    def body(self, window: Toplevel) -> Misc | None:
        """Fill the dialog in: the bars, entries, swatch and buttons.

        TkCurses extension:
            tkinter's colour dialog is the platform's; this is how the one here
            is built. See :meth:`tkcurses.commondialog.Dialog.body`.
        """
        self.levels = BAR_LEVELS[window.winfo_colordepth()]
        self.cells = max(1, BAR_WIDTH // len(self.levels))
        self._bar_cells = self.cells * len(self.levels)
        self.rgb = self._initial(window)
        self._steps: dict[str, list[Label]] = {}
        self._markers: dict[str, Label] = {}
        self._entries: dict[str, Entry] = {}

        top = tkcurses.Frame(window, name="top")
        top.pack(padx=1, pady=1)

        strips = tkcurses.Frame(top, name="strips")
        strips.pack(side="left", anchor="n")
        for row, channel in enumerate(CHANNELS):
            self._build_channel(strips, row, channel)

        self._build_selection(top)

        buttons = tkcurses.Frame(window, name="buttons")
        buttons.pack(pady=1)
        tkcurses.Button(buttons, text="OK", command=self.ok).pack(side="left", padx=1)
        tkcurses.Button(buttons, text="Cancel", command=lambda: self.finish(None)).pack(
            side="left", padx=1
        )

        self._refresh()
        return self.entry

    def _build_selection(self, top: Frame) -> None:
        """The Selection entry, and the panel showing what it comes to.

        Tk's shape: a column beside the bars, holding the entry above a panel
        painted in the colour itself. The panel is what answers "what have I
        actually chosen" - a question three numbers do not answer, and one a
        person can only settle by looking at a block of the colour.
        """
        chosen = tkcurses.Frame(top, name="chosen")
        chosen.pack(side="left", padx=2, anchor="n")
        tkcurses.Label(chosen, text="Selection:", anchor="w").pack(fill="x")
        self.entry = tkcurses.Entry(
            chosen, name="selection", width=PANEL_WIDTH, relief="flat"
        )
        self.entry.pack()
        self.entry.bind("<Return>", self._on_selection)
        # Bordered, as Tk's sunken frame round its panel is: without an edge
        # a pale colour and the dialog behind it run into one another and the
        # panel stops looking like a thing.
        panel = tkcurses.Frame(chosen, name="panel", relief="solid", borderwidth=1)
        panel.pack()
        self._panel = [
            tkcurses.Label(panel, text=" " * PANEL_WIDTH) for _ in range(PANEL_HEIGHT)
        ]
        for band in self._panel:
            band.pack()

    def _initial(self, window: Misc) -> list[int]:
        """The colour to start on, as three channels.

        An ``initialcolor`` the terminal cannot show is reported as the colour
        it will be drawn in, since that is the colour the swatch beside it is
        about to be.
        """
        wanted = str(self.options.get("initialcolor") or "")
        if not wanted:
            return [0, 0, 0]
        try:
            channels = window.winfo_rgb(wanted)
        except (tkcurses.TclError, ValueError):
            return [0, 0, 0]
        return [value // 256 for value in channels]

    def _build_channel(self, strips: Frame, row: int, channel: str) -> None:
        """One label, one entry, one bar and the marker beneath it."""
        tkcurses.Label(strips, text=f"{channel}:", width=7, anchor="e").grid(
            row=row * 2, column=0
        )
        # Flat, because a bordered entry is three rows tall for one row of
        # text and three of those plus the bars do not fit a small
        # terminal. The bar beside it has to line up with its text, too.
        entry = tkcurses.Entry(
            strips, name=channel.lower(), width=CHANNEL_WIDTH, relief="flat"
        )
        entry.grid(row=row * 2, column=1)
        entry.bind("<Return>", self._on_channel(channel))
        self._entries[channel] = entry

        bar = tkcurses.Frame(strips, name=f"{channel.lower()}bar")
        bar.grid(row=row * 2, column=2)
        steps = []
        position = CHANNELS.index(channel)
        for level in self.levels:
            # This channel alone, from nothing to full. Painted here and
            # never again: the scale does not depend on where the other two
            # channels are, which is what keeps it a scale.
            shown = [0, 0, 0]
            shown[position] = level
            step = tkcurses.Label(
                bar,
                text=" " * self.cells,
                background=_hex((shown[0], shown[1], shown[2])),
            )
            step.pack(side="left")
            # Press and drag both ask the bar where the pointer is, in screen
            # columns, rather than which step was hit: the press holds the
            # implicit grab, so a drag reports its position relative to the
            # step it started on and not the one it is over.
            step.bind("<Button-1>", self._on_bar(channel, bar))
            step.bind("<B1-Motion>", self._on_bar(channel, bar))
            steps.append(step)
        self._steps[channel] = steps
        self._markers[channel] = tkcurses.Label(
            strips, text=" " * self._bar_cells, anchor="w"
        )
        self._markers[channel].grid(row=row * 2 + 1, column=2, sticky="w")

    # -------------------------------------------------------------- painting

    def _refresh(self) -> None:
        """Move the markers, and put the colour in the entries and the panel.

        The bars themselves are not touched. They were painted when they were
        built and mean the same thing however the colour moves - see the
        module docstring for why that departs from Tk.
        """
        for position, channel in enumerate(CHANNELS):
            value = self.rgb[position]
            selected = _nearest_step(self.levels, value)
            # Padded out to the bar's full width: a label that shrank to its
            # text would be centred in the grid cell by the width it lost,
            # and the marker would drift away from the step it points at.
            marker = " " * (selected * self.cells + self.cells // 2) + MARKER
            self._markers[channel].configure(text=marker.ljust(self._bar_cells))
            self._set(self._entries[channel], str(value))
        self._set(self.entry, self.color)
        for band in self._panel:
            band.configure(background=self.color)

    @staticmethod
    def _set(entry: Entry, text: str) -> None:
        """Replace an entry's contents without disturbing anything else."""
        entry.delete(0, "end")
        entry.insert(0, text)

    @property
    def color(self) -> str:
        """The colour chosen so far, as ``#rrggbb``.

        TkCurses extension:
            tkinter's dialog does not expose it.
        """
        return _hex((self.rgb[0], self.rgb[1], self.rgb[2]))

    # -------------------------------------------------------------- handlers

    def _on_bar(self, channel: str, bar: Frame) -> Any:
        """A handler setting this channel from where the pointer is."""

        def handler(event: Any) -> str:
            offset = event.x_root - bar.winfo_rootx()
            index = min(max(offset // self.cells, 0), len(self.levels) - 1)
            self.set_channel(channel, self.levels[index])
            return "break"

        return handler

    def _on_channel(self, channel: str) -> Any:
        """A handler applying whatever was typed into one channel's entry."""

        def handler(event: Any) -> str:  # noqa: ARG001
            text = self._entries[channel].get().strip()
            try:
                value = int(float(text))
            except ValueError:
                # Tk's rule for an entry that will not read as a number: put
                # it back to zero rather than refusing or complaining.
                value = 0
            self.set_channel(channel, value)
            return "break"

        return handler

    def _on_selection(self, event: Any) -> str:  # noqa: ARG002
        """Apply whatever the Selection entry holds, if it is a colour."""
        if not self._apply_selection():
            # Tk puts the old colour back rather than leaving a bad value
            # where it looks as though it was accepted.
            self._set(self.entry, self.color)
        return "break"

    def _apply_selection(self) -> bool:
        """Take the Selection entry's text as the colour. True if it was one.

        Anything ``winfo_rgb`` understands is accepted, names included -
        which is Tk's behaviour, since Tk hands the text to ``winfo_rgb``
        too. What Tk has not got, and this has not either, is a list of
        names to pick from.
        """
        text = self.entry.get().strip()
        if not text:
            return False
        try:
            channels = self.entry.winfo_rgb(text)
        except (tkcurses.TclError, ValueError):
            # An unknown name raises ValueError rather than TclError, and a
            # dialog that let it out would take the application down for a
            # typo in a text box.
            return False
        self.rgb = [value // 256 for value in channels]
        self._refresh()
        return True

    def set_channel(self, channel: str, value: int) -> None:
        """Set one channel and redraw the dialog.

        Args:
            channel: ``"Red"``, ``"Green"`` or ``"Blue"``.
            value: The intensity; outside 0 to 255 it is brought within, as Tk
                does.

        TkCurses extension:
            tkinter's dialog does not expose it.
        """
        self.rgb[CHANNELS.index(channel)] = min(max(value, 0), 255)
        self._refresh()

    def ok(self) -> None:
        """Answer with the colour shown, applying anything typed in the
        ``Selection:`` entry first.

        TkCurses extension:
            How the dialog here answers.

        Differences from tkinter:
            Tk answers with the last colour applied, so a colour typed and then
            OK gets the one before it.
        """
        self._apply_selection()
        self.finish(self.color)


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
