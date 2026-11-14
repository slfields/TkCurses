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

"""The rest of tkinter's Misc: the screen asked about, atoms, ``send``, the
version, and the palette.

Where an answer can only be the terminal's - its size in millimetres, its
visual - the answer is checked for its shape and its consistency with the
rest of this library. Where it can be Tk's - an atom's number, a refusal, a
palette's colours - it is compared with real tkinter.
"""

from __future__ import annotations

import contextlib
import re
from typing import Any

import pytest

import tkcurses
from tkcurses._core.colors import ColorDepth

tkinter = pytest.importorskip("tkinter")


@pytest.fixture
def real_root():
    try:
        root = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    root.withdraw()
    yield root
    root.destroy()


def _answers(root: Any, errors: tuple[type, ...]) -> list:
    found = []

    def ask(label: str, call: Any) -> None:
        try:
            found.append((label, call()))
        except errors as error:
            found.append((label, "error", str(error)))

    ask("root's name", root.winfo_name)
    ask("interps", root.winfo_interps)
    ask("PRIMARY", lambda: root.winfo_atom("PRIMARY"))
    ask("atom 68", lambda: root.winfo_atomname(68))
    ask("a new atom is kept", lambda: root.winfo_atomname(root.winfo_atom("TKC")))
    ask("same number again", lambda: root.winfo_atom("TKC") == root.winfo_atom("TKC"))
    ask("atomname of text", lambda: root.winfo_atomname("x"))
    ask("pathname of text", lambda: root.winfo_pathname("x"))
    ask("pathname of 1", lambda: root.winfo_pathname(1))
    ask("the root by its id", lambda: root.winfo_pathname(root.winfo_id()))
    ask("send elsewhere", lambda: root.send("nobody", "set", "x", "1"))
    ask("colormapfull", root.winfo_colormapfull)
    ask("vroot", lambda: (root.winfo_vrootx(), root.winfo_vrooty()))
    ask("patchlevel", lambda: tuple(root.info_patchlevel()))
    ask("patchlevel fields", lambda: root.info_patchlevel()._fields)
    ask(
        "strictMotif",
        lambda: (
            root.tk_strictMotif(),
            root.tk_strictMotif(1),
            root.tk_strictMotif(),
            root.tk_strictMotif("no"),
        ),
    )
    return found


def _alone(answers: list) -> list:
    """Tk's answers as they would be with no other Tk on the display.

    The name and the interpreter list are the X server's, shared by every
    Tk application on it: a second one open at the same moment is named
    ``tk #2`` and both are listed. Measured with two in one process -
    ``'tk #2' ('tk #2', 'tk')``. Under ``pytest -n 4`` that second one is
    another worker's test, so the comparison failed once in a while and
    never alone. TkCurses has no display to share and always answers as
    the only one.
    """
    alone = []
    for answer in answers:
        if answer[0] == "root's name":
            answer = (answer[0], re.sub(r" #\d+$", "", answer[1]))
        elif answer[0] == "interps":
            mine = next(a[1] for a in alone if a[0] == "root's name")
            names = {re.sub(r" #\d+$", "", name) for name in answer[1]}
            answer = (answer[0], (mine,) if mine in names else ())
        alone.append(answer)
    return alone


def test_the_answers_tk_can_give_are_tks(real_root):
    ours = _answers(tkcurses.Misc(), (tkcurses.TclError,))
    theirs = _alone(_answers(real_root, (tkinter.TclError,)))
    # The atom made for "TKC" is numbered by the server in Tk and from 69
    # here; both keep it and give it back, which is what is compared.
    assert ours == theirs


def test_the_comparison_holds_with_another_tk_open(real_root):
    """The race made certain: a second Tk, as another worker's would be."""
    second = tkinter.Tk()
    second.withdraw()
    try:
        assert second.winfo_name() != "tk"
        ours = _answers(tkcurses.Misc(), (tkcurses.TclError,))
        assert ours == _alone(_answers(second, (tkinter.TclError,)))
    finally:
        second.destroy()


def test_the_screen_is_described_in_cells_at_ten_to_the_inch():
    root = tkcurses.Misc()
    width, height = root.winfo_screenwidth(), root.winfo_screenheight()
    assert root.winfo_screenmmwidth() == round(width * 2.54)
    assert root.winfo_screenmmheight() == round(height * 2.54)
    assert root.winfo_screencells() == root.winfo_cells()


@pytest.mark.parametrize(
    ("depth", "visual"),
    [
        (ColorDepth.NONE, "staticgray"),
        (ColorDepth.BASIC, "staticcolor"),
        (ColorDepth.EXTENDED, "staticcolor"),
        (ColorDepth.DIRECT, "truecolor"),
    ],
)
def test_the_visual_follows_the_terminals_colour(monkeypatch, depth, visual):
    root = tkcurses.Misc()
    monkeypatch.setattr(type(root), "winfo_colordepth", lambda self: depth)
    assert root.winfo_visual() == visual
    assert root.winfo_screenvisual() == visual
    assert root.winfo_visualsavailable() == [(visual, root.winfo_depth())]
    found = root.winfo_visualsavailable(includeids=True)
    assert found == [(visual, root.winfo_depth(), int(root.winfo_visualid(), 16))]


def test_send_to_itself_runs_the_command():
    root = tkcurses.Misc()
    assert root.send(root.winfo_name(), "info", "patchlevel") == "9.0.2"


# -------------------------------------------------------------- palette

OPTIONS = (
    "background", "foreground", "activebackground", "activeforeground",
    "disabledforeground", "highlightbackground", "highlightcolor",
    "insertbackground", "selectbackground", "selectforeground", "troughcolor",
    "selectcolor", "buttonbackground",
)  # fmt: skip

PALETTES = {
    "one colour": lambda r: r.tk_setPalette("#336699"),
    "named": lambda r: r.tk_setPalette(background="#eeeeee", selectForeground="green"),
    "pairs": lambda r: r.tk_setPalette("background", "black", "foreground", "yellow"),
    "bisque": lambda r: r.tk_bisque(),
    "no background": lambda r: r.tk_setPalette(foreground="red"),
    "odd": lambda r: r.tk_setPalette("a", "b", "c"),
}


def _palette(module: Any, root: Any, apply: Any) -> list:
    """Each widget's colours after a palette, a widget made after it, and
    what the option database answers."""
    widgets = {
        "button": module.Button(root),
        "red button": module.Button(root, bg="red"),
        "entry": module.Entry(root),
        "scrollbar": module.Scrollbar(root),
        "check": module.Checkbutton(root),
        "spinbox": module.Spinbox(root),
    }
    try:
        apply(root)
    except module.TclError as error:
        return ["error", str(error)]
    widgets["made after"] = module.Button(root)
    found: list = []
    for name, widget in widgets.items():
        for option in OPTIONS:
            with contextlib.suppress(module.TclError):
                found.append((name, option, widget.cget(option)))
    found.append(root.option_get("background", "Background"))
    found.append(root.option_get("troughColor", "TroughColor"))
    return found


@pytest.mark.parametrize("palette", sorted(PALETTES))
def test_a_palette_colours_as_tks_does(palette):
    try:
        real = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    try:
        theirs = _palette(tkinter, real, PALETTES[palette])
    finally:
        real.destroy()
    ours = _palette(tkcurses, tkcurses.Misc(), PALETTES[palette])
    assert ours == theirs
