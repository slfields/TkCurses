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

"""BarGraph options, validation and the refresh throttle, without a terminal."""

from __future__ import annotations

import pytest

import tkcurses as tk
import tkcurses.bargraph as widget_module
from tkcurses.bargraph import BarGraph
from tkcurses.bargraph._render import Cell


@pytest.fixture
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


def test_defaults(root):
    graph = BarGraph(root)
    assert graph.cget("segments") == 1
    assert graph.cget("scale") == "100%"
    assert graph.cget("relief") == "solid"
    assert graph.cget("borderwidth") in (0, "0")


def test_thresholds_allowed_on_a_stacked_graph(root):
    graph = BarGraph(root, series=2, thresholds=[("80%", "yellow"), ("90%", "red")])
    assert len(graph.cget("thresholds")) == 2


@pytest.mark.parametrize(
    "options",
    [
        {"scale": 7},
        {"segments": 0},
        {"mode": "pie"},
        {"orient": "diagonal"},
        {"orient": "vertical", "readout": True},
        {"colormode": "rainbow"},
        {"colormode": "gradient", "gradientstart": "notacolor"},
        {"colormode": "gradient", "colors": ["notacolor"]},
    ],
)
def test_rejects(root, options):
    with pytest.raises(tk.TclError):
        BarGraph(root, **options)


def test_set_get_and_reshape(root):
    graph = BarGraph(root, segments=2, series=2)
    graph.set(0, [40, 25])
    assert graph.get(0) == (40.0, 25.0)
    with pytest.raises(tk.TclError):
        graph.set(0, [1])
    graph.configure(series=3)
    assert graph.get(0) == (40.0, 25.0, 0.0)


def test_many_sets_arm_one_timer(root):
    graph = BarGraph(root, refreshinterval=100)
    graph.set(0, [1])
    first = graph._timer
    for value in range(50):
        graph.set(0, [value])
    assert first is not None
    assert graph._timer == first


def test_destroy_cancels_the_timer(root):
    graph = BarGraph(root)
    graph.set(0, [1])
    graph.destroy()
    assert graph._timer is None


# ------------------------------------------------------------- composing ----


def _text(window) -> list[str]:
    return [
        "".join("~" if cell is None else cell.char for cell in row) for row in window
    ]


def test_compose_draws_the_bars(root):
    graph = BarGraph(root, segments=2, scale=16, maximum=16)
    graph.set_all([[12], [5]])
    assert _text(graph._compose(3, 2)) == ["▄  ", "█ ▅"]


def test_percent_scale_fills_the_space_it_is_given(root):
    graph = BarGraph(root, scale="100%", maximum=10)
    graph.set(0, [5])
    assert _text(graph._compose(1, 4)) == [" ", " ", "█", "█"]
    assert _text(graph._compose(1, 2)) == [" ", "█"]


def test_box_and_title_leave_the_border_to_the_frame(root):
    graph = BarGraph(root, borderwidth=1, label="Hi", scale=8)
    window = graph._compose(8, 3)
    assert _text(window)[0] == "~~ Hi ~~"
    assert window[2] == [None] * 8


def test_vertical_axis_width_follows_its_tick_labels(root):
    graph = BarGraph(root, axis=True, maximum=1, scale="100%")
    rows = _text(graph._compose(6, 10))
    # Ticks 0, 0.2 ... 1: the widest label is 3 cells, so the ruler is at
    # column 3 and the bars start at 4. Label cells left blank stay the
    # frame's (~).
    assert rows[-1][:4] == "~~0┤"
    # 0.2 lands one row above 0, too close, so spaced() drops it.
    assert "0.4" in "".join(rows)
    assert "0.2" not in "".join(rows)


def test_thresholds_color_by_zone(root):
    graph = BarGraph(
        root,
        orient="horizontal",
        scale=16,
        maximum=16,
        thresholds=[(10, "yellow"), (13, "red")],
    )
    graph.set(0, [15])
    cells = graph._compose(2, 1)[0]
    assert [cell.fg for cell in cells] == [("zone", 0), ("zone", 2)]


# --------------------------------------------------------------- options ----


def test_a_bad_option_leaves_the_widget_as_it_was(root):
    graph = BarGraph(root, segments=2)
    with pytest.raises(tk.TclError):
        graph.configure(segments=3, mode="pie")
    assert graph.cget("segments") == 2
    assert graph._config.segments == 2


