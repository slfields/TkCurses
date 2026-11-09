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

"""A click on tagged text reaches the tag's bindings in a real terminal.

Without hover reporting there is no motion between clicks, so the
character under the pointer is picked from the ``<Enter>`` a click brings
and forgotten with the ``<Leave>`` after it - and a link works anyway.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

PROGRAM = """
import tkcurses

root = tkcurses.Tk()
log = []
shown = tkcurses.Label(root, text="", anchor="w", width=60, borderwidth=0)
shown.place(x=0, y=6)


def note(word):
    log.append(word)
    shown.configure(text=" ".join(log) + " .")


text = tkcurses.Text(root, width=30, height=3, borderwidth=0)
text.place(x=0, y=0)
text.insert("1.0", "plain LINK plain")
text.tag_add("link", "1.6", "1.10")
text.tag_bind("link", "<Enter>", lambda e: note("enter"))
text.tag_bind("link", "<Leave>", lambda e: note("leave"))
text.tag_bind("link", "<Button-1>", lambda e: note("click"))
root.after(8000, root.quit)
root.mainloop()
"""


def logged(term, text):
    term.wait_for(lambda t: t.display[6].rstrip().endswith(text + " ."))


def test_a_click_on_a_link_reaches_its_binding(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    term.run_source(PROGRAM, workdir=tmp_path)
    term.wait_for_text("plain LINK")
    term.click(7, 0)
    logged(term, "enter click leave")
    term.click(1, 0)
    # The plain text has no tag to hear it; the line below shows nothing new.
    term.click(8, 0)
    logged(term, "enter click leave enter click leave")
