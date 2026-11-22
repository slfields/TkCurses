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

"""Number format: how the axis and the readout write a value.

A value is rounded to a number of significant digits, optionally written
with a fixed count of decimals, and given its units before or after. It is
scaled along a *ladder*: SI prefixes (k, M, G up, when its whole part needs
more digits than it has; m, µ, n down, for a unit that can take them, when
it is below 1), binary prefixes (Ki, Mi, Gi), or time units (ns, µs, ms, s,
min, h, d - the largest the value reaches at least one of). Rounding never
carries a value over the graph's maximum: 99.97 on a graph whose maximum is
99.97 is never written ``100``. Pure: errors are ``ValueError``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Literal

from tkcurses._core.cells import cells

Placement = Literal["suffix", "prefix"]
Rounding = Literal["nearest", "down", "up"]
UnitScale = Literal["si", "binary", "time", "none"]

PLACEMENTS = ("suffix", "prefix")
ROUNDINGS = ("nearest", "down", "up")
UNIT_SCALES = ("si", "binary", "time", "none")

#: Significant digits when none are given: as many as ``{:g}`` writes.
DEFAULT_DIGITS = 6
#: The most significant digits or decimals asked for; a float holds ~15.
MAX_DIGITS = 15

#: A ladder: each rung's label and its size in the ladder's own unit.
Ladder = tuple[tuple[str, Decimal], ...]

_SI: Ladder = tuple(
    (label, Decimal(1000) ** (index - 4))
    for index, label in enumerate(
        ("p", "n", "µ", "m", "", "k", "M", "G", "T", "P", "E")
    )
)
_SI_ONE = 4
_BINARY: Ladder = tuple(
    (label, Decimal(1024) ** index)
    for index, label in enumerate(("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei"))
)
_NONE: Ladder = (("", Decimal(1)),)
#: Time units, in seconds. They stop at days: weeks and months are not
#: lengths people read off an axis.
_TIME: Ladder = (
    ("ns", Decimal("1e-9")),
    ("µs", Decimal("1e-6")),
    ("ms", Decimal("1e-3")),
    ("s", Decimal(1)),
    ("min", Decimal(60)),
    ("h", Decimal(3600)),
    ("d", Decimal(86400)),
)
#: What ``units`` may name with ``unitscale="time"``.
TIME_UNITS = {label: index for index, (label, _) in enumerate(_TIME)} | {"us": 1}
#: Units that never take a smaller SI prefix: 500m% means nothing.
_NO_DOWN = frozenset({"", "%"})
_MODES = {"nearest": ROUND_HALF_UP, "down": ROUND_FLOOR, "up": ROUND_CEILING}


@dataclass(frozen=True, slots=True)
class NumberFormat:
    """How to write a value. The defaults write ``50``, ``2.5``, ``1.5k``."""

    units: str = ""
    placement: Placement = "suffix"
    #: A space between the number and a suffix: ``1.2 kB`` rather than
    #: ``1.2kB``. A prefix (a currency) is always written against it.
    space: bool = False
    digits: int | None = None
    #: A fixed count of decimals, ``5.0`` and ``12.3``; None trims them.
    decimals: int | None = None
    rounding: Rounding = "nearest"
    unitscale: UnitScale = "si"

    def __post_init__(self) -> None:
        if self.placement not in PLACEMENTS:
            raise ValueError(f'bad placement "{self.placement}"')
        if self.rounding not in ROUNDINGS:
            raise ValueError(f'bad rounding "{self.rounding}"')
        if self.unitscale not in UNIT_SCALES:
            raise ValueError(f'bad unitscale "{self.unitscale}"')
        if self.digits is not None and not 1 <= self.digits <= MAX_DIGITS:
            raise ValueError(f"digits must be 1 to {MAX_DIGITS}, not {self.digits}")
        if self.decimals is not None and not 0 <= self.decimals <= MAX_DIGITS:
            raise ValueError(f"decimals must be 0 to {MAX_DIGITS}, not {self.decimals}")
        if self.unitscale == "time" and self.units not in TIME_UNITS:
            names = ", ".join(label for label, _ in _TIME)
            raise ValueError(
                f'unitscale="time" needs units naming a time unit ({names}),'
                f" not {self.units!r}"
            )

    @property
    def steps(self) -> float | Literal["decimal", "binary"]:
        """What a round number is in this format: see ``scale.Steps``."""
        if self.unitscale == "time":
            return float(_TIME[TIME_UNITS[self.units]][1])
        return "binary" if self.unitscale == "binary" else "decimal"

    @property
    def time_unit_seconds(self) -> float | None:
        """For a time scale, how many seconds one unit of the data is."""
        if self.unitscale != "time":
            return None
        return float(_TIME[TIME_UNITS[self.units]][1])

    def format(self, value: float, ceiling: float | None = None) -> str:
        """``value`` written out. If ``value`` is at most ``ceiling``, the
        text never shows more than ``ceiling``: rounding that would carry it
        over rounds down instead."""
        if not math.isfinite(value):
            raise ValueError(f"cannot format {value}")
        number, prefix = self._number(value, ceiling)
        return self._with_units(number, prefix)

    def plain(self, value: float, ceiling: float | None = None) -> str:
        """``value`` with its scale prefix but without the units."""
        number, prefix = self._number(value, ceiling)
        return number + prefix

    # ------------------------------------------------------------------

    def _number(self, value: float, ceiling: float | None) -> tuple[str, str]:
        mode = self.rounding
        if ceiling is not None and value <= ceiling:
            number, prefix, shown = self._rounded(value, mode)
            if shown > ceiling and mode != "down":
                number, prefix, shown = self._rounded(value, "down")
            return number, prefix
        number, prefix, _ = self._rounded(value, mode)
        return number, prefix

    def _ladder(self) -> tuple[Ladder, int, int, int]:
        """The ladder, the data unit's rung, and the lowest and highest
        rungs a value may be written at."""
        if self.unitscale == "time":
            return _TIME, TIME_UNITS[self.units], 0, len(_TIME) - 1
        if self.unitscale == "binary":
            return _BINARY, 0, 0, len(_BINARY) - 1
        if self.unitscale == "si":
            down = self.placement == "suffix" and self.units not in _NO_DOWN
            return _SI, _SI_ONE, 0 if down else _SI_ONE, len(_SI) - 1
        return _NONE, 0, 0, 0

    def _rounded(self, value: float, mode: Rounding) -> tuple[str, str, float]:
        """The digits, the rung's label, and the value they stand for, in
        the data's units."""
        digits = self.digits or DEFAULT_DIGITS
        ladder, start, low, high = self._ladder()
        base = Decimal(repr(value)) * ladder[start][1]
        size = abs(base)
        rung = start
        if self.unitscale == "time" or (size and size < ladder[start][1]):
            # Time: the largest unit it reaches one of. Below 1, where a
            # smaller prefix is allowed: the fewest digits, 12m not 0.012.
            reached = [i for i in range(low, high + 1) if size >= ladder[i][1]]
            if size and self.unitscale == "time":
                rung = reached[-1] if reached else low
            elif size:
                rung = max([i for i in reached if i <= start], default=low)
        while True:
            rounded = self._round(base / ladder[rung][1], digits, mode)
            step = ladder[rung + 1][1] / ladder[rung][1] if rung < high else None
            whole = len(str(abs(int(rounded)))) if rounded else 1
            if step is not None and (
                # Rounding reached the next rung: 999.6m is 1, 59.99 s 1 min.
                (abs(rounded) >= step and (rung != start or self.unitscale == "time"))
                # Above the data's unit, the SI rule: scaled when the whole
                # part outgrows the digits, then as far as it goes.
                or (rung >= start and self.unitscale != "time" and whole > digits)
            ):
                rung += 1
                continue
            shown = float(rounded * ladder[rung][1] / ladder[start][1])
            return self._text(rounded), ladder[rung][0], shown

    def _round(self, value: Decimal, digits: int, mode: Rounding) -> Decimal:
        if value == 0:
            return Decimal(0)
        exponent = value.copy_abs().adjusted() - digits + 1
        if self.decimals is not None:
            exponent = max(exponent, -self.decimals)
        quantum = Decimal(1).scaleb(exponent)
        rounded = value.quantize(quantum, rounding=_MODES[mode])
        # Rounding can add a digit (9.99 -> 10.0); quantize again at the new
        # size so the count of significant digits holds.
        if rounded and rounded.copy_abs().adjusted() > value.copy_abs().adjusted():
            exponent = rounded.copy_abs().adjusted() - digits + 1
            if self.decimals is not None:
                exponent = max(exponent, -self.decimals)
            rounded = rounded.quantize(
                Decimal(1).scaleb(exponent), rounding=_MODES[mode]
            )
        return rounded

    def _text(self, rounded: Decimal) -> str:
        if self.decimals is not None:
            text = f"{rounded:.{self.decimals}f}"
        else:
            text = f"{rounded:f}"
            if "." in text:
                text = text.rstrip("0").rstrip(".")
        if text.startswith("-") and float(text) == 0:
            text = text[1:]
        return text

    def _with_units(self, number: str, prefix: str) -> str:
        if self.unitscale == "time":
            # The rung is the whole unit: 1.5 min, not 1.5 minms.
            return f"{number}{' ' if self.space else ''}{prefix}"
        if self.placement == "prefix":
            sign = "-" if number.startswith("-") else ""
            return f"{sign}{self.units}{number.lstrip('-')}{prefix}"
        after = prefix + self.units
        gap = " " if self.space and after else ""
        return f"{number}{gap}{after}"


