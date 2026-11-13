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
library offers. Four things are asserted:

- ours never raises anything but ``TclError``, which is what a program
  written against tkinter catches;
- a value Tk takes, ours takes;
- a value Tk refuses, ours refuses - on 2026-11-03 Tk refused 571 of these
  that we stored (TkCurses-m595), and :data:`STILL_TAKEN` names what is left;
- where both refuse, the words are the same.

Like the other surface comparisons this needs a display, and so is skipped
in CI. TkCurses-vgkb.
"""

from __future__ import annotations

import re

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
        "value",
        "onvalue",
        "offvalue",
        "tristatevalue",
    ]
)
VALUES = ("abc", "2.5", -3)

#: (module, widget, option) that still take a value Tk refuses.
STILL_TAKEN: frozenset[tuple[str, str, str]] = frozenset()


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
                and our_type is None
                and (module, name, option) not in STILL_TAKEN
            ):
                wrong.append(f"{case}: Tk says {their_message!r}, ours takes it")
            elif (
                their_type is not None
                and our_type is not None
                and their_message != our_message
            ):
                wrong.append(f"{case}: Tk {their_message!r}, ours {our_message!r}")
    assert not wrong, f"{module}.{name}:\n  " + "\n  ".join(wrong)


@pytest.mark.parametrize(
    ("spec", "message"),
    [("WATCH", 'bad cursor spec "WATCH"'),
     ("pointer", 'bad cursor spec "pointer"'),
     ("watch red blue green", 'bad cursor spec "watch red blue green"'),
     ("watch nocolour", 'invalid color name "nocolour"'),
     ("@/nonexistent.xbm black", 'cleanup reading bitmap file "/nonexistent.xbm"'),
     ("@/nonexistent.xbm", 'bad cursor spec "@/nonexistent.xbm"')],
)  # fmt: skip
def test_a_cursor_tk_would_not_make_is_refused(spec, message):
    """Measured on Tk 9.0.2 on X11: the cursor font's names and ``none``,
    case and all, with up to two colours; a bitmap file is read."""
    root = tkcurses.Misc()
    for widget, option in (
        (tkcurses.Button(root), "cursor"),
        (tkcurses.Spinbox(root), "buttoncursor"),
        (tkcurses.PanedWindow(root), "sashcursor"),
    ):
        with pytest.raises(tkcurses.TclError, match=re.escape(message)):
            widget.configure(**{option: spec})


def test_a_cursor_bitmap_needs_a_hot_spot_and_its_mask_does_not(tmp_path):
    """``@cursor.xbm mask.xbm fg bg``: Tk reads both, and only the cursor's
    own bitmap must say where its hot spot is."""
    bits = "static unsigned char c_bits[] = { 0x01, 0x02 };\n"
    plain = tmp_path / "plain.xbm"
    plain.write_text("#define c_width 2\n#define c_height 2\n" + bits)
    hot = tmp_path / "hot.xbm"
    hot.write_text(
        "#define c_width 2\n#define c_height 2\n"
        "#define c_x_hot 0\n#define c_y_hot 0\n" + bits
    )
    button = tkcurses.Button(tkcurses.Misc())
    button.configure(cursor=f"@{hot} {plain} black white")
    assert button.cget("cursor") == f"@{hot} {plain} black white"
    with pytest.raises(tkcurses.TclError, match="bad hot spot in bitmap file"):
        button.configure(cursor=f"@{plain} black")
    button.configure(cursor=("watch", "red"))
    assert button.cget("cursor") == "watch red"


@pytest.mark.parametrize(
    "value", ["2c", "1i", "3m", "10p", " 2 c ", "1e1c", "0x10c", "2x", "2C", "c"]
)
def test_a_distance_with_a_unit_is_taken_or_refused_as_tk_does(value, real_root):
    """Tk's unit suffixes are read, at ten cells to the inch. What Tk takes
    is taken and what it refuses is refused, with its message."""
    try:
        tkinter.Button(real_root, borderwidth=value)
        theirs = None
    except tkinter.TclError as error:
        theirs = str(error)
    try:
        tkcurses.Button(tkcurses.Misc(), borderwidth=value)
        ours = None
    except tkcurses.TclError as error:
        ours = str(error)
    assert ours == theirs
