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

import re
from dataclasses import dataclass, field
from typing import Any

from tkcurses._core.cells import cells

__all__ = [
    "MenuEntry",
    "Placed",
    "accelerator_sequence",
    "lay_out",
    "measure_entries",
    "place_popup",
    "visible_window",
]

#: Entry kinds, in the spelling Tk uses for ``type``.
KINDS = ("command", "cascade", "checkbutton", "radiobutton", "separator")

#: The entry a menu with ``tearoff`` starts with. Not one of :data:`KINDS`:
#: a program never adds one, the menu does.
TEAROFF = "tearoff"

#: Drawn to the right of an entry that opens a submenu.
CASCADE = "▸"

#: Cells between a label and an accelerator, so the two never touch.
GAP = 2

#: Cells between an entry's image and its label, beside each other - as a
#: Label leaves.
IMAGE_GAP = 1


@dataclass
class MenuEntry:
    """One line of a menu.

    Attributes:
        kind: One of :data:`KINDS`.
        options: Everything the entry was given, already checked.
    """

    kind: str
    options: dict[str, Any] = field(default_factory=dict)
    #: The size of the entry's image in cells, ``(width, height)``, or None
    #: for an entry with no image. Set by the menu, which knows the images,
    #: before it lays the entries out.
    picture: tuple[int, int] | None = None
    #: True for an entry that takes no room and cannot be chosen: the
    #: tear-off entry of a menu that has already been torn off, which Tk
    #: keeps at index 0 and does not draw.
    hidden: bool = False

    @property
    def compound(self) -> str:
        """Where the image goes against the label: ``-compound``."""
        return str(self.options.get("compound") or "none")

    @property
    def shows_label(self) -> bool:
        """False for an image that takes the label's place - ``compound``
        ``none`` - as in Tk; True for the rest."""
        return self.picture is None or (self.compound != "none" and bool(self.label))

    @property
    def content_width(self) -> int:
        """How wide the image and the label are together, in cells."""
        label = cells(self.label)
        if self.picture is None:
            return label
        width, _ = self.picture
        if not self.shows_label:
            return width
        if self.compound in ("left", "right"):
            return width + IMAGE_GAP + label
        return max(width, label)

    @property
    def height(self) -> int:
        """How many rows the entry takes: one, or its image's, and a row
        more for a label above or below it."""
        if self.hidden:
            return 0
        if self.picture is None:
            return 1
        _, height = self.picture
        if self.shows_label and self.compound in ("top", "bottom"):
            return height + 1
        return max(1, height)

    @property
    def label_row(self) -> int:
        """Which of the entry's rows its label, accelerator and indicator go
        on: under or over an image stacked with it, else the middle one."""
        if self.picture is not None and self.shows_label:
            if self.compound == "top":
                return self.height - 1
            if self.compound == "bottom":
                return 0
        return (self.height - 1) // 2

    @property
    def label(self) -> str:
        """The text on the left, empty for a separator."""
        if self.kind in ("separator", TEAROFF):
            return ""
        return str(self.options.get("label") or "")

    @property
    def accelerator(self) -> str:
        """The shortcut shown on the right, if any."""
        return str(self.options.get("accelerator") or "")

    @property
    def breaks_column(self) -> bool:
        """True if this entry starts a new column - ``-columnbreak``."""
        value = self.options.get("columnbreak", 0)
        return str(value).strip().lower() not in ("", "0", "false", "no", "off")

    @property
    def selectable(self) -> bool:
        """True if the active entry may rest here.

        A separator is a line, not a choice, and a disabled entry is not one
        either - so both are skipped rather than landed on, which is what
        stops an arrow key appearing to do nothing.
        """
        return (
            self.kind != "separator"
            and not self.hidden
            and str(self.options.get("state")) != "disabled"
        )


