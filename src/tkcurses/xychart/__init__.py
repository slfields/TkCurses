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
    areas, straight, smooth and step lines, missing values, Kibana's
    axis bounds, reference lines, a legend with statistics, and a
    crosshair with a readout - and is a :class:`tkcurses.Canvas`,
    drawing with canvas items a program can add to.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import time as _time
from bisect import bisect_right
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

import tkcurses
from tkcurses import TclError
from tkcurses._charts.color import DEFAULT_COLORS
from tkcurses._charts.legend import LEGEND_MODES, LEGEND_SIZES, MAX_LINES, POSITIONS
from tkcurses._charts.options import (
    NUMBER_OPTIONS,
    choice,
    color,
    count,
    flag,
    items,
    number,
    number_format,
)
from tkcurses._charts.scale import SCALE_TYPES
from tkcurses._charts.size import ScreenSize, dimension
from tkcurses._core.colors import rgb_of
from tkcurses._core.geometry import BORDER_WIDTH
from tkcurses.xychart._axes import BOUNDS
from tkcurses.xychart._fit import END_VALUES, MISSING
from tkcurses.xychart._model import Model, checked_x
from tkcurses.xychart._path import INTERPOLATIONS, POINTS
from tkcurses.xychart._scene import Config, Drawing, Item, Reference, chart
from tkcurses.xychart._stack import STACK_MODES
from tkcurses.xychart._stats import STATISTICS

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from tkcurses import Event

__all__ = ["CURSOR_EVENT", "LEGEND_EVENT", "NATURAL_SIZE", "XYChart"]

_T = TypeVar("_T")

