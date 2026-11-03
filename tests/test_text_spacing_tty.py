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

"""Line spacing on a real terminal: blank rows between lines. TkCurses-gm66.8."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def test_spacing_puts_blank_rows_between_lines(terminal, tmp_path):
    term = terminal(cols=20, rows=10)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
text = tkcurses.Text(root, width=10, height=8, spacing1=1, spacing3=1,
                     relief="flat", highlightthickness=0)
text.insert("1.0", "first\\nsecond")
text.place(x=0, y=0)
root.after(4000, root.quit)
root.mainloop()
root.destroy()
""",
        workdir=tmp_path,
    )

    def laid_out(t):
        rows = [line.strip() for line in t.display[:5]]
        return rows == ["", "first", "", "", "second"]

    term.wait_for(laid_out, message="the two lines, three rows apart")
