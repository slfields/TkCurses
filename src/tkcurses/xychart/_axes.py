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

"""An XY chart's value axis: the range it spans, after Kibana's bounds.
Pure.

``bounds`` is Kibana's: ``full`` takes the axis to zero, so a value's
height is its size; ``data`` spans only the values; ``custom`` takes
``minimum`` and ``maximum`` as given, either left to ``full`` when not
given. An area is measured from zero, so with an area on the chart
``data`` is ``full``, as Kibana offers only full and custom for areas. A
log scale cannot reach zero, so there ``full`` is ``data``. ``nice``
rounds the ends out to the steps the ticks will take, as Kibana's "Round
to nice value" does; custom bounds are kept exactly. A percentage stack's
axis is 0 to 100.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from tkcurses._charts.scale import ScaleType, ValueRange, round_steps, tidy

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

__all__ = ["BOUNDS", "NICE_TICKS", "value_range"]

BOUNDS = ("full", "data", "custom")
#: How many steps :func:`value_range` rounds to: the ends land on a step
#: of the largest round size giving at most this many, as d3's ``nice``.
NICE_TICKS = 10


def value_range(
    values: Iterable[float | None],
    *,
    bounds: str = "full",
    minimum: float | None = None,
    maximum: float | None = None,
    nice: bool = True,
    scaletype: ScaleType = "linear",
    base: float = 10.0,
    areas: bool = False,
    percentage: bool = False,
) -> ValueRange:
    """The range a value axis spans for ``values``.

    Raises:
        ValueError: If ``bounds`` is not one of :data:`BOUNDS`, custom
            bounds are not in order, or a log scale's are not above zero.
    """
    if bounds not in BOUNDS:
        raise ValueError(f'bad bounds "{bounds}": must be full, data or custom')
    if percentage:
        return ValueRange(100.0, 0.0)
    log = scaletype == "log"
    known = [v for v in values if v is not None and math.isfinite(v)]
    if log:
        known = [v for v in known if v > 0]
    if bounds == "data" and areas:
        bounds = "full"
    if known:
        low, high = min(known), max(known)
    else:
        low, high = (1.0, base) if log else (0.0, 1.0)
    if bounds != "data" and not log:
        low, high = min(low, 0.0), max(high, 0.0)
    if bounds == "custom":
        low = low if minimum is None else float(minimum)
        high = high if maximum is None else float(maximum)
        if not high > low:
            raise ValueError(f"maximum ({high:g}) must be above minimum ({low:g})")
        if log and not low > 0:
            raise ValueError(f"a log scale needs a minimum above 0, not {low:g}")
        return ValueRange(high, low, scaletype, base)
    if high == low:
        low, high = _widened(low, log, base)
    if nice:
        low, high = _nice(low, high, log, base)
    return ValueRange(high, low, scaletype, base)


def _widened(value: float, log: bool, base: float) -> tuple[float, float]:
    """A range around one value, so it is drawn in the middle. At the
    ends of what a float holds, where halving underflows to nothing or
    widening overflows, the value is drawn at one end of the range
    instead: a range must still span something."""
    if log:
        low, high = value / base, value * base
        if not 0 < low < high < math.inf:
            low, high = (
                (value, value * base)
                if value * base < math.inf
                else (
                    value / base,
                    value,
                )
            )
        return low, high
    if value == 0:
        return 0.0, 1.0
    half = abs(value) / 2
    low, high = value - half, value + half
    if not -math.inf < low < high < math.inf:
        # 5e-324 / 2 is 0, and 1.7e308 * 1.5 is infinite.
        low, high = (0.0, value) if value > 0 else (value, 0.0)
    return low, high


def _nice(low: float, high: float, log: bool, base: float) -> tuple[float, float]:
    if log:
        return (
            _power(base, math.floor(math.log(low, base) + 1e-9), low),
            _power(base, math.ceil(math.log(high, base) - 1e-9), high),
        )
    if not math.isfinite(high - low):
        # Wider than a float holds - from near the most negative float to
        # near the most positive - so no step fits: left as it is.
        return low, high
    for step in round_steps():
        if (high - low) / step <= NICE_TICKS:
            nice_low = _outward(low, step, math.floor, -1)
            nice_high = _outward(high, step, math.ceil, 1)
            # Below the smallest round step, both ends can round together.
            nice_high = max(nice_high, tidy(nice_low + step))
            # Rounding out past the largest float is infinite: the end
            # stays where the values put it.
            if not math.isfinite(nice_low):
                nice_low = low
            if not math.isfinite(nice_high):
                nice_high = high
            return nice_low, nice_high
    raise AssertionError("unreachable")  # pragma: no cover


def _power(base: float, exponent: int, end: float) -> float:
    """``base`` to ``exponent``, a log axis's round end - or ``end`` as it
    is, where that power is past what a float holds: ``10 ** -324`` is 0
    and ``10 ** 309`` overflows."""
    try:
        power = tidy(base**exponent)
    except OverflowError:
        return end
    return power if 0 < power < math.inf else end


def _outward(
    value: float, step: float, rounding: Callable[[float], int], way: int
) -> float:
    """``value`` rounded to a multiple of ``step``, away from the middle.

    A little slack absorbs float noise - 0.30000000000000004 is a multiple
    of 0.1 - but never takes the end past a value it must hold.
    """
    end = tidy(rounding(value / step - way * 1e-9) * step)
    if (end - value) * way < 0 and not math.isclose(end, value, rel_tol=1e-9):
        end = tidy(end + way * step)
    return end
