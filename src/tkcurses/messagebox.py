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

"""Message boxes: tell somebody something, or ask a short question, as
``tkinter.messagebox``.

Sample output:
    # size: 50x10
    from tkcurses import messagebox
    messagebox.askyesno("Unsaved changes", "Save the document before closing?")

Each function takes a title and a message, and the options ``parent``,
``default`` - the button Return presses - and ``icon``. What they answer
differs, and the difference matters because code writes
``if askyesno(...)``: the ``show*`` functions answer ``"ok"`` and
:func:`askquestion` the name of the button pressed, which are strings;
:func:`askokcancel`, :func:`askyesno` and :func:`askretrycancel` answer
True or False; and :func:`askyesnocancel` True, False or None.

Closing a box with Escape answers as its cancelling button does, so a
caller never has a third case to handle:

=================  ========================  ====================
``type``           buttons                   Escape answers
=================  ========================  ====================
abortretryignore   Abort, Retry, Ignore      ``abort``
ok                 OK                        ``ok``
okcancel           OK, Cancel                ``cancel``
retrycancel        Retry, Cancel             ``cancel``
yesno              Yes, No                   ``no``
yesnocancel        Yes, No, Cancel           ``cancel``
=================  ========================  ====================

Differences from tkinter:
    ``icon`` is accepted and not drawn: Tk draws a stock picture beside
    the message, and a terminal has none.
"""
# The button sets and what each dismissal means are Tk's, read out of its own
# msgbox.tcl rather than remembered. The icon is carried in the options so
# that anything reading them back sees what was asked for.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import tkcurses
from tkcurses.commondialog import Dialog

if TYPE_CHECKING:
    from tkcurses import Misc, Toplevel

__all__ = [
    "ABORT",
    "ABORTRETRYIGNORE",
    "CANCEL",
    "ERROR",
    "IGNORE",
    "INFO",
    "NO",
    "OK",
    "OKCANCEL",
    "QUESTION",
    "RETRY",
    "RETRYCANCEL",
    "WARNING",
    "YES",
    "YESNO",
    "YESNOCANCEL",
    "Message",
    "askokcancel",
    "askquestion",
    "askretrycancel",
    "askyesno",
    "askyesnocancel",
    "showerror",
    "showinfo",
    "showwarning",
]

# icons
ERROR = "error"
INFO = "info"
QUESTION = "question"
WARNING = "warning"

# types
ABORTRETRYIGNORE = "abortretryignore"
OK = "ok"
OKCANCEL = "okcancel"
RETRYCANCEL = "retrycancel"
YESNO = "yesno"
YESNOCANCEL = "yesnocancel"

# replies
ABORT = "abort"
RETRY = "retry"
IGNORE = "ignore"
CANCEL = "cancel"
YES = "yes"
NO = "no"

#: Each type's buttons, in order, and what dismissing the box answers.
#: Straight out of Tk's msgbox.tcl, including the underlined letters.
_TYPES: dict[str, tuple[tuple[tuple[str, str], ...], str]] = {
    ABORTRETRYIGNORE: (
        ((ABORT, "&Abort"), (RETRY, "&Retry"), (IGNORE, "&Ignore")),
        ABORT,
    ),
    OK: (((OK, "&OK"),), OK),
    OKCANCEL: (((OK, "&OK"), (CANCEL, "&Cancel")), CANCEL),
    RETRYCANCEL: (((RETRY, "&Retry"), (CANCEL, "&Cancel")), CANCEL),
    YESNO: (((YES, "&Yes"), (NO, "&No")), NO),
    YESNOCANCEL: (((YES, "&Yes"), (NO, "&No"), (CANCEL, "&Cancel")), CANCEL),
}


def _label(marked: str) -> tuple[str, int]:
    """Split Tk's ``&Abort`` into the text and which letter is underlined."""
    index = marked.find("&")
    if index < 0:
        return marked, -1
    return marked[:index] + marked[index + 1 :], index


