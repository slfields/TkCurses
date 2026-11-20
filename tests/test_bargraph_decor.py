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

"""Ticks, peak hold, and the window put together with every decoration."""

from __future__ import annotations

import itertools

import pytest

from tkcurses.bargraph._decor import (
    Decor,
    PeakHold,
    auto_ticks,
    compose,
    even_ticks,
    level_cell,
    readout_value,
    spaced,
)
from tkcurses.bargraph._layout import LayoutSpec, compute_layout, natural_size
from tkcurses.bargraph._render import (
    BACKGROUND,
    GRID,
    TEXT,
    Cell,
    marker,
    render_bars,
    series,
)
from tkcurses.bargraph._scale import ValueRange

# ---------------------------------------------------------------- ticks ----


@pytest.mark.parametrize(
    ("maximum", "length", "spacing", "expected"),
    [
        (100, 10, 2, [0, 20, 40, 60, 80, 100]),
        (100, 20, 2, [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]),
        (1, 10, 2, [0, 0.2, 0.4, 0.6, 0.8, 1.0]),
        (7, 4, 2, [0, 5]),
        (0, 10, 2, [0]),
        (100, 0, 2, [0]),
    ],
)
def test_auto_ticks(maximum, length, spacing, expected):
    assert auto_ticks(maximum, length, spacing) == expected


def test_even_ticks():
    assert even_ticks(100, 3) == [0, 50, 100]
    assert even_ticks(100, 1) == [0]


@pytest.mark.parametrize(("value", "cell"), [(0, 0), (8, 0), (9, 1), (16, 1), (17, 2)])
def test_level_cell_is_where_the_tip_would_end(value, cell):
    assert level_cell(value, maximum=64, peak_points=64) == cell


def test_spaced_drops_ticks_that_land_too_close():
    # Cells 0, 1, 3 at 8 points per unit... 0 -> 0, 16 -> 1, 32 -> 3.
    assert spaced([0, 16, 32], maximum=32, peak_points=32, min_spacing=2) == [0, 32]


def test_readout_value():
    assert readout_value([3, -1, 4], "stacked") == 7
    assert readout_value([3, 9, 4], "overlay") == 9


def test_peak_hold_holds_then_falls_back():
    hold = PeakHold(hold_ms=1000)
    assert hold.update([5.0], now_ms=0) == [5.0]
    assert hold.update([2.0], now_ms=500) == [5.0]
    assert hold.update([7.0], now_ms=600) == [7.0]
    assert hold.update([1.0], now_ms=1500) == [7.0]
    assert hold.update([1.0], now_ms=1700) == [1.0]


def test_peak_hold_follows_a_falling_value_after_the_hold():
    # A sweep falling from 100: held for 1000 ms, then the peak goes down
    # with the bar. It used to catch the value at that moment (40 here) and
    # hold it for another 1000 ms, a second stale marker partway down.
    hold = PeakHold(hold_ms=1000)
    falling = [(0, 100.0), (500, 70.0), (1001, 40.0), (1500, 20.0), (2000, 5.0)]
    held = [hold.update([value], now_ms=when)[0] for when, value in falling]
    assert held == [100.0, 100.0, 40.0, 20.0, 5.0]


def test_peak_hold_starts_a_new_hold_on_a_rise_after_expiring():
    hold = PeakHold(hold_ms=1000)
    hold.update([100.0], now_ms=0)
    assert hold.update([10.0], now_ms=1100) == [10.0]
    assert hold.update([30.0], now_ms=1200) == [30.0]
    assert hold.update([20.0], now_ms=1900) == [30.0]
    assert hold.update([20.0], now_ms=2201) == [20.0]


# --------------------------------------------------------------- compose ----


def _text(window) -> list[str]:
    return [
        "".join("~" if cell is None else cell.char for cell in row) for row in window
    ]


def _window(spec, length, rows, maximum, decor_options, *, width=None, height=None):
    natural = natural_size(spec, length)
    width = natural[0] if width is None else width
    height = natural[1] if height is None else height
    layout = compute_layout(width, height, spec)
    peak = layout.length_cells * 8 if spec.relative else length * 8
    bars = render_bars(rows, layout, "stacked", maximum, peak)
    decor = Decor(maximum=maximum, peak_points=peak, **decor_options)
    return compose(width, height, layout, bars, rows, decor)


