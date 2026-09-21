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


"""A repaint stays cheap enough to happen inside a click handler.

Not a benchmark. **ncurses drops mouse reports that arrive faster than the
application drains them**, at somewhere around 50-80ms of handler time on
the machine this was measured on - so a widget that takes longer than that
to repaint can cost a user the click they are in the middle of making
(TkCurses-9lr).

Measured before the caches went in, per repaint on a 120x40 screen:

    Listbox,  5000 rows        0.30 ms
    Treeview, 2000 rows        0.49 ms
    Text,     5000 lines     352.99 ms
    Canvas,   500 rectangles 757.55 ms

and after: 3.4ms and 17.3ms. The bounds below are far looser than those,
deliberately - a shared runner is several times slower than the machine
that produced them, and a test that fails for being on a busy machine
teaches nobody anything. They are set to catch a return to hundreds of
milliseconds, which is the thing that actually matters.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.tty

#: Generous by design, and scaled by the same factor that tells the harness
#: how much slower this machine is.
#:
#: The measured costs on a development machine are 3.4ms and 17.3ms. A
#: GitHub runner is not "several times" slower, which is what the first
#: version of these numbers assumed: it measured 31-35ms and 100-124ms, ten
#: times and six times. Fixed budgets picked from local measurements
#: therefore described this machine rather than the code, and CI failed on
#: every Python version.
#:
#: TKCURSES_TEST_TIMEOUT_SCALE already exists to say how much slower the
#: machine is - CI sets it to 4 - so the budgets follow it. At scale 4 that
#: is 100ms and 480ms against observed 35ms and 124ms, which a busy runner
#: can absorb and a return to the old 353ms and 758ms cannot hide in.
_SCALE = float(os.environ.get("TKCURSES_TEST_TIMEOUT_SCALE", "1"))
TEXT_BUDGET_MS = 25 * _SCALE
CANVAS_BUDGET_MS = 120 * _SCALE

#: An image is the third widget whose content can dwarf its window, and it
#: was missed when this file was written: a 320x200 photograph composed
#: 32,000 cells on every repaint and a 24-row window kept 9% of them.
#: The image here is 640x1600 in a 58x36 window - 512,000 cells against
#: 2,088 - so walking EITHER axis in full blows the budget by an order of
#: magnitude, which a merely-large image did not: at 640x400 a repaint that
#: ignored the row range still came in under it.
#: Measured at 47ms before the draw was clipped to the visible region, and
#: 6ms after. The budget is set where a return to composing the whole image
#: cannot hide.
IMAGE_BUDGET_MS = 20 * _SCALE

TIMED = """
import time
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer

text = tkcurses.Text(root, name='tx')
text.place(x=0, y=0, width=58, height=36)
text.insert('end', '\\n'.join('line %d of some text' % i for i in range(5000)))

# Deliberately far wider and taller than the 58x36 window it goes in, so a
# repaint that walks either axis of the whole image cannot stay in budget.
photo = tkcurses.PhotoImage(master=root, name='shot', width=640, height=1600)
photo.put('#3060a0', to=(0, 0, 640, 1600))
for stripe in range(0, 640, 7):
    photo.put('#e0d0b0', to=(stripe, 0, stripe + 3, 1600))
shown = tkcurses.Label(root, name='shown', image='shot', anchor='nw')
shown.place(x=0, y=0, width=58, height=36)

canvas = tkcurses.Canvas(root, name='c')
canvas.place(x=60, y=0, width=58, height=36)
for index in range(500):
    canvas.create_rectangle(
        index % 50, index % 28, index % 50 + 5, index % 28 + 3, fill='white')

root.update_layout()


def cost(widget, rounds):
    widget._redraw()
    start = time.perf_counter()
    for _ in range(rounds):
        widget._redraw()
    return (time.perf_counter() - start) / rounds * 1000


# Rows 37 and 38, not 0 and 1. The widgets are placed at y=0 and are 36
# rows tall, so rows 0 and 1 are cells the Text's own border owns: the
# result was written underneath a widget, and whether it showed through
# depended on whether anything repainted that panel afterwards. It did show
# on four Python versions and not on the fifth, where the failure screen has
# both widgets drawn, the measurement plainly finished, and no 'measured'
# anywhere. Nothing is placed below row 36, so nothing can paint over it.
buffer.write(
    37,
    0,
    (
        'text=%.2f canvas=%.2f image=%.2f'
        % (cost(text, 5), cost(canvas, 3), cost(shown, 5))
    ).ljust(48),
)
buffer.write(38, 0, 'measured'.ljust(12))
root.tk.screen.refresh()
root.after(30000, root.quit)
root.mainloop()
"""


@pytest.fixture
def costs(terminal, tmp_path):
    term = terminal(cols=120, rows=40)
    term.run_source(TIMED, workdir=tmp_path)
    # Ten, not a hundred and twenty. wait_for_text multiplies by
    # TKCURSES_TEST_TIMEOUT_SCALE, so 120 became 480s on CI - eight times
    # the suite's own 60s pytest-timeout, which killed the test before it
    # could report anything useful. Forty seconds at CI's scale leaves the
    # failure legible.
    term.wait_for_text("measured", timeout=10)
    reported = term.row(37).strip()
    return {part.split("=")[0]: float(part.split("=")[1]) for part in reported.split()}


def test_a_text_repaints_quickly_enough_to_sit_in_a_handler(costs):
    assert costs["text"] < TEXT_BUDGET_MS, costs


def test_a_canvas_repaints_quickly_enough_to_sit_in_a_handler(costs):
    assert costs["canvas"] < CANVAS_BUDGET_MS, costs


def test_an_image_repaints_in_time_with_its_window_not_its_content(costs):
    """A 320x200 photograph in a 58x36 window.

    The window is the small number here and the repaint has to follow it.
    Composing the whole image instead took 47ms, which is past the 50-80ms
    boundary where ncurses begins dropping mouse reports as soon as the
    machine is a few times slower - so a click on a picture could simply go
    missing. This is TkCurses-g9w's fault a third time, in a widget that
    did not exist when g9w was closed.
    """
    assert costs["image"] < IMAGE_BUDGET_MS, costs
