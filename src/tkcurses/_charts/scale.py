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

"""Value ranges, round numbers and the ticks on a chart's value axis.
Pure: errors are ``ValueError``; a widget turns them into ``TclError``.

:class:`ValueRange` is where along an axis a value falls, from
``minimum`` to ``maximum``, evenly or logarithmically. :func:`round_up`
and :func:`round_steps` find the round numbers a scale ends at and steps
by, and :func:`auto_ticks`, :func:`log_ticks` and :func:`even_ticks`
choose the ticks. Shared by the chart widgets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

__all__ = [
    "SCALE_TYPES",
    "ScaleType",
    "Steps",
    "ValueRange",
    "as_range",
    "auto_ticks",
    "even_ticks",
    "fitted_ticks",
    "label_start",
    "log_ticks",
    "round_steps",
    "round_up",
    "tidy",
]

ScaleType = Literal["linear", "log", "sqrt"]
#: The scale types, in the order an error names them.
SCALE_TYPES = ("linear", "log", "sqrt")


@dataclass(frozen=True, slots=True)
class ValueRange:
    """The values a bar spans, and how they are spaced along it.

    Linear: evenly from ``minimum`` to ``maximum``. Log: by the logarithm
    of the value, so each power of ``base`` takes the same length; then
    ``minimum`` must be above zero. Square root: by the square root of
    the value, signed, so a negative value mirrors a positive one, as a
    d3 ``scaleSqrt`` (a power scale of exponent 0.5) places it. A value at
    or below ``minimum`` is an empty bar, one at or above ``maximum`` a
    full one.
    """

    maximum: float
    minimum: float = 0.0
    scaletype: ScaleType = "linear"
    base: float = 10.0

    def __post_init__(self) -> None:
        if self.scaletype not in SCALE_TYPES:
            raise ValueError(
                f'bad scaletype "{self.scaletype}": must be linear, log or sqrt'
            )
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
        position = self.position(value)
        assert position is not None
        return position

    def position(self, value: float) -> float | None:
        """How far along ``value`` falls, 0 at ``minimum`` and 1 at
        ``maximum``, and beyond them for a value outside: not clamped, so a
        line through it can be clipped where it leaves. ``None`` for a
        value a log scale cannot place, at or below zero."""
        if self.log:
            if not value > 0:
                return None
            low = math.log(self.minimum)
            return (math.log(value) - low) / (math.log(self.maximum) - low)
        if self.scaletype == "sqrt":
            low = _signed_root(self.minimum)
            return (_signed_root(value) - low) / (_signed_root(self.maximum) - low)
        return (value - self.minimum) / (self.maximum - self.minimum)

    def to_points(self, value: float, peak_points: int) -> int:
        """``value`` as a length in points along a bar ``peak_points`` long."""
        return round(self.fraction(value) * peak_points)


def _signed_root(value: float) -> float:
    return math.copysign(math.sqrt(abs(value)), value)


def as_range(maximum: float | ValueRange) -> ValueRange:
    """A plain maximum is a linear range from zero."""
    if isinstance(maximum, ValueRange):
        return maximum
    if maximum <= 0:
        raise ValueError(f"maximum must be positive, not {maximum}")
    return ValueRange(float(maximum))


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


def auto_ticks(
    maximum: float | ValueRange,
    length_cells: int,
    min_spacing: int,
    steps: Steps = "decimal",
) -> list[float]:
    """Round tick values across the range that fit ``length_cells``.

    Linear: the step is the smallest of :func:`round_steps` that
    keeps ticks at least ``min_spacing`` cells apart on average - 1, 2 or 5
    times a power of ten; for ``"binary"`` steps, times a power of 1024;
    for a time unit, steps a clock reads well, 15 s, 1 min, 1 h - from the
    first multiple of it at or above the minimum. Log: see
    :func:`log_ticks`. Rounding to cells can still bring two together, so
    :func:`spaced` then drops any that land too close.
    """
    if not isinstance(maximum, ValueRange) and maximum <= 0:
        return [0.0]
    span = as_range(maximum)
    if length_cells <= 0:
        return [span.minimum]
    fits = max(1, length_cells // max(1, min_spacing))
    if span.log:
        return log_ticks(span, fits)
    for step in round_steps(steps):
        first = math.ceil(span.minimum / step - 1e-9)
        last = math.floor(span.maximum / step + 1e-9)
        if last - first <= fits:
            return [tidy(i * step) for i in range(first, last + 1)]
    raise AssertionError("unreachable")  # pragma: no cover


def log_ticks(span: ValueRange, fits: int) -> list[float]:
    """Ticks for a log range, at most about ``fits`` of them: each power of
    the base, and 2 and 5 times each when there is room for those too and
    the base is above 5. With too many powers, every second, third...
    """
    low = math.ceil(math.log(span.minimum, span.base) - 1e-9)
    high = math.floor(math.log(span.maximum, span.base) + 1e-9)
    powers = [tidy(span.base**k) for k in range(low, high + 1)]
    if not powers:
        return [span.minimum]
    between = [m for m in (2, 5) if m < span.base]
    if between and len(powers) * (1 + len(between)) <= fits:
        ticks = [
            tidy(power * m)
            for power in [tidy(span.base ** (low - 1)), *powers]
            for m in (1, *between)
        ]
        return sorted(t for t in set(ticks) if span.minimum <= t <= span.maximum)
    every = max(1, math.ceil(len(powers) / max(1, fits)))
    return powers[::every]


def even_ticks(maximum: float | ValueRange, count: int) -> list[float]:
    """``count`` ticks spread evenly along the bar (``ticks=N``): evenly
    spaced values on a linear range, a geometric series on a log one."""
    span = as_range(maximum)
    if count < 2:
        return [span.minimum]
    if span.log:
        ratio = span.maximum / span.minimum
        return [tidy(span.minimum * ratio ** (i / (count - 1))) for i in range(count)]
    width = span.maximum - span.minimum
    return [tidy(span.minimum + width * i / (count - 1)) for i in range(count)]


def fitted_ticks(
    span: ValueRange,
    length: int,
    width: Callable[[float], int],
    gap: int = 2,
    steps: Steps = "decimal",
) -> list[float]:
    """The most round ticks across ``span`` whose labels fit along an axis
    ``length`` cells long: each ``width(tick)`` cells, at least ``gap``
    apart, centred on its tick but kept on the axis.

    Linear and square-root ranges step evenly in value, as a d3 power
    scale's ticks do, taking the smallest of :func:`round_steps` whose
    labels all fit. Log ranges take :func:`log_ticks`, as many as fit.
    None when not even one label fits.
    """
    if length <= 0:
        return []
    if span.log:
        for fits in range(length, 0, -1):
            ticks = log_ticks(span, fits)
            if len(_apart(span, ticks, length, width, gap)) == len(ticks):
                return ticks
        return []
    for step in round_steps(steps):
        first = math.ceil(span.minimum / step - 1e-9)
        last = math.floor(span.maximum / step + 1e-9)
        if last - first + 1 > length:
            continue
        ticks = [tidy(i * step) for i in range(first, last + 1)]
        if len(_apart(span, ticks, length, width, gap)) == len(ticks):
            return ticks
    raise AssertionError("unreachable")  # pragma: no cover


def label_start(position: float, label: int, length: int) -> int:
    """Where a label ``label`` cells wide starts on an axis ``length``
    cells long, centred on ``position`` (0 to 1) but kept on the axis."""
    centre = position * (length - 1)
    start = round(centre - (label - 1) / 2)
    return max(0, min(start, length - label))


def _apart(
    span: ValueRange,
    ticks: list[float],
    length: int,
    width: Callable[[float], int],
    gap: int,
) -> list[float]:
    """``ticks`` without any whose label would come within ``gap`` cells
    of the one kept before it, or not fit on the axis at all."""
    kept: list[float] = []
    end = -math.inf
    for tick in ticks:
        position = span.position(tick)
        label = width(tick)
        if position is None or label > length:
            continue
        start = label_start(position, label, length)
        if start >= end + gap:
            kept.append(tick)
            end = start + label
    return kept
