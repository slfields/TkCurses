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

"""XYChart's legend, crosshair and readout: what the scene draws for
them, and the keys, clicks and event that work them."""

from __future__ import annotations

import datetime

import pytest

import tkcurses as tk
from tkcurses._charts.numformat import NumberFormat
from tkcurses._core.colors import rgb_of
from tkcurses.xychart import CURSOR_EVENT, LEGEND_EVENT, XYChart
from tkcurses.xychart._model import Model
from tkcurses.xychart._scene import TAG, Config, chart

COLORS = ("green", "red", "blue")
START = datetime.datetime(2026, 11, 23, 23, 30)


def model_of(*series):
    model = Model()
    for name, points, kind in series:
        model.add(name, points, kind=kind)
    return model


TWO = (
    ("cpu", [(t, 40 + t) for t in range(10)], "line"),
    ("mem", [(t, None if t == 4 else 10.0 * t) for t in range(10)], "line"),
)


def draw(model, width=60, height=14, *, cursor=None, focus=None, **options):
    config = Config(colors=COLORS, **options)
    return chart(
        model,
        config,
        width,
        height,
        depth=256,
        rgb=rgb_of,
        background=(0, 0, 0),
        xkind=model.xkind or "number",
        cursor=cursor,
        legend_focus=focus,
    )


def keyed(drawing):
    return {item.key: item for item in drawing.items}


def option(item, name):
    return dict(item.options).get(name)


def text(item):
    return option(item, "text")


# ------------------------------------------------------------------ legend


def test_two_series_have_a_legend_at_the_right():
    drawing = draw(model_of(*TWO))
    items = keyed(drawing)
    assert text(items["legend.cpu.name"]) == "cpu"
    assert option(items["legend.cpu.name"], "font") == "bold"
    assert text(items["legend.cpu.swatch"]) == "██"
    assert option(items["legend.mem.swatch"], "fill") == "red"
    assert drawing.legend is not None
    assert drawing.plot.x + drawing.plot.width <= drawing.legend.edge.x
    assert TAG + ".legend" in items["legend.edge"].tags


def test_one_series_has_none_unless_asked():
    one = model_of(TWO[0])
    assert draw(one).legend is None
    assert draw(one, legend="show").legend is not None
    assert draw(model_of(*TWO), legend="hide").legend is None


@pytest.mark.parametrize("side", ["left", "top", "bottom"])
def test_the_legend_and_the_plot_never_meet(side):
    drawing = draw(model_of(*TWO), legendposition=side)
    edge, plot = drawing.legend.edge, drawing.plot
    apart = (
        edge.x + edge.width <= plot.x
        or plot.x + plot.width <= edge.x
        or edge.y + edge.height <= plot.y
        or plot.y + plot.height <= edge.y
    )
    assert apart


def test_statistics_go_under_the_description():
    model = model_of(*TWO)
    model.configure("cpu", description="all cores")
    items = keyed(
        draw(
            model,
            legendstats=("average", "count"),
            numbers=NumberFormat(units="%"),
            legendsize="xlarge",
        )
    )
    assert text(items["legend.cpu.told"]) == "all cores\navg 44.5% · count 10"
    # mem misses a value: avg of the nine it has, with missing="hide".
    assert text(items["legend.mem.told"]) == "avg 45.6% · count 9"


def test_statistics_are_of_the_values_drawn():
    filled = keyed(draw(model_of(*TWO), legendstats=("count",), missing="linear"))
    assert text(filled["legend.mem.told"]) == "count 10"


def test_a_hidden_series_keeps_a_hollow_dim_entry():
    model = model_of(*TWO)
    model.configure("mem", hidden=True)
    items = keyed(draw(model))
    assert text(items["legend.mem.swatch"]) == "░░"
    assert option(items["legend.mem.name"], "font") is None
    assert option(items["legend.mem.name"], "fill") not in ("", None)
    assert not [key for key in items if key.startswith("line.mem")]


def test_the_entry_with_the_keyboard_is_underlined():
    items = keyed(draw(model_of(*TWO), focus="mem"))
    assert option(items["legend.mem.name"], "font") == "bold underline"


# ------------------------------------------------------- crosshair, readout


def test_with_no_crosshair_the_readout_names_the_range():
    items = keyed(draw(model_of(*TWO)))
    assert text(items["readout.x"]) == "0 \u2013 9"
    assert items["readout.x"].coords == (0, 26)  # the bottom row


def test_the_crosshair_marks_each_series_and_the_readout_says_their_values():
    drawing = draw(model_of(*TWO), cursor=3, numbers=NumberFormat(units="%"))
    items = keyed(drawing)
    keys = [item.key for item in drawing.items]
    assert keys.index("cursor.line") < keys.index("line.cpu.0")
    assert keys.index("cursor.cpu") > keys.index("line.mem.0")
    assert text(items["readout.x"]) == "3"
    assert text(items["readout.cpu"]) == "cpu 43%"
    assert option(items["readout.cpu"], "fill") == "green"
    assert text(items["readout.mem"]) == "mem 30%"


