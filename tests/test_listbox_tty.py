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

"""What a Listbox looks like and how it answers a real terminal."""

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


LIST = (
    "lb = tkcurses.Listbox(root, width=16, height=5)\n"
    "lb.place(x=1, y=1)\n"
    "lb.insert('end', 'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta')\n"
)


def test_a_listbox_shows_its_items(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(LIST), workdir=tmp_path)
    term.wait_for_text("alpha")
    term.wait_for_text("beta")


def test_only_as_many_items_as_fit_are_shown(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(LIST + "buffer.write(10, 0, 'ready')"), workdir=tmp_path)
    term.wait_for_text("ready")
    term.wait_for_idle()
    assert "zeta" not in "\n".join(term.display)


def test_the_selected_item_is_marked(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(LIST + "lb.selection_set(1)"), workdir=tmp_path)
    # Both markers and the text between them, in one wait: "▶" arriving does
    # not promise that "◀" at the other end of the row has - TkCurses-txk.
    term.wait_for(
        lambda t: any(
            "▶" in line and "◀" in line and "beta" in line for line in t.display
        ),
        message="the marked row, both markers",
    )
    row = next(i for i, line in enumerate(term.display) if "▶" in line)
    assert "beta" in term.display[row]
    assert "◀" in term.display[row]


def test_a_disabled_listbox_keeps_its_selection_out_of_sight(terminal, tmp_path):
    """``listbox(n)``: the selection *"is not shown (though selection
    information is retained)"*, and Tk 9.0.2 draws it so. The row and its
    markers go out in one write, so the row holding "beta" is the whole
    answer - TkCurses-txk."""
    term = terminal(cols=40, rows=12)
    source = LIST + "lb.selection_set(1)\nlb.configure(state='disabled')"
    term.run_source(program(source), workdir=tmp_path)
    term.wait_for_text("beta")
    term.wait_for_idle()
    row = next(i for i, line in enumerate(term.display) if "beta" in line)
    assert "▶" not in term.display[row]
    assert "◀" not in term.display[row]


def test_the_arrows_move_the_selection(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(LIST + "lb.focus_set()\nlb.selection_set(0)\nlb.activate(0)"),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "▶" in "\n".join(t.display), message="the marker")
    term.send_keys("<Down>")
    term.wait_for(
        lambda t: any("▶" in line and "beta" in line for line in t.display),
        message="the selection on beta",
    )


def test_scrolling_past_the_bottom_brings_later_items_in(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(LIST + "lb.focus_set()\nlb.activate(0)"), workdir=tmp_path)
    term.wait_for_text("alpha")
    for _ in range(6):
        term.send_keys("<Down>")
    term.wait_for_text("zeta")


def test_clicking_selects_the_row_under_the_pointer(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(LIST + "buffer.write(10, 0, 'ready')"), workdir=tmp_path)
    term.wait_for_text("ready")
    # Row 2 on screen is the second item: the box starts at y=1 and has a border.
    term.click(4, 3)
    term.wait_for(
        lambda t: any("▶" in line and "beta" in line for line in t.display),
        message="beta selected",
    )


def test_a_selection_change_fires_the_virtual_event(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            LIST + "def chose(event):\n"
            "    buffer.write(11, 0, 'chose %s' % (lb.curselection(),))\n"
            "    root.tk.screen.refresh()\n"
            "lb.bind('<<ListboxSelect>>', chose)\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.click(4, 2)
    term.wait_for_text("chose (0,)")


def test_a_listbox_packs_with_the_other_widgets(terminal, tmp_path):
    term = terminal(cols=40, rows=14)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, relief='solid')\n"
            "f.pack(fill='both', expand=True)\n"
            "tkcurses.Label(f, text='Pick one').pack(side='top')\n"
            "lb = tkcurses.Listbox(f, width=14, height=4)\n"
            "lb.pack(side='top')\n"
            "lb.insert('end', 'one', 'two', 'three')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("Pick one")
    term.wait_for_text("three")


# ------------------------------------------------ keeping its own border


