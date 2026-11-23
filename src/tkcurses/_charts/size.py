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

"""A chart's size: ``width`` and ``height`` each in cells or a share of
the terminal, and a natural size on an axis not given. Shared by the
chart widgets, so their size rules are one piece of code.

A percentage, ``"50%"``, is of the *terminal*, kept as written so it reads
back that way. While either axis is one, :class:`ScreenSize` binds the
root's ``<Configure>`` and has the widget ask again after each resize.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from tkcurses import TclError, _signed_distance

if TYPE_CHECKING:
    from collections.abc import Callable

    from tkcurses import Event

__all__ = ["ScreenSize", "cells", "dimension", "is_share"]


def dimension(widget: Any, value: Any) -> Any:
    """``width`` or ``height``: a distance in cells, as any Frame's, or a
    percentage of the screen, ``"50%"``, kept as written."""
    if isinstance(value, str) and value.strip().endswith("%"):
        try:
            share = float(value.strip()[:-1])
        except ValueError:
            share = math.nan
        if not 0 < share <= 100:  # also refuses nan
            raise TclError(
                "expected screen distance or percentage above 0 and at most 100"
                f' but got "{value}"'
            )
        return f"{share:g}%"
    return _signed_distance(widget, value)


def cells(value: Any, screen: int) -> int:
    """A ``width`` or ``height`` in cells against a ``screen`` that long;
    0 for one not given."""
    if is_share(value):
        return max(1, round(screen * float(value[:-1]) / 100))
    return max(0, int(value))


def is_share(value: Any) -> bool:
    """Whether a checked ``width`` or ``height`` is a share of the screen."""
    return isinstance(value, str) and value.endswith("%")


class ScreenSize:
    """The cells a chart asks for, and the binding that keeps a share of
    the terminal up to date.

    Unlike a Frame's, an axis left out is not left to children: a chart
    has none, and would ask for nothing on it, so it asks for ``natural``.
    """

    def __init__(
        self, widget: Any, natural: tuple[int, int], ask: Callable[[], None]
    ) -> None:
        self._widget = widget
        self.natural = natural
        #: Called to ask again, after the terminal is resized.
        self._ask = ask
        #: The root's ``<Configure>`` binding, while a size is a percentage.
        self.binding: str | None = None

    def requested(self) -> tuple[int, int]:
        """``width`` by ``height`` in cells, the natural size on an axis not
        given; and following the terminal from now on if either is a
        share of it, or no longer if neither is."""
        width = self._widget._options["width"]
        height = self._widget._options["height"]
        screen_width, screen_height = self._widget._screen_size()
        self.follow(is_share(width) or is_share(height))
        return (
            cells(width, screen_width) or self.natural[0],
            cells(height, screen_height) or self.natural[1],
        )

    def follow(self, follow: bool) -> None:
        """Ask again whenever the terminal is resized, while ``follow``."""
        root = self._widget._root()
        if follow and self.binding is None:
            self.binding = root.bind("<Configure>", self._resized, add="+")
        elif not follow and self.binding is not None:
            root.unbind("<Configure>", self.binding)
            self.binding = None

    def _resized(self, event: Event) -> None:
        # The root's tag is on every widget's bindtags: only its own counts.
        if event.widget is self._widget._root() and self._widget.winfo_exists():
            self._ask()
