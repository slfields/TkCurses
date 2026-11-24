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

"""The ``scale`` option and the mapping from data values to points.

``scale`` is either an absolute integer number of points (fixed peak size)
or a ``"NN%"`` string (peak size relative to the frame, so the graph resizes
with it). Where along that length a value falls is
:class:`tkcurses._charts.scale.ValueRange`'s. Pure: errors are
``ValueError``; the widget turns them into ``TclError``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from tkcurses._charts.scale import ValueRange, as_range
from tkcurses.bargraph._glyphs import POINTS_PER_CELL

#: The smallest scale: one cell, so all eight steps can show.
MIN_POINTS = POINTS_PER_CELL


@dataclass(frozen=True, slots=True)
class Scale:
    """A parsed ``scale`` option.

    Exactly one of ``points`` (absolute) and ``percent`` (relative) is set.
    """

    points: int | None = None
    percent: float | None = None

    @property
    def relative(self) -> bool:
        """True when the peak size follows the frame."""
        return self.percent is not None

    def peak_points(self, available_cells: int) -> int:
        """The peak length in points, given the cells available along the bar.

        Absolute scales ignore ``available_cells``. Relative scales take
        their percentage of it, floored to whole points, never below
        :data:`MIN_POINTS`.
        """
        if self.points is not None:
            return self.points
        assert self.percent is not None
        available = max(0, available_cells) * POINTS_PER_CELL
        return max(MIN_POINTS, math.floor(available * self.percent / 100))

    def __str__(self) -> str:
        if self.points is not None:
            return str(self.points)
        return f"{self.percent:g}%"


def parse_scale(value: object) -> Scale:
    """Parse ``64``, ``"64"`` or ``"75%"`` into a :class:`Scale`."""
    if isinstance(value, Scale):
        return value
    if isinstance(value, bool):
        raise ValueError(f"bad scale {value!r}")
    if isinstance(value, int):
        return _absolute(value)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("%"):
            try:
                percent = float(text[:-1])
            except ValueError:
                raise ValueError(f"bad scale {value!r}") from None
            if not (0 < percent <= 100) or not math.isfinite(percent):
                raise ValueError(f"scale percentage must be in (0, 100], not {value!r}")
            return Scale(percent=percent)
        try:
            points = int(text)
        except ValueError:
            raise ValueError(f"bad scale {value!r}") from None
        # Outside the try, so "7" is told what "7" as a number is told.
        return _absolute(points)
    raise ValueError(f"bad scale {value!r}")


def _absolute(points: int) -> Scale:
    if points < MIN_POINTS:
        raise ValueError(f"scale must be at least {MIN_POINTS} points, not {points}")
    return Scale(points=points)


def parse_level(value: object, maximum: float) -> float:
    """A threshold or marker level, in data units.

    Numbers are data units already; ``"NN%"`` is a percentage of ``maximum``.
    """
    if isinstance(value, bool):
        raise ValueError(f"bad level {value!r}")
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            if text.endswith("%"):
                return float(text[:-1]) / 100 * maximum
            return float(text)
        except ValueError:
            raise ValueError(f"bad level {value!r}") from None
    raise ValueError(f"bad level {value!r}")


def to_points(value: float, maximum: float | ValueRange, peak_points: int) -> int:
    """Map a data value to points along a bar ``peak_points`` long.

    ``maximum`` is a :class:`ValueRange`, or a plain maximum for a linear
    range from zero: ``round(clamp(value, 0, maximum) / maximum * peak)``.
    """
    return as_range(maximum).to_points(value, peak_points)
