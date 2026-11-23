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

"""A treemap: a hierarchy of values drawn as nested rectangles.

TkCurses extension:
    Neither tkinter nor Tk has a treemap. This one follows the behaviour
    of Kibana's treemap charts - two levels, largest first, labels that
    hide when they do not fit, a legend - and the item interface of
    :class:`tkcurses.ttk.Treeview`.
"""

from __future__ import annotations

import contextlib
import curses
import functools
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import tkcurses
from tkcurses import TclError, _signed_distance
from tkcurses._charts.color import DEFAULT_COLORS, hex_color
from tkcurses._charts.geometry import Rect
from tkcurses._charts.numformat import PLACEMENTS, ROUNDINGS, UNIT_SCALES, NumberFormat
from tkcurses._charts.options import choice, color, count, flag, items, optional_count
from tkcurses._core.bindings import parse_sequence
from tkcurses._core.cells import cells
from tkcurses._core.colors import ColorDepth, parse_color, rgb_of
from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses.treemap._compose import Cell, Scene, compose
from tkcurses.treemap._labels import percent
from tkcurses.treemap._layout import Regions, TileLayout, lay_out, regions
from tkcurses.treemap._legend import (
    LEGEND_MODES,
    LEGEND_SIZES,
    MAX_LINES,
    POSITIONS,
    LegendLayout,
    entries,
    extent,
    place,
    shown,
)
from tkcurses.treemap._model import Model
from tkcurses.treemap._navigate import OPPOSITE, Direction, neighbour
from tkcurses.treemap._shades import OUTLINE_MODES, outlined_levels, shades_of

if TYPE_CHECKING:
    from collections.abc import Callable

    from tkcurses import Event
    from tkcurses._charts.color import RGB

__all__ = ["NATURAL_SIZE", "PATH_SEPARATOR", "SELECT_EVENT", "ZOOM_EVENT", "TreeMap"]

VALUES = ("percent", "value", "none")
#: The events a tag binding is told about, and the item each one is for:
#: a pointer event's is the tile under the pointer; these, as named; any
#: other's, a key's, the focused item, as in a Treeview.
_POINTER_EVENTS = frozenset({"Button", "ButtonRelease", "Motion"})
#: Sent when an item is selected, by a key, a click or
#: :meth:`TreeMap.selection_set`.
SELECT_EVENT = "<<TreeMapSelect>>"
#: Sent when the treemap zooms into a group or back out.
ZOOM_EVENT = "<<TreeMapZoom>>"
#: Written between a group and its child in the readout.
PATH_SEPARATOR = " \u203a "  # a single right-pointing angle quote
#: What :meth:`TreeMap.item` reads and sets.
_ITEM_OPTIONS = ("text", "value", "tags", "description")
#: The size a treemap asks for on an axis whose width or height is not
#: given.
NATURAL_SIZE = (40, 12)


def _dimension(widget: Any, value: Any) -> Any:
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


def _cells(value: Any, screen: int) -> int:
    """A ``width`` or ``height`` in cells against a ``screen`` that long;
    0 for one not given."""
    if isinstance(value, str) and value.endswith("%"):
        return max(1, round(screen * float(value[:-1]) / 100))
    return max(0, int(value))


def _is_share(value: Any) -> bool:
    return isinstance(value, str) and value.endswith("%")


@dataclass(frozen=True)
class _Config:
    """A treemap's own options, checked."""

    labels: bool
    values: str
    percentdecimals: int
    colors: tuple[str, ...]
    outline: str
    readout: bool
    numbers: NumberFormat
    legend: str
    legendposition: str
    legendsize: str
    nestedlegend: bool
    legendlines: int


def _parse(options: dict[str, Any]) -> _Config:
    decimals = count(options["percentdecimals"], "percentdecimals", minimum=0)
    if decimals > 10:
        raise ValueError(f"percentdecimals must be at most 10, not {decimals}")
    lines = count(options["legendlines"], "legendlines", minimum=1)
    if lines > MAX_LINES:
        raise ValueError(f"legendlines must be at most {MAX_LINES}, not {lines}")
    return _Config(
        labels=flag(options["labels"]),
        values=choice(options["values"], "values", VALUES),
        percentdecimals=decimals,
        colors=tuple(color(c) for c in items(options["colors"])) or DEFAULT_COLORS,
        outline=choice(options["outline"], "outline", OUTLINE_MODES),
        readout=flag(options["readout"]),
        numbers=NumberFormat(
            units=str(options["units"]),
            placement=choice(options["unitplacement"], "unitplacement", PLACEMENTS),  # type: ignore[arg-type]
            space=flag(options["unitspace"]),
            digits=optional_count(options["digits"], "digits", minimum=1),
            decimals=optional_count(options["decimals"], "decimals", minimum=0),
            rounding=choice(options["rounding"], "rounding", ROUNDINGS),  # type: ignore[arg-type]
            unitscale=choice(options["unitscale"], "unitscale", UNIT_SCALES),  # type: ignore[arg-type]
        ),
        legend=choice(options["legend"], "legend", LEGEND_MODES),
        legendposition=choice(options["legendposition"], "legendposition", POSITIONS),
        legendsize=choice(options["legendsize"], "legendsize", ("auto", *LEGEND_SIZES)),
        nestedlegend=flag(options["nestedlegend"]),
        legendlines=lines,
    )