def measure_entries(entries: list[MenuEntry], *, indicators: bool) -> tuple[int, int]:
    """The size a menu's contents need, as ``(width, height)`` in cells.

    Args:
        entries: The entries, in order.
        indicators: Whether room is kept on the left for a tick or a bullet.
            Kept for every entry once any entry needs it, so the labels line
            up rather than stepping in and out.
    """
    labels = max((entry.content_width for entry in entries), default=0)
    accelerators = max((cells(entry.accelerator) for entry in entries), default=0)
    cascades = any(entry.kind == "cascade" for entry in entries)
    width = labels
    if indicators:
        width += 4
    if accelerators:
        width += GAP + accelerators
    if cascades:
        width += 2
    return (max(1, width), max(1, sum(entry.height for entry in entries)))


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


def visible_window(
    count: int, active: int, rows: int, heights: list[int] | None = None
) -> int:
    """The first entry to show, so that ``active`` is among ``rows`` rows.

    Scrolls the least it can: a menu already showing the active entry does
    not move, which is what stops the list jumping about under the arrow
    keys. ``heights`` gives each entry's rows when they are not all one; an
    active entry taller than the window starts it.
    """
    sizes = heights if heights is not None else [1] * count
    if rows <= 0 or sum(sizes) <= rows or not sizes:
        return 0
    active = max(0, min(active, len(sizes) - 1))
    first, used = active, sizes[active]
    while first > 0 and used + sizes[first - 1] <= rows:
        first -= 1
        used += sizes[first]
    # Never past the first entry from which the rest fill the window.
    last_first, tail = len(sizes), 0
    while last_first > 0 and tail + sizes[last_first - 1] <= rows:
        last_first -= 1
        tail += sizes[last_first]
    return max(0, min(first, last_first))


#: Cells between one column of a menu and the next.
COLUMN_GAP = 2


@dataclass(frozen=True)
class Placed:
    """Where one entry of a posted menu goes, relative to its text area."""

    #: The column's left edge.
    x: int
    #: The row within the column.
    row: int
    #: The column's width, which the entry is drawn across.
    width: int
    #: How many rows the entry takes.
    height: int = 1


def lay_out(
    entries: list[MenuEntry], *, indicators: bool
) -> tuple[list[Placed], tuple[int, int]]:
    """Place a posted menu's entries in columns, as ``-columnbreak`` asks.

    An entry with ``-columnbreak`` starts a new column at the top; the rest
    go below the one before. Measured on Tk 9.0.2 with ``xposition`` and
    ``yposition``: each column is as wide as ITS OWN labels and accelerators
    need - a column of short entries stays narrow beside a wide one - and the
    menu is as tall as its tallest column. A break on the first entry starts
    nothing, there being no column before it. TkCurses-aj1.13.1.

    Returns each entry's place, in order, and the size of the whole.
    """
    columns: list[list[int]] = [[]]
    for number, entry in enumerate(entries):
        if entry.breaks_column and columns[-1]:
            columns.append([])
        columns[-1].append(number)
    placed: dict[int, Placed] = {}
    x = 0
    for column in columns:
        width, _ = measure_entries(
            [entries[number] for number in column], indicators=indicators
        )
        row = 0
        for number in column:
            tall = entries[number].height
            placed[number] = Placed(x, row, width, tall)
            row += tall
        x += width + COLUMN_GAP
    total_width = max(1, x - COLUMN_GAP)
    height = max(
        1,
        max(
            (sum(entries[number].height for number in column) for column in columns),
            default=1,
        ),
    )
    return [placed[number] for number in range(len(entries))], (total_width, height)


# ---------------------------------------------------------- accelerators
#
# An entry's -accelerator is display only, in Tk as here: its manual says it
# "does not actually set the corresponding binding (which can be achieved
# using the bind command)". So every application writes the shortcut twice,
# once as text and once as a binding, and the two drift. accelerator_sequence
# reads the text the way people write it, so Menu.bind_accelerators can make
# the binding from it - a TkCurses addition, not tkinter API. aj1.13.1.

#: Modifier spellings, lower-cased, to the name a binding sequence uses.
_ACCELERATOR_MODIFIERS = {
    "ctrl": "Control",
    "control": "Control",
    "ctl": "Control",
    "alt": "Alt",
    "option": "Alt",
    "opt": "Alt",
    "meta": "Meta",
    "shift": "Shift",
}

