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

"""What a Radiobutton looks like and how a group behaves in a real terminal."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
{body}
root.update_layout()
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


GROUP = (
    "v = tkcurses.StringVar(root, '')\n"
    "group = []\n"
    "for n, word in enumerate(('Small', 'Medium', 'Large')):\n"
    "    b = tkcurses.Radiobutton(root, text=word, variable=v, value=word.lower())\n"
    "    b.place(x=2, y=2 + n * 2)\n"
    "    group.append(b)\n"
)


def test_an_unchosen_group_shows_empty_indicators(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(GROUP), workdir=tmp_path)
    term.wait_for_text("( ) Small")
    term.wait_for_text("( ) Medium")
    term.wait_for_text("( ) Large")


def test_choosing_one_marks_only_that_one(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(GROUP + "root.after(100, lambda: v.set('medium'))"), workdir=tmp_path
    )
    term.wait_for_text("(•) Medium")
    term.wait_for_idle()
    display = "\n".join(term.display)
    assert "( ) Small" in display
    assert "( ) Large" in display


def test_a_click_moves_the_choice(terminal, tmp_path):
    """The one a person actually does: click the third, the first clears."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(GROUP + "root.after(100, lambda: v.set('small'))"), workdir=tmp_path
    )
    term.wait_for_text("(•) Small")
    # Round brackets still: a click chooses without taking the focus, which
    # is what Tk does - angle brackets are the focus marker.
    term.click(3, 6)
    term.wait_for_text("(•) Large")
    term.wait_for_idle()
    assert "( ) Small" in "\n".join(term.display)


def test_a_label_over_the_group_variable_follows_the_choice(terminal, tmp_path):
    """What a person watches in UAT: one click, two things change."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            GROUP + "tkcurses.Label(root, textvariable=v, width=10).place(x=20, y=2)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("( ) Small")
    term.click(3, 4)
    term.wait_for_text("medium")


def test_space_chooses_the_focused_button(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(GROUP + "root.after(100, group[0].focus_set)"), workdir=tmp_path
    )
    term.wait_for_text("< > Small")
    term.send(b" ")
    term.wait_for_text("<•> Small")


def test_tab_walks_the_group(terminal, tmp_path):
    """Every radiobutton is its own focus stop, as it is in Tk."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(GROUP + "root.after(100, group[0].focus_set)"), workdir=tmp_path
    )
    term.wait_for_text("< > Small")
    term.send_keys("<Tab>")
    term.wait_for_text("< > Medium")
    term.wait_for_idle()
    assert "( ) Small" in "\n".join(term.display)


def test_clicking_the_chosen_one_leaves_it_chosen(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(GROUP + "root.after(100, lambda: v.set('small'))"), workdir=tmp_path
    )
    term.wait_for_text("(•) Small")
    term.click(3, 2)
    term.wait_for_idle()
    assert "(•) Small" in "\n".join(term.display)


def test_a_group_packs_into_a_frame(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, relief='solid')\n"
            "f.pack(fill='both', expand=True)\n"
            "v = tkcurses.IntVar(root, 2)\n"
            "for n in (1, 2, 3):\n"
            "    tkcurses.Radiobutton(\n"
            "        f, text='Choice %d' % n, variable=v, value=n\n"
            "    ).pack(anchor='w')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("( ) Choice 1")
    term.wait_for_text("(•) Choice 2")
    term.wait_for_text("( ) Choice 3")


def test_buttons_without_a_variable_still_form_one_group(terminal, tmp_path):
    """Tk's default group, which is what makes the no-variable case usable."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "for n, word in enumerate(('Yes', 'No')):\n"
            "    tkcurses.Radiobutton(\n"
            "        root, text=word, value=word.lower()\n"
            "    ).place(x=2, y=2 + n * 2)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("( ) Yes")
    term.click(3, 2)
    term.wait_for_text("(•) Yes")
    term.click(3, 4)
    term.wait_for_text("(•) No")
    term.wait_for_idle()
    assert "( ) Yes" in "\n".join(term.display)
