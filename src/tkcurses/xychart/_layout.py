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

"""Where an XY chart puts its parts, in cells. Pure.

From the top: a row for ``ylabel``, when there is one; the plot, with
the value axis's labels to its left and the axis line between; the time
axis's line under the plot; a row of its tick labels; and a row for
``xlabel`` and a time axis's context. The value labels' width depends on
how many fit the plot's height, so :func:`layout` takes the rows first
and asks for the width after.

A chart too small for a plot of :data:`MIN_PLOT` cells with its axes is
drawn without them, the whole area its plot.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tkcurses._charts.geometry import Rect

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["MIN_PLOT", "Layout", "layout"]

#: The smallest plot, columns by rows, worth giving up room for axes.
MIN_PLOT = (8, 2)


@dataclass(frozen=True, slots=True)
class Layout:
    """The chart's parts, in cells. With no axes, every row and column
    but the plot is ``None``."""

    plot: Rect
    #: The column of the value axis's line, left of the plot.
    axis_column: int | None = None
    #: The row of the x axis's line, under the plot.
    axis_row: int | None = None
    #: The x axis's tick labels.
    tick_row: int | None = None
    #: ``xlabel`` and a time axis's context.
    title_row: int | None = None
    #: ``ylabel``, above the value axis.
    ylabel_row: int | None = None

    @property
    def axes(self) -> bool:
        return self.axis_column is not None


def layout(
    width: int,
    height: int,
    *,
    ylabel: bool,
    ticklabels: bool,
    title: bool,
    label_width: Callable[[int], int],
) -> Layout:
    """The parts of a chart ``width`` by ``height`` cells.

    ``ylabel`` and ``title`` say whether those rows have anything in them;
    ``ticklabels`` whether the x axis has a row of labels. ``label_width``
    is how wide the value axis's labels are on a plot of so many rows.
    """
    bare = Layout(Rect(0, 0, max(0, width), max(0, height)))
    top = 1 if ylabel else 0
    below = 1 + (1 if ticklabels else 0) + (1 if title else 0)
    rows = height - top - below
    if rows < MIN_PLOT[1]:
        return bare
    labels = max(0, label_width(rows))
    columns = width - labels - 1
    if columns < MIN_PLOT[0]:
        return bare
    axis_row = top + rows
    tick_row = axis_row + 1 if ticklabels else None
    title_row = axis_row + (2 if ticklabels else 1) if title else None
    return Layout(
        plot=Rect(labels + 1, top, columns, rows),
        axis_column=labels,
        axis_row=axis_row,
        tick_row=tick_row,
        title_row=title_row,
        ylabel_row=0 if ylabel else None,
    )
