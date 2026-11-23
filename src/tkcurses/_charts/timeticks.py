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

"""Ticks on a time axis: steps a clock or a calendar reads, and labels to
match. Pure.

The steps run from a second to centuries: 1, 2, 5, 10, 15 and 30 seconds
and minutes; 1, 2, 3, 6 and 12 hours; 1 and 2 days; weeks, starting on
Monday; 1, 2, 3 and 6 months; and 1, 2 and 5 times a power of ten years.
:func:`time_ticks` takes the smallest whose labels all fit. Ticks fall
on local time - midnight, the hour, the first of the month - counted on
the calendar, so a day across a change of clocks is still one step.

A label says only what changes at its step: ``14:05`` for minutes,
``Nov 23`` for days, ``Nov`` for months, ``2026`` for years. Where a
larger unit turns over, the tick says that instead - ``Nov 24`` at
midnight, ``2027`` in January - and the *context*, written once, says
the larger unit the first tick is in.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tkcurses._charts.scale import ValueRange, label_start
from tkcurses._core.cells import cells

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ["STEPS", "TimeTicks", "time_ticks"]

_MINUTE = 60
_HOUR = 3600
_DAY = 86400

#: Every step, smallest first: a unit, how many of it, and roughly how
#: long that is in seconds.
STEPS: tuple[tuple[str, int, float], ...] = (
    *(("second", n, n) for n in (1, 2, 5, 10, 15, 30)),
    *(("minute", n, n * _MINUTE) for n in (1, 2, 5, 10, 15, 30)),
    *(("hour", n, n * _HOUR) for n in (1, 2, 3, 6, 12)),
    *(("day", n, n * _DAY) for n in (1, 2)),
    ("week", 1, 7 * _DAY),
    *(("month", n, n * 30.44 * _DAY) for n in (1, 2, 3, 6)),
    *(
        ("year", m * 10**e, m * 10**e * 365.25 * _DAY)
        for e in range(4)
        for m in (1, 2, 5)
    ),
)


@dataclass(frozen=True, slots=True)
class TimeTicks:
    """Ticks on a time axis, their labels, the step's unit, and the larger
    unit the first tick is in, written once beside the axis."""

    values: tuple[float, ...] = ()
    labels: tuple[str, ...] = ()
    unit: str = ""
    context: str = ""


def time_ticks(low: float, high: float, length: int, gap: int = 2) -> TimeTicks:
    """The most ticks from ``low`` to ``high`` (epoch seconds) whose labels
    fit along an axis ``length`` cells long, at least ``gap`` apart.
    None when not even one fits, or the range is empty."""
    if length <= 0 or not high > low:
        return TimeTicks()
    span = ValueRange(high, low)
    for unit, count, seconds in STEPS:
        if (high - low) / seconds + 1 > length:
            continue
        values = list(_ticks(unit, count, low, high))
        labels = [_label(unit, value) for value in values]
        if _fit(span, values, labels, length, gap):
            context = _context(unit, values[0]) if values else ""
            return TimeTicks(tuple(values), tuple(labels), unit, context)
    return TimeTicks()


def _fit(
    span: ValueRange, values: list[float], labels: list[str], length: int, gap: int
) -> bool:
    end = -gap
    for value, label in zip(values, labels, strict=True):
        width = cells(label)
        position = span.position(value)
        if position is None or width > length:
            return False
        start = label_start(position, width, length)
        if start < end + gap:
            return False
        end = start + width
    return True


def _ticks(unit: str, count: int, low: float, high: float) -> Iterator[float]:
    """Each tick from ``low`` to ``high``, in local time, ascending."""
    at = _floor(unit, count, _dt.datetime.fromtimestamp(low))
    last = None
    while True:
        stamp = at.timestamp()
        if stamp > high:
            return
        if stamp >= low and stamp != last:
            yield stamp
            last = stamp
        at = _advance(unit, count, at)


def _floor(unit: str, count: int, at: _dt.datetime) -> _dt.datetime:
    """The tick at or before ``at``."""
    at = at.replace(microsecond=0)
    if unit == "second":
        return at.replace(second=at.second - at.second % count)
    at = at.replace(second=0)
    if unit == "minute":
        return at.replace(minute=at.minute - at.minute % count)
    at = at.replace(minute=0)
    if unit == "hour":
        return at.replace(hour=at.hour - at.hour % count)
    at = at.replace(hour=0)
    if unit == "day":
        return at
    if unit == "week":
        return at - _dt.timedelta(days=at.weekday())
    at = at.replace(day=1)
    if unit == "month":
        return at.replace(month=at.month - (at.month - 1) % count)
    year = max(_dt.MINYEAR, at.year - at.year % count)
    return at.replace(year=year, month=1)


def _advance(unit: str, count: int, at: _dt.datetime) -> _dt.datetime:
    """The tick after ``at``, counted on the calendar."""
    if unit in ("second", "minute", "hour"):
        return at + _dt.timedelta(**{f"{unit}s": count})
    if unit in ("day", "week"):
        days = count * (7 if unit == "week" else 1)
        # Midnight again on the calendar, whatever the clocks did.
        return (at + _dt.timedelta(days=days)).replace(hour=0, minute=0, second=0)
    if unit == "month":
        months = at.month - 1 + count
        return at.replace(year=at.year + months // 12, month=months % 12 + 1)
    return at.replace(year=at.year + count)


def _label(unit: str, stamp: float) -> str:
    at = _dt.datetime.fromtimestamp(stamp)
    day = f"{at:%b} {at.day}"
    if unit == "second":
        return day if (at.hour, at.minute, at.second) == (0, 0, 0) else f"{at:%H:%M:%S}"
    if unit in ("minute", "hour"):
        return day if (at.hour, at.minute) == (0, 0) else f"{at:%H:%M}"
    if unit in ("day", "week"):
        return str(at.year) if (at.month, at.day) == (1, 1) else day
    if unit == "month":
        return str(at.year) if at.month == 1 else f"{at:%b}"
    return str(at.year)


def _context(unit: str, stamp: float) -> str:
    at = _dt.datetime.fromtimestamp(stamp)
    if unit in ("second", "minute", "hour"):
        return f"{at:%b} {at.day}, {at.year}"
    if unit in ("day", "week", "month"):
        return str(at.year)
    return ""
