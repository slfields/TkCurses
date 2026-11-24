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

"""An XY chart's series: named lists of points. Pure.

A series is a name, a kind (``line`` or ``area``) and points ``(x, y)``,
kept sorted by x. ``y`` is a finite number, or ``None`` for a missing
value. ``x`` is a finite number or a time - a ``datetime`` (naive is
local time) or a ``date`` - held as epoch seconds; every point of every
series is the same kind, which the first point decides until no series
has any. An x given twice in one series keeps the later ``y``, as a
re-sent bucket would.

Errors use Treeview's words, ``Series X not found`` and ``Series X
already exists``, and are ``ValueError``; the widget turns them into
``TclError``.
"""

from __future__ import annotations

import bisect
import datetime as _dt
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "KINDS",
    "Model",
    "Series",
    "XKind",
    "checked_kind",
    "checked_x",
    "checked_y",
]

XKind = Literal["number", "time"]
#: What a series draws as.
KINDS = ("line", "area")


@dataclass(slots=True)
class Series:
    """One series: its name, how it draws, and its points sorted by x."""

    name: str
    kind: str = "line"
    #: The name the legend and readout show; :attr:`name` when empty.
    text: str = ""
    #: A colour spec, or ``""`` for the next of the chart's ``colors``.
    color: str = ""
    description: str = ""
    #: Left out of the drawing, the stack, the scale and the readout.
    hidden: bool = False
    xs: list[float] = field(default_factory=list)
    ys: list[float | None] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.text or self.name

    def points(self) -> list[tuple[float, float | None]]:
        return list(zip(self.xs, self.ys, strict=True))

    def put(self, x: float, y: float | None) -> None:
        """Add a point in x order; one at an x already there replaces it."""
        if not self.xs or x > self.xs[-1]:  # the usual case: appending
            self.xs.append(x)
            self.ys.append(y)
            return
        at = bisect.bisect_left(self.xs, x)
        if at < len(self.xs) and self.xs[at] == x:
            self.ys[at] = y
        else:
            self.xs.insert(at, x)
            self.ys.insert(at, y)


def checked_kind(value: Any) -> str:
    kind = str(value)
    if kind not in KINDS:
        raise ValueError(f'bad kind "{value}": must be line or area')
    return kind


def checked_x(value: Any) -> tuple[float, XKind]:
    """``value`` as an x: epoch seconds for a time, or a finite number.

    Raises:
        ValueError: If it is neither, or is NaN or an infinity.
    """
    if isinstance(value, _dt.datetime):
        return value.timestamp(), "time"
    if isinstance(value, _dt.date):
        return _dt.datetime.combine(value, _dt.time()).timestamp(), "time"
    return _finite(value, "x"), "number"


def checked_y(value: Any) -> float | None:
    """``value`` as a y: a finite number, or ``None`` for a missing one."""
    if value is None:
        return None
    return _finite(value, "y")


def _finite(value: Any, axis: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f'expected a number for {axis} but got "{value}"')
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'expected a number for {axis} but got "{value}"') from None
    if not math.isfinite(number):
        raise ValueError(f'{axis} must be finite, not "{value}"')
    return number


def _pairs(points: Iterable[Any]) -> list[tuple[Any, Any]]:
    pairs = []
    for point in points:
        try:
            x, y = point
        except (TypeError, ValueError):
            raise ValueError(f'expected a point (x, y) but got "{point}"') from None
        pairs.append((x, y))
    return pairs


class Model:
    """The series of one chart, in drawing order.

    ``version`` goes up on every change, so what was worked out for one
    version can be reused until the next.
    """

    def __init__(self) -> None:
        self._series: dict[str, Series] = {}
        self.version = 0

    # ------------------------------------------------------------ reading

    def names(self) -> list[str]:
        """Every series' name, in drawing order."""
        return list(self._series)

    def get(self, name: str) -> Series:
        try:
            return self._series[name]
        except KeyError:
            raise ValueError(f"Series {name} not found") from None

    def exists(self, name: str) -> bool:
        return name in self._series

    def shown(self) -> list[Series]:
        """The series not hidden, in drawing order."""
        return [series for series in self._series.values() if not series.hidden]

    @property
    def xkind(self) -> XKind | None:
        """Whether x is a number or a time; ``None`` while no series has a
        point."""
        return self._xkind if any(s.xs for s in self._series.values()) else None

    def xs(self) -> list[float]:
        """Every x of the shown series, sorted, each once."""
        return sorted({x for series in self.shown() for x in series.xs})

    # ------------------------------------------------------------ changing

    def add(
        self,
        name: str,
        points: Iterable[Any] = (),
        *,
        kind: Any = "line",
        text: str = "",
        color: str = "",
        description: str = "",
    ) -> None:
        """Add a series, last in the drawing order."""
        name = str(name)
        if name in self._series:
            raise ValueError(f"Series {name} already exists")
        series = Series(
            name, checked_kind(kind), str(text), str(color), str(description)
        )
        checked = self._checked(points)
        self._series[name] = series
        for x, y in checked:
            series.put(x, y)
        self.version += 1

    def set(self, name: str, points: Iterable[Any]) -> None:
        """Replace a series' points."""
        series = self.get(name)
        checked = self._checked(points, ignore=series)
        series.xs.clear()
        series.ys.clear()
        for x, y in checked:
            series.put(x, y)
        self.version += 1

    def append(self, name: str, *points: Any) -> None:
        """Add points to a series; one at an x it has replaces that one."""
        series = self.get(name)
        for x, y in self._checked(points):
            series.put(x, y)
        self.version += 1

    def configure(
        self,
        name: str,
        *,
        kind: Any = None,
        text: str | None = None,
        color: str | None = None,
        description: str | None = None,
        hidden: bool | None = None,
    ) -> None:
        """Change a series; ``None`` leaves an option as it is."""
        series = self.get(name)
        new_kind = series.kind if kind is None else checked_kind(kind)
        series.kind = new_kind
        if text is not None:
            series.text = str(text)
        if color is not None:
            series.color = str(color)
        if description is not None:
            series.description = str(description)
        if hidden is not None:
            series.hidden = bool(hidden)
        self.version += 1

    def delete(self, *names: str) -> None:
        """Remove series. Every name is checked before any is removed, so a
        mistake in the list leaves the chart as it was."""
        for name in names:
            self.get(name)
        for name in names:
            self._series.pop(name, None)
        self.version += 1

    # ------------------------------------------------------------- checks

    _xkind: XKind = "number"

    def _checked(
        self, points: Iterable[Any], ignore: Series | None = None
    ) -> list[tuple[float, float | None]]:
        """Every point checked, before any is kept: all one kind of x, and
        the kind the chart already has. ``ignore`` is a series whose points
        are being replaced, so they do not decide the kind."""
        others = any(s.xs for s in self._series.values() if s is not ignore)
        current: XKind | None = self._xkind if others else None
        checked = []
        for x, y in _pairs(points):
            value, kind = checked_x(x)
            if current is None:
                current = kind
            elif kind != current:
                raise ValueError(f'x is a {current} in this chart, not a {kind}: "{x}"')
            checked.append((value, checked_y(y)))
        if current is not None:
            self._xkind = current
        return checked
