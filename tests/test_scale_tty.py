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

"""What a Scale looks like and how it answers a real terminal."""

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


HORIZONTAL = (
    "s = tkcurses.Scale(\n"
    "    root, orient='horizontal', from_=0, to=10, length=20, label='Volume'\n"
    ")\n"
    "s.place(x=2, y=2)\n"
)


def test_a_scale_draws_a_trough_with_a_handle(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(HORIZONTAL), workdir=tmp_path)
    term.wait_for_text("█░░░░░")
    term.wait_for_text("Volume")


def test_the_value_is_shown_above_the_handle(terminal, tmp_path):
    """Tk puts it there, and it reads as belonging to the handle."""
    term = terminal(cols=40, rows=12)
    term.run_source(program(HORIZONTAL + "root.after(100, lambda: s.set(10))"))
    term.wait_for_text("░░░░█")
    row = next(i for i, line in enumerate(term.display) if "█" in line)
    assert "10" in term.display[row - 1]


def test_the_handle_moves_when_the_value_is_set(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(HORIZONTAL + "root.after(100, lambda: s.set(5))"), workdir=tmp_path
    )
    term.wait_for_text("█░░░░░░░░░")
    term.wait_for_text("░░░░░█░░░░")


def test_a_click_on_the_trough_moves_the_handle(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            HORIZONTAL + "def report(value):\n"
            "    buffer.write(11, 0, 'value=%s  ' % value)\n"
            "    root.tk.screen.refresh()\n"
            "s.configure(command=report)\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.wait_for_text("█")
    row = next(i for i, line in enumerate(term.display) if "█" in line)
    column = term.display[row].index("█")
    term.click(column + 10, row)
    term.wait_for_text("value=5")


def test_a_drag_follows_the_pointer(terminal, tmp_path):
    """The gesture a person actually uses on a slider."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            HORIZONTAL + "def report(value):\n"
            "    buffer.write(11, 0, 'value=%s  ' % value)\n"
            "    root.tk.screen.refresh()\n"
            "s.configure(command=report)\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.wait_for_text("█")
    row = next(i for i, line in enumerate(term.display) if "█" in line)
    column = term.display[row].index("█")
    term.send_mouse(column, row, action="press")
    term._drain(0.08)
    term.send_mouse(column + 8, row, action="move", button=1)
    term.wait_for_text("value=4")
    term._drain(0.08)
    term.send_mouse(column + 18, row, action="move", button=1)
    term.wait_for_text("value=9")
    term._drain(0.08)
    term.send_mouse(column + 18, row, action="release")


def test_focus_is_visible(terminal, tmp_path):
    """Caps at the ends of the trough, because colour cannot be relied on."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(HORIZONTAL + "root.after(100, s.focus_set)"), workdir=tmp_path
    )
    term.wait_for_text("█░░░░")
    term.wait_for_text("[█")
    assert "░]" in "\n".join(term.display)


def test_the_trough_does_not_move_when_focused(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            HORIZONTAL + "def report(row):\n"
            "    root.update_layout()\n"
            "    buffer.write(row, 0, 'w%s=%s' % (row, s.winfo_width()))\n"
            "    root.tk.screen.refresh()\n"
            "report(9)\n"
            "root.after(100, lambda: (s.focus_set(), report(10)))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("w9=22")
    term.wait_for_text("w10=22")


def test_the_arrows_move_the_handle(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(HORIZONTAL + "s.focus_set()\ns.set(5)"), workdir=tmp_path)
    term.wait_for_text("░░░░░█░░░░")
    term.send_keys("<Right>")
    term.wait_for_text("░░░░░░█░░░")
    term.send_keys("<Left>")
    term.send_keys("<Left>")
    term.wait_for_text("░░░░█░░░░░")


def test_end_and_home_reach_the_two_ends(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(HORIZONTAL + "s.focus_set()"), workdir=tmp_path)
    term.wait_for_text("[█░")
    term.send_keys("<End>")
    term.wait_for_text("░█]")
    term.send_keys("<Home>")
    term.wait_for_text("[█░")


def test_a_vertical_scale_runs_down_the_screen(terminal, tmp_path):
    term = terminal(cols=40, rows=16)
    term.run_source(
        program(
            "s = tkcurses.Scale(root, from_=0, to=10, length=8, showvalue=False)\n"
            "s.place(x=4, y=2)\n"
            "root.after(100, lambda: s.set(10))"
        ),
        workdir=tmp_path,
    )
    # The handle is at `to`, which on a vertical scale is the bottom end.
    term.wait_for(
        lambda t: (
            len([line for line in t.display if "░" in line or "█" in line]) >= 8
            and any("█" in line for line in t.display)
            and max(i for i, line in enumerate(t.display) if "█" in line)
            > max(i for i, line in enumerate(t.display) if "░" in line)
        ),
        message="the handle at the bottom of the trough",
    )


def test_a_vertical_scale_shows_its_value_beside_the_handle(terminal, tmp_path):
    term = terminal(cols=40, rows=16)
    term.run_source(
        program(
            "s = tkcurses.Scale(root, from_=0, to=10, length=8)\n"
            "s.place(x=4, y=2)\n"
            "root.after(100, lambda: s.set(7))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("7 █")


def test_ticks_are_drawn_under_the_trough(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "s = tkcurses.Scale(\n"
            "    root, orient='horizontal', from_=0, to=10, length=21,\n"
            "    showvalue=False, tickinterval=5\n"
            ")\n"
            "s.place(x=2, y=2)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("█░░░░")
    row = next(i for i, line in enumerate(term.display) if "█" in line)
    ticks = term.display[row + 1]
    assert "0" in ticks
    assert "5" in ticks
    assert "10" in ticks


def test_a_reversed_scale_starts_at_its_high_end(terminal, tmp_path):
    """A volume that runs 10 down to 0 is a real thing, and must not break."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "s = tkcurses.Scale(\n"
            "    root, orient='horizontal', from_=10, to=0, length=20\n"
            ")\n"
            "s.place(x=2, y=2)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("█░░░░░░░░░")
    row = next(i for i, line in enumerate(term.display) if "█" in line)
    assert "10" in term.display[row - 1]


def test_a_label_over_the_variable_follows_the_scale(terminal, tmp_path):
    """What a person watches in UAT: drag here, a number changes over there."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "v = tkcurses.IntVar(root, 0)\n"
            "s = tkcurses.Scale(\n"
            "    root, orient='horizontal', from_=0, to=10, length=20,\n"
            "    variable=v, showvalue=False\n"
            ")\n"
            "s.place(x=2, y=2)\n"
            "tkcurses.Label(root, textvariable=v, width=4).place(x=2, y=6)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("█░░░░")
    row = next(i for i, line in enumerate(term.display) if "█" in line)
    column = term.display[row].index("█")
    term.click(column + 20, row)
    term.wait_for_text("10")


def test_a_scale_stretches_when_it_is_packed_to_fill(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "s = tkcurses.Scale(\n"
            "    root, orient='horizontal', from_=0, to=10, length=5,\n"
            "    showvalue=False\n"
            ")\n"
            "s.pack(fill='x')\n"
            "root.after(100, lambda: s.set(10))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("░" * 30)