BORDERED = (
    "lb = tkcurses.Listbox(root, width=12, height=3)\n"
    "lb.place(x=1, y=1)\n"
    "lb.insert('end', 'alpha', 'beta', 'gamma')\n"
    "lb.selection_set(1)\n"
)


def bordered(terminal, tmp_path, extra=""):
    term = terminal(cols=32, rows=10)
    term.run_source(program(BORDERED + extra), workdir=tmp_path)
    term.wait_for_text("alpha")
    term.wait_for_idle()
    return term


def test_every_row_keeps_the_right_border(terminal, tmp_path):
    """The assertion none of these tests used to make, and the bug it missed.

    The row's right-hand marker went on with insstr, which *inserts*: it
    shifted the row one cell right and dropped the last one, which on a
    bordered listbox was the border. Every row lost it, and the text ran on
    into whatever was beside the widget.
    """
    term = bordered(terminal, tmp_path)
    rows = [
        i for i, line in enumerate(term.display) if "alpha" in line or "beta" in line
    ]
    assert rows, term.describe()
    for row in rows:
        line = term.display[row]
        left = line.index("│")
        right = line.index("│", left + 1)
        assert right - left == 13, f"row {row} lost its right border\n{term.describe()}"


def test_the_border_is_a_closed_box(terminal, tmp_path):
    """Top, bottom and both sides, all at the same columns."""
    term = bordered(terminal, tmp_path)
    top = next(i for i, line in enumerate(term.display) if "┌" in line)
    bottom = next(i for i, line in enumerate(term.display) if "└" in line)
    left = term.display[top].index("┌")
    right = term.display[top].index("┐")
    assert term.display[bottom].index("└") == left
    assert term.display[bottom].index("┘") == right
    for row in range(top + 1, bottom):
        assert term.display[row][left] == "│", term.describe()
        assert term.display[row][right] == "│", term.describe()


def test_the_selected_row_still_has_its_markers(terminal, tmp_path):
    """The markers are what the insstr was for, so the fix has to keep them."""
    term = bordered(terminal, tmp_path)
    row = next(i for i, line in enumerate(term.display) if "beta" in line)
    assert "▶" in term.display[row], term.describe()
    assert "◀" in term.display[row], term.describe()


def test_nothing_is_written_beyond_the_border(terminal, tmp_path):
    """A long item must stop inside the box rather than run past it."""
    term = bordered(
        terminal,
        tmp_path,
        "lb.insert('end', 'a very long item indeed that will not fit')\n",
    )
    top = next(i for i, line in enumerate(term.display) if "┌" in line)
    right = term.display[top].index("┐")
    for row in range(top, top + 5):
        assert term.display[row][right + 1 :].strip() == "", term.describe()


def test_an_unbordered_listbox_still_marks_its_selection(terminal, tmp_path):
    """Without a border the markers really do reach the window's last cell,
    which is the one case insstr was right for."""
    term = terminal(cols=32, rows=10)
    term.run_source(
        program(
            "lb = tkcurses.Listbox(root, width=12, height=2, relief='flat')\n"
            "lb.place(x=1, y=1)\n"
            "lb.insert('end', 'first', 'second')\n"
            "lb.selection_set(0)\n"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("first")
    term.wait_for_idle()
    row = next(i for i, line in enumerate(term.display) if "first" in line)
    assert "▶" in term.display[row] and "◀" in term.display[row], term.describe()


def test_a_listbox_scrolled_sideways_shows_the_rest_of_its_items(terminal, tmp_path):
    """TkCurses-019: xview moves every row, and the start is gone."""
    body = (
        "lb = tkcurses.Listbox(root, width=16, height=3)\n"
        "lb.place(x=1, y=1)\n"
        "lb.insert('end', 'abcdefghij-KLMNOPQRST-uvwxyz', 'short')\n"
        "lb.xview_scroll(11, 'units')\n"
    )
    term = terminal(cols=40, rows=8)
    term.run_source(program(body), workdir=tmp_path)
    term.wait_for_text("KLMNOP")
    assert not any("abcdef" in line for line in term.display)
