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

"""The classic Tk dialog: a message, a row of buttons, and which one was
pressed, as ``tkinter.dialog``.

Sample output:
    # size: 50x10
    from tkcurses import dialog
    dialog.Dialog(root, title="Quit", text="Quit without saving?",
                  bitmap="", default=1, strings=("Quit", "Cancel"))

Unlike the other dialogs, *making* a :class:`Dialog` shows it and waits,
and the answer is left on it as ``num``: the index in ``strings`` of the
button pressed, or -1 if the dialog was closed without one. ``default``
is the index of the button Return presses, and moving the focus to
another button moves Return with it; below zero, Return does nothing.

Differences from tkinter:
    ``bitmap`` is accepted and not drawn: a terminal has no stock icons.
"""
# The rules come from Tk's own dialog.tcl. destroy() does nothing, as in
# tkinter, because by the time anyone could call it the window is gone.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import tkcurses
from tkcurses.commondialog import Dialog as _Dialog

if TYPE_CHECKING:
    from tkcurses import Misc, Toplevel

__all__ = ["DIALOG_ICON", "Dialog"]

#: The icon tkinter's own example asks for. Kept so that code naming it still
#: imports; nothing draws it.
DIALOG_ICON = "questhead"

#: What a dialog returns when it was dismissed rather than answered. Tk's
#: value, from the <Destroy> binding in dialog.tcl.
DISMISSED = -1


class _ButtonRow(_Dialog):
    """The dialog itself, built on the common base."""

    def __init__(self, master: Misc | None, options: dict[str, Any]) -> None:
        super().__init__(master, **options)
        self.chosen = DISMISSED

    def body(self, window: Toplevel) -> Misc | None:
        text = str(self.options.get("text") or "")
        if text:
            # Wrapped, as dialog.tcl wraps it: "option add
            # *Dialog.msg.wrapLength 3i" on X11, which in Tk's default font
            # is about forty characters. A long message - a file's whole path
            # - was otherwise cut by the window. TkCurses-tyd9.
            tkcurses.Label(window, text=text, justify="left", wraplength=40).pack(
                padx=1, pady=1
            )
        row = tkcurses.Frame(window)
        row.pack(pady=1)
        default = _default_index(self.options.get("default"))
        buttons = []
        for index, label in enumerate(self.options.get("strings") or ()):
            button = tkcurses.Button(
                row, text=str(label), command=_chooser(self, index)
            )
            button.pack(side="left", padx=1)
            buttons.append(button)
        if 0 <= default < len(buttons):
            # Return presses whichever button has the focus, and the focus
            # starts on the default one - which is Tk's rule, and the reason
            # it rebinds Return as the focus moves rather than binding it
            # once to the default.
            return buttons[default]
        return None

    def finish(self, result: Any = None) -> None:
        """Record the index and close. Escape arrives here with None."""
        self.chosen = DISMISSED if result is None else int(result)
        super().finish(self.chosen)


def _chooser(dialog: _ButtonRow, index: int) -> Any:
    """A command that answers the dialog with one button's index."""
    return lambda: dialog.finish(index)


def _default_index(value: Any) -> int:
    """Tk's ``default``: an index, or below zero for no default at all.

    An empty string is how tkinter spells "none", and it reaches Tcl as a
    value that compares below zero there.
    """
    if value is None or value == "":
        return DISMISSED
    try:
        return int(value)
    except (TypeError, ValueError):
        return DISMISSED


class Dialog:
    """A message and a row of buttons, shown as soon as it is made.

    Attributes:
        num: The index of the button that was pressed, or -1 if the dialog
            was dismissed without one.

    Example:
        >>> answer = Dialog(root, {          # doctest: +SKIP
        ...     "title": "File Modified",
        ...     "text": 'Save "Python.h" before leaving?',
        ...     "bitmap": DIALOG_ICON,
        ...     "default": 0,
        ...     "strings": ("Save File", "Discard Changes", "Return to Editor"),
        ... }).num
    """

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: The widget the dialog belongs to.
            cnf: Options as a dictionary, merged with the keywords. tkinter's
                own example passes every option this way.
            **kw: ``title``, ``text``, ``bitmap``, ``default`` and
                ``strings``.

        Raises:
            TclError: If there is no master and no root window.
        """
        options = {**(cnf or {}), **kw}
        self.num: int = _ButtonRow(master, options).show()

    def destroy(self) -> None:
        """Do nothing. The window went when the dialog was answered."""