@pytest.mark.parametrize(
    "options",
    [
        {"maximum": 0},
        {"labelanchor": "center"},
        {"thresholds": [(80, "y"), ("80%", "r")]},
        {"markers": [90]},
        {"gap": -1},
        {"thickness": "x"},
        {"readoutformat": "{:q}", "orient": "horizontal", "readout": True},
        {"digits": 0},
        {"digits": 16},
        {"digits": "three"},
        {"decimals": -1},
        {"rounding": "sideways"},
        {"unitscale": "metric"},
        {"unitplacement": "middle"},
        {"unitspace": "maybe"},
        {"unitscale": "time"},
        {"unitscale": "time", "units": "m"},
        {"scaletype": "cubic"},
        {"scaletype": "log", "minimum": 0},
        {"scaletype": "log", "logbase": 1},
        {"minimum": 100},
        {"minimum": "low"},
        {"maximum": "inf"},
        {"scaletype": "log", "series": 2},
    ],
)
def test_more_bad_options(root, options):
    with pytest.raises(tk.TclError):
        BarGraph(root, **options)


def test_absolute_scale_requests_its_natural_size(root):
    graph = BarGraph(root, segments=3, scale=24)
    assert (graph._requested.width, graph._requested.height) == (5, 3)
    graph.configure(borderwidth=1)
    assert (graph._requested.width, graph._requested.height) == (7, 5)


def test_percent_scale_requests_its_minimum(root):
    graph = BarGraph(root, orient="horizontal", segments=2)
    assert (graph._requested.width, graph._requested.height) == (1, 3)


# ---------------------------------------------------------------- colors ----


def test_roles_map_to_the_configured_colors(root):
    graph = BarGraph(
        root,
        series=2,
        colors=["white", "red"],
        markers=[(50, "cyan")],
        foreground="grey",
    )
    assert graph._color_of(("series", 1)) == "red"
    assert graph._color_of(("series", 3)) == "red"  # cycles
    assert graph._color_of(("marker", 0)) == "cyan"
    assert graph._color_of(("text", 0)) == "grey"


def test_default_colors_cycle(root):
    graph = BarGraph(root, series=2)
    assert graph._color_of(("series", 0)) == "green"


def test_zone_colors(root):
    graph = BarGraph(
        root, colors=["white"], thresholds=[("90%", "red"), ("80%", "yellow")]
    )
    assert [graph._color_of(("zone", i)) for i in range(3)] == [
        "white",
        "yellow",
        "red",
    ]


def test_monochrome_uses_fill_patterns_for_full_cells(root):
    graph = BarGraph(root)
    full = Cell("█", ("series", 1), ("background", 0))
    partial = Cell("▄", ("series", 1), ("background", 0))
    assert graph._glyph(full, monochrome=True) == "▓"
    assert graph._glyph(full, monochrome=False) == "█"
    assert graph._glyph(partial, monochrome=True) == "▄"


def test_runs_group_cells_and_skip_the_frame(root):
    graph = BarGraph(root)
    a = Cell("a", ("text", 0), ("background", 0))
    grid = Cell("┈", ("grid", 0), ("background", 0))
    # Without a color manager every attribute is plain except gridlines' dim.
    runs = graph._runs([a, a, None, a, grid], monochrome=False)
    assert [(column, text) for column, text, _ in runs] == [
        (0, "aa"),
        (3, "a"),
        (4, "┈"),
    ]


# -------------------------------------------------------------- peak hold ----


def test_peak_role(root):
    graph = BarGraph(root, series=3)
    config = graph._config
    assert graph._peak_role(config, (5, 3, 0), 9) == ("series", 1)
    overlay = BarGraph(root, series=3, mode="overlay")._config
    assert graph._peak_role(overlay, (5, 9, 2), 9) == ("series", 1)
    zoned = BarGraph(root, thresholds=[(80, "y"), (90, "r")])._config
    assert graph._peak_role(zoned, (85,), 95) == ("zone", 2)


def test_peak_hold_keeps_the_timer_running_while_peaks_fall(root):
    graph = BarGraph(root, peakholdtime=1000)
    graph.set(0, [80])
    graph.refresh()
    graph.set(0, [10])
    graph.refresh()
    assert graph._held == [80]
    assert graph._peaks_falling()


# --------------------------------------------------------------- gradient ----


