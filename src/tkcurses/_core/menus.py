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

"""Where a posted menu goes, and how much of it fits.

A menu is the one thing in a terminal application that has to be placed
against the *screen* rather than inside its parent: it is posted at a point,
and where it ends up depends on how much room there is below and to the right
of that point. Two cases decide everything, and both are easy to get wrong:

**A menu near an edge** must move rather than be cut off. Tk flips a dropdown
above its point when there is no room below, and pulls it left when it would
run off the right. A menu clipped at the screen edge is a menu whose last
entries cannot be read or reached.

**A menu taller than the screen** cannot be moved anywhere that helps, so it
scrolls: a window of entries follows the active one. That window is the one
piece of state a menu keeps about its own display, and working it out here
means it can be exercised without posting anything.

None of this touches curses, so the awkward sizes - a menu exactly as tall as
the screen, a point already off it, a screen too small for even one entry -
can be tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["MenuEntry", "measure_entries", "place_popup", "visible_window"]

#: Entry kinds, in the spelling Tk uses for ``type``.
KINDS = ("command", "cascade", "checkbutton", "radiobutton", "separator")

#: Drawn to the right of an entry that opens a submenu.
CASCADE = "▸"

#: Cells between a label and an accelerator, so the two never touch.
GAP = 2


@dataclass
class MenuEntry:
    """One line of a menu.

    Attributes:
        kind: One of :data:`KINDS`.
        options: Everything the entry was given, already checked.
    """

    kind: str
    options: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        """The text on the left, empty for a separator."""
        return "" if self.kind == "separator" else str(self.options.get("label") or "")

    @property
    def accelerator(self) -> str:
        """The shortcut shown on the right, if any."""
        return str(self.options.get("accelerator") or "")

    @property
    def selectable(self) -> bool:
        """True if the active entry may rest here.

        A separator is a line, not a choice, and a disabled entry is not one
        either - so both are skipped rather than landed on, which is what
        stops an arrow key appearing to do nothing.
        """
        return self.kind != "separator" and str(self.options.get("state")) != "disabled"


def measure_entries(entries: list[MenuEntry], *, indicators: bool) -> tuple[int, int]:
    """The size a menu's contents need, as ``(width, height)`` in cells.

    Args:
        entries: The entries, in order.
        indicators: Whether room is kept on the left for a tick or a bullet.
            Kept for every entry once any entry needs it, so the labels line
            up rather than stepping in and out.
    """
    labels = max((len(entry.label) for entry in entries), default=0)
    accelerators = max((len(entry.accelerator) for entry in entries), default=0)
    cascades = any(entry.kind == "cascade" for entry in entries)
    width = labels
    if indicators:
        width += 4
    if accelerators:
        width += GAP + accelerators
    if cascades:
        width += 2
    return (max(1, width), max(1, len(entries)))


def place_popup(
    x: int,
    y: int,
    width: int,
    height: int,
    screen_width: int,
    screen_height: int,
) -> tuple[int, int, int]:
    """Where a menu of a given size goes when posted at a point.

    Returns ``(x, y, height)``. The height comes back reduced when the menu
    is taller than the screen, which is the caller's signal that it will have
    to scroll.

    Flipped rather than clipped: a menu with no room below its point is
    drawn above it instead, and one that would run off the right is pulled
    left until it fits. Only when neither side has room is it clamped, which
    is the case where the menu is simply wider or taller than the screen.
    """
    if y + height > screen_height and y - height >= 0:
        y -= height
    if x + width > screen_width and x - width >= 0:
        x -= width
    height = min(height, screen_height)
    width = min(width, screen_width)
    x = max(0, min(x, screen_width - width))
    y = max(0, min(y, screen_height - height))
    return (x, y, height)


def visible_window(count: int, active: int, rows: int) -> int:
    """The first entry to show, so that ``active`` is among ``rows`` of them.

    Scrolls the least it can: a menu already showing the active entry does
    not move, which is what stops the list jumping about under the arrow
    keys.
    """
    if rows <= 0 or count <= rows:
        return 0
    first = min(max(0, active - rows + 1), count - rows)
    return max(0, min(first, count - rows))
