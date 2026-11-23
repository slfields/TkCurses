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

"""The XYChart widget and the scene it draws, without a terminal."""

from __future__ import annotations

import datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import tkcurses as tk
from tkcurses._charts.geometry import Rect
from tkcurses._core.colors import rgb_of
from tkcurses.xychart import NATURAL_SIZE, XYChart
from tkcurses.xychart._model import Model
from tkcurses.xychart._scene import TAG, Config, scene

PLOT = Rect(0, 0, 40, 20)
COLORS = ("green", "red", "blue")


def draw(model, depth=256, plot=PLOT, **options):
    config = Config(colors=COLORS, **options)
    return scene(model, config, plot, depth=depth, rgb=rgb_of, background=(0, 0, 0))


def model_of(*series):
    model = Model()
    for name, points, kind in series:
        model.add(name, points, kind=kind)
    return model


LINE = ("a", [(0, 1), (5, 4), (10, 2)], "line")
AREA = ("b", [(0, 2), (5, 2), (10, 2)], "area")

# ------------------------------------------------------------------- scene


def test_nothing_to_draw_is_no_items():
    assert draw(Model()) == []
    assert draw(model_of(LINE), plot=Rect(0, 0, 0, 5)) == []


def test_fills_come_before_lines_and_lines_before_points():
    items = draw(model_of(LINE, AREA), points="show")
    kinds = [item.key.split(".")[0] for item in items]
    assert kinds == sorted(kinds, key=["area", "line", "point"].index)
    assert {"area", "line", "point"} == set(kinds)


def test_every_item_is_tagged_and_named_for_its_series():
    for item in draw(model_of(LINE, AREA), points="show"):
        assert item.tags[0] == TAG
        part, name = item.key.split(".")[:2]
        assert item.tags[1] == f"{TAG}.{'series' if part == 'line' else part}.{name}"


def test_keys_are_unique():
    items = draw(model_of(LINE, AREA), points="show", dottedgaps=True)
    assert len({item.key for item in items}) == len(items)


def test_an_area_is_dimmed_at_256_colours_and_not_below():
    dim = [i for i in draw(model_of(AREA)) if i.kind == "polygon"]
    assert dict(dim[0].options)["fill"] not in ("green", "")
    flat = [i for i in draw(model_of(AREA), depth=8) if i.kind == "polygon"]
    assert dict(flat[0].options)["fill"] == "green"


def test_series_take_the_colours_in_turn_unless_they_have_their_own():
    model = model_of(LINE, ("c", [(0, 0), (10, 9)], "line"))
    model.configure("c", color="#123456")
    fills = {
        item.key.split(".")[1]: dict(item.options)["fill"]
        for item in draw(model, points="hide")
    }
    assert fills == {"a": "green", "c": "#123456"}


def test_a_hidden_series_is_not_drawn():
    model = model_of(LINE, AREA)
    model.configure("b", hidden=True)
    assert {item.key.split(".")[1] for item in draw(model)} == {"a"}


def test_a_point_is_one_pixel_lighter_than_its_line():
    model = model_of(("a", [(5, 1)], "line"))
    line, point = draw(model)  # the line is the one pixel too
    x, y = point.coords[:2]
    assert (point.kind, point.coords) == ("rectangle", (x, y, x + 1, y + 1))
    assert line.coords == point.coords
    assert dict(point.options) == {"fill": "#80e680", "outline": ""}
    assert dict(draw(model, depth=8)[1].options)["fill"] == "white"


def test_points_follow_the_option():
    def points(mode):
        return [
            i for i in draw(model_of(LINE), points=mode) if i.key.startswith("point")
        ]

    assert len(points("show")) == 3
    assert points("hide") == []
    assert len(points("auto")) == 3  # 20 pixels apart


def test_a_filled_gap_is_dotted_only_when_asked():
    gappy = ("a", [(0, 1), (1, None), (2, None), (3, None), (4, 4)], "line")
    solid = draw(model_of(gappy), missing="linear")
    dotted = draw(model_of(gappy), missing="linear", dottedgaps=True)
    assert len([i for i in dotted if i.key.startswith("line")]) > len(solid)
    hidden = draw(model_of(gappy))  # missing="hide": no line across
    assert all(i.coords[-2] < 39 or i.coords[0] > 0 for i in hidden)