def test_gradient_starts_at_a_quarter_unless_named(root):
    graph = BarGraph(
        root,
        series=2,
        colors=["red", "green"],
        colormode="gradient",
        gradientstart=["", "#000080"],
    )
    red, green = graph._config.gradient
    assert red == ((51, 0, 0), (205, 0, 0))
    assert green == ((0, 0, 128), (0, 205, 0))


def test_gradient_shade_colors(root):
    graph = BarGraph(root, colors=["red"], colormode="gradient")
    graph._steps = 8
    assert graph._color_of(("shade", 0)) == "#330000"
    assert graph._color_of(("shade", 7)) == "#cd0000"


def test_solid_colormode_checks_no_colors(root):
    # Color names are TkCurses' business in solid mode, as before.
    assert BarGraph(root, colors=["whatever"])._config.gradient == ()


# ---------------------------------------------------------- number format ----


def test_number_format_options_default_to_the_old_labels(root):
    graph = BarGraph(root)
    assert graph.cget("digits") == "" and graph.cget("decimals") == ""
    assert graph.cget("readoutformat") == ""
    assert graph.cget("unitscale") == "si"


def test_digits_and_decimals_may_be_unset_again(root):
    graph = BarGraph(root, digits=3, decimals=1)
    graph.configure(digits="", decimals=None)
    assert graph._config.numbers.digits is None
    assert graph._config.numbers.decimals is None


def test_axis_labels_use_the_number_format(root):
    graph = BarGraph(
        root, axis=True, maximum=2000, ticks=[0, 1000, 2000], digits=3, units="B"
    )
    rows = _text(graph._compose(8, 10))
    assert rows[0].startswith("2kB┤")
    assert any(row.startswith("1kB┤") for row in rows)
    assert rows[-1].startswith("~0B┤")


def test_axis_width_follows_the_formatted_labels(root):
    graph = BarGraph(
        root, axis=True, maximum=100, ticks=[0, 100], units="$", unitplacement="prefix"
    )
    assert _text(graph._compose(8, 4))[0][:5] == "$100┤"


def test_readout_uses_the_number_format(root):
    graph = BarGraph(
        root, orient="horizontal", readout=True, units="%", maximum=100, scale=40
    )
    graph.set(0, [42.4])
    assert _text(graph._compose(10, 1))[0].endswith("~42%")
    graph.configure(decimals=1)
    assert _text(graph._compose(11, 1))[0].endswith("~42.4%")


def test_readoutformat_still_wins(root):
    graph = BarGraph(
        root,
        orient="horizontal",
        readout=True,
        units="%",
        readoutformat="{:.2f}",
        scale=40,
    )
    graph.set(0, [42.4])
    assert _text(graph._compose(12, 1))[0].endswith("~42.40")


# ------------------------------------------------------------ axis title ----


def test_axis_title_is_a_name_and_the_ticks_keep_their_units(root):
    # Units and magnifiers stay with each value: one axis can need several
    # magnifiers, and for bytes the two are one word.
    graph = BarGraph(
        root,
        borderwidth=1,
        axis=True,
        axislabel="Used",
        maximum=16 * 2**30,
        ticks=[0, 8 * 2**30, 16 * 2**30],
        units="B",
        unitspace=True,
        digits=3,
        unitscale="binary",
    )
    rows = _text(graph._compose(24, 8))
    assert rows[0].startswith("~~ Used ~")
    assert rows[1].startswith("~16 GiB┤")
    assert any(row.startswith("~~8 GiB┤") for row in rows)


def test_axis_title_needs_the_box(root):
    graph = BarGraph(root, axis=True, axislabel="Load", ticks=[0, 100])
    assert "Load" not in "".join(_text(graph._compose(12, 6)))


def test_axis_title_left_out_where_it_does_not_fit(root):
    graph = BarGraph(
        root, borderwidth=1, axis=True, axislabel="A long axis title", ticks=[0, 100]
    )
    assert "A long" not in _text(graph._compose(12, 6))[0]


def test_axis_title_moves_aside_for_the_graph_label(root):
    graph = BarGraph(
        root,
        borderwidth=1,
        axis=True,
        axislabel="ms",
        label="Load",
        labelanchor="nw",
        ticks=[0, 100],
    )
    top = _text(graph._compose(20, 6))[0]
    assert top.startswith("~~ Load ~") and top.endswith("~ ms ~~")


# ------------------------------------------------------------- log scale ----


def test_log_scale_defaults_its_minimum_to_one(root):
    graph = BarGraph(root, scaletype="log", maximum=1000)
    assert graph._config.values.minimum == 1
    assert BarGraph(root)._config.values.minimum == 0


