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

"""tkinter's validation idiom: a registered command with Tk's percent codes.

``validatecommand=(root.register(check), "%P")`` is how tkinter programs
validate. Every path an edit can take - insert, delete, a key, Backspace,
typing over a selection, the focus, a variable write, ``validate()``, a
Spinbox arrow - is run on real tkinter and here, and each substitution
compared.
"""

from __future__ import annotations

from typing import Any

import pytest

import tkcurses
from tkcurses import ttk

tkinter = pytest.importorskip("tkinter")
real_ttk = pytest.importorskip("tkinter.ttk")

CODES = ("%d", "%i", "%P", "%s", "%S", "%v", "%V", "%W")


def _scenario(tk: Any, themed: Any, root: Any) -> list:
    """What each validator was called with, path by path. Path names are
    left out: the two libraries number their widgets differently."""
    log: list = []

    def heard(*args: str) -> bool:
        log.append(args[:-1])
        return True

    def run(label: str, action: Any) -> None:
        log.clear()
        action()
        root.update()
        results.append((label, list(log)))

    results: list = []
    for cls in (tk.Entry, themed.Entry):
        var = tk.StringVar(root, value="abcd")
        entry = cls(
            root,
            textvariable=var,
            validate="all",
            validatecommand=(root.register(heard), *CODES),
        )
        entry.pack()
        root.update()
        run("insert", lambda e=entry: e.insert(1, "XY"))
        run("delete range", lambda e=entry: e.delete(0, 2))
        run("delete one", lambda e=entry: e.delete(1))
        run("focus in", lambda e=entry: (e.focus_force(), root.update()))
        entry.icursor(2)
        run("key", lambda e=entry: e.event_generate("<KeyPress>", keysym="z"))
        run("BackSpace", lambda e=entry: e.event_generate("<KeyPress-BackSpace>"))
        entry.selection_range(0, 2)
        entry.icursor(2)
        run("over a selection", lambda e=entry: e.event_generate("<KeyPress-q>"))
        run("variable write", lambda v=var: v.set("new"))
        if hasattr(entry, "validate"):
            run("validate()", entry.validate)
    spinbox = tk.Spinbox(
        root,
        from_=0,
        to=5,
        validate="all",
        validatecommand=(root.register(heard), *CODES),
    )
    spinbox.pack()
    root.update()
    run("spinbox arrow", lambda: spinbox.invoke("buttonup"))
    return results


def _outcomes(tk: Any, root: Any) -> list:
    """What a validator's answer does: the text, and whether validation is
    still on."""
    found = []
    for answer in (None, "no", 0, "yes"):
        entry = tk.Entry(
            root,
            validate="key",
            validatecommand=(root.register(lambda p, a=answer: a), "%P"),
        )
        entry.insert(0, "x")
        found.append((repr(answer), entry.get(), entry.cget("validate")))
    digits = tk.Entry(
        root,
        validate="key",
        validatecommand=(root.register(lambda p: p.isdigit()), "%P"),
    )
    digits.insert(0, "12")
    digits.insert(0, "x")
    found.append(("digits", digits.get(), digits.cget("validate")))
    script = tk.Entry(
        root,
        validate="key",
        validatecommand=root.register(lambda *a: found.append(a) or True) + " %P %% %z",
    )
    script.insert(0, "q")
    named = tk.Entry(root, validate="key", validatecommand=("nosuchcommand", "%P"))
    named.insert(0, "q")
    found.append(("unknown name", named.get(), named.cget("validate")))
    found.append(("cget", digits.cget("validatecommand").split(" ")[1:]))
    return found


@pytest.fixture
def real_root():
    try:
        root = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    root.report_callback_exception = lambda *args: None
    yield root
    root.destroy()


def test_every_path_substitutes_as_tk_does(real_root):
    theirs = _scenario(tkinter, real_ttk, real_root)
    ours = _scenario(tkcurses, ttk, tkcurses.Misc())
    assert ours == theirs


def test_the_answer_is_read_as_tk_reads_it(real_root):
    assert _outcomes(tkcurses, tkcurses.Misc()) == _outcomes(tkinter, real_root)


def test_backspace_over_a_selection_asks_the_validator():
    """It used to delete the selection without asking."""
    root = tkcurses.Misc()
    entry = tkcurses.Entry(root)
    entry.insert(0, "abcd")
    entry.configure(validate="key", validatecommand=lambda text: False)
    entry.selection_range(0, 2)
    entry.event_generate("<KeyPress-BackSpace>")
    assert entry.get() == "abcd"


def test_a_validator_taking_nothing_is_called_with_nothing():
    """tkinter calls a plain callable with no arguments."""
    root = tkcurses.Misc()
    calls = []
    entry = tkcurses.Entry(
        root, validate="key", validatecommand=lambda: calls.append(1) or True
    )
    entry.insert(0, "q")
    assert (calls, entry.get(), entry.cget("validate")) == ([1], "q", "key")


def test_deletecommand_forgets_a_registered_name():
    root = tkcurses.Misc()
    name = root.register(lambda: True)
    root.deletecommand(name)
    entry = tkcurses.Entry(root, validate="key", validatecommand=name)
    entry.insert(0, "q")
    assert (entry.get(), entry.cget("validate")) == ("", "none")


@pytest.mark.parametrize(
    ("keysym", "char"),
    [("z", "z"), ("space", " "), ("Return", "\r"), ("BackSpace", "\b"),
     ("Tab", "\t"), ("Escape", "\x1b"), ("Delete", "\x7f"), ("Up", ""),
     ("plus", "+"), ("F1", "")],
)  # fmt: skip
def test_a_generated_key_carries_its_character(keysym, char):
    """As Tk 9.0.2 reports for a generated key event."""
    root = tkcurses.Misc()
    heard = []
    root.bind("<Key>", lambda event: heard.append(event.char))
    root.event_generate("<KeyPress>", keysym=keysym)
    assert heard == [char]


def test_a_generated_event_may_wait_for_the_queue():
    root = tkcurses.Misc()
    heard = []
    root.bind("<<Ping>>", lambda event: heard.append(1))
    root.event_generate("<<Ping>>", when="tail")
    assert heard == []
    root.update()
    assert heard == [1]
    with pytest.raises(tkcurses.TclError, match='bad -when value "x"'):
        root.event_generate("<<Ping>>", when="x")
