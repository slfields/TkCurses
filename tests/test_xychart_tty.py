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

"""XYChart on a real terminal: what the screen actually shows.

Every test waits for each cell it asserts on, in one predicate, so a frame
caught half drawn is waited out rather than asserted on.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

# Twelve pixels tall: the area, at 1, reaches the top pixel, and the line,
# at 0.5, is the upper half of row 3. Each program ends itself.
PROGRAM = """
import tkcurses as tk
from tkcurses.xychart import XYChart

root = tk.Tk()
chart = XYChart(root{options})
chart.pack(fill="both", expand=True)
chart.add_series("a", [(0, 1), (10, 1)], kind="area")
chart.add_series("b", [(0, 0.5), (10, 0.5)])
{body}
root.after(8000, root.destroy)
root.mainloop()
"""


def run(terminal, body="", *, options="", term="xterm-256color", cols=20):
    screen = terminal(cols=cols, rows=6, env={"TERM": term})
    screen.run_source(PROGRAM.format(body=body, options=options))
    return screen


def colours(cell):
    return (cell.fg, cell.bg)


def test_a_line_is_drawn_over_a_dimmed_area(terminal):
    term = run(terminal)

    def drawn(t):
        top, fill, line = t.char_at(0, 5), t.char_at(1, 5), t.char_at(3, 5)
        dim = fill.fg
        return (
            (top.data, top.fg) == ("▀", "green")
            and top.bg == dim
            and fill.data == "█"
            and dim not in ("green", "default", "black")
            and (line.data, line.fg, line.bg) == ("▀", "red", dim)
            and all(
                colours(t.char_at(row, 19)) == (dim, "black") for row in (1, 2, 4, 5)
            )
        )

    term.wait_for(drawn, message="green over a dimmed fill, red across it")


def test_below_256_colours_an_area_is_its_lines_colour(terminal):
    term = run(terminal, term="xterm")

    def drawn(t):
        return all(
            colours(t.char_at(row, 5)) == ("green", "black") for row in (0, 1, 5)
        ) and colours(t.char_at(3, 5)) == ("red", "green")

    term.wait_for(drawn, message="the area in green itself")


def test_a_change_is_drawn(terminal):
    term = run(
        terminal, "root.after(300, lambda: chart.set_series('b', [(0, 0), (10, 0)]))"
    )

    def moved(t):
        bottom, middle = t.char_at(5, 5), t.char_at(3, 5)
        # The fill is the top half, the line the bottom: drawn as ▀.
        return (
            bottom.data == "▀"
            and bottom.bg == "red"
            and middle.data == "█"
            and "red" not in colours(middle)
        )

    term.wait_for(moved, message="the line moved to zero, the bottom pixel")


def test_the_programs_own_items_are_drawn_over_the_chart(terminal):
    term = run(terminal, 'chart.create_text(5, 6, text="HI", anchor="w")')

    def drawn(t):
        return t.text_at(3, 5, 2) == "HI" and t.char_at(3, 8).fg == "red"

    term.wait_for(drawn, message="HI on the line, the line either side")


def test_a_share_of_the_screen_follows_the_terminal(terminal):
    # Packed to keep its width: fill="both" would give it the whole row.
    body = 'chart.pack_configure(side="left", fill="y", expand=False)'
    term = run(terminal, body, options=', width="50%"', cols=20)
    term.wait_for(
        lambda t: t.char_at(1, 9).data == "█" and t.char_at(1, 10).data == " ",
        message="half of 20",
    )
    term.resize(40, 6)
    term.wait_for(
        lambda t: t.char_at(1, 19).data == "█" and t.char_at(1, 20).data == " ",
        message="half of 40",
    )
