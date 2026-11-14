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

"""Tk's ``image`` command, reached through ``tk.call``, against real tkinter.

tkinter's own ``image_names`` and ``image_types`` go this way, and so does a
program that deletes an image by name. Every subcommand is run in order on
both libraries, and every answer and refusal must be the same - except that
Tk keeps message-box icons of its own, ``::tk::icons::...``, and this
library has none.
"""

from __future__ import annotations

from typing import Any

import pytest

import tkcurses

tkinter = pytest.importorskip("tkinter")

XBM = "#define t_width 4\n#define t_height 2\nstatic unsigned char t_bits[] = { 0x0f, 0x09 };\n"

#: Each step is a tk.call, in order, on an application holding a 4x6 photo
#: "pic" shown by a label, and a 4x2 bitmap "bits".
STEPS: list[tuple[Any, ...]] = [
    ("image",),
    ("image", "bogus"),
    ("image", "names"),
    ("image", "names", "x"),
    ("image", "types"),
    ("image", "types", "x"),
    ("image", "type", "pic"),
    ("image", "type", "bits"),
    ("image", "type", "nope"),
    ("image", "type"),
    ("image", "width", "pic"),
    ("image", "height", "pic"),
    ("image", "width", "bits"),
    ("image", "height", "nope"),
    ("image", "inuse", "pic"),
    ("image", "inuse", "bits"),
    ("image", "inuse", "nope"),
    ("image", "delete"),
    ("image", "delete", "nope"),
    ("image", "delete", "bits", "pic"),
    ("image", "names"),
    ("image", "create", "photo", "made", "-width", "2", "-height", 3),
    ("image", "width", "made"),
    ("image", "height", "made"),
    ("image", "create", "photo"),
    ("image", "create", "nope"),
    ("image", "create"),
    ("image", "create", "bitmap", "bm2", "-foreground", "red"),
    ("image", "create", "photo", "bad", "-zzz", "1"),
    ("image", "create", "photo", "odd", "-width"),
    ("image", "names"),
    ("image", "delete", "made", "image1", "bm2"),
    ("image", "names"),
]


def _run(module: Any, root: Any) -> list:
    picture = module.PhotoImage(master=root, name="pic", width=4, height=6)
    module.BitmapImage(master=root, name="bits", data=XBM)
    label = module.Label(root, image=picture)
    found: list = []
    for step in STEPS:
        try:
            answer = root.tk.call(*step)
        except module.TclError as error:
            found.append((step, "error", str(error)))
            continue
        if isinstance(answer, tuple):
            answer = sorted(str(a) for a in answer if not str(a).startswith("::tk::"))
        found.append((step, answer))
    found.append(("label keeps the name", str(label.cget("image"))))
    try:
        found.append(("deleted object's width", picture.width()))
    except module.TclError as error:
        found.append(("deleted object's width", str(error)))
    found.append(("image_types", root.image_types()))
    return found


def test_the_image_command_answers_as_tks_does():
    try:
        real = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    try:
        theirs = _run(tkinter, real)
    finally:
        real.destroy()
    assert _run(tkcurses, tkcurses.Misc()) == theirs


def test_an_image_made_by_the_command_lasts_until_it_is_deleted():
    """Nothing in Python refers to it, and it must not be collected."""
    import gc

    root = tkcurses.Misc()
    name = root.tk.call("image", "create", "photo", "-width", 3, "-height", 3)
    gc.collect()
    assert root.tk.call("image", "width", name) == 3
    root.tk.call("image", "delete", name)
    gc.collect()
    assert name not in root.image_names()


def test_a_deleted_image_leaves_its_label_drawing_nothing_at_its_size():
    root = tkcurses.Misc()
    picture = tkcurses.PhotoImage(master=root, width=4, height=4)
    label = tkcurses.Label(root, image=picture)
    before = label.winfo_reqwidth(), label.winfo_reqheight()
    root.tk.call("image", "delete", str(picture))
    assert label._image() is None
    assert (label.winfo_reqwidth(), label.winfo_reqheight()) == before
