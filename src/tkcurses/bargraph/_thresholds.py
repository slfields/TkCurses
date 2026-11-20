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

"""Threshold color zones.

Only the part of a bar above each level changes color; the whole bar never
does. On a bar of several series the levels apply to its tip, and the series
colors show below the first (see ``render.zoned_runs``). Pure: errors are
``ValueError``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tkcurses.bargraph._scale import ValueRange, parse_level, to_points

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True, slots=True)
class Zone:
    """A run of the bar in one color role.

    ``role`` is 0 for the base color (``colors[0]``) and ``j + 1`` for the
    ``j``-th threshold in ascending order. ``start`` and ``end`` are points
    from the bar's zero edge, ``end`` exclusive.
    """

    role: int
    start: int
    end: int


def parse_thresholds(
    thresholds: Iterable[tuple[object, str]], maximum: float
) -> tuple[tuple[float, str], ...]:
    """Normalize ``(level, color)`` pairs to data units, sorted ascending."""
    parsed = sorted(
        ((parse_level(level, maximum), str(color)) for level, color in thresholds),
        key=lambda pair: pair[0],
    )
    levels = [level for level, _ in parsed]
    if len(set(levels)) != len(levels):
        raise ValueError(f"duplicate threshold levels: {levels}")
    return tuple(parsed)


def zones(
    value_points: int,
    levels: Iterable[float],
    maximum: float | ValueRange,
    peak_points: int,
) -> list[Zone]:
    """Split a bar ``value_points`` long into color zones.

    ``levels`` are threshold levels in data units, sorted ascending.
    """
    result: list[Zone] = []
    start = 0
    role = 0
    for level in levels:
        boundary = to_points(level, maximum, peak_points)
        if boundary >= value_points:
            break
        if boundary > start:
            result.append(Zone(role, start, boundary))
            start = boundary
        role += 1
    if value_points > start:
        result.append(Zone(role, start, value_points))
    return result
