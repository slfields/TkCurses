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

"""XYCharts: lines and areas, stacking, joining, gaps, scales and size;
axes, references, the legend and the crosshair.

What to do, pass 1: n steps the data through lines, areas and times; s
steps stackmode, i interpolation, p points, m missing, e endvalues, d
dottedgaps, c scaletype, b bounds, f nicebounds; h hides and shows the
second series; l starts and stops a live feed, one point every 200 ms
from the program's own timer; x draws a note of the program's own on
the chart; z steps the size through filling the area, 50% by 50% of
the screen, 60 columns by 50%, and 30 columns alone. Run it again under
TERM=xterm and TERM=vt100.

Pass 2: a puts titles on the axes, g draws gridlines, t takes the tick
labels away, r adds reference lines and a band, u steps the units, k
the legend's statistics, j the legend's side and then hides it, o the
readout. Left, Right, Home and End move the crosshair and Escape takes
it away; Up, Down and Space, or a click, hide and show series from the
legend. Line 8 counts the <<XYChartCursor>> events the program got.

What to look for: **lines are unbroken and joined where they should
be**, areas fill to zero or to the area beneath in a dimmer shade and
never hide a line, the gaps in the data show as the missing option
says, the note stays on top, the live feed draws smoothly, and a
percentage size follows the terminal when it is resized. Pass 2: the
axes' labels never meet each other or the plot, the legend and the
readout name each series in its colour, and every series can be shown
again from the legend, even after all are hidden.
TkCurses-j2ao.7, TkCurses-j2ao.12.
"""

from __future__ import annotations

import datetime
import math

from tkcurses.xychart import CURSOR_EVENT, LEGEND_EVENT, XYChart
from uat import _support

TITLE = "53 - XYCharts"

#: Sixty points of each, never random, so two runs draw the same.
COUNT = 60


def wave(base, size, period, phase=0.0):
    """The value at point ``n`` of a sine wave."""
    return lambda n: round(
        base + size * math.sin(2 * math.pi * (n + phase) / period), 2
    )


def gappy(value):
    """``value`` with some missing: the first two, and in every sixty from
    the start one alone and four together, then the last - every case
    ``missing`` and ``endvalues`` speak of."""
    return lambda n: (
        None if n in (0, 1) or n % COUNT in (17, 30, 31, 32, 33, 59) else value(n)
    )


#: Each data set: names, kinds, and the value at point n, for any n, so
#: the live feed carries on where the data left off.
SERIES = {
    "lines": (
        ("cpu", "line", wave(50, 30, 20)),
        ("load", "line", gappy(wave(35, 10, 33, 5))),
        # Below load, so the two cross rather than run together: where
        # two lines share a pixel only the later one shows.
        ("disk", "line", wave(14, 10, 140, -35)),
    ),
    "areas": (
        ("web", "area", wave(20, 8, 25)),
        ("db", "area", gappy(wave(12, 6, 15, 3))),
        ("cache", "area", lambda n: 6 + (n % 10)),
    ),
}
SERIES["times"] = SERIES["lines"]

#: The first minute of the times data: a fixed day, local time.
START = datetime.datetime(2026, 11, 23, 23, 30)


#: In the times data, the readings after this one come after an outage.
OUTAGE_AFTER = 27
#: How long the outage is: the minutes with no reading at all.
OUTAGE = datetime.timedelta(minutes=15)


def x_of(data, n):
    """Point n's x: n itself; or, for times, a reading a minute, with
    :data:`OUTAGE` missing after reading :data:`OUTAGE_AFTER`, so a time
    axis, spaced by the clock, is not spaced by the count."""
    if data != "times":
        return n
    at = START + datetime.timedelta(minutes=n)
    return at + OUTAGE if n > OUTAGE_AFTER else at


