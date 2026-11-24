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

"""What holds for every XY chart, whatever its series, options and
history; and the size it asks for.

The parts have their own properties beside them: filling
(``test_xychart_fit.py``), stacking (``test_xychart_stack.py``), joining
and clipping (``test_xychart_path.py``), the value axis
(``test_xychart_axes.py``), labels, legend and readout
(``test_xychart_layout.py``) and statistics (``test_xychart_stats.py``).
These are the whole chart's: everything drawn at once, and the widget
after any sequence of changes, keys and clicks.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import tkcurses as tk
from tkcurses._charts.numformat import NumberFormat
from tkcurses._core.colors import rgb_of
from tkcurses.xychart import CURSOR_EVENT, LEGEND_EVENT, NATURAL_SIZE, XYChart
from tkcurses.xychart._model import Model
from tkcurses.xychart._scene import TAG, Config, Reference, chart

COLORS = ("green", "red", "blue")

#: The root and the screen are the same for every example: each example
#: makes and destroys its own charts on them.
SHARED = [HealthCheck.function_scoped_fixture]

# -------------------------------------------------------------- strategies

values = st.one_of(st.none(), st.floats(-1e4, 1e4, allow_nan=False, width=32))
series = st.lists(
    st.tuples(
        st.sampled_from(["line", "area"]),
        st.lists(values, min_size=1, max_size=30),
        st.booleans(),  # hidden
    ),
    min_size=1,
    max_size=4,
)
configs = st.fixed_dictionaries(
    {
        "stackmode": st.sampled_from(["stacked", "percentage", "unstacked"]),
        "interpolation": st.sampled_from(["straight", "smooth", "step"]),
        "points": st.sampled_from(["auto", "show", "hide"]),
        "missing": st.sampled_from(["hide", "zero", "linear", "last", "next"]),
        "endvalues": st.sampled_from(["hide", "zero", "nearest"]),
        "dottedgaps": st.booleans(),
        "scaletype": st.sampled_from(["linear", "log", "sqrt"]),
        "bounds": st.sampled_from(["full", "data", "custom"]),
        "gridlines": st.booleans(),
        "ticklabels": st.booleans(),
        "legend": st.sampled_from(["auto", "show", "hide"]),
        "legendposition": st.sampled_from(["right", "left", "top", "bottom"]),
        "readout": st.booleans(),
        "xlabel": st.sampled_from(["", "x"]),
        "ylabel": st.sampled_from(["", "y"]),
    }
)
references = st.lists(
    st.tuples(
        st.floats(-2e4, 2e4, allow_nan=False),
        st.sampled_from(["y", "x"]),
        st.booleans(),  # a band
    ),
    max_size=3,
)


def build(given_series):
    model = Model()
    for n, (kind, ys, hidden) in enumerate(given_series):
        model.add(f"s{n}", list(enumerate(ys)), kind=kind)
        model.configure(f"s{n}", hidden=hidden)
    return model


def draw(model, options, width, height, refs=(), cursor=None):
    if options["bounds"] == "custom":
        options = {**options, "minimum": 1.0, "maximum": 50.0}
    config = Config(colors=COLORS, numbers=NumberFormat(), **options)
    made = [
        Reference(
            f"r{n}", value, "ref", "", (value - 3, value + 3) if band else None, axis
        )
        for n, (value, axis, band) in enumerate(refs)
    ]
    return chart(
        model,
        config,
        width,
        height,
        depth=256,
        rgb=rgb_of,
        background=(0, 0, 0),
        references=made,
        now=None,
        cursor=cursor,
    )


# ----------------------------------------------------------- the scene


@settings(max_examples=200, deadline=None)
@given(
    series,
    configs,
    references,
    st.integers(1, 90),
    st.integers(1, 30),
    st.integers(0, 29),
)
def test_everything_drawn_on_the_plot_stays_on_it(
    given_series, options, refs, width, height, at
):
    """Fills, lines, points, bands, reference lines and the crosshair, all
    at once: whatever is not text lies on the plot, a rectangle's far
    edge at most one past it, as a canvas rectangle's fill stops short."""
    model = build(given_series)
    drawing = draw(model, options, width, height, refs, cursor=float(at))
    if drawing.plot is None:
        assert all(item.kind == "text" for item in drawing.items)
        return
    plot = drawing.plot
    left, right = plot.x, plot.x + plot.width - 1
    top, bottom = plot.y * 2, (plot.y + plot.height) * 2 - 1
    for item in drawing.items:
        if item.kind == "text":
            continue
        xs, ys = item.coords[0::2], item.coords[1::2]
        if item.kind == "rectangle":
            assert left <= xs[0] < xs[1] <= right + 1, item
            assert top <= ys[0] < ys[1] <= bottom + 1, item
        else:
            assert all(left <= x <= right for x in xs), item
            assert all(top <= y <= bottom for y in ys), item


