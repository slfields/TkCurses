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

"""What a Canvas draws in a real terminal.

The half-cell plane is the point of this widget, so most of these assert on
actual glyphs: that a circle is round, that two colours share a cell, that
one item covers another.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


#: The canvas is 40x12 at (0, 0), so on a 12-row terminal it covers every
#: row there is. A test that writes a marker into the screen BUFFER and then
#: waits for it is writing underneath an opaque panel, and whether it ever
#: shows depends on what repaints that panel afterwards - which is why those
#: tests asked for 13 rows and put the marker on row 12.
#:
#: This was TkCurses-txk's second shape: "the program exited with code 0
#: while waiting for text 'ready'". The program had run, drawn, and quit
#: normally; the marker was simply never visible. The same mistake is
#: written up in test_redraw_cost_tty.py, which moved its own results to
#: rows 37 and 38 for exactly this reason.
def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
c = tkcurses.Canvas(root, width=40, height=12, relief='flat')
c.place(x=0, y=0)
{body}
root.update_layout()
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


INK = "▀▄█"


def inked(term):
    """Every cell with drawing in it, as ``(row, column)``."""
    return {
        (row, column)
        for row, line in enumerate(term.display)
        for column, cell in enumerate(line)
        if cell in INK
    }


def test_a_line_is_drawn(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("c.create_line(0, 0, 20, 0, fill='white')"), workdir=tmp_path
    )
    term.wait_for(lambda t: inked(t), message="a line")
    term.wait_for_idle()
    cells = inked(term)
    assert all(row == 0 for row, _ in cells)
    assert len(cells) == 21


def test_a_horizontal_line_uses_the_upper_half(terminal, tmp_path):
    """Pixel row 0 is the top half of cell row 0."""
    term = terminal(cols=40, rows=12)
    term.run_source(program("c.create_line(0, 0, 5, 0)"), workdir=tmp_path)
    term.wait_for(lambda t: inked(t), message="a line")
    term.wait_for_idle()
    assert term.display[0][0] == "▀"


def test_a_line_one_pixel_lower_uses_the_lower_half(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program("c.create_line(0, 1, 5, 1)"), workdir=tmp_path)
    term.wait_for(lambda t: inked(t), message="a line")
    term.wait_for_idle()
    assert term.display[0][0] == "▄"


def test_two_lines_in_one_cell_make_a_full_block(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("c.create_line(0, 0, 5, 0)\nc.create_line(0, 1, 5, 1)"),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "█" in "".join(t.display), message="a full block")
    term.wait_for_idle()
    assert term.display[0][0] == "█"


def test_a_circle_is_as_wide_as_it_is_tall(terminal, tmp_path):
    """The whole reason for the half-cell plane."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("c.create_oval(0, 0, 20, 20, outline='white')"), workdir=tmp_path
    )
    term.wait_for(lambda t: len(inked(t)) > 20, message="a circle")
    term.wait_for_idle()
    cells = inked(term)
    columns = {column for _, column in cells}
    rows = {row for row, _ in cells}
    width = max(columns) - min(columns) + 1
    height_in_pixels = (max(rows) - min(rows) + 1) * 2
    assert abs(width - height_in_pixels) <= 2


def test_an_oval_is_hollow_and_a_filled_one_is_not(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("c.create_oval(0, 0, 20, 20, outline='white')"), workdir=tmp_path
    )
    term.wait_for(lambda t: len(inked(t)) > 20, message="an oval")
    term.wait_for_idle()
    hollow = len(inked(term))

    solid = terminal(cols=40, rows=12)
    solid.run_source(
        program("c.create_oval(0, 0, 20, 20, fill='white', outline='')"),
        workdir=tmp_path / "solid",
    )
    solid.wait_for(lambda t: len(inked(t)) > 20, message="a filled oval")
    solid.wait_for_idle()
    assert len(inked(solid)) > hollow


