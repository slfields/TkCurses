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

"""wm_manage and wm_forget, measured against Tk 9.0.2 through tkinter."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

PROGRAM = """
import tkcurses

root = tkcurses.Tk()
tkcurses.Label(root, text="main window").pack(anchor="w")
frame = tkcurses.Frame(root, name="f", width=20, height=5, bd=1, relief="solid")
frame.pack(anchor="w")
inner = tkcurses.Label(frame, text="inside")
inner.place(x=1, y=1)
inner.bind("<Key-a>", lambda event: None)
report = tkcurses.Label(root, text="", anchor="w", width={cols})
report.place(x=0, y=22)


def show(*words):
    report.configure(text=" ".join(str(word) for word in words) + " .")


{body}
root.after(6000, root.quit)
root.mainloop()
"""


def run(terminal, tmp_path, body, cols=80):
    term = terminal(cols=cols, rows=24)
    term.run_source(PROGRAM.format(body=body, cols=cols), workdir=tmp_path)
    return term


def reported(term, text):
    term.wait_for(lambda t: t.display[22].rstrip().endswith(text + " ."))


def test_a_managed_frame_is_a_window_of_its_own(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "root.wm_manage(frame)\n"
        "root.update_idletasks()\n"
        "show(frame.winfo_manager(), frame.winfo_toplevel(), inner.winfo_toplevel(),"
        " frame not in root.pack_slaves(), int(frame.winfo_ismapped()), frame.winfo_parent(),"
        " frame.winfo_width(), frame.winfo_height())",
    )
    reported(term, "wm .f .f True 1 . 20 5")
    # Centred on 80x24, as a new toplevel is: columns 30-49, rows 9-13.
    term.wait_for(lambda t: t.display[11][32:38] == "inside")
    assert term.display[9][30] == "┌"


def test_a_managed_frame_refuses_the_geometry_managers(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "root.wm_manage(frame)\n"
        "said = []\n"
        "for call in (frame.pack, frame.grid, lambda: frame.place(x=0, y=0)):\n"
        "    try:\n"
        "        call()\n"
        "    except tkcurses.TclError as error:\n"
        "        said.append(str(error))\n"
        "show(' | '.join(said))",
        cols=170,
    )
    reported(
        term,
        "can't pack \".f\": it's a top-level window"
        " | can't manage \".f\": it's a top-level window"
        ' | can\'t use placer on top-level window ".f"; use wm command instead',
    )


def test_forget_hands_it_back_with_its_children_and_bindings(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "root.wm_manage(frame)\n"
        "root.wm_forget(frame)\n"
        "root.update_idletasks()\n"
        "before = (repr(frame.winfo_manager()), int(frame.winfo_ismapped()),"
        " frame.winfo_toplevel())\n"
        "frame.pack(anchor='w')\n"
        "root.update_idletasks()\n"
        "show(*before, frame.winfo_manager(), int(frame.winfo_ismapped()),"
        " inner.winfo_toplevel(), inner.bind(), frame.winfo_children() == [inner])",
    )
    reported(term, "'' 0 . pack 1 . ('<Key-a>',) True")
    term.wait_for(lambda t: t.display[3][2:8] == "inside")


@pytest.mark.parametrize(
    ("make", "name"),
    [("tkcurses.Button", "b"), ("tkcurses.Canvas", "c"), ("ttk.Frame", "t")],
)
def test_only_a_classic_frame_labelframe_or_toplevel_can_be(
    terminal, tmp_path, make, name
):
    term = run(
        terminal,
        tmp_path,
        "from tkcurses import ttk\n"
        f"widget = {make}(root, name='{name}')\n"
        "try:\n"
        "    root.wm_manage(widget)\n"
        "except tkcurses.TclError as error:\n"
        "    show(error)",
    )
    reported(
        term,
        f'window ".{name}" is not manageable: must be a frame, labelframe or toplevel',
    )


def test_a_labelframe_can_be(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "box = tkcurses.LabelFrame(root, text='box', width=10, height=4)\n"
        "box.pack()\n"
        "root.wm_manage(box)\n"
        "show(box.winfo_manager(), box.winfo_toplevel() is box)",
    )
    reported(term, "wm True")


def test_a_toplevel_forgotten_is_unmapped_and_managed_again(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "top = tkcurses.Toplevel(root, name='t')\n"
        "root.wm_forget(top)\n"
        "gone = (int(top.winfo_ismapped()), top.winfo_toplevel())\n"
        "root.wm_manage(top)\n"
        "show(*gone, int(top.winfo_ismapped()), top.winfo_toplevel())",
    )
    reported(term, "0 . 1 .t")


def test_the_root_and_a_plain_frame_are_left_alone_by_forget(terminal, tmp_path):
    term = run(
        terminal,
        tmp_path,
        "root.wm_forget(root)\n"
        "root.wm_forget(frame)\n"
        "show(frame.winfo_manager(), int(frame.winfo_ismapped()))",
    )
    reported(term, "pack 1")