class Message(Dialog):
    """A message box: the class the functions are built on.

    ``Message(title=..., message=..., type="yesno").show()`` answers the
    name of the button pressed.
    """

    command: ClassVar[str | None] = "tk_messageBox"

    def _fixoptions(self) -> None:
        """Settle the type and the default button, as Tk does.

        Raises:
            TclError: If the type is not one of the six, or the default names
                a button that type has not got. Tk raises for both, rather
                than showing a box nobody asked for.
        """
        kind = str(self.options.get("type") or OK)
        if kind not in _TYPES:
            raise tkcurses.TclError(
                f'bad -type value "{kind}": must be {", ".join(sorted(_TYPES))}'
            )
        self.options["type"] = kind
        buttons, _ = _TYPES[kind]
        # "If no default button was specified, the default default is the
        # first button" - msgbox.tcl, which cites the bug that made it so.
        default = str(self.options.get("default") or buttons[0][0])
        if default not in {name for name, _ in buttons}:
            raise tkcurses.TclError(f'bad -default value "{default}"')
        self.options["default"] = default

    def body(self, window: Toplevel) -> Misc | None:
        """Fill the box in: the message and its buttons.

        TkCurses extension:
            tkinter's message box is the platform's; this is how the one here
            is built. See :meth:`tkcurses.commondialog.Dialog.body`.
        """
        message = str(self.options.get("message") or "")
        if message:
            tkcurses.Label(window, text=message, justify="left").pack(padx=1, pady=1)
        buttons, _ = _TYPES[str(self.options["type"])]
        default = str(self.options["default"])
        row = tkcurses.Frame(window)
        row.pack(pady=1)
        focus: Misc | None = None
        for name, marked in buttons:
            text, underline = _label(marked)
            button = tkcurses.Button(
                row, text=text, underline=underline, command=_answer(self, name)
            )
            button.pack(side="left", padx=1)
            if name == default:
                focus = button
        return focus

    def _fixresult(self, widget: Misc, result: Any) -> Any:  # noqa: ARG002
        """Turn a dismissal into the answer this box's type stands for."""
        if result is None:
            return _TYPES[str(self.options["type"])][1]
        return str(result)


def _answer(dialog: Message, name: str) -> Any:
    """A command that closes the box with one button's name."""
    return lambda: dialog.finish(name)


def _show(
    title: str | None = None,
    message: str | None = None,
    _icon: str | None = None,
    _type: str | None = None,
    **options: Any,
) -> str:
    """Build a message box and show it, as tkinter's own helper does."""
    if _icon and "icon" not in options:
        options["icon"] = _icon
    if _type and "type" not in options:
        options["type"] = _type
    if title:
        options["title"] = title
    if message:
        options["message"] = message
    return str(Message(**options).show())


def showinfo(
    title: str | None = None, message: str | None = None, **options: Any
) -> str:
    """Show an info message. Returns ``"ok"``."""
    return _show(title, message, INFO, OK, **options)


def showwarning(
    title: str | None = None, message: str | None = None, **options: Any
) -> str:
    """Show a warning message. Returns ``"ok"``."""
    return _show(title, message, WARNING, OK, **options)


def showerror(
    title: str | None = None, message: str | None = None, **options: Any
) -> str:
    """Show an error message. Returns ``"ok"``."""
    return _show(title, message, ERROR, OK, **options)


def askquestion(
    title: str | None = None, message: str | None = None, **options: Any
) -> str:
    """Ask a question. Returns the name of the button pressed."""
    return _show(title, message, QUESTION, YESNO, **options)


def askokcancel(
    title: str | None = None, message: str | None = None, **options: Any
) -> bool:
    """Ask whether to go ahead. True for OK."""
    return _show(title, message, QUESTION, OKCANCEL, **options) == OK


def askyesno(
    title: str | None = None, message: str | None = None, **options: Any
) -> bool:
    """Ask a question. True for Yes."""
    return _show(title, message, QUESTION, YESNO, **options) == YES


def askyesnocancel(
    title: str | None = None, message: str | None = None, **options: Any
) -> bool | None:
    """Ask a question. True for Yes, False for No, None for Cancel."""
    answer = _show(title, message, QUESTION, YESNOCANCEL, **options)
    if answer == CANCEL:
        return None
    return answer == YES


def askretrycancel(
    title: str | None = None, message: str | None = None, **options: Any
) -> bool:
    """Ask whether to try again. True for Retry."""
    return _show(title, message, WARNING, RETRYCANCEL, **options) == RETRY