@settings(max_examples=60)
@given(
    st.lists(
        st.lists(st.one_of(st.none(), st.floats(-1e6, 1e6)), min_size=1, max_size=12),
        min_size=1,
        max_size=3,
    ),
    st.sampled_from(["line", "area"]),
    st.sampled_from(["straight", "smooth", "step"]),
    st.sampled_from(["stacked", "unstacked", "percentage"]),
    st.sampled_from(["full", "data", "custom"]),
)
def test_every_pixel_drawn_is_on_the_plot(columns, kind, interpolation, mode, bounds):
    model = Model()
    for n, ys in enumerate(columns):
        model.add(f"s{n}", list(enumerate(ys)), kind=kind)
    plot = Rect(3, 2, 30, 15)
    extra = {"minimum": -10.0, "maximum": 10.0} if bounds == "custom" else {}
    items = draw(
        model,
        plot=plot,
        interpolation=interpolation,
        stackmode=mode,
        bounds=bounds,
        points="show",
        missing="linear",
        dottedgaps=True,
        **extra,
    )
    for item in items:
        xs, ys = item.coords[0::2], item.coords[1::2]
        if item.kind == "rectangle":  # one pixel: the far corner is outside it
            xs, ys = xs[:1], ys[:1]
        assert all(plot.x <= x < plot.x + plot.width for x in xs), item
        assert all(plot.y <= y < plot.y + plot.height for y in ys), item


# ------------------------------------------------------------------ widget


@pytest.fixture
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


def test_defaults(root):
    chart = XYChart(root)
    assert chart.cget("stackmode") == "stacked"
    assert chart.cget("interpolation") == "straight"
    assert chart.cget("points") == "auto"
    assert chart.cget("bounds") == "full"
    assert chart.series() == ()


def test_the_natural_size_is_60_by_16_and_each_axis_is_its_own(root):
    assert NATURAL_SIZE == (60, 16)
    chart = XYChart(root)
    assert (chart.winfo_reqwidth(), chart.winfo_reqheight()) == (60, 16)
    wide = XYChart(root, width=20)
    assert (wide.winfo_reqwidth(), wide.winfo_reqheight()) == (20, 16)
    short = XYChart(root, height=5)
    assert (short.winfo_reqwidth(), short.winfo_reqheight()) == (60, 5)


def test_a_share_of_the_screen_is_read_back_as_written_and_followed(root):
    chart = XYChart(root, width="50%", height=10)
    assert (chart.cget("width"), chart.cget("height")) == ("50%", 10)
    assert chart._size.binding is not None
    chart.configure(width=30)
    assert chart._size.binding is None
    chart.configure(height="25%")
    assert chart._size.binding is not None
    chart.destroy()


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (
            {"stackmode": "x"},
            'bad stackmode "x": must be stacked, percentage, or unstacked',
        ),
        ({"bounds": "x"}, 'bad bounds "x": must be full, data, or custom'),
        ({"logbase": 1}, "logbase must be above 1, not 1"),
        ({"minimum": 5, "maximum": 1}, r"maximum \(1\) must be above minimum \(5\)"),
        (
            {"scaletype": "log", "minimum": 0},
            "a log scale needs a minimum above 0, not 0",
        ),
        ({"colors": ["nocolour"]}, 'unknown color name "nocolour"'),
        ({"dottedgaps": "perhaps"}, "expected a boolean, not 'perhaps'"),
        ({"width": "abc"}, None),
    ],
)
def test_a_bad_option_is_refused_at_creation_and_in_configure(root, options, message):
    with pytest.raises(tk.TclError, match=message):
        XYChart(root, **options)
    chart = XYChart(root)
    with pytest.raises(tk.TclError, match=message):
        chart.configure(**options)
    assert chart.cget("stackmode") == "stacked"
    assert chart.cget("minimum") == ""
    assert chart._config == XYChart(root)._config


def test_the_series_methods(root):
    chart = XYChart(root)
    chart.add_series("cpu", [(2, 5), (1, 3)], text="CPU")
    chart.add_series("mem", kind="area", color="red")
    assert chart.series() == ("cpu", "mem")
    assert chart.series_points("cpu") == [(1.0, 3.0), (2.0, 5.0)]
    chart.append("cpu", (3, 7), (2, 6))
    assert chart.series_points("cpu") == [(1.0, 3.0), (2.0, 6.0), (3.0, 7.0)]
    chart.set_series("cpu", [(0, None)])
    assert chart.series_points("cpu") == [(0.0, None)]
    assert chart.series_cget("cpu", "text") == "CPU"
    assert chart.series_cget("mem", "kind") == "area"
    chart.series_configure("mem", description="memory", hidden=1)
    assert chart.series_configure("mem") == {
        "kind": "area",
        "text": "",
        "color": "red",
        "description": "memory",
        "hidden": True,
    }
    chart.delete_series("cpu")
    assert chart.series() == ("mem",)


def test_times_on_the_x_axis(root):
    chart = XYChart(root)
    day = datetime.date(2026, 11, 23)
    chart.add_series("a", [(day, 1)])
    midnight = datetime.datetime(2026, 11, 23)
    assert chart.series_points("a") == [(midnight, 1.0)]
    with pytest.raises(tk.TclError):
        chart.append("a", (5, 1))  # a number where times are


