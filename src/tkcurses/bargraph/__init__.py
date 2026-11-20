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

"""A bar graph widget: :class:`BarGraph`.

TkCurses extension: tkinter and Tk have no bar graph widget, and this module
has no counterpart in either. Import it on its own::

    from tkcurses.bargraph import BarGraph
"""

# BarGraph began as a separate package, tkcurses-bargraph, by the same
# author, and moved into TkCurses for 0.6.
#
# This is the only module of the package that touches the rest of TkCurses,
# and it uses Frame's internals on purpose: _redraw, _window, _rect,
# _bordered, _write_line, _request_size, _apply_requested_size,
# _invalidate_layout and _options, the application's screen and colors, and
# CursesDispatcher. Everything else - parsing the options, laying out,
# rendering and composing - is pure and lives in the private modules beside
# it; this one turns their colour roles into curses attributes and writes
# the cells. ARCHITECTURE.md, BarGraph.

from __future__ import annotations

import contextlib
import curses
import dataclasses
import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import tkcurses
from tkcurses import TclError
from tkcurses._core.cells import cells
from tkcurses._core.colors import ColorDepth, parse_color, rgb_of
from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses.bargraph._decor import (
    MIN_TICK_ROWS,
    Decor,
    PeakHold,
    Window,
    auto_ticks,
    compose,
    even_ticks,
    readout_value,
    spaced,
)
from tkcurses.bargraph._glyphs import FULL, mono_pattern
from tkcurses.bargraph._gradient import (
    default_start,
    hex_color,
    shade_parts,
    shade_rgb,
    shade_window,
    step_count,
)
from tkcurses.bargraph._layout import (
    LABEL_ANCHORS,
    LayoutSpec,
    compute_layout,
    length_cells_for,
    natural_size,
)
from tkcurses.bargraph._model import AutoScale, Model
from tkcurses.bargraph._numformat import (
    PLACEMENTS,
    ROUNDINGS,
    UNIT_SCALES,
    NumberFormat,
    for_readout,
    widest,
)
from tkcurses.bargraph._render import BACKGROUND, Cell, Role, render_bars, series, zone
from tkcurses.bargraph._scale import (
    Scale,
    ValueRange,
    parse_level,
    parse_scale,
    round_up,
)
from tkcurses.bargraph._thresholds import parse_thresholds

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tkcurses.bargraph._gradient import RGB
    from tkcurses.bargraph._layout import Layout
    from tkcurses.bargraph._render import Mode

#: Series colors when ``colors`` is not given, cycled by series index.
DEFAULT_COLORS = ("green", "red", "blue", "yellow", "magenta", "cyan")


@dataclass(frozen=True, slots=True)
class _Config:
    """The options, parsed and checked. Built before anything is applied, so
    a bad value leaves the widget as it was."""

    segments: int
    series: int
    mode: Mode
    orient: str
    scale: Scale
    maximum: float
    values: ValueRange
    #: ``maximum="auto"``: ``maximum`` is only where it starts.
    auto: bool
    autoscaledelay: int
    thickness: int
    gap: int
    colors: tuple[str, ...]
    refreshinterval: int
    label: str
    labelanchor: str
    labels: tuple[str, ...]
    labelwidth: int
    baseline: bool
    axis: bool
    ticks: str | int | tuple[float, ...]
    gridlines: bool
    markers: tuple[tuple[float, str], ...]
    peakholdtime: int
    readout: bool
    readoutformat: str
    numbers: NumberFormat
    axislabel: str
    thresholds: tuple[tuple[float, str], ...]
    #: Levels as given, so a ``"NN%"`` can follow an autoscaled maximum.
    raw_levels: tuple[tuple[tuple[object, str], ...], tuple[tuple[object, str], ...]]
    raw_ticks: tuple[object, ...]
    colormode: str
    #: ``(start, end)`` RGB per series, for the gradient; empty when solid.
    gradient: tuple[tuple[RGB, RGB], ...]


def _gradient(
    colors: tuple[str, ...], starts: tuple[str, ...], series_count: int
) -> tuple[tuple[RGB, RGB], ...]:
    """Each series' gradient ends: its start color, given or 25 % of its own
    brightness, and its own color - both as the terminal renders them."""
    ends: list[tuple[RGB, RGB]] = []
    for index in range(series_count):
        name = colors[index % len(colors)]
        end = rgb_of(name)
        if end is None:
            raise ValueError(f'unknown color "{name}" in colors')
        start_name = starts[index % len(starts)] if starts else ""
        if start_name:
            start = rgb_of(start_name)
            if start is None:
                raise ValueError(f'unknown color "{start_name}" in gradientstart')
        else:
            start = default_start(end)
        ends.append((start, end))
    return tuple(ends)