def test_vertical_with_axis_baseline_and_labels():
    spec = LayoutSpec(
        segments=2,
        relative=False,
        labels=("a", "b"),
        baseline=True,
        axis=True,
        axis_label_width=2,
    )
    window = _window(
        spec,
        4,
        [[20], [6]],
        32,
        {"labels": ("a", "b"), "baseline": True, "axis": True, "ticks": (0, 32)},
    )
    assert _text(window) == [
        "32┤   ",
        "~~│▄  ",
        "~~│█  ",
        "~~│█ ▆",
        "~0┴───",
        "~~~a~b",
    ]
    assert window[0][0] == Cell("3", TEXT, BACKGROUND)


def test_gridlines_sit_under_the_bars():
    spec = LayoutSpec(relative=False, segments=2)
    window = _window(
        spec, 4, [[32], [4]], 32, {"gridlines": True, "ticks": (0, 16, 32)}
    )
    # Tick 16 ends in cell 1 and tick 32 in cell 3; tick 0 has no line.
    assert _text(window) == [
        "█┈┈",
        "█  ",
        "█┈┈",
        "█ ▄",
    ]
    assert window[0][1] == Cell("┈", GRID, BACKGROUND)


def test_markers_never_cover_a_color():
    spec = LayoutSpec(relative=False, segments=3)
    window = _window(spec, 2, [[4], [16], [2, 14]], 16, {"markers": (4, 12)})
    # Marker 0 at 4 ends in cell 0, marker 1 at 12 in cell 1.
    assert _text(window) == [
        "──█─█",
        "▄─█─▂",
    ]
    m0, m1 = marker(0), marker(1)
    assert window[0][0] == Cell("─", m1, BACKGROUND)
    # Behind a partial glyph, the marker takes the graph background's place...
    assert window[1][0] == Cell("▄", series(0), m0)
    # ...but leaves a full cell alone...
    assert window[1][2] == Cell("█", series(0), BACKGROUND)
    # ...and a partial glyph whose background is another series.
    assert window[1][4] == Cell("▂", series(0), series(1))
    # In the gaps between bars, the line is drawn.
    assert window[1][1] == Cell("─", m0, BACKGROUND)


def test_markers_and_peaks_draw_over_gridlines():
    spec = LayoutSpec(relative=False, segments=2)
    window = _window(
        spec,
        2,
        [[0], [0]],
        16,
        {
            "gridlines": True,
            "ticks": (16,),
            "markers": (16,),
            "peaks": ((16, series(1)), None),
        },
    )
    # The marker covers the gridline across the row; the peak, drawn after,
    # covers the marker in its own track.
    assert window[0] == [
        Cell("─", series(1), BACKGROUND),
        Cell("─", marker(0), BACKGROUND),
        Cell("─", marker(0), BACKGROUND),
    ]


def test_peak_hold_line_in_the_track_only():
    spec = LayoutSpec(relative=False, segments=2)
    window = _window(spec, 2, [[4], [4]], 16, {"peaks": ((12, series(0)), None)})
    assert _text(window) == [
        "─  ",
        "▄ ▄",
    ]
    assert window[0][0] == Cell("─", series(0), BACKGROUND)


def test_horizontal_with_labels_axis_and_readout():
    spec = LayoutSpec(
        orient="horizontal",
        relative=False,
        labels=("cpu",),
        readout_width=3,
        axis=True,
    )
    window = _window(
        spec,
        4,
        [[10]],
        32,
        {
            "labels": ("cpu",),
            "axis": True,
            "ticks": (0, 16, 32),
            "readoutformat": "{:.0f}",
        },
    )
    # Tick 16's label would touch tick 0's, so it is skipped; tick 32's would
    # run past the edge, so it ends there instead.
    assert _text(window) == [
        "cpu~█▎  ~~10",
        "~~~~┬┬─┬~~~~",
        "~~~~0~32~~~~",
    ]


