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

"""The themed widgets on a real terminal.

The claim this cycle makes is that appearance lives in one place and every
widget follows it. That is not something a unit test can show: it has to be
a screen that changes when the database does.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

THEMED = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
style = ttk.Style(root)
names = list(style.theme_names())

for index in range(3):
    ttk.Separator(root, name='sep%d' % index).place(x=10, y=1 + index, width=20)
bar = ttk.Progressbar(root, name='bar', length=20, value=50)
bar.place(x=10, y=5)
ttk.Sizegrip(root, name='grip').place(x=34, y=7)


def announce():
    buffer.write(0, 0, ('theme=%s' % style.theme_use()).ljust(20))
    root.tk.screen.refresh()


def cycle(event):
    style.theme_use(names[(names.index(style.theme_use()) + 1) % len(names)])
    announce()


def fill(event):
    bar.configure(value=100)
    root.tk.screen.refresh()


root.bind('<Key-n>', cycle)
root.bind('<Key-f>', fill)
root.update_layout()
announce()
root.after(8000, root.quit)
root.mainloop()
"""


@pytest.fixture
def themed(terminal, tmp_path):
    term = terminal(cols=56, rows=10)
    term.run_source(THEMED, workdir=tmp_path)
    term.wait_for_text("theme=default")
    term.wait_for_idle()
    return term


def separator_row(term):
    """The first separator's row, as the characters it was drawn with."""
    return term.display[1][10:30]


def test_the_separators_draw_with_the_default_theme(themed):
    assert separator_row(themed) == "─" * 20, themed.describe()


def test_switching_the_theme_redraws_what_is_already_on_screen(themed):
    """The claim the whole cycle rests on, and the thing a unit test cannot
    show: appearance lives in one place, and changing it changes what is
    already drawn. A theme that only took effect on the next repaint would
    be a theme nobody could demonstrate.
    """
    themed.send(b"n")
    themed.wait_for_text("theme=ascii")
    themed.wait_for_idle()
    assert separator_row(themed) == "-" * 20, themed.describe()


def test_every_theme_draws_its_own_rail(themed):
    seen = {}
    for _ in range(6):
        name = themed.row(0).strip().split("=")[1]
        seen[name] = separator_row(themed)[0]
        themed.send(b"n")
        themed.wait_for_idle()
    assert seen["default"] == "─"
    assert seen["ascii"] == "-"
    assert seen["dos"] == "═"
    assert seen["double"] == "═"
    assert seen["minimal"] == " "


def test_one_theme_change_reaches_every_widget_of_a_class(themed):
    """Three separators, one theme_use, all three follow."""
    themed.send(b"n")
    themed.wait_for_text("theme=ascii")
    themed.wait_for_idle()
    for row in (1, 2, 3):
        assert themed.display[row][10:30] == "-" * 20, themed.describe()


def test_a_progressbar_shows_how_far_along_it_is(themed):
    row = themed.display[5][10:30]
    assert row.count("█") == 10, themed.describe()
    assert row.count("░") == 10, themed.describe()


def test_a_progressbar_fills_when_its_value_does(themed):
    themed.send(b"f")
    themed.wait_for(
        lambda t: t.display[5][10:30].count("█") == 20,
        message="the bar to fill",
    )


def test_the_sizegrip_marks_the_corner(themed):
    assert "◢" in "\n".join(themed.display), themed.describe()


RESTYLE = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
style = ttk.Style(root)
bars = [ttk.Progressbar(root, name='b%d' % i, length=18, value=60) for i in range(3)]
for index, bar in enumerate(bars):
    bar.place(x=8, y=1 + index)


def restyle(event):
    style.configure('TProgressbar', foreground='green')
    style.map('TProgressbar', foreground=[('disabled', 'red')])
    buffer.write(0, 0, 'restyled  ')
    root.tk.screen.refresh()


def disable(event):
    bars[1].state(['disabled'])
    bars[1]._redraw()
    buffer.write(0, 0, 'disabled  ')
    root.tk.screen.refresh()


