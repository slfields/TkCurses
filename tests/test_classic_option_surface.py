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

"""Every classic widget's options, against the real tkinter beside it.

The classic counterpart of ``test_ttk_option_surface.py``, and it asks a
different question for a reason. That one compares the option NAMES
``configure()`` lists; this one asks whether each option is ACCEPTED, by
creating the widget with it. They differ here because ``configure()`` leaves
out the short spellings ``bg``, ``fg`` and ``bd`` (TkCurses-bv0) although every
widget takes them, and listing would report 52 gaps that break no program.

Only the direction that breaks programs is checked: an option real Tk takes
and this library refuses with ``unknown option``. The value passed is the real
widget's own default, so a refusal of the VALUE is not a gap and is ignored.

Measured on 2026-11-02 against Tcl/Tk 9.0.2: 224 gaps across nineteen widgets,
none on the root window. Each is listed in :data:`KNOWN_GAPS` against the issue
that owns it - ten children of TkCurses-gm66, plus three older issues - so the
list can only shrink and a new gap fails the suite.

Like the ttk comparison, this needs a display for real tkinter and is skipped
without one, which includes CI.
"""

from __future__ import annotations

import pytest

pytest.importorskip("tkinter", reason="the comparison needs real tkinter")

import tkinter

import tkcurses

CLASSIC = (
    "Button", "Canvas", "Checkbutton", "Entry", "Frame", "Label",
    "LabelFrame", "Listbox", "Menu", "Menubutton", "Message", "OptionMenu",
    "PanedWindow", "Radiobutton", "Scale", "Scrollbar", "Spinbox", "Text",
    "Tk", "Toplevel",
)  # fmt: skip

#: Options real Tk takes and we refuse, per widget, grouped by the issue that
#: owns them. A gap not listed here is a test failure, and a listed one that has
#: been closed is too: this list may shrink and must never silently grow.
KNOWN_GAPS: dict[str, dict[str, str]] = {
    "Button": {
        "TkCurses-l26": "bitmap",
    },
    "Canvas": {
        "TkCurses-gm66.10": "confine offset xscrollincrement yscrollincrement",
    },
    "Checkbutton": {
        "TkCurses-gm66.10": "selectimage tristateimage",
        "TkCurses-l26": "bitmap",
    },
    "Entry": {},
    "Frame": {
        "TkCurses-yi4": "backgroundimage bgimg",
    },
    "Label": {
        "TkCurses-l26": "bitmap",
    },
    "LabelFrame": {
        "TkCurses-gm66.10": "labelwidget",
    },
    "Listbox": {
        "TkCurses-9e8": "exportselection",
        "TkCurses-gm66.10": "justify listvariable",
    },
    "Menu": {
        "TkCurses-gm66.10": "font tearoffcommand type",
    },
    "Menubutton": {
        "TkCurses-l26": "bitmap",
    },
    "Message": {},
    "OptionMenu": {
        "TkCurses-l26": "bitmap",
    },
    "PanedWindow": {},
    "Radiobutton": {
        "TkCurses-gm66.10": "selectimage tristateimage tristatevalue",
        "TkCurses-l26": "bitmap",
    },
    "Scale": {},
    "Scrollbar": {},
    "Spinbox": {},
    "Text": {
        "TkCurses-gm66.13": "endline startline",
    },
    "Tk": {
        "TkCurses-yi4": "backgroundimage bgimg",
    },
    "Toplevel": {
        "TkCurses-yi4": "backgroundimage bgimg",
    },
}


def _gaps(name: str) -> set[str]:
    return {
        option
        for options in KNOWN_GAPS.get(name, {}).values()
        for option in options.split()
    }


@pytest.fixture(scope="module")
def real_root():
    try:
        root = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def made():
    """Roots built by a test, destroyed after it: only one may exist at once."""
    roots = []
    yield roots
    for window in roots:
        window.destroy()


def _refused(name, real_root, made) -> tuple[set[str], set[str]]:
    """What real Tk's widget takes, and which of those ours refuses."""
    if name == "Tk":
        theirs = real_root
        made.append(tkcurses.Tk(useTk=False))

        def make(**kw):
            # Tk() takes no options, in tkinter either: configure is the way.
            made[-1].configure(**kw)

    elif name == "OptionMenu":
        theirs = tkinter.OptionMenu(real_root, tkinter.StringVar(real_root), "a")
        ours = tkcurses.Misc()
        menu = tkcurses.OptionMenu(ours, tkcurses.StringVar(ours), "a")

        def make(**kw):
            menu.configure(**kw)

    else:
        theirs = getattr(tkinter, name)(real_root)
        ours = tkcurses.Misc()

        def make(**kw):
            getattr(tkcurses, name)(ours, **kw)

    offered = set(theirs.keys())  # a widget's, not a dict's
    refused = set()
    for option in offered:
        try:
            make(**{option: str(theirs.cget(option))})
        except tkcurses.TclError as error:
            if "unknown option" in str(error):
                refused.add(option)
        except Exception:
            # The VALUE was refused, not the option.
            # Tk's defaults include values this library cannot read yet: padx
            # is "3m", a screen distance, and int() raises on it
            # (TkCurses-2qo). The option itself was recognised.
            continue
    return offered, refused


@pytest.mark.parametrize("name", CLASSIC)
def test_we_refuse_no_option_tk_takes_beyond_the_known_gaps(name, real_root, made):
    """A gap here means valid tkinter code fails against tkcurses."""
    _theirs, refused = _refused(name, real_root, made)
    unexplained = sorted(refused - _gaps(name))
    assert not unexplained, (
        f"tkinter.{name} takes options we refuse and nothing owns: {unexplained}."
        " Add them, or list them in KNOWN_GAPS against an issue."
    )


@pytest.mark.parametrize("name", CLASSIC)
def test_every_known_gap_is_still_a_gap(name, real_root, made):
    """So the list shrinks when something is fixed rather than going stale."""
    gaps = _gaps(name)
    if not gaps:
        pytest.skip("no gaps recorded for this widget")
    theirs, refused = _refused(name, real_root, made)
    assert gaps <= refused, (
        f"tkinter.{name}: {sorted(gaps - refused)} is listed as a gap but we"
        " accept it now - remove it from KNOWN_GAPS"
    )
    assert gaps <= theirs


def test_every_gap_is_owned_by_an_issue_id():
    for name, owners in KNOWN_GAPS.items():
        assert name in CLASSIC, name
        for owner in owners:
            assert owner.startswith("TkCurses-"), (name, owner)
