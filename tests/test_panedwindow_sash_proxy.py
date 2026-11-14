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

"""PanedWindow's ``sash`` and ``proxy`` commands, against real tkinter.

Tk's units are pixels and these are cells, so what is compared is what
does not depend on them: every refusal, the marks, and how far each drag
moves a sash from where it was - a drag of ten moves it ten in either.
"""

from __future__ import annotations

from typing import Any

import pytest

import tkcurses
from tkcurses._core.geometry import Rect

tkinter = pytest.importorskip("tkinter")


def _steps(paned: Any) -> list:
    path = str(paned)
    start = paned.sash_coord(0)[0]

    def moved(index: int = 0) -> int:
        return paned.sash_coord(index)[0] - start

    steps = [
        ("coord 5", lambda: paned.sash_coord(5)),
        ("coord x", lambda: paned.sash_coord("x")),
        ("place 9", lambda: paned.sash("place", 9, 1, 1)),
        ("mark unset", lambda: paned.sash_mark(0)),
        ("mark", lambda: paned.sash("mark", 0, 50, 7)),
        ("mark read", lambda: paned.sash_mark(0)),
        ("dragto 60", lambda: (paned.sash("dragto", 0, 60, 7), moved())),
        ("mark kept", lambda: paned.sash_mark(0)),
        ("dragto 70", lambda: (paned.sash("dragto", 0, 70, 0), moved())),
        ("dragto unmarked", lambda: paned.sash("dragto", 1, 0, 0)),
        ("bogus", lambda: paned.sash("bogus")),
        ("none", lambda: paned.sash()),
        ("mark 2 args", lambda: paned.sash("mark", 0, 1)),
        ("dragto 1 arg", lambda: paned.sash("dragto", 0)),
        ("coord no index", lambda: paned.sash("coord")),
        ("mark x", lambda: paned.sash("mark", 0, "x", 1)),
        ("proxy unset", lambda: paned.proxy_coord()),
        ("proxy place", lambda: paned.proxy_place(30, 45)),
        ("proxy along", lambda: paned.proxy_coord()[0]),
        ("proxy forget", lambda: paned.proxy_forget()),
        ("proxy kept", lambda: paned.proxy_coord()[0]),
        ("proxy below", lambda: (paned.proxy_place(-5, 9), paned.proxy_coord()[0])),
        ("proxy bogus", lambda: paned.proxy("bogus")),
        ("proxy none", lambda: paned.proxy()),
        ("proxy place 1", lambda: paned.proxy("place", 1)),
        ("proxy place a", lambda: paned.proxy_place("a", 1)),
        ("proxy coord 1", lambda: paned.proxy("coord", 1)),
        ("proxy forget 1", lambda: paned.proxy("forget", 1)),
        ("off a sash", lambda: paned.identify(1, 1)),
    ]
    found = []
    for label, step in steps:
        try:
            answer = step()
        except (tkinter.TclError, tkcurses.TclError) as error:
            answer = ("error", str(error).replace(path, "PATH"))
        found.append((label, answer))
    return found


def test_sash_and_proxy_answer_as_tks_do():
    try:
        real = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    try:
        real.geometry("400x200")
        theirs_paned = tkinter.PanedWindow(real, borderwidth=0, sashpad=0)
        theirs_paned.pack(fill="both", expand=1)
        for _ in range(3):
            theirs_paned.add(tkinter.Frame(theirs_paned, width=100, height=100))
        real.update()
        theirs = _steps(theirs_paned)
    finally:
        real.destroy()

    root = tkcurses.Misc()
    paned = tkcurses.PanedWindow(root, borderwidth=0)
    for _ in range(3):
        paned.add(tkcurses.Frame(paned, width=20, height=5))
    paned._allocate(Rect(0, 0, 100, 10))
    paned._map()
    assert _steps(paned) == theirs


def test_a_vertical_proxy_keeps_its_row_and_takes_the_border_for_its_column():
    root = tkcurses.Misc()
    paned = tkcurses.PanedWindow(root, orient="vertical")
    paned.add(tkcurses.Frame(paned, height=5))
    paned.add(tkcurses.Frame(paned, height=5))
    paned._allocate(Rect(0, 0, 20, 14))
    paned._map()
    paned.proxy_place(7, 6)
    edge = 1 if paned._border_drawn else 0
    assert paned.proxy_coord() == (edge, 6)
    paned.proxy_place(7, 99)
    assert paned.proxy_coord()[1] == 14 - edge - paned._sash_parts()[2]
