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
move along as new seconds come in.

A TkCurses widget: neither tkinter nor Tk has a chart. Every half second
the program adds a reading to each service with append and drops the
oldest; the chart draws once for all three. Press s to step the areas
through stacked, percentage and unstacked, and click the legend to hide
or show a service.
"""

import math

import tkcurses as tk
from tkcurses.xychart import XYChart

#: How many seconds the chart keeps.
KEEP = 60
SERVICES = {
    "web": lambda t: 40 + 15 * math.sin(t / 7),
    "api": lambda t: 25 + 10 * math.sin(t / 11 + 2),
    "search": lambda t: 10 + 8 * max(0.0, math.sin(t / 5)),
}

root = tk.Tk()
root.title("Traffic")
status = tk.Label(root, anchor="w")
status.pack(side="bottom", fill="x")
chart = XYChart(root, units="/s", xlabel="seconds", legendstats=("last",))
chart.pack(fill="both", expand=True)
for name, rate in SERVICES.items():
    chart.add_series(name, [(t, round(rate(t), 1)) for t in range(KEEP)], kind="area")
clock = {"now": KEEP}


def tick() -> None:
    """One more second on every service, the oldest dropped."""
    now = clock["now"]
    clock["now"] += 1
    for name, rate in SERVICES.items():
        chart.append(name, (now, round(rate(now), 1)))
        chart.set_series(name, chart.series_points(name)[-KEEP:])
    root.after(500, tick)


def show() -> None:
    status.configure(text=f"{chart.cget('stackmode')}  s: stacking  ^C: quit")


def step() -> None:
    modes = ("stacked", "percentage", "unstacked")
    now = modes.index(str(chart.cget("stackmode")))
    chart.configure(stackmode=modes[(now + 1) % len(modes)])
    show()


root.bind("s", lambda _event: step())
show()
root.after(500, tick)
root.mainloop()
