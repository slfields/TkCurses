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

"""BarGraph on a real terminal: what the screen actually shows.

Every test waits for each cell it asserts on, in one predicate, so a frame
caught half drawn is waited out rather than asserted on.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

# Each program ends itself, so a failing test cannot leave one behind.
PROGRAM = """
import tkcurses as tk
from tkcurses.bargraph import BarGraph

root = tk.Tk()
{body}
root.after(8000, root.destroy)
root.mainloop()
"""

FULL = "█"
YELLOW = ("yellow", "brown")  # pyte names ANSI yellow "brown"


def run(terminal, body, *, cols, rows, term=None):
    env = {"TERM": term} if term else None
    screen = terminal(cols=cols, rows=rows, env=env)
    screen.run_source(PROGRAM.format(body=body))
    return screen


def test_bars_box_and_label_on_screen(terminal):
    term = run(
        terminal,
        """
graph = BarGraph(root, segments=2, series=2, scale=16, maximum=16,
                 borderwidth=1, label="CPU", colors=["green", "red"],
                 refreshinterval=10)
graph.pack(side="top", anchor="nw")
graph.set_all([[8, 4], [5, 0]])
""",
        cols=30,
        rows=8,
    )

    def drawn(t):
        # The whole label, a space either side, in the box's top edge.
        # Segment 0: series 0 fills the bottom cell, series 1 half the next.
        # Segment 1: series 0 alone, 5 eighths. Colors are graph-wide.
        return (
            t.row(0).startswith("┌─ CPU ─┐")
            and t.text_at(2, 1, 3) == "█ ▅"
            and t.char_at(1, 1).data == "▄"
            and t.char_at(2, 1).fg == "green"
            and t.char_at(2, 3).fg == "green"
            and t.char_at(1, 1).fg == "red"
        )

    term.wait_for(drawn, message="the stacked bars in their box")


def test_a_percent_graph_follows_its_frame(terminal):
    term = run(
        terminal,
        """
graph = BarGraph(root, orient="horizontal", segments=1, maximum=100,
                 labels=["load"], readout=True, refreshinterval=10)
graph.pack(fill="x", side="top")
graph.set(0, [50])
""",
        cols=24,
        rows=10,
    )
    # Label (4 + space), readout (space + 3): 24 - 9 = 15 cells of bar,
    # half of it full: 7 cells and a half.
    term.wait_for(
        lambda t: (
            t.row(0).startswith("load " + FULL * 7 + "▌")
            and t.row(0).rstrip().endswith("50")
        ),
        message="half of the bar, and the readout",
    )


def test_source_is_polled_on_the_refresh_timer(terminal):
    term = run(
        terminal,
        """
values = iter([[2], [4], [6], [8]] + [[8]] * 1000)
graph = BarGraph(root, orient="horizontal", scale=8, maximum=8,
                 labels=["n"], refreshinterval=50, source=lambda: [next(values)])
graph.pack(side="top", anchor="nw")
""",
        cols=20,
        rows=6,
    )
    # 8 of 8: one full cell, reached only after several polls.
    term.wait_for_text("n " + FULL)


def test_a_percent_graph_lays_out_again_when_its_container_shrinks(terminal):
    term = run(
        terminal,
        """
box = tk.Frame(root, width=20, height=1)
box.pack_propagate(False)
box.pack(side="top", anchor="nw")
graph = BarGraph(box, orient="horizontal", maximum=100, refreshinterval=10)
graph.pack(fill="both", expand=True)
graph.set(0, [100])
root.after(600, lambda: box.configure(width=12))
""",
        cols=30,
        rows=6,
    )
    # Full scale follows the frame: 20 cells, then 12 after the shrink.
    term.wait_for(lambda t: t.row(0).rstrip() == FULL * 20, message="20 cells")
    term.wait_for(lambda t: t.row(0).rstrip() == FULL * 12, message="12 cells")


def test_peak_hold_marks_only_a_peak_above_the_bar(terminal):
    # Held 6, then the bar falls to 0.05 - less than an eighth of a cell, so
    # nothing is drawn - and the hold runs out. The peak goes down with the
    # bar and is level with it, so no stray mark shows at zero.
    term = run(
        terminal,
        """
