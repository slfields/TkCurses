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

"""Meters: bar graphs that follow live values.

A TkCurses widget: neither tkinter nor Tk has a bar graph. The numbers are
made up from the clock, so the program runs anywhere: four cores whose
load rises and falls, and a request rate that bursts now and then.

The cores' graph asks for its values itself, through ``source``, every
``refreshinterval``; the history graph is given each new value with
``set_all``. A core turns yellow above 70% and red above 90%, and the
mark beyond its bar is the highest it reached in the last two seconds.
The request graph shows the last three seconds, and its scale follows
the values: it grows the moment a burst arrives, and once the burst has
left the graph shrinks back a step at a time, each after the values have
stayed under it for a second and a half.
"""

import math
import time

import tkcurses as tk
from tkcurses.bargraph import BarGraph

START = time.monotonic()
HISTORY = 12


def cores() -> list[list[float]]:
    """Each core's load, in percent: a slow wave, out of step with the
    next core's."""
    now = time.monotonic() - START
    return [[50 + 48 * math.sin(now * 1.3 + core * 1.7)] for core in range(4)]


def requests() -> float:
    """Requests a second: about forty, and five times that for a second
    and a half in every ten."""
    now = time.monotonic() - START
    burst = 5 if now % 10 > 8.5 else 1
    return burst * (40 + 10 * math.sin(now * 3))


root = tk.Tk()
root.title("Meters")
load = BarGraph(
    root,
    orient="horizontal",
    segments=4,
    labels=[f"cpu{n}" for n in range(4)],
    maximum=100,
    thresholds=[(70, "yellow"), (90, "red")],
    peakholdtime=2000,
    readout=True,
    units="%",
    digits=2,
    source=cores,
    refreshinterval=200,
    label="Load",
    borderwidth=1,
)
load.pack(fill="x", padx=1)
rate = BarGraph(
    root,
    segments=HISTORY,
    maximum="auto",
    autoscaledelay=1500,
    axis=True,
    units="/s",
    digits=3,
    thickness=3,
    gap=0,
    colors=["cyan"],
    label="Requests",
    borderwidth=1,
)
rate.pack(fill="both", expand=True, padx=1)
history = [0.0] * HISTORY


def tick() -> None:
    history.append(requests())
    del history[0]
    rate.set_all([[value] for value in history])
    root.after(250, tick)


tick()
root.mainloop()
