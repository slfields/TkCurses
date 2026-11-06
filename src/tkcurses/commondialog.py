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

"""The base class of the dialogs, as ``tkinter.commondialog``.

A dialog is made with a master and options, and :meth:`Dialog.show`
puts it up, waits, and answers. The application keeps running
underneath; it is the caller that waits.

Differences from tkinter:
    tkinter's dialogs are the platform's, which ``show`` asks Tk for.
    Here there are none to ask for, so each dialog is built from widgets:
    a subclass fills the window in :meth:`Dialog.body` and answers with
    :meth:`Dialog.finish`.
"""
# The shape a caller sees survives from tkinter because messagebox, filedialog
# and colorchooser are written against it; _fixoptions and _fixresult are
# still the two hooks either side of show.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import tkcurses

if TYPE_CHECKING:
    from tkcurses import Misc, Toplevel

__all__ = ["Dialog", "fit", "restore_focus_grab", "take_focus_grab"]

#: Cells left between the dialog's border and its content on each side.
PADDING = 1

#: Smallest a dialog may be, whatever it holds. Narrower than this and a
#: title has nowhere to go and the buttons collide.
MINIMUM_WIDTH = 16
MINIMUM_HEIGHT = 5


def fit(window: Toplevel) -> None:
    """Size a dialog to what it holds, within the screen, and centre it.

    TkCurses extension:
        The window manager does this in tkinter, and a terminal has none.
        For a dialog of your own, call it once the widgets are in.
    """
    # Shared rather than private, because all three dialog shapes need it -
    # this module's, simpledialog's Toplevel subclass, and SimpleDialog - and
    # they have no base class in common.
    if window.tk.layout.running:
        # A layout pass is already in progress, and update_layout refuses to
        # nest: it would return without laying anything out, and the
        # requested sizes read below would be whatever had been computed so
        # far - partial, or zero. Measured: a dialog sized mid-run comes out
        # at its minimum rather than its content's size.
        #
        # That is the mechanism behind TkCurses-3k4, a colour chooser seen
        # once at 45 cells instead of the 48 it asks for. It became easier to
        # reach when <Configure> started firing from _allocate, because an
        # application handler - one that opens a dialog, say - can now run
        # inside a layout pass.
        #
        # Deferred rather than forced: the idle pass runs before anything is
        # drawn, so the dialog is sized before a person could see it.
        window.after_idle(lambda: fit(window))
        return
    window.update_layout()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    # No border compensation here any more. A container's requested size now
    # includes the border it draws, which it always should have - a bordered
    # frame that sized to its children used to clip them by exactly its
    # border, and this was that bug patched at one call site.
    wanted_width = max(window.winfo_reqwidth(), MINIMUM_WIDTH)
    wanted_height = max(window.winfo_reqheight(), MINIMUM_HEIGHT)
    width = min(wanted_width, screen_width)
    height = min(wanted_height, screen_height)
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")
    window.update_layout()


def take_focus_grab(window: Toplevel) -> tuple[Misc | None, Misc | None]:
    """Give ``window`` the keyboard and the grab, and answer what it took
    them from, for :func:`restore_focus_grab`.

    TkCurses extension:
        tkinter has these as Tk's ``tk::SetFocusGrab``, which it does not
        expose. Without the pair, closing a dialog opened from another
        would leave the first with no keyboard.
    """
    displaced = (window.tk.grab, window.tk.focus)
    window.grab_set()
    return displaced


def restore_focus_grab(
    window: Toplevel, displaced: tuple[Misc | None, Misc | None]
) -> None:
    """Release ``window``'s grab and give the keyboard and grab back to what
    :func:`take_focus_grab` took them from.

    TkCurses extension:
        Tk's ``tk::RestoreFocusGrab``, which tkinter does not expose.
    """
    grab, focus = displaced
    window.grab_release()
    if grab is not None and grab.winfo_exists():
        grab.grab_set()
    if focus is not None and focus.winfo_exists():
        focus.focus_set()