#: Key spellings, lower-cased, to the keysym a binding names.
_ACCELERATOR_KEYS = {
    "del": "Delete",
    "delete": "Delete",
    "ins": "Insert",
    "insert": "Insert",
    "home": "Home",
    "end": "End",
    "pgup": "Prior",
    "pageup": "Prior",
    "prior": "Prior",
    "pgdn": "Next",
    "pgdown": "Next",
    "pagedown": "Next",
    "next": "Next",
    "esc": "Escape",
    "escape": "Escape",
    "enter": "Return",
    "return": "Return",
    "tab": "Tab",
    "space": "space",
    "spacebar": "space",
    "backspace": "BackSpace",
    "bksp": "BackSpace",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "plus": "plus",
    "minus": "minus",
    "comma": "comma",
    "period": "period",
    "dot": "period",
    "slash": "slash",
}

#: A punctuation key written as itself, to its keysym name - kept as a name,
#: so a "<" or ">" never sits inside the brackets of a sequence.
_ACCELERATOR_PUNCTUATION = {
    "+": "plus",
    "-": "minus",
    ",": "comma",
    ".": "period",
    "/": "slash",
    ";": "semicolon",
    "=": "equal",
    "[": "bracketleft",
    "]": "bracketright",
    "<": "less",
    ">": "greater",
    "'": "apostrophe",
    "`": "grave",
    "\\": "backslash",
}

_FUNCTION_KEY = re.compile(r"^f([1-9]|1[0-9]|2[0-4])$")


def accelerator_sequence(text: str) -> str:
    """The binding sequence an accelerator's text describes.

    ``Ctrl+O`` gives ``<Control-Key-o>``. Modifiers are ``Ctrl``, ``Control``
    or a leading ``^``, ``Alt`` or ``Option``, ``Meta`` and ``Shift``, joined
    by ``+`` or ``-``; keys are a character, ``F1`` to ``F24``, or a name -
    ``Del``, ``Ins``, ``Home``, ``End``, ``PgUp``, ``PgDn``, ``Esc``,
    ``Enter``, ``Tab``, ``Space``, ``Backspace``, the arrows. A chord is
    written with a space or a comma between its keys: ``Ctrl+X Ctrl+S``.

    A letter is the key, not the character: ``Ctrl+O`` means the o key with
    Control held, as menus write it, and ``Shift+O`` the O. A terminal sends
    Ctrl+Shift+O as it sends Ctrl+O, so that one can be bound but never told
    apart here.

    Raises:
        ValueError: For text it cannot read - better than a shortcut shown on
            screen that nothing binds.
    """
    # A comma between keys has a space after it ("Ctrl+K, Ctrl+C"); one with
    # none is the comma key ("Ctrl+,").
    keys = [part for part in re.split(r",\s+|\s+", text.strip()) if part]
    if not keys:
        raise ValueError(f"no key in accelerator {text!r}")
    return "".join(_one_key(key, text) for key in keys)


def _one_key(key: str, text: str) -> str:
    modifiers: list[str] = []
    rest = key
    if rest.startswith("^") and len(rest) > 1:
        modifiers.append("Control")
        rest = rest[1:]
    while True:
        match = re.match(r"^([A-Za-z]+)[+-](?=.)", rest)
        if match is None or match.group(1).lower() not in _ACCELERATOR_MODIFIERS:
            break
        name = _ACCELERATOR_MODIFIERS[match.group(1).lower()]
        if name not in modifiers:
            modifiers.append(name)
        rest = rest[match.end() :]
    keysym = _keysym(rest, shifted="Shift" in modifiers)
    if keysym is None:
        raise ValueError(f"cannot read the key {rest!r} in accelerator {text!r}")
    return "<" + "".join(f"{name}-" for name in modifiers) + f"Key-{keysym}>"


def _keysym(key: str, *, shifted: bool) -> str | None:
    if len(key) == 1:
        if key.isalpha():
            return key.upper() if shifted else key.lower()
        if key.isdigit():
            return key
        return _ACCELERATOR_PUNCTUATION.get(key)
    lowered = key.lower()
    if _FUNCTION_KEY.match(lowered):
        return lowered.upper()
    return _ACCELERATOR_KEYS.get(lowered)
