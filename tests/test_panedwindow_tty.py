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

"""What Menubutton, OptionMenu and PanedWindow look like in a real terminal."""

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


# -------------------------------------------------------------- menubutton


def test_a_menubutton_posts_its_menu_when_clicked(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "m = tkcurses.Menu(root)\n"
            "m.add_command(label='Open')\n"
            "m.add_command(label='Close')\n"
            "tkcurses.Menubutton(root, text='File', menu=m).place(x=2, y=2)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("File")
    row = next(i for i, line in enumerate(term.display) if "File" in line)
    term.click(term.display[row].index("File") + 1, row)
    term.wait_for_text("Open")
    term.wait_for_text("Close")


def test_a_menubutton_shows_its_indicator(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tkcurses.Menubutton(root, text='File', indicatoron=True).place(x=2, y=2)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("▾")


def test_a_menubutton_menu_dismisses_cleanly(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "m = tkcurses.Menu(root)\n"
            "m.add_command(label='Open')\n"
            "tkcurses.Menubutton(root, text='File', menu=m).place(x=2, y=2)\n"
            "tkcurses.Label(root, text='behind the menu').place(x=2, y=6)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("behind the menu")
    row = next(i for i, line in enumerate(term.display) if "File" in line)
    term.click(term.display[row].index("File") + 1, row)
    term.wait_for_text("Open")
    term.send_keys("<Escape>")
    term.wait_for(
        lambda t: "Open" not in "\n".join(t.display), message="the menu to close"
    )
    term.wait_for_text("behind the menu")


# -------------------------------------------------------------- optionmenu


def test_an_optionmenu_shows_the_chosen_value(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "v = tkcurses.StringVar(root, 'medium')\n"
            "o = tkcurses.OptionMenu(root, v, 'small', 'medium', 'large')\n"
            "o.place(x=2, y=2)\n"
            "tkcurses.Label(root, textvariable=v, width=8).place(x=2, y=6)"
        ),
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: "\n".join(t.display).count("medium") == 2, message="both views"
    )


def test_choosing_from_an_optionmenu_changes_the_button(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "v = tkcurses.StringVar(root, 'small')\n"
            "o = tkcurses.OptionMenu(root, v, 'small', 'medium', 'large')\n"
            "o.place(x=2, y=2)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("small")
    row = next(i for i, line in enumerate(term.display) if "small" in line)
    term.click(term.display[row].index("small") + 1, row)
    term.wait_for_text("large")
    row = next(i for i, line in enumerate(term.display) if "large" in line)
    term.click(5, row)
    term.wait_for(
        lambda t: "medium" not in "\n".join(t.display), message="the menu to close"
    )
    term.wait_for_text("large")


# ------------------------------------------------------------- panedwindow


PANED = (
    "p = tkcurses.PanedWindow(root, orient='horizontal')\n"
    # Placed rather than packed, so the bottom rows stay clear for the
    # status line: a pane's window would otherwise draw over it.
    "p.place(x=0, y=0, relwidth=1.0, height=8)\n"
    "left = tkcurses.Label(p, text='LEFT', relief='solid')\n"
    "p.add(left, minsize=6)\n"
    "right = tkcurses.Label(p, text='RIGHT', relief='solid')\n"
    "p.add(right, minsize=6)\n"
)


def test_a_paned_window_shows_both_panes_and_a_sash(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(program(PANED), workdir=tmp_path)
    term.wait_for_text("LEFT")
    term.wait_for_text("RIGHT")
    term.wait_for_text("┃")  # the sash handle


def test_the_sash_sits_between_the_panes(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(program(PANED), workdir=tmp_path)
    term.wait_for_text("LEFT")
    term.wait_for_idle()
    row = next(i for i, line in enumerate(term.display) if "LEFT" in line)
    left = term.display[row].index("LEFT")
    right = term.display[row].index("RIGHT")
    sash = next(
        i for i, cell in enumerate(term.display[row]) if cell in "│┃" and i > left
    )
    assert left < sash < right


def test_dragging_the_sash_resizes_the_panes(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            PANED + "def report():\n"
            "    buffer.write(9, 0, 'w=%d|    ' % left.winfo_width())\n"
            "    root.tk.screen.refresh()\n"
            "p.bind('<ButtonRelease-1>', lambda e: root.after_idle(report))\n"
            "root.after(200, report)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("w=")
    term.wait_for_idle()
    # The handle, which is unique to the sash - hunting for a box-drawing
    # character finds the root window's own border first.
    row, column = next(
        (r, c)
        for r, line in enumerate(term.display)
        for c, cell in enumerate(line)
        if cell == "┃"
    )
    width = int(term.display[9].split("w=")[1].split("|")[0])
    term.send_mouse(column, row, action="press")
    term._drain(0.08)
    # Rightwards: the left pane starts at its own size, which is its minsize,
    # and as in Tk a sash cannot take a pane below that.
    term.send_mouse(column + 6, row, action="move", button=1)
    term._drain(0.08)
    term.send_mouse(column + 6, row, action="release")
    term.wait_for_text(f"w={width + 6}|")


def test_the_arrows_move_the_sash(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            PANED + "def report(event=None):\n"
            "    buffer.write(9, 0, 'w=%d|    ' % left.winfo_width())\n"
            "    root.tk.screen.refresh()\n"
            "p.bind('<Any-Key>', lambda e: root.after_idle(report), add=True)\n"
            "p.focus_set()\n"
            "root.after(200, report)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("w=")
    term.wait_for_idle()
    width = int(term.display[9].split("w=")[1].split("|")[0])
    term.send_keys("<Right>")
    term.wait_for_text(f"w={width + 1}|")
    term.send_keys("<Left>")
    term.wait_for_text(f"w={width}|")


#: Something else to hold the focus, so it can be tabbed to and away from.
OTHER_FOCUS = "b = tkcurses.Button(root, text='OTHER')\nb.place(x=0, y=8)\n"


def test_tabbing_to_a_paned_window_marks_its_sash(terminal, tmp_path):
    """The sash is the only thing that says a paned window has the focus.

    A click marked it as a side effect of starting a drag, so the fault was
    invisible to anyone using the mouse; Tab moved the focus with nothing to
    repaint it, and the one keyboard user who might have moved a sash had no
    way to tell they could.
    """
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(OTHER_FOCUS + PANED),
        workdir=tmp_path,
    )
    term.wait_for_text("┃")
    term.wait_for_idle()
    row, column = next(
        (r, c)
        for r, line in enumerate(term.display)
        for c, cell in enumerate(line)
        if cell == "┃"
    )
    assert not term.attrs_at(row, column)["reverse"], "nothing has the focus yet"

    term.send_keys("<Tab>", "<Tab>")
    term.wait_for(
        lambda t: t.attrs_at(row, column)["reverse"], message="the sash marked"
    )

    term.send_keys("<Tab>")
    term.wait_for(
        lambda t: not t.attrs_at(row, column)["reverse"],
        message="the sash unmarked again",
    )


def test_panes_nest(terminal, tmp_path):
    term = terminal(cols=44, rows=12)
    term.run_source(
        program(
            "outer = tkcurses.PanedWindow(root, orient='horizontal')\n"
            "outer.pack(fill='both', expand=True)\n"
            "outer.add(tkcurses.Label(outer, text='SIDE', relief='solid'), minsize=8)\n"
            "inner = tkcurses.PanedWindow(outer, orient='vertical')\n"
            "outer.add(inner, minsize=10)\n"
            "inner.add(tkcurses.Label(inner, text='TOP', relief='solid'), minsize=2)\n"
            "inner.add(tkcurses.Label(inner, text='BOTTOM', relief='solid'), minsize=2)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("SIDE")
    term.wait_for_text("TOP")
    term.wait_for_text("BOTTOM")
    term.wait_for_idle()
    display = "\n".join(term.display)
    assert "┃" in display  # the vertical sash
    assert "━" in display  # the horizontal one


def test_a_paned_window_survives_the_terminal_shrinking(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(program(PANED), workdir=tmp_path)
    term.wait_for_text("LEFT")
    term.resize(cols=24, rows=8)
    term.wait_for_text("LEFT")
    assert "Traceback" not in term.stderr


def test_a_label_packed_into_a_paned_window_is_drawn_over_the_panes(terminal, tmp_path):
    # TkCurses-ect9: refused until pack was given a slot beside the panes.
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            PANED + "tkcurses.Label(p, text='PACKED', bg='red').pack(side='bottom')\n"
        ),
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: t.contains("PACKED") and t.contains("LEFT"),
        message="the packed label and the panes",
    )