def test_a_rectangle_has_four_corners_and_a_hollow_middle(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("c.create_rectangle(2, 2, 20, 14, outline='white')"),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: len(inked(t)) > 20, message="a rectangle")
    term.wait_for_idle()
    cells = inked(term)
    assert (1, 2) in cells  # pixel (2,2) is the lower half of cell row 1
    assert (1, 20) in cells
    assert (5, 11) not in cells  # the middle is empty


def test_a_filled_rectangle_is_solid(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("c.create_rectangle(2, 2, 20, 13, fill='white', outline='')"),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: len(inked(t)) > 20, message="a filled rectangle")
    term.wait_for_idle()
    assert (5, 11) in inked(term)


def test_two_colours_share_one_cell(terminal, tmp_path):
    """Half blocks were chosen over the denser sets for exactly this."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "c.create_line(0, 0, 9, 0, fill='red')\n"
            "c.create_line(0, 1, 9, 1, fill='blue')"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "▀" in "".join(t.display), message="a split cell")
    term.wait_for_idle()
    assert term.display[0][0] == "▀"
    attrs = term.attrs_at(0, 0)
    assert attrs["fg"] == "red"
    assert attrs["bg"] == "blue"


def test_an_item_made_later_covers_one_made_earlier(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "c.create_rectangle(0, 0, 19, 11, fill='red', outline='')\n"
            "c.create_rectangle(0, 0, 19, 11, fill='blue', outline='')"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: len(inked(t)) > 20, message="two rectangles")
    term.wait_for_idle()
    assert term.attrs_at(2, 4)["fg"] == "blue"


def test_text_is_drawn_over_a_shape_made_before_it(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "c.create_rectangle(0, 0, 30, 15, fill='red', outline='')\n"
            "c.create_text(2, 4, text='LABEL', anchor='nw', fill='white')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("LABEL")


def test_a_shape_made_after_text_covers_it(terminal, tmp_path):
    """Composing the plane first and laying text over it would not do this."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "c.create_text(2, 4, text='HIDDEN', anchor='nw')\n"
            "c.create_rectangle(0, 0, 30, 15, fill='red', outline='')"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: len(inked(t)) > 20, message="the rectangle")
    term.wait_for_idle()
    assert "HIDDEN" not in "\n".join(term.display)


def test_a_text_item_honours_its_anchor(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("c.create_text(20, 10, text='MIDDLE', anchor='center')"),
        workdir=tmp_path,
    )
    term.wait_for_text("MIDDLE")
    row = next(i for i, line in enumerate(term.display) if "MIDDLE" in line)
    column = term.display[row].index("MIDDLE")
    assert row == 5  # pixel row 10 is cell row 5
    assert column == 20 - len("MIDDLE") // 2


def test_a_text_item_takes_a_font(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("c.create_text(2, 4, text='BOLD', anchor='nw', font='bold')"),
        workdir=tmp_path,
    )
    term.wait_for_text("BOLD")
    row = next(i for i, line in enumerate(term.display) if "BOLD" in line)
    assert term.attrs_at(row, term.display[row].index("BOLD"))["bold"]