def test_log_scale_cannot_stack_series(root):
    with pytest.raises(tk.TclError, match="cannot stack"):
        BarGraph(root, scaletype="log", series=2)
    # Overlaid, or a single series, is fine.
    BarGraph(root, scaletype="log", series=2, mode="overlay")
    BarGraph(root, scaletype="log", series=1)


def test_log_bars_give_each_power_the_same_length(root):
    graph = BarGraph(
        root, segments=3, scaletype="log", maximum=1000, scale=24, refreshinterval=0
    )
    graph.set_all([[10], [100], [1000]])
    assert _text(graph._compose(5, 3)) == ["    █", "  █ █", "█ █ █"]


def test_minimum_raises_the_base_of_a_linear_graph(root):
    graph = BarGraph(root, segments=2, minimum=50, maximum=100, scale=16)
    graph.set_all([[40], [75]])
    assert _text(graph._compose(3, 2)) == ["   ", "  █"]


def test_explicit_ticks_off_the_scale_are_dropped(root):
    graph = BarGraph(
        root, axis=True, minimum=50, maximum=100, ticks=[0, 50, 100, 150], scale=16
    )
    rows = "".join(_text(graph._compose(6, 2)))
    assert "100┤" in rows and "50┤" in rows
    assert "150" not in rows and "0┤" not in rows.replace("50┤", "").replace("100┤", "")


def test_time_axis_ticks_read_as_a_clock(root):
    graph = BarGraph(
        root, axis=True, maximum=120, units="s", unitscale="time", scale=40
    )
    rows = _text(graph._compose(8, 5))
    labels = [row.split("┤")[0].strip("~ ") for row in rows if "┤" in row]
    assert labels == ["2min", "1min", "0s"]


# ------------------------------------------------------------- autoscale ----


@pytest.fixture
def clock(monkeypatch):
    """The widget's monotonic clock, in seconds, set by the test."""
    now = [100.0]
    monkeypatch.setattr(widget_module.time, "monotonic", lambda: now[0])
    return now


def test_auto_maximum_grows_with_the_data(root, clock):
    graph = BarGraph(root, maximum="auto", scale=16, refreshinterval=0)
    assert graph._shown.maximum == 1
    graph.set_all([[42]])
    graph.refresh()
    assert graph._shown.maximum == 50
    assert _text(graph._compose(1, 2)) == ["▅", "█"]  # 13 of 16 eighths


def test_auto_maximum_shrinks_after_autoscale_ms(root, clock):
    graph = BarGraph(root, maximum="auto", autoscaledelay=2000, refreshinterval=0)
    graph.set_all([[180]])
    graph.refresh()
    graph.set_all([[30]])
    graph.refresh()
    assert graph._shown.maximum == 200
    clock[0] += 2.5
    graph.refresh()
    assert graph._shown.maximum == 50


def test_percent_levels_follow_the_auto_maximum(root, clock):
    graph = BarGraph(
        root,
        maximum="auto",
        thresholds=[("50%", "red"), (30, "yellow")],
        markers=[("80%", "blue")],
        refreshinterval=0,
    )
    graph.set_all([[180]])
    graph.refresh()
    assert graph._shown.thresholds == ((30, "yellow"), (100, "red"))
    assert graph._shown.markers == ((160, "blue"),)


def test_auto_maximum_is_kept_across_configure(root, clock):
    graph = BarGraph(root, maximum="auto", refreshinterval=0)
    graph.set_all([[180]])
    graph.refresh()
    graph.configure(label="cpu", autoscaledelay=100)
    assert graph._shown.maximum == 200
    graph.configure(minimum=500)
    assert graph._shown.maximum == 1000  # a new scale starts over


def test_auto_maximum_keeps_the_timer_while_it_waits_to_shrink(root, clock):
    graph = BarGraph(root, maximum="auto", autoscaledelay=1000, refreshinterval=5)
    graph.set_all([[180]])
    graph._tick()
    graph.set_all([[30]])
    graph._tick()
    assert graph._autoscale.shrinking and graph._timer is not None


def test_gap_zero_puts_bars_side_by_side(root):
    graph = BarGraph(root, segments=3, gap=0, scale=8, refreshinterval=0)
    graph.set_all([[100], [50], [100]])
    assert _text(graph._compose(3, 1)) == ["█▄█"]
