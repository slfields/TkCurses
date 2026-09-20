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


"""The terminal changes size under an application that is already full.

Everything the other modules build - stretched containers, a window, a list
with a scrollbar - and then the one event that touches all of it at once.
tty only: a resize cannot fail without a real screen, because what goes
wrong is what is left drawn afterwards.

**Never wait on idle after a resize.** ``wait_for_idle`` returns when the
terminal goes quiet, and the terminal is quiet in the gap between the
resize arriving and the application reacting to it. A test that waited on
idle here read the screen from *before* the relayout, passed locally,
and failed on a loaded CI runner - the give-away being that the captured
screen was identical across two rounds of supposed fixes. Every test below
waits for the application to say the new size out loud.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


FULL = """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer

frame = tkcurses.Frame(root, name='wide', relief='solid')
frame.place(x=0, y=2, relwidth=1.0, height=6)
tkcurses.Label(frame, text='STRETCHED', anchor='w').place(x=1, y=1, width=12)

bar = tkcurses.Scrollbar(frame, name='bar', orient='vertical')
box = tkcurses.Listbox(frame, name='box', yscrollcommand=bar.set)
bar.configure(command=box.yview)
box.place(x=14, y=1, width=14, relheight=0.8)
bar.place(x=29, y=1, width=1, relheight=0.8)
for index in range(40):
    box.insert('end', 'row %d' % index)

win = tkcurses.Toplevel(root, name='corner', width=14, height=4)
win.title(' corner ')
tkcurses.Label(win, text='INWINDOW', anchor='w').place(x=1, y=1, width=10)


def report(event=None):
    root.update_layout()
    buffer.write(0, 0, ('size=%dx%d frame=%d win=+%d+%d' % (
        root.winfo_width(), root.winfo_height(), frame.winfo_width(),
        win.winfo_x(), win.winfo_y())).ljust(30))
    # On its own row: at 34 columns the first line is cut off, and a test
    # that parses a truncated line fails for a reason that has nothing to do
    # with what it is testing.
    buffer.write(1, 0, ('told=%.3f is=%.3f' % (
        bar.get()[1], box.yview()[1])).ljust(24))
    root.tk.screen.refresh()


root.bind('<Configure>', report, add='+')
root.update_layout()
win.geometry('14x4+%d+%d' % (root.winfo_width() - 16, root.winfo_height() - 6))
report()
root.mainloop()
"""

START = (50, 18)


@pytest.fixture
def full(terminal, tmp_path):
    term = terminal(cols=START[0], rows=START[1])
    term.run_source(FULL, workdir=tmp_path)
    term.wait_for_text("size=50x18")
    term.wait_for_idle()
    return term


def resize(term, cols, rows):
    """Resize and wait for the application to say it has caught up."""
    term.resize(cols, rows)
    term.wait_for_text(f"size={cols}x{rows}")
    term.wait_for_idle()


# --------------------------------------------------------- following the size


def test_a_stretched_container_follows_a_shrink(full):
    resize(full, 34, 12)
    assert "frame=34" in full.row(0), full.describe()


def test_a_stretched_container_follows_a_growth(full):
    resize(full, 64, 20)
    assert "frame=64" in full.row(0), full.describe()


def test_the_contents_are_still_drawn_after_a_resize(full):
    """The fault this guards against is the one the demo had: a resize
    clears the terminal under a double-buffered application, so nothing is
    dirty, so nothing is sent, and the screen stays blank where widgets
    plainly still are.
    """
    resize(full, 34, 12)
    assert any("STRETCHED" in row for row in full.display), full.describe()

    resize(full, 64, 20)
    assert any("STRETCHED" in row for row in full.display), full.describe()


def test_a_widget_is_not_left_drawn_at_its_old_size(full):
    """Shrinking the terminal shrinks the frame. Its old right-hand border
    must not still be sitting out there in the cells it gave up.
    """
    resize(full, 34, 12)

    for row in full.display:
        assert not row[34:].strip(), full.describe()


# ------------------------------------------------------- windows at the edge


def test_a_window_past_the_new_edge_is_brought_inside(full):
    """A window is always wholly inside the terminal, so a shrink that would
    leave one outside moves it instead (TkCurses-l2i, TkCurses-nvf).

    This test asserted the opposite until the invariant was fixed: that the
    window kept its geometry, vanished, and came back on the way out. That
    was the behaviour, and the behaviour was wrong - a modal window outside
    the screen still takes every click through its grab, so the application
    stopped answering with nothing drawn to say why.
    """
    assert any("INWINDOW" in row for row in full.display), full.describe()

    resize(full, 34, 12)

    assert any("INWINDOW" in row for row in full.display), full.describe()
    # 14x4 window, 34x12 terminal: the last position that fits.
    assert "win=+20+8" in full.row(0), full.describe()


def test_a_window_moved_by_a_shrink_goes_back_when_there_is_room(full):
    """Being brought inside must not cost the position permanently, or a
    one-column shrink and back would rearrange the screen.
    """
    resize(full, 34, 12)
    assert "win=+20+8" in full.row(0), full.describe()

    resize(full, *START)

    assert "win=+34+12" in full.row(0), full.describe()
    assert any("INWINDOW" in row for row in full.display), full.describe()


def test_a_window_still_inside_the_new_size_stays_drawn(full):
    """The control: a shrink that does not reach the window must leave it
    alone, or the test above would pass for a library that simply drops
    every window on any resize.
    """
    resize(full, 48, 17)
    assert any("INWINDOW" in row for row in full.display), full.describe()


# ------------------------------------------------------- several in a row


def test_successive_resizes_settle_at_the_last_one(full):
    """Resizes arrive faster than an application redraws. What matters is
    that the last one wins rather than the last one to finish.
    """
    full.resize(30, 10)
    full.resize(40, 14)
    full.resize(56, 19)
    full.wait_for_text("size=56x19")
    full.wait_for_idle()

    assert "frame=56" in full.row(0), full.describe()
    assert any("STRETCHED" in row for row in full.display), full.describe()


def test_a_resize_back_to_the_starting_size_restores_the_starting_screen(full):
    """A round trip is the cheapest way to catch state that accumulates:
    anything left behind by the shrink shows up as a difference here.
    """
    before = [row.rstrip() for row in full.display]

    resize(full, 34, 12)
    resize(full, *START)

    assert [row.rstrip() for row in full.display] == before, full.describe()


# ------------------------------------------------ the scrollbar, on resize


def test_a_resize_re_tells_the_scrollbar_how_much_is_visible(full):
    """The same fault as filling before layout, reached the other way.

    The list is ``relheight=0.8``, so a shrink really does change how many
    rows are visible - and the widget's own ``yview()`` says so. The
    scrollbar is never told, so the thumb keeps the size it had for a
    terminal that is no longer there.
    """
    resize(full, 34, 12)

    told, actual = full.row(1).split("told=")[1].split(" is=")
    assert float(told) == pytest.approx(float(actual), abs=0.01), full.describe()
