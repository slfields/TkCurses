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

"""Cells written past curses, so a picture is not held to 255 pairs."""

from __future__ import annotations

import pytest

from tkcurses._core.direct import DirectPainter


@pytest.fixture
def painter():
    made = DirectPainter()
    made.enable()
    return made


def test_a_disabled_painter_collects_nothing():
    """Off is off: nothing is gathered, so nothing can be written."""
    idle = DirectPainter()
    idle.add(None, 0, 0, "█", (1, 2, 3), (4, 5, 6))
    assert idle.pending == 0
    assert idle.render() == b""


def test_semicolons_not_colons(painter):
    """The whole reason we emit this ourselves rather than let ncurses.

    ncurses builds the colon form from the xterm-direct terminfo -
    ESC[38:2::r:g:b m, with an empty colour-space field - and many terminals
    cannot parse it. chafa emits semicolons and works where we did not.
    TkCurses-bvu.7.
    """
    painter.add(None, 0, 0, "█", (51, 102, 204), (17, 34, 51))
    out = painter.render().decode()
    assert "\x1b[38;2;51;102;204m" in out
    assert "\x1b[48;2;17;34;51m" in out
    assert ":" not in out, f"a colon-separated sequence was emitted: {out!r}"


def test_a_run_of_one_colour_is_written_once(painter):
    """Otherwise a full-screen picture is a hundred kilobytes a frame."""
    for column in range(10):
        painter.add(None, 3, column, "█", (255, 0, 0), (0, 0, 0))
    out = painter.render().decode()
    assert out.count("\x1b[38;2;255;0;0m") == 1
    assert out.count("\x1b[48;2;0;0;0m") == 1
    assert "██████████" in out


def test_the_cursor_moves_only_where_a_run_breaks(painter):
    """Adjacent cells continue; a gap or a new row needs a position."""
    for column in (0, 1, 2, 7, 8):
        painter.add(None, 5, column, "▀", (1, 1, 1), (2, 2, 2))
    out = painter.render().decode()
    # One move for the row, one for the gap after column 2.
    assert out.count("\x1b[6;") == 2
    assert "\x1b[6;1H" in out and "\x1b[6;8H" in out


def test_positions_are_one_based_as_the_terminal_counts(painter):
    painter.add(None, 0, 0, "█", (1, 1, 1), (2, 2, 2))
    assert "\x1b[1;1H" in painter.render().decode()


def test_the_attributes_are_given_back_at_the_end(painter):
    """Or the next thing curses writes inherits the picture's colours."""
    painter.add(None, 0, 0, "█", (1, 1, 1), (2, 2, 2))
    assert painter.render().decode().endswith("\x1b[0m")


def test_clear_forgets_the_frame(painter):
    painter.add(None, 0, 0, "█", (1, 1, 1), (2, 2, 2))
    painter.clear()
    assert painter.pending == 0
    assert painter.render() == b""


def test_a_short_write_is_finished_rather_than_dropped(monkeypatch):
    """os.write may write less than it is given, and a pty is where it does.

    Ignoring the count left the first part of a picture in exact colour and
    the rest in whatever curses had put there - which measured as MORE
    distinct colours on screen and a WORSE picture, a failure that looks
    like a quality problem and is not one.
    """
    import os as real_os

    written = bytearray()

    def dribble(fd, data):
        # One byte at a time, which is legal and is what a full pty does.
        written.extend(data[:1])
        return 1

    made = DirectPainter(stream=99)
    made.enable()
    for column in range(40):
        made.add(None, 0, column, "█", (column * 6, 0, 0), (0, 0, 0))
    expected = made.render()
    monkeypatch.setattr(real_os, "write", dribble)
    sent = made.paint()
    assert sent == len(expected), (
        f"{sent} of {len(expected)} bytes written; a short write was treated "
        "as a complete one"
    )
    assert bytes(written) == expected


def test_a_closed_terminal_does_not_fail_the_frame(monkeypatch):
    """The curses rendering underneath is still correct, so carry on."""
    import os as real_os

    def refuse(fd, data):
        raise OSError("closed")

    made = DirectPainter(stream=99)
    made.enable()
    made.add(None, 0, 0, "█", (1, 1, 1), (2, 2, 2))
    monkeypatch.setattr(real_os, "write", refuse)
    assert made.paint() == 0


def test_a_palette_terminal_is_written_in_its_own_form():
    """ESC[38;5;N, not ESC[38;2;r;g;b, where there is a palette.

    The ceiling is worth escaping on a 256-colour terminal too - measured,
    14 colours through the pair table against 88 written by hand - but it
    has to be said in the form that terminal understands.
    """
    made = DirectPainter()
    made.enable(True, index_of=lambda rgb: 208 if rgb[0] > 128 else 21)
    made.add(None, 0, 0, "▀", (255, 135, 0), (0, 0, 255))
    out = made.render().decode()
    assert "\x1b[38;5;208m" in out
    assert "\x1b[48;5;21m" in out
    assert ";2;" not in out, f"direct colour written to a palette: {out!r}"