#: The size a chart asks for on an axis whose width or height is not
#: given, in cells: room for a time axis's labels.
NATURAL_SIZE = (60, 16)
#: What :meth:`XYChart.series_configure` reads and sets.
_SERIES_OPTIONS = ("kind", "text", "color", "description", "hidden")
#: Sent when the crosshair moves or goes.
CURSOR_EVENT = "<<XYChartCursor>>"
#: Sent when a click or Space on the legend hides or shows a series;
#: :meth:`XYChart.legend_focus` names it.
LEGEND_EVENT = "<<XYChartLegend>>"
#: Stands for "not given" to :meth:`XYChart.cursor`, where ``None``
#: removes the crosshair.
_NOT_GIVEN: Any = object()
#: The axes a reference line may be on.
_REFERENCE_AXES = ("y", "x")


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
    lines = count(options["legendlines"], "legendlines", minimum=1)
    if lines > MAX_LINES:
        raise ValueError(f"legendlines must be at most {MAX_LINES}, not {lines}")
    stats = tuple(
        choice(stat, "legendstats", STATISTICS)
        for stat in items(options["legendstats"])
    )
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
        xlabel=str(options["xlabel"]),
        ylabel=str(options["ylabel"]),
        ticklabels=flag(options["ticklabels"]),
        gridlines=flag(options["gridlines"]),
        nowmarker=flag(options["nowmarker"]),
        numbers=number_format(options),
        legend=choice(options["legend"], "legend", LEGEND_MODES),
        legendposition=choice(options["legendposition"], "legendposition", POSITIONS),
        legendsize=choice(options["legendsize"], "legendsize", ("auto", *LEGEND_SIZES)),
        legendlines=lines,
        legendstats=stats,
        readout=flag(options["readout"]),
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

    **Axes.** The value axis is on the left and x along the bottom, each
    with ticks at as many round values as their labels fit, and times
    ticked at steps a clock or calendar reads: ``14:05``, ``Nov 24``,
    with the day or year the first tick is in written once below. Text
    takes whole cells, so the axes are drawn outside the plot. A chart
    too small for a plot eight columns by two rows with its axes is drawn
    without them.

    **Reference lines.** :meth:`reference_add` draws a line across the
    plot at a value, or down it at an x, with an optional shaded band;
    the band goes under the series and the line over them.

    **Legend.** With two series or more, a legend beside the chart names
    each in its colour, with its description and any of the figures
    ``legendstats`` asks for. Clicking an entry hides its series, and
    clicking again shows it; a hidden series keeps a hollow entry.

    **Crosshair and readout.** The chart takes the focus. **Left** and
    **Right** move a crosshair to the previous or next x of any series,
    **Home** and **End** to the first and last, and a click puts it at
    the x nearest the mouse; **Escape** removes it. Each series' point
    there is marked, and the bottom row reads out the x and each value
    in its series' colour; with no crosshair, it names the range of x.
    ``<<XYChartCursor>>`` is sent when the crosshair moves or goes, and
    :meth:`cursor` reads or sets it. **Up** and **Down** move along the
    legend's entries, and **Space** hides or shows the one underlined.
    Hiding or showing a series from the legend, by Space or a click,
    sends ``<<XYChartLegend>>``, and :meth:`legend_focus` names it.
    The crosshair stays at its x as the data changes, or moves to the
    nearest x left of it when that x has gone. A key the chart uses goes
    no further; one it has nothing to do with - **Escape** with no
    crosshair and no entry underlined - reaches the window's bindings,
    so an Escape that closes a dialog still does.

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
        xlabel: A title under the x axis. Default none.
        ylabel: A title above the value axis. Default none.
        ticklabels: Write the values at the ticks. Default True; without
            them the axes keep their lines and ticks and the plot is
            wider and taller.
        gridlines: Draw a dotted line across the plot at each tick of
            both axes, under the series. Default False.
        nowmarker: On an x axis of times, a line down the plot at the
            time the chart was last drawn, when that is on the axis.
            Default False.
        units: Written with every value on the value axis: ``"%"``,
            ``"ms"``, ``"B"``, ``"$"``. Default none. A percentage stack's
            axis is written in ``%`` whatever this says.
        unitplacement: ``"suffix"`` (the default), after the number; or
            ``"prefix"``, before it, for a currency: ``$1.2k``.
        unitspace: A space between the number and what follows it:
            ``50 ms`` rather than ``50ms``. Default False.
        digits: Significant digits, 1 to 15; a value whose whole part
            needs more is scaled, with the scale's letter: with 3, 1234 is
            ``1.23k``. Default none: up to six.
        decimals: A fixed count of decimals, 0 to 15: with 1, 5 is
            ``5.0``. Default none: as many as the digits need.
        rounding: How a value cut to its digits is rounded: ``"nearest"``
            (the default), ``"down"`` or ``"up"``. Ticks fall on round
            values, so it shows in the legend's figures and the readout.
        unitscale: How a value is scaled to the fewest digits. ``"si"``
            (the default): by thousands, k, M, G, and for a unit other
            than ``"%"`` by m, µ, n below 1. ``"binary"``: by 1024s, Ki,
            Mi, Gi, for bytes. ``"time"``: ``units`` names the unit the
            data is in, ``"ms"``, ``"s"``, ``"min"`` and the rest, and each
            value is written in the largest it reaches one of, ticked at
            steps a clock reads. ``"none"``: never.

        legend: ``"auto"`` (the default) shows the legend for two series
            or more; ``"show"``; or ``"hide"``.
        legendposition: ``"right"`` (the default), ``"left"``, ``"top"``
            or ``"bottom"``.
        legendsize: The legend's width at the left or right: ``"auto"``
            (the default), as wide as its widest entry up to a third of
            the chart; or ``"small"``, ``"medium"``, ``"large"`` or
            ``"xlarge"``, 12, 20, 28 or 36 columns.
        legendlines: The most lines a name, a description or the figures
            wrap onto, 1 to 5. Default 1.
        legendstats: Figures written under each series' name, over the
            values it draws: any of ``"average"``, ``"median"``,
            ``"min"``, ``"max"``, ``"range"``, ``"last"``,
            ``"lastnonnull"``, ``"first"``, ``"firstnonnull"``,
            ``"difference"``, ``"differencepercent"``, ``"sum"``,
            ``"count"``, ``"distinctcount"``, ``"variance"`` and
            ``"stddev"``. Default none.
        readout: Give the bottom row to the readout. Default True.

    The number format is BarGraph's and TreeMap's, by the same names. The
    x axis writes numbers plainly. The legend's figures and the readout
    are written to three significant digits when neither ``digits`` nor
    ``decimals`` is given.

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

    Sample output (xlabel, ylabel, gridlines):
        # size: 60x14
        from tkcurses.xychart import XYChart
        chart = XYChart(root, xlabel="minute", ylabel="requests",
                        gridlines=True)
        chart.pack(fill="both", expand=True)
        chart.add_series("web", [(t, 20 + (t * 7) % 30) for t in range(40)])
        chart.reference_add(60, text="limit", color="red", band=(55, 65))

    Sample output (ticklabels):
        # size: 60x10
        from tkcurses.xychart import XYChart
        for labels in (True, False):
            chart = XYChart(root, ticklabels=labels, width=30)
            chart.pack(side="left", fill="y")
            chart.add_series("a", [(t, 30 + (t * 13) % 40) for t in range(20)])

    Sample output (units, unitplacement, unitspace):
        # size: 60x10
        from tkcurses.xychart import XYChart
        for units, placement in (("ms", "suffix"), ("$", "prefix")):
            chart = XYChart(root, units=units, unitplacement=placement,
                            unitspace=units == "ms", width=30)
            chart.pack(side="left", fill="y")
            chart.add_series("a", [(t, 900 + (t * 130) % 400) for t in range(20)])

    Sample output (digits, decimals, unitscale):
        # size: 60x10
        from tkcurses.xychart import XYChart
        for options in ({"digits": 2, "decimals": 1},
                        {"units": "ms", "unitscale": "time"}):
            chart = XYChart(root, width=30, **options)
            chart.pack(side="left", fill="y")
            chart.add_series("a", [(t, 1000 * t * t) for t in range(20)])

    Sample output (legend, legendstats, readout, rounding):
        # size: 72x12
        from tkcurses.xychart import XYChart
        chart = XYChart(root, legendstats=["average", "max"], units="%",
                        digits=2, rounding="down")
        chart.pack(fill="both", expand=True)
        chart.add_series("cpu", [(t, 40 + (t * 7) % 30) for t in range(30)])
        chart.add_series("load", [(t, 10 + t) for t in range(30)])
        chart.cursor(12)

    Sample output (legendposition, legendsize, legendlines):
        # size: 60x12
        from tkcurses.xychart import XYChart
        chart = XYChart(root, legendposition="left", legendsize="small",
                        legendlines=2, readout=False)
        chart.pack(fill="both", expand=True)
        chart.add_series("requests per second", [(t, t % 7) for t in range(30)])
        chart.add_series("errors", [(t, t % 3) for t in range(30)])

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
        "xlabel": "",
        "ylabel": "",
        "ticklabels": True,
        "gridlines": False,
        "nowmarker": False,
        **NUMBER_OPTIONS,
        "legend": "auto",
        "legendposition": "right",
        "legendsize": "auto",
        "legendlines": 1,
        "legendstats": (),
        "readout": True,
        # The chart takes the focus, for its keys.
        "takefocus": True,
    }

    _value_checks: ClassVar[dict[str, Callable[[Any, Any], Any]]] = {
        "width": dimension,
        "height": dimension,
    }

    #: The options this class adds, which :func:`_parse` checks.
    _own_options = frozenset(_widget_options) - {"width", "height", "takefocus"}

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
        self._references: dict[str, Reference] = {}
        self._reference_count = 0
        #: What was last drawn, and where: what a click is on.
        self._drawing = Drawing()
        #: The crosshair's x, or None.
        self._cursor: float | None = None
        #: The series whose legend entry has the keyboard.
        self._legend_focus: str | None = None
        self._size = ScreenSize(self, NATURAL_SIZE, self._apply_requested_size)
        options = {**self._widget_options, **(cnf or {}), **kw}
        try:
            config = _parse({key: options[key] for key in self._own_options})
        except ValueError as error:
            raise TclError(str(error)) from None
        self._config = config
        super().__init__(master, cnf, name=name, **kw)
        self._install_chart_bindings()

    def _install_chart_bindings(self) -> None:
        """The keys and the click, bound once for the class. The Canvas
        bound its own mouse routing to this class already; the click
        handler here replaces it, and calls it first, so a program's
        ``tag_bind`` on a chart item still fires."""
        name = self.winfo_class()
        marker = f"{name}:chart"
        if marker in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(marker)
        for key in ("Left", "Right", "Home", "End", "Up", "Down", "Escape", "space"):
            self.bind_class(name, f"<Key-{key}>", _chart_key)
        # A second click soon after the first is a double click, which
        # Tk sends instead of <Button-1>: two entries clicked in quick
        # succession must both toggle.
        self.bind_class(name, "<Button-1>", _chart_click)
        self.bind_class(name, "<Double-Button-1>", _chart_click)
        self.bind_class(name, "<FocusIn>", _chart_refocus)
        self.bind_class(name, "<FocusOut>", _chart_refocus)

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

    def series_points(self, name: str) -> list[tuple[Any, float | None]]:
        """A series' points, sorted by x, as :meth:`set_series` takes them:
        on a chart of times, each x is a naive ``datetime`` in local time,
        whatever it was given as; otherwise a float."""
        points = self._check(lambda: self._model.get(name).points())
        if self._model.xkind != "time":
            return points
        return [(_dt.datetime.fromtimestamp(x), y) for x, y in points]

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

    # ----------------------------------------------------------- crosshair

    def legend_focus(self) -> str:
        """The series whose legend entry was last chosen - by Up or Down,
        or by a click - or ``""`` when none is. In a handler for
        ``<<XYChartLegend>>``, it is the series just hidden or shown.
        """
        return self._legend_focus or ""

    def cursor(self, x: Any = _NOT_GIVEN) -> Any:
        """The crosshair's x, or ``None`` when there is none; with ``x``,
        put it at the x of any shown series nearest that, or remove it
        with ``None``. On a chart of times the x is a naive ``datetime``
        in local time.

        Raises:
            tkcurses.TclError: If ``x`` is not a number or a time.
        """
        if x is _NOT_GIVEN:
            if self._cursor is None:
                return None
            if self._model.xkind == "time":
                return _dt.datetime.fromtimestamp(self._cursor)
            return self._cursor
        if x is None:
            self._set_cursor(None)
            return None
        where, _ = self._check(lambda: checked_x(x))
        xs = self._model.xs()
        if xs:
            self._set_cursor(min(xs, key=lambda each: abs(each - where)))
        return None

    def _set_cursor(self, x: float | None, *, redraw: bool = True) -> None:
        if x != self._cursor:
            self._cursor = x
            if redraw:
                self._changed()
            self.event_generate(CURSOR_EVENT)

    def _keep_cursor(self) -> None:
        """After a change to the data, keep the crosshair at its x, or move
        it to the nearest x left of it when that has gone. Called while
        drawing, which then draws it where it went."""
        if self._cursor is None:
            return
        xs = self._model.xs()
        if not xs:
            self._set_cursor(None, redraw=False)
        elif self._cursor not in xs:
            at = bisect_right(xs, self._cursor)
            self._set_cursor(xs[at - 1] if at else xs[0], redraw=False)

    def _key(self, key: str) -> str | None:
        """Act on a key; ``"break"`` when it was used, so it goes no
        further, and ``None`` when the chart had nothing to do with it,
        so the window's own binding for it still runs."""
        xs = self._model.xs()
        if key in ("Left", "Right", "Home", "End") and xs:
            now = self._cursor
            if key == "Home":
                self._set_cursor(xs[0])
            elif key == "End":
                self._set_cursor(xs[-1])
            elif now is None:
                self._set_cursor(xs[-1] if key == "Left" else xs[0])
            else:
                at = xs.index(now) if now in xs else bisect_right(xs, now) - 1
                step = -1 if key == "Left" else 1
                self._set_cursor(xs[max(0, min(len(xs) - 1, at + step))])
            return "break"
        if key == "Escape":
            if self._cursor is None and self._legend_focus is None:
                return None
            self._legend_focus = None
            self._set_cursor(None)
            self._changed()
            return "break"
        if key in ("Up", "Down"):
            entries = list(self._drawing.entries) if self._drawing.legend else []
            if not entries:
                return None
            step = 1 if key == "Down" else -1
            if self._legend_focus in entries:
                at = entries.index(self._legend_focus) + step
                at = max(0, min(len(entries) - 1, at))
            else:
                at = 0 if key == "Down" else len(entries) - 1
            self._legend_focus = entries[at]
            self._changed()
            return "break"
        if key == "space" and self._legend_focus in self._model.names():
            self._toggle(self._legend_focus)
            return "break"
        return None

    def _toggle(self, name: str) -> None:
        """Hide or show ``name`` from the legend, and say so: the
        program's own :meth:`series_configure` sends nothing, as Tk
        reports no configure a program makes itself."""
        hidden = self._model.get(name).hidden
        self.series_configure(name, hidden=not hidden)
        self.event_generate(LEGEND_EVENT)

    def _click(self, column: int, row: int) -> None:
        """A click on the legend hides or shows its series; on the plot, it
        puts the crosshair at the nearest x."""
        drawing = self._drawing
        if drawing.legend is not None:
            name = drawing.legend.at(column, row)
            if name is not None and name in self._model.names():
                self._legend_focus = name
                self._toggle(name)
                return
        plot = drawing.plot
        if plot is None or not drawing.xs:
            return
        if not (
            plot.x <= column < plot.x + plot.width
            and plot.y <= row < plot.y + plot.height
        ):
            return
        span = drawing.xspan
        if span is None:
            self._set_cursor(drawing.xs[0])
            return
        fraction = (column - plot.x) / max(1, plot.width - 1)
        where = span.minimum + fraction * (span.maximum - span.minimum)
        self._set_cursor(min(drawing.xs, key=lambda each: abs(each - where)))

    # ---------------------------------------------------------- references

    def reference_add(
        self,
        value: Any,
        *,
        text: str = "",
        color: str = "",
        band: tuple[Any, Any] | None = None,
        axis: str = "y",
    ) -> str:
        """Draw a reference line, and return its id.

        Args:
            value: Where the line is: a value on the value axis, or with
                ``axis="x"`` an x, a number or a time as the series' are.
            text: Written by the line, at its right-hand end, or at its top
                on the x axis.
            color: The line's colour; white when not given.
            band: ``(low, high)``: also shade that range, in the colour
                dimmed as an area's fill is, under the series.
            axis: ``"y"`` (the default), a line across the plot; or
                ``"x"``, a line down it.

        Raises:
            tkcurses.TclError: If a value is not a number, or a time on an x
                axis of numbers, or the reverse; or the colour or axis is
                bad. Nothing is drawn.
        """
        axis = self._check(lambda: choice(axis, "axis", _REFERENCE_AXES))
        place = self._check(lambda: self._reference_value(axis))
        where = self._check(lambda: place(value))
        ends = None
        if band is not None:
            pair = self._check(lambda: items(band))
            if len(pair) != 2:
                raise TclError(f"band must be two values, low and high, not {band!r}")
            ends = (
                self._check(lambda: place(pair[0])),
                self._check(lambda: place(pair[1])),
            )
        if color:
            self._check(lambda: _checked_color(color))
        self._reference_count += 1
        ident = f"ref{self._reference_count}"
        self._references[ident] = Reference(
            ident, where, str(text), str(color), ends, axis
        )
        self._changed()
        return ident

    def reference_delete(self, *idents: str) -> None:
        """Remove reference lines by id.

        Raises:
            tkcurses.TclError: If any id is not a reference. None is
                removed.
        """
        for ident in idents:
            if ident not in self._references:
                raise TclError(f"Reference {ident} not found")
        for ident in idents:
            self._references.pop(ident, None)
        self._changed()

    def references(self) -> tuple[str, ...]:
        """Every reference line's id, in the order they were added."""
        return tuple(self._references)

    def _reference_value(self, axis: str) -> Callable[[Any], float]:
        """How a reference's value is read on ``axis``."""
        if axis == "y":
            return lambda value: number(value, "value")
        kind = self._model.xkind

        def place(value: Any) -> float:
            where, given = checked_x(value)
            if kind is not None and given != kind:
                wanted = "a time" if kind == "time" else "a number"
                raise ValueError(
                    f"the x axis is of {kind}s: a reference there needs {wanted}"
                )
            return where

        return place

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
            self._keep_cursor()  # drawn in this same pass
            self._sync()
            self._redraw()

    def _redraw(self) -> None:
        if getattr(self, "_syncing", True):
            return  # mid-change, or not yet made: one repaint at the end
        if self._drawn_for is not None and self._drawn_for != self._drawn_key():
            self._sync()  # resized since the items were made
        super()._redraw()

    def _cells(self) -> tuple[int, int]:
        """The canvas's size in cells, where the chart is laid out."""
        width, height = self._plane_size()
        return (width, height // 2)

    def _depth(self) -> int:
        colors = self.tk.colors
        if colors is None or not colors.has_colors:
            return 0
        return int(colors.depth)

    def _drawn_key(self) -> tuple[Any, ...]:
        return (
            self._model.version,
            self._config,
            self._cells(),
            self._depth(),
            tuple(self._references.values()),
            self._cursor,
            self._legend_focus if self._has_focus() else None,
        )

    def _has_focus(self) -> bool:
        try:
            return self.focus_get() is self
        except (KeyError, TclError):
            return False

    def _sync(self) -> None:
        """Make the canvas items match the scene: changed in place where a
        key is still there, made where it is new, deleted where it went."""
        key = self._drawn_key()
        background = rgb_of(str(self._options["background"] or "black")) or (0, 0, 0)
        width, height = self._cells()
        drawing = chart(
            self._model,
            self._config,
            width,
            height,
            depth=self._depth(),
            rgb=rgb_of,
            background=background,
            references=tuple(self._references.values()),
            now=_time.time(),
            xkind=self._model.xkind or "number",
            cursor=self._cursor,
            legend_focus=self._legend_focus if self._has_focus() else None,
        )
        self._drawing = drawing
        wanted = drawing.items
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


def _chart_of(event: Event) -> XYChart | None:
    widget = event.widget
    return widget if isinstance(widget, XYChart) else None


def _chart_key(event: Event) -> str | None:
    chart = _chart_of(event)
    if chart is None:
        return None
    return chart._key(str(event.keysym))


def _chart_click(event: Event) -> None:
    """The Canvas's routing to items first, then the chart's own."""
    chart = _chart_of(event)
    if chart is None:
        return
    tkcurses._canvas_mouse(event)
    chart.focus_set()
    column = int(chart.canvasx(event.x))
    row = int(chart.canvasy(event.y)) // 2
    chart._click(column, row)


def _chart_refocus(event: Event) -> None:
    """Draw again when the focus comes or goes: the legend's focused
    entry shows only while the chart has it."""
    chart = _chart_of(event)
    if chart is not None:
        chart._changed()
