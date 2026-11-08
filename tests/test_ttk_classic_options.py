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

"""A themed widget takes Tk's ttk options and refuses the classic ones.

Each ttk widget here is built on a classic one and keeps that widget's
options as the defaults its drawing reads, but a program may name only what
Tk 9.0.2's themed widget has: ``ttk.Button(overrelief=...)`` is
``unknown option``, as on Tk. The record of Tk's options is
``tests/support/tk_ttk_options.json``, taken from real tkinter; these tests
need no display.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tkcurses
from tkcurses import TclError, ttk

RECORD = json.loads(
    (Path(__file__).parent / "support" / "tk_ttk_options.json").read_text()
)

#: Tk has these and TkCurses does not yet; the option-surface comparison
#: against real tkinter keeps the same list.
MISSING = {
    "OptionMenu": {"padding"},
    "Progressbar": {"phase"},
    "Treeview": {"selecttype"},
}


def build(name: str, root: tkcurses.Misc) -> tkcurses.Widget:
    if name == "OptionMenu":
        return ttk.OptionMenu(root, tkcurses.StringVar(root), "a", "a")
    return getattr(ttk, name)(root)


def classic_only(name: str) -> list[str]:
    cls = getattr(ttk, name)
    return sorted(set(cls._option_spec()) - set(RECORD[name]))


def test_the_table_is_the_record():
    assert {k: set(v) for k, v in ttk._TK_OPTIONS.items()} == {
        k: set(v) for k, v in RECORD.items()
    }


@pytest.mark.parametrize("name", sorted(RECORD))
def test_keys_are_tks_options(name):
    root = tkcurses.Misc()
    widget = build(name, root)
    assert set(widget.keys()) == set(RECORD[name]) - MISSING.get(name, set())
    assert set(widget.configure()) == set(widget.keys())


@pytest.mark.parametrize("name", sorted(RECORD))
def test_every_classic_only_option_is_refused(name):
    root = tkcurses.Misc()
    widget = build(name, root)
    refused = classic_only(name)
    assert refused, "nothing to refuse - the test would prove nothing"
    for option in refused:
        message = f'unknown option "-{option}"'
        with pytest.raises(TclError, match=message):
            widget.cget(option)
        # Not the value it holds: None is dropped before the check, as
        # tkinter drops it, and some of these hold None.
        with pytest.raises(TclError, match=message):
            widget.configure({option: "1"})
        with pytest.raises(TclError, match=message):
            widget.configure(option)


@pytest.mark.parametrize(
    "name, option",
    [
        ("Button", "overrelief"),
        ("Checkbutton", "selectcolor"),
        ("Scale", "sliderrelief"),
        ("Entry", "selectbackground"),
        ("Scrollbar", "troughcolor"),
        ("Notebook", "relief"),
    ],
)
def test_the_constructor_refuses_one_too(name, option):
    """The cases the measurement named."""
    root = tkcurses.Misc()
    with pytest.raises(TclError, match=f'unknown option "-{option}"'):
        getattr(ttk, name)(root, **{option: "1"})


def test_a_programs_subclass_answers_as_its_base():
    class Mine(ttk.Button):
        pass

    root = tkcurses.Misc()
    assert set(Mine(root).keys()) == set(RECORD["Button"])
    with pytest.raises(TclError):
        Mine(root, relief="raised")


def test_the_classic_widgets_keep_theirs():
    root = tkcurses.Misc()
    button = tkcurses.Button(root, overrelief="raised", relief="flat")
    assert button.cget("overrelief") == "raised"


def test_the_drawing_still_reads_the_classic_defaults():
    """A notebook is framed and a tree sunken though neither can be told to."""
    root = tkcurses.Misc()
    assert ttk.Notebook(root)._options["relief"] == "solid"
    assert ttk.Treeview(root)._options["relief"] == "sunken"
    assert ttk.LabeledScale(root).scale._options["relief"] == "flat"
