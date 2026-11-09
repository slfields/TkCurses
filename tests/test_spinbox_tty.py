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

"""What a Spinbox looks like and how it answers a real terminal."""

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


SIZES = (
    "s = tkcurses.Spinbox(\n"
    "    root, values=('small', 'medium', 'large'), width=10, state='readonly'\n"
    ")\n"
    "s.place(x=2, y=2)\n"
)


def test_a_spinbox_shows_its_value_and_two_arrows(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(SIZES), workdir=tmp_path)
    term.wait_for_text("small")
    term.wait_for_text("▲▼")


def test_clicking_the_up_arrow_steps(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(SIZES), workdir=tmp_path)
    term.wait_for_text("▲▼")
    row = next(i for i, line in enumerate(term.display) if "▲" in line)
    column = term.display[row].index("▲")
    term.click(column, row)
    term.wait_for_text("medium")
    term.click(column, row)
    term.wait_for_text("large")


def test_clicking_the_down_arrow_steps_back(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(SIZES), workdir=tmp_path)
    term.wait_for_text("▲▼")
    row = next(i for i, line in enumerate(term.display) if "▲" in line)
    column = term.display[row].index("▼")
    term.click(column, row)
    term.wait_for_idle()
    assert "small" in "\n".join(term.display)  # no wrap: it stays put
    up = term.display[row].index("▲")
    term.click(up, row)
    term.wait_for_text("medium")
    term.click(column, row)
    term.wait_for_text("small")


def test_the_arrow_keys_step(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(SIZES + "s.focus_set()"), workdir=tmp_path)
    term.wait_for_text("small")
    term.send_keys("<Up>")
    term.wait_for_text("medium")
    term.send_keys("<Down>")
    term.wait_for_text("small")


def test_a_readonly_spinbox_refuses_typing_but_still_steps(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(SIZES + "s.focus_set()"), workdir=tmp_path)
    term.wait_for_text("small")
    term.send(b"zzz")
    term.wait_for_idle()
    assert "zzz" not in "\n".join(term.display)
    term.send_keys("<Up>")
    term.wait_for_text("medium")


def test_a_numeric_spinbox_counts(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "s = tkcurses.Spinbox(root, from_=0, to=4, width=6)\n"
            "s.place(x=2, y=2)\n"
            "s.focus_set()"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("0")
    for expected in ("1", "2", "3", "4"):
        term.send_keys("<Up>")
        term.wait_for_text(expected)
    # The end of the range, and no wrap: it stays there.
    term.send_keys("<Up>")
    term.wait_for_idle()
    row = next(i for i, line in enumerate(term.display) if "▲" in line)
    assert "4" in term.display[row]


def test_a_spinbox_can_still_be_typed_into(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "s = tkcurses.Spinbox(root, from_=0, to=99, width=6)\n"
            "s.place(x=2, y=2)\n"
            "s.focus_set()"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("0")
    term.send_keys("<End>")
    term.send(b"7")
    term.wait_for_text("07")


def test_the_arrows_stay_put_as_the_value_changes_width(terminal, tmp_path):
    """A column of spinboxes has to line up whatever is in them."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "s = tkcurses.Spinbox(\n"
            "    root, values=('a', 'bbbbbb', 'cc'), width=10, state='readonly'\n"
            ")\n"
            "s.place(x=2, y=2)\n"
            "s.focus_set()"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("▲▼")
    row = next(i for i, line in enumerate(term.display) if "▲" in line)
    first = term.display[row].index("▲")
    term.send_keys("<Up>")
    term.wait_for_text("bbbbbb")
    assert term.display[row].index("▲") == first


def test_a_label_over_the_variable_follows_the_spinbox(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "v = tkcurses.StringVar(root, '')\n"
            "s = tkcurses.Spinbox(\n"
            "    root, values=('red', 'green'), textvariable=v, width=8,\n"
            "    state='readonly'\n"
            ")\n"
            "s.place(x=2, y=2)\n"
            "s.focus_set()\n"
            "tkcurses.Label(root, textvariable=v, width=8).place(x=2, y=6)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("red")
    term.send_keys("<Up>")
    term.wait_for(
        lambda t: "\n".join(t.display).count("green") == 2, message="both views"
    )


def test_a_disabled_spinbox_still_shows_its_value(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "s = tkcurses.Spinbox(\n"
            "    root, values=('small', 'large'), width=8, state='disabled'\n"
            ")\n"
            "s.place(x=2, y=2)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("small")


def test_spinboxes_pack_into_a_frame(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, relief='solid', bd=1)\n"
            "f.pack(fill='both', expand=True)\n"
            "tkcurses.Spinbox(f, from_=1, to=12, width=4).pack(anchor='w')\n"
            "tkcurses.Spinbox(f, from_=1, to=31, width=4).pack(anchor='w')"
        ),
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: "\n".join(t.display).count("▲▼") == 2, message="two spinboxes"
    )


# ------------------------------------------------ keeping its own border


def test_the_field_row_keeps_its_right_border(terminal, tmp_path):
    """The same fault the Listbox had, in the same shape.

    The second arrow went on with insstr, which *inserts*: it shifted the row
    one cell right and dropped the last, which on a bordered spinbox was the
    border. Found by looking for the pattern rather than by seeing it.
    """
    term = terminal(cols=32, rows=10)
    term.run_source(
        program(
            "s = tkcurses.Spinbox(root, width=12, from_=0, to=5)\ns.place(x=1, y=1)\n"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("▲")
    term.wait_for_idle()
    row = next(i for i, line in enumerate(term.display) if "▲" in line)
    line = term.display[row]
    left = line.index("│")
    assert "│" in line[left + 1 :], f"the field row lost its border\n{term.describe()}"
    assert line[line.index("▲") + 1] == "▼", term.describe()
    assert line[line.index("▼") + 1] == "│", "the arrows sit inside the border"


def test_an_unbordered_spinbox_still_shows_both_arrows(terminal, tmp_path):
    """Without a border the second arrow really is the window's last cell,
    which is the one case insstr was right for."""
    term = terminal(cols=32, rows=10)
    term.run_source(
        program(
            "s = tkcurses.Spinbox(root, width=12, from_=0, to=5, relief='flat')\n"
            "s.place(x=1, y=1)\n"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("▲")
    term.wait_for_idle()
    row = next(i for i, line in enumerate(term.display) if "▲" in line)
    assert "▼" in term.display[row], term.describe()
