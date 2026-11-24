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

"""Traffic: requests a second to three services, as stacked areas that
move along as new seconds come in, in a box labelled with what they are.

A TkCurses widget: neither tkinter nor Tk has a chart. The chart fetches
its own data: source is a function it calls every refreshinterval, and
each call is one more second, the oldest dropped. Press r to step how
often - every half second, every two, every quarter - and p to pause,
which takes the source away, and again to carry on. s steps the areas
through stacked, percentage and unstacked; a click on the legend hides
or shows a service.
"""

import math

import tkcurses as tk
from tkcurses.xychart import XYChart

#: How many seconds the chart keeps.
KEEP = 60
#: How often the chart asks for data, in milliseconds, stepped by r.
RATES = (500, 2000, 250)
SERVICES = {
    "web": lambda t: 40 + 15 * math.sin(t / 7),
    "api": lambda t: 25 + 10 * math.sin(t / 11 + 2),
    "search": lambda t: 10 + 8 * max(0.0, math.sin(t / 5)),
}
clock = {"now": KEEP - 1}


def last_minute() -> dict[str, list[tuple[int, float]]]:
    """Each service's last KEEP seconds."""
    now = clock["now"]
    return {
        name: [(t, round(rate(t), 1)) for t in range(now - KEEP + 1, now + 1)]
        for name, rate in SERVICES.items()
    }


def readings() -> dict[str, list[tuple[int, float]]]:
    """The chart's source: one second on, then the last minute."""
    clock["now"] += 1
    return last_minute()


root = tk.Tk()
root.title("Traffic")
status = tk.Label(root, anchor="w")
status.pack(side="bottom", fill="x")
chart = XYChart(
    root,
    units="/s",
    xlabel="seconds",
    legendstats=("last",),
    borderwidth=1,
    label="Requests a second",
    refreshinterval=RATES[0],
    source=readings,
)
chart.pack(fill="both", expand=True)
for name, points in last_minute().items():
    chart.add_series(name, points, kind="area")


def show() -> None:
    paused = not chart.cget("source")
    every = "paused" if paused else f"every {chart.cget('refreshinterval')}ms"
    status.configure(
        text=f"{chart.cget('stackmode')}  {every}  s: stack  r: rate  p: pause"
    )


def step() -> None:
    modes = ("stacked", "percentage", "unstacked")
    now = modes.index(str(chart.cget("stackmode")))
    chart.configure(stackmode=modes[(now + 1) % len(modes)])
    show()


def rate() -> None:
    now = RATES.index(int(chart.cget("refreshinterval")))
    chart.configure(refreshinterval=RATES[(now + 1) % len(RATES)])
    show()


def pause() -> None:
    # "" takes the source away: None given to configure is ignored.
    chart.configure(source="" if chart.cget("source") else readings)
    show()


root.bind("s", lambda _event: step())
root.bind("r", lambda _event: rate())
root.bind("p", lambda _event: pause())
show()
root.mainloop()
