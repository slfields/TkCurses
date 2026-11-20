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

"""Bar graphs: eighths of a cell, colours, labels and a resize.

What to do: step the left bar with Up and Down, an eighth of a cell a
press; switch the middle graph between stacked and overlay with m, and
the right one between solid and gradient with g; make the terminal
narrower and wider.

What to look for: **each press moves the bar's tip by one eighth**, the
colours change at the threshold levels, the labels sit centred under
their bars in your font, and the middle graph follows the terminal's
size. TkCurses-5r79.8.
"""

from __future__ import annotations

from tkcurses.bargraph import BarGraph
from uat import _support

TITLE = "51 - Bar graphs"


def build(root, screen):
    area = _support.content_area(root, top=5)
    for column, weight in ((0, 0), (1, 1), (2, 1)):
        area.columnconfigure(column, weight=weight)
    area.rowconfigure(0, weight=1)
    state = {"value": 13}

    # Eight cells of 8 points each, and a maximum of 64: one value is one
    # eighth of a cell.
    steps = BarGraph(
        area,
        scale=64,
        maximum=64,
        thresholds=[(48, "yellow"), (56, "red")],
        thickness=4,
        baseline=True,
        label="Steps",
        borderwidth=1,
    )
    steps.grid(row=0, column=0, sticky="n", padx=1)
    series = BarGraph(
        area,
        segments=3,
        series=3,
        colors=["green", "yellow", "cyan"],
        maximum=100,
        labels=["東京", "Café", "plain"],
        label="Series",
        borderwidth=1,
    )
    series.grid(row=0, column=1, sticky="nsew", padx=1)
    series.set_all([[40, 30, 20], [20, 45, 15], [55, 10, 25]])
    shades = BarGraph(
        area,
        orient="horizontal",
        segments=3,
        colors=["red", "green", "blue"],
        series=1,
        maximum=100,
        readout=True,
        units="%",
        labels=["low", "mid", "full"],
        label="Shades",
        borderwidth=1,
    )
    shades.grid(row=0, column=2, sticky="new", padx=1)
    shades.set_all([[30], [65], [100]])

    def report():
        value = state["value"]
        whole, eighths = divmod(value, 8)
        screen.line(0, f" {TITLE} ")
        screen.line(1, "Up/Down: step Steps by 1/8   m: stack/overlay   g: gradient")
        screen.line(
            2,
            f"Steps: {value} of 64 = {whole} cell{'' if whole == 1 else 's'} and"
            f" {eighths}/8; yellow from"
            " 48, red from 56",
        )
        screen.line(
            3,
            f"Series: {series.cget('mode')}   Shades: {shades.cget('colormode')}"
            "   Resize: Series follows",
        )
        screen.footer(" Escape quits ")
        screen.refresh()

    def step(by):
        state["value"] = max(0, min(64, state["value"] + by))
        steps.set(0, [state["value"]])
        report()
        return "break"

    def toggle(graph, option, one, other):
        graph.configure(**{option: other if graph.cget(option) == one else one})
        report()

    steps.set(0, [state["value"]])
    root.bind_all("<Up>", lambda _event: step(1))
    root.bind_all("<Down>", lambda _event: step(-1))
    root.bind_all("m", lambda _event: toggle(series, "mode", "stacked", "overlay"))
    root.bind_all("g", lambda _event: toggle(shades, "colormode", "solid", "gradient"))
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
