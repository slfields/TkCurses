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

"""Tests for the dialog base class that need no terminal.

Everything about *showing* a dialog needs curses and lives in the tty tests.
What is here is the plumbing either side of that: which widget a dialog
decides is its master, what happens to the options on the way in, and what
happens to the answer on the way out.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tkcurses import Frame, Label, Misc, TclError, Toplevel
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack
from tkcurses.commondialog import Dialog, fit


class Recording(Dialog):
    """A dialog that records the hooks being called, and never shows."""

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.calls: list[str] = []

    def _fixoptions(self):
        self.calls.append("fixoptions")
        self.options["fixed"] = True

    def _fixresult(self, widget, result):
        self.calls.append("fixresult")
        return f"<{result}>"


# ------------------------------------------------------------------ master


def test_the_master_is_whatever_was_passed():
    master = Misc()
    assert Dialog(master).master is master


def test_the_parent_option_stands_in_for_the_master():
    """tkinter takes either, because its own dialog functions pass parent."""
    master = Misc()
    assert Dialog(parent=master).master is master


def test_a_dialog_with_neither_has_no_master_until_it_is_shown():
    """The root is looked up when the dialog is shown, not when it is made.

    A dialog can be built before there is a root - a module-level default
    argument, say - and only showing it needs one.
    """
    assert Dialog().master is None


def test_showing_without_a_root_says_so_rather_than_starting_one():
    """tkinter would make a temporary root here.

    This will not: bringing curses up reconfigures the terminal, and that has
    to be something the application asked for rather than something a
    message box does behind its back.
    """
    with pytest.raises(TclError, match="No root window"):
        Dialog().show()


# ----------------------------------------------------------------- options


def test_the_options_are_kept_as_they_were_given():
    dialog = Dialog(title="Save", initialdir="/tmp")
    assert dialog.options == {"title": "Save", "initialdir": "/tmp"}


def test_parent_stays_in_the_options():
    """tkinter leaves it there, and filedialog reads it back out."""
    master = Misc()
    assert Dialog(parent=master).options == {"parent": master}


def test_show_adds_its_own_options_to_the_ones_already_there():
    dialog = Recording(title="Save")
    with pytest.raises(TclError):
        dialog.show(initialdir="/tmp")
    assert dialog.options["title"] == "Save"
    assert dialog.options["initialdir"] == "/tmp"


def test_fixoptions_runs_before_anything_is_built():
    """The hook exists to correct the options, so it has to run first."""
    dialog = Recording()
    with pytest.raises(TclError):
        dialog.show()
    assert dialog.calls == ["fixoptions"]
    assert dialog.options["fixed"] is True


# ------------------------------------------------------------------ result


def test_a_dialog_returns_none_until_something_finishes_it():
    assert Dialog()._result is None


def test_finish_records_the_answer():
    dialog = Dialog()
    dialog.finish("yes")
    assert dialog._result == "yes"


def test_finish_with_nothing_is_a_cancel():
    dialog = Dialog()
    dialog.finish("yes")
    dialog.finish()
    assert dialog._result is None


def test_closing_a_dialog_that_was_never_opened_is_harmless():
    """destroy() runs on every exit path, including the ones that failed."""
    Dialog()._close()


# --------------------------------------------- sizing during a layout pass


@pytest.fixture
def root():
    """A mapped root with a panel stack, so windows get real geometry."""
    application = Misc()
    application.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    application._rect = Rect(0, 0, 60, 20)
    application._mapped = True
    type(application)._screen_size = lambda self: (60, 20)
    return application


def _dialog(root, name):
    """A window whose content is wider than the dialog minimum."""
    window = Toplevel(root, name=name)
    frame = Frame(window, name="f")
    for index in range(3):
        Label(frame, name=f"l{index}", text="Selection:" + "x" * index).pack()
    frame.pack()
    return window


def test_a_dialog_sized_mid_layout_still_gets_its_content_size(root):
    """Regression, TkCurses-3k4.

    ``update_layout`` refuses to nest, so called during a layout pass it
    lays nothing out and returns. ``fit`` then read requested sizes that
    were partial or zero and sized the dialog to the minimum - measured,
    30x10 instead of the 16x5 its content asks for.

    That is the mechanism behind a colour chooser seen once at 45 cells
    instead of 48, and it became easier to reach when ``<Configure>`` began
    firing from ``_allocate``: an application handler that opens a dialog
    now runs inside a layout pass.
    """
    settled = _dialog(root, "settled")
    fit(settled)
    wanted = settled.geometry()

    root.tk.layout._running = True
    window = _dialog(root, "midrun")
    fit(window)
    root.tk.layout._running = False

    root.tk.timers.run_idle()

    assert window.geometry() == wanted


def test_the_sizing_is_deferred_rather_than_dropped(root):
    """It is put off to the idle pass, which runs before anything is drawn -
    so the dialog is sized before a person could see it, not never.
    """
    root.tk.layout._running = True
    window = _dialog(root, "deferred")
    fit(window)
    root.tk.layout._running = False

    assert root.tk.timers.run_idle() > 0
