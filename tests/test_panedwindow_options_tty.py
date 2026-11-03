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

"""A PanedWindow's proxy on a real terminal. TkCurses-gm66.9.

With ``opaqueresize`` off a drag moves a line over the panes and leaves them
alone until the release. The line is its own panel, so it has to show over a
pane's own window - which only a real terminal composes.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def test_a_proxy_shows_over_the_pane_until_the_release(terminal, tmp_path):
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
panes = tkcurses.PanedWindow(root, opaqueresize=False, showhandle=False)
panes.place(x=0, y=0, width=21, height=4)
for name in ("left", "right"):
    pane = tkcurses.Frame(panes, width=10, height=4)
    tkcurses.Label(pane, text=name).place(x=0, y=0)
    panes.add(pane)
root.after(4000, root.quit)
root.mainloop()
root.destroy()
""",
        workdir=tmp_path,
    )

    def column(t):
        return [x for x in range(21) if t.display[2][x] == "│"]

    term.wait_for(
        lambda t: column(t) == [10] and "right" in t.display[0], message="the sash"
    )
    term.send_mouse(10, 2, action="press")
    term._drain(0.08)
    term.send_mouse(4, 2, action="move", button=1)
    term.wait_for(
        lambda t: column(t) == [4, 10] and t.display[0].index("right") == 11,
        message="a proxy over the left pane, the panes not yet moved",
    )
    term.send_mouse(4, 2, action="release")
    term.wait_for(
        lambda t: column(t) == [4] and t.display[0].index("right") == 5,
        message="the sash moved to the proxy and the proxy gone",
    )
