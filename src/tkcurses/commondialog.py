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

"""The base class the dialog modules are built on.

tkinter's ``commondialog.Dialog`` is a thin wrapper round a *native* dialog:
``show()`` hands the options to a Tcl command - ``tk_messageBox``,
``tk_getOpenFile`` - and the platform puts a window on the screen. There is no
native anything in a terminal, so the same class here has to build the dialog
itself, out of the widgets the library already has.

What survives from tkinter is the shape a caller sees, because that is what
``messagebox``, ``filedialog`` and ``colorchooser`` are written against:
construct with a master and some options, call ``show()``, get a value back.
``_fixoptions`` and ``_fixresult`` are still the two hooks either side of it.
What is new is :meth:`Dialog.body`, which a subclass fills in with the content
of the window, and :meth:`Dialog.finish`, which it calls to close the dialog
with an answer.

``show()`` blocks. That is what a dialog is for - the caller wants the answer
on the next line, not in a callback - and it is what tkinter does too. The
event loop keeps running underneath, so the application is not frozen; it is
the *caller* that waits, in ``wait_window``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import tkcurses
from tkcurses._core.geometry import BORDER_WIDTH

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
    """Size a dialog to its content and centre it on the screen.

    A terminal has no window manager to do either, and a dialog that needs
    moving or resizing by hand is not a dialog. Clamped to the screen,
    because a window curses will not make is worse than a small one: the
    request is not a promise.

    Shared rather than private, because all three dialog shapes need it -
    this module's, simpledialog's Toplevel subclass, and SimpleDialog - and
    they have no base class in common to inherit it from.
    """
    window.update_layout()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    # A toplevel reports the room its *contents* need, not its own outer
    # size, so the border it draws round them has to be added back on.
    # Without that the dialog is two cells too small and clips its own
    # content by exactly the border.
    edge = 2 * BORDER_WIDTH if window._border_drawn else 0
    wanted_width = max(window.winfo_reqwidth() + edge, MINIMUM_WIDTH)
    wanted_height = max(window.winfo_reqheight() + edge, MINIMUM_HEIGHT)
    width = min(wanted_width, screen_width)
    height = min(wanted_height, screen_height)
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")
    window.update_layout()


def take_focus_grab(window: Toplevel) -> tuple[Misc | None, Misc | None]:
    """Give ``window`` the grab, and hand back what it displaced.

    Tk keeps a stack of these - ``tk::SetFocusGrab`` and
    ``tk::RestoreFocusGrab`` - because grab_release does not put anything
    back: it releases, full stop. Without the pair, a dialog opened from
    inside another leaves the outer one with no keyboard when it closes, and
    the application looks wedged while a window is plainly sitting there.
    """
    displaced = (window.tk.grab, window.tk.focus)
    window.grab_set()
    return displaced


def restore_focus_grab(
    window: Toplevel, displaced: tuple[Misc | None, Misc | None]
) -> None:
    """Release ``window``'s grab and give back what :func:`take_focus_grab` took."""
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
        """Fill the dialog in. Subclasses override this.

        Args:
            window: The toplevel to build into, already titled and mapped.

        Returns:
            The widget that should have the keyboard, or None to leave the
            focus on the window itself.
        """
        return None

    # --------------------------------------------------------------- using

    def show(self, **options: Any) -> Any:
        """Put the dialog up, wait for an answer, and return it.

        Args:
            **options: Options to add to the ones given at construction,
                as tkinter's ``show`` does.

        Returns:
            Whatever :meth:`finish` was called with, passed through
            ``_fixresult``. A dialog dismissed with Escape returns None.

        Raises:
            TclError: If there is no master and no root window to fall back
                on. Unlike tkinter, this will not start one: bringing curses
                up reconfigures the terminal, which has to be something the
                application asked for.
        """
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
        """Close the dialog, and make ``result`` what ``show()`` returns."""
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
