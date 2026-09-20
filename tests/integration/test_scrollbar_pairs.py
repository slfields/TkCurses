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


"""A scrollbar and the widget it scrolls, wired the way applications wire it.

Two objects, two directions, and a loop between them:

    widget -yscrollcommand-> scrollbar.set      "this is where I am"
    scrollbar -command-> widget.yview           "go here"

Each half can be right on its own and the pair still wrong, because what is
being tested is whether the two agree - and agreement is not a property
either one has. That is why none of this could be a unit test, and why the
pair had no test at all before this module.

The invariant, stated once: **what the scrollbar was last told is what the
widget reports.** Everything below is that sentence under some disturbance.
"""

from __future__ import annotations

import pytest

import tkcurses

#: Enough items that a five-row widget is well short of showing them all.
ITEMS = 20


class Recorder:
    """A scrollbar that also keeps what it was told, so a test can compare.

    A real Scrollbar, not a stand-in: the point is the pair, and half of a
    pair replaced by a fake tests nothing.
    """

    def __init__(self, parent):
        self.bar = tkcurses.Scrollbar(parent, name="bar", orient="vertical")
        self.told: list[tuple[float, float]] = []

    def set(self, first, last):
        self.told.append((float(first), float(last)))
        self.bar.set(first, last)

    @property
    def last(self):
        return self.told[-1] if self.told else None


def listbox_pair(app, fill_first: bool):
    recorder = Recorder(app)
    box = tkcurses.Listbox(app, name="lb", height=5, yscrollcommand=recorder.set)
    recorder.bar.configure(command=box.yview)
    box.place(x=0, y=0, width=20, height=5)
    recorder.bar.place(x=20, y=0, width=1, height=5)

    def fill():
        for index in range(ITEMS):
            box.insert("end", f"item {index}")

    if fill_first:
        fill()
        app.update_layout()
    else:
        app.update_layout()
        fill()
    return recorder, box


@pytest.fixture
def pair(app):
    """The ordinary case: laid out, then filled."""
    return listbox_pair(app, fill_first=False)


# --------------------------------------------------------- the two directions


def test_the_scrollbar_is_told_where_the_widget_is(pair):
    recorder, box = pair
    assert recorder.last == box.yview()


def test_moving_the_widget_moves_the_scrollbar(pair):
    recorder, box = pair

    box.yview("moveto", 0.5)

    assert recorder.last == box.yview()
    assert recorder.last[0] == pytest.approx(0.5)


def test_driving_the_scrollbar_moves_the_widget(pair):
    """The other direction, through the command the application wired up.

    Called the way the scrollbar's own handlers call it - ``command("moveto",
    fraction)`` - rather than by reaching for ``box.yview`` directly, which
    would test the widget and not the pair.
    """
    recorder, box = pair

    recorder.bar.cget("command")("moveto", 0.5)

    assert box.yview()[0] == pytest.approx(0.5)
    assert recorder.last == box.yview()


def test_a_press_on_the_trough_scrolls_the_widget(pair):
    """The whole loop, from a gesture: the scrollbar's class binding reads
    its own ``command`` and calls it, the widget moves, and the widget's
    ``yscrollcommand`` reports back.
    """
    recorder, box = pair
    bar = recorder.bar
    before = box.yview()[0]

    bar.event_generate("<Button-1>", x=0, y=bar._rect.height - 1)

    assert box.yview()[0] > before
    assert recorder.last == box.yview()


def test_a_scroll_by_units_keeps_the_two_in_step(pair):
    recorder, box = pair

    box.yview("scroll", 2, "units")

    assert recorder.last == box.yview()


def test_scrolling_to_the_end_leaves_the_scrollbar_at_the_end(pair):
    recorder, box = pair

    box.yview("moveto", 1.0)

    assert recorder.last[1] == pytest.approx(1.0)
    assert recorder.last == box.yview()


# ------------------------------------------------------------- the edge cases


def test_an_empty_widget_reports_a_full_thumb(app):
    """Nothing to scroll is not the same as scrolled to nowhere: the thumb
    fills the trough, which is how a person sees there is nothing hidden.
    """
    _recorder, box = listbox_pair(app, fill_first=False)
    box.delete(0, "end")

    assert box.yview() == (0.0, 1.0)


def test_a_widget_taller_than_its_contents_reports_a_full_thumb(app):
    recorder = Recorder(app)
    box = tkcurses.Listbox(app, name="lb", height=10, yscrollcommand=recorder.set)
    box.place(x=0, y=0, width=20, height=10)
    app.update_layout()
    box.insert("end", "one", "two")

    assert box.yview()[1] == pytest.approx(1.0)
    assert recorder.last == box.yview()


def test_deleting_the_contents_puts_the_scrollbar_back(pair):
    recorder, box = pair
    box.yview("moveto", 1.0)

    box.delete(0, "end")

    assert recorder.last == box.yview()


# ------------------------------------------- filled before it was laid out


def test_filling_before_layout_still_leaves_the_two_agreeing(app):
    """The ordinary tkinter idiom, and the broken one.

        lb = Listbox(...); lb.pack(); lb.insert(...); root.mainloop()

    The fractions depend on how many rows are *visible*, which is not known
    until layout has given the widget a size. Filled first, the scrollbar is
    told a fraction computed against the wrong height and nothing ever
    corrects it - measured, told (0.0, 0.05) where the widget says
    (0.0, 0.15), and a later update_layout() does not repair it.

    Tk does repair it: measured on 9.0.2, the two disagree before update()
    and agree after.
    """
    recorder, box = listbox_pair(app, fill_first=True)

    assert recorder.last == box.yview()


def test_a_text_widget_filled_before_layout_also_agrees(app):
    recorder = Recorder(app)
    text = tkcurses.Text(app, name="tx", height=5, yscrollcommand=recorder.set)
    text.place(x=0, y=0, width=20, height=5)
    text.insert("end", "\n".join(f"line {index}" for index in range(ITEMS)))
    app.update_layout()

    assert recorder.last == text.yview()


def test_the_same_widget_filled_after_layout_does_agree(app):
    """The control for the two above. Without it, a bug that made every
    comparison fail would look like the same known fault.
    """
    recorder, box = listbox_pair(app, fill_first=False)
    assert recorder.last == box.yview()
