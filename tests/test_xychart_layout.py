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

"""XYChart's axes, gridlines, reference lines and current-time marker:
the layout, the items the scene makes for them, and the widget's
reference methods."""

from __future__ import annotations

import datetime
import itertools

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import tkcurses as tk
from tkcurses._charts.numformat import NumberFormat
from tkcurses._core.cells import cells
from tkcurses._core.colors import rgb_of
from tkcurses.xychart import XYChart
from tkcurses.xychart._layout import MIN_PLOT, layout
from tkcurses.xychart._model import Model
from tkcurses.xychart._scene import TAG, Config, Reference, chart

COLORS = ("green", "red", "blue")
START = datetime.datetime(2026, 11, 23, 23, 30)


def model_of(*series):
    model = Model()
    for name, points, kind in series:
        model.add(name, points, kind=kind)
    return model


def draw(model, width=40, height=12, *, depth=256, refs=(), now=None, **options):
    config = Config(colors=COLORS, **options)
    return chart(
        model,
        config,
        width,
        height,
        depth=depth,
        rgb=rgb_of,
        background=(0, 0, 0),
        references=refs,
        now=now,
        xkind=model.xkind or "number",
    )


def by_key(items):
    return {item.key: item for item in items}


def option(item, name):
    return dict(item.options)[name]


def text_cells(item):
    """The cells a text item covers, as ``(row, column)``, as the Canvas
    places it: the anchor's share of its width off ``x``, the row ``y``
    falls in, less whole rows for a block anchored low."""
    x, y = item.coords
    lines = option(item, "text").split("\n")
    anchor = option(item, "anchor")
    width = max(cells(line) for line in lines)
    across = 1.0 if "e" in anchor else 0.0 if "w" in anchor else 0.5
    down = 1.0 if anchor.startswith("s") else 0.0 if anchor.startswith("n") else 0.5
    column = x - int(width * across)
    row = y // 2 - int(len(lines) * down)
    return {
        (row + n, column + c)
        for n, line in enumerate(lines)
        for c in range(cells(line))
    }


LINE = ("a", [(t, 10 + t) for t in range(30)], "line")


# ------------------------------------------------------------------ layout


def test_the_parts_are_stacked_and_the_plot_gets_the_rest():
    lay = layout(
        40, 12, ylabel=True, ticklabels=True, title=True, label_width=lambda _: 3
    )
    assert lay.ylabel_row == 0
    assert (lay.plot.x, lay.plot.y, lay.plot.width, lay.plot.height) == (4, 1, 36, 8)
    assert (lay.axis_column, lay.axis_row, lay.tick_row, lay.title_row) == (
        3,
        9,
        10,
        11,
    )


def test_rows_with_nothing_in_them_are_not_kept():
    lay = layout(
        40, 12, ylabel=False, ticklabels=False, title=False, label_width=lambda _: 0
    )
    assert (lay.plot.x, lay.plot.y, lay.plot.width, lay.plot.height) == (1, 0, 39, 11)
    assert (lay.tick_row, lay.title_row, lay.ylabel_row) == (None, None, None)


def test_the_label_width_is_asked_for_the_plots_rows():
    asked = []
    layout(
        40,
        12,
        ylabel=True,
        ticklabels=True,
        title=False,
        label_width=lambda rows: asked.append(rows) or 0,
    )
    assert asked == [9]


@pytest.mark.parametrize("size", [(MIN_PLOT[0] + 2, 20), (40, MIN_PLOT[1] + 1)])
def test_too_small_for_axes_is_all_plot(size):
    lay = layout(
        *size, ylabel=False, ticklabels=True, title=False, label_width=lambda _: 2
    )
    assert not lay.axes
    assert (lay.plot.width, lay.plot.height) == size


# -------------------------------------------------------------------- axes


def test_the_axes_are_drawn_round_the_plot():
    items = by_key(draw(model_of(LINE)))
    up, across = items["axis.y"], items["axis.x"]
    assert set(option(up, "text").split("\n")) == {"│", "┤"}
    assert option(across, "text").startswith("└┬")  # x = 0 is the first column
    assert TAG + ".axis" in up.tags
    ylabels = [option(i, "text") for k, i in items.items() if k.startswith("tick.y.")]
    assert ylabels == ["0", "10", "20", "30", "40"]


