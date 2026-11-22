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
"""Which shade each child takes, and which tiles are outlined. Pure.

A group's children are shades of its colour, so the group reads as one
region and its children can still be told apart. Shades are not dealt
out in order, since two children side by side could then match: each
child, largest first, takes the lowest shade none of its neighbours has.

Where shades cannot be told apart - a terminal of fewer than 256
colours, a palette that rounds them together, or no colour at all - the
tiles are *outlined* instead (:mod:`tkcurses.treemap._outline`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from tkcurses._charts.color import BLACK, WHITE, mix

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from tkcurses._charts.color import RGB
    from tkcurses._charts.geometry import Rect

__all__ = [
    "OUTLINE_MODES",
    "SHADES",
    "adjacent",
    "assign",
    "outlined_levels",
    "shades_of",
]

OutlineMode = Literal["auto", "on", "off"]
OUTLINE_MODES: tuple[OutlineMode, ...] = ("auto", "on", "off")

#: Each shade as ``(toward, fraction)``: shade 0 is the colour itself.
SHADES: tuple[tuple[RGB, float], ...] = (
    (BLACK, 0.0),
    (BLACK, 0.25),
    (WHITE, 0.30),
    (BLACK, 0.50),
)

#: Fewer distinct shades than this, after the palette, and a group is
#: outlined - unless it has fewer children than this to tell apart.
MIN_DISTINCT = 3
#: Colour depths, as terminfo counts them.
EXTENDED = 256


def shades_of(color: RGB) -> tuple[RGB, ...]:
    """The shades of ``color``, in :data:`SHADES` order."""
    return tuple(mix(color, toward, fraction) for toward, fraction in SHADES)


def _touch(a: Rect, b: Rect) -> bool:
    """Whether ``a`` and ``b`` share a stretch of edge, not just a corner."""
    across = min(a.x + a.width, b.x + b.width) - max(a.x, b.x)
    down = min(a.y + a.height, b.y + b.height) - max(a.y, b.y)
    side_by_side = (a.x + a.width == b.x or b.x + b.width == a.x) and down > 0
    stacked = (a.y + a.height == b.y or b.y + b.height == a.y) and across > 0
    return side_by_side or stacked


def adjacent(rects: Sequence[Rect]) -> list[set[int]]:
    """For each rectangle, the indices of those sharing an edge with it."""
    near: list[set[int]] = [set() for _ in rects]
    for i, a in enumerate(rects):
        for j in range(i + 1, len(rects)):
            if _touch(a, rects[j]):
                near[i].add(j)
                near[j].add(i)
    return near


def assign(rects: Sequence[Rect], count: int = len(SHADES)) -> list[int]:
    """A shade for each of ``rects``, given largest first.

    Each takes the lowest of ``count`` shades no neighbour has yet. When
    all are taken - rare, since it needs five tiles round one - it takes
    the shade of its smallest neighbour, the one a reader least confuses
    it with.
    """
    near = adjacent(rects)
    shades: list[int | None] = [None] * len(rects)
    for i in range(len(rects)):
        taken = {shades[j] for j in near[i] if shades[j] is not None}
        free = [shade for shade in range(count) if shade not in taken]
        if free:
            shades[i] = free[0]
        else:
            smallest = min(
                (j for j in near[i] if shades[j] is not None),
                key=lambda j: (rects[j].width * rects[j].height, j),
            )
            shades[i] = shades[smallest]
    return [shade or 0 for shade in shades]


def outlined_levels(
    mode: OutlineMode,
    depth: int,
    groups: Mapping[str, int],
    distinct: Mapping[str, int],
) -> frozenset[str]:
    """Which levels are drawn outlined: ``""`` for the top level, a group's
    iid for its children.

    Args:
        mode: ``on`` outlines everything, ``off`` nothing; ``auto`` decides.
        depth: The terminal's colours: 0 for none, then 8, 16, 256, or more.
        groups: Each group's iid and how many children it has.
        distinct: For each group, how many of its shades the terminal can
            show apart.

    ``auto`` outlines everything without colour; every group below 256
    colours; and at 256 or more, a group whose shades come out fewer than
    :data:`MIN_DISTINCT`, or than its children, whichever is smaller.
    """
    if mode == "off":
        return frozenset()
    if mode == "on" or depth <= 0:
        return frozenset({"", *groups})
    if depth < EXTENDED:
        return frozenset(groups)
    return frozenset(
        group
        for group, children in groups.items()
        if distinct.get(group, 0) < min(MIN_DISTINCT, children)
    )
