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

"""Latency: a day of response times as lines against the clock, with
a target line, the hour after a deploy shaded, and a readout that
follows the crosshair, in a box with the chart's label in its edge.

A TkCurses widget: neither tkinter nor Tk has a chart. The left and
right arrows move the crosshair from reading to reading, Home and End
to the first and last, and Escape takes it away; a click on the chart
puts it at the nearest reading, and a click on the legend hides or
shows a line. Press r to take the references away and put them back.
"""

import datetime
import math

import tkcurses as tk
from tkcurses.xychart import CURSOR_EVENT, LEGEND_EVENT, XYChart

#: Readings every ten minutes through one day.
DAY = datetime.datetime(2026, 11, 23)
TIMES = [DAY + datetime.timedelta(minutes=10 * n) for n in range(144)]
#: The target the service is held to, and when a deploy went out.
TARGET = 250
DEPLOY = DAY + datetime.timedelta(hours=15, minutes=30)


def median(n: int) -> float:
    """Busier by day than by night - quietest at three in the morning,
    busiest at three in the afternoon - with a little ripple."""
    hour = n / 6
    day = (1 - math.cos(2 * math.pi * (hour - 3) / 24)) / 2
    return round(90 + 50 * day + 4 * math.sin(n / 3), 1)


def p95(n: int) -> float:
    """The slowest one in twenty: well above the median, and worse for
    an hour after the deploy."""
    after = TIMES[n] - DEPLOY
    slow = 120 if datetime.timedelta(0) <= after < datetime.timedelta(hours=1) else 0
    return round(2.1 * median(n) + slow, 1)


root = tk.Tk()
root.title("Latency")
status = tk.Label(root, anchor="w")
status.pack(side="bottom", fill="x")
chart = XYChart(
    root,
    units="ms",
    legendstats=("max",),
    legendposition="bottom",
    borderwidth=1,
    label=f"Response times, {DAY.day} {DAY:%B %Y}",
)
chart.pack(fill="both", expand=True)
chart.add_series("median", [(t, median(n)) for n, t in enumerate(TIMES)])
chart.add_series("p95", [(t, p95(n)) for n, t in enumerate(TIMES)], color="red")
chart.focus_set()


def references(on: bool) -> None:
    if on:
        chart.reference_add(TARGET, text="target", color="yellow")
        # A band on the x axis: the hour after the deploy, shaded.
        hour = DEPLOY + datetime.timedelta(hours=1)
        chart.reference_add(DEPLOY, text="deploy", axis="x", band=(DEPLOY, hour))
    else:
        chart.reference_delete(*chart.references())


def show(_event: object = None) -> None:
    """Say where the crosshair is, and whether p95 was over the target."""
    at = chart.cursor()
    if at is None:
        status.configure(text="arrows: crosshair  r: references  ^C: quit")
        return
    over = dict(chart.series_points("p95")).get(at)
    verdict = "over target" if over is not None and over > TARGET else "within target"
    status.configure(text=f"{at:%H:%M}  p95 {verdict}")


def hidden(_event: object = None) -> None:
    name = chart.legend_focus()
    state = "hidden" if chart.series_cget(name, "hidden") else "shown"
    status.configure(text=f"{name} {state}")


chart.bind(CURSOR_EVENT, show)
chart.bind(LEGEND_EVENT, hidden)
root.bind("r", lambda _event: references(not chart.references()))
references(True)
show()
root.mainloop()