def widest(fmt: NumberFormat, maximum: float) -> int:
    """The most cells a value from 0 to ``maximum`` takes, so a column made
    for it rarely has to cut one short."""
    samples = {0.0, maximum}
    samples.update(maximum * step / 256 for step in range(257))
    # Just under each power of ten and each prefix step down to a ten
    # thousandth of the maximum, where the most digits are written before
    # the value rounds up, gains a digit or scales.
    floor = maximum / 10_000
    for exponent in range(-MAX_DIGITS, 20):
        edges = [10.0**exponent, 1024.0 ** max(0, exponent // 3)]
        if fmt.time_unit_seconds:
            edges += [60 ** max(0, exponent) / fmt.time_unit_seconds]
        for edge in edges:
            for near in (edge * 0.9999999, edge * 0.99):
                if floor <= near <= maximum:
                    samples.add(near)
    return max(cells(fmt.format(sample, maximum)) for sample in samples)


def for_readout(fmt: NumberFormat) -> NumberFormat:
    """The readout's format: ``fmt``, but when neither digits nor decimals
    is given, whole numbers, as the readout has always written them - or,
    on a time scale, where whole units would write 1.5 min as 2 min, three
    significant digits."""
    if fmt.digits is None and fmt.decimals is None:
        time = fmt.unitscale == "time"
        return NumberFormat(
            units=fmt.units,
            placement=fmt.placement,
            space=fmt.space,
            digits=3 if time else None,
            decimals=None if time else 0,
            rounding=fmt.rounding,
            unitscale=fmt.unitscale,
        )
    return fmt