def test_the_palette_is_asked_once_per_run_not_once_per_cell():
    """The index lookup sits inside the per-cell loop, so it must be cheap.

    Run-length encoding already collapses a run to one sequence; this pins
    that the conversion collapses with it rather than being called for every
    cell of a flat region.
    """
    calls = 0

    def index_of(rgb):
        nonlocal calls
        calls += 1
        return 42

    made = DirectPainter()
    made.enable(True, index_of=index_of)
    for column in range(20):
        made.add(None, 0, column, "█", (1, 2, 3), (4, 5, 6))
    made.render()
    assert calls == 2, (
        f"{calls} palette lookups for one run of one colour pair; the "
        "conversion is being done per cell rather than per change"
    )


def test_one_picture_does_not_wipe_another(painter):
    """Cells are kept per contributor, not in one shared heap.

    Each widget clears before it draws. With a single dictionary the second
    picture to draw erased the first, so only one of them was ever painted.
    """
    first, second = object(), object()
    painter.add(first, 0, 0, "█", (255, 0, 0), (0, 0, 0))
    painter.add(second, 5, 0, "█", (0, 255, 0), (0, 0, 0))
    painter.clear(second)
    painter.add(second, 5, 0, "█", (0, 0, 255), (0, 0, 0))
    assert painter.pending == 2, "clearing one contributor dropped the other"
    out = painter.render().decode()
    assert "\x1b[38;2;255;0;0m" in out, "the first picture was wiped"
    assert "\x1b[38;2;0;0;255m" in out


def test_a_contributor_that_draws_nothing_leaves_nothing(painter):
    """The collected-image trap, in the painter rather than the widget.

    A widget whose image has been collected draws nothing at all. If its
    cells are not cleared with it, the picture is repainted past curses for
    ever - which is exactly the stale art UAT 35 exists to demonstrate.
    """
    owner = object()
    for column in range(6):
        painter.add(owner, 0, column, "█", (1, 2, 3), (4, 5, 6))
    painter.clear(owner)
    assert painter.pending == 0
    assert painter.render() == b""


def test_an_unchanged_picture_over_an_unchanged_frame_costs_nothing(monkeypatch):
    """The expensive part is the write, and most frames do not need one.

    A full-screen photograph is tens of kilobytes. Writing it again on every
    tick was most of the cost of painting this way - it made the whole test
    suite slower by 15% and pushed CI past its ten-minute job limit.
    """
    import os as real_os

    writes = []
    monkeypatch.setattr(
        real_os, "write", lambda fd, data: (writes.append(data), len(data))[1]
    )

    made = DirectPainter(stream=99)
    made.enable()
    for column in range(20):
        made.add(None, 0, column, "█", (1, 2, 3), (4, 5, 6))

    assert made.paint(repainted=True) > 0, "the first frame has to be written"
    assert made.paint(repainted=False) == 0, "nothing changed, so nothing to say"
    assert len(writes) == 1


def test_a_frame_curses_painted_is_always_written_again(monkeypatch):
    """Curses repaints those cells without saying so, so ours goes back on."""
    import os as real_os

    writes = []
    monkeypatch.setattr(
        real_os, "write", lambda fd, data: (writes.append(data), len(data))[1]
    )

    made = DirectPainter(stream=99)
    made.enable()
    made.add(None, 0, 0, "█", (1, 2, 3), (4, 5, 6))
    made.paint(repainted=True)
    made.paint(repainted=True)
    assert len(writes) == 2


def test_a_changed_picture_is_written_even_on_a_quiet_frame(monkeypatch):
    import os as real_os

    writes = []
    monkeypatch.setattr(
        real_os, "write", lambda fd, data: (writes.append(data), len(data))[1]
    )

    made = DirectPainter(stream=99)
    made.enable()
    made.add(None, 0, 0, "█", (1, 2, 3), (4, 5, 6))
    made.paint(repainted=True)
    made.clear(None)
    made.add(None, 0, 0, "█", (9, 9, 9), (4, 5, 6))
    assert made.paint(repainted=False) > 0, "the picture changed and was not written"


def test_a_short_write_is_not_remembered_as_done(monkeypatch):
    """Or the rest of the picture is never sent.

    A partial write leaves the terminal holding half the picture. Recording
    that as what is on screen would make the next frame skip it.
    """
    import os as real_os

    sent = {"count": 0}

    def give_up_half_way(fd, data):
        # Writes a little, then the terminal goes away. The loop breaks and
        # the picture is only partly on screen.
        sent["count"] += 1
        if sent["count"] > 2:
            raise OSError("closed")
        return 8

    monkeypatch.setattr(real_os, "write", give_up_half_way)
    made = DirectPainter(stream=99)
    made.enable()
    for column in range(20):
        made.add(None, 0, column, "█", (1, 2, 3), (4, 5, 6))
    written = made.paint(repainted=True)
    assert 0 < written < len(made.render()), "the write should have been cut short"

    monkeypatch.setattr(real_os, "write", lambda fd, data: len(data))
    assert made.paint(repainted=False) > 0, (
        "a partial write was remembered as complete, so the rest of the "
        "picture would never be sent"
    )
