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

"""Rectangles of character cells, and cutting regions off them. Pure."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Rect"]


@dataclass(frozen=True, slots=True)
class Rect:
    """A rectangle in cells, relative to the widget's window."""

    x: int
    y: int
    width: int
    height: int

    @property
    def empty(self) -> bool:
        return self.width <= 0 or self.height <= 0

    def inset(self, cells: int) -> Rect:
        """This rect with ``cells`` taken off every side."""
        return Rect(
            self.x + cells,
            self.y + cells,
            max(0, self.width - 2 * cells),
            max(0, self.height - 2 * cells),
        )

    def take_top(self, rows: int) -> tuple[Rect, Rect]:
        """``(taken, rest)`` with up to ``rows`` taken from the top."""
        rows = min(max(0, rows), self.height)
        return (
            Rect(self.x, self.y, self.width, rows),
            Rect(self.x, self.y + rows, self.width, self.height - rows),
        )

    def take_bottom(self, rows: int) -> tuple[Rect, Rect]:
        """``(taken, rest)`` with up to ``rows`` taken from the bottom."""
        rows = min(max(0, rows), self.height)
        return (
            Rect(self.x, self.y + self.height - rows, self.width, rows),
            Rect(self.x, self.y, self.width, self.height - rows),
        )

    def take_left(self, columns: int) -> tuple[Rect, Rect]:
        """``(taken, rest)`` with up to ``columns`` taken from the left."""
        columns = min(max(0, columns), self.width)
        return (
            Rect(self.x, self.y, columns, self.height),
            Rect(self.x + columns, self.y, self.width - columns, self.height),
        )

    def take_right(self, columns: int) -> tuple[Rect, Rect]:
        """``(taken, rest)`` with up to ``columns`` taken from the right."""
        columns = min(max(0, columns), self.width)
        return (
            Rect(self.x + self.width - columns, self.y, columns, self.height),
            Rect(self.x, self.y, self.width - columns, self.height),
        )
