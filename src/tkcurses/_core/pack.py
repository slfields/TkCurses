"""The pack geometry manager.

Pack fills a container by taking a slice off one edge of the remaining space
for each child in turn. The space left after a slice is the *cavity* the next
child is packed into, which is why packing order matters and why a child
packed to the left of one packed to the top does not share its row.

Tk's algorithm in cells. Each child gets a *parcel* - the slice - and then
sits inside it according to ``fill`` and ``anchor``. Padding comes in two
kinds and they are not interchangeable: ``padx``/``pady`` is space outside the
widget but inside its parcel, and ``ipadx``/``ipady`` is added to the widget's
own size.

``expand`` is settled before any parcel is cut. Space left over once every
child has what it asked for is shared among the children that asked to
expand, so the sharing is decided from the whole cavity rather than from
whatever happens to remain when the last child is reached.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tkcurses._core.geometry import Rect, Size

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["PackLayout", "PackOptions", "parse_anchor"]

#: The edges a child can be packed against.
SIDES = ("top", "bottom", "left", "right")

#: What a child may be stretched to fill within its parcel.
FILLS = ("none", "x", "y", "both")

#: Anchor names, and the fraction of the leftover room each puts before the
#: widget horizontally and vertically. "center" is the Tk default.
_ANCHORS: dict[str, tuple[float, float]] = {
    "nw": (0.0, 0.0),
    "n": (0.5, 0.0),
    "ne": (1.0, 0.0),
    "w": (0.0, 0.5),
    "center": (0.5, 0.5),
    "e": (1.0, 0.5),
    "sw": (0.0, 1.0),
    "s": (0.5, 1.0),
    "se": (1.0, 1.0),
}


def parse_anchor(anchor: str) -> tuple[float, float]:
    """Fractions an anchor name puts before the widget, horizontally then down.

    Raises:
        ValueError: If the name is not one Tk recognises.
    """
    try:
        return _ANCHORS[anchor.lower()]
    except KeyError:
        raise ValueError(f"bad anchor {anchor!r}") from None


@dataclass
class PackOptions:
    """How one child is packed.

    Attributes:
        side: Which edge of the cavity to take the parcel from.
        fill: Whether the child stretches to its parcel, and in which axis.
        expand: Whether the child claims a share of the leftover space.
        anchor: Where the child sits in its parcel when it does not fill it.
        padx: Cells of space either side of the child, inside its parcel.
        pady: Cells of space above and below.
        ipadx: Cells added to the child's own width.
        ipady: Cells added to the child's own height.
    """

    side: str = "top"
    fill: str = "none"
    expand: bool = False
    anchor: str = "center"
    padx: int = 0
    pady: int = 0
    ipadx: int = 0
    ipady: int = 0

    @property
    def vertical(self) -> bool:
        """True if this child is packed against the top or bottom edge."""
        return self.side in ("top", "bottom")

    def demand(self, requested: Size) -> Size:
        """Room this child needs in its parcel, padding included."""
        return Size(
            requested.width + 2 * self.ipadx + 2 * self.padx,
            requested.height + 2 * self.ipady + 2 * self.pady,
        )


class PackLayout:
    """Packs one container's children.

    Holds the packing order, which is the order children were added and the
    order parcels are cut, and is what ``before`` and ``after`` reorder.
    """

    #: Packed children decide how much room their container needs.
    propagates = True

    def __init__(self) -> None:
        self._order: list[Any] = []
        self._options: dict[int, PackOptions] = {}

    # ----------------------------------------------------------- membership

    def add(
        self,
        widget: Any,
        options: PackOptions,
        *,
        before: Any = None,
        after: Any = None,
    ) -> None:
        """Pack ``widget``, or re-pack it with new options.

        Packing something already packed keeps its place in the order unless
        ``before`` or ``after`` moves it, which is what lets
        ``widget.pack(fill="x")`` change one option without sending the widget
        to the end.
        """
        if widget not in self._order:
            self._order.append(widget)
        self._options[id(widget)] = options
        if before is not None:
            self._move(widget, self._index(before))
        elif after is not None:
            self._move(widget, self._index(after) + 1)

    def remove(self, widget: Any) -> None:
        """Stop packing ``widget``. Removing what is not packed is harmless."""
        if widget in self._order:
            self._order.remove(widget)
        self._options.pop(id(widget), None)

    def options_for(self, widget: Any) -> PackOptions | None:
        """How ``widget`` is packed, or None if it is not."""
        return self._options.get(id(widget))

    def slaves(self, container: Any = None) -> list[Any]:  # noqa: ARG002
        """The children being packed, in packing order."""
        return list(self._order)

    def _index(self, widget: Any) -> int:
        """Position of ``widget`` in the packing order.

        Raises:
            ValueError: If it is not packed here, which is what Tk reports for
                a ``before`` or ``after`` naming a stranger.
        """
        try:
            return self._order.index(widget)
        except ValueError:
            raise ValueError(f"{widget!r} is not packed in this container") from None

    def _move(self, widget: Any, position: int) -> None:
        """Move ``widget`` to ``position`` in the packing order."""
        current = self._order.index(widget)
        self._order.pop(current)
        if current < position:
            position -= 1
        self._order.insert(max(0, position), widget)

    # ------------------------------------------------------------ geometry

    def requested(self, container: Any = None) -> Size:  # noqa: ARG002
        """Room the packed children need altogether.

        Along each child's own axis the demands add up; across it they do not,
        because a parcel spans the cavity. So five children packed on top of
        one another need the sum of their heights and the width of the widest.
        """
        width = height = 0
        for widget in self._order:
            options = self._options[id(widget)]
            demand = options.demand(self._requested_of(widget))
            if options.vertical:
                height += demand.height
                width = max(width, demand.width)
            else:
                width += demand.width
                height = max(height, demand.height)
        return Size(width, height)

    def apply(self, container: Any, area: Rect) -> None:  # noqa: ARG002
        """Cut parcels out of ``area`` and put each child in its own."""
        cavity = area
        extra = self._expansion(area)
        for widget in list(self._order):
            options = self._options[id(widget)]
            demand = options.demand(self._requested_of(widget))
            parcel, cavity = self._cut(
                cavity, options, demand, extra.get(id(widget), 0)
            )
            self._place(widget, parcel, options)

    def _expansion(self, area: Rect) -> dict[int, int]:
        """Extra cells each expanding child receives, by widget id.

        Leftover space is worked out per axis from the whole cavity, then
        split among the children that expand along that axis. The remainder
        goes to the earliest of them, so the total is exactly the space
        available and no cell is lost to rounding.
        """
        shares: dict[int, int] = {}
        for vertical in (True, False):
            claimants = [
                widget
                for widget in self._order
                if self._options[id(widget)].expand
                and self._options[id(widget)].vertical is vertical
            ]
            if not claimants:
                continue
            used = self._used_along(vertical)
            room = area.height if vertical else area.width
            leftover = max(0, room - used)
            each, remainder = divmod(leftover, len(claimants))
            for position, widget in enumerate(claimants):
                shares[id(widget)] = each + (1 if position < remainder else 0)
        return shares

    def _used_along(self, vertical: bool) -> int:
        """Cells the children packed along one axis take before expanding."""
        total = 0
        for widget in self._order:
            options = self._options[id(widget)]
            if options.vertical is not vertical:
                continue
            demand = options.demand(self._requested_of(widget))
            total += demand.height if vertical else demand.width
        return total

    @staticmethod
    def _cut(
        cavity: Rect, options: PackOptions, demand: Size, extra: int
    ) -> tuple[Rect, Rect]:
        """Take one parcel off the cavity, returning the parcel and the rest.

        A parcel spans the cavity across its axis: a child packed on the left
        gets the full height of what remains, however short the child is.
        """
        if options.vertical:
            height = min(cavity.height, demand.height + extra)
            if options.side == "top":
                parcel = Rect(cavity.x, cavity.y, cavity.width, height)
                rest = Rect(
                    cavity.x, cavity.y + height, cavity.width, cavity.height - height
                )
            else:
                parcel = Rect(
                    cavity.x, cavity.y + cavity.height - height, cavity.width, height
                )
                rest = Rect(cavity.x, cavity.y, cavity.width, cavity.height - height)
        else:
            width = min(cavity.width, demand.width + extra)
            if options.side == "left":
                parcel = Rect(cavity.x, cavity.y, width, cavity.height)
                rest = Rect(
                    cavity.x + width, cavity.y, cavity.width - width, cavity.height
                )
            else:
                parcel = Rect(
                    cavity.x + cavity.width - width, cavity.y, width, cavity.height
                )
                rest = Rect(cavity.x, cavity.y, cavity.width - width, cavity.height)
        return parcel, rest

    def _place(self, widget: Any, parcel: Rect, options: PackOptions) -> None:
        """Put one child inside its parcel, honouring fill and anchor."""
        inner = Rect(
            parcel.x + options.padx,
            parcel.y + options.pady,
            max(0, parcel.width - 2 * options.padx),
            max(0, parcel.height - 2 * options.pady),
        )
        requested = self._requested_of(widget)
        width = min(inner.width, requested.width + 2 * options.ipadx)
        height = min(inner.height, requested.height + 2 * options.ipady)
        if options.fill in ("x", "both"):
            width = inner.width
        if options.fill in ("y", "both"):
            height = inner.height

        across, down = parse_anchor(options.anchor)
        x = inner.x + int((inner.width - width) * across)
        y = inner.y + int((inner.height - height) * down)
        self._assign(widget, Rect(x, y, width, height))

    @staticmethod
    def _requested_of(widget: Any) -> Size:
        """The size a child asked for."""
        return Size(widget.winfo_reqwidth(), widget.winfo_reqheight())

    @staticmethod
    def _assign(widget: Any, rect: Rect) -> None:
        """Give a child its region, in coordinates relative to its master.

        The parcel arithmetic is done in screen cells, because that is what a
        container's content area is expressed in, but a widget's own rect is
        an offset from its master.
        """
        master = widget.master
        origin_x = master.winfo_rootx() if master is not None else 0
        origin_y = master.winfo_rooty() if master is not None else 0
        widget._allocate(
            Rect(rect.x - origin_x, rect.y - origin_y, rect.width, rect.height)
        )


def pack_order(layout: PackLayout) -> Iterable[Any]:
    """The packing order, for callers that only want to read it."""
    return tuple(layout.slaves())
