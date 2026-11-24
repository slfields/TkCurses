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

"""Crosshair: a day of weather on two charts, and the widgets around
them following the crosshair.

A TkCurses widget: neither tkinter nor Tk has a chart. A chart sends
<<XYChartCursor>> whenever its crosshair moves or goes, and cursor()
says where it is. One handler, bound on the window rather than on
either chart, hears both charts and keeps everything else in step: the
other chart's crosshair, the readings panel at the right, and the hour
on the scale below. The scale works the other way too: drag it, or
click it and use the arrows, and both crosshairs move.

The left and right arrows move the crosshair of the chart with the
focus, Home and End to the ends, and Escape takes it away; a click on
a chart puts it there. Tab moves the focus from one widget to the next.
"""

import datetime
import math

import tkcurses as tk
from tkcurses.xychart import CURSOR_EVENT, XYChart

#: A reading every hour of one day.
DAY = datetime.datetime(2026, 11, 23)
HOURS = [DAY + datetime.timedelta(hours=n) for n in range(24)]


def daylight(n: int) -> float:
    """0 at four in the morning, 1 at four in the afternoon."""
    return (1 - math.cos(2 * math.pi * (n - 4) / 24)) / 2


OUTDOOR = [round(3 + 9 * daylight(n), 1) for n in range(24)]
# The heating comes on at six and goes off at eleven at night.
INDOOR = [round(21.0 if 6 <= n < 23 else 17 + 0.3 * daylight(n), 1) for n in range(24)]
HUMIDITY = [round(88 - 30 * daylight(n), 1) for n in range(24)]

root = tk.Tk()
root.title("Crosshair")
tk.Label(root, anchor="w", text="Tab: next widget  arrows: move  ^C: quit").pack(
    side="bottom", fill="x"
)
hour = tk.Scale(root, from_=0, to=23, orient="horizontal", label="hour")
hour.pack(side="bottom", fill="x")

# As wide as its widest line, whatever it says: the charts keep their width.
panel = tk.Frame(root, width=17)
panel.pack(side="right", fill="y")
panel.pack_propagate(False)
heading = tk.Label(panel, anchor="w")
heading.pack(fill="x")
readings = {
    name: tk.Label(panel, anchor="w") for name in ("outdoor", "indoor", "humidity")
}
for label in readings.values():
    label.pack(fill="x")


def chart(units: str, label: str) -> XYChart:
    """One of the two charts, boxed and labelled, with no legend or
    readout of its own: the panel says what they would."""
    made = XYChart(
        root,
        units=units,
        legend="hide",
        readout=False,
        borderwidth=1,
        label=label,
        height=8,  # each asks for the same, so they share the height
    )
    made.pack(fill="both", expand=True)
    return made


temperature = chart("°C", "Temperature")
temperature.add_series("outdoor", list(zip(HOURS, OUTDOOR, strict=True)))
temperature.add_series("indoor", list(zip(HOURS, INDOOR, strict=True)), color="red")
humidity = chart("%", "Humidity")
humidity.add_series("humidity", list(zip(HOURS, HUMIDITY, strict=True)), color="blue")
CHARTS = (temperature, humidity)


def show(at: datetime.datetime | None) -> None:
    """The panel: each reading at the crosshair, or none."""
    heading.configure(text="no crosshair" if at is None else f"at {at:%H:%M}")
    for each in CHARTS:
        unit = each.cget("units")
        for name in each.series():
            value = None if at is None else dict(each.series_points(name)).get(at)
            text = f"{name:<9}" + ("-" if value is None else f"{value:5.1f}{unit}")
            readings[name].configure(text=text)


def follow(event: tk.Event) -> None:
    """Either chart's crosshair moved: bring everything else to it.

    Moving the other chart's crosshair sends that chart's own event,
    which comes back here and moves this chart's to where it already
    is. A chart sends its event only when its crosshair actually moves,
    so that sends nothing, and the two never chase each other.
    """
    at = event.widget.cursor()
    for each in CHARTS:
        if each is not event.widget:
            each.cursor(at)
    show(at)
    if at is not None:
        # Scale.set calls the command below only if the hour changes.
        hour.set(at.hour)


def moved(value: str) -> None:
    """The scale moved: put the crosshairs at its hour."""
    temperature.cursor(HOURS[int(float(value))])  # follow does the rest


# On the window, not a chart: a chart's event passes through its
# toplevel's bindings too, so this one binding hears both charts.
root.bind(CURSOR_EVENT, follow)
hour.configure(command=moved)
temperature.focus_set()
show(None)
root.mainloop()
