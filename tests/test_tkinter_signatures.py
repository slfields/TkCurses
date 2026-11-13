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

"""A call that works positionally in tkinter works here, and means the same.

``Treeview.insert("", "end", "mine")`` raised TypeError because ``iid`` was
keyword-only here; ``PhotoImage.write("x.png", "png")`` passed ``"png"`` as
a palette. Comparing every shared method's signature with the running
tkinter's finds the class of fault, and the behaviour tests below hold each
fix to what Tk 9.0.2 was measured doing.
"""

from __future__ import annotations

import inspect

import pytest

import tkcurses as tk
from tests.test_method_surface import PAIRS, _methods
from tkcurses import ttk
from tkcurses._core.geometry import Rect

_POSITIONAL = (
    inspect.Parameter.POSITIONAL_ONLY,
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
)

#: (class label, method) pairs still taking fewer positional arguments than
#: tkinter's, each owned by an issue. Only ever shrinks.
KNOWN_GAPS: frozenset[tuple[str, str]] = frozenset()


def _positional(function: object) -> list[str] | None:
    """The names a call may give positionally, past ``self``; None when
    there is no limit or no signature to read."""
    try:
        parameters = list(inspect.signature(function).parameters.values())  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in parameters):
        return None
    return [p.name for p in parameters if p.kind in _POSITIONAL][1:]


def _shortfalls() -> dict[tuple[str, str], tuple[list[str], list[str]]]:
    found = {}
    for label, ours, theirs in PAIRS:
        for name in _methods(theirs):
            if not hasattr(ours, name):
                continue
            mine = _positional(getattr(ours, name))
            tkinters = _positional(getattr(theirs, name))
            if mine is not None and tkinters is not None and len(mine) < len(tkinters):
                found[(label, name)] = (mine, tkinters)
    return found


def test_the_comparison_reads_signatures():
    """Guards against passing by reading nothing."""
    assert _positional(tk.Misc.winfo_containing) == ["rootX", "rootY", "displayof"]
    assert len(PAIRS) > 40


def test_no_method_takes_fewer_positional_arguments_than_tkinters():
    unexplained = {
        key: value for key, value in _shortfalls().items() if key not in KNOWN_GAPS
    }
    assert not unexplained, (
        "these take fewer positional arguments than tkinter's, so a call that"
        f" works there fails or means something else here: {unexplained}"
    )


def test_every_known_gap_is_still_a_gap():
    assert not (KNOWN_GAPS - set(_shortfalls()))


# --------------------------------------------------------------- the fixes


@pytest.fixture
def root():
    window = tk.Tk(useTk=False)
    yield window
    window.destroy()


def test_winfo_containing_takes_displayof(root):
    frame = tk.Frame(root)
    root._rect, root._mapped = Rect(0, 0, 20, 10), True
    frame._rect, frame._mapped = Rect(2, 1, 5, 3), True
    assert root.winfo_containing(3, 2, root) is frame


def test_canvas_tag_bind_returns_a_handle_tag_unbind_takes(root):
    """Measured on Tk 9.0.2: the handle removes only its own binding, the
    sequences bound are listed, and unbinding by sequence removes all."""
    canvas = tk.Canvas(root)
    canvas.create_rectangle(0, 0, 3, 3, tags="box")
    first = canvas.tag_bind("box", "<1>", lambda event: None)
    second = canvas.tag_bind("box", "<1>", print, add="+")
    assert isinstance(first, str) and first != second
    assert canvas.tag_bind("box") == ("<1>",)
    assert canvas.tag_bind("nothing") == ()
    canvas.tag_unbind("box", "<1>", first)
    assert canvas.tag_bind("box", "<1>") == (print,)
    canvas.tag_unbind("box", "<1>")
    assert canvas.tag_bind("box", "<1>") == ()
    assert canvas.tag_bind("box") == ()


def test_paneconfigure_reads_as_tk_does(root):
    """Tk 9.0.2's five-tuples for the options a pane takes here."""
    paned = tk.PanedWindow(root)
    label = tk.Label(paned, text="x")
    paned.add(label, minsize=3, sticky="n")
    assert paned.paneconfigure(label) == {
        "height": ("height", "", "", "", ""),
        "minsize": ("minsize", "", "", 0, 3),
        "sticky": ("sticky", "", "", "nsew", "n"),
        "stretch": ("stretch", "stretch", "Stretch", "last", "last"),
        "width": ("width", "", "", "", ""),
    }
    assert paned.paneconfigure(label, "sticky") == ("sticky", "", "", "nsew", "n")
    assert paned.paneconfig(label, {"minsize": 5}) is None
    assert paned.panecget(label, "minsize") == 5
    with pytest.raises(tk.TclError, match='unknown option "-zz"'):
        paned.paneconfigure(label, "zz")


def test_ttk_scale_get_answers_the_value_at_a_point(root):
    """The value whose slider centres there, clamped at the ends, the other
    axis ignored and the value left alone - as Tk 9.0.2 answers."""
    scale = ttk.Scale(root, from_=0, to=100, length=21, value=40)
    scale.place(x=0, y=0)
    root.update_layout()
    for value in (0, 25, 50, 100):
        assert scale.get(*scale.coords(value)) == value
    x, y = scale.coords(50)
    assert scale.get(x, y + 99) == 50
    assert scale.get(-50, 0) == 0
    assert scale.get(500, 0) == 100
    assert scale.get() == 40
    with pytest.raises(tk.TclError, match=r"get \?x y\?"):
        scale.get(5)