graph = BarGraph(root, orient="horizontal", scale=80, maximum=10,
                 labels=["p"], peakholdtime=300, refreshinterval=20)
graph.pack(side="top", anchor="nw")
graph.set(0, [6])
root.after(200, lambda: graph.set(0, [0.05]))
""",
        cols=30,
        rows=4,
    )
    term.wait_for(
        lambda t: t.row(0).startswith("p ") and "│" in t.row(0),
        message="the held peak",
    )
    term.wait_for(lambda t: t.row(0).rstrip() == "p", message="an empty bar")
    # And it stays empty: the expired peak is not drawn again.
    term.wait_for_idle(0.5)
    assert term.row(0).rstrip() == "p"


def test_thresholds_recolor_the_top_of_a_stacked_bar(terminal):
    # 8 user + 6 system on a 16-point scale, threshold at 12: user green in
    # the bottom cell; the top cell is past 12, so the zone's yellow shows
    # at the tip whichever series is there.
    term = run(
        terminal,
        """
graph = BarGraph(root, series=2, scale=16, maximum=16, refreshinterval=10,
                 colors=["green", "cyan"], thresholds=[(12, "yellow")])
graph.pack(side="top", anchor="nw")
graph.set(0, [8, 6])
""",
        cols=20,
        rows=4,
    )
    term.wait_for(
        lambda t: (
            t.char_at(1, 0).data == FULL
            and t.char_at(1, 0).fg == "green"
            and t.char_at(0, 0).data == "▆"
            and t.char_at(0, 0).fg in YELLOW
        ),
        message="green below the level, yellow above it",
    )


GRADIENT = """
graph = BarGraph(root, segments=2, scale=64, maximum=100, colors=["red"],
                 colormode="gradient", refreshinterval=10, {extra})
