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

"""Widgets laid out by the widget they are embedded in.

A Canvas's window items and a Text's embedded windows are geometry managers
of their own in Tk: the canvas or the text decides where each window goes,
from an item's coordinates or a character's place, and moves it as the view
scrolls. Here that is one more layout beside pack, grid, place and a paned
window's panes, applied after them, and it asks its host for every rectangle
rather than keeping options of its own - the host is the only thing that
knows where its content is.

The host answers two calls:

``_embedded_rect(widget, area)``
    Where ``widget`` goes, in screen cells, or None to take it off the
    screen: it is hidden, or wholly out of view.
``_embedded_lost(widget)``
    ``widget`` has left - packed elsewhere, given to another host, or
    destroyed - so whatever held it no longer does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tkcurses._core.geometry import Rect, Size

if TYPE_CHECKING:
    from collections.abc import Sequence


class EmbedLayout:
    """The children one widget positions itself, in the order they came."""

    #: An embedded window makes no claim on its host's size: a canvas or a
    #: text keeps the size it was configured with, as in Tk.
    propagates = False

    def __init__(self, host: Any) -> None:
        self._host = host
        self._order: list[Any] = []

    def add(self, widget: Any) -> None:
        """Start laying ``widget`` out; a second add changes nothing."""
        if widget not in self._order:
            self._order.append(widget)

    def requested(self, container: object) -> Size:  # noqa: ARG002
        """Nothing: see :attr:`propagates`."""
        return Size(0, 0)

    def apply(self, container: Any, area: Rect) -> None:
        """Put each child where its host says, or take it off the screen."""
        for widget in list(self._order):
            rect = container._embedded_rect(widget, area)
            if rect is None or rect.width <= 0 or rect.height <= 0:
                if widget._mapped:
                    widget._unmap()
                continue
            master = widget.master
            origin_x = master.winfo_rootx() if master is not None else 0
            origin_y = master.winfo_rooty() if master is not None else 0
            widget._allocate(
                Rect(rect.x - origin_x, rect.y - origin_y, rect.width, rect.height)
            )
            if not widget._mapped:
                widget._map()

    def slaves(self, container: object) -> Sequence[Any]:  # noqa: ARG002
        """The embedded children, in the order they were embedded."""
        return list(self._order)

    def remove(self, widget: Any) -> None:
        """Stop laying ``widget`` out, and tell the host it has gone."""
        if widget in self._order:
            self._order.remove(widget)
            self._host._embedded_lost(widget)