def test_value_labels_are_in_the_number_format():
    items = draw(model_of(LINE), numbers=NumberFormat(units="ms", space=True))
    labels = [option(i, "text") for i in items if i.key.startswith("tick.y.")]
    assert labels[-1] == "40 ms"
    # Right-aligned against the axis line.
    axis = by_key(items)["axis.y"].coords[0]
    assert all(
        max(c for _, c in text_cells(i)) == axis - 1
        for i in items
        if i.key.startswith("tick.y.")
    )


def test_a_percentage_stack_is_labelled_in_percent():
    model = model_of(("a", [(0, 1), (9, 3)], "area"), ("b", [(0, 1), (9, 1)], "area"))
    labels = [
        option(i, "text")
        for i in draw(model, stackmode="percentage", numbers=NumberFormat(units="B"))
        if i.key.startswith("tick.y.")
    ]
    assert labels[0] == "0%" and labels[-1] == "100%"


def test_without_tick_labels_the_lines_and_ticks_stay():
    with_labels = by_key(draw(model_of(LINE)))
    without = by_key(draw(model_of(LINE), ticklabels=False))
    assert not [k for k in without if k.startswith("tick.")]
    assert "axis.y" in without and "axis.x" in without
    assert without["axis.y"].coords[0] == 0
    assert len(option(without["axis.y"], "text")) > len(
        option(with_labels["axis.y"], "text")
    )


def test_titles_go_above_and_below():
    items = by_key(draw(model_of(LINE), xlabel="minute", ylabel="load"))
    assert text_cells(items["ylabel"]) == {(0, c) for c in range(4)}
    xlabel = text_cells(items["xlabel"])
    assert {row for row, _ in xlabel} == {11}
    plot_left = items["axis.y"].coords[0] + 1
    middle = sum(c for _, c in xlabel) / len(xlabel)
    assert abs(middle - (plot_left + (40 - plot_left) / 2)) <= 1


def test_a_time_axis_says_its_day_once():
    points = [(START + datetime.timedelta(minutes=n), n) for n in range(60)]
    items = draw(model_of(("a", points, "line")), width=60, height=14)
    keyed = by_key(items)
    assert option(keyed["context"], "text") == "Nov 23, 2026"
    labels = [option(i, "text") for i in items if i.key.startswith("tick.x.")]
    assert "Nov 24" in labels  # midnight
    assert all(len(label) == 5 for label in labels if label != "Nov 24")


def test_a_title_and_the_context_share_their_row_without_meeting():
    points = [(START + datetime.timedelta(minutes=n), n) for n in range(60)]
    items = by_key(
        draw(
            model_of(("a", points, "line")),
            width=30,
            height=14,
            xlabel="when it happened",
        )
    )
    assert not text_cells(items["context"]) & text_cells(items["xlabel"])


def test_one_x_has_no_x_ticks():
    items = draw(model_of(("a", [(5, 1)], "line")))
    assert not [i for i in items if i.key.startswith("tick.x.")]
    keyed = by_key(items)
    columns = 40 - keyed["axis.y"].coords[0] - 1
    assert option(keyed["axis.x"], "text") == "└" + "─" * columns


def test_gridlines_are_under_the_series_only_when_asked():
    assert not [i for i in draw(model_of(LINE)) if i.key.startswith("grid.")]
    items = draw(model_of(LINE), gridlines=True)
    keys = [i.key for i in items]
    grids = [n for n, k in enumerate(keys) if k.startswith("grid.")]
    lines = [n for n, k in enumerate(keys) if k.startswith("line.")]
    assert grids and max(grids) < min(lines)
    assert any(k.startswith("grid.x.") for k in keys)
    assert any(k.startswith("grid.y.") for k in keys)


def test_gridlines_are_dimmed_where_colours_mix():
    def grid_fill(depth):
        return {
            option(i, "fill")
            for i in draw(model_of(LINE), depth=depth, gridlines=True)
            if i.key.startswith("grid.")
        }

    (dim,) = grid_fill(256)
    assert dim.startswith("#") and dim != "#ffffff"
    assert grid_fill(8) == {""}