@pytest.mark.parametrize("baseline", [True, False])
def test_the_bottom_tick_is_spaced_like_the_rest(baseline):
    # Five ticks evenly across 8 rows: with a baseline the lowest goes on its
    # corner, where an empty bar ends, and every pair is two rows apart.
    # Without one there is no row below the bars, and the lowest pair is
    # one row apart - there are only 8 rows for 9 places.
    spec = LayoutSpec(
        segments=1, relative=False, baseline=baseline, axis=True, axis_label_width=4
    )
    ticks = (0, 500, 1000, 1500, 2000)
    window = _window(
        spec, 8, [[0]], 2000, {"baseline": baseline, "axis": True, "ticks": ticks}
    )
    rows = [
        next(
            r
            for r, line in enumerate(_text(window))
            if line.lstrip("~").startswith(f"{t}")
        )
        for t in reversed(ticks)
    ]
    gaps = [b - a for a, b in itertools.pairwise(rows)]
    assert gaps == ([2, 2, 2, 2] if baseline else [2, 2, 2, 1])
    if baseline:
        assert _text(window)[-1] == "~~~0┴─"


def test_the_bottom_tick_on_a_horizontal_baseline_is_on_its_corner():
    spec = LayoutSpec(orient="horizontal", relative=False, axis=True, baseline=True)
    window = _window(
        spec, 8, [[10]], 32, {"axis": True, "baseline": True, "ticks": (0, 16, 32)}
    )
    assert _text(window)[1:] == ["├───┬───┬", "0~~~16~32"]


def test_title_in_the_box_edge_with_spaces():
    spec = LayoutSpec(relative=False, borderwidth=1, title="CPU")
    window = _window(
        spec, 2, [[0]], 16, {"title": "CPU", "borderwidth": 1}, width=12, height=4
    )
    assert _text(window)[0] == "~~~ CPU ~~~~"
    # The rest of the border is left for TkCurses to draw.
    assert window[3] == [None] * 12


def test_title_without_a_box():
    spec = LayoutSpec(relative=False, title="Load", labelanchor="nw")
    window = _window(spec, 1, [[0]], 8, {"title": "Load", "labelanchor": "nw"}, width=6)
    assert _text(window)[0] == "Load~~"


def test_no_readout_without_a_format():
    spec = LayoutSpec(orient="horizontal", relative=False, readout_width=2)
    window = _window(spec, 1, [[8]], 8, {})
    assert _text(window) == ["█~~~"]


# -------------------------------------------------------------- property ----

from hypothesis import given  # noqa: E402
from hypothesis import strategies as st  # noqa: E402


@given(
    orient=st.sampled_from(["vertical", "horizontal"]),
    segments=st.integers(1, 4),
    boxed=st.booleans(),
    title=st.sampled_from(["", "Load average"]),
    labels=st.booleans(),
    baseline=st.booleans(),
    axis=st.booleans(),
    gridlines=st.booleans(),
    readout=st.booleans(),
    width=st.integers(0, 30),
    height=st.integers(0, 12),
    values=st.lists(st.floats(-5, 120, allow_nan=False), min_size=4, max_size=4),
)
def test_compose_stays_in_bounds_and_off_the_border(
    orient,
    segments,
    boxed,
    title,
    labels,
    baseline,
    axis,
    gridlines,
    readout,
    width,
    height,
    values,
):
    names = tuple(f"s{i}" for i in range(segments)) if labels else ()
    horizontal_readout = readout and orient == "horizontal"
    spec = LayoutSpec(
        orient=orient,
        segments=segments,
        borderwidth=int(boxed),
        title=title,
        labels=names,
        baseline=baseline,
        axis=axis,
        axis_label_width=3,
        readout_width=3 if horizontal_readout else 0,
    )
    layout = compute_layout(width, height, spec)
    peak = max(8, layout.length_cells * 8)
    rows = [[values[i]] for i in range(segments)]
    bars = render_bars(rows, layout, "stacked", 100, peak)
    decor = Decor(
        maximum=100,
        peak_points=peak,
        title=title,
        borderwidth=int(boxed),
        labels=names,
        baseline=baseline,
        axis=axis,
        ticks=tuple(auto_ticks(100, layout.length_cells, 2)),
        gridlines=gridlines,
        markers=(90,),
        peaks=tuple((v, series(0)) for v in values[:segments]),
        readoutformat="{:.0f}" if horizontal_readout else "",
    )
    window = compose(width, height, layout, bars, rows, decor)
    assert len(window) == height
    assert all(len(row) == width for row in window)
    if boxed:
        title_cells = set()
        if layout.title is not None:
            t = layout.title
            title_cells = {(x, t.y) for x in range(t.x, t.x + t.width)}
        for y in range(height):
            for x in range(width):
                edge = x in (0, width - 1) or y in (0, height - 1)
                if edge and (x, y) not in title_cells:
                    assert window[y][x] is None