class TreeMap(tkcurses.Frame):
    """A treemap: named values drawn as rectangles, each sized by its value.

    Items are added as a :class:`tkcurses.ttk.Treeview`'s are, with
    :meth:`insert`, and have two levels at most. An item at the top level
    may hold *children*; it is then a *group*, its size is the sum of
    theirs, and their tiles are drawn inside its own, in shades of its
    colour, under a header row when it has room. The rectangles are laid
    out largest first, as near square to the eye as the squarified
    algorithm makes them.

    A TreeMap is a :class:`tkcurses.Frame`, placed with ``pack``, ``grid``
    or ``place`` like any widget. A change to the items is drawn once the
    program is idle, so a loop that changes a hundred of them is drawn
    once.

    A bad option value raises :class:`tkcurses.TclError` and leaves the
    treemap as it was, at creation and in :meth:`configure` alike.

    **Size.** ``width`` and ``height`` are each given on their own, in
    cells or as a percentage of the terminal: ``width="50%", height=10``
    asks for half the terminal's width and ten rows, and follows the
    terminal when it is resized. An axis not given asks for 40 columns or
    12 rows. As for any widget, this is a request: ``fill`` and
    ``expand`` give it more.

    **Keys and the mouse.** A treemap takes the keyboard focus, and while
    it has it the focused item is drawn reversed: its label row, a group's
    header, or the whole tile when it is too small for text.

    - The arrow keys move the focus to the next tile that way on the same
      level, and the opposite key comes back.
    - Space selects the focused item. Return selects it too, or on a
      group zooms in, so the group's children fill the treemap.
    - Escape zooms back out, or moves from a child to its group.
    - A click focuses and selects the tile under the pointer, a group's
      header being the group. A double-click zooms into its group.
    - A click on a legend entry focuses its item without selecting it,
      so the bottom row names even an item too small to have a tile.

    Selecting sends ``<<TreeMapSelect>>`` and zooming in or out sends
    ``<<TreeMapZoom>>``. A treemap selects one item at most, marked with
    a ``●`` before its name. The bottom row names the focused item, with
    its value and its share of everything and of its group, and its legend
    entry is reversed too.

    **Acting on one item.** Give items ``tags`` and bind to a tag, as in a
    Treeview: ``tree.tag_bind("disk", "<<TreeMapSelect>>", show)`` runs
    ``show`` only when an item tagged ``disk`` is selected.

    Options:
        labels: Write each tile's name in it, cut with ``…`` to fit, or
            left out where fewer than three cells would remain. Default
            True.
        values: What is written under each name: ``"percent"`` (the
            default), its share of what is shown; ``"value"``, the number
            itself, in the number format below; or ``"none"``.
        percentdecimals: Decimal places in a percentage, 0 to 10. Default 2.
        colors: The colours the top-level items take in turn, largest
            first. A group's children take shades of its colour. Default
            green, red, blue, yellow, magenta and cyan.
        outline: Lines between tiles. ``"auto"`` (the default) draws them
            where shades cannot be told apart: everywhere on a terminal
            without colour, between a group's children below 256 colours,
            and at 256 where the palette rounds a group's shades together.
            ``"on"`` draws them everywhere, ``"off"`` nowhere.
        readout: A row at the bottom with the total, and how many items are
            too small to have a cell. Default True.
        legend: A list beside the tiles naming each top-level item, with a
            swatch of its colour, largest first; zoomed in, the group's
            children. An item's ``description`` is written under its name
            here, and only here. ``"auto"`` (the default) shows it when it names two
            or more; ``"show"`` always; ``"hide"`` never. Either way it
            gives way, before the readout, when the tiles would be left
            fewer than 10 columns or 3 rows.
        legendposition: ``"right"`` (the default), ``"left"``, ``"top"``
            or ``"bottom"``. At the top or bottom the entries flow across
            in columns, in at most a third of the height.
        legendsize: The legend's width at the left or right, its edge
            included: ``"small"`` 12 cells, ``"medium"`` 20, ``"large"``
            28, ``"xlarge"`` 36; or ``"auto"`` (the default), the widest
            entry, at most a third of the treemap.
        nestedlegend: List each group's children under it, indented.
            Default False.
        legendlines: How many lines, 1 to 5, a name wraps onto before it
            is cut with ``…``, and a description after it. Default 1.
        foreground: The colour of the readout and of text on no tile.
            Default white.
        background: The colour of cells no tile covers, as for any Frame.
            Default black.
        borderwidth: ``1`` draws a box around the treemap. Default 0.
        relief: The box's style, as for any Frame. Default ``"solid"``.
        units: Written with every value: ``"B"``, ``"ms"``, ``"$"``.
            Default none.
        unitplacement: ``"suffix"`` (the default), after the number; or
            ``"prefix"``, before it.
        unitspace: A space between the number and its units. Default False.
        digits: Significant digits, 1 to 15; a value whose whole part
            needs more is scaled, with the scale's letter: with 3, 1234 is
            ``1.23k``. Default none: up to six.
        decimals: A fixed count of decimals, 0 to 15: with 2, 330 is
            ``330.00``. Default none.
        rounding: How a value cut to its digits is rounded: ``"nearest"``
            (the default), ``"down"`` or ``"up"``.
        unitscale: How a value is scaled to the fewest digits. ``"si"``
            (the default): by thousands, k, M, G, when its whole part
            outgrows its digits. ``"binary"``: by 1024s, Ki, Mi, Gi, for
            bytes. ``"time"``: ``units`` names the unit the data is in,
            ``"ms"``, ``"s"``, ``"min"`` and the rest, and each value is
            written in the largest it reaches one of. ``"none"``: never.

    The number format is BarGraph's, and applies with ``values="value"``
    and in the readout.

    Standard options, described in :doc:`/reference/options`:
    ``background``, ``borderwidth``, ``cursor``, ``height``,
    ``highlightbackground``, ``highlightcolor``, ``highlightthickness``,
    ``padx``, ``pady``, ``relief``, ``takefocus``, ``width``.

    Not supported, as on any Frame: ``backgroundimage``, ``class``,
    ``colormap``, ``container``, ``tile`` and ``visual``.

    Sample output:
        # size: 50x12
        from tkcurses.treemap import TreeMap
        tree = TreeMap(root)
        tree.pack(fill="both", expand=True)
        tree.insert("", "end", "web", text="web")
        for name, size in (("nginx", 330), ("apache", 170), ("php", 50)):
            tree.insert("web", "end", text=name, value=size)
        tree.insert("", "end", "db", text="db")
        for name, size in (("postgres", 140), ("mysql", 60)):
            tree.insert("db", "end", text=name, value=size)
        tree.insert("", "end", text="cache", value=100)

    Sample output (labels, values):
        # size: 60x8
        from tkcurses.treemap import TreeMap
        for labels, values in ((True, "percent"), (False, "value")):
            tree = TreeMap(root, labels=labels, values=values, width=30)
            tree.pack(side="left", fill="y")
            for name, size in (("nginx", 330), ("apache", 170), ("php", 50)):
                tree.insert("", "end", text=name, value=size)

    Sample output (percentdecimals):
        # size: 60x8
        from tkcurses.treemap import TreeMap
        for places in (0, 3):
            tree = TreeMap(root, percentdecimals=places, width=30)
            tree.pack(side="left", fill="y")
            for name, size in (("nginx", 330), ("apache", 170), ("php", 50)):
                tree.insert("", "end", text=name, value=size)

    Sample output (colors):
        from tkcurses.treemap import TreeMap
        tree = TreeMap(root, colors=["#4060c0", "#c08020"])
        tree.pack(fill="both", expand=True)
        tree.insert("", "end", "web", text="web")
        for name, size in (("nginx", 330), ("apache", 170), ("php", 50)):
            tree.insert("web", "end", text=name, value=size)
        tree.insert("", "end", text="cache", value=200)

    Sample output (outline):
        # size: 60x10
        from tkcurses.treemap import TreeMap
        for outline in ("auto", "on"):
            tree = TreeMap(root, outline=outline, width=30)
            tree.pack(side="left", fill="y")
            tree.insert("", "end", "web", text="web")
            for name, size in (("nginx", 330), ("apache", 170), ("php", 50)):
                tree.insert("web", "end", text=name, value=size)
            tree.insert("", "end", text="cache", value=200)

    Sample output (readout):
        # size: 50x10
        from tkcurses.treemap import TreeMap
        for readout in (True, False):
            tree = TreeMap(root, readout=readout, height=5)
            tree.pack(fill="x")
            for size in (5000, 3000, 1):
                tree.insert("", "end", text=f"{size}", value=size)

    Sample output (legend):
        # size: 60x8
        from tkcurses.treemap import TreeMap
        for legend in ("show", "hide"):
            tree = TreeMap(root, legend=legend, width=30)
            tree.pack(side="left", fill="y")
            for name, size in (("web", 550), ("db", 200), ("cache", 100)):
                tree.insert("", "end", text=name, value=size)

    Sample output (legendposition, legendsize):
        # size: 60x10
        from tkcurses.treemap import TreeMap
        for position, size in (("left", "small"), ("bottom", "auto")):
            tree = TreeMap(root, legendposition=position, legendsize=size,
                           width=30)
            tree.pack(side="left", fill="y")
            for name, size in (("web", 550), ("db", 200), ("cache", 100)):
                tree.insert("", "end", text=name, value=size)

    Sample output (nestedlegend, legendlines):
        # size: 50x10
        from tkcurses.treemap import TreeMap
        tree = TreeMap(root, nestedlegend=True, legendlines=2,
                       legendsize="medium")
        tree.pack(fill="both", expand=True)
        tree.insert("", "end", "web", text="web servers",
                    description="the front end")
        for name, size in (("nginx", 330), ("apache", 170)):
            tree.insert("web", "end", text=name, value=size)
        tree.insert("", "end", text="database", value=200,
                    description="primary and replica")

    Sample output (units, unitplacement, unitspace):
        # size: 60x8
        from tkcurses.treemap import TreeMap
        for units, placement in (("B", "suffix"), ("$", "prefix")):
            tree = TreeMap(root, values="value", units=units, width=30,
                           unitplacement=placement, unitspace=units == "B")
            tree.pack(side="left", fill="y")
            for name, size in (("nginx", 330), ("apache", 170), ("php", 50)):
                tree.insert("", "end", text=name, value=size)

    Sample output (digits, decimals, rounding):
        # size: 60x8
        from tkcurses.treemap import TreeMap
        for options in ({"digits": 1, "rounding": "up"}, {"decimals": 2}):
            tree = TreeMap(root, values="value", width=30, **options)
            tree.pack(side="left", fill="y")
            for name, size in (("nginx", 1234), ("apache", 170), ("php", 50)):
                tree.insert("", "end", text=name, value=size)

    Sample output (unitscale):
        # size: 60x8
        from tkcurses.treemap import TreeMap
        for scale, units in (("binary", "B"), ("time", "s")):
            tree = TreeMap(root, values="value", unitscale=scale,
                           units=units, digits=3, width=30)
            tree.pack(side="left", fill="y")
            for size in (400_000, 250_000, 90_000):
                tree.insert("", "end", text=scale, value=size)
    """

    _widget_options: ClassVar[dict[str, Any]] = {
        "relief": "solid",  # so borderwidth=1 alone draws the box
        "foreground": "",
        "takefocus": True,
        "labels": True,
        "values": "percent",
        "percentdecimals": 2,
        "colors": (),
        "outline": "auto",
        "readout": True,
        "units": "",
        "unitplacement": "suffix",
        "unitspace": False,
        "digits": "",
        "decimals": "",
        "rounding": "nearest",
        "unitscale": "si",
        "legend": "auto",
        "legendposition": "right",
        "legendsize": "auto",
        "nestedlegend": False,
        "legendlines": 1,
    }

    #: Frame hides ``foreground``; a TreeMap writes its readout in it.
    _not_tk_options: ClassVar[frozenset[str]] = frozenset()

    _value_checks: ClassVar[dict[str, Callable[[Any, Any], Any]]] = {
        "width": _dimension,
        "height": _dimension,
    }

    #: The options this class adds and :func:`_parse` checks.
    _own_options = frozenset(_widget_options) - {"relief", "foreground", "takefocus"}

    def __init__(
        self,
        master: Any = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        self._model = Model()
        self._pending: str | None = None
        self._cached: tuple[Any, TileLayout, Regions, LegendLayout | None] | None = None
        #: The group zoomed into, or "".
        self._zoom = ""
        #: ``(key, at, back)``: pressing ``key`` with the focus on ``at``
        #: goes ``back`` where the last arrow came from, so Right then Left
        #: returns whatever the geometry would pick.
        self._back: tuple[Direction, str, str] | None = None
        self._tag_bindings: dict[str, dict[str, Callable[[Event], Any]]] = {}
        self._tag_dispatch: dict[str, str] = {}
        #: The group just zoomed out of, for a ``<<TreeMapZoom>>`` tag binding.
        self._zoomed_out = ""
        #: The root's ``<Configure>`` binding, while a size is a percentage.
        self._screen_binding: str | None = None
        options = {**self._widget_options, **(cnf or {}), **kw}
        try:
            config = _parse({key: options[key] for key in self._own_options})
        except ValueError as error:
            raise TclError(str(error)) from None
        self._config = config
        super().__init__(master, cnf, name=name, **kw)
        self._install_class_bindings()
        self._apply(config)

    def _install_class_bindings(self) -> None:
        """The keys and the mouse, bound once for the class."""
        name = self.winfo_class()
        if name in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(name)
        bind = self.bind_class
        for key in ("Left", "Right", "Up", "Down"):
            bind(name, f"<Key-{key}>", functools.partial(_treemap_arrow, key))
        bind(name, "<Key-Return>", _treemap_return)
        bind(name, "<Key-space>", _treemap_space)
        bind(name, "<Key-Escape>", _treemap_escape)
        bind(name, "<Button-1>", _treemap_click)
        bind(name, "<Double-Button-1>", _treemap_double)
        bind(name, "<FocusIn>", _treemap_refocus)
        bind(name, "<FocusOut>", _treemap_refocus)

    # ------------------------------------------------------------- options

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, or with none, describe them all.

        Every option is checked before any is applied, so one bad value
        changes nothing.

        Raises:
            tkcurses.TclError: An option is unknown or its value is bad.
        """
        given = {**(cnf or {}), **kw}
        if not given:
            return super().configure(cnf, **kw)
        ours = {key: value for key, value in given.items() if key in self._own_options}
        config = None
        if ours:
            merged = {key: self._options[key] for key in self._own_options} | ours
            try:
                config = _parse(merged)
            except ValueError as error:
                raise TclError(str(error)) from None
        result = super().configure(cnf, **kw)
        if config is not None:
            self._apply(config)
        else:
            self._apply_requested_size()
            self._changed()
        return result

    config = configure

    def _apply(self, config: _Config) -> None:
        self._config = config
        self._cached = None
        self._apply_requested_size()
        self._changed()

    def _apply_requested_size(self) -> None:
        """Ask for ``width`` by ``height``, each in cells or a share of the
        screen, and :data:`NATURAL_SIZE` on an axis not given.

        Unlike a Frame's, an axis left out is not left to children: a
        treemap has none, and would ask for nothing on it.
        """
        width, height = self._options["width"], self._options["height"]
        screen_width, screen_height = self._screen_size()
        self._request_size(
            _cells(width, screen_width) or NATURAL_SIZE[0],
            _cells(height, screen_height) or NATURAL_SIZE[1],
        )
        self._follow_screen(_is_share(width) or _is_share(height))

    def _follow_screen(self, follow: bool) -> None:
        """Ask again whenever the terminal is resized, while a size is a
        percentage of it."""
        root = self._root()
        if follow and self._screen_binding is None:
            self._screen_binding = root.bind(
                "<Configure>", self._screen_resized, add="+"
            )
        elif not follow and self._screen_binding is not None:
            root.unbind("<Configure>", self._screen_binding)
            self._screen_binding = None

    def _screen_resized(self, event: Event) -> None:
        # The root's tag is on every widget's bindtags: only its own counts.
        if event.widget is self._root() and self.winfo_exists():
            self._apply_requested_size()

    # ---------------------------------------------------------------- items

    def _do(self, action: Callable[[], Any]) -> Any:
        """Run a change to the items, as a TclError if it is refused."""
        try:
            result = action()
        except ValueError as error:
            raise TclError(str(error)) from None
        self._changed()
        return result

    def _ask(self, action: Callable[[], Any]) -> Any:
        """Run a question about the items, as a TclError if it is refused."""
        try:
            return action()
        except ValueError as error:
            raise TclError(str(error)) from None

    def insert(
        self,
        parent: str,
        index: Any = "end",
        iid: str | None = None,
        *,
        text: str = "",
        value: Any = 0,
        tags: Any = (),
        description: str = "",
    ) -> str:
        """Add an item and return its identifier.

        Args:
            parent: ``""`` for the top level, or a top-level item to add a
                child to. A child cannot have children of its own.
            index: Where among its siblings: a number, or ``"end"``.
            iid: An identifier; ``I001``, ``I002`` and on when omitted, as a
                Treeview's are.
            text: The name written in its tile.
            value: Its size: a number, not negative. Zero takes no room. A
                group's size is its children's sum, whatever its own value.
            tags: Names to group items by, for :meth:`tag_bind` and
                :meth:`tag_has`: a list, or a string of names with spaces
                between, as a Treeview's are.
            description: Said about the item in the legend, under its
                name, and nowhere else: not in its tile, not in the bottom
                row. It wraps to the legend's width, onto at most
                ``legendlines`` lines. Default none.

        Raises:
            tkcurses.TclError: ``parent`` is not an item, or is a child;
                ``iid`` is in use; ``value`` is not a number, or negative.
        """
        return str(
            self._do(
                lambda: self._model.insert(
                    parent,
                    index,
                    iid,
                    text=text,
                    value=value,
                    tags=tags,
                    description=description,
                )
            )
        )

    def item(self, iid: str, option: str | None = None, **kw: Any) -> Any:
        """Read or change an item's ``text``, ``value``, ``tags`` and
        ``description``.

        With neither ``option`` nor keywords, a dict of all four; with
        ``option``, that one; with keywords, they are set.
        """
        entry = self._ask(lambda: self._model.item(iid))
        unknown = set(kw) - set(_ITEM_OPTIONS)
        if option is not None and option not in _ITEM_OPTIONS:
            unknown.add(option)
        if unknown:
            raise TclError(f'unknown option "-{sorted(unknown)[0]}"')
        if kw:
            self._do(
                lambda: self._model.configure(
                    iid,
                    text=kw.get("text"),
                    value=kw.get("value"),
                    tags=kw.get("tags"),
                    description=kw.get("description"),
                )
            )
            return None
        values = {
            "text": entry.text,
            "value": entry.value,
            "tags": entry.tags,
            "description": entry.description,
        }
        return values if option is None else values[option]

    def delete(self, *items: str) -> None:
        """Remove items, a group with its children; one not found raises
        and removes none."""
        self._do(lambda: self._model.delete(*items))

    def move(self, item: str, parent: str, index: Any) -> None:
        """Put ``item`` under ``parent`` at ``index``; two levels still."""
        self._do(lambda: self._model.move(item, parent, index))

    def get_children(self, item: str = "") -> tuple[str, ...]:
        """The items under ``item``, or the top level, in their order."""
        return tuple(self._ask(lambda: self._model.get_children(item)))

    def parent(self, item: str) -> str:
        """The group above ``item``, or ``""``."""
        return str(self._ask(lambda: self._model.parent(item)))

    def index(self, item: str) -> int:
        """Where ``item`` is among its siblings."""
        return int(self._ask(lambda: self._model.index(item)))

    def exists(self, item: str) -> bool:
        """Whether ``item`` names an item."""
        return self._model.exists(item)

    # ------------------------------------------------- focus and selection

    def focus(self, item: str | None = None) -> Any:
        """With no argument, the focused item, or ``""``; with one, focus
        it. The arrow keys move the focus, and Return and Space act on it.
        Focusing ``""`` focuses nothing."""
        if item is None:
            return self._model.focus
        if item:
            self._ask(lambda: self._model.item(item))
        self._model.focus = item
        self._back = None
        self._changed()
        return None

    def selection(self) -> tuple[str, ...]:
        """The selected item, as a tuple of one, or ``()``. A treemap selects
        one item at most; the tuple is a Treeview's answer."""
        return (self._model.selected,) if self._model.selected else ()

    def selection_set(self, *items: str) -> None:
        """Select one item, or none with no argument or ``""``, and send
        ``<<TreeMapSelect>>``.

        Raises:
            tkcurses.TclError: More than one item is named, or one is not
                an item.
        """
        named = [item for item in items if item]
        if len(named) > 1:
            raise TclError("a treemap selects one item at most")
        if named:
            self._ask(lambda: self._model.item(named[0]))
        self._select(named[0] if named else "")

    def _select(self, item: str) -> None:
        self._model.selected = item
        self._changed()
        self.event_generate(SELECT_EVENT)

    def zoom(self, item: str | None = None) -> Any:
        """With no argument, the group zoomed into, or ``""``; with one,
        zoom into it so its children fill the treemap, or out with ``""``.
        A change sends ``<<TreeMapZoom>>``.

        Raises:
            tkcurses.TclError: ``item`` is not a top-level item with
                children.
        """
        if item is None:
            return self._zoom
        if item:
            entry = self._ask(lambda: self._model.item(item))
            if entry.parent or not entry.children:
                raise TclError(
                    f"{item} is not a group: a treemap zooms into a top-level"
                    " item with children"
                )
        if item == self._zoom:
            return None
        self._zoom = item
        self._back = None
        self._changed()
        self.event_generate(ZOOM_EVENT)
        return None

    def identify(self, x: int, y: int) -> str:
        """The item drawn at ``(x, y)``, in cells from the widget's top
        left, or ``""``: a group's header is the group's, and a legend
        entry its item's."""
        scene = self._scene_now()
        if scene is None:
            return ""
        tile = scene.layout.at(x, y)
        if tile is not None:
            return tile.iid
        if scene.legend is not None:
            return scene.legend.at(x, y) or ""
        return ""

    # ------------------------------------------------------------------ tags

    def tag_has(self, tagname: str, item: str | None = None) -> Any:
        """The items carrying ``tagname``, or whether ``item`` does."""
        if item is not None:
            return tagname in self._ask(lambda: self._model.item(item)).tags
        return self._model.tagged(tagname)

    def tag_bind(
        self,
        tagname: str,
        sequence: str | None = None,
        callback: Callable[[Event], Any] | None = None,
    ) -> None:
        """Run ``callback`` for ``sequence`` on the items carrying
        ``tagname`` only.

        The item an event is for is the tile under the pointer for a mouse
        event; the selected item for ``<<TreeMapSelect>>``; the group zoomed
        into, or out of, for ``<<TreeMapZoom>>``; and the focused item for
        a key. So ``tag_bind("disk", "<<TreeMapSelect>>", show)`` runs
        ``show`` when an item tagged ``disk`` is chosen, however it was.
        """
        if sequence is None or callback is None:
            return
        self._tag_bindings.setdefault(tagname, {})[sequence] = callback
        if sequence not in self._tag_dispatch:
            self._tag_dispatch[sequence] = self.bind(
                sequence, functools.partial(_treemap_tag_event, sequence), add="+"
            )

    def _event_item(self, sequence: str, event: Event) -> str:
        if sequence == SELECT_EVENT:
            return self._model.selected
        if sequence == ZOOM_EVENT:
            return self._zoom or self._zoomed_out
        parsed = parse_sequence(sequence)
        if getattr(parsed, "type", None) in _POINTER_EVENTS:
            return self.identify(int(event.x), int(event.y))
        return self._model.focus

    def _deliver_tags(self, sequence: str, event: Event) -> None:
        item = self._event_item(sequence, event)
        if not item or not self._model.exists(item):
            return
        for tag in self._model.item(item).tags:
            callback = self._tag_bindings.get(tag, {}).get(sequence)
            if callback is not None:
                callback(event)

    # ------------------------------------------------------------- the keys

    def _scene_now(self) -> Scene | None:
        width, height = self._rect.width, self._rect.height
        if width <= 0 or height <= 0:
            return None
        return self._scene(width, height)

    def _layout_now(self) -> TileLayout:
        scene = self._scene_now()
        return scene.layout if scene is not None else TileLayout((), ())

    def _arrow(self, direction: Direction) -> str | None:
        layout = self._layout_now()
        model = self._model
        current = layout.tile(model.focus) if model.focus else None
        if current is None:
            first = self._first(layout)
            if first is None:
                return None
            self.focus(first)
            return "break"
        target = None
        back = self._back
        if back is not None and back[0] == direction and back[1] == current.iid:
            target = back[2] if layout.tile(back[2]) is not None else None
        if target is None:
            level = [
                (tile.iid, tile.rect)
                for tile in layout.tiles
                if tile.level == current.level and tile.iid != current.iid
            ]
            target = neighbour(current.rect, level, direction)
        if target is None:
            return None
        model.focus = target
        self._back = (OPPOSITE[direction], target, current.iid)
        self._changed()
        return "break"

    def _first(self, layout: TileLayout) -> str | None:
        """The tile the first arrow focuses: the largest at the top of what
        is shown."""
        top = 1 if self._zoom else 0
        for tile in layout.tiles:
            if tile.level == top:
                return tile.iid
        return None

    def _return(self) -> str | None:
        item = self._model.focus
        if not item:
            return None
        if not self._zoom and self._model.get_children(item):
            self._zoom_into(item)
        else:
            self._select(item)
        return "break"

    def _zoom_into(self, group: str) -> None:
        self.zoom(group)
        children = self._model.ordered(group)
        self.focus(children[0] if children else "")

    def _space(self) -> str | None:
        if not self._model.focus:
            return None
        self._select(self._model.focus)
        return "break"

    def _escape(self) -> str | None:
        if self._zoom:
            group = self._zoom
            self._zoomed_out = group
            self.zoom("")
            self.focus(group)
            return "break"
        focused = self._model.focus
        if focused and self._model.exists(focused) and self._model.parent(focused):
            self.focus(self._model.parent(focused))
            return "break"
        return None

    def _click(self, x: int, y: int) -> None:
        self.focus_set()
        scene = self._scene_now()
        if scene is None:
            return
        tile = scene.layout.at(x, y)
        if tile is not None:
            self.focus(tile.iid)
            self._select(tile.iid)
            return
        entry = scene.legend.at(x, y) if scene.legend is not None else None
        if entry is not None:
            self.focus(entry)  # the legend points, and does not select

    def _double(self, x: int, y: int) -> None:
        tile = self._layout_now().at(x, y)
        if tile is None or self._zoom:
            return
        group = tile.iid if tile.group else self._model.parent(tile.iid)
        if group:
            self._zoom_into(group)

    # ------------------------------------------------------------ repainting

    def _changed(self) -> None:
        """Draw again once idle, however many changes come first."""
        if self._pending is None and self.winfo_exists():
            self._pending = self.after_idle(self._repaint)

    def _repaint(self) -> None:
        self._pending = None
        self._redraw()

    def destroy(self) -> None:
        """Cancel a pending repaint, then destroy the widget as any is."""
        if self._pending is not None:
            with contextlib.suppress(TclError):
                self.after_cancel(self._pending)
            self._pending = None
        self._follow_screen(False)
        super().destroy()

    # --------------------------------------------------------------- drawing

    def _depth(self) -> int:
        """The terminal's colours: 0 without any."""
        colors = self.tk.colors
        if colors is None or not colors.has_colors:
            return 0
        return int(colors.depth)

    def _palette(self) -> tuple[tuple[str, RGB], ...]:
        if not self._depth():
            return ()
        return tuple(
            (spec, rgb_of(spec) or (255, 255, 255)) for spec in self._config.colors
        )

    def _outlined(self, palette: tuple[tuple[str, RGB], ...]) -> frozenset[str]:
        model = self._model
        depth = self._depth()
        groups = {
            iid: len(kids)
            for iid in model.get_children()
            if (kids := model.get_children(iid))
        }
        distinct: dict[str, int] = {}
        if palette and depth:
            order = model.ordered()
            for group in groups:
                _spec, rgb = palette[order.index(group) % len(palette)]
                tier = ColorDepth(depth)
                resolved = {
                    (found.color, found.attr)
                    for found in (
                        parse_color(hex_color(shade), tier) for shade in shades_of(rgb)
                    )
                }
                distinct[group] = len(resolved)
        return outlined_levels(self._config.outline, depth, groups, distinct)  # type: ignore[arg-type]

    def _area(self, width: int, height: int) -> Rect:
        edge = 1 if self._bordered and width >= 2 and height >= 2 else 0
        return Rect(edge, edge, width - 2 * edge, height - 2 * edge)

    def _scene(self, width: int, height: int) -> Scene:
        """What a ``width`` by ``height`` frame is drawn from."""
        config = self._config
        model = self._model
        palette = self._palette()
        outlined = self._outlined(palette)
        area = self._area(width, height)
        if self._zoom and not (
            model.exists(self._zoom) and model.get_children(self._zoom)
        ):
            self._zoom = ""  # the group, or its last child, was deleted
        zoom = self._zoom
        key = (model.version, area, outlined, config, zoom)
        if self._cached is not None and self._cached[0] == key:
            _key, layout, cut, legend = self._cached
        else:
            cut, legend = self._regions(area, zoom)
            layout = lay_out(model, cut.tiles, zoom=zoom, outlined=outlined)
            self._cached = (key, layout, cut, legend)
        whole = model.total(zoom)

        def value_text(iid: str) -> str | None:
            size = model.size(iid)
            if config.values == "percent":
                return percent(size, whole, config.percentdecimals)
            if config.values == "value":
                return config.numbers.format(size)
            return None

        readout = self._readout(layout) if config.readout else ""
        return Scene(
            width,
            height,
            cut,
            layout,
            model,
            colors=palette,
            outlined=outlined,
            labels=config.labels,
            value_text=value_text,
            readout=readout,
            focus=model.focus,
            show_focus=self.focus_get() is self,
            selected=model.selected,
            legend=legend,
        )

    def _regions(self, area: Rect, zoom: str) -> tuple[Regions, LegendLayout | None]:
        """``area`` cut into tiles, legend and readout, and the legend's
        entries placed."""
        config = self._config
        listed = entries(self._model, zoom, config.nestedlegend)
        side = config.legendposition
        size = 0
        if shown(config.legend, listed):
            rest = area.take_bottom(1)[1] if config.readout else area
            size = extent(listed, side, config.legendsize, rest, config.legendlines)  # type: ignore[arg-type]
        cut = regions(
            area,
            readout=config.readout,
            legend=side if size else None,  # type: ignore[arg-type]
            legend_extent=size,
        )
        if cut.legend is None:
            return cut, None
        return cut, place(listed, cut.legend, side, config.legendlines)  # type: ignore[arg-type]

    def _readout(self, layout: TileLayout) -> str:
        """The bottom row: the focused item's place, value and shares; or,
        with nothing focused, the total and what is too small to show."""
        model = self._model
        config = self._config
        if not model.get_children():
            return ""
        focused = model.focus
        if focused and model.exists(focused):
            size = model.size(focused)
            names = [model.item(iid).text or iid for iid in model.path(focused)]
            text = PATH_SEPARATOR.join(names)
            text += f"   {config.numbers.format(size)}"
            text += f"   {percent(size, model.total(), config.percentdecimals)} of all"
            parent = model.parent(focused)
            if parent:
                share = percent(size, model.size(parent), config.percentdecimals)
                text += f"   {share} of {names[0]}"
            return text
        whole = model.total(self._zoom)
        text = f"total {config.numbers.format(whole)}"
        if self._zoom:
            name = model.item(self._zoom).text or self._zoom
            text = f"{name}{PATH_SEPARATOR}{text}"
        if layout.hidden:
            text += f" \u00b7 {len(layout.hidden)} too small to show"
        return text

    def _compose(self, width: int, height: int) -> list[list[Cell]]:
        """The treemap as rows of cells, ``width`` by ``height``, border
        cells included and left blank. Separate from painting so it can be
        checked without a terminal."""
        return compose(self._scene(width, height))

    def _attribute(self, cell: Cell) -> int:
        bold = curses.A_BOLD if cell.bold else curses.A_NORMAL
        if cell.reverse:
            bold |= curses.A_REVERSE
        colors = self.tk.colors
        if colors is None or not colors.has_colors:
            return bold
        fg = cell.fg or str(self._options["foreground"] or "white")
        bg = cell.bg or str(self._options["background"] or "black")
        return int(colors.attribute_for(fg, bg, bold))

    def _redraw(self) -> None:
        """Paint the frame and its box, then the tiles inside it."""
        super()._redraw()
        window = self._window
        if window is None or self.tk.screen is None:
            return
        width, height = self._rect.width, self._rect.height
        if width <= 0 or height <= 0:
            return
        area = self._area(width, height)
        grid = self._compose(width, height)
        dispatcher = CursesDispatcher.get()
        with contextlib.suppress(curses.error):
            for y in range(area.y, area.y + area.height):
                for start, text, attribute in self._runs(grid[y], area):
                    self._write_line(dispatcher, window, y, start, text, attribute)

    def _runs(self, row: list[Cell], area: Rect) -> list[tuple[int, str, int]]:
        """A row inside ``area`` as ``(column, text, attribute)`` runs."""
        runs: list[tuple[int, str, int]] = []
        for x in range(area.x, area.x + area.width):
            cell = row[x]
            if cell.char == "":
                continue
            attribute = self._attribute(cell)
            last = runs[-1] if runs else None
            if (
                last is not None
                and last[2] == attribute
                and last[0] + cells(last[1]) == x
            ):
                runs[-1] = (last[0], last[1] + cell.char, attribute)
            else:
                runs.append((x, cell.char, attribute))
        return runs


# ---------------------------------------------------------------- bindings


def _tree(event: Event) -> TreeMap | None:
    widget = event.widget
    return widget if isinstance(widget, TreeMap) else None


def _treemap_arrow(direction: Direction, event: Event) -> str | None:
    tree = _tree(event)
    return tree._arrow(direction) if tree is not None else None


def _treemap_return(event: Event) -> str | None:
    tree = _tree(event)
    return tree._return() if tree is not None else None


def _treemap_space(event: Event) -> str | None:
    tree = _tree(event)
    return tree._space() if tree is not None else None


def _treemap_escape(event: Event) -> str | None:
    tree = _tree(event)
    return tree._escape() if tree is not None else None


def _treemap_click(event: Event) -> None:
    tree = _tree(event)
    if tree is not None:
        tree._click(int(event.x), int(event.y))


def _treemap_double(event: Event) -> None:
    tree = _tree(event)
    if tree is not None:
        tree._double(int(event.x), int(event.y))


def _treemap_refocus(event: Event) -> None:
    """Draw again when the keyboard focus comes or goes: the focused tile
    is shown only while the treemap has it."""
    tree = _tree(event)
    if tree is not None:
        tree._changed()


def _treemap_tag_event(sequence: str, event: Event) -> None:
    """Deliver one event to the tag bindings of the item it is for."""
    tree = _tree(event)
    if tree is not None:
        tree._deliver_tags(sequence, event)