@settings(max_examples=200, deadline=None)
@given(
    series,
    configs,
    references,
    st.integers(1, 90),
    st.integers(1, 30),
    st.one_of(st.none(), st.integers(0, 29)),
)
def test_every_key_names_one_item(given_series, options, refs, width, height, at):
    """The widget keeps one canvas item per key: a key used twice would
    leave the first item behind, never changed and never deleted. With
    the crosshair on, the readout and the marks name every series."""
    cursor = None if at is None else float(at)
    drawing = draw(build(given_series), options, width, height, refs, cursor)
    keys = [item.key for item in drawing.items]
    assert len(keys) == len(set(keys))


@settings(max_examples=200, deadline=None)
@given(series, configs, st.integers(20, 90), st.integers(8, 30))
def test_every_tick_is_inside_its_axis(given_series, options, width, height):
    """A tick label names a value the axis reaches, at the row or column
    where that value is drawn: never past either end."""
    options = {**options, "ticklabels": True, "legend": "hide"}
    drawing = draw(build(given_series), options, width, height)
    if drawing.plot is None:
        return
    plot = drawing.plot
    for item in drawing.items:
        if not item.key.startswith("tick."):
            continue
        column, row = item.coords[0], item.coords[1] // 2
        if item.key.startswith("tick.y."):
            assert plot.y <= row < plot.y + plot.height, item
        else:
            label = dict(item.options)["text"]
            assert plot.x <= column and column + len(label) <= plot.x + plot.width, item
    xs = drawing.xs
    if drawing.xspan is not None:
        assert drawing.xspan.minimum == min(xs) and drawing.xspan.maximum == max(xs)


# ------------------------------------------------------------ the widget


@pytest.fixture
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


points = st.lists(st.tuples(st.integers(0, 40), values), max_size=12)
names = st.sampled_from(["a", "b", "c"])
operations = st.lists(
    st.one_of(
        st.tuples(st.just("add"), names, points, st.sampled_from(["line", "area"])),
        st.tuples(st.just("set"), names, points),
        st.tuples(st.just("append"), names, st.tuples(st.integers(0, 60), values)),
        st.tuples(st.just("delete"), names),
        st.tuples(st.just("hide"), names, st.booleans()),
        st.tuples(st.just("reference"), st.floats(-100, 100, allow_nan=False)),
        st.tuples(st.just("unreference")),
        st.tuples(
            st.just("key"),
            st.sampled_from(
                ["Left", "Right", "Home", "End", "Escape", "Up", "Down", "space"]
            ),
        ),
        st.tuples(st.just("click"), st.integers(0, 59), st.integers(0, 15)),
        st.tuples(
            st.just("configure"),
            st.sampled_from(
                [
                    {"stackmode": "percentage"},
                    {"stackmode": "stacked"},
                    {"legend": "show"},
                    {"legendposition": "left"},
                    {"readout": False},
                    {"readout": True},
                    {"gridlines": True},
                    {"scaletype": "log"},
                    {"scaletype": "linear"},
                    {"legendstats": ("average", "max")},
                ]
            ),
        ),
    ),
    max_size=25,
)


def apply(widget, operation):
    kind, *args = operation
    try:
        if kind == "add":
            widget.add_series(args[0], args[1], kind=args[2])
        elif kind == "set":
            widget.set_series(args[0], args[1])
        elif kind == "append":
            widget.append(args[0], args[1])
        elif kind == "delete":
            widget.delete_series(args[0])
        elif kind == "hide":
            widget.series_configure(args[0], hidden=args[1])
        elif kind == "reference":
            widget.reference_add(args[0])
        elif kind == "unreference" and widget.references():
            widget.reference_delete(widget.references()[0])
        elif kind == "key":
            widget.event_generate(f"<Key-{args[0]}>")
        elif kind == "click":
            widget.event_generate("<Button-1>", x=args[0], y=args[1])
        elif kind == "configure":
            widget.configure(**args[0])
    except tk.TclError:
        pass  # a refused change changes nothing, which is checked below


def kept(cursor, xs):
    """Where the crosshair belongs after the data changed: where it was if
    that x is still there, else the nearest x left of it, else the first;
    nowhere when there are none."""
    if cursor is None or not xs:
        return None
    if cursor in xs:
        return cursor
    left = [x for x in xs if x < cursor]
    return left[-1] if left else xs[0]