def _parse(options: dict[str, Any]) -> _Config:
    """Check every BarGraph option; ``ValueError`` names the first bad one."""
    segments = _count(options["segments"], "segments")
    series_count = _count(options["series"], "series")
    mode = str(options["mode"])
    if mode not in ("stacked", "overlay"):
        raise ValueError(f'bad mode "{mode}": must be stacked or overlay')
    orient = str(options["orient"])
    if orient not in ("vertical", "horizontal"):
        raise ValueError(f'bad orient "{orient}": must be vertical or horizontal')
    auto = options["maximum"] == "auto"
    scaletype = _choice(options["scaletype"], "scaletype", ("linear", "log"))
    raw_minimum = options["minimum"]
    if raw_minimum is None or raw_minimum == "":
        minimum = 1.0 if scaletype == "log" else 0.0
    else:
        minimum = _number(raw_minimum, "minimum")
    logbase = _number(options["logbase"], "logbase")
    if scaletype == "log" and not logbase > 1:
        raise ValueError(f"logbase must be above 1, not {logbase:g}")
    if scaletype == "log" and not minimum > 0:
        raise ValueError(f"a log scale needs a minimum above 0, not {minimum:g}")
    numbers = _numbers(options)
    if auto:
        # Where it starts, before any values: the first round number.
        maximum = round_up(
            minimum,
            minimum,
            scaletype,  # type: ignore[arg-type]
            logbase,
            numbers.steps,
        )
    else:
        maximum = _number(options["maximum"], "maximum")
    values = ValueRange(
        maximum=maximum,
        minimum=minimum,
        scaletype=scaletype,  # type: ignore[arg-type]
        base=logbase,
    )
    if not maximum > 0:
        raise ValueError(f"maximum must be positive, not {maximum:g}")
    series_wanted = _count(options["series"], "series")
    if values.log and mode == "stacked" and series_wanted > 1:
        # A stack's parts add up, but on a log axis equal lengths are equal
        # ratios, not equal amounts: each part's length would be wrong.
        raise ValueError(
            'a log scale cannot stack series: use mode="overlay", or one series'
        )
    labelanchor = str(options["labelanchor"])
    if labelanchor not in LABEL_ANCHORS:
        raise ValueError(f'bad labelanchor "{labelanchor}"')
    readout = _flag(options["readout"])
    if readout and orient != "horizontal":
        raise ValueError("readout needs orient=horizontal")
    raw_thresholds = tuple(_pairs(options["thresholds"], "thresholds"))
    raw_markers = tuple(_pairs(options["markers"], "markers"))
    for _, color in (*raw_thresholds, *raw_markers):
        _color(color)
    thresholds = parse_thresholds(raw_thresholds, maximum)
    ticks: str | int | tuple[float, ...]
    raw_ticks: tuple[object, ...] = ()
    if options["ticks"] == "auto":
        ticks = "auto"
    elif isinstance(options["ticks"], int | str) and str(options["ticks"]).isdigit():
        ticks = int(options["ticks"])
    else:
        raw_ticks = tuple(_items(options["ticks"]))
        ticks = tuple(sorted(parse_level(tick, maximum) for tick in raw_ticks))
    colormode = str(options["colormode"])
    if colormode not in ("solid", "gradient"):
        raise ValueError(f'bad colormode "{colormode}": must be solid or gradient')
    colors = (
        tuple(_color(color) for color in _items(options["colors"])) or DEFAULT_COLORS
    )
    starts = tuple(
        "" if start is None else str(start)
        for start in _items(options["gradientstart"])
    )
    gradient = (
        _gradient(colors, starts, series_count) if colormode == "gradient" else ()
    )
    readoutformat = str(options["readoutformat"])
    try:
        readoutformat.format(maximum)
    except (ValueError, IndexError, KeyError) as error:
        raise ValueError(f"bad readoutformat {readoutformat!r}: {error}") from None
    return _Config(
        segments=segments,
        series=series_count,
        mode=mode,  # type: ignore[arg-type]
        orient=orient,
        scale=parse_scale(options["scale"]),
        maximum=maximum,
        values=values,
        auto=auto,
        autoscaledelay=_count(options["autoscaledelay"], "autoscaledelay", minimum=0),
        thickness=_count(options["thickness"], "thickness"),
        gap=_count(options["gap"], "gap", minimum=0),
        colors=colors,
        refreshinterval=_count(
            options["refreshinterval"], "refreshinterval", minimum=0
        ),
        label=str(options["label"]),
        labelanchor=labelanchor,
        labels=tuple(
            "" if label is None else str(label) for label in _items(options["labels"])
        ),
        labelwidth=_count(options["labelwidth"], "labelwidth", minimum=0),
        baseline=_flag(options["baseline"]),
        axis=_flag(options["axis"]),
        ticks=ticks,
        gridlines=_flag(options["gridlines"]),
        markers=tuple(
            (parse_level(level, maximum), str(color)) for level, color in raw_markers
        ),
        peakholdtime=_count(options["peakholdtime"], "peakholdtime", minimum=0),
        readout=readout,
        readoutformat=readoutformat,
        numbers=numbers,
        axislabel=str(options["axislabel"]),
        thresholds=thresholds,
        raw_levels=(raw_thresholds, raw_markers),
        raw_ticks=raw_ticks,
        colormode=colormode,
        gradient=gradient,
    )


def _numbers(options: dict[str, Any]) -> NumberFormat:
    """The number format the axis and the readout write values in."""
    return NumberFormat(
        units=str(options["units"]),
        placement=_choice(options["unitplacement"], "unitplacement", PLACEMENTS),  # type: ignore[arg-type]
        space=_flag(options["unitspace"]),
        digits=_optional_count(options["digits"], "digits", minimum=1),
        decimals=_optional_count(options["decimals"], "decimals", minimum=0),
        rounding=_choice(options["rounding"], "rounding", ROUNDINGS),  # type: ignore[arg-type]
        unitscale=_choice(options["unitscale"], "unitscale", UNIT_SCALES),  # type: ignore[arg-type]
    )


def _at_maximum(config: _Config, maximum: float) -> _Config:
    """``config`` with its scale ending at ``maximum``, and each ``"NN%"``
    level a percentage of it; absolute levels stay where they are."""
    raw_thresholds, raw_markers = config.raw_levels
    thresholds: list[tuple[float, str]] = []
    for level, color in sorted(
        ((parse_level(level, maximum), str(color)) for level, color in raw_thresholds),
        key=lambda pair: pair[0],
    ):
        # "50%" and 50 can meet as the maximum moves: the first one given
        # keeps the level.
        if not thresholds or thresholds[-1][0] != level:
            thresholds.append((level, color))
    ticks = config.ticks
    if isinstance(ticks, tuple):
        ticks = tuple(sorted(parse_level(tick, maximum) for tick in config.raw_ticks))
    return dataclasses.replace(
        config,
        maximum=maximum,
        values=dataclasses.replace(config.values, maximum=maximum),
        thresholds=tuple(thresholds),
        markers=tuple(
            (parse_level(level, maximum), str(color)) for level, color in raw_markers
        ),
        ticks=ticks,
    )


