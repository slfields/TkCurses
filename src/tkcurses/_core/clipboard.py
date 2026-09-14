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

"""Clipboard and selection storage.

X11 has several selections — ``PRIMARY`` for the mouse, ``CLIPBOARD`` for
explicit copy and paste — and tkinter exposes both: ``clipboard_*`` works on
one, ``selection_*`` on the other. A terminal has neither, so both are kept
here as ordinary strings in the process.

That means a copy is not visible to other programs, which is a real
limitation rather than a stub: the surrounding API behaves exactly as tkinter
does, but the data does not leave the application. Escape-sequence clipboard
access (OSC 52) would lift that, and is deliberately not attempted here
because it is not supported by every terminal and fails silently on the rest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tkcurses._core.errors import TclError

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["CLIPBOARD", "PRIMARY", "Selections"]

#: The selection ``clipboard_*`` works on.
CLIPBOARD = "CLIPBOARD"

#: The selection ``selection_*`` works on by default, as in tkinter.
PRIMARY = "PRIMARY"


class Selections:
    """Named selections and their owners.

    A selection is absent until something is put in it, which is the state
    tkinter reports by raising rather than returning an empty string: the
    caller needs to tell "nothing has been copied" apart from "an empty string
    was copied".
    """

    def __init__(self) -> None:
        self._content: dict[str, str] = {}
        self._owners: dict[str, Any] = {}
        self._handlers: dict[tuple[str, Any], Callable[..., str]] = {}

    # ------------------------------------------------------------- contents

    def get(self, selection: str = PRIMARY) -> str:
        """Return the contents of ``selection``.

        Raises:
            TclError: If nothing owns the selection, as tkinter does.
        """
        try:
            return self._content[selection]
        except KeyError:
            raise TclError(
                f"{selection} selection doesn't exist or form unknown"
            ) from None

    def set(self, text: str, selection: str = CLIPBOARD) -> None:
        """Replace the contents of ``selection``."""
        self._content[selection] = text

    def append(self, text: str, selection: str = CLIPBOARD) -> None:
        """Add to ``selection``, starting it if it is empty.

        tkinter's ``clipboard_append`` also implicitly claims the selection,
        which is why a bare append works without a preceding clear.
        """
        self._content[selection] = self._content.get(selection, "") + text

    def clear(self, selection: str = CLIPBOARD) -> None:
        """Discard the contents of ``selection``.

        Clearing something already empty is not an error: tkinter code
        routinely calls ``clipboard_clear()`` before every append.
        """
        self._content.pop(selection, None)

    def __contains__(self, selection: object) -> bool:
        """True if ``selection`` currently holds anything."""
        return selection in self._content

    # --------------------------------------------------------------- owners

    def own(self, owner: Any, selection: str = PRIMARY) -> None:
        """Record ``owner`` as holding ``selection``."""
        self._owners[selection] = owner

    def owner(self, selection: str = PRIMARY) -> Any:
        """The widget that claimed ``selection``, or None."""
        return self._owners.get(selection)

    def disown(self, owner: Any) -> None:
        """Release everything ``owner`` holds, as when a widget is destroyed."""
        for selection, current in list(self._owners.items()):
            if current is owner:
                del self._owners[selection]
        for key in [key for key in self._handlers if key[1] is owner]:
            del self._handlers[key]

    # ------------------------------------------------------------- handlers

    def handle(
        self, owner: Any, command: Callable[..., str], selection: str = PRIMARY
    ) -> None:
        """Register ``command`` to supply ``selection`` on demand.

        X11 asks the owner for the data at the moment it is pasted rather than
        copying it up front, and tkinter exposes that as ``selection_handle``.
        Here the handler is consulted by :meth:`resolve`, so a widget can hand
        over text it would rather not keep duplicated.
        """
        self._handlers[(selection, owner)] = command

    def resolve(self, selection: str = PRIMARY) -> str:
        """Contents of ``selection``, asking its owner's handler first.

        Raises:
            TclError: If no handler and no stored contents can supply it.
        """
        owner = self._owners.get(selection)
        handler = self._handlers.get((selection, owner))
        if handler is not None:
            return handler(0, -1)
        return self.get(selection)