class Dialog:
    """A modal window that returns a value.

    Attributes:
        command: The Tcl command tkinter would have called. Kept because it
            is part of the class tkinter documents and subclasses set it;
            nothing here reads it, since there is no Tcl to call.
        master: The widget the dialog belongs to, or None to use the root.
        options: Everything the caller passed, as tkinter keeps them.
    """

    command: ClassVar[str | None] = None

    def __init__(self, master: Misc | None = None, **options: Any) -> None:
        """
        Args:
            master: The widget the dialog belongs to. tkinter falls back to
                the ``parent`` option, so a caller may give either.
            **options: Dialog options, whose names are each module's business.
        """
        if master is None:
            master = options.get("parent")
        self.master = master
        self.options: dict[str, Any] = options
        #: What the dialog will return, set by finish().
        self._result: Any = None
        self._window: Toplevel | None = None
        self._displaced: tuple[Misc | None, Misc | None] = (None, None)

    # ----------------------------------------------------------- the hooks

    def _fixoptions(self) -> None:
        """Adjust the options before the dialog is built. A hook."""

    def _fixresult(self, widget: Misc, result: Any) -> Any:  # noqa: ARG002
        """Adjust the answer before it is returned. A hook."""
        return result

    def body(self, window: Toplevel) -> Misc | None:  # noqa: ARG002
        """Fill the dialog's window in. A subclass overrides this.

        Args:
            window: The toplevel to build in, already titled and shown.

        Returns:
            The widget that should have the keyboard, or None to leave it on
            the window.

        TkCurses extension:
            tkinter's dialogs are the platform's and have no body to fill.
        """
        return None

    # --------------------------------------------------------------- using

    def show(self, **options: Any) -> Any:
        """Put the dialog up, wait for an answer, and return it.

        Args:
            **options: Options to add to the ones given when it was made, as
                tkinter's ``show`` takes.

        Returns:
            What the dialog answered; None if it was closed with Escape.

        Raises:
            TclError: If there is no master and no root window.

        Differences from tkinter:
            With no root window it raises rather than making one: a root takes
            over the terminal, which should never happen as a side effect.
        """
        # What finish was called with, passed through _fixresult.
        self.options.update(options)
        self._fixoptions()
        master = self.master
        if master is None:
            master = tkcurses._get_default_root("show a dialog")
        window = self._open(master)
        try:
            master.wait_window(window)
        finally:
            self._close()
        return self._fixresult(master, self._result)

    def finish(self, result: Any = None) -> None:
        """Close the dialog, and make ``result`` what :meth:`show` answers.

        TkCurses extension:
            How a dialog built here answers; see :meth:`body`.
        """
        self._result = result
        self._close()

    # ----------------------------------------------------------- internals

    def _open(self, master: Misc) -> Toplevel:
        """Build the window, put it on the screen and take the keyboard."""
        window = tkcurses.Toplevel(master)
        self._window = window
        window.title(str(self.options.get("title") or ""))
        window.transient(master)
        focus = self.body(window)
        fit(window)
        # The grab goes on after the window is sized and placed, so that a
        # click during the build cannot reach it at a position it is about
        # to leave. What it displaces is kept, to be handed back on the way
        # out - a dialog opened from inside another has to leave the outer
        # one holding the keyboard, or nothing works afterwards.
        self._displaced = take_focus_grab(window)
        (focus or window).focus_set()
        window.bind("<Escape>", lambda event: self.finish(None))  # noqa: ARG005
        window.protocol("WM_DELETE_WINDOW", lambda: self.finish(None))
        return window

    def _close(self) -> None:
        """Take the dialog down. Safe to call more than once."""
        window, self._window = self._window, None
        if window is None or not window.winfo_exists():
            return
        restore_focus_grab(window, self._displaced)
        window.destroy()
