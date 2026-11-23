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

"""XYCharts: lines and areas, stacking, joining, gaps, scales and size.

What to do, pass 1: n steps the data through lines, areas and times; s
steps stackmode, i interpolation, p points, m missing, e endvalues, d
dottedgaps, c scaletype, b bounds, f nicebounds; h hides and shows the
second series; l starts and stops a live feed, one point every 200 ms
from the program's own timer; x draws a note of the program's own on
the chart; z steps the size through filling the area, 50% by 50% of
the screen, 60 columns by 50%, and 30 columns alone. Run it again under
TERM=xterm and TERM=vt100.

What to look for: **lines are unbroken and joined where they should
be**, areas fill to zero or to the area beneath in a dimmer shade and
never hide a line, the gaps in the data show as the missing option
says, the note stays on top, the live feed draws smoothly, and a
percentage size follows the terminal when it is resized.
TkCurses-j2ao.7.
"""

from __future__ import annotations

import datetime
import math

from tkcurses.xychart import XYChart
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
        ("disk", "line", wave(30, 22, 140, -35)),
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


def x_of(data, n):
    """Point n's x: n itself, or a minute after START for each."""
    return START + datetime.timedelta(minutes=n) if data == "times" else n


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


def fill(chart, name):
    """Replace every series with the data set ``name``."""
    chart.delete_series(*chart.series())
    for series, kind, value in SERIES[name]:
        chart.add_series(
            series, [(x_of(name, n), value(n)) for n in range(COUNT)], kind=kind
        )


def build(root, screen):
    area = _support.content_area(root, top=7)
    # Custom bounds take these: the lines' and areas' middles.
    chart = XYChart(area, minimum=20, maximum=60)
    chart.pack(fill="both", expand=True)
    state = {"data": "lines", "size": 0, "live": None, "next": COUNT, "note": None}
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
            f"colours {DEPTHS.get(depth, depth)}   data={state['data']}"
            f"   {second} {'hidden' if hidden else 'shown'}"
            f"   live={'on' if state['live'] else 'off'}"
            f"   note={'on' if state['note'] else 'off'}",
        )
        screen.line(
            4,
            f"stackmode={chart.cget('stackmode')}"
            f" interpolation={chart.cget('interpolation')}"
            f" points={chart.cget('points')}",
        )
        screen.line(
            5,
            f"missing={chart.cget('missing')} endvalues={chart.cget('endvalues')}"
            f" dottedgaps={int(chart.cget('dottedgaps'))}",
        )
        screen.line(
            6,
            f"scaletype={chart.cget('scaletype')} bounds={chart.cget('bounds')}"
            f" nicebounds={int(chart.cget('nicebounds'))}"
            f"   size: {SIZES[state['size']][0]}",
        )
        screen.footer(" Escape quits ")
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
    # A resize changes what a percentage asks for: show the size it got.
    root.bind(
        "<Configure>",
        lambda event: root.after_idle(report) if event.widget is root else None,
        add="+",
    )
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
