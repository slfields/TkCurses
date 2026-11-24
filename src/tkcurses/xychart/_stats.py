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

"""The legend's statistics: figures about one series' values. Pure.

Kibana's legend statistics, by Tk-style names. They are worked out over
the values a series draws - after ``missing`` has filled what it fills,
before stacking - in one pass over them: a running sum, count, least and
greatest, the first and last, and the variance by Welford's method
(B. P. Welford, "Note on a Method for Calculating Corrected Sums of
Squares and Products", *Technometrics* 4(3), 1962), which does not lose
precision as a sum of squares does. The median sorts the values it
collected on the way.

A value missing, ``None``, counts only for ``first`` and ``last``,
which are the first and last values whatever they are; every other
figure is of the values there are, and is ``None`` when there are none.
A figure past the largest float - the sum of two values near it, say -
is ``None`` too, rather than an infinity no one can read.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

__all__ = ["LABELS", "STATISTICS", "statistics"]

#: Every statistic, in Kibana's order.
STATISTICS = (
    "average",
    "median",
    "min",
    "max",
    "range",
    "last",
    "lastnonnull",
    "first",
    "firstnonnull",
    "difference",
    "differencepercent",
    "sum",
    "count",
    "distinctcount",
    "variance",
    "stddev",
)

#: What the legend writes before each figure.
LABELS = {
    "average": "avg",
    "median": "median",
    "min": "min",
    "max": "max",
    "range": "range",
    "last": "last",
    "lastnonnull": "last known",
    "first": "first",
    "firstnonnull": "first known",
    "difference": "diff",
    "differencepercent": "diff",
    "sum": "sum",
    "count": "count",
    "distinctcount": "distinct",
    "variance": "var",
    "stddev": "sd",
}


def statistics(
    values: Sequence[float | None], wanted: Iterable[str]
) -> dict[str, float | None]:
    """Each statistic in ``wanted`` over ``values``, ``None`` where there
    is nothing to work it out from.

    ``difference`` is the last value known less the first, and
    ``differencepercent`` that as a percentage of the first's size;
    ``variance`` and ``stddev`` are of the values as a whole population,
    as Kibana's are.
    """
    count = 0
    total = 0.0  # may overflow; checked at the end
    mean = 0.0
    squares = 0.0  # Welford's running sum of squared differences
    low = math.inf
    high = -math.inf
    first_known: float | None = None
    last_known: float | None = None
    seen: list[float] = []
    for value in values:
        if value is None:
            continue
        count += 1
        total += value
        delta = value - mean
        mean += delta / count
        squares += delta * (value - mean)
        low = min(low, value)
        high = max(high, value)
        if first_known is None:
            first_known = value
        last_known = value
        seen.append(value)
    known = count > 0
    figures: dict[str, float | None] = {
        "average": mean if known else None,
        "median": _median(seen) if known else None,
        "min": low if known else None,
        "max": high if known else None,
        "range": high - low if known else None,
        "last": values[-1] if values else None,
        "lastnonnull": last_known,
        "first": values[0] if values else None,
        "firstnonnull": first_known,
        "difference": (
            last_known - first_known
            if last_known is not None and first_known is not None
            else None
        ),
        "differencepercent": (
            (last_known - first_known) / abs(first_known) * 100
            if last_known is not None and first_known
            else None
        ),
        "sum": total if known else None,
        "count": float(count),
        "distinctcount": float(len(set(seen))),
        "variance": squares / count if known else None,
        "stddev": (
            math.sqrt(squares / count) if known and squares / count >= 0 else None
        ),
    }
    return {name: _finite(figures[name]) for name in wanted}


def _finite(figure: float | None) -> float | None:
    return figure if figure is not None and math.isfinite(figure) else None


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    both = ordered[middle - 1] + ordered[middle]
    if math.isfinite(both):
        return both / 2
    # Two values near the largest float: halved first, which would lose
    # the smallest ones, whose halves are 0.
    return ordered[middle - 1] / 2 + ordered[middle] / 2
