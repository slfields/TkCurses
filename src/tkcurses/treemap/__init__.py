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
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import tkcurses
from tkcurses import TclError
from tkcurses._charts.color import DEFAULT_COLORS, hex_color
from tkcurses._charts.geometry import Rect
from tkcurses._charts.numformat import PLACEMENTS, ROUNDINGS, UNIT_SCALES, NumberFormat
from tkcurses._charts.options import choice, color, count, flag, items, optional_count
from tkcurses._core.cells import cells
from tkcurses._core.colors import ColorDepth, parse_color, rgb_of
from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses.treemap._compose import Cell, Scene, compose
from tkcurses.treemap._labels import percent
from tkcurses.treemap._layout import Regions, TileLayout, lay_out, regions
from tkcurses.treemap._model import Model
from tkcurses.treemap._shades import OUTLINE_MODES, outlined_levels, shades_of

if TYPE_CHECKING:
    from collections.abc import Callable

    from tkcurses._charts.color import RGB

__all__ = ["Treemap"]

VALUES = ("percent", "value", "none")
#: The size a treemap asks for when neither width nor height is given.
NATURAL_SIZE = (40, 12)


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


def _parse(options: dict[str, Any]) -> _Config:
    decimals = count(options["percentdecimals"], "percentdecimals", minimum=0)
    if decimals > 10:
        raise ValueError(f"percentdecimals must be at most 10, not {decimals}")
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
    )