STACKS = ("stacked", "percentage", "unstacked")
INTERPOLATIONS = ("straight", "smooth", "step")
POINTS = ("auto", "show", "hide")
MISSING = ("hide", "zero", "linear", "last", "next")
ENDS = ("hide", "zero", "nearest")
SCALES = ("linear", "log", "sqrt")
BOUNDS = ("full", "data", "custom")
SIZES = (
    ("fill", None),
    ("50% x 50%", ("50%", "50%")),
    ("60 x 50%", (60, "50%")),
    ("width 30", (30, 0)),
)
DEPTHS = {0: "none", 8: "8", 16: "16", 256: "256", 1 << 24: "truecolor"}
#: The legend's statistics, by k.
STATS = ((), ("average", "max"), ("last", "min", "max", "average", "difference"))
#: The units, by u: none, after the number, before it.
UNITS = (("", "suffix"), ("%", "suffix"), ("$", "prefix"))
#: The legend, by j: each side, then hidden.
LEGENDS = (
    ("auto", "right"),
    ("auto", "bottom"),
    ("auto", "left"),
    ("auto", "top"),
    ("hide", "right"),
)


def fill(chart, name):
    """Replace every series with the data set ``name``."""
    chart.delete_series(*chart.series())
    for series, kind, value in SERIES[name]:
        chart.add_series(
            series, [(x_of(name, n), value(n)) for n in range(COUNT)], kind=kind
        )


def add_references(chart, data):
    """An alert line at 70, a normal band from 40 to 50 with its line at
    45, and a deploy marked down the chart at the 45th reading."""
    chart.reference_add(70, text="alert", color="red")
    chart.reference_add(45, text="normal", color="green", band=(40, 50))
    chart.reference_add(x_of(data, 45), text="deploy", axis="x")


