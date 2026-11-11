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

"""``tk.call``: the Tcl commands a tkinter program reaches for.

Every answer and every refusal here was measured on Tk 9.0.2 through
tkinter's own ``tk.call``. There is no Tcl interpreter behind TkCurses's:
the commands are served one by one, and anything else says so.
"""

from __future__ import annotations

import re

import pytest

import tkcurses as tk
from tkcurses import ttk


@pytest.fixture
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


def refused(root, message, *args):
    with pytest.raises(tk.TclError, match=re.escape(message)):
        root.tk.call(*args)


# ------------------------------------------------------------------ info


def test_info_names_the_tcl_followed(root):
    assert root.tk.call("info", "patchlevel") == "9.0.2"
    assert root.tk.call("info", "tclversion") == "9.0"
    assert root.tk.call(("info", "patchlevel")) == "9.0.2"


def test_info_refuses_as_tcl_does(root):
    refused(root, 'wrong # args: should be "info subcommand ?arg ...?"', "info")
    refused(
        root, 'wrong # args: should be "info patchlevel"', "info", "patchlevel", "x"
    )
    refused(root, 'TkCurses does not interpret "info commands"', "info", "commands")


# -------------------------------------------------------------------- tk


def test_the_windowing_system_is_x11(root):
    """The bindings here are Tk's X11 ones; a prefix serves, as in Tk."""
    assert root.tk.call("tk", "windowingsystem") == "x11"
    assert root.tk.call("tk", "wind") == "x11"
    refused(
        root,
        'wrong # args: should be "tk windowingsystem"',
        "tk",
        "windowingsystem",
        "x",
    )


def test_tk_refuses_as_tk_does(root):
    refused(root, 'wrong # args: should be "tk subcommand ?arg ...?"', "tk")
    refused(
        root,
        'unknown or ambiguous subcommand "s": must be appname, busy, caret,'
        " fontchooser, inactive, print, scaling, sysnotify, systray,"
        " useinputmethods, or windowingsystem",
        "tk", "s",
    )  # fmt: skip
    refused(root, 'TkCurses does not interpret "tk appname"', "tk", "appname")


def test_scaling_is_ten_cells_to_the_inch(root):
    assert root.tk.call("tk", "scaling") == pytest.approx(10 / 72)
    assert root.tk.call("tk", "scaling", "-displayof", ".") == pytest.approx(10 / 72)


def test_setting_the_scaling_reads_back_through_the_screens_millimetres(root):
    """ScalingCmd's arithmetic, with the terminal's columns as the screen's
    pixels: a set value reads back rounded, as 2.0 read back 1.998 on Tk."""
    columns = root.tk._screen_columns()
    assert root.tk.call("tk", "scaling", 2.0) == ""
    millimetres = int((25.4 / 72) / 2.0 * columns + 0.5)
    assert root.tk.call("tk", "scaling") == pytest.approx(
        25.4 / 72 * columns / millimetres
    )
    root.tk.call("tk", "scaling", " 3 ")
    assert root.tk.call("tk", "scaling") == pytest.approx(3.0, rel=0.05)


@pytest.mark.parametrize("factor", [0, -1, "1e9"])
def test_a_factor_too_small_or_large_is_the_largest_the_screen_allows(root, factor):
    """Measured: 0, -1 and 1e3 all read back the same large number - the
    screen one millimetre wide."""
    root.tk.call("tk", "scaling", factor)
    assert root.tk.call("tk", "scaling") == pytest.approx(
        25.4 / 72 * root.tk._screen_columns()
    )


def test_scaling_does_not_resize_a_cell(root):
    root.tk.call("tk", "scaling", 2.0)
    assert root.winfo_fpixels("1i") == 10.0


def test_scaling_refuses_as_tk_does(root):
    refused(root, 'expected floating-point number but got "x"', "tk", "scaling", "x")
    refused(root, 'value for "-displayof" missing', "tk", "scaling", "-displayof")
    refused(
        root, 'bad window path name ".nosuch"', "tk", "scaling", "-displayof", ".nosuch"
    )
    refused(
        root,
        'wrong # args: should be "tk scaling ?-displayof window? ?factor?"',
        "tk", "scaling", "1", "2",
    )  # fmt: skip