class Treemap(tkcurses.Frame):
    """A treemap: named values drawn as rectangles, each sized by its value.

    Items are added as a :class:`tkcurses.ttk.Treeview`'s are, with
    :meth:`insert`, and have two levels at most. An item at the top level
    may hold *children*; it is then a *group*, its size is the sum of
    theirs, and their tiles are drawn inside its own, in shades of its
    colour, under a header row when it has room. The rectangles are laid
    out largest first, as near square to the eye as the squarified
    algorithm makes them.

    A Treemap is a :class:`tkcurses.Frame`, placed with ``pack``, ``grid``
    or ``place`` like any widget. A change to the items is drawn once the
    program is idle, so a loop that changes a hundred of them is drawn
    once.

    A bad option value raises :class:`tkcurses.TclError` and leaves the
    treemap as it was, at creation and in :meth:`configure` alike.

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
        from tkcurses.treemap import Treemap
        tree = Treemap(root)
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
        from tkcurses.treemap import Treemap
        for labels, values in ((True, "percent"), (False, "value")):
            tree = Treemap(root, labels=labels, values=values, width=30)
            tree.pack(side="left", fill="y")
            for name, size in (("nginx", 330), ("apache", 170), ("php", 50)):
                tree.insert("", "end", text=name, value=size)

    Sample output (percentdecimals):
        # size: 60x8
        from tkcurses.treemap import Treemap
        for places in (0, 3):
            tree = Treemap(root, percentdecimals=places, width=30)
            tree.pack(side="left", fill="y")
            for name, size in (("nginx", 330), ("apache", 170), ("php", 50)):
                tree.insert("", "end", text=name, value=size)

    Sample output (colors):
        from tkcurses.treemap import Treemap
        tree = Treemap(root, colors=["#4060c0", "#c08020"])
        tree.pack(fill="both", expand=True)
        tree.insert("", "end", "web", text="web")
        for name, size in (("nginx", 330), ("apache", 170), ("php", 50)):
            tree.insert("web", "end", text=name, value=size)
        tree.insert("", "end", text="cache", value=200)

    Sample output (outline):
        # size: 60x10
        from tkcurses.treemap import Treemap
        for outline in ("auto", "on"):
            tree = Treemap(root, outline=outline, width=30)
            tree.pack(side="left", fill="y")
            tree.insert("", "end", "web", text="web")
            for name, size in (("nginx", 330), ("apache", 170), ("php", 50)):
                tree.insert("web", "end", text=name, value=size)
            tree.insert("", "end", text="cache", value=200)

    Sample output (readout):
        # size: 50x10
        from tkcurses.treemap import Treemap
        for readout in (True, False):
            tree = Treemap(root, readout=readout, height=5)
            tree.pack(fill="x")
            for size in (5000, 3000, 1):
                tree.insert("", "end", text=f"{size}", value=size)

    Sample output (units, unitplacement, unitspace):
        # size: 60x8
        from tkcurses.treemap import Treemap
        for units, placement in (("B", "suffix"), ("$", "prefix")):
            tree = Treemap(root, values="value", units=units, width=30,
                           unitplacement=placement, unitspace=units == "B")
            tree.pack(side="left", fill="y")
            for name, size in (("nginx", 330), ("apache", 170), ("php", 50)):
                tree.insert("", "end", text=name, value=size)

    Sample output (digits, decimals, rounding):
        # size: 60x8
        from tkcurses.treemap import Treemap
        for options in ({"digits": 1, "rounding": "up"}, {"decimals": 2}):
            tree = Treemap(root, values="value", width=30, **options)
            tree.pack(side="left", fill="y")
            for name, size in (("nginx", 1234), ("apache", 170), ("php", 50)):
                tree.insert("", "end", text=name, value=size)

    Sample output (unitscale):
        # size: 60x8
        from tkcurses.treemap import Treemap
        for scale, units in (("binary", "B"), ("time", "s")):
            tree = Treemap(root, values="value", unitscale=scale,
                           units=units, digits=3, width=30)
            tree.pack(side="left", fill="y")
            for size in (400_000, 250_000, 90_000):
                tree.insert("", "end", text=scale, value=size)
    """

    _widget_options: ClassVar[dict[str, Any]] = {
        "relief": "solid",  # so borderwidth=1 alone draws the box
        "foreground": "",
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
    }

    #: Frame hides ``foreground``; a Treemap writes its readout in it.
    _not_tk_options: ClassVar[frozenset[str]] = frozenset()

    #: The options this class adds and :func:`_parse` checks.
    _own_options = frozenset(_widget_options) - {"relief", "foreground"}

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
        self._cached: tuple[Any, TileLayout, Regions] | None = None
        options = {**self._widget_options, **(cnf or {}), **kw}
        try:
            config = _parse({key: options[key] for key in self._own_options})
        except ValueError as error:
            raise TclError(str(error)) from None
        self._config = config
        super().__init__(master, cnf, name=name, **kw)
        self._apply(config)

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
        """Ask for :data:`NATURAL_SIZE` unless width or height is set."""
        if int(self._options["width"]) or int(self._options["height"]):
            super()._apply_requested_size()
            return
        self._request_size(*NATURAL_SIZE)

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

        Raises:
            tkcurses.TclError: ``parent`` is not an item, or is a child;
                ``iid`` is in use; ``value`` is not a number, or negative.
        """
        return str(
            self._do(
                lambda: self._model.insert(parent, index, iid, text=text, value=value)
            )
        )

    def item(self, iid: str, option: str | None = None, **kw: Any) -> Any:
        """Read or change an item's ``text`` and ``value``.

        With neither ``option`` nor keywords, a dict of both; with
        ``option``, that one; with keywords, they are set.
        """
        entry = self._ask(lambda: self._model.item(iid))
        unknown = set(kw) - {"text", "value"}
        if option is not None and option not in ("text", "value"):
            unknown.add(option)
        if unknown:
            raise TclError(f'unknown option "-{sorted(unknown)[0]}"')
        if kw:
            self._do(
                lambda: self._model.configure(
                    iid, text=kw.get("text"), value=kw.get("value")
                )
            )
            return None
        values = {"text": entry.text, "value": entry.value}
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
        key = (model.version, area, outlined, config.readout)
        if self._cached is not None and self._cached[0] == key:
            _key, layout, cut = self._cached
        else:
            cut = regions(area, readout=config.readout)
            layout = lay_out(model, cut.tiles, outlined=outlined)
            self._cached = (key, layout, cut)
        whole = model.total()

        def value_text(iid: str) -> str | None:
            size = model.size(iid)
            if config.values == "percent":
                return percent(size, whole, config.percentdecimals)
            if config.values == "value":
                return config.numbers.format(size)
            return None

        readout = ""
        if config.readout and model.get_children():
            readout = f"total {config.numbers.format(whole)}"
            if layout.hidden:
                readout += f" · {len(layout.hidden)} too small to show"
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
        )

    def _compose(self, width: int, height: int) -> list[list[Cell]]:
        """The treemap as rows of cells, ``width`` by ``height``, border
        cells included and left blank. Separate from painting so it can be
        checked without a terminal."""
        return compose(self._scene(width, height))

    def _attribute(self, cell: Cell) -> int:
        bold = curses.A_BOLD if cell.bold else curses.A_NORMAL
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