def build(root, screen):
    area = _support.content_area(root, top=9)
    # Custom bounds take these: the lines' and areas' middles.
    chart = XYChart(area, minimum=20, maximum=60)
    chart.pack(fill="both", expand=True)
    chart.focus_set()
    state = {
        "data": "lines",
        "size": 0,
        "live": None,
        "next": COUNT,
        "note": None,
        "stats": 0,
        "units": 0,
        "legend": 0,
        "cursors": 0,
    }
    fill(chart, state["data"])

    def report():
        colors = root.tk.colors
        depth = int(colors.depth) if colors is not None and colors.has_colors else 0
        second = chart.series()[1]
        hidden = chart.series_cget(second, "hidden")
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            "n: data  s: stack  i: interpolation  p: points  m: missing"
            "  e: ends  d: dotted",
        )
        screen.line(
            2, "c: scale  b: bounds  f: nice  h: hide 2nd  l: live  x: note  z: size"
        )
        screen.line(
            3,
            "a: titles  g: grid  t: ticks  r: refs  u: units  k: stats"
            "  j: legend  o: readout",
        )
        screen.line(
            4,
            "Left Right Home End, click: crosshair   Up Down Space, click: legend",
        )
        screen.line(
            5,
            f"colours {DEPTHS.get(depth, depth)}  data={state['data']}"
            f"  {second} {'hidden' if hidden else 'shown'}"
            f"  live={'on' if state['live'] else 'off'}"
            f"  note={'on' if state['note'] else 'off'}"
            f"  size: {SIZES[state['size']][0]}",
        )
        screen.line(
            6,
            f"stack={chart.cget('stackmode')}"
            f" interp={chart.cget('interpolation')}"
            f" missing={chart.cget('missing')} ends={chart.cget('endvalues')}"
            f" dotted={int(chart.cget('dottedgaps'))}",
        )
        screen.line(
            7,
            f"points={chart.cget('points')} scale={chart.cget('scaletype')}"
            f" bounds={chart.cget('bounds')} nice={int(chart.cget('nicebounds'))}"
            f" grid={int(chart.cget('gridlines'))}"
            f" ticks={int(chart.cget('ticklabels'))}"
            f" titles={int(bool(chart.cget('xlabel')))}",
        )
        legend, side = chart.cget("legend"), chart.cget("legendposition")
        at = chart.cursor()
        if isinstance(at, datetime.datetime):
            at = at.strftime("%H:%M")
        elif at is not None:
            at = f"{at:g}"
        screen.line(
            8,
            f"legend={'hide' if legend == 'hide' else side}"
            f"  stats={len(chart.cget('legendstats'))}"
            f"  units={chart.cget('units') or '-'}"
            f"  refs={'on' if chart.references() else 'off'}"
            f"  readout={int(chart.cget('readout'))}"
            f"  cursor={'-' if at is None else at} ({state['cursors']} sent)",
        )
        screen.footer(" Escape quits, once the crosshair and the underline are gone ")
        screen.refresh()

    def step(option, choices):
        now = str(chart.cget(option))
        chart.configure(**{option: choices[(choices.index(now) + 1) % len(choices)]})
        report()

    def toggle(option):
        chart.configure(**{option: not chart.cget(option)})
        report()

    def data():
        names = tuple(SERIES)
        state["data"] = names[(names.index(state["data"]) + 1) % len(names)]
        fill(chart, state["data"])
        state["next"] = COUNT
        if chart.references():
            # The deploy line is at an x of the old data: put it again.
            chart.reference_delete(*chart.references())
            add_references(chart, state["data"])
        report()

    def titles():
        on = not chart.cget("xlabel")
        chart.configure(xlabel="reading" if on else "", ylabel="value" if on else "")
        report()

    def references():
        if chart.references():
            chart.reference_delete(*chart.references())
        else:
            add_references(chart, state["data"])
        report()

    def cycle(name, choices, apply):
        state[name] = (state[name] + 1) % len(choices)
        apply(choices[state[name]])
        report()

    def counted(_event):
        state["cursors"] += 1
        report()

    def hide():
        second = chart.series()[1]
        chart.series_configure(second, hidden=not chart.series_cget(second, "hidden"))
        report()

    def feed():
        """One more point on every series, the oldest dropped: what a
        program's own timer does to show live data."""
        n = state["next"]
        state["next"] += 1
        for series, _kind, value in SERIES[state["data"]]:
            points = chart.series_points(series)
            chart.set_series(series, [*points[1:], (x_of(state["data"], n), value(n))])
        state["live"] = root.after(200, feed)

    def live():
        if state["live"]:
            root.after_cancel(state["live"])
            state["live"] = None
        else:
            feed()
        report()

    def note():
        if state["note"]:
            chart.delete(state["note"])
            state["note"] = None
        else:
            state["note"] = chart.create_text(
                4, 4, text=" a note of the program's own ", anchor="nw", fill="white"
            )
        report()

    def size():
        state["size"] = (state["size"] + 1) % len(SIZES)
        given = SIZES[state["size"]][1]
        chart.pack_forget()
        if given is None:
            chart.configure(width=0, height=0)
            chart.pack(fill="both", expand=True)
        else:
            chart.configure(width=given[0], height=given[1])
            chart.pack(anchor="nw")
        report()

    root.bind_all("n", lambda _event: data())
    root.bind_all("s", lambda _event: step("stackmode", STACKS))
    root.bind_all("i", lambda _event: step("interpolation", INTERPOLATIONS))
    root.bind_all("p", lambda _event: step("points", POINTS))
    root.bind_all("m", lambda _event: step("missing", MISSING))
    root.bind_all("e", lambda _event: step("endvalues", ENDS))
    root.bind_all("d", lambda _event: toggle("dottedgaps"))
    root.bind_all("c", lambda _event: step("scaletype", SCALES))
    root.bind_all("b", lambda _event: step("bounds", BOUNDS))
    root.bind_all("f", lambda _event: toggle("nicebounds"))
    root.bind_all("h", lambda _event: hide())
    root.bind_all("l", lambda _event: live())
    root.bind_all("x", lambda _event: note())
    root.bind_all("z", lambda _event: size())
    root.bind_all("a", lambda _event: titles())
    root.bind_all("g", lambda _event: toggle("gridlines"))
    root.bind_all("t", lambda _event: toggle("ticklabels"))
    root.bind_all("r", lambda _event: references())
    root.bind_all("o", lambda _event: toggle("readout"))
    root.bind_all(
        "u",
        lambda _event: cycle(
            "units", UNITS, lambda u: chart.configure(units=u[0], unitplacement=u[1])
        ),
    )
    root.bind_all(
        "k",
        lambda _event: cycle(
            "stats", STATS, lambda wanted: chart.configure(legendstats=wanted)
        ),
    )
    root.bind_all(
        "j",
        lambda _event: cycle(
            "legend",
            LEGENDS,
            lambda pair: chart.configure(legend=pair[0], legendposition=pair[1]),
        ),
    )
    chart.bind(CURSOR_EVENT, counted)
    # A series hidden or shown from the legend: line 5 says which.
    chart.bind(LEGEND_EVENT, lambda _event: report())
    # A resize changes what a percentage asks for: show the size it got.
    root.bind(
        "<Configure>",
        lambda event: root.after_idle(report) if event.widget is root else None,
        add="+",
    )
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
