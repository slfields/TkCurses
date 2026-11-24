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

"""Sensors: two thermometers that sometimes fail to report, and the ways
a chart can draw what is missing.

A TkCurses widget: neither tkinter nor Tk has a chart. A reading that
did not arrive is None. Press m to step how the gaps are drawn - left
as gaps, as zero, joined straight, held at the last reading or taken
from the next - and d to dot whatever was filled in, so it is not taken
for a reading. The legend counts the values each line draws: the
readings the sensor sent, and, once m fills the gaps, those too.
"""

import math

import tkcurses as tk
from tkcurses.xychart import XYChart

#: The hours each sensor sent nothing.
LOST = {"indoor": {7, 8, 9, 30}, "outdoor": {0, 15, 16, 17, 18, 19, 40, 47}}


def indoor(hour: int) -> float:
    return round(20 + 1.5 * math.sin(math.pi * (hour - 9) / 12), 1)


def outdoor(hour: int) -> float:
    return round(8 + 6 * math.sin(math.pi * (hour - 9) / 12), 1)


root = tk.Tk()
root.title("Sensors")
status = tk.Label(root, anchor="w")
status.pack(side="bottom", fill="x")
chart = XYChart(
    root,
    units="\N{DEGREE SIGN}C",
    unitspace=False,
    bounds="data",
    xlabel="hours",
    legendstats=("count",),
    legendposition="bottom",
)
chart.pack(fill="both", expand=True)
for name, reading in (("indoor", indoor), ("outdoor", outdoor)):
    chart.add_series(
        name, [(h, None if h in LOST[name] else reading(h)) for h in range(48)]
    )


def show() -> None:
    status.configure(
        text=f"missing={chart.cget('missing')} dotted={int(chart.cget('dottedgaps'))}"
        "  m: missing  d: dotted  ^C: quit"
    )


def step() -> None:
    rules = ("hide", "zero", "linear", "last", "next")
    now = rules.index(str(chart.cget("missing")))
    chart.configure(missing=rules[(now + 1) % len(rules)])
    show()


def dot() -> None:
    chart.configure(dottedgaps=not chart.cget("dottedgaps"))
    show()


root.bind("m", lambda _event: step())
root.bind("d", lambda _event: dot())
show()
root.mainloop()
