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

"""A named font, actually drawn.

The rest of the module is bookkeeping; this is the part that makes it worth
having. A widget names a font in its option and the styling has to arrive on
the screen, which is the one thing no amount of reading options back can
show.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

PROGRAM = """
import tkcurses
from tkcurses import font

root = tkcurses.Tk()
# Held in a list: a Font deletes itself when the last reference goes, which
# is tkinter's behaviour and would otherwise leave the labels naming fonts
# that are no longer there.
fonts = [
    font.Font(root, weight="bold", name="heading"),
    font.Font(root, underline=1, name="under"),
    font.Font(root, name="plain"),
]
for row, name in enumerate(("heading", "under", "plain"), start=1):
    tkcurses.Label(root, text=name.upper() + "TEXT", font=name).place(x=0, y=row)
root.update_layout()
buffer = root.tk.screen.buffer
buffer.write(0, 0, "ready")
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


def test_a_named_font_styles_the_widget_that_names_it(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    term.run_source(PROGRAM, workdir=tmp_path)
    term.wait_for_text("HEADINGTEXT")
    term.wait_for_idle()

    bold = term.attrs_at(1, 1)
    underlined = term.attrs_at(2, 1)
    plain = term.attrs_at(3, 1)

    assert bold["bold"] is True, term.describe()
    assert bold["underscore"] is False, term.describe()
    assert underlined["underscore"] is True, term.describe()
    assert underlined["bold"] is False, term.describe()
    assert plain["bold"] is False and plain["underscore"] is False, term.describe()
