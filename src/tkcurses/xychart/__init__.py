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

"""Line and area charts, drawn on a Canvas.

TkCurses extension:
    Neither tkinter nor Tk has a chart. This one follows the behaviour of
    Kibana's line and area charts - stacked, percentage and unstacked
    areas, straight, smooth and step lines, missing values, and Kibana's
    axis bounds - and is a :class:`tkcurses.Canvas`, drawing with canvas
    items a program can add to.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

import tkcurses
from tkcurses import TclError
from tkcurses._charts.color import DEFAULT_COLORS
from tkcurses._charts.geometry import Rect
from tkcurses._charts.options import choice, color, flag, items, number
from tkcurses._charts.scale import SCALE_TYPES
from tkcurses._charts.size import ScreenSize, dimension
from tkcurses._core.colors import rgb_of
from tkcurses._core.geometry import BORDER_WIDTH
from tkcurses.xychart._axes import BOUNDS
from tkcurses.xychart._fit import END_VALUES, MISSING
from tkcurses.xychart._model import Model
from tkcurses.xychart._path import INTERPOLATIONS, POINTS
from tkcurses.xychart._scene import Config, Item, scene
from tkcurses.xychart._stack import STACK_MODES

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

__all__ = ["NATURAL_SIZE", "XYChart"]

_T = TypeVar("_T")

#: The size a chart asks for on an axis whose width or height is not
#: given, in cells: room for a time axis's labels.
NATURAL_SIZE = (60, 16)
#: What :meth:`XYChart.series_configure` reads and sets.
_SERIES_OPTIONS = ("kind", "text", "color", "description", "hidden")


def _optional_number(value: Any, name: str) -> float | None:
    if value is None or value == "":
        return None
    return number(value, name)


def _parse(options: dict[str, Any]) -> Config:
    """The chart's own options, checked; ``ValueError`` names the first bad
    one."""
    colors = tuple(color(spec) for spec in items(options["colors"]))
    scaletype = choice(options["scaletype"], "scaletype", SCALE_TYPES)
    logbase = number(options["logbase"], "logbase")
    if not logbase > 1:
        raise ValueError(f"logbase must be above 1, not {logbase:g}")
    bounds = choice(options["bounds"], "bounds", BOUNDS)
    minimum = _optional_number(options["minimum"], "minimum")
    maximum = _optional_number(options["maximum"], "maximum")
    if minimum is not None and maximum is not None and not maximum > minimum:
        raise ValueError(f"maximum ({maximum:g}) must be above minimum ({minimum:g})")
    if scaletype == "log" and minimum is not None and not minimum > 0:
        raise ValueError(f"a log scale needs a minimum above 0, not {minimum:g}")
    return Config(
        colors=colors or DEFAULT_COLORS,
        stackmode=choice(options["stackmode"], "stackmode", STACK_MODES),
        interpolation=choice(options["interpolation"], "interpolation", INTERPOLATIONS),
        points=choice(options["points"], "points", POINTS),
        missing=choice(options["missing"], "missing", MISSING),
        endvalues=choice(options["endvalues"], "endvalues", END_VALUES),
        dottedgaps=flag(options["dottedgaps"]),
        scaletype=scaletype,  # type: ignore[arg-type]
        logbase=logbase,
        bounds=bounds,
        minimum=minimum,
        maximum=maximum,
        nicebounds=flag(options["nicebounds"]),
    )


class XYChart(tkcurses.Canvas):
    """A chart of line and area series against a value axis.

    Each *series* is a name and a list of points ``(x, y)``, added with
    :meth:`add_series` and changed with :meth:`set_series` and
    :meth:`append`. ``x`` is a number or a time - a ``datetime``, naive
    meaning local time, or a ``date`` - the same kind for every point;
    ``y`` is a number, or ``None`` where a value is missing. A series is
    drawn as a ``"line"``, or as an ``"area"`` filled down to zero or to
    the area below it.

    An XYChart is a :class:`tkcurses.Canvas`, and draws everything as
    canvas items tagged ``xychart``, so a program can draw on it too: its
    own items stay above the chart's and are never touched by it. A
    change is drawn once the program is idle, so a loop that appends a
    hundred points draws once, and the chart's items keep their ids from
    one drawing to the next.

    A bad option value raises :class:`tkcurses.TclError` and leaves the
    chart as it was, at creation and in :meth:`configure` alike.

    **Size.** ``width`` and ``height`` are each given on their own, in
    cells or as a percentage of the terminal: ``width="50%", height=10``
    asks for half the terminal's width and ten rows, and follows the
    terminal when it is resized. An axis not given asks for 60 columns or
    16 rows. As for any widget, this is a request: ``fill`` and
    ``expand`` give it more.

    **Half-cells.** A canvas draws in pixels half a cell tall, and a cell
    holds two colours at most. An area is filled in its line's colour
    mixed toward the background, at 256 colours and more; below that, in
    the line's own colour. Where three series meet in one cell, the last
    drawn shows. Every line is drawn after every fill, so no area hides a
    line.

    Options:
        colors: The colours series take in turn, in the order they were
            added, when a series has none of its own. Default green, red,
            blue, yellow, magenta and cyan.
        stackmode: How areas are drawn together. ``"stacked"`` (the
            default) puts each area on the ones before it;
            ``"percentage"`` does the same with each x's total made 100;
            ``"unstacked"`` draws each from zero. Lines never stack.
        interpolation: How points are joined: ``"straight"`` (the
            default); ``"smooth"``, a curve that never rises above or
            dips below the points it joins; or ``"step"``, each value
            held until the next x.
        points: A dot at each point given: ``"auto"`` (the default) when
            neighbouring points are four pixels apart or more;
            ``"show"``; or ``"hide"``.
        missing: What is drawn where a series has ``None`` between two
            values: ``"hide"`` (the default) leaves a gap; ``"zero"``;
            ``"linear"`` joins the values either side; ``"last"`` holds
            the one before; ``"next"`` takes the one after.
        endvalues: What is drawn where ``None`` comes before a series'
            first value or after its last, when ``missing`` fills gaps:
            ``"hide"`` (the default), ``"zero"``, or ``"nearest"``.
        dottedgaps: Draw the stretches ``missing`` filled in as dotted
            lines. Default False.
        scaletype: The value axis: ``"linear"`` (the default); ``"log"``,
            where each power of ``logbase`` takes the same height and a
            value at or below zero is missing; or ``"sqrt"``, by the
            square root.
        logbase: The base of a log axis, above 1. Default 10.
        bounds: How far the value axis reaches. ``"full"`` (the default)
            takes it to zero; ``"data"`` spans only the values, and acts
            as ``"full"`` when an area is drawn; ``"custom"`` runs from
            ``minimum`` to ``maximum``, cutting lines where they leave.
        minimum: The bottom of a ``"custom"`` axis; when not given, as
            ``"full"``.
        maximum: The top of a ``"custom"`` axis; when not given, as
            ``"full"``.
        nicebounds: Round the axis's ends out to round numbers, unless
            they are custom. Default True.

    The Canvas's own options are as on :class:`tkcurses.Canvas`:
    ``closeenough``, ``confine``, ``offset``, ``scrollregion``,
    ``xscrollincrement`` and ``yscrollincrement``. The chart is drawn
    from canvas coordinate 0, 0 at the canvas's size, and scrolls with
    every other item.

    Standard options, described in :doc:`/reference/options`:
    ``background``, ``borderwidth``, ``cursor``, ``height``,
    ``highlightbackground``, ``highlightcolor``, ``highlightthickness``,
    ``insertbackground``, ``insertborderwidth``, ``insertofftime``,
    ``insertontime``, ``insertwidth``, ``relief``, ``selectbackground``,
    ``selectborderwidth``, ``selectforeground``, ``state``, ``takefocus``,
    ``width``, ``xscrollcommand``, ``yscrollcommand``.

    Sample output:
        # size: 50x12
        from tkcurses.xychart import XYChart
        chart = XYChart(root)
        chart.pack(fill="both", expand=True)
        chart.add_series("cpu", [(t, 40 + (t * 7) % 30) for t in range(40)])
        chart.add_series("load", [(t, 10 + t) for t in range(40)])

    Sample output (colors):
        # size: 50x10
        from tkcurses.xychart import XYChart
        chart = XYChart(root, colors=["#4060c0", "#c08020"])
        chart.pack(fill="both", expand=True)
        chart.add_series("a", [(t, t % 9) for t in range(30)])
        chart.add_series("b", [(t, 9 - t % 9) for t in range(30)])

    Sample output (stackmode):
        # size: 60x10
        from tkcurses.xychart import XYChart
        for mode in ("stacked", "unstacked"):
            chart = XYChart(root, stackmode=mode, width=30)
            chart.pack(side="left", fill="y")
            chart.add_series("a", [(t, 4 + t % 5) for t in range(20)], kind="area")
            chart.add_series("b", [(t, 6) for t in range(20)], kind="area")

    Sample output (interpolation, points):
        # size: 60x10
        from tkcurses.xychart import XYChart
        for way in ("smooth", "step"):
            chart = XYChart(root, interpolation=way, points="show", width=30)
            chart.pack(side="left", fill="y")
            chart.add_series("a", [(0, 2), (4, 9), (8, 3), (12, 7)])

    Sample output (missing, endvalues, dottedgaps):
        # size: 60x10
        from tkcurses.xychart import XYChart
        values = [None, 3, 5, None, None, 8, 6, None]
        for missing in ("hide", "linear"):
            chart = XYChart(root, missing=missing, endvalues="nearest",
                            dottedgaps=True, width=30)
            chart.pack(side="left", fill="y")
            chart.add_series("a", list(enumerate(values)))

    Sample output (scaletype, logbase):
        # size: 60x10
        from tkcurses.xychart import XYChart
        for scale in ("linear", "log"):
            chart = XYChart(root, scaletype=scale, logbase=10, width=30)
            chart.pack(side="left", fill="y")
            chart.add_series("a", [(t, 2 ** t) for t in range(12)])

    Sample output (bounds, minimum, maximum, nicebounds):
        # size: 60x10
        from tkcurses.xychart import XYChart
        for options in ({"bounds": "data", "nicebounds": False},
                        {"bounds": "custom", "minimum": 20, "maximum": 60}):
            chart = XYChart(root, width=30, **options)
            chart.pack(side="left", fill="y")
            chart.add_series("a", [(t, 30 + (t * 13) % 40) for t in range(20)])
    """

    _widget_options: ClassVar[dict[str, Any]] = {
        # Not given: NATURAL_SIZE, rather than the Canvas's 40 by 10.
        "width": 0,
        "height": 0,
        "colors": (),
        "stackmode": "stacked",
        "interpolation": "straight",
        "points": "auto",
        "missing": "hide",
        "endvalues": "hide",
        "dottedgaps": False,
        "scaletype": "linear",
        "logbase": 10,
        "bounds": "full",
        "minimum": "",
        "maximum": "",
        "nicebounds": True,
    }

    _value_checks: ClassVar[dict[str, Callable[[Any, Any], Any]]] = {
        "width": dimension,
        "height": dimension,
    }

    #: The options this class adds, which :func:`_parse` checks.
    _own_options = frozenset(_widget_options) - {"width", "height"}

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
        #: The canvas item made for each scene key, with what it was given.
        self._made: dict[str, tuple[int, Item]] = {}
        #: Set while the chart changes its items, so each change does not
        #: repaint the canvas: it is repainted once at the end.
        self._syncing = False
        #: What the items were last made from.
        self._drawn_for: tuple[Any, ...] | None = None
        self._size = ScreenSize(self, NATURAL_SIZE, self._apply_requested_size)
        options = {**self._widget_options, **(cnf or {}), **kw}
        try:
            config = _parse({key: options[key] for key in self._own_options})
        except ValueError as error:
            raise TclError(str(error)) from None
        self._config = config
        super().__init__(master, cnf, name=name, **kw)

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
            self._config = config
        self._changed()
        return result

    config = configure

    def _apply_requested_size(self) -> None:
        """Ask for ``width`` by ``height``, each in cells or a share of the
        screen, and :data:`NATURAL_SIZE` on an axis not given, with the
        border and padding."""
        edge = 2 * BORDER_WIDTH if self._bordered else 0
        width, height = self._size.requested()
        self._request_size(
            width + 2 * int(self._options["padx"]) + edge,
            height + 2 * int(self._options["pady"]) + edge,
        )

    def _plane_size(self) -> tuple[int, int]:
        area = self._text_area()
        if area.width > 0 and area.height > 0:
            return (area.width, area.height * 2)
        width, height = self._size.requested()
        return (max(1, width), max(1, height) * 2)

    def destroy(self) -> None:
        """Cancel a pending drawing, then destroy the chart as any canvas."""
        if self._pending is not None:
            with contextlib.suppress(TclError):
                self.after_cancel(self._pending)
            self._pending = None
        self._size.follow(False)
        super().destroy()

    # -------------------------------------------------------------- series

    def add_series(
        self,
        name: str,
        points: Iterable[Any] = (),
        *,
        kind: str = "line",
        text: str = "",
        color: str = "",
        description: str = "",
    ) -> None:
        """Add a series, drawn after those already there.

        Args:
            name: What the series is called by every other method.
            points: Pairs ``(x, y)``, in any order.
            kind: ``"line"`` or ``"area"``.
            text: The name shown for it; ``name`` when not given.
            color: Its colour; the next of ``colors`` when not given.
            description: A note about it, shown in the legend.

        Raises:
            tkcurses.TclError: If a series of that name exists, a point is
                not a pair of finite numbers or times, or its x is not the
                kind the chart's other points are. Nothing is added.
        """
        if color:
            self._check(lambda: _checked_color(color))
        self._do(
            lambda: self._model.add(
                name,
                points,
                kind=kind,
                text=text,
                color=color,
                description=description,
            )
        )

    def set_series(self, name: str, points: Iterable[Any]) -> None:
        """Replace a series' points.

        Raises:
            tkcurses.TclError: If there is no such series or a point is
                bad. The series keeps the points it had.
        """
        self._do(lambda: self._model.set(name, points))

    def append(self, name: str, *points: Any) -> None:
        """Add points to a series. A point at an x the series has replaces
        that one.

        Raises:
            tkcurses.TclError: If there is no such series or a point is
                bad. None of them is added.
        """
        self._do(lambda: self._model.append(name, *points))

    def delete_series(self, *names: str) -> None:
        """Remove series.

        Raises:
            tkcurses.TclError: If any name is not a series. None is
                removed.
        """
        self._do(lambda: self._model.delete(*names))

    def series(self) -> tuple[str, ...]:
        """Every series' name, in the order they are drawn."""
        return tuple(self._model.names())

    def series_points(self, name: str) -> list[tuple[float, float | None]]:
        """A series' points, sorted by x. A time is given back as seconds
        since the epoch."""
        return self._check(lambda: self._model.get(name).points())

    def series_cget(self, name: str, option: str) -> Any:
        """One option of a series: ``kind``, ``text``, ``color``,
        ``description`` or ``hidden``."""
        series = self._check(lambda: self._model.get(name))
        if option not in _SERIES_OPTIONS:
            raise TclError(f'unknown option "-{option}"')
        return getattr(series, option)

    def series_configure(self, name: str, **options: Any) -> Any:
        """Change a series' ``kind``, ``text``, ``color``, ``description``
        or ``hidden``; with none, return them all. A hidden series is not
        drawn and takes no part in the stack or the axis.

        Raises:
            tkcurses.TclError: If there is no such series, or an option is
                unknown or bad. Nothing is changed.
        """
        series = self._check(lambda: self._model.get(name))
        if not options:
            return {option: getattr(series, option) for option in _SERIES_OPTIONS}
        for option in options:
            if option not in _SERIES_OPTIONS:
                raise TclError(f'unknown option "-{option}"')
        if options.get("color"):
            self._check(lambda: _checked_color(options["color"]))
        if "hidden" in options:
            options["hidden"] = self._check(lambda: flag(options["hidden"]))
        self._do(lambda: self._model.configure(name, **options))
        return None

    def _do(self, action: Callable[[], _T]) -> _T:
        result = self._check(action)
        self._changed()
        return result

    def _check(self, action: Callable[[], _T]) -> _T:
        try:
            return action()
        except ValueError as error:
            raise TclError(str(error)) from None

    # ------------------------------------------------------------- drawing

    def _changed(self) -> None:
        """Draw again once the program is idle."""
        if getattr(self, "_pending", "") is None:
            self._pending = self.after_idle(self._update)

    def _update(self) -> None:
        self._pending = None
        if self.winfo_exists():
            self._sync()
            self._redraw()

    def _redraw(self) -> None:
        if getattr(self, "_syncing", True):
            return  # mid-change, or not yet made: one repaint at the end
        if self._drawn_for is not None and self._drawn_for != self._drawn_key():
            self._sync()  # resized since the items were made
        super()._redraw()

    def _plot(self) -> Rect:
        """Where the series are drawn, in pixels."""
        width, height = self._plane_size()
        return Rect(0, 0, width, height)

    def _depth(self) -> int:
        colors = self.tk.colors
        if colors is None or not colors.has_colors:
            return 0
        return int(colors.depth)

    def _drawn_key(self) -> tuple[Any, ...]:
        return (self._model.version, self._config, self._plot(), self._depth())

    def _sync(self) -> None:
        """Make the canvas items match the scene: changed in place where a
        key is still there, made where it is new, deleted where it went."""
        key = self._drawn_key()
        background = rgb_of(str(self._options["background"] or "black")) or (0, 0, 0)
        wanted = scene(
            self._model,
            self._config,
            self._plot(),
            depth=self._depth(),
            rgb=rgb_of,
            background=background,
        )
        self._syncing = True
        try:
            made_new = False
            for item in wanted:
                had = self._made.get(item.key)
                if had is not None and had[1].kind == item.kind:
                    ident, before = had
                    if before.coords != item.coords:
                        self.coords(ident, *item.coords)
                    if before.options != item.options or before.tags != item.tags:
                        self.itemconfigure(ident, tags=item.tags, **dict(item.options))
                else:
                    if had is not None:
                        self.delete(had[0])
                    ident = getattr(self, f"create_{item.kind}")(
                        *item.coords, tags=item.tags, **dict(item.options)
                    )
                    made_new = True
                self._made[item.key] = (ident, item)
            keep = {item.key for item in wanted}
            for gone in [k for k in self._made if k not in keep]:
                self.delete(self._made.pop(gone)[0])
            if made_new:
                # The chart's items in drawing order, under the program's.
                for item in reversed(wanted):
                    self.tag_lower(self._made[item.key][0])
        finally:
            self._syncing = False
        self._drawn_for = key


def _checked_color(spec: str) -> str:
    return color(spec)
