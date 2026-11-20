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

"""Scales: what a bar graph can draw beside its bars, and how it writes
its numbers.

A TkCurses widget: neither tkinter nor Tk has a bar graph. Four graphs:

- response times on a log scale, written in the units a clock uses, with
  a red line at the half-second the service promises;
- disks, with each one's size in binary units read out beside its bar,
  turning yellow and red as it fills;
- a budget in dollars, with the axis on the ticks it names, gridlines and
  a baseline;
- temperatures shaded from cool to hot along each bar.
"""

import tkcurses as tk
from tkcurses.bargraph import BarGraph

GiB = 2**30

root = tk.Tk()
root.title("Scales")
root.columnconfigure((0, 1), weight=1, uniform="half")
root.rowconfigure((0, 1), weight=1, uniform="half")

latency = BarGraph(
    root,
    segments=4,
    labels=["p50", "p90", "p99", "max"],
    scaletype="log",
    minimum=1,
    maximum=100_000,
    units="ms",
    unitscale="time",
    axis=True,
    gridlines=True,
    markers=[(500, "red")],
    thickness=3,
    label="Response time",
    axislabel="log",
    borderwidth=1,
)
latency.grid(row=0, column=0, sticky="nsew")
latency.set_all([[12], [180], [1_400], [75_000]])

disks = BarGraph(
    root,
    orient="horizontal",
    segments=3,
    labels=["/", "/home", "/var"],
    maximum=512 * GiB,
    thresholds=[("80%", "yellow"), ("95%", "red")],
    colors=["green"],
    readout=True,
    units="B",
    unitspace=True,
    unitscale="binary",
    digits=3,
    label="Disks",
    borderwidth=1,
)
disks.grid(row=0, column=1, sticky="nsew")
disks.set_all([[210 * GiB], [440 * GiB], [500 * GiB]])

budget = BarGraph(
    root,
    segments=4,
    labels=["Jan", "Feb", "Mar", "Apr"],
    maximum=2_000,
    ticks=[0, 500, 1_000, 1_500, 2_000],
    units="$",
    unitplacement="prefix",
    digits=4,
    axis=True,
    gridlines=True,
    baseline=True,
    thickness=3,
    label="Budget",
    borderwidth=1,
)
budget.grid(row=1, column=0, sticky="nsew")
budget.set_all([[1_250], [800], [1_900], [1_475]])

heat = BarGraph(
    root,
    segments=5,
    labels=["Mon", "Tue", "Wed", "Thu", "Fri"],
    maximum=40,
    colormode="gradient",
    colors=["red"],
    gradientstart=["blue"],
    units="°C",
    readout=False,
    axis=True,
    thickness=2,
    label="Temperature",
    borderwidth=1,
)
heat.grid(row=1, column=1, sticky="nsew")
heat.set_all([[18], [24], [31], [37], [27]])

root.mainloop()
