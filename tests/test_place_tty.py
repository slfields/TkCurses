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

"""place over packed content, driven through a real pseudo-terminal."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def test_a_badge_placed_over_packed_content_is_drawn_on_top(terminal, tmp_path):
    # The overlay Tk allows: place in a container that packs. TkCurses-huq9.
    term = terminal(cols=30, rows=6)
    term.run_source(
        "import tkcurses as tk\n"
        "root = tk.Tk()\n"
        'tk.Label(root, text="packed row", anchor="w").pack(fill="x")\n'
        'tk.Label(root, text="[3]").place(relx=1.0, anchor="ne")\n'
        "root.after(4000, root.quit)\n"
        "root.mainloop()\n",
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: t.display[0].endswith("[3]") and t.display[0].startswith("packed"),
        message="the badge at the end of the packed row",
    )