def _count(value: Any, name: str, *, minimum: int = 1) -> int:
    """An integer option, given as an int or its decimal string."""
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ValueError(f"{name} must be an integer, not {value!r}")
    try:
        number = int(value)
    except ValueError:
        raise ValueError(f"{name} must be an integer, not {value!r}") from None
    if number < minimum:
        raise ValueError(f"{name} must be at least {minimum}, not {number}")
    return number


def _number(value: Any, name: str) -> float:
    """A number option, given as a number or its string."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number, not {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number, not {value!r}") from None
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number, not {value!r}")
    return number


def _optional_count(value: Any, name: str, *, minimum: int) -> int | None:
    """An integer option that may be left unset, as None or ''."""
    if value is None or value == "":
        return None
    return _count(value, name, minimum=minimum)


def _choice(value: Any, name: str, allowed: tuple[str, ...]) -> str:
    text = str(value)
    if text not in allowed:
        raise ValueError(f'bad {name} "{text}": must be {", ".join(allowed)}')
    return text


def _color(value: Any) -> str:
    """A colour, refused here rather than when a bar is first drawn in it:
    an unknown name used to raise on every repaint and leave the whole
    window blank. Known or not does not depend on the terminal's depth."""
    text = str(value)
    try:
        parse_color(text)
    except ValueError:
        raise ValueError(f'unknown color name "{text}"') from None
    return text


def _flag(value: Any) -> bool:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("1", "true", "yes", "on"):
            return True
        if lowered in ("0", "false", "no", "off", ""):
            return False
        raise ValueError(f"expected a boolean, not {value!r}")
    return bool(value)


def _items(value: Any) -> tuple[Any, ...]:
    """A list option: a sequence, or empty for None or ''."""
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return tuple(value.split())
    return tuple(value)


def _pairs(value: Any, name: str) -> tuple[tuple[Any, Any], ...]:
    pairs = []
    for item in _items(value):
        try:
            level, color = item
        except (TypeError, ValueError):
            raise ValueError(
                f"{name} entries must be (level, color) pairs: {item!r}"
            ) from None
        pairs.append((level, color))
    return tuple(pairs)


