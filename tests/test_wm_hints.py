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

"""The window manager hints a terminal has no use for, against real tkinter.

``wm iconname``, ``wm group``, ``wm aspect`` and the rest ask a window
manager for an icon, a group, a session's command line - none of which a
terminal has. They are checked, kept and read back, so the same calls are
made on a real Tk window and on one here, and every answer and every refusal
must be the same.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

import tkcurses

if TYPE_CHECKING:
    from collections.abc import Callable

tkinter = pytest.importorskip("tkinter")

#: Each step is a call on (window, another window, a photo image), run in
#: order on one window, so a getter reads back what the setter before it did.
STEPS: list[tuple[str, Callable[[Any, Any, Any], Any]]] = [
    ("aspect()", lambda w, o, i: w.wm_aspect()),
    ("aspect(1,2,3,4)", lambda w, o, i: w.wm_aspect(1, 2, 3, 4)),
    ("aspect() again", lambda w, o, i: w.aspect()),
    ("aspect('a',..)", lambda w, o, i: w.wm_aspect("a", 2, 3, 4)),
    ("aspect(0,..)", lambda w, o, i: w.wm_aspect(0, 2, 3, 4)),
    ("aspect(1,2)", lambda w, o, i: w.wm_aspect(1, 2)),
    ("aspect('',..)", lambda w, o, i: w.wm_aspect("", "", "", "")),
    ("aspect() cleared", lambda w, o, i: w.wm_aspect()),
    ("client()", lambda w, o, i: w.wm_client()),
    ("client('host')", lambda w, o, i: w.wm_client("host")),
    ("client() again", lambda w, o, i: w.client()),
    ("client('')", lambda w, o, i: w.wm_client("")),
    ("client() cleared", lambda w, o, i: w.wm_client()),
    ("command()", lambda w, o, i: w.wm_command()),
    ("command('prog -x')", lambda w, o, i: w.wm_command("prog -x")),
    ("command() again", lambda w, o, i: w.command()),
    ("group()", lambda w, o, i: w.wm_group()),
    ("group(other)", lambda w, o, i: w.wm_group(o)),
    ("group() again", lambda w, o, i: w.group()),
    ("group('.nope')", lambda w, o, i: w.wm_group(".nope")),
    ("iconbitmap()", lambda w, o, i: w.wm_iconbitmap()),
    ("iconbitmap('error')", lambda w, o, i: w.wm_iconbitmap("error")),
    ("iconbitmap() again", lambda w, o, i: w.iconbitmap()),
    ("iconbitmap('nope')", lambda w, o, i: w.wm_iconbitmap("nope")),
    ("iconbitmap(default=)", lambda w, o, i: w.wm_iconbitmap(default="error")),
    ("iconmask('info')", lambda w, o, i: w.wm_iconmask("info")),
    ("iconmask() again", lambda w, o, i: w.iconmask()),
    ("iconmask('nope')", lambda w, o, i: w.wm_iconmask("nope")),
    ("iconname()", lambda w, o, i: w.wm_iconname()),
    ("iconname('x')", lambda w, o, i: w.wm_iconname("x")),
    ("iconname() again", lambda w, o, i: w.iconname()),
    ("iconphoto(False, img)", lambda w, o, i: w.wm_iconphoto(False, i)),
    ("iconphoto(True, img)", lambda w, o, i: w.iconphoto(True, i)),
    ("iconphoto('nope')", lambda w, o, i: w.wm_iconphoto(True, "nope")),
    ("iconphoto(False)", lambda w, o, i: w.wm_iconphoto(False)),
    ("iconposition()", lambda w, o, i: w.wm_iconposition()),
    ("iconposition(1,2)", lambda w, o, i: w.wm_iconposition(1, 2)),
    ("iconposition() again", lambda w, o, i: w.iconposition()),
    ("iconposition('a',2)", lambda w, o, i: w.wm_iconposition("a", 2)),
    ("iconposition(1)", lambda w, o, i: w.wm_iconposition(1)),
    ("iconwindow()", lambda w, o, i: w.wm_iconwindow()),
    ("iconwindow(other)", lambda w, o, i: w.wm_iconwindow(o)),
    ("iconwindow() again", lambda w, o, i: w.iconwindow()),
    ("positionfrom()", lambda w, o, i: w.wm_positionfrom()),
    ("positionfrom('user')", lambda w, o, i: w.wm_positionfrom("user")),
    ("positionfrom() again", lambda w, o, i: w.positionfrom()),
    ("positionfrom('p')", lambda w, o, i: w.wm_positionfrom("p")),
    ("positionfrom() abbreviated", lambda w, o, i: w.wm_positionfrom()),
    ("positionfrom('bad')", lambda w, o, i: w.wm_positionfrom("bad")),
    ("sizefrom('program')", lambda w, o, i: w.wm_sizefrom("program")),
    ("sizefrom() again", lambda w, o, i: w.sizefrom()),
    ("sizefrom('')", lambda w, o, i: w.wm_sizefrom("")),
    ("sizefrom() cleared", lambda w, o, i: w.wm_sizefrom()),
    ("colormapwindows()", lambda w, o, i: w.wm_colormapwindows()),
    ("colormapwindows(other)", lambda w, o, i: w.wm_colormapwindows(o)),
    ("colormapwindows() again", lambda w, o, i: w.colormapwindows()),
    ("colormapwindows('.nope')", lambda w, o, i: w.wm_colormapwindows(".nope")),
]


def _run(window: Any, other: Any, image: Any, errors: tuple[type, ...]) -> list:
    """Every step's answer or refusal, with the other window's path, which
    differs between the two libraries, written as OTHER."""
    path = str(other)
    answers = []
    for label, step in STEPS:
        try:
            answer: Any = step(window, other, image)
        except errors as error:
            answers.append((label, "error", str(error)))
            continue
        if isinstance(answer, list):
            answer = ["OTHER" if str(item) == path else item for item in answer]
        elif answer is not None and not isinstance(answer, tuple):
            answer = "OTHER" if str(answer) == path else str(answer)
        answers.append((label, answer))
    return answers


@pytest.fixture
def real_root():
    try:
        root = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    root.withdraw()
    yield root
    root.destroy()


def test_the_hints_answer_and_refuse_as_tks_do(real_root):
    window = tkinter.Toplevel(real_root)
    theirs = _run(
        window,
        tkinter.Toplevel(real_root),
        tkinter.PhotoImage(master=real_root, width=4, height=4),
        (tkinter.TclError,),
    )

    root = tkcurses.Misc()
    ours = _run(
        tkcurses.Toplevel(root),
        tkcurses.Toplevel(root),
        tkcurses.PhotoImage(master=root, width=4, height=4),
        (tkcurses.TclError,),
    )
    assert ours == theirs


def test_a_hint_is_kept_per_window():
    root = tkcurses.Misc()
    first, second = tkcurses.Toplevel(root), tkcurses.Toplevel(root)
    first.wm_iconname("first")
    assert second.wm_iconname() == ""
    assert first.wm_iconname() == "first"