# -------------------------------------------------------------- references


def test_a_reference_line_crosses_the_plot_over_the_series():
    refs = (Reference("ref1", 25, text="limit", color="red", band=(20, 30)),)
    items = draw(model_of(LINE), refs=refs)
    keys = [i.key for i in items]
    assert (
        keys.index("ref.ref1.band")
        < keys.index("line.a.0")
        < keys.index("ref.ref1.line")
    )
    line = by_key(items)["ref.ref1.line"]
    x0, y0, x1, y1 = line.coords
    assert y0 == y1 and option(line, "fill") == "red"
    plot_left = by_key(items)["axis.y"].coords[0] + 1
    assert (x0, x1) == (plot_left, 39)
    band = by_key(items)["ref.ref1.band"]
    assert band.coords[0] == plot_left and band.coords[1] < y0 < band.coords[3]
    assert option(band, "fill") not in ("red", "")  # dimmed, as a fill is
    label = by_key(items)["ref.ref1.text"]
    assert max(c for _, c in text_cells(label)) == 39
    assert {row for row, _ in text_cells(label)} == {y0 // 2}


def test_a_reference_reaches_the_axis_unless_bounds_are_custom():
    refs = (Reference("ref1", 100),)
    top = [
        option(i, "text")
        for i in draw(model_of(LINE), refs=refs)
        if i.key.startswith("tick.y.")
    ][-1]
    assert float(top) >= 100
    custom = draw(model_of(LINE), refs=refs, bounds="custom", minimum=0, maximum=50)
    assert "ref.ref1.line" not in by_key(custom)


def test_an_x_reference_runs_down_the_plot_with_its_text_at_the_top():
    items = by_key(
        draw(model_of(LINE), refs=(Reference("r", 10, text="deploy", axis="x"),))
    )
    x0, y0, x1, y1 = items["ref.r.line"].coords
    assert x0 == x1 and y0 == 0 and y1 > y0
    assert min(c for _, c in text_cells(items["ref.r.text"])) == x0 + 1
    assert {row for row, _ in text_cells(items["ref.r.text"])} == {0}


def test_an_x_reference_near_the_right_edge_writes_its_text_to_the_left():
    items = by_key(
        draw(model_of(LINE), refs=(Reference("r", 29, text="deploy", axis="x"),))
    )
    x0 = items["ref.r.line"].coords[0]
    assert max(c for _, c in text_cells(items["ref.r.text"])) == x0 - 1


def test_a_reference_off_the_axis_is_not_drawn():
    refs = (Reference("r", 100, axis="x", band=(200, 300)),)
    assert not [
        i for i in draw(model_of(LINE), refs=refs) if i.key.startswith("ref.r.")
    ]


# -------------------------------------------------------------- now marker


def test_the_current_time_is_marked_on_a_time_axis():
    points = [(START + datetime.timedelta(minutes=n), n) for n in range(60)]
    model = model_of(("a", points, "line"))
    middle = (START + datetime.timedelta(minutes=30)).timestamp()
    items = by_key(draw(model, nowmarker=True, now=middle))
    x0, _, x1, _ = items["now"].coords
    assert x0 == x1
    assert "now" not in by_key(draw(model, nowmarker=False, now=middle))
    assert "now" not in by_key(draw(model, nowmarker=True, now=middle + 86400))
    assert "now" not in by_key(draw(model_of(LINE), nowmarker=True, now=15))


# ---------------------------------------------------------------- property


@settings(max_examples=150, deadline=None)
@given(
    width=st.integers(1, 90),
    height=st.integers(1, 30),
    count=st.integers(1, 40),
    scale=st.sampled_from([1, 1e-3, 1e6, 123.456]),
    time=st.booleans(),
    ticklabels=st.booleans(),
    xlabel=st.sampled_from(["", "minute", "a very long title for the x axis"]),
    ylabel=st.sampled_from(["", "load", "a title longer than most charts are wide"]),
    units=st.sampled_from(["", "%", "B"]),
)
def test_every_label_is_on_the_canvas_and_none_meet(
    width, height, count, scale, time, ticklabels, xlabel, ylabel, units
):
    if time:
        points = [
            (START + datetime.timedelta(hours=n * 7), n * scale) for n in range(count)
        ]
    else:
        points = [(n * scale, (n % 7) * scale) for n in range(count)]
    items = draw(
        model_of(("a", points, "line")),
        width,
        height,
        ticklabels=ticklabels,
        xlabel=xlabel,
        ylabel=ylabel,
        numbers=NumberFormat(units=units),
    )
    taken: set[tuple[int, int]] = set()
    for item in items:
        if item.kind != "text":
            continue
        covered = text_cells(item)
        assert all(0 <= r < height and 0 <= c < width for r, c in covered), item
        if TAG + ".axis" in item.tags:
            assert not covered & taken, item
            taken |= covered
    ylabels = [
        min(r for r, _ in text_cells(i)) for i in items if i.key.startswith("tick.y.")
    ]
    assert all(a - b >= 2 for a, b in itertools.pairwise(ylabels))


# ------------------------------------------------------------------ widget


@pytest.fixture
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


@pytest.fixture
def chart_widget(root):
    widget = XYChart(root)
    widget.add_series("a", [(t, t) for t in range(10)])
    return widget


def test_references_are_added_listed_and_deleted(chart_widget):
    first = chart_widget.reference_add(5, text="five", color="red", band=(4, 6))
    second = chart_widget.reference_add(3, axis="x")
    assert (first, second) == ("ref1", "ref2")
    assert chart_widget.references() == ("ref1", "ref2")
    chart_widget._update()
    assert chart_widget.find_withtag(f"{TAG}.ref.ref1")
    with pytest.raises(tk.TclError, match="Reference nope not found"):
        chart_widget.reference_delete("ref1", "nope")
    assert chart_widget.references() == ("ref1", "ref2")
    chart_widget.reference_delete("ref1")
    chart_widget._update()
    assert chart_widget.references() == ("ref2",)
    assert not chart_widget.find_withtag(f"{TAG}.ref.ref1")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"value": "x"}, "value must be a number"),
        ({"value": 1, "axis": "z"}, 'bad axis "z": must be y or x'),
        ({"value": 1, "color": "nocolour"}, 'unknown color name "nocolour"'),
        ({"value": 1, "band": (1,)}, "band must be two values"),
        ({"value": 1, "band": (1, "b")}, "value must be a number"),
        ({"value": START, "axis": "x"}, "a reference there needs a number"),
    ],
)
def test_a_bad_reference_is_refused_and_adds_nothing(chart_widget, kwargs, message):
    value = kwargs.pop("value")
    with pytest.raises(tk.TclError, match=message):
        chart_widget.reference_add(value, **kwargs)
    assert chart_widget.references() == ()


