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
with it). :class:`ValueRange` is where along that length a value falls: from
``minimum`` to ``maximum``, evenly or logarithmically. Pure: errors are
``ValueError``; the widget turns them into ``TclError``.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from tkcurses.bargraph._glyphs import POINTS_PER_CELL

if TYPE_CHECKING:
    from collections.abc import Iterator

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


ScaleType = Literal["linear", "log"]


@dataclass(frozen=True, slots=True)
class ValueRange:
    """The values a bar spans, and how they are spaced along it.

    Linear: evenly from ``minimum`` to ``maximum``. Log: by the logarithm
    of the value, so each power of ``base`` takes the same length; then
    ``minimum`` must be above zero. A value at or below ``minimum`` is an
    empty bar, one at or above ``maximum`` a full one.
    """

    maximum: float
    minimum: float = 0.0
    scaletype: ScaleType = "linear"
    base: float = 10.0

    def __post_init__(self) -> None:
        if self.scaletype not in ("linear", "log"):
            raise ValueError(f'bad scaletype "{self.scaletype}": must be linear or log')
        for name in ("maximum", "minimum", "base"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be a finite number")
        if not self.maximum > self.minimum:
            raise ValueError(
                f"maximum ({self.maximum:g}) must be above minimum ({self.minimum:g})"
            )
        if self.log:
            if not self.base > 1:
                raise ValueError(f"logbase must be above 1, not {self.base:g}")
            if not self.minimum > 0:
                raise ValueError(
                    f"a log scale needs a minimum above 0, not {self.minimum:g}"
                )

    @property
    def log(self) -> bool:
        return self.scaletype == "log"

    def fraction(self, value: float) -> float:
        """How far along the bar ``value`` falls, from 0 to 1."""
        if not value > self.minimum:  # NaN too: nothing drawn
            return 0.0
        if value >= self.maximum:
            return 1.0
        if self.log:
            low = math.log(self.minimum)
            return (math.log(value) - low) / (math.log(self.maximum) - low)
        return (value - self.minimum) / (self.maximum - self.minimum)

    def to_points(self, value: float, peak_points: int) -> int:
        """``value`` as a length in points along a bar ``peak_points`` long."""
        return round(self.fraction(value) * peak_points)


def as_range(maximum: float | ValueRange) -> ValueRange:
    """A plain maximum is a linear range from zero."""
    if isinstance(maximum, ValueRange):
        return maximum
    if maximum <= 0:
        raise ValueError(f"maximum must be positive, not {maximum}")
    return ValueRange(float(maximum))


def to_points(value: float, maximum: float | ValueRange, peak_points: int) -> int:
    """Map a data value to points along a bar ``peak_points`` long.

    ``maximum`` is a :class:`ValueRange`, or a plain maximum for a linear
    range from zero: ``round(clamp(value, 0, maximum) / maximum * peak)``.
    """
    return as_range(maximum).to_points(value, peak_points)


#: Steps, in seconds, that read well on a clock, from a second up.
_CLOCK_STEPS = (
    1, 2, 5, 10, 15, 30,
    60, 120, 300, 600, 900, 1800,
    3600, 7200, 10800, 21600, 43200,
    86400, 172800, 604800, 1209600,
)  # fmt: skip


# The 1-2-5 series is the long-standing convention for the steps of chart
# and instrument scales, not taken from any one source; the binary prefixes
# it is written with (KiB, MiB) are IEC 80000-13's.
#: What counts as a round number: ``"decimal"``, 1, 2 or 5 times a power of
#: ten; ``"binary"``, the same times a power of 1024 (500 KiB, 1 MiB, 2 MiB);
#: or a number, the length in seconds of the data's time unit, for steps a
#: clock reads well.
Steps = float | Literal["decimal", "binary"]


def round_steps(kind: Steps = "decimal") -> Iterator[float]:
    """Round numbers of ``kind``, ascending, from a trillionth upward."""
    below_one = (m * 10.0**e for e in range(-12, 0) for m in (1, 2, 5))
    if kind == "decimal" or kind == "binary":
        yield from below_one
        yield from _counted(kind == "binary")
        return
    seconds = float(kind)
    for step in below_one:
        yield step / seconds
    for step in _CLOCK_STEPS:
        yield step / seconds
    exponent = 1
    while True:
        for mantissa in (1, 2, 5):
            yield mantissa * 10.0**exponent * 86400 / seconds
        exponent += 1


def _counted(binary: bool) -> Iterator[float]:
    """1, 2, 5, 10, 20, 50...; in binary, up to 500, then 1, 2, 5 KiB..."""
    power = 1.0
    while True:
        for exponent in range(4 if binary else 1):
            for mantissa in (1, 2, 5):
                if not binary or mantissa * 10**exponent < 1000:
                    yield mantissa * 10.0**exponent * power
        power *= 1024 if binary else 10


def round_up(
    value: float,
    minimum: float = 0.0,
    scaletype: ScaleType = "linear",
    base: float = 10.0,
    steps: Steps = "decimal",
) -> float:
    """The round number at or above ``value`` that a scale from ``minimum``
    can end at: on a log scale the next power of ``base``; otherwise the
    next of :func:`round_steps` - 50, 100, 200; 512 KiB, 1 MiB; 30 s,
    1 min, 5 min. Always above ``minimum``.
    """
    if scaletype == "log":
        exponent = math.ceil(math.log(max(value, minimum), base) - 1e-9)
        result = base**exponent
        if result <= minimum * (1 + 1e-9):
            result *= base
        return tidy(result)
    value = max(value, minimum)
    floor = minimum if minimum > 0 else 0.0
    for candidate in round_steps(steps):
        # With nothing to fit, the first whole number: 1 from zero.
        enough = value > 0 or candidate >= 1
        if enough and candidate >= value * (1 - 1e-12) and candidate > floor * 1.000001:
            return tidy(candidate)
    raise AssertionError("unreachable")  # pragma: no cover


def tidy(value: float) -> float:
    """``value`` without float noise: 0.30000000000000004 is 0.3."""
    return float(f"{value:.10g}")