class BarGraph(tkcurses.Frame):
    """A bar graph: one or more bars, each of one or more values.

    Each bar is a *segment*, and each of its values a *series*. The series
    are stacked end to end, or overlaid from zero; each series has one color
    across the whole graph. Bars are drawn with the Unicode Block Elements
    (``▁▂▃▄▅▆▇█`` and ``▏▎▍▌▋▊▉``), so a bar's tip falls on an eighth of a
    character cell.

    A BarGraph is a :class:`tkcurses.Frame`, and is placed with ``pack``,
    ``grid`` or ``place`` like any widget. Its values are given with
    :meth:`set` and :meth:`set_all`, or polled from a ``source`` function;
    either way, the screen is repainted at most once every ``refreshinterval``.

    A bad option value raises :class:`tkcurses.TclError` and leaves the graph
    as it was, at creation and in :meth:`configure` alike.

    Options:
        segments: How many bars. Default 1.
        series: How many values each bar holds. Default 1.
        mode: ``"stacked"`` (the default): each series starts where the one
            before it ends, so the bar's length is their total.
            ``"overlay"``: each starts from zero, the shortest drawn on top.
        orient: ``"vertical"`` (the default), bars growing up; or
            ``"horizontal"``, bars growing right.
        scale: How long a full bar is. An integer is a fixed length in
            eighths of a cell, at least 8, and the graph keeps that size. A
            percentage such as ``"75%"`` (the default is ``"100%"``) is that
            share of the space the graph is given, so the bars follow the
            window, and bar thickness grows to fill it too.
        maximum: The value that fills a bar to the end of its scale.
            Default 100. Values above it are drawn full. ``"auto"``: the
            maximum follows the data. It grows at once to the round number
            at or above the largest value shown - 1, 2 or 5 times a power
            of ten; on a log scale the next power of ``logbase``; for
            times, a step a clock reads well - so no bar is ever cut off.
            It shrinks only once the values have stayed under a lower round
            number for ``autoscaledelay``. ``"NN%"`` levels follow it; levels
            given as values stay where they are.
        autoscaledelay: How long, in milliseconds, the values must stay under
            a lower round number before an autoscaled maximum shrinks to
            it. Default 5000; ``0`` shrinks at once. Measured on a
            monotonic clock, as peak hold is.
        minimum: The value a bar starts from; values at or below it are
            drawn empty. Default 0, or 1 on a log scale, which cannot start
            at 0.
        scaletype: How values are spaced along the bar. ``"linear"`` (the
            default): evenly, so twice the value is twice the length.
            ``"log"``: by their logarithm, so each power of ``logbase``
            takes the same length - for values that span several orders of
            magnitude. A log scale cannot stack several series: on it, equal
            lengths are equal ratios, not equal amounts, so a stacked part's
            length would not show its value. Use ``mode="overlay"``, or one
            series. A ``"NN%"`` level is still NN% of ``maximum``'s value,
            which on a log scale is far further along the bar than NN% of
            its length: ``"50%"`` of 1000 is 500, nine tenths of the way.
        logbase: The base of a log scale, any number above 1: each power of
            it takes the same length, and the axis ticks fall on them.
            Default 10.
        colors: One color per series, cycled. Any color TkCurses accepts:
            a name, or ``"#rrggbb"``. Default green, red, blue, yellow,
            magenta, cyan. With ``thresholds``, a single-value graph is drawn
            in the first.
        thickness: Cells across each bar. Default 1; with a percentage
            scale, the least it can be.
        gap: Cells between bars, 0 or more. Default 1. With ``0`` the bars
            touch and keep their own colors, so neighbours of one color
            run together as one shape, as in a histogram; nothing is shaded
            to tell them apart.
        refreshinterval: The shortest time between repaints, in milliseconds.
            Default 100. Values can change faster; the screen follows at
            this rate. ``0`` repaints at the next idle moment.
        source: A function of no arguments returning every segment's
            values - what :meth:`set_all` takes. Called every
            ``refreshinterval``, and its result drawn. Default ``None``.
        label: The graph's label. In the top edge of the box when there is
            one, otherwise on a row of its own. Default none.
        labelanchor: Where the label goes: ``"n"`` (the default), ``"nw"``,
            ``"ne"``, ``"s"``, ``"sw"`` or ``"se"``.
        labels: A label for each bar: under vertical bars, to the left of
            horizontal ones. Default none.
        labelwidth: The most cells a horizontal graph's bar labels may take;
            longer ones are cut short. Default 12.
        borderwidth: ``1`` draws a box around the graph, with the label in
            its top edge. Default 0.
        relief: The box's style, as for any Frame. Default ``"solid"``.
        foreground: The color of the axis, baseline, labels and readout.
            Default white.
        background: The color of the graph's empty cells, as for any Frame.
            Default black.
        baseline: Draw a line along the bars' zero edge. Default False.
        axis: Draw a value axis with tick labels. Default False.
        ticks: Where the axis ticks and gridlines go. ``"auto"`` (the
            default) picks round steps of 1, 2 or 5 that fit; an integer
            spreads that many evenly from 0 to ``maximum``; a list gives the
            values themselves, each a number or a ``"NN%"`` of ``maximum``.
        gridlines: Draw a dim line across the graph at each tick, under the
            bars. Default False.
        markers: ``(level, color)`` pairs: a line across the graph at each
            level, a value or a ``"NN%"``, drawn over gridlines and empty
            cells but never over a bar. Default none.
        peakholdtime: Mark each bar's highest value for this many
            milliseconds; then the mark falls back with the bar. ``0`` (the
            default) turns it off.
        thresholds: ``(level, color)`` pairs. The part of a bar above each
            level takes that level's color, whichever series is there; the
            rest of the bar keeps its colors. Levels apply to the bar's tip:
            the total when stacked, the longest value when overlaid. Default
            none.
        readout: Show each bar's value at its right, in a column of its own:
            the total when stacked, the largest when overlaid. Horizontal
            graphs only. Written in the number format below, as whole
            numbers unless ``digits`` or ``decimals`` is set. Default False.
        readoutformat: A :meth:`str.format` pattern for the readout, such as
            ``"{:.1f}%"``, used instead of the number format. Default none.
        units: Written with every axis label and readout value: ``"%"``,
            ``"ms"``, ``"B"``, ``"$"``. Default none.
        unitplacement: ``"suffix"`` (the default), after the number; or
            ``"prefix"``, before it, for a currency: ``$1.23k``.
        unitspace: A space between the number and what follows it:
            ``1.23 kB`` rather than ``1.23kB``. A prefix is always written
            against the number. Default False.
        digits: Significant digits, 1 to 15. A value whose whole part needs
            more is scaled, and the scale's letter written before the units:
            with 3, 1234 is ``1.23k``. Default none: up to six, as Python's
            ``{:g}`` writes them.
        decimals: A fixed count of decimals, 0 to 15: with 1, 5 is ``5.0``
            and 12.34 is ``12.3``. ``digits`` still caps the precision.
            Default none: as many as the digits need, trailing zeros dropped.
        rounding: ``"nearest"`` (the default), ``"down"`` or ``"up"``.
            Whichever, a value at or below ``maximum`` is never written as
            more than it.
        unitscale: How a value is scaled to the fewest digits. ``"si"``
            (the default): by thousands, k, M, G, T, P, E, when its whole
            part outgrows its digits; and, for a suffix unit other than
            ``"%"``, by m, µ, n, p when it is below 1, so 0.012 s is
            ``12ms``. A bare number or a currency is never scaled down.
            ``"binary"``: by 1024s, Ki, Mi, Gi..., for bytes. ``"time"``:
            ``units`` names the unit the data is in - ``"ns"``, ``"µs"``
            (or ``"us"``), ``"ms"``, ``"s"``, ``"min"``, ``"h"`` or
            ``"d"`` - and each value is written in the largest of them it
            reaches one of, as a decimal: with ``units="ms"``, 1000 is
            ``1 s`` and 90 000 is ``1.5 min``; automatic ticks then fall on
            steps a clock reads well, 15 s, 30 s, 1 min, 5 min, 1 h.
            ``"none"``: never.
        axislabel: A name for the value axis, drawn in the box's edge at
            the axis's end: the top of a vertical graph, the bottom of a
            horizontal one. It is a name only: each tick label keeps its own
            magnifier and units, ``4 GiB``, since one axis can need several
            magnifiers. Drawn only with ``axis`` and a box
            (``borderwidth=1``), and only where it fits: if ``label`` is in
            its place it moves to the other end of the edge, and if neither
            end has room, it is left out. Default none.
        colormode: ``"solid"`` (the default), or ``"gradient"``: each series
            is shaded by position along the scale, from its start color at
            zero to its own color at the maximum, in at most 16 shades.
            Smooth on a truecolor terminal, in bands at 256 colors, and solid
            below that. Thresholds still color what is above their levels.
        gradientstart: The gradient's start color for each series, cycled.
            An empty entry, or none at all, starts at a quarter of the series
            color's brightness.

    Sample output:
        graph = BarGraph(root, segments=3, series=2, colors=["green", "red"],
                         labels=["a", "b", "c"], label="Load", borderwidth=1)
        graph.pack(fill="both", expand=True)
        graph.set_all([[40, 25], [10, 5], [70, 20]])

    Sample output (mode, series):
        # size: 40x8
        values = [[30, 40, 20], [50, 20, 60]]
        for mode in ("stacked", "overlay"):
            graph = BarGraph(root, segments=2, series=3, mode=mode,
                             label=mode, borderwidth=1, thickness=3)
            graph.pack(side="left", fill="both", expand=True)
            graph.set_all(values)

    Sample output (orient, labels):
        graph = BarGraph(root, orient="horizontal", segments=3,
                         labels=["cpu", "memory", "disk"])
        graph.pack(fill="x")
        graph.set_all([[35], [80], [55]])

    Sample output (scale, maximum):
        # Fixed: 24 eighths, 3 cells, whatever the window.
        graph = BarGraph(root, segments=4, scale=24, maximum=10)
        graph.pack(side="left")
        graph.set_all([[2], [5], [8], [10]])

    Sample output (scaletype, logbase):
        # size: 40x12
        graph = BarGraph(root, segments=5, scaletype="log", maximum=1e6,
                         labels=["1", "40", "2k", "90k", "1M"], axis=True,
                         markers=[("50%", "red"), (1000, "yellow")],
                         digits=3, thickness=3)
        graph.pack(fill="both", expand=True)
        graph.set_all([[1], [40], [2000], [90000], [1e6]])

    Sample output (minimum):
        # size: 40x12
        graph = BarGraph(root, segments=4, minimum=50, maximum=100,
                         axis=True, units="%", thickness=3)
        graph.pack(fill="both", expand=True)
        graph.set_all([[40], [62], [85], [97]])

    Sample output (colors):
        graph = BarGraph(root, segments=4, series=3,
                         colors=["#4080ff", "#ff8000", "magenta"])
        graph.pack(fill="both", expand=True)
        graph.set_all([[30, 20, 10], [20, 30, 25], [50, 10, 5], [10, 10, 60]])

    Sample output (thickness, gap):
        graph = BarGraph(root, segments=3, scale=48, thickness=4, gap=2)
        graph.pack(side="left")
        graph.set_all([[40], [70], [100]])

    Sample output (label, labelanchor, borderwidth):
        graph = BarGraph(root, segments=3, scale=32, label="Queue depth",
                         labelanchor="sw", borderwidth=1, thickness=3)
        graph.pack(side="left")
        graph.set_all([[30], [60], [90]])

    Sample output (labelwidth):
        graph = BarGraph(root, orient="horizontal", segments=2,
                         labels=["a very long label", "short"], labelwidth=6)
        graph.pack(fill="x")
        graph.set_all([[60], [30]])

    Sample output (axis, ticks, foreground):
        # size: 40x12
        graph = BarGraph(root, segments=4, axis=True, ticks=[0, 25, 50, 75, 100],
                         foreground="cyan", thickness=3)
        graph.pack(fill="both", expand=True)
        graph.set_all([[20], [45], [70], [95]])

    Sample output (baseline, gridlines):
        # size: 40x12
        graph = BarGraph(root, segments=4, baseline=True, gridlines=True,
                         axis=True, thickness=3)
        graph.pack(fill="both", expand=True)
        graph.set_all([[20], [45], [70], [95]])

    Sample output (markers):
        # size: 40x12
        graph = BarGraph(root, segments=4, markers=[("90%", "red"), (50, "yellow")],
                         thickness=3)
        graph.pack(fill="both", expand=True)
        graph.set_all([[20], [45], [70], [95]])

    Sample output (peakholdtime):
        # The values fell a moment ago; each bar's peak is still marked.
        graph = BarGraph(root, segments=3, peakholdtime=60000, thickness=3,
                         refreshinterval=10)
        graph.pack(fill="both", expand=True)
        graph.set_all([[90], [70], [100]])
        root.after(200, lambda: graph.set_all([[30], [50], [20]]))

    Sample output (thresholds):
        graph = BarGraph(root, orient="horizontal", segments=3, colors=["white"],
                         thresholds=[("80%", "yellow"), ("90%", "red")],
                         labels=["/", "/home", "/var"])
        graph.pack(fill="x")
        graph.set_all([[60], [85], [97]])

    Sample output (units, unitspace, digits, unitscale):
        graph = BarGraph(root, orient="horizontal", segments=3,
                         maximum=8 * 2**30, labels=["ram", "swap", "disk"],
                         readout=True, units="B", unitspace=True, digits=3,
                         unitscale="binary")
        graph.pack(fill="x")
        graph.set_all([[5.5 * 2**30], [700 * 2**20], [7.9 * 2**30]])

    Sample output (unitplacement, decimals, rounding):
        # size: 40x12
        graph = BarGraph(root, segments=4, maximum=2500, axis=True,
                         ticks=[0, 625, 1250, 1875, 2500], units="$",
                         unitplacement="prefix", digits=3, decimals=2,
                         rounding="down", thickness=3)
        graph.pack(fill="both", expand=True)
        graph.set_all([[900], [1600], [2100], [2450]])

    Sample output (axislabel):
        # size: 40x12
        graph = BarGraph(root, segments=3, maximum=16 * 2**30, axis=True,
                         axislabel="Memory", borderwidth=1, units="B",
                         unitspace=True, digits=3, unitscale="binary",
                         thickness=4, ticks=[0, 4 * 2**30, 8 * 2**30,
                                             12 * 2**30, 16 * 2**30])
        graph.pack(fill="both", expand=True)
        graph.set_all([[11 * 2**30], [3.5 * 2**30], [14.5 * 2**30]])

    Sample output (readout, readoutformat):
        graph = BarGraph(root, orient="horizontal", segments=2,
                         labels=["rx", "tx"], readout=True,
                         readoutformat="{:.1f}%")
        graph.pack(fill="x")
        graph.set_all([[42.5], [7.25]])

    Sample output (colormode, gradientstart):
        # size: 40x12
        graph = BarGraph(root, segments=3, series=1, colors=["red"],
                         colormode="gradient", thickness=3)
        graph.pack(side="left", fill="both", expand=True)
        graph.set_all([[100], [60], [30]])
        cool = BarGraph(root, segments=2, colors=["#00e0ff"],
                        colormode="gradient", gradientstart=["#ffffff"],
                        thickness=3)
        cool.pack(side="left", fill="both", expand=True)
        cool.set_all([[100], [50]])
    """

    _widget_options: ClassVar[dict[str, Any]] = {
        "relief": "solid",  # so borderwidth=1 alone draws the box
        "foreground": "",
        "segments": 1,
        "series": 1,
        "mode": "stacked",
        "orient": "vertical",
        "scale": "100%",
        "maximum": 100.0,
        "autoscaledelay": 5000,
        "minimum": "",
        "scaletype": "linear",
        "logbase": 10.0,
        "thickness": 1,
        "gap": 1,
        "colors": (),
        "refreshinterval": 100,
        "source": None,
        "label": "",
        "labelanchor": "n",
        "labels": (),
        "labelwidth": 12,
        "baseline": False,
        "axis": False,
        "ticks": "auto",
        "gridlines": False,
        "markers": (),
        "peakholdtime": 0,
        "readout": False,
        "readoutformat": "",
        "units": "",
        "unitplacement": "suffix",
        "unitspace": False,
        "digits": "",
        "decimals": "",
        "rounding": "nearest",
        "unitscale": "si",
        "axislabel": "",
        "thresholds": (),
        "colormode": "solid",
        "gradientstart": (),
    }

    #: Frame hides ``foreground``, which Tk's frame has no use for; a
    #: BarGraph draws its axis, baseline and labels in it, so offers it.
    _not_tk_options: ClassVar[frozenset[str]] = frozenset()

    #: The options this class adds and :func:`_parse` checks.
    _own_options = frozenset(_widget_options) - {"relief", "foreground", "source"}

    def __init__(
        self,
        master: Any = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        self._timer: str | None = None
        self._config: _Config | None = None
        #: The config drawn: ``_config`` at the autoscaled maximum, if any.
        self._shown: _Config | None = None
        self._autoscale: AutoScale | None = None
        self._peak: PeakHold | None = None
        self._held: list[float] = []
        #: Shades per series in the last frame drawn with a gradient.
        self._steps = 1
        options = {**self._widget_options, **(cnf or {}), **kw}
        try:
            config = _parse({key: options[key] for key in self._own_options})
            self._model = Model(config.segments, config.series)
        except ValueError as error:
            raise TclError(str(error)) from None
        super().__init__(master, cnf, name=name, **kw)
        self._apply(config)

    # ------------------------------------------------------------- options

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, or with none, describe them all.

        Every option is checked before any is applied, so one bad value
        changes nothing. Changing ``segments`` or ``series`` reshapes the
        graph's values: what fits is kept, and the rest is zero.

        Args:
            cnf: Options as a dictionary.
            **kw: Options as keyword arguments.

        Returns:
            With no options given, a description of every option, as any
            widget's ``configure`` returns; otherwise None.

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
            self._model.resize(config.segments, config.series)
            self._apply(config)
        else:
            # A Frame option such as borderwidth changes the natural size.
            self._apply_requested_size()
        return result

    config = configure

    def _apply(self, config: _Config) -> None:
        """Make ``config`` current: peak hold, autoscale, requested size, a
        repaint."""
        self._config = config
        self._shown = config
        if config.auto:
            wanted = AutoScale(
                config.autoscaledelay,
                config.values.minimum,
                config.values.scaletype,
                config.values.base,
                config.numbers.steps,
            )
            same = self._autoscale is not None and (
                dataclasses.replace(self._autoscale, current=None, hold_ms=0)
                == dataclasses.replace(wanted, hold_ms=0)
            )
            if same and self._autoscale is not None:
                self._autoscale.hold_ms = config.autoscaledelay
            else:
                self._autoscale = wanted
            if self._autoscale.current is not None:
                self._shown = _at_maximum(config, self._autoscale.current)
        else:
            self._autoscale = None
        if config.peakholdtime:
            if self._peak is None or self._peak.hold_ms != config.peakholdtime:
                self._peak = PeakHold(config.peakholdtime)
        else:
            self._peak = None
            self._held = []
        self._model.dirty = True
        self._apply_requested_size()
        self._invalidate_layout()
        self._schedule()

    def _apply_requested_size(self) -> None:
        """Ask for the graph's natural size, unless width or height is set.

        An absolute scale asks for exactly what its bars need. A ``%`` scale
        asks for one cell of length, its minimum; the geometry manager is
        expected to give it more (``fill``/``expand``).
        """
        config = self._shown
        if (
            config is None
            or int(self._options["width"])
            or int(self._options["height"])
        ):
            super()._apply_requested_size()
            return
        edge = 1 if self._bordered else 0
        spec = self._spec(config, edge, self._axis_width_estimate(config))
        if config.scale.points is not None:
            length = length_cells_for(config.scale.points)
        else:
            length = 1
        self._request_size(*natural_size(spec, length))

    # ---------------------------------------------------------------- data

    def set(self, segment: int, values: Sequence[float]) -> None:
        """Replace one bar's values.

        The graph is repainted on the refresh timer, not at once, so
        calling this faster than ``refreshinterval`` costs nothing extra.

        Args:
            segment: Which bar, from 0.
            values: One number per series.

        Raises:
            tkcurses.TclError: ``segment`` is out of range, there is not one
                value per series, or a value is not a finite number.
        """
        try:
            self._model.set(segment, values)
        except ValueError as error:
            raise TclError(str(error)) from None
        self._schedule()

    def set_all(self, rows: Sequence[Sequence[float]]) -> None:
        """Replace every bar's values at once.

        Args:
            rows: One sequence of values per bar, each with one number per
                series - ``[[user, system], [user, system], ...]``.

        Raises:
            tkcurses.TclError: There is not one row per bar, or a row is
                wrong as for :meth:`set`.
        """
        try:
            self._model.set_all(rows)
        except ValueError as error:
            raise TclError(str(error)) from None
        self._schedule()

    def get(self, segment: int) -> tuple[float, ...]:
        """One bar's current values.

        Args:
            segment: Which bar, from 0.

        Returns:
            The values, one per series, as last set.

        Raises:
            tkcurses.TclError: ``segment`` is out of range.
        """
        try:
            return self._model.get(segment)
        except ValueError as error:
            raise TclError(str(error)) from None

    # ------------------------------------------------------------- refresh

    def _schedule(self) -> None:
        """Arm the refresh timer if it isn't already."""
        if self._timer is None and self._config is not None:
            self._timer = self.after(self._config.refreshinterval, self._tick)

    def _tick(self) -> None:
        """Pull from ``source``, repaint, and re-arm if there's more to do."""
        self._timer = None
        source = self._options["source"]
        if source is not None:
            self.set_all(source())
        shrinking = self._autoscale is not None and self._autoscale.shrinking
        if self._model.dirty or self._peaks_falling() or shrinking:
            self.refresh()
        shrinking = self._autoscale is not None and self._autoscale.shrinking
        if source is not None or self._peaks_falling() or shrinking:
            self._schedule()

    def _peaks_falling(self) -> bool:
        """True while a held peak is above its segment's current value."""
        if self._peak is None:
            return False
        current = self._values_for_peaks()
        return any(held > now for held, now in zip(self._held, current, strict=False))

    def _values_for_peaks(self) -> list[float]:
        assert self._config is not None
        return [readout_value(row, self._config.mode) for row in self._model.rows()]

    def refresh(self) -> None:
        """Repaint now, without waiting for the refresh timer."""
        self._model.dirty = False
        now = time.monotonic() * 1000
        if self._peak is not None:
            self._held = self._peak.update(self._values_for_peaks(), now)
        if self._autoscale is not None and self._config is not None:
            # Held peaks count, so the scale never cuts one off.
            largest = max([*self._values_for_peaks(), *self._held], default=0.0)
            before = self._autoscale.current
            maximum = self._autoscale.update(largest, now)
            if maximum != before:
                self._shown = _at_maximum(self._config, maximum)
                # The axis labels' width, and with it the layout, may change.
                self._apply_requested_size()
                self._invalidate_layout()
        self._redraw()

    def destroy(self) -> None:
        """Stop the refresh timer, then destroy the widget as any widget is."""
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None
        super().destroy()

    # -------------------------------------------------------------- layout

    def _spec(self, config: _Config, edge: int, axis_label_width: int) -> LayoutSpec:
        horizontal = config.orient == "horizontal"
        readout_width = 0
        if config.readout and config.readoutformat:
            readout_width = cells(config.readoutformat.format(config.maximum))
        elif config.readout:
            readout_width = widest(for_readout(config.numbers), config.maximum)
        return LayoutSpec(
            orient="horizontal" if horizontal else "vertical",
            segments=config.segments,
            thickness=config.thickness,
            gap=config.gap,
            relative=config.scale.relative,
            borderwidth=edge,
            title=config.label,
            labelanchor=config.labelanchor,
            labels=config.labels,
            labelwidth=config.labelwidth,
            axis=config.axis,
            axis_label_width=axis_label_width,
            readout_width=readout_width,
            baseline=config.baseline,
            axis_title=config.axislabel,
        )

    @staticmethod
    def _axis_width_estimate(config: _Config) -> int:
        return cells(config.numbers.format(config.maximum, config.maximum))

    @staticmethod
    def _ticks(config: _Config, layout: Layout, peak_points: int) -> tuple[float, ...]:
        if not (config.axis or config.gridlines):
            return ()
        if config.orient == "vertical":
            spacing = MIN_TICK_ROWS
        else:
            spacing = cells(config.numbers.format(config.maximum, config.maximum)) + 1
        if config.ticks == "auto":
            chosen = auto_ticks(
                config.values,
                layout.length_cells,
                spacing,
                config.numbers.steps,
            )
            return tuple(spaced(chosen, config.values, peak_points, spacing))
        if isinstance(config.ticks, int):
            return tuple(even_ticks(config.values, config.ticks))
        assert isinstance(config.ticks, tuple)
        # Ticks off the scale have nowhere to go.
        low, high = config.values.minimum, config.values.maximum
        return tuple(tick for tick in config.ticks if low <= tick <= high)

    def _compose(self, width: int, height: int) -> Window:
        """The graph as a ``width`` x ``height`` grid of cells.

        Separate from painting so it can be checked without a terminal.
        """
        config = self._shown
        assert config is not None
        edge = 1 if self._bordered and width >= 2 and height >= 2 else 0
        estimate = self._axis_width_estimate(config)
        layout = compute_layout(width, height, self._spec(config, edge, estimate))
        peak_points = config.scale.peak_points(layout.length_cells)
        ticks = self._ticks(config, layout, peak_points)
        if config.axis and config.orient == "vertical" and ticks:
            # The tick labels decide the axis width, which decides the room
            # left for the bars; measured once more if the estimate was off.
            labels = max(
                cells(config.numbers.format(tick, config.maximum)) for tick in ticks
            )
            if labels != estimate:
                layout = compute_layout(width, height, self._spec(config, edge, labels))
                peak_points = config.scale.peak_points(layout.length_cells)
                ticks = self._ticks(config, layout, peak_points)
        rows = self._model.rows()
        levels = tuple(level for level, _ in config.thresholds)
        bars = render_bars(
            rows, layout, config.mode, config.values, peak_points, levels=levels
        )
        peaks: tuple[tuple[float, Role] | None, ...] = ()
        if self._peak is not None and self._held:
            # Only a peak above its bar is drawn: one level with it adds
            # nothing, and on an empty bar it would show as a stray tick.
            peaks = tuple(
                (held, self._peak_role(config, row, held))
                if held > readout_value(row, config.mode)
                else None
                for held, row in zip(self._held, rows, strict=False)
            )
        decor = Decor(
            maximum=config.maximum,
            values=config.values,
            peak_points=peak_points,
            mode=config.mode,
            title=config.label,
            labelanchor=config.labelanchor,
            borderwidth=edge,
            labels=config.labels,
            baseline=config.baseline,
            ticks=ticks,
            axis=config.axis,
            gridlines=config.gridlines,
            markers=tuple(level for level, _ in config.markers),
            peaks=peaks,
            readout=config.readout,
            readoutformat=config.readoutformat if config.readout else "",
            numbers=config.numbers,
            axis_title=config.axislabel if layout.axis_title is not None else "",
        )
        window = compose(width, height, layout, bars, rows, decor)
        if self._gradient_active():
            self._steps = step_count(layout.length_cells)
            window = shade_window(window, layout)
        return window

    def _gradient_active(self) -> bool:
        """A gradient is drawn only where there are shades to draw it in:
        256 colors or more. Below that the graph is solid."""
        config = self._config
        if config is None or config.colormode != "gradient":
            return False
        colors = self.tk.colors
        return (
            colors is not None
            and colors.has_colors
            and colors.depth >= ColorDepth.EXTENDED
        )

    @staticmethod
    def _peak_role(config: _Config, row: Sequence[float], held: float) -> Role:
        """The color a held peak is drawn in: the zone it reached, or the
        series on top of the bar (stacked) or the longest (overlay)."""
        if config.thresholds:
            return zone(sum(1 for level, _ in config.thresholds if held > level))
        if config.mode == "overlay":
            return series(max(range(len(row)), key=lambda i: (row[i], -i)))
        positive = [i for i, value in enumerate(row) if value > 0]
        return series(positive[-1] if positive else len(row) - 1)

    # ------------------------------------------------------------ painting

    def _color_of(self, role: Role) -> str:
        """The color spec for a role (background is handled by the caller)."""
        config = self._shown
        assert config is not None
        kind, index = role
        if kind == "series":
            return config.colors[index % len(config.colors)]
        if kind == "shade":
            which, step = shade_parts(index)
            start, end = config.gradient[which % len(config.gradient)]
            return hex_color(shade_rgb(start, end, step, self._steps))
        if kind == "zone":
            return config.colors[0] if index == 0 else config.thresholds[index - 1][1]
        if kind == "marker":
            return config.markers[index][1]
        return str(self._options["foreground"] or "white")

    def _monochrome(self) -> bool:
        colors = self.tk.colors
        return colors is None or not colors.has_colors

    def _attribute(self, cell: Cell) -> int:
        dim = curses.A_DIM if cell.fg[0] == "grid" else curses.A_NORMAL
        colors = self.tk.colors
        if colors is None or not colors.has_colors:
            return dim
        background = str(self._options["background"] or "black")
        fg = background if cell.fg == BACKGROUND else self._color_of(cell.fg)
        bg = background if cell.bg == BACKGROUND else self._color_of(cell.bg)
        return int(colors.attribute_for(fg, bg, dim))

    @staticmethod
    def _glyph(cell: Cell, monochrome: bool) -> str:
        """The character drawn: on a monochrome terminal a full cell takes
        its series' or zone's fill pattern, so they can be told apart."""
        if monochrome and cell.char == FULL and cell.fg[0] in ("series", "zone"):
            return mono_pattern(cell.fg[1])
        if monochrome and cell.char == FULL and cell.fg[0] == "shade":
            return mono_pattern(shade_parts(cell.fg[1])[0])
        return cell.char

    def _redraw(self) -> None:
        """Paint the frame and its box, then the graph inside it."""
        super()._redraw()
        window = self._window
        if window is None or self.tk.screen is None or self._config is None:
            return
        width, height = self._rect.width, self._rect.height
        if width <= 0 or height <= 0:
            return
        grid = self._compose(width, height)
        monochrome = self._monochrome()
        dispatcher = CursesDispatcher.get()
        with contextlib.suppress(curses.error):
            for y, row in enumerate(grid):
                for start, text, attribute in self._runs(row, monochrome):
                    self._write_line(dispatcher, window, y, start, text, attribute)

    def _runs(
        self, row: list[Cell | None], monochrome: bool
    ) -> list[tuple[int, str, int]]:
        """A row as ``(column, text, attribute)`` runs: one write per run of
        cells sharing an attribute, skipping cells left to the frame."""
        runs: list[tuple[int, str, int]] = []
        for x, cell in enumerate(row):
            # A wide character's second cell is drawn by the character.
            if cell is None or cell.char == "":
                continue
            attribute = self._attribute(cell)
            glyph = self._glyph(cell, monochrome)
            last = runs[-1] if runs else None
            if (
                last is not None
                and last[2] == attribute
                and last[0] + cells(last[1]) == x
            ):
                runs[-1] = (last[0], last[1] + glyph, attribute)
            else:
                runs.append((x, glyph, attribute))
        return runs
