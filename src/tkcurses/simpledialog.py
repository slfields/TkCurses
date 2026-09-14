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

"""Asking for one value, and the base class for asking for several.

Three shapes, and tkinter gives them three different lives:

:class:`Dialog` is the one people subclass. It is a ``Toplevel`` whose
*constructor* blocks: build it and the next line runs once the person has
answered, with the answer on ``self.result``. Override ``body`` to put the
fields in, ``validate`` to check them and ``apply`` to keep them.

:class:`SimpleDialog` is older and does it the other way round: constructing
it puts the window up, and ``go()`` waits and returns the index of the button
pressed.

``askstring``, ``askinteger`` and ``askfloat`` are one field and two buttons,
and they return None when cancelled - which is why they cannot simply return
the text.

The rule worth knowing is what a **bad value** does. ``ok`` asks ``validate``
first, and if it refuses, the dialog *stays up* with the focus back in the
field: it does not close, and it does not return anything. A prompt that
accepted nonsense and returned it would be worse than one that never
appeared, because the caller has no way to tell the two apart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import tkcurses
from tkcurses import messagebox
from tkcurses.commondialog import fit, restore_focus_grab, take_focus_grab

if TYPE_CHECKING:
    from tkcurses import Event, Misc

__all__ = [
    "Dialog",
    "SimpleDialog",
    "askfloat",
    "askinteger",
    "askstring",
]


class Dialog(tkcurses.Toplevel):
    """A dialog to subclass, whose constructor waits for an answer.

    Attributes:
        parent: The window the dialog belongs to.
        result: What ``apply`` left behind, or None if it was cancelled.
    """

    def __init__(self, parent: Misc | None, title: str | None = None) -> None:
        """
        Args:
            parent: The application window. None uses the root.
            title: Shown on the dialog's top edge.

        Raises:
            TclError: If there is no parent and no root window.
        """
        master = (
            parent
            if parent is not None
            else tkcurses._get_default_root("show a dialog")
        )
        super().__init__(master)
        if title:
            self.title(title)
        self.transient(master)
        self.parent = parent
        self.result: Any = None

        body = tkcurses.Frame(self)
        self.initial_focus = self.body(body) or self
        body.pack(padx=1, pady=1)
        self.buttonbox()

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        fit(self)
        self.initial_focus.focus_set()
        # Kept so that closing hands the keyboard back to whatever had it,
        # which matters when this dialog was opened from inside another.
        self._displaced = take_focus_grab(self)
        self.wait_window(self)

    # --------------------------------------------------- construction hooks

    def body(self, master: Misc) -> Misc | None:  # noqa: ARG002
        """Put the fields in. Override this.

        Returns:
            The widget that should have the keyboard, or None.
        """
        return None

    def buttonbox(self) -> None:
        """Add the standard OK and Cancel. Override to do something else."""
        box = tkcurses.Frame(self)
        tkcurses.Button(
            box, text="OK", width=10, command=self.ok, default="active"
        ).pack(side="left", padx=1, pady=1)
        tkcurses.Button(box, text="Cancel", width=10, command=self.cancel).pack(
            side="left", padx=1, pady=1
        )
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack()

    # ------------------------------------------------ the standard buttons

    def ok(self, event: Event | None = None) -> None:  # noqa: ARG002
        """Validate, apply, and close - in that order, and only in that order.

        A dialog whose ``validate`` refuses stays where it is with the focus
        back in the field that needs attention. Closing anyway and returning
        the bad value would leave the caller unable to tell a refusal from an
        answer.
        """
        if not self.validate():
            self.initial_focus.focus_set()
            return
        self.withdraw()
        self.update_idletasks()
        try:
            self.apply()
        finally:
            self.cancel()

    def cancel(self, event: Event | None = None) -> None:  # noqa: ARG002
        """Close without applying, handing the keyboard back."""
        if self.parent is not None and self.parent.winfo_exists():
            self.parent.focus_set()
        self.destroy()

    # ------------------------------------------------------- command hooks

    def validate(self) -> bool:
        """True if the fields may be applied. Override to check them."""
        return True

    def apply(self) -> None:
        """Keep the answer, usually on ``self.result``. Override this."""

    def destroy(self) -> None:
        """Take the window down, handing back the grab it displaced."""
        restore_focus_grab(self, getattr(self, "_displaced", (None, None)))
        super().destroy()


class SimpleDialog:
    """A message over a row of buttons, shown by :meth:`go`.

    Older than :class:`Dialog` and unlike it in two ways: the window goes up
    when the object is made rather than when it is shown, and the answer is
    the *index* of the button pressed.

    Attributes:
        num: The index of the button pressed, starting as ``default``.
    """

    def __init__(
        self,
        master: Misc,
        text: str = "",
        buttons: list[str] | None = None,
        default: int | None = None,
        cancel: int | None = None,
        title: str | None = None,
        class_: str | None = None,  # noqa: ARG002 - tkinter signature
    ) -> None:
        """
        Args:
            master: The window the dialog belongs to.
            text: The message.
            buttons: One label per button.
            default: Index of the button Return presses, or None for none.
            cancel: Index the dialog answers when dismissed, or None.
            title: Shown on the dialog's top edge.
            class_: Accepted for tkinter's signature; a terminal has no
                option database keyed by widget class to consult.
        """
        self.root = tkcurses.Toplevel(master)
        if title:
            self.root.title(title)
        self.num = default
        self.default = default
        self.cancel = cancel

        tkcurses.Message(self.root, text=text, aspect=400).pack(
            expand=True, fill="both"
        )
        self.frame = tkcurses.Frame(self.root)
        self.frame.pack()
        for index, label in enumerate(buttons or []):
            button = tkcurses.Button(
                self.frame, text=label, command=_pressed(self, index)
            )
            if index == default:
                button.configure(relief="ridge")
            button.pack(side="left", fill="both", expand=True)

        self.root.bind("<Return>", self.return_event)
        self.root.bind(
            "<Escape>",
            lambda event: self.wm_delete_window(),  # noqa: ARG005
        )
        self.root.protocol("WM_DELETE_WINDOW", self.wm_delete_window)
        self.root.transient(master)
        fit(self.root)

    def go(self) -> int | None:
        """Wait for a button, then take the dialog down and return its index."""
        self.root.focus_set()
        self._displaced = take_focus_grab(self.root)
        self.root.wait_window(self.root)
        return self.num

    def return_event(self, event: Event | None = None) -> None:  # noqa: ARG002
        """Press the default button, or complain if there is not one."""
        if self.default is None:
            self.root.bell()
        else:
            self.done(self.default)

    def wm_delete_window(self) -> None:
        """Answer with the cancel button, or complain if there is not one."""
        if self.cancel is None:
            self.root.bell()
        else:
            self.done(self.cancel)

    def done(self, num: int) -> None:
        """Answer with one button's index and close."""
        self.num = num
        restore_focus_grab(self.root, getattr(self, "_displaced", (None, None)))
        self.root.destroy()


