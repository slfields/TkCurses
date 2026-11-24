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

"""The graph's data: ``segments`` bars, each holding ``series`` values.

Pure: errors are ``ValueError``; the widget turns them into ``TclError``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tkcurses._charts.scale import ScaleType, Steps, round_up

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


class Model:
    """Values for every segment, plus a dirty flag for the refresh throttle."""

    def __init__(self, segments: int = 1, series: int = 1) -> None:
        _check_count("segments", segments)
        _check_count("series", series)
        self._series = series
        self._rows: list[list[float]] = [[0.0] * series for _ in range(segments)]
        self.dirty = True

    @property
    def segments(self) -> int:
        return len(self._rows)

    @property
    def series(self) -> int:
        return self._series

    def get(self, segment: int) -> tuple[float, ...]:
        """One segment's values."""
        return tuple(self._rows[self._index(segment)])

    def rows(self) -> tuple[tuple[float, ...], ...]:
        """Every segment's values."""
        return tuple(tuple(row) for row in self._rows)

    def set(self, segment: int, values: Sequence[float]) -> None:
        """Replace one segment's values; marks the model dirty."""
        index = self._index(segment)
        self._rows[index] = self._checked(values)
        self.dirty = True

    def set_all(self, rows: Iterable[Sequence[float]]) -> None:
        """Replace every segment's values at once; marks the model dirty."""
        checked = [self._checked(row) for row in rows]
        if len(checked) != self.segments:
            raise ValueError(f"expected {self.segments} segments, got {len(checked)}")
        self._rows = checked
        self.dirty = True

    def resize(self, segments: int | None = None, series: int | None = None) -> None:
        """Change the shape, keeping existing values and padding with zeros."""
        if segments is not None:
            _check_count("segments", segments)
            if segments < self.segments:
                del self._rows[segments:]
            else:
                self._rows.extend(
                    [0.0] * self._series for _ in range(segments - self.segments)
                )
        if series is not None:
            _check_count("series", series)
            self._rows = [(row + [0.0] * series)[:series] for row in self._rows]
            self._series = series
        self.dirty = True

    def _index(self, segment: int) -> int:
        if not 0 <= segment < self.segments:
            raise ValueError(f"segment {segment} out of range 0-{self.segments - 1}")
        return segment

    def _checked(self, values: Sequence[float]) -> list[float]:
        row = [float(value) for value in values]
        if len(row) != self._series:
            raise ValueError(f"expected {self._series} values, got {len(row)}")
        if not all(math.isfinite(value) for value in row):
            raise ValueError(f"values must be finite: {row}")
        return row


def _check_count(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be an integer >= 1, not {value!r}")


@dataclass(slots=True)
class AutoScale:
    """A maximum that follows the data.

    It grows at once to the round number at or above the largest value, so
    nothing is ever drawn past the end of the scale. It shrinks only when
    the values have stayed under a lower round number for ``hold_ms``, and
    then to the highest round number they needed in that time, so a value
    that dips for a moment does not make the scale jump.
    """

    hold_ms: int
    minimum: float = 0.0
    scaletype: ScaleType = "linear"
    base: float = 10.0
    #: What counts as a round number: see ``scale.Steps``.
    steps: Steps = "decimal"
    #: The maximum now; None until the first update.
    current: float | None = None
    #: When the values first fell under ``current``'s round number, and the
    #: highest they needed since; None while they still need it.
    _since: float | None = field(default=None, repr=False)
    _needed: float = field(default=0.0, repr=False)

    def __post_init__(self) -> None:
        if self.hold_ms < 0:
            raise ValueError(f"hold_ms must be at least 0, not {self.hold_ms}")

    def ceiling(self, value: float) -> float:
        """The round number a scale holding ``value`` ends at."""
        return round_up(value, self.minimum, self.scaletype, self.base, self.steps)

    def update(self, largest: float, now_ms: float) -> float:
        """Take the largest value shown at ``now_ms``; return the maximum."""
        needed = self.ceiling(largest)
        if self.current is None or needed >= self.current:
            self.current = max(needed, self.current or needed)
            self._since = None
            return self.current
        if self._since is None:
            self._since, self._needed = now_ms, needed
        else:
            self._needed = max(self._needed, needed)
        if now_ms - self._since >= self.hold_ms:
            self.current, self._since = self._needed, None
        return self.current

    @property
    def shrinking(self) -> bool:
        """True while the maximum is waiting to shrink: the widget keeps its
        timer running until it has, though no new values arrive."""
        return self._since is not None
