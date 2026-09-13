"""The place geometry manager.

Place puts a widget where it is told. There is no negotiation, no cavity and
no cell: a child names a position, optionally a size, and gets it.

Positions and sizes come in two forms that add together. The absolute form -
``x``, ``y``, ``width``, ``height`` - is in cells. The relative form -
``relx``, ``rely``, ``relwidth``, ``relheight`` - is a fraction of the
container, so ``relwidth=0.5`` is half the container's width whatever that
turns out to be. Giving both adds the absolute to the relative, which is how
"half the width, less two cells for a border" is expressed.

A placed child does not affect what its container asks for. That is the point
of the manager: it is the one that lets a widget sit on top of a layout rather
than take part in it, and a container whose children are all placed requests
nothing on their behalf.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tkcurses._core.geometry import Rect, Size
from tkcurses._core.pack import parse_anchor

__all__ = ["PlaceLayout", "PlaceOptions"]

#: What a coordinate or size may be measured against.
BORDERMODES = ("inside", "outside", "ignore")


@dataclass
class PlaceOptions:
    """Where one child is placed.

    Attributes:
        x: Cells from the container's left edge.
        y: Cells from its top edge.
        relx: Fraction of the container's width, added to ``x``.
        rely: Fraction of its height, added to ``y``.
        width: Width in cells. None means the child's requested width.
        height: Height in cells. None means its requested height.
        relwidth: Fraction of the container's width, added to ``width``.
        relheight: Fraction of its height, added to ``height``.
        anchor: Which point of the child lands on the position given.
        bordermode: Whether the position is measured inside the container's
            border, outside it, or ignoring it.
    """

    x: int = 0
    y: int = 0
    relx: float = 0.0
    rely: float = 0.0
    width: int | None = None
    height: int | None = None
    relwidth: float | None = None
    relheight: float | None = None
    anchor: str = "nw"
    bordermode: str = "inside"


class PlaceLayout:
    """Places one container's children."""

    #: Placed children make no claim on their container's size.
    propagates = False

    def __init__(self) -> None:
        self._order: list[Any] = []
        self._options: dict[int, PlaceOptions] = {}

    # ----------------------------------------------------------- membership

    def add(self, widget: Any, options: PlaceOptions) -> None:
        """Place ``widget``, or move it."""
        if widget not in self._order:
            self._order.append(widget)
        self._options[id(widget)] = options

    def remove(self, widget: Any) -> None:
        """Stop placing ``widget``."""
        if widget in self._order:
            self._order.remove(widget)
        self._options.pop(id(widget), None)

    def options_for(self, widget: Any) -> PlaceOptions | None:
        """How ``widget`` is placed, or None if it is not."""
        return self._options.get(id(widget))

    def slaves(self, container: Any = None) -> list[Any]:  # noqa: ARG002
        """The children being placed, in the order they were added."""
        return list(self._order)

    # ------------------------------------------------------------ geometry

    def requested(self, container: Any = None) -> Size:  # noqa: ARG002
        """Nothing.

        A placed child makes no claim on its container's size - that is what
        distinguishes place from the other two managers. A container with only
        placed children asks for nothing and keeps whatever size it is given.
        """
        return Size(0, 0)

    def apply(self, container: Any, area: Rect) -> None:
        """Put each child where its options say."""
        for widget in list(self._order):
            options = self._options[id(widget)]
            self._place(widget, container, area, options)

    def _place(
        self, widget: Any, container: Any, area: Rect, options: PlaceOptions
    ) -> None:
        """Work out one child's region and give it to them."""
        frame = self._frame(container, area, options.bordermode)
        requested = Size(widget.winfo_reqwidth(), widget.winfo_reqheight())

        # A relative size replaces the requested one rather than adding to it:
        # relwidth=1.0 means the container's width, not the container's width
        # plus whatever the child happened to ask for. An absolute width given
        # alongside is an adjustment to the relative one, which is how "half
        # the width, less two cells" is written.
        width = self._extent(
            options.width, options.relwidth, frame.width, requested.width
        )
        height = self._extent(
            options.height, options.relheight, frame.height, requested.height
        )

        x = frame.x + options.x + int(frame.width * options.relx)
        y = frame.y + options.y + int(frame.height * options.rely)
        across, down = parse_anchor(options.anchor)
        x -= int(width * across)
        y -= int(height * down)
        self._assign(widget, Rect(x, y, width, height))

    @staticmethod
    def _extent(
        absolute: int | None, relative: float | None, available: int, requested: int
    ) -> int:
        """One dimension of a placed child, from whichever options were given.

        Negative is possible on the way - ``width=-2`` with ``relwidth=0.5``
        is deliberate - so the clamp is applied to the result rather than to
        the option.
        """
        if relative is None:
            return max(0, absolute if absolute is not None else requested)
        return max(0, int(available * relative) + (absolute or 0))

    @staticmethod
    def _frame(container: Any, area: Rect, bordermode: str) -> Rect:
        """The rectangle a child's coordinates are measured against.

        ``inside`` is the container's content area, which is what ``area``
        already is. The other two measure against the whole widget, border
        included; they differ in Tk only for borders this library does not
        draw, so they behave alike here rather than pretending otherwise.
        """
        if bordermode == "inside":
            return area
        return Rect(
            container.winfo_rootx(),
            container.winfo_rooty(),
            container.winfo_width(),
            container.winfo_height(),
        )

    @staticmethod
    def _assign(widget: Any, rect: Rect) -> None:
        """Give a child its region, in coordinates relative to its master."""
        master = widget.master
        origin_x = master.winfo_rootx() if master is not None else 0
        origin_y = master.winfo_rooty() if master is not None else 0
        widget._allocate(
            Rect(rect.x - origin_x, rect.y - origin_y, rect.width, rect.height)
        )
