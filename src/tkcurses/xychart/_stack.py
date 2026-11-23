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

"""Stacking an XY chart's areas. Pure.

``stackmode`` is Kibana's: ``stacked`` puts each area on the ones before
it, ``percentage`` does the same with each x's total made 100, and
``unstacked`` draws each from zero. Only areas stack; a line is drawn at
its own values whatever the mode, on the same axis.

Areas stack at every x any of them has. At an x, each adds its value -
after missing values are filled - and one with no value there adds
nothing and has a gap, so the areas above it close up, as elastic-charts
draws a missing value in a stack. Positive values stack up from zero and
negative ones down from it, each side on its own, as d3's diverging
offset does, so a negative value never hides a positive one. A
percentage divides by the total of the values' sizes, and an x whose
total is zero is a gap in every area.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["STACK_MODES", "Band", "Layer", "stack"]

STACK_MODES = ("stacked", "percentage", "unstacked")


@dataclass(frozen=True, slots=True)
class Layer:
    """One series' values as drawn: what each was given, as it was fitted."""

    name: str
    kind: str
    xs: tuple[float, ...]
    ys: tuple[float | None, ...]
    #: Which of ``ys`` missing values filled in.
    filled: tuple[bool, ...]


@dataclass(frozen=True, slots=True)
class Band:
    """A series as drawn: its top at each x, and its bottom - ``None`` for
    the axis's zero, as an unstacked area and a line have. ``None`` in
    ``highs`` is a gap."""

    name: str
    kind: str
    xs: tuple[float, ...]
    highs: tuple[float | None, ...]
    lows: tuple[float, ...] | None
    filled: tuple[bool, ...]


def stack(layers: Sequence[Layer], mode: str = "stacked") -> list[Band]:
    """Each layer as drawn in ``mode``, in the same order.

    Raises:
        ValueError: If ``mode`` is not one of :data:`STACK_MODES`.
    """
    if mode not in STACK_MODES:
        raise ValueError(
            f'bad stackmode "{mode}": must be stacked, percentage or unstacked'
        )
    areas = [layer for layer in layers if layer.kind == "area"]
    if mode == "unstacked" or not areas:
        return [_alone(layer) for layer in layers]
    stacked = _stacked(areas, percentage=mode == "percentage")
    return [
        stacked[layer.name] if layer.kind == "area" else _alone(layer)
        for layer in layers
    ]


def _alone(layer: Layer) -> Band:
    return Band(layer.name, layer.kind, layer.xs, layer.ys, None, layer.filled)


def _stacked(areas: Sequence[Layer], *, percentage: bool) -> dict[str, Band]:
    xs = sorted({x for layer in areas for x in layer.xs})
    at = [dict(zip(layer.xs, layer.ys, strict=True)) for layer in areas]
    marks = [dict(zip(layer.xs, layer.filled, strict=True)) for layer in areas]
    highs: list[list[float | None]] = [[] for _ in areas]
    lows: list[list[float]] = [[] for _ in areas]
    for x in xs:
        values = [values.get(x) for values in at]
        total = sum(abs(v) for v in values if v is not None)
        if percentage and total == 0:
            for i in range(len(areas)):
                highs[i].append(None)
                lows[i].append(0.0)
            continue
        up = down = 0.0
        for i, value in enumerate(values):
            if value is None:
                highs[i].append(None)
                lows[i].append(up)
                continue
            # Divided first: 100 / total overflows for a tiny total.
            size = value / total * 100 if percentage else value
            if size >= 0:
                lows[i].append(up)
                up += size
                highs[i].append(up)
            else:
                lows[i].append(down)
                down += size
                highs[i].append(down)
    return {
        layer.name: Band(
            layer.name,
            layer.kind,
            tuple(xs),
            tuple(highs[i]),
            tuple(lows[i]),
            tuple(marks[i].get(x, False) for x in xs),
        )
        for i, layer in enumerate(areas)
    }
