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

"""What an XY chart draws, as canvas items. Pure.

:func:`scene` turns the series and the options into a list of
:class:`Item` values, each with a key that stays the same from one
drawing to the next while it describes the same part: the widget keeps
the canvas item it made for a key, and changes it in place rather than
making another. Items come in drawing order: every area's fill, then
every line, then the points, so no fill hides a line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tkcurses._charts.color import hex_color, mix
from tkcurses._charts.scale import ScaleType, ValueRange
from tkcurses.xychart._axes import value_range
from tkcurses.xychart._fit import fit
from tkcurses.xychart._path import (
    area,
    clip_line,
    clip_polygon,
    dashes,
    pixels,
    points_shown,
    project,
    trace,
)
from tkcurses.xychart._stack import Band, Layer, stack

if TYPE_CHECKING:
    from collections.abc import Callable

    from tkcurses._charts.color import RGB
    from tkcurses._charts.geometry import Rect
    from tkcurses.xychart._model import Model

__all__ = ["DIM", "LIGHT", "TAG", "Config", "Item", "scene"]

#: The tag every item the chart makes carries, and the start of the tag
#: naming its part.
TAG = "xychart"
#: How far an area's fill is mixed from its line's colour toward the
#: background, at 256 colours and above.
DIM = 0.6
#: How far a point is mixed from its line's colour toward white.
LIGHT = 0.5
#: The colours below which a mixed colour would round back to its own.
MIXES_FROM = 256


@dataclass(frozen=True, slots=True)
class Config:
    """The options a scene depends on, checked."""

    colors: tuple[str, ...]
    stackmode: str = "stacked"
    interpolation: str = "straight"
    points: str = "auto"
    missing: str = "hide"
    endvalues: str = "hide"
    dottedgaps: bool = False
    scaletype: ScaleType = "linear"
    logbase: float = 10.0
    bounds: str = "full"
    minimum: float | None = None
    maximum: float | None = None
    nicebounds: bool = True


@dataclass(frozen=True, slots=True)
class Item:
    """One canvas item: what kind, where, how it looks, and its tags."""

    key: str
    kind: str
    coords: tuple[int, ...]
    options: tuple[tuple[str, Any], ...] = ()
    tags: tuple[str, ...] = field(default=(TAG,))


def scene(
    model: Model,
    config: Config,
    plot: Rect,
    *,
    depth: int,
    rgb: Callable[[str], RGB | None],
    background: RGB,
) -> list[Item]:
    """Every item the chart draws in ``plot``, a rectangle of pixels.

    ``depth`` is the terminal's colours, 0 for none; ``rgb`` says what a
    colour spec is in red, green and blue, and ``background`` is the
    canvas's.
    """
    if plot.width < 1 or plot.height < 1:
        return []
    names = model.names()
    colors = {
        name: model.get(name).color or config.colors[i % len(config.colors)]
        for i, name in enumerate(names)
    }
    layers = []
    for series in model.shown():
        fitted = fit(series.xs, series.ys, config.missing, config.endvalues)
        layers.append(
            Layer(series.name, series.kind, tuple(series.xs), fitted.ys, fitted.filled)
        )
    bands = stack(layers, config.stackmode)
    has_area = any(band.kind == "area" for band in bands)
    yspan = value_range(
        _values(bands),
        bounds=config.bounds,
        minimum=config.minimum,
        maximum=config.maximum,
        nice=config.nicebounds,
        scaletype=config.scaletype,
        base=config.logbase,
        areas=has_area,
        percentage=config.stackmode == "percentage" and has_area,
    )
    xs = [x for band in bands for x in band.xs]
    if not xs:
        return []
    low, high = min(xs), max(xs)
    xspan = ValueRange(high, low) if high > low else None
    baseline = _baseline(yspan, plot)
    fills: list[Item] = []
    lines: list[Item] = []
    dots: list[Item] = []
    for band in bands:
        color = colors[band.name]
        tags = (TAG, f"{TAG}.series.{band.name}")
        highs = project(band.xs, band.highs, xspan, yspan, plot)
        if band.kind == "area":
            lows = (
                None
                if band.lows is None
                else project(band.xs, band.lows, xspan, yspan, plot)
            )
            fill = _dimmed(color, depth, rgb, background)
            for n, outline in enumerate(
                area(highs, lows, baseline, config.interpolation)
            ):
                shape = pixels(clip_polygon(outline, plot))
                if len(shape) >= 3:
                    fills.append(
                        Item(
                            f"area.{band.name}.{n}",
                            "polygon",
                            _flat(shape),
                            (("fill", fill), ("outline", "")),
                            (TAG, f"{TAG}.area.{band.name}"),
                        )
                    )
        filled = band.filled if config.dottedgaps else (False,) * len(band.filled)
        n = 0
        for piece in trace(highs, filled, config.interpolation):
            for part in clip_line(piece.points, plot):
                drawn = pixels(part)
                for run in dashes(drawn) if piece.dotted else [drawn]:
                    lines.append(_line(f"line.{band.name}.{n}", run, color, tags))
                    n += 1
        _points(band, highs, config.points, color, depth, rgb, plot, dots)
    return fills + lines + dots


def _values(bands: list[Band]) -> list[float | None]:
    values: list[float | None] = []
    for band in bands:
        values.extend(band.highs)
        if band.lows is not None:
            values.extend(band.lows)
    return values


def _baseline(yspan: ValueRange, plot: Rect) -> float:
    """The pixel row of zero, kept on the plot: an area's bottom."""
    bottom = plot.y + plot.height - 1
    position = yspan.position(0.0)
    if position is None:  # a log axis: from its bottom
        return float(bottom)
    return min(max(bottom - position * (plot.height - 1), plot.y), bottom)


