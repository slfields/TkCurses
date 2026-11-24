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

# No readout or legend, which have tests of their own below: eight rows
# are then six of plot, twelve pixels tall, then the x axis and its
# labels. The value axis's labels, 0, 0.5 and 1, and its line take
# columns 0 to 3, so the plot is columns 4 to 19. The area, at 1, reaches the top
# pixel, and the line, at 0.5, is the upper half of row 3. Each program
# ends itself.
PROGRAM = """
import tkcurses as tk
from tkcurses.xychart import XYChart

root = tk.Tk()
chart = XYChart(root, readout=False, legend="hide"{options})
chart.pack(fill="both", expand=True)
chart.add_series("a", [(0, 1), (10, 1)], kind="area")
chart.add_series("b", [(0, 0.5), (10, 0.5)])
{body}
root.after(8000, root.destroy)
root.mainloop()
"""


def run(terminal, body="", *, options="", term="xterm-256color", cols=20):
    screen = terminal(cols=cols, rows=8, env={"TERM": term})
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
    # Ten columns is too narrow for a plot with axes, so it is all plot;
    # at twenty the axes are back, and the plot still ends at column 19.
    body = 'chart.pack_configure(side="left", fill="y", expand=False)'
    term = run(terminal, body, options=', width="50%"', cols=20)
    term.wait_for(
        lambda t: t.char_at(1, 9).data == "█" and t.char_at(1, 10).data == " ",
        message="half of 20",
    )
    term.resize(40, 8)
    term.wait_for(
        lambda t: t.char_at(1, 19).data == "█" and t.char_at(1, 20).data == " ",
        message="half of 40",
    )


def test_the_axes_are_drawn_beside_and_under_the_plot(terminal):
    term = run(terminal)

    def drawn(t):
        return (
            t.text_at(0, 0, 4) == "  1┤"
            and t.text_at(3, 0, 4) == "0.5┤"
            and t.text_at(5, 0, 4) == "  0┤"
            and t.text_at(6, 3, 2) == "└┬"
            and t.char_at(7, 4).data == "0"
            and t.text_at(7, 18, 2) == "10"
        )

    term.wait_for(drawn, message="0 to 1 up the left, 0 to 10 along the bottom")


# Two lines, with the legend and the readout: 40 by 10.
LIVE = """
import tkcurses as tk
from tkcurses.xychart import XYChart

root = tk.Tk()
chart = XYChart(root)
chart.pack(fill="both", expand=True)
chart.add_series("up", [(t, t) for t in range(10)])
chart.add_series("down", [(t, 9 - t) for t in range(10)])
chart.focus_set()
{body}
root.after(8000, root.destroy)
root.mainloop()
"""


def run_live(terminal, body=""):
    screen = terminal(cols=40, rows=10, env={"TERM": "xterm-256color"})
    screen.run_source(LIVE.format(body=body))
    return screen


def test_the_keys_move_the_crosshair_and_the_readout_follows(terminal):
    term = run_live(terminal)
    term.wait_for(lambda t: t.row(9).startswith("0 \u2013 9"), message="the range")
    term.send_keys("<Right>")
    term.wait_for(
        lambda t: (
            t.row(9).startswith("0  up 0  down 9")
            and t.char_at(9, 3).fg == "green"
            and t.char_at(9, 9).fg == "red"
        ),
        message="the crosshair at 0, each value in its colour",
    )
    term.send_keys("<End>")
    term.wait_for(lambda t: t.row(9).startswith("9  up 9  down 0"), message="at 9")
    term.send_keys("<Escape>")
    term.wait_for(lambda t: t.row(9).startswith("0 \u2013 9"), message="gone again")


def test_a_click_on_the_legend_hides_its_series(terminal):
    term = run_live(terminal)
    term.wait_for(lambda t: "██ down" in t.row(1), message="the legend")
    column = term.row(1).index("down")
    term.send_mouse(column, 1)
    term.wait_for(
        lambda t: "░░ down" in t.row(1) and t.char_at(1, column).fg != "red",
        message="down hidden: a hollow swatch",
    )


def click(term, column, row):
    """A press and its release, as a terminal reports a click."""
    term.send_mouse(column, row)
    term.send_mouse(column, row, action="release")


def test_a_series_hidden_last_can_be_shown_again(terminal):
    # Both hidden: the plot is empty but the legend stays to be clicked.
    term = run_live(terminal)
    term.wait_for(lambda t: "██ down" in t.row(1), message="the legend")
    up, down = term.row(0).index("up"), term.row(1).index("down")
    click(term, up, 0)
    term.wait_for(lambda t: "░░ up" in t.row(0), message="up hidden")
    click(term, down, 1)
    term.wait_for(
        lambda t: "░░ up" in t.row(0) and "░░ down" in t.row(1),
        message="both hidden, both entries still there",
    )
    click(term, up, 0)
    term.wait_for(
        lambda t: "██ up" in t.row(0) and t.contains("┤"),
        message="up shown again, with its axis",
    )


def test_a_box_alone_has_the_label_in_its_edge(terminal):
    term = run(terminal, options=', borderwidth=1, label="cpu"')

    def boxed(t):
        top, bottom = t.display[0], t.display[7]
        return (
            top.startswith("┌")
            and top.endswith("┐")
            and " cpu " in top
            and bottom.startswith("└")
            and bottom.endswith("┘")
            and all(t.display[row][0] == "│" for row in range(1, 7))
        )

    term.wait_for(boxed, message="a box with cpu in its top edge")


SOURCE = """
import tkcurses as tk
from tkcurses.xychart import XYChart

root = tk.Tk()
calls = []

def readings():
    calls.append(1)
    return {"a": [(0, 1), (len(calls) * 10, 2)]}

chart = XYChart(root, legend="hide", refreshinterval=50, source=readings)
chart.pack(fill="both", expand=True)
chart.add_series("a", [(0, 1)])
root.after(8000, root.destroy)
root.mainloop()
"""


def test_a_source_is_called_and_drawn_on_its_own(terminal):
    screen = terminal(cols=30, rows=8)
    screen.run_source(SOURCE)
    for reach in (10, 30):
        screen.wait_for(
            lambda t, reach=reach: any(
                t.display[7].startswith(f"0 \u2013 {n}  ")
                for n in range(reach, reach + 60, 10)
            ),
            message=f"the readout's range reaching {reach} or more",
        )
