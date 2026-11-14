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

"""Tk's busy command: a window that the pointer does not reach.

The answers are compared with real tkinter call by call; what reaches a
busy window is checked in a real terminal. Tk's busy window takes the
pointer and nothing else - its manual says keyboard events still reach a
widget with the focus - and the same is held here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

import tkcurses

if TYPE_CHECKING:
    from collections.abc import Callable

tkinter = pytest.importorskip("tkinter")

#: Each a call on (root, frame, child of the frame, entry), in order.
STEPS: list[tuple[str, Callable[[Any, Any, Any, Any], Any]]] = [
    ("status before", lambda r, f, b, e: f.tk_busy_status()),
    ("cget before", lambda r, f, b, e: f.tk_busy_cget("cursor")),
    ("current before", lambda r, f, b, e: r.tk_busy_current()),
    ("forget before", lambda r, f, b, e: f.tk_busy_forget()),
    ("configure before", lambda r, f, b, e: f.tk_busy_configure()),
    ("hold", lambda r, f, b, e: f.tk_busy_hold()),
    ("hold again", lambda r, f, b, e: f.busy_hold(cursor="watch")),
    ("status", lambda r, f, b, e: f.busy_status()),
    ("child's status", lambda r, f, b, e: b.tk_busy_status()),
    ("current", lambda r, f, b, e: r.tk_busy_current()),
    ("current matching", lambda r, f, b, e: r.busy_current("*frame*")),
    ("current not", lambda r, f, b, e: r.tk_busy_current("x")),
    ("cget", lambda r, f, b, e: f.busy_cget("cursor")),
    ("cget unknown", lambda r, f, b, e: f.tk_busy_cget("bogus")),
    ("configure()", lambda r, f, b, e: f.tk_busy_configure()),
    ("configure(name)", lambda r, f, b, e: f.busy_configure("cursor")),
    ("configure bad", lambda r, f, b, e: f.tk_busy_configure(cursor="nonsense")),
    ("configure unknown", lambda r, f, b, e: f.busy_config(bogus=1)),
    ("hold unknown", lambda r, f, b, e: e.tk_busy_hold(bogus=1)),
    ("held all the same", lambda r, f, b, e: e.tk_busy_status()),
    ("forget", lambda r, f, b, e: f.busy_forget()),
    ("status after", lambda r, f, b, e: f.tk_busy_status()),
    ("forget again", lambda r, f, b, e: f.tk_busy_forget()),
    ("hold the root", lambda r, f, b, e: r.busy()),
    ("root's status", lambda r, f, b, e: r.tk_busy_status()),
    ("forget the root", lambda r, f, b, e: r.tk_busy_forget()),
]


def _run(root: Any, errors: tuple[type, ...], module: Any) -> list:
    frame = module.Frame(root)
    frame.pack()
    child = module.Button(frame, text="x")
    child.pack()
    entry = module.Entry(root)
    entry.pack()
    answers = []
    for label, step in STEPS:
        try:
            answer = step(root, frame, child, entry)
        except errors as error:
            answers.append((label, "error", str(error)))
            continue
        if isinstance(answer, list):
            answer = [str(item) for item in answer]
        elif isinstance(answer, dict):
            answer = {k: tuple(str(v) for v in t) for k, t in answer.items()}
        elif isinstance(answer, tuple):
            answer = tuple(str(v) for v in answer)
        answers.append((label, answer))
    return answers


def test_busy_answers_and_refuses_as_tks_does():
    try:
        real = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    real.withdraw()
    try:
        theirs = _run(real, (tkinter.TclError,), tkinter)
    finally:
        real.destroy()
    ours = _run(tkcurses.Misc(), (tkcurses.TclError,), tkcurses)
    assert ours == theirs


def test_a_destroyed_busy_window_is_no_longer_current():
    root = tkcurses.Misc()
    frame = tkcurses.Frame(root)
    frame.tk_busy_hold()
    frame.destroy()
    assert root.tk_busy_current() == []


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
held = tkcurses.Frame(root)
held.place(x=2, y=2)
box = tkcurses.Checkbutton(held, text='Wrap')
box.pack()
entry = tkcurses.Entry(held, width=10)
entry.pack()
entry.focus_set()
held.tk_busy_hold()
{body}
root.after(4000, root.quit)
root.mainloop()
"""


def _box_and_entry(box: str, entry: str) -> Callable[[Any], bool]:
    return lambda t: box in t.row(2) and entry in t.row(4)


@pytest.mark.tty
def test_a_busy_window_takes_no_click_and_still_takes_keys(terminal, tmp_path):
    """The click comes first and the key after, so once the key's letter is
    in the entry the click has been handled - and dropped."""
    term = terminal(cols=40, rows=12)
    term.run_source(program(""), workdir=tmp_path)
    term.wait_for_text("Wrap")
    term.click(5, 2)
    term.send(b"a")
    term.wait_for(_box_and_entry("[ ] Wrap", "a"), message="the key and no tick")


@pytest.mark.tty
def test_a_forgotten_busy_window_takes_clicks_again(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("entry.bind('<Key-z>', lambda e: held.tk_busy_forget())"),
        workdir=tmp_path,
    )
    term.wait_for_text("Wrap")
    term.send(b"z")
    term.wait_for(_box_and_entry("[ ] Wrap", "z"), message="the z")
    term.click(5, 2)
    term.wait_for(_box_and_entry("[x] Wrap", "z"), message="the tick")