@settings(max_examples=150, deadline=None, suppress_health_check=SHARED)
@given(operations)
def test_after_anything_the_canvas_holds_the_chart_and_the_programs_items(
    root, history
):
    """After any sequence of changes, keys and clicks, drawn after each:
    the canvas holds exactly the items the chart says it made, one per
    key; the program's own items are untouched and above them; the
    crosshair is at an x of a shown series, or nowhere; a change to the
    data keeps it at its x or moves it left; the cursor event is sent
    exactly when it moves; and the legend event exactly when a key or
    click hides or shows a series, naming it."""
    widget = XYChart(root, width=60, height=16)
    try:
        widget.focus_set()
        # Two series to start from, so keys and clicks have something to
        # move along before the history adds or takes any away.
        widget.add_series("a", [(x, x % 4) for x in range(0, 30, 3)])
        widget.add_series("b", [(x, 5 - x % 5) for x in range(0, 30, 2)], kind="area")
        line = widget.create_line(2, 2, 20, 20, fill="red")
        note = widget.create_text(5, 5, text="mine", anchor="nw")
        mine = {line: widget.coords(line), note: widget.coords(note)}
        sent = []
        widget.bind(CURSOR_EVENT, lambda _e: sent.append(widget._cursor))
        legend = []
        widget.bind(LEGEND_EVENT, lambda _e: legend.append(widget.legend_focus()))

        def hidden():
            return {n: widget.series_cget(n, "hidden") for n in widget.series()}

        for operation in history:
            before = widget._cursor
            was = hidden()
            sent.clear()
            legend.clear()
            apply(widget, operation)
            widget._update()
            after = widget._cursor
            assert bool(sent) == (after != before), (operation, before, after)
            if operation[0] not in ("key", "click"):
                assert after == kept(before, widget._model.xs()), operation
                assert legend == [], operation
            else:
                now = hidden()
                changed = [
                    n for n in now if was.get(n) is not None and now[n] != was[n]
                ]
                assert legend == changed, (operation, was, now)
            made = {ident for ident, _ in widget._made.values()}
            assert set(widget.find_withtag(TAG)) == made
            assert len(made) == len(widget._made)
            assert {item.key for item in widget._drawing.items} == set(widget._made)
            order = widget.find_all()
            assert set(order[-2:]) == set(mine)
            assert {ident: widget.coords(ident) for ident in mine} == mine
            cursor = widget._cursor
            assert cursor is None or cursor in widget._model.xs()
            assert all(not math.isnan(x) for x in widget._model.xs())
    finally:
        widget.destroy()


@settings(max_examples=150, deadline=None, suppress_health_check=SHARED)
@given(
    st.lists(st.integers(0, 30), min_size=1, max_size=12, unique=True),
    st.integers(0, 11),
    st.lists(st.integers(0, 30), max_size=12, unique=True),
)
def test_new_data_keeps_the_crosshair_or_moves_it_left(root, xs, pick, new):
    """Whatever the points become, the crosshair stays at its x if it is
    still there, else goes to the nearest x left of it, else the first."""
    widget = XYChart(root, width=60, height=16)
    try:
        widget.add_series("a", [(x, 1) for x in xs])
        at = sorted(xs)[pick % len(xs)]
        widget.cursor(at)
        widget.set_series("a", [(x, 1) for x in new])
        widget._update()
        assert widget.cursor() == kept(at, sorted(new))
    finally:
        widget.destroy()


# ------------------------------------------------------------------ size


SCREEN = (80, 24)


@pytest.fixture
def screen(monkeypatch):
    size = [SCREEN]
    monkeypatch.setattr(tk.Misc, "_screen_size", lambda self: size[0])
    return size


def requested(widget):
    return (widget._requested.width, widget._requested.height)


cells_or_share = st.one_of(
    st.integers(1, 200), st.integers(1, 100).map(lambda p: f"{p}%")
)


@settings(deadline=None, suppress_health_check=SHARED)
@given(cells_or_share, cells_or_share)
def test_the_axes_are_independent(screen, root, width, height):
    """Whatever one axis is given, the other asks for what it alone says:
    cells as given, a share of the terminal, or the natural size."""

    def expected(value, whole):
        if isinstance(value, str):
            return max(1, round(whole * int(value[:-1]) / 100))
        return value

    made = [
        XYChart(root, width=width, height=height),
        XYChart(root, width=width),
        XYChart(root, height=height),
    ]
    try:
        both, wide, tall = (requested(widget) for widget in made)
        assert both == (expected(width, SCREEN[0]), expected(height, SCREEN[1]))
        assert wide[1] == NATURAL_SIZE[1]
        assert tall[0] == NATURAL_SIZE[0]
    finally:
        for widget in made:
            widget.destroy()