def test_a_missing_value_reads_as_a_dash():
    items = keyed(draw(model_of(*TWO), cursor=4))
    assert text(items["readout.mem"]) == "mem \u2013"
    assert "cursor.mem" not in items


def test_a_readout_too_long_is_cut():
    items = keyed(
        draw(
            model_of(*TWO),
            30,
            14,
            cursor=3,
            legend="hide",
            numbers=NumberFormat(units=" requests per second"),
        )
    )
    words = [text(i) for k, i in items.items() if k.startswith("readout.")]
    assert sum(len(w) for w in words) + 2 * (len(words) - 1) <= 30
    assert words[-1].endswith("…")


def test_a_time_is_read_out_with_its_day():
    points = [(START + datetime.timedelta(minutes=n), n) for n in range(60)]
    items = keyed(
        draw(
            model_of(("a", points, "line")),
            cursor=(START + datetime.timedelta(minutes=31)).timestamp(),
        )
    )
    assert text(items["readout.x"]) == "Nov 24 00:01"


def test_without_the_readout_the_plot_takes_the_row():
    with_it, without = draw(model_of(*TWO)), draw(model_of(*TWO), readout=False)
    assert without.plot.height == with_it.plot.height + 1
    assert not [i for i in without.items if i.key.startswith("readout.")]


# ------------------------------------------------------------------ widget


@pytest.fixture
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


@pytest.fixture
def widget(root):
    made = XYChart(root, width=60, height=14)
    for name, points, kind in TWO:
        made.add_series(name, points, kind=kind)
    made._update()
    return made


def press(widget, key):
    widget.event_generate(f"<Key-{key}>")
    widget._update()


def test_the_keys_move_the_crosshair_between_xs(widget):
    moves = []
    widget.bind(CURSOR_EVENT, lambda _e: moves.append(widget.cursor()))
    assert widget.cursor() is None
    press(widget, "Right")
    assert widget.cursor() == 0
    press(widget, "Right")
    press(widget, "Right")
    assert widget.cursor() == 2
    press(widget, "Left")
    assert widget.cursor() == 1
    press(widget, "End")
    press(widget, "Right")  # stays at the last
    assert widget.cursor() == 9
    press(widget, "Home")
    press(widget, "Escape")
    assert widget.cursor() is None
    assert moves == [0, 1, 2, 1, 9, 0, None]
    assert widget.find_withtag(f"{TAG}.readout")


def test_left_with_no_crosshair_starts_at_the_end(widget):
    press(widget, "Left")
    assert widget.cursor() == 9


def test_cursor_snaps_to_the_nearest_x_and_reads_back(widget):
    widget.cursor(3.4)
    assert widget.cursor() == 3
    widget.cursor(None)
    assert widget.cursor() is None
    with pytest.raises(tk.TclError, match="expected a number for x"):
        widget.cursor("soon")


def test_the_crosshair_stays_across_updates_or_moves_left(widget):
    widget.cursor(6)
    widget.set_series("cpu", [(t, 1) for t in range(10)])
    widget._update()
    assert widget.cursor() == 6
    moves = []
    widget.bind(CURSOR_EVENT, lambda _e: moves.append(widget.cursor()))
    widget.set_series("cpu", [(t, 1) for t in (0, 2, 4, 8)])
    widget.set_series("mem", [(t, 1) for t in (1, 5)])
    widget._update()
    assert widget.cursor() == 5
    assert moves == [5]
    assert widget.find_withtag(f"{TAG}.cursor")


def test_a_time_chart_reads_its_crosshair_as_a_datetime(root):
    widget = XYChart(root)
    widget.add_series(
        "a", [(START + datetime.timedelta(minutes=n), n) for n in range(10)]
    )
    widget.cursor(START + datetime.timedelta(minutes=4, seconds=20))
    assert widget.cursor() == START + datetime.timedelta(minutes=4)


def test_up_down_and_space_hide_a_series_from_the_legend(widget):
    widget.focus_set()
    press(widget, "Down")
    press(widget, "Down")
    press(widget, "space")
    assert widget.series_cget("mem", "hidden") is True
    press(widget, "space")
    assert widget.series_cget("mem", "hidden") is False


def click(widget, column, row):
    widget.event_generate("<Button-1>", x=column, y=row)
    widget._update()


def test_a_click_on_the_plot_puts_the_crosshair_at_the_nearest_x(widget):
    plot = widget._drawing.plot
    click(widget, plot.x + plot.width - 1, plot.y + 1)
    assert widget.cursor() == 9
    click(widget, plot.x, plot.y + 1)
    assert widget.cursor() == 0


