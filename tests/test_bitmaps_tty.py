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

"""What a bitmap puts on the terminal: a named one's glyph, a file's bits."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

XBM = "#define t_width 4\n#define t_height 2\nstatic unsigned char t_bits[] = { 0x0f, 0x09 };\n"


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
{body}
root.after(4000, root.quit)
root.mainloop()
"""


def test_a_named_bitmap_is_its_glyph_in_the_foreground(terminal, tmp_path):
    term = terminal(cols=30, rows=6)
    term.run_source(
        program(
            "tkcurses.Label(root, bitmap='warning', foreground='cyan',"
            " borderwidth=0).place(x=3, y=2)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_cell(2, 3, lambda cell: cell.data == "⚠" and cell.fg == "cyan")


def test_compound_puts_the_text_beside_it(terminal, tmp_path):
    term = terminal(cols=30, rows=6)
    term.run_source(
        program(
            "tkcurses.Label(root, bitmap='error', text='Failed', compound='left',"
            " borderwidth=0).place(x=0, y=1)"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: t.display[1].startswith("✖ Failed"))


def test_a_file_draws_its_bits(terminal, tmp_path):
    """Row one has all four bits, row two the outer two: the outer cells
    are full, the inner ones lit only on top."""
    (tmp_path / "t.xbm").write_text(XBM)
    term = terminal(cols=30, rows=6)
    term.run_source(
        program(
            f"tkcurses.Label(root, bitmap='@{tmp_path / 't.xbm'}',"
            " borderwidth=0).place(x=2, y=1)"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: t.display[1][2:6] == "█▀▀█")


def test_a_dialog_shows_its_bitmap_beside_the_message(terminal, tmp_path):
    term = terminal(cols=60, rows=14)
    term.run_source(
        program(
            "from tkcurses.dialog import Dialog\n"
            "root.after(50, lambda: Dialog(root, title='Q', text='Really quit?',"
            " bitmap='warning', default=0, strings=('Yes', 'No')))"
        ),
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: any(
            "⚠" in line
            and "Really quit?" in line
            and line.index("⚠") < line.index("Really quit?")
            for line in t.display
        )
    )