root.bind('<Key-r>', restyle)
root.bind('<Key-d>', disable)
buffer.write(0, 0, 'plain     ')
root.update_layout()
root.tk.screen.refresh()
root.after(8000, root.quit)
root.mainloop()
"""


@pytest.fixture
def bars(terminal, tmp_path):
    term = terminal(cols=40, rows=6)
    term.run_source(RESTYLE, workdir=tmp_path)
    term.wait_for_text("plain")
    term.wait_for_idle()
    return term


def colours(term):
    """The foreground of each of the three bars."""
    return [term.attrs_at(row, 9)["fg"] for row in (1, 2, 3)]


def test_one_configure_reaches_every_widget_of_the_class(bars):
    """The claim the cycle rests on, on a screen: one call naming a class,
    and three widgets nobody touched individually change together.

    This needed Style.configure to repaint. It did not at first - the
    database changed and nothing already drawn moved, because a widget
    resolves its appearance when it paints.
    """
    assert colours(bars) == ["white"] * 3
    bars.send(b"r")
    bars.wait_for_text("restyled")
    bars.wait_for_idle()
    assert colours(bars) == ["green"] * 3, bars.describe()


def test_a_mapped_state_reaches_only_the_widget_in_it(bars):
    """The other half: a map entry is per widget, not per class."""
    bars.send(b"r")
    bars.wait_for_text("restyled")
    bars.wait_for_idle()
    bars.send(b"d")
    bars.wait_for_text("disabled")
    bars.wait_for_idle()
    assert colours(bars) == ["green", "red", "green"], bars.describe()


GRIP = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
top = tkcurses.Toplevel(root)
top.geometry('20x6+3+2')
{lock}
tkcurses.Label(top, text='window').place(x=1, y=1)
ttk.Sizegrip(top, name='grip').place(relx=1.0, x=-1, rely=1.0, y=-1)
root.update_layout()
buffer.write(0, 0, 'ready')
root.tk.screen.refresh()
root.after(8000, root.quit)
root.mainloop()
"""


def window_size(term):
    """The drawn window's size, read off the screen.

    Read rather than reported, because a programmatic geometry() does not
    fire <Configure> here - TkCurses-b5o, found while writing this - so a
    program cannot tell you its own new size as it changes. What a person
    sees is the better assertion anyway.
    """
    rows = [
        index for index, line in enumerate(term.display) if "┌" in line or "└" in line
    ]
    top_row = term.display[rows[0]]
    return (
        top_row.index("┐") - top_row.index("┌") + 1,
        rows[-1] - rows[0] + 1,
    )


def drag_the_grip(term, across, down):
    """Press the grip and pull it, as a hand would."""
    row = next(index for index, line in enumerate(term.display) if "◢" in line)
    column = term.display[row].index("◢")
    term.send_mouse(column, row, action="press")
    term._drain(0.08)
    for step in range(1, max(abs(across), abs(down)) + 1):
        term.send_mouse(
            column + min(step, across), row + min(step, down), action="move"
        )
        term._drain(0.05)
    term.send_mouse(column + across, row + down, action="release")
    term._drain(0.08)
    term.wait_for_idle()


def grip_window(terminal, tmp_path, lock=""):
    term = terminal(cols=50, rows=16)
    term.run_source(GRIP.format(lock=lock), workdir=tmp_path)
    term.wait_for_text("ready")
    term.wait_for_idle()
    assert window_size(term) == (20, 6), term.describe()
    return term


def test_dragging_the_grip_resizes_the_window(terminal, tmp_path):
    """The thing the first version of this widget said was impossible.

    It is not. A Toplevel here is the library's own window - it has a
    geometry, a place in the z-order, and it redraws when it changes size -
    so dragging its corner is a real operation. Only the root is different,
    because the root's size is the terminal's.
    """
    term = grip_window(terminal, tmp_path)
    drag_the_grip(term, 8, 4)
    assert window_size(term) == (28, 10), term.describe()


def test_the_grip_stays_in_the_corner_it_moved(terminal, tmp_path):
    term = grip_window(terminal, tmp_path)
    drag_the_grip(term, 8, 4)
    row = next(index for index, line in enumerate(term.display) if "◢" in line)
    bottom = max(index for index, line in enumerate(term.display) if "└" in line)
    assert row == bottom - 1, term.describe()


def test_a_window_locked_across_grows_only_downwards(terminal, tmp_path):
    """wm_resizable is honoured per axis, as Tk honours it."""
    term = grip_window(terminal, tmp_path, lock="top.wm_resizable(False, True)")
    drag_the_grip(term, 8, 4)
    assert window_size(term) == (20, 10), term.describe()


def test_a_locked_window_does_not_move_at_all(terminal, tmp_path):
    term = grip_window(terminal, tmp_path, lock="top.wm_resizable(False, False)")
    drag_the_grip(term, 8, 4)
    assert window_size(term) == (20, 6), term.describe()
