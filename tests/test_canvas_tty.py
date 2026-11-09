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


def test_a_click_finds_the_item_in_a_canvas_away_from_the_corner(terminal, tmp_path):
    """canvasx(event.x) is the canvas point under the pointer wherever the
    canvas is, and an item's binding hears a click on it. TkCurses-0n21: both
    took a screen position, and were wrong for a canvas not at (0, 0)."""
    term = terminal(cols=40, rows=14)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
shown = tkcurses.Label(root, text="waiting")
shown.place(x=0, y=13)
c = tkcurses.Canvas(root, width=20, height=8)
c.place(x=10, y=3)
c.create_rectangle(4, 4, 8, 8, fill="white", outline="", tags="hot")

def clicked(event):
    shown.configure(text=f"at {c.canvasx(event.x)},{c.canvasy(event.y)}")

def hit(event):
    shown.configure(text=shown.cget("text") + " hit")

c.bind("<Button-1>", clicked)
c.tag_bind("hot", "<Button-1>", hit, add="+")
root.mainloop()
""",
        workdir=tmp_path,
    )
    term.wait_for(lambda t: len(inked(t)) >= 4, message="the square")
    row = min(r for r, _ in inked(term))
    column = min(c for _, c in inked(term))
    # The square's top-left cell is canvas (4, 4): two columns and one row
    # past where the canvas's coordinates start.
    term.click(column, row)
    term.wait_for_text("at 4,4")
    term.wait_for_text("hit")


def test_selected_text_wears_the_select_colours(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "c.configure(selectforeground='black', selectbackground='yellow')\n"
            "t = c.create_text(2, 2, text='hello', anchor='nw', fill='white')\n"
            "c.select_from(t, 1)\n"
            "c.select_to(t, 3)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_cell(1, 4, lambda cell: cell.data == "l" and cell.bg == "brown")
    term.wait_for_cell(1, 2, lambda cell: cell.data == "h")
    term.wait_for_cell(1, 6, lambda cell: cell.data == "o")
    row = term._screen.buffer[1]
    backgrounds = [row[column].bg for column in range(2, 7)]
    assert backgrounds[1:4] == ["brown"] * 3
    assert "brown" not in (backgrounds[0], backgrounds[4])


def test_the_focus_items_cursor_is_the_terminals(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "t = c.create_text(2, 2, text='hello', anchor='nw')\n"
            "c.focus_set()\n"
            "c.focus(t)\n"
            "c.icursor(t, 3)"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: t.cursor_cell() == (1, 5), message="the cursor in hello")


def test_a_quarter_pieslice_inks_only_the_upper_right(terminal, tmp_path):
    """Angles run counter-clockwise from three o'clock, as Tk's do."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("c.create_arc(0, 0, 20, 20, extent=90, fill='red', outline='red')"),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: (2, 15) in inked(t), message="the slice")
    term.wait_for_idle()
    cells = inked(term)
    assert all(column >= 10 and row <= 5 for row, column in cells)
    assert (2, 15) in cells


def test_an_image_item_draws_and_follows_its_image(terminal, tmp_path):
    """A 4x4 photo at (10, 4) fills cells 10-13 of rows 2 and 3; a put()
    after the loop starts shows without anything asked of the canvas."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "photo = tkcurses.PhotoImage(width=4, height=4)\n"
            "photo.put('red', to=(0, 0, 4, 4))\n"
            "c.create_image(10, 4, image=photo, anchor='nw')\n"
            "def grow():\n"
            "    photo.configure(width=6)\n"
            "    photo.put('red', to=(4, 0, 6, 4))\n"
            "root.after(300, grow)"
        ),
        workdir=tmp_path,
    )
    first = {(row, column) for row in (2, 3) for column in range(10, 14)}
    term.wait_for(lambda t: first <= inked(t), message="the image")
    grown = first | {(row, column) for row in (2, 3) for column in (14, 15)}
    term.wait_for(lambda t: inked(t) == grown, message="the image, wider")


def test_a_built_in_bitmap_draws_as_its_glyph(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("c.create_bitmap(5, 6, bitmap='question', anchor='nw')"),
        workdir=tmp_path,
    )
    term.wait_for_cell(3, 5, lambda cell: cell.data == "?")


def test_a_button_in_a_canvas_is_clicked_and_follows_the_view(terminal, tmp_path):
    """The canvas lays the button out; a click reaches it; scrolling the
    view moves it, and scrolling it out of sight takes it off the screen."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "c.configure(scrollregion=(0, 0, 200, 40))\n"
            "said = tkcurses.Label(root, text='', borderwidth=0)\n"
            "said.place(x=0, y=11)\n"
            "b = tkcurses.Button(c, text='Go',"
            " command=lambda: said.configure(text='pressed'))\n"
            "c.create_window(10, 4, window=b, anchor='nw')\n"
            "root.bind('<Key-l>', lambda e: c.xview_scroll(4, 'units'))\n"
            "root.bind('<Key-f>', lambda e: c.xview_moveto(1))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("Go")
    row, column = next(
        (r, line.index("Go")) for r, line in enumerate(term.display) if "Go" in line
    )
    term.click(column, row)
    term.wait_for_text("pressed")
    term.send(b"l")
    term.wait_for(
        lambda t: "Go" in t.display[row] and t.display[row].index("Go") < column,
        message="the button, moved left",
    )
    term.send(b"f")
    term.wait_for(lambda t: not any("Go" in line for line in t.display))
