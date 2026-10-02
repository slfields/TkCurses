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

"""What pack and grid accept for padx, pady, ipadx and ipady.

One contract, two managers, so it is tested once against both rather than
twice. Every row of ``SPECIFICATIONS`` is a measurement of real Tk 8.6 taken
by running the same matrix through ``tkinter`` and through this library and
diffing the answers - 168 cases, including the exact wording of every error.
That matters because the two option families disagree:

* ``padx``/``pady`` take a distance per side, so ``padx=(0, 1)`` pads the
  right of a widget and not its left.
* ``ipadx``/``ipady`` take one distance. ``ipadx=(2, 8)`` is an error where
  ``padx=(2, 8)`` is fine, and ``ipadx=(2,)`` is accepted because tkinter
  stringifies it to ``"2"`` before Tcl sees it.

The issue that prompted this (TkCurses-l8f) guessed the asymmetry was a bug in
this library to be fixed consistently across all four. It is Tk's, and the
measurement is what settled it.
"""

from __future__ import annotations

import pytest

from tkcurses import Misc, TclError, Widget
from tkcurses._core.geometry import Rect, Size

#: ``(value, what padx does, what ipadx does)``. A string result is the
#: message Tk raises, with ``{option}`` standing in for the option's name;
#: anything else is what ``pack_info``/``grid_info`` reads back.
WRONG_PARTS = "wrong number of parts to pad specification"
SPECIFICATIONS = [
    (3, 3, 3),
    ((2, 8), (2, 8), 'bad {option} value "2 8": must be positive screen distance'),
    ("2 8", (2, 8), 'bad {option} value "2 8": must be positive screen distance'),
    ((2,), 2, 2),
    ("4", 4, 4),
    ((0, 1), (0, 1), 'bad {option} value "0 1": must be positive screen distance'),
    ((2, 2), 2, 'bad {option} value "2 2": must be positive screen distance'),
    ("3 3", 3, 'bad {option} value "3 3": must be positive screen distance'),
    (0, 0, 0),
    # negatives name the offending part for a pad, the whole value for an ipad
    (
        -1,
        'bad pad value "-1": must be positive screen distance',
        'bad {option} value "-1": must be positive screen distance',
    ),
    (
        (-1, 2),
        'bad pad value "-1": must be positive screen distance',
        'bad {option} value "-1 2": must be positive screen distance',
    ),
    # a pad counts its parts before converting them; an ipad does not
    (
        (1, 2, 3),
        WRONG_PARTS,
        'bad {option} value "1 2 3": must be positive screen distance',
    ),
    ("", WRONG_PARTS, 'bad {option} value "": must be positive screen distance'),
    (
        "x",
        'bad pad value "x": must be positive screen distance',
        'bad {option} value "x": must be positive screen distance',
    ),
    # fractional distances round, they do not truncate
    (2.6, 3, 3),
    (0.5, 1, 1),
    (2.5, 3, 3),
    (
        (2.6, 8.4),
        (3, 8),
        'bad {option} value "2.6 8.4": must be positive screen distance',
    ),
    (True, 1, 1),
    (" 2  8 ", (2, 8), 'bad {option} value " 2  8 ": must be positive screen distance'),
    ([2, 8], (2, 8), 'bad {option} value "2 8": must be positive screen distance'),
    ("+2", 2, 2),
]

MANAGERS = ("pack", "grid")
AXES = ("x", "y")


@pytest.fixture
def root():
    root = Misc()
    root._rect = Rect(0, 0, 40, 12)
    root._mapped = True
    return root


def child(root):
    """A widget asking for a fixed size, so padding is the only variable."""
    widget = Widget(root, name="w")
    widget._requested = Size(4, 1)
    return widget


def apply(widget, manager, option, value):
    """Configure one pad option and read it back, as Tk's info dict would."""
    if manager == "pack":
        widget.pack(**{option: value})
        return widget.pack_info()[option]
    widget.grid(row=0, column=0, **{option: value})
    return widget.grid_info()[option]


def check(root, manager, option, value, expected):
    """Assert one measured row, whether it is a value or an error."""
    widget = child(root)
    if isinstance(expected, str):
        with pytest.raises(TclError) as caught:
            apply(widget, manager, option, value)
        assert str(caught.value) == expected.format(option=option)
    else:
        assert apply(widget, manager, option, value) == expected


@pytest.mark.parametrize("manager", MANAGERS)
@pytest.mark.parametrize("axis", AXES)
@pytest.mark.parametrize(("value", "expected", "_ipad"), SPECIFICATIONS)
def test_an_external_pad_takes_a_distance_per_side(
    root, manager, axis, value, expected, _ipad
):
    check(root, manager, f"pad{axis}", value, expected)


@pytest.mark.parametrize("manager", MANAGERS)
@pytest.mark.parametrize("axis", AXES)
@pytest.mark.parametrize(("value", "_pad", "expected"), SPECIFICATIONS)
def test_an_internal_pad_takes_one_distance_only(
    root, manager, axis, value, _pad, expected
):
    check(root, manager, f"ipad{axis}", value, expected)


@pytest.mark.parametrize("manager", MANAGERS)
def test_a_pair_of_equal_sides_reads_back_as_one_number(root, manager):
    """Tk does not remember how the pad was spelled, only what it means."""
    assert apply(child(root), manager, "padx", (2, 2)) == 2


@pytest.mark.parametrize("manager", MANAGERS)
def test_a_pair_survives_a_later_configure_that_does_not_mention_it(root, manager):
    """Options not named in a call keep what they had - pairs included.

    Re-parsing every option on every call would push the stored pair back
    through the parser as a value it never accepted from a caller.
    """
    widget = child(root)
    if manager == "pack":
        widget.pack(padx=(1, 5))
        widget.pack_configure(side="left")
        assert widget.pack_info()["padx"] == (1, 5)
    else:
        widget.grid(row=0, column=0, padx=(1, 5))
        widget.grid_configure(sticky="ew")
        assert widget.grid_info()["padx"] == (1, 5)