def test_a_click_on_an_entry_hides_its_series(widget):
    placed = {p.iid: p for p in widget._drawing.legend.placed}
    entry = placed["cpu"]
    click(widget, entry.x + 4, entry.y)
    assert widget.series_cget("cpu", "hidden") is True
    assert widget.cursor() is None


def test_a_click_still_reaches_the_programs_tag_bindings(widget):
    seen = []
    widget.tag_bind(f"{TAG}.axis", "<Button-1>", lambda _e: seen.append(1))
    axis = widget._drawing.plot.x - 1
    click(widget, axis, 1)
    assert seen == [1]


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"legend": "maybe"}, 'bad legend "maybe"'),
        ({"legendposition": "middle"}, 'bad legendposition "middle"'),
        ({"legendlines": 6}, "legendlines must be at most 5"),
        ({"legendstats": ["average", "mode"]}, 'bad legendstats "mode"'),
    ],
)
def test_a_bad_legend_option_is_refused(root, options, message):
    with pytest.raises(tk.TclError, match=message):
        XYChart(root, **options)


def test_with_every_series_hidden_the_legend_stays_to_show_them_again(widget):
    widget.series_configure("cpu", hidden=True)
    widget.series_configure("mem", hidden=True)
    widget._update()
    legend = widget._drawing.legend
    assert legend is not None
    assert widget.find_withtag(f"{TAG}.legend")
    entry = {p.iid: p for p in legend.placed}["mem"]
    click(widget, entry.x + 4, entry.y)
    assert widget.series_cget("mem", "hidden") is False
    assert widget.find_withtag(f"{TAG}.series.mem")


def test_with_every_series_hidden_the_keys_still_reach_the_legend(widget):
    widget.focus_set()
    for name in ("cpu", "mem"):
        widget.series_configure(name, hidden=True)
    widget._update()
    press(widget, "Down")
    press(widget, "space")
    assert widget.series_cget("cpu", "hidden") is False


def test_a_quick_second_click_counts_as_a_click(widget):
    placed = {p.iid: p for p in widget._drawing.legend.placed}
    widget.event_generate("<Button-1>", x=placed["cpu"].x + 4, y=placed["cpu"].y)
    widget.event_generate("<Double-Button-1>", x=placed["mem"].x + 4, y=placed["mem"].y)
    assert widget.series_cget("cpu", "hidden") is True
    assert widget.series_cget("mem", "hidden") is True


@pytest.mark.parametrize(
    ("key", "ready"),
    [
        ("Escape", lambda w: w.cursor(0)),
        ("Left", lambda w: None),
        ("Home", lambda w: None),
        ("Down", lambda w: None),
        ("space", lambda w: press(w, "Down")),
    ],
)
def test_a_key_the_chart_uses_goes_no_further(root, widget, key, ready):
    reached = []
    root.bind(f"<Key-{key}>", lambda _e: reached.append(key))
    ready(widget)
    press(widget, key)
    assert reached == []


def test_a_key_with_nothing_to_do_reaches_the_window(root, widget):
    # Escape with no crosshair and no legend entry chosen is the
    # program's, as TreeMap's Escape is when it has nothing to undo.
    reached = []
    root.bind("<Escape>", lambda _e: reached.append("Escape"))
    widget.cursor(0)
    press(widget, "Escape")
    press(widget, "Escape")
    assert reached == ["Escape"]
    root.bind("<Key-space>", lambda _e: reached.append("space"))
    press(widget, "space")
    assert reached == ["Escape", "space"]


def test_a_legend_click_sends_the_legend_event_naming_its_series(widget):
    heard = []
    widget.bind(
        LEGEND_EVENT,
        lambda _e: heard.append(
            (widget.legend_focus(), widget.series_cget(widget.legend_focus(), "hidden"))
        ),
    )
    placed = {p.iid: p for p in widget._drawing.legend.placed}
    click(widget, placed["mem"].x + 4, placed["mem"].y)
    click(widget, placed["mem"].x + 4, placed["mem"].y)
    assert heard == [("mem", True), ("mem", False)]


def test_space_on_the_legend_sends_it_too(widget):
    heard = []
    widget.bind(LEGEND_EVENT, lambda _e: heard.append(widget.legend_focus()))
    widget.focus_set()
    press(widget, "space")  # nothing underlined: nothing changes
    press(widget, "Down")
    press(widget, "space")
    assert heard == ["cpu"]


def test_the_programs_own_change_sends_no_legend_event(widget):
    # As Tk reports no configure a program makes itself.
    heard = []
    widget.bind(LEGEND_EVENT, lambda _e: heard.append(1))
    widget.series_configure("cpu", hidden=True)
    widget._update()
    assert heard == []


def test_legend_focus_is_empty_until_an_entry_is_chosen(widget):
    assert widget.legend_focus() == ""
    widget.focus_set()
    press(widget, "Down")
    assert widget.legend_focus() == "cpu"
    press(widget, "Escape")
    assert widget.legend_focus() == ""