# ------------------------------------------------------------ log ticks ----


def test_log_ticks_are_powers_of_the_base():
    span = ValueRange(1e6, minimum=1, scaletype="log")
    assert auto_ticks(span, 20, 2) == [1, 10, 100, 1e3, 1e4, 1e5, 1e6]


def test_log_ticks_add_two_and_five_when_there_is_room():
    span = ValueRange(1000, minimum=1, scaletype="log")
    assert auto_ticks(span, 30, 2) == [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]


def test_log_ticks_skip_powers_when_crowded():
    span = ValueRange(1e6, minimum=1, scaletype="log")
    assert auto_ticks(span, 6, 2) == [1, 1e3, 1e6]


def test_log_ticks_in_another_base():
    span = ValueRange(1024, minimum=1, scaletype="log", base=2)
    assert auto_ticks(span, 40, 2) == [2.0**k for k in range(11)]


def test_linear_ticks_start_at_the_minimum():
    assert auto_ticks(ValueRange(100, minimum=50), 10, 2) == [50, 60, 70, 80, 90, 100]
    assert even_ticks(ValueRange(100, minimum=50), 3) == [50, 75, 100]


def test_even_ticks_on_a_log_range_are_geometric():
    span = ValueRange(1000, minimum=1, scaletype="log")
    assert even_ticks(span, 4) == [1, 10, 100, 1000]


# ------------------------------------------------------------ time ticks ----


@pytest.mark.parametrize(
    ("maximum", "unit_seconds", "ticks"),
    [
        (100, 1, [0, 15, 30, 45, 60, 75, 90]),
        (600, 1, [0, 120, 240, 360, 480, 600]),
        (7200, 1, [0, 1800, 3600, 5400, 7200]),
        (90_000, 1, [0, 21_600, 43_200, 64_800, 86_400]),
        (2.5, 1, [0, 0.5, 1, 1.5, 2, 2.5]),
        (120_000, 1e-3, [0, 30_000, 60_000, 90_000, 120_000]),
    ],
)
def test_time_ticks_step_as_a_clock_reads(maximum, unit_seconds, ticks):
    assert auto_ticks(float(maximum), 12, 2, float(unit_seconds)) == ticks


def test_log_time_ticks_stay_on_powers():
    span = ValueRange(10_000, minimum=1, scaletype="log")
    assert auto_ticks(span, 20, 2, 1e-3) == [1, 10, 100, 1000, 10_000]


def test_binary_ticks_count_in_powers_of_1024():
    assert auto_ticks(10 * 2.0**20, 16, 2, "binary") == [
        i * 2 * 2.0**20 for i in range(6)
    ]


def test_text_gives_a_wide_character_two_cells_or_a_space():
    from tkcurses.bargraph._decor import CONTINUATION, _Painter
    from tkcurses.bargraph._layout import Rect as Area

    layout = compute_layout(5, 1, LayoutSpec())
    window = [[None] * 5]
    painter = _Painter(window, layout, Decor(maximum=10, peak_points=8))
    painter.inside = Area(0, 0, 5, 1)
    painter.text(0, 0, "é界x界")
    drawn = [cell.char if cell is not None else None for cell in window[0]]
    # The accent rides on its letter; 界 takes two cells; the last 界 has
    # one cell left and is a space rather than half a character.
    assert drawn == ["é", "界", "", "x", " "]
    assert window[0][2] is CONTINUATION