# ------------------------------------------------------- cget and configure


@pytest.fixture
def button(root):
    return tk.Button(root, text="hi")


def test_cget_takes_tks_dashed_name(button):
    assert button.tk.call(button, "cget", "-text") == "hi"
    assert button.tk.call(button, "cget", "-width") == 0
    assert button.tk.call(button, "cget", "-command") == ""
    assert button.tk.call(str(button), "cg", "-text") == "hi"


def test_configure_sets_and_answers_nothing(button):
    assert button.tk.call(button, "configure", "-text", "new", "-width", 3) == ""
    assert button.cget("text") == "new"
    assert button.cget("width") == 3


def test_configure_with_one_option_is_its_five_tuple_dashed(button):
    assert button.tk.call(button, "configure", "-text") == (
        "-text", "text", "Text", "", "hi",
    )  # fmt: skip
    assert button.tk.call(button, "conf", "-bg")[0] == "-background"


def test_configure_alone_is_every_five_tuple(button):
    entries = button.tk.call(button, "configure")
    assert isinstance(entries, tuple)
    assert ("-text", "text", "Text", "", "hi") in entries
    assert all(entry[0].startswith("-") and len(entry) == 5 for entry in entries)


@pytest.mark.parametrize(
    ("args", "message"),
    [(("cget", "text"), 'unknown option "text"'),
     (("cget", "-zz"), 'unknown option "-zz"'),
     (("cget",), 'should be ".!button cget option"'),
     (("configure", "-text", "a", "-width"), 'value for "-width" missing'),
     (("configure", "-zz", 1), 'unknown option "-zz"'),
     (("configure", "-width", "x"), 'expected integer but got "x"'),
     (("c", "-text"), 'ambiguous option "c"'),
     (("flash",), 'does not interpret ".!button flash"')],
)  # fmt: skip
def test_cget_and_configure_refuse_as_tk_does(button, args, message):
    refused(button, message, button, *args)


def test_a_themed_widget_refuses_a_classic_option(root):
    widget = ttk.Button(root, text="yo")
    assert root.tk.call(widget, "configure", "-text")[4] == "yo"
    refused(root, 'unknown option "-bg"', widget, "configure", "-bg", "red")


def _every_widget(root):
    classes = [
        tk.Button, tk.Canvas, tk.Checkbutton, tk.Entry, tk.Frame, tk.Label,
        tk.LabelFrame, tk.Listbox, tk.Menu, tk.Menubutton, tk.Message,
        tk.PanedWindow, tk.Radiobutton, tk.Scale, tk.Scrollbar, tk.Spinbox,
        tk.Text, tk.Toplevel, ttk.Button, ttk.Checkbutton, ttk.Combobox,
        ttk.Entry, ttk.Frame, ttk.Label, ttk.Labelframe, ttk.Menubutton,
        ttk.Notebook, ttk.Panedwindow, ttk.Progressbar, ttk.Radiobutton,
        ttk.Scale, ttk.Scrollbar, ttk.Separator, ttk.Sizegrip, ttk.Spinbox,
        ttk.Treeview,
    ]  # fmt: skip
    return [cls(root) for cls in classes]


def test_configure_alone_works_on_every_widget(root):
    """Each entry is asked for by name, so one that could not be would fail
    here rather than in a program."""
    for widget in [root, *_every_widget(root)]:
        entries = root.tk.call(widget, "configure")
        assert entries, type(widget).__name__
        for entry in entries:
            assert root.tk.call(widget, "cget", entry[0]) == entry[4], (
                type(widget).__name__, entry[0],
            )  # fmt: skip


# -------------------------------------------------------------- the rest


def test_a_command_not_served_says_so(root):
    refused(
        root,
        'TkCurses has no Tcl interpreter: it does not run "source"',
        "source",
        "x.tcl",
    )
    refused(root, 'invalid command name ".nosuch"', ".nosuch", "cget", "-text")
    refused(root, 'wrong # args: should be ". option ?arg ...?"', ".")
