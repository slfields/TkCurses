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

"""Every option of every widget, made with a bad value, against real tkinter.

Three values - ``"abc"``, ``"2.5"`` and ``-3`` - for each option either
library offers. Three things are asserted, and one is deliberately not:

- ours never raises anything but ``TclError``, which is what a program
  written against tkinter catches;
- a value Tk takes, ours takes;
- where both refuse, the words are the same.

What is NOT asserted is that ours refuses everything Tk refuses: on
2026-11-03 Tk refused 571 of these that we stored, which is a validation gap
of its own (TkCurses-m595), not a crash.

Like the other surface comparisons this needs a display, and so is skipped
in CI. TkCurses-vgkb.
"""

from __future__ import annotations

import pytest

pytest.importorskip("tkinter", reason="the comparison needs real tkinter")

import tkinter
import tkinter.ttk

import tkcurses
import tkcurses.ttk

CLASSIC = (
    "Button", "Canvas", "Checkbutton", "Entry", "Frame", "Label", "LabelFrame",
    "Listbox", "Menu", "Menubutton", "Message", "PanedWindow", "Radiobutton",
    "Scale", "Scrollbar", "Spinbox", "Text", "Toplevel",
)  # fmt: skip
TTK = (
    "Button", "Checkbutton", "Combobox", "Entry", "Frame", "Label", "Labelframe",
    "Menubutton", "Notebook", "Panedwindow", "Progressbar", "Radiobutton",
    "Scale", "Scrollbar", "Separator", "Sizegrip", "Spinbox", "Treeview",
)  # fmt: skip

#: Options whose value is not a number or a word in either library's sense:
#: names, commands, variables, images, fonts and the window-system options.
#: Each has its own test where it is checked.
NOT_VALUES = frozenset(
    [
        "class",
        "colormap",
        "container",
        "visual",
        "screen",
        "use",
        "menu",
        "labelwidget",
        "image",
        "selectimage",
        "tristateimage",
        "textvariable",
        "variable",
        "listvariable",
        "command",
        "xscrollcommand",
        "yscrollcommand",
        "validatecommand",
        "invalidcommand",
        "postcommand",
        "tearoffcommand",
        "values",
        "font",
        "cursor",
        "style",
        "bitmap",
        "tile",
        "name",
        "show",
        "takefocus",
        "default",
        "columns",
        "displaycolumns",
        "validate",
        "vcmd",
        "invcmd",
        "format",
        "text",
        "label",
        "placeholder",
        "inactiveselectbackground",
        "mode",
        "sashcursor",
        "value",
        "onvalue",
        "offvalue",
        "tristatevalue",
        "exportselection",
    ]
)
VALUES = ("abc", "2.5", -3)


@pytest.fixture(scope="module")
def real_root():
    try:
        root = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    root.withdraw()
    yield root
    root.destroy()


def _outcome(make, keyword, value):
    try:
        widget = make(**{keyword: value})
    except Exception as error:  # the type is what is compared
        return type(error), str(error)
    widget.destroy()
    return None, None


@pytest.mark.parametrize(
    ("module", "name"),
    [("tk", name) for name in CLASSIC] + [("ttk", name) for name in TTK],
)
def test_a_bad_value_is_answered_as_tkinter_answers_it(real_root, module, name):
    theirs_class = getattr(tkinter if module == "tk" else tkinter.ttk, name)
    ours_class = getattr(tkcurses if module == "tk" else tkcurses.ttk, name)
    ours_root = tkcurses.Misc()
    # An option we do not offer at all is a different gap, with its own
    # issue (TkCurses-zkks): this compares values, not the option lists.
    offered = set(ours_class(ours_root).keys())
    options = sorted(set(theirs_class(real_root).keys()) & offered)
    wrong = []
    for option in options:
        if option in NOT_VALUES or len(option) <= 2:  # bg, fg, bd: synonyms
            continue
        keyword = option + "_" if option in ("from", "in") else option
        for value in VALUES:
            their_type, their_message = _outcome(
                lambda **kw: theirs_class(real_root, **kw), keyword, value
            )
            our_type, our_message = _outcome(
                lambda **kw: ours_class(ours_root, **kw), keyword, value
            )
            case = f"{option}={value!r}"
            if our_type is not None and not issubclass(our_type, tkcurses.TclError):
                wrong.append(f"{case}: raised {our_type.__name__}: {our_message}")
            elif their_type is None and our_type is not None:
                wrong.append(f"{case}: Tk takes it, ours says {our_message!r}")
            elif (
                their_type is not None
                and our_type is not None
                and their_message != our_message
            ):
                wrong.append(f"{case}: Tk {their_message!r}, ours {our_message!r}")
    assert not wrong, f"{module}.{name}:\n  " + "\n  ".join(wrong)