def test_an_x_reference_on_a_time_chart_is_a_time(root):
    widget = XYChart(root)
    widget.add_series(
        "a", [(START + datetime.timedelta(minutes=n), n) for n in range(10)]
    )
    widget.reference_add(START + datetime.timedelta(minutes=5), axis="x")
    with pytest.raises(tk.TclError, match="needs a time"):
        widget.reference_add(5, axis="x")


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"digits": 0}, "digits must be at least 1"),
        ({"unitscale": "metric"}, 'bad unitscale "metric"'),
        ({"units": "kg", "unitscale": "time"}, "needs units naming a time unit"),
    ],
)
def test_a_bad_number_option_is_refused(root, options, message):
    with pytest.raises(tk.TclError, match=message):
        XYChart(root, **options)
    widget = XYChart(root)
    with pytest.raises(tk.TclError, match=message):
        widget.configure(**options)
    assert widget.cget("digits") == ""


def test_the_axis_options_read_back(root):
    widget = XYChart(
        root, xlabel="t", ylabel="v", ticklabels=0, gridlines=1, nowmarker=1, units="%"
    )
    assert [
        widget.cget(name)
        for name in (
            "xlabel",
            "ylabel",
            "ticklabels",
            "gridlines",
            "nowmarker",
            "units",
        )
    ] == ["t", "v", 0, 1, 1, "%"]