def _line(
    key: str, run: list[tuple[int, int]], color: str, tags: tuple[str, ...]
) -> Item:
    if len(run) == 1:
        return _dot(key, run[0], color, tags)
    return Item(key, "line", _flat(run), (("fill", color),), tags)


def _dot(key: str, at: tuple[int, int], color: str, tags: tuple[str, ...]) -> Item:
    """One pixel: a rectangle with no outline, whose fill stops short of its
    far corner as Tk's does, so the far corner is one pixel on."""
    x, y = at
    options = (("fill", color), ("outline", ""))
    return Item(key, "rectangle", (x, y, x + 1, y + 1), options, tags)


def _points(
    band: Band,
    highs: list[tuple[float, float] | None],
    mode: str,
    color: str,
    depth: int,
    rgb: Callable[[str], RGB | None],
    plot: Rect,
    out: list[Item],
) -> None:
    """A pixel at each value the series was given, a shade lighter."""
    given = [
        point
        for point, filled in zip(highs, band.filled, strict=True)
        if point is not None and not filled
    ]
    if not points_shown(mode, [x for x, _ in given]):
        return
    light = _lightened(color, depth, rgb)
    right, bottom = plot.x + plot.width - 1, plot.y + plot.height - 1
    tags = (TAG, f"{TAG}.point.{band.name}")
    for n, (x, y) in enumerate(given):
        px, py = round(x), round(y)
        if plot.x <= px <= right and plot.y <= py <= bottom:
            out.append(_dot(f"point.{band.name}.{n}", (px, py), light, tags))


def _dimmed(
    color: str, depth: int, rgb: Callable[[str], RGB | None], background: RGB
) -> str:
    own = rgb(color)
    if depth < MIXES_FROM or own is None:
        return color
    return hex_color(mix(own, background, DIM))


def _lightened(color: str, depth: int, rgb: Callable[[str], RGB | None]) -> str:
    own = rgb(color)
    if depth < MIXES_FROM or own is None:
        return "white"
    return hex_color(mix(own, (255, 255, 255), LIGHT))


def _flat(points: list[tuple[int, int]]) -> tuple[int, ...]:
    return tuple(c for point in points for c in point)