graph.pack(side="top", anchor="nw")
graph.set_all({rows})
"""


def column(t, col, rows=8):
    """Foreground colors up one column, from the bottom row."""
    return [t.char_at(row, col).fg for row in reversed(range(rows))]


def full_column(t, col, rows=8):
    return all(t.char_at(row, col).data == FULL for row in range(rows))


def test_the_gradient_is_smooth_on_a_direct_color_terminal(terminal):
    term = run(
        terminal,
        GRADIENT.format(extra="", rows="[[100], [50]]"),
        cols=10,
        rows=10,
        term="xterm-direct",
    )

    def shaded(t):
        if not full_column(t, 0):
            return False
        full, half = column(t, 0), column(t, 2)
        reds = [int(color[:2], 16) for color in full if len(color) == 6]
        # 25 % of red at zero, red itself at the maximum, evenly between;
        # by position, not by value, so the half bar has the bottom shades.
        return (
            full[0] == "330000"
            and full[-1] == "cd0000"
            and len(reds) == 8
            and reds == sorted(reds)
            and len(set(reds)) == 8
            and half[:4] == full[:4]
        )

    term.wait_for(shaded, message="eight shades of red, darkest at the bottom")


def test_the_gradient_bands_at_256_colors(terminal):
    term = run(
        terminal,
        GRADIENT.format(extra="", rows="[[100], [0]]"),
        cols=10,
        rows=10,
        term="xterm-256color",
    )

    def banded(t):
        # Matched to the palette: a few bands, darkest at the bottom.
        shades = column(t, 0)
        return (
            full_column(t, 0)
            and shades[-1] == "red"
            and shades[0] != shades[-1]
            and 2 <= len(set(shades)) <= 6
        )

    term.wait_for(banded, message="a few bands of red")


def test_the_gradient_is_solid_below_256_colors(terminal):
    term = run(
        terminal,
        GRADIENT.format(extra="", rows="[[100], [0]]"),
        cols=10,
        rows=10,
        term="xterm",
    )
    term.wait_for(
        lambda t: full_column(t, 0) and set(column(t, 0)) == {"red"},
        message="solid red",
    )


def test_thresholds_win_over_the_gradient(terminal):
    term = run(
        terminal,
        GRADIENT.format(extra='thresholds=[("75%", "#ffff00")]', rows="[[100], [0]]"),
        cols=10,
        rows=10,
        term="xterm-direct",
    )

    def zoned(t):
        shades = column(t, 0)
        return (
            full_column(t, 0)
            and shades[0] == "330000"
            and shades[:6] == sorted(shades[:6])
            and shades[6:] == ["ffff00", "ffff00"]
        )

    term.wait_for(zoned, message="shaded red, yellow above 75%")


def test_a_held_peak_takes_the_shade_at_its_level(terminal):
    # Bar 0 peaks at 50 and drops away; bar 1 stays full as the reference.
    term = run(
        terminal,
        GRADIENT.format(extra="peakholdtime=5000", rows="[[50], [100]]")
        + "root.after(300, lambda: graph.set(0, [0]))\n",
        cols=10,
        rows=10,
        term="xterm-direct",
    )

    def peak_row(t):
        rows = [row for row in range(8) if t.char_at(row, 0).data not in " █"]
        return rows[0] if len(rows) == 1 else None

    def held(t):
        row = peak_row(t)
        if row is None or not full_column(t, 2):
            return False
        here, there = t.char_at(row, 0).fg, t.char_at(row, 2).fg
        return here == there and here not in ("cd0000", "330000")

    term.wait_for(held, message="the peak, alone, in its level's shade")


def test_ctrl_c_ends_a_graph_program(terminal):
    # As TkCurses documents it: Ctrl-C closes an application that has no
    # WM_DELETE_WINDOW handler.
    term = run(
        terminal,
        "graph = BarGraph(root)\ngraph.pack()\ngraph.set(0, [100])\n",
        cols=20,
        rows=4,
    )
    term.wait_for_text(FULL)
    term.send(b"\x03")
    assert term.wait_for_exit(timeout=5) == 0


def test_wide_characters_in_labels_take_their_two_cells(terminal):
    # "界面" is four cells wide and "ab" two: the label column is four, and
    # every bar starts in the same column after it. Measured by characters,
    # the column was two, and the wide label pushed its bar two cells right.
    term = run(
        terminal,
        """
graph = BarGraph(root, orient="horizontal", segments=2, scale=40,
                 maximum=10, labels=["界面", "ab"], refreshinterval=10,
                 readout=True)
graph.pack(side="top", anchor="nw")
graph.set_all([[10], [10]])
""",
        cols=30,
        rows=4,
    )
    full = FULL * 5

    def aligned(t):
        return (
            t.row(0).startswith("界面 " + full)
            and t.row(2).startswith("ab   " + full)
            and t.row(0).rstrip().endswith(" 10")
            and t.row(2).rstrip().endswith(" 10")
        )

    term.wait_for(aligned, message="both bars starting in column 5")


def test_a_label_with_a_combining_mark_is_measured_without_it(terminal):
    # "Cafe" with a combining acute is four cells, so it is centred over a
    # ten-cell graph three cells in, as "Café" would be.
    term = run(
        terminal,
        """
graph = BarGraph(root, segments=1, thickness=10, scale=16, maximum=10,
                 label="Cafe\\u0301", refreshinterval=10)
graph.pack(side="top", anchor="nw")
graph.set(0, [10])
""",
        cols=20,
        rows=5,
    )
    term.wait_for(
        lambda t: t.row(0).startswith("   Café") and t.row(1).startswith(FULL * 10),
        message="the label centred, the accent on its letter",
    )
