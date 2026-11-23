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

"""Missing values: what an XY chart draws where a series has none. Pure.

``missing`` fills a gap *between* two known values, as Kibana's "Missing
values" does: ``hide`` leaves it, so the line breaks; ``zero`` drops to
zero; ``linear`` joins the neighbours, by how far along in x the point
is; ``last`` carries the value before forward; ``next`` brings the one
after back. ``endvalues`` covers the gaps before the first known value
and after the last: ``hide``, ``zero`` or ``nearest``. As in Kibana, end
values apply only while ``missing`` fills something: with ``hide`` the
ends stay hidden too.

A value filled in is marked, so the segments through it can be dotted.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["END_VALUES", "MISSING", "Fitted", "fit"]

MISSING = ("hide", "zero", "linear", "last", "next")
END_VALUES = ("hide", "zero", "nearest")


@dataclass(frozen=True, slots=True)
class Fitted:
    """A series' values after filling, and which of them were filled."""

    ys: tuple[float | None, ...]
    filled: tuple[bool, ...]


def fit(
    xs: Sequence[float],
    ys: Sequence[float | None],
    missing: str = "hide",
    endvalues: str = "hide",
) -> Fitted:
    """``ys`` at ``xs`` with the gaps filled by ``missing`` and
    ``endvalues``.

    Raises:
        ValueError: If ``missing`` or ``endvalues`` is not one of the
            names, or ``xs`` and ``ys`` differ in length.
    """
    if missing not in MISSING:
        raise ValueError(f'bad missing "{missing}": must be {_names(MISSING)}')
    if endvalues not in END_VALUES:
        raise ValueError(f'bad endvalues "{endvalues}": must be {_names(END_VALUES)}')
    if len(xs) != len(ys):
        raise ValueError("xs and ys differ in length")
    out = list(ys)
    known = [i for i, y in enumerate(ys) if y is not None]
    if missing != "hide":
        for before, after in pairwise(known):
            for i in range(before + 1, after):
                out[i] = _between(xs, ys, before, after, i, missing)
        if known:
            first, last = known[0], known[-1]
            for i in range(first):
                out[i] = _end(endvalues, ys[first])
            for i in range(last + 1, len(ys)):
                out[i] = _end(endvalues, ys[last])
        elif endvalues == "zero":
            out = [0.0] * len(ys)
    filled = tuple(y is None and o is not None for y, o in zip(ys, out, strict=True))
    return Fitted(tuple(out), filled)


def _between(
    xs: Sequence[float],
    ys: Sequence[float | None],
    before: int,
    after: int,
    i: int,
    missing: str,
) -> float:
    low, high = ys[before], ys[after]
    assert low is not None and high is not None
    if missing == "zero":
        return 0.0
    if missing == "last":
        return low
    if missing == "next":
        return high
    span = xs[after] - xs[before]
    share = (xs[i] - xs[before]) / span if span else 0.0
    return low + (high - low) * share


def _end(endvalues: str, nearest: float | None) -> float | None:
    if endvalues == "zero":
        return 0.0
    if endvalues == "nearest":
        return nearest
    return None


def _names(names: tuple[str, ...]) -> str:
    return ", ".join(names[:-1]) + " or " + names[-1]