def test_moving_an_item_clears_where_it_was(terminal, tmp_path):
    term = terminal(cols=40, rows=13)
    term.run_source(
        program(
            "r = c.create_rectangle(0, 0, 6, 6, fill='white', outline='')\n"
            "buffer.write(12, 0, 'ready')\n"
            "root.after(200, lambda: c.move(r, 20, 0))"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: (1, 2) in inked(t), message="the rectangle")
    term.wait_for_idle()
    term.wait_for(lambda t: (1, 22) in inked(t), message="the move")
    term.wait_for_idle()
    assert (1, 2) not in inked(term)


def test_deleting_an_item_clears_it(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "r = c.create_rectangle(0, 0, 10, 10, fill='white', outline='')\n"
            "root.after(200, lambda: c.delete(r))"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: len(inked(t)) > 10, message="the rectangle")
    term.wait_for_idle()
    term.wait_for(lambda t: not inked(t), message="it to go")
    term.wait_for_idle()


def test_a_hidden_item_is_not_drawn(terminal, tmp_path):
    term = terminal(cols=40, rows=13)
    term.run_source(
        program(
            "c.create_rectangle(0, 0, 10, 10, fill='white', state='hidden')\n"
            "buffer.write(12, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.wait_for_idle()
    assert not inked(term)


def test_clicking_an_item_runs_its_binding(terminal, tmp_path):
    term = terminal(cols=40, rows=13)
    term.run_source(
        program(
            "def hit(event):\n"
            "    buffer.write(11, 0, 'hit %s' % (c.find_withtag('current'),))\n"
            "    root.tk.screen.refresh()\n"
            "r = c.create_rectangle(0, 0, 10, 10, fill='white', outline='', tags='hot')\n"
            "c.tag_bind('hot', '<Button-1>', hit)\n"
            "buffer.write(12, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.wait_for(lambda t: len(inked(t)) > 5, message="the rectangle")
    term.wait_for_idle()
    term.click(2, 2)
    term.wait_for_text("hit (1,)")


def test_clicking_past_an_item_runs_nothing(terminal, tmp_path):
    term = terminal(cols=40, rows=13)
    term.run_source(
        program(
            "def hit(event):\n"
            "    buffer.write(11, 0, 'should not happen')\n"
            "    root.tk.screen.refresh()\n"
            "c.create_rectangle(0, 0, 6, 6, fill='white', outline='', tags='hot')\n"
            "c.tag_bind('hot', '<Button-1>', hit)\n"
            "buffer.write(12, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.click(30, 8)
    term.wait_for_idle()
    assert "should not happen" not in "\n".join(term.display)


def test_scrolling_moves_what_is_visible(terminal, tmp_path):
    term = terminal(cols=40, rows=13)
    term.run_source(
        program(
            "c.configure(scrollregion=(0, 0, 80, 48))\n"
            "c.create_rectangle(50, 30, 70, 40, fill='white', outline='')\n"
            "buffer.write(12, 0, 'ready')\n"
            "root.after(200, lambda: (c.xview_moveto(0.5), c.yview_moveto(0.5)))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.wait_for(lambda t: inked(t), message="the rectangle to scroll in")
    term.wait_for_idle()


def test_a_canvas_survives_the_terminal_shrinking(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("c.create_oval(0, 0, 30, 20, outline='white')").replace(
            "c.place(x=0, y=0)", "c.pack(fill='both', expand=True)"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: len(inked(t)) > 20, message="an oval")
    term.wait_for_idle()
    term.resize(cols=24, rows=8)
    term.wait_for(lambda t: len(inked(t)) > 5, message="the oval after resize")
    term.wait_for_idle()
    assert "Traceback" not in term.stderr


def test_a_filled_shape_is_the_colour_it_was_given(terminal, tmp_path):
    """Reported from UAT 24: a magenta triangle came out white.

    The canvas laid each cell's colour pair *over* a base attribute that
    already carried one. Colour is a packed field, not a flag, so the two
    pair numbers OR'd into the number of a third - and the fill was drawn in
    whatever colour that pair happened to be.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "c.create_polygon(2, 2, 30, 10, 2, 18, fill='magenta', outline='white')"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: len(inked(t)) > 20, message="the triangle")
    term.wait_for_idle()
    solid = [
        term.attrs_at(row, column)
        for row, column in inked(term)
        if term.display[row][column] == "█"
    ]
    assert solid, "no filled cells at all"
    assert any(cell["fg"] == "magenta" and cell["bg"] == "black" for cell in solid), (
        f"no cell was filled magenta: {solid[:4]}"
    )


def test_a_shape_does_not_take_the_canvas_background_as_its_colour(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "c.configure(background='blue')\n"
            "c.create_rectangle(2, 2, 20, 12, fill='red', outline='')"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: len(inked(t)) > 10, message="the rectangle")
    term.wait_for_idle()
    row, column = next(iter(sorted(inked(term))))
    assert term.attrs_at(row, column)["fg"] == "red"