def test_points_read_back_can_be_given_back(root):
    """As a program feeding live data does: read, drop the oldest, add one."""
    chart = XYChart(root)
    start = datetime.datetime(2026, 11, 23, 23, 58)
    minute = datetime.timedelta(minutes=1)
    chart.add_series("a", [(start + n * minute, n) for n in range(3)])
    points = chart.series_points("a")
    chart.set_series("a", [*points[1:], (points[-1][0] + minute, 3)])
    assert chart.series_points("a") == [(start + n * minute, n) for n in range(1, 4)]
    numbers = XYChart(root)
    numbers.add_series("a", [(1, 2)])
    numbers.set_series("a", numbers.series_points("a"))
    assert numbers.series_points("a") == [(1.0, 2.0)]


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda c: c.add_series("a"), "already"),
        (lambda c: c.add_series("b", kind="bar"), "bar"),
        (lambda c: c.add_series("b", color="nocolour"), "unknown color name"),
        (lambda c: c.add_series("b", [(0, "x")]), None),
        (lambda c: c.set_series("nosuch", []), "nosuch"),
        (lambda c: c.append("nosuch", (0, 1)), "nosuch"),
        (lambda c: c.delete_series("a", "nosuch"), "nosuch"),
        (lambda c: c.series_cget("a", "colour"), 'unknown option "-colour"'),
        (lambda c: c.series_configure("a", colour="red"), 'unknown option "-colour"'),
        (lambda c: c.series_configure("a", color="nocolour"), "unknown color name"),
        (lambda c: c.series_configure("a", hidden="perhaps"), "boolean"),
        (lambda c: c.series_points("nosuch"), "nosuch"),
    ],
)
def test_refusals_are_tcl_errors_and_change_nothing(root, call, message):
    chart = XYChart(root)
    chart.add_series("a", [(0, 1)])
    with pytest.raises(tk.TclError, match=message):
        call(chart)
    assert chart.series() == ("a",)
    assert chart.series_points("a") == [(0.0, 1.0)]
    assert chart.series_configure("a")["color"] == ""


def test_many_changes_ask_for_one_drawing(root, monkeypatch):
    asked = []
    chart = XYChart(root)
    monkeypatch.setattr(chart, "after_idle", lambda f: asked.append(f) or "after#1")
    chart._pending = None
    chart.add_series("a")
    for n in range(100):
        chart.append("a", (n, n))
    assert len(asked) == 1
    chart._update()
    chart.append("a", (100, 1))
    assert len(asked) == 2


def test_items_are_changed_in_place_and_keep_their_ids(root):
    chart = XYChart(root)
    chart.add_series("a", [(0, 1), (5, 4), (10, 2)])
    chart.add_series("b", [(0, 2), (10, 2)], kind="area")
    chart._update()
    before = chart.find_withtag(TAG)
    assert before
    # The same range, so the axes keep their ticks too.
    chart.set_series("a", [(0, 4), (5, 1), (10, 2)])
    chart._update()
    assert chart.find_withtag(TAG) == before
    chart.delete_series("b")
    chart._update()
    assert chart.find_withtag(f"{TAG}.area.b") == ()
    assert set(chart.find_withtag(TAG)) < set(before)


def test_the_programs_own_items_stay_above_the_charts(root):
    chart = XYChart(root)
    mine = chart.create_line(0, 0, 10, 10)
    chart.add_series("a", [(0, 1), (10, 2)])
    chart._update()
    chart.add_series("b", [(0, 3), (10, 1)], kind="area")
    chart._update()
    order = chart.find_all()
    assert order[-1] == mine
    ours = [item for item in order if TAG in chart.gettags(item)]
    assert order[: len(ours)] == tuple(ours)
    assert chart.find_withtag(f"{TAG}.area.b")[0] == ours[0]  # fills first
    chart.delete(mine)
    chart.set_series("a", [(0, 2), (10, 2)])
    chart._update()  # a chart whose program drew nothing is left alone


def test_a_hidden_series_leaves_the_canvas(root):
    chart = XYChart(root)
    chart.add_series("a", [(0, 1), (10, 2)])
    chart._update()
    chart.series_configure("a", hidden=True)
    chart._update()
    assert chart.find_withtag(TAG) == ()
    chart.series_configure("a", hidden=False)
    chart._update()
    assert chart.find_withtag(f"{TAG}.series.a")


def test_an_option_change_draws_again(root):
    chart = XYChart(root, points="hide")
    chart.add_series("a", [(0, 1), (10, 2)])
    chart._update()
    assert chart.find_withtag(f"{TAG}.point.a") == ()
    chart.configure(points="show")
    chart._update()
    assert len(chart.find_withtag(f"{TAG}.point.a")) == 2


def test_destroy_cancels_the_pending_drawing(root):
    chart = XYChart(root, width="50%")
    chart.add_series("a", [(0, 1)])
    assert chart._pending is not None
    chart.destroy()
    assert chart._pending is None
    assert chart._size.binding is None
