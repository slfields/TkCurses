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

"""A scrolled text against a real terminal.

The thing worth checking here cannot be seen from the object at all: that the
keyboard reaches it. A widget whose class name does not match the tag its
bindings live under receives every key and does nothing with any of them,
and reads perfectly well in every other respect.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

PROGRAM = """
import tkcurses
from tkcurses.scrolledtext import ScrolledText

root = tkcurses.Tk()
scrolled = ScrolledText(root, height=6, width=28)
scrolled.pack(side="top", fill="both", expand=True)
for number in range(1, 21):
    scrolled.insert("end", "line %02d\\n" % number)
scrolled.focus_set()
root.update_layout()
buffer = root.tk.screen.buffer
root.tk.screen.refresh()
root.after(6000, root.quit)
root.mainloop()
"""


def start(term, tmp_path):
    term.run_source(PROGRAM, workdir=tmp_path)
    term.wait_for_text("line 20")
    term.wait_for_idle()


def test_the_text_and_its_scrollbar_are_both_drawn(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    start(term, tmp_path)
    screen = "\n".join(term.display)
    assert "line 20" in screen
    assert "▲" in screen and "▼" in screen, f"no scrollbar:\n{term.describe()}"


def test_typing_reaches_it(terminal, tmp_path):
    """The one a wrong class name breaks, and the one nothing else shows."""
    term = terminal(cols=40, rows=12)
    start(term, tmp_path)
    term.send(b"XYZ")
    term.wait_for_text("XYZ")


def test_the_arrows_move_the_view(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    start(term, tmp_path)
    assert not term.contains("line 01"), "it starts at the end of the text"
    for _ in range(25):
        term.send_keys("<Up>")
    term.wait_for(
        lambda t: t.contains("line 01"), message="the view to follow the cursor"
    )


def test_the_thumb_follows_the_view(terminal, tmp_path):
    """The bar is wired to the text, so what it shows has to be true."""
    term = terminal(cols=40, rows=12)
    start(term, tmp_path)

    def thumb_rows():
        return [row for row, line in enumerate(term.display) if "█" in line]

    at_end = thumb_rows()
    for _ in range(20):
        term.send_keys("<Up>")
    term.wait_for(lambda t: t.contains("line 01"), message="the top of the text")
    at_start = thumb_rows()
    assert at_start and at_end, term.describe()
    assert min(at_start) < min(at_end), (
        f"the thumb did not move up with the view:\n{term.describe()}"
    )
