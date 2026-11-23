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

"""The shared legend's statistics line: measured and wrapped as a
description is, and drawn after it."""

from tkcurses._charts.geometry import Rect
from tkcurses._charts.legend import DESCRIPTION_WIDTH, LEAD, Entry, place


def test_statistics_widen_an_entry_as_a_description_does():
    assert Entry("a", "cpu", stats="avg 41%").width == LEAD + len("avg 41%")
    long = "x" * (DESCRIPTION_WIDTH + 10)
    assert Entry("a", "cpu", stats=long).width == LEAD + DESCRIPTION_WIDTH


def test_the_wider_of_description_and_statistics_counts():
    entry = Entry("a", "cpu", description="load", stats="avg 41% · max 72%")
    assert entry.width == LEAD + len("avg 41% · max 72%")


def test_statistics_come_after_the_name_and_the_description():
    entry = Entry("a", "cpu", description="all cores", stats="max 72%")
    laid = place([entry], Rect(0, 0, 20, 6), "right", 1)
    (placed,) = laid.placed
    assert placed.lines == ("cpu", "all cores", "max 72%")
    assert placed.name_lines == 1


def test_statistics_wrap_on_lines_of_their_own():
    entry = Entry("a", "cpu", stats="avg 41% max 72% min 3%")
    laid = place([entry], Rect(0, 0, 12, 6), "right", 3)
    (placed,) = laid.placed
    assert placed.lines[0] == "cpu"
    assert " ".join(placed.lines[1:]) == "avg 41% max 72% min 3%"
    assert all(len(line) <= 12 - 1 - LEAD for line in placed.lines)


def test_an_entry_without_statistics_is_unchanged():
    entry = Entry("a", "cpu", description="all cores")
    laid = place([entry], Rect(0, 0, 20, 6), "right", 1)
    assert laid.placed[0].lines == ("cpu", "all cores")