def _pressed(dialog: SimpleDialog, index: int) -> Any:
    """A command that answers the dialog with one button's index."""
    return lambda: dialog.done(index)


class _QueryDialog(Dialog):
    """One prompt, one entry, and a value that has to pass ``validate``."""

    errormessage = "Not a value."

    def __init__(
        self,
        title: str | None,
        prompt: str,
        initialvalue: Any = None,
        minvalue: Any = None,
        maxvalue: Any = None,
        parent: Misc | None = None,
    ) -> None:
        self.prompt = prompt
        self.minvalue = minvalue
        self.maxvalue = maxvalue
        self.initialvalue = initialvalue
        self.entry: tkcurses.Entry | None = None
        super().__init__(parent, title)

    def body(self, master: Misc) -> Misc | None:
        tkcurses.Label(master, text=self.prompt, justify="left").grid(
            row=0, padx=1, sticky="w"
        )
        self.entry = tkcurses.Entry(master, name="entry")
        self.entry.grid(row=1, padx=1, sticky="we")
        if self.initialvalue is not None:
            self.entry.insert(0, str(self.initialvalue))
            self.entry.select_range(0, "end")
        return self.entry

    def getresult(self) -> Any:
        """Read the entry as this dialog's kind of value. Override this."""
        raise NotImplementedError

    def validate(self) -> bool:
        """Check the value, saying why and staying up when it will not do."""
        try:
            result = self.getresult()
        except ValueError:
            messagebox.showwarning(
                "Illegal value",
                self.errormessage + "\nPlease try again",
                parent=self,
            )
            return False
        if self.minvalue is not None and result < self.minvalue:
            messagebox.showwarning(
                "Too small",
                f"The allowed minimum value is {self.minvalue}. Please try again.",
                parent=self,
            )
            return False
        if self.maxvalue is not None and result > self.maxvalue:
            messagebox.showwarning(
                "Too large",
                f"The allowed maximum value is {self.maxvalue}. Please try again.",
                parent=self,
            )
            return False
        self.result = result
        return True


class _QueryInteger(_QueryDialog):
    errormessage = "Not an integer."

    def getresult(self) -> int:
        assert self.entry is not None
        return self.getint(self.entry.get())


class _QueryFloat(_QueryDialog):
    errormessage = "Not a floating-point value."

    def getresult(self) -> float:
        assert self.entry is not None
        return self.getdouble(self.entry.get())


class _QueryString(_QueryDialog):
    def __init__(self, *args: Any, **kw: Any) -> None:
        self._show = kw.pop("show", None)
        super().__init__(*args, **kw)

    def body(self, master: Misc) -> Misc | None:
        entry = super().body(master)
        if self._show is not None and entry is not None:
            entry.configure(show=self._show)
        return entry

    def getresult(self) -> str:
        assert self.entry is not None
        return self.entry.get()


def askinteger(title: str | None, prompt: str, **kw: Any) -> int | None:
    """Ask for a whole number. None if cancelled."""
    # result is whatever apply() left there, which validate() has already
    # made an int of; narrowed rather than cast so the promise is checked.
    result = _QueryInteger(title, prompt, **kw).result
    return None if result is None else int(result)


def askfloat(title: str | None, prompt: str, **kw: Any) -> float | None:
    """Ask for a number. None if cancelled."""
    result = _QueryFloat(title, prompt, **kw).result
    return None if result is None else float(result)


def askstring(title: str | None, prompt: str, **kw: Any) -> str | None:
    """Ask for some text. None if cancelled - which is not the same as
    the empty string, and is why this cannot simply return what was typed."""
    result = _QueryString(title, prompt, **kw).result
    return None if result is None else str(result)
