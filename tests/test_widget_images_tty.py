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

"""What an image actually puts on the terminal.

The geometry is covered without a terminal in test_widget_images.py; this is
the half only a screen can answer - and on this plane that means checking
the *glyphs*, because which half-block appears is the whole evidence that
two pixel rows were folded into one cell.

The fixture image is 2 pixels wide and 2 tall, all lit, so it must arrive as
a single row of `██`. A `▀` or a `▄` there would mean a row went missing.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

#: The glyphs a composed cell can use, and nothing else ever reaches the
#: screen from an image.
UPPER, LOWER, FULL = "▀", "▄", "█"


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
art = tkcurses.PhotoImage(master=root, width=2, height=2)
art.put('red', to=(0, 0, 2, 2))
{body}
root.update_layout()
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


#: What a colour name renders as, so an assertion can be written with the
#: name whichever form reached the terminal.
_AS_RGB = {
    "black": "000000",
    "red": "cd0000",
    "green": "00cd00",
    "brown": "cdcd00",
    "yellow": "cdcd00",
    "blue": "0000ee",
    "magenta": "cd00cd",
    "cyan": "00cdcd",
    "white": "e5e5e5",
}


def colour_at(term, row, column, which="fg"):
    """The colour of one cell, as a NAME wherever one fits.

    An image's cells are written past curses now - as ``ESC[38;5;N`` against
    the palette, or ``ESC[38;2;r;g;b`` where the terminal takes direct
    colour - so pyte reports them as hex where it used to report a name for
    the basic ``ESC[36m`` form curses emitted. It is the same colour on the
    terminal; only the spelling changed. This turns it back so the
    assertions can stay written in names.
    """
    value = term.attrs_at(row, column)[which]
    for name, rgb in _AS_RGB.items():
        if value == rgb:
            return name
    return value


def block(term, x, y, width, height):
    """The rectangle of screen at (x, y), as a list of row strings."""
    return [row[x : x + width] for row in term.display[y : y + height]]


def test_a_label_draws_its_image(terminal, tmp_path):
    """Two lit pixel rows fold into one cell of full block."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("tkcurses.Label(root, image=art, anchor='nw').place(x=4, y=3)"),
        workdir=tmp_path,
    )
    term.wait_for_text(FULL)
    assert block(term, 4, 3, 2, 1) == [FULL * 2]


def test_one_lit_row_draws_the_upper_half(terminal, tmp_path):
    """The evidence that a pixel really is half a cell."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "art.transparency_set(0, 1, True)\n"
            "art.transparency_set(1, 1, True)\n"
            "tkcurses.Label(root, image=art, anchor='nw').place(x=0, y=0)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text(UPPER)
    assert block(term, 0, 0, 2, 1) == [UPPER * 2]


def test_the_lower_row_alone_draws_the_lower_half(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "art.transparency_set(0, 0, True)\n"
            "art.transparency_set(1, 0, True)\n"
            "tkcurses.Label(root, image=art, anchor='nw').place(x=0, y=0)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text(LOWER)
    assert block(term, 0, 0, 2, 1) == [LOWER * 2]


def test_a_tall_image_takes_half_as_many_rows(terminal, tmp_path):
    """Eight pixel rows are four rows of terminal, not eight."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tall = tkcurses.PhotoImage(master=root, width=3, height=8)\n"
            "tall.put('cyan', to=(0, 0, 3, 8))\n"
            "tkcurses.Label(root, image=tall, anchor='nw').place(x=0, y=0)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text(FULL)
    term.wait_for_idle()
    assert block(term, 0, 0, 3, 5) == [FULL * 3] * 4 + ["   "]


def test_two_colours_share_one_cell(terminal, tmp_path):
    """A cell whose halves disagree keeps both, as a foreground and a background."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "pair = tkcurses.PhotoImage(master=root, data=[['red'], ['blue']])\n"
            "tkcurses.Label(root, image=pair, anchor='nw').place(x=0, y=0)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text(UPPER)
    term.wait_for_idle()
    assert term.display[0][0] == UPPER
    assert colour_at(term, 0, 0) == "red"
    assert colour_at(term, 0, 0, "bg") == "blue"


def test_an_image_hides_the_text_by_default(terminal, tmp_path):
    """compound defaults to none, and none means the image wins."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("tkcurses.Label(root, text='hello', image=art).place(x=0, y=0)"),
        workdir=tmp_path,
    )
    term.wait_for_text(FULL)
    term.wait_for_idle()
    assert "hello" not in "\n".join(term.display)


def test_compound_left_draws_the_image_then_the_text(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tkcurses.Label(root, text='hi', image=art, compound='left',"
            " anchor='nw').place(x=0, y=0)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("hi")
    assert block(term, 0, 0, 5, 1) == [f"{FULL * 2} hi"]


def test_compound_right_draws_the_text_then_the_image(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tkcurses.Label(root, text='hi', image=art, compound='right',"
            " anchor='nw').place(x=0, y=0)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("hi")
    assert block(term, 0, 0, 5, 1) == [f"hi {FULL * 2}"]


def test_compound_top_stacks_the_image_above(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tkcurses.Label(root, text='hi', image=art, compound='top',"
            " anchor='nw').place(x=0, y=0)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("hi")
    assert block(term, 0, 0, 2, 2) == [FULL * 2, "hi"]


def test_compound_bottom_stacks_the_image_below(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tkcurses.Label(root, text='hi', image=art, compound='bottom',"
            " anchor='nw').place(x=0, y=0)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("hi")
    assert block(term, 0, 0, 2, 2) == ["hi", FULL * 2]


def test_a_hole_shows_what_is_behind_it(terminal, tmp_path):
    """A transparent pixel is skipped, not painted.

    Asserted on the colour, because the characters cannot tell the two
    apart. The image paints in red; a cell whose pixels are both holes is
    never written at all, so it keeps the label's own blue.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "art.transparency_set(0, 0, True)\n"
            "art.transparency_set(0, 1, True)\n"
            "tkcurses.Label(root, image=art, background='blue', anchor='nw')"
            ".place(x=0, y=0, width=4, height=2)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text(FULL)
    term.wait_for_idle()
    assert term.display[0][0] == " "
    assert colour_at(term, 0, 0, "bg") == "blue"
    assert term.display[0][1] == FULL
    assert colour_at(term, 0, 1) == "red"


def test_the_image_repaints_when_it_is_written_to(terminal, tmp_path):
    """A widget follows its image with nothing asked of the widget."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tkcurses.Label(root, image=art, anchor='nw').place(x=0, y=0)\n"
            "root.after(200, lambda: (art.put('green', to=(0, 0, 2, 1)),"
            " art.transparency_set(0, 1, True),"
            " art.transparency_set(1, 1, True),"
            " root.tk.screen.refresh()))"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: t.display[0][0] == UPPER, message="the repainted image")
    term.wait_for_idle()
    assert colour_at(term, 0, 0) == "green"


def test_the_widget_grows_when_its_image_does(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tkcurses.Label(root, image=art, anchor='nw').place(x=0, y=0)\n"
            # configure, not put: put clips to the image it writes into, so
            # it can change the pixels but never the size.
            "root.after(200, lambda: (art.configure(width=4, height=8),"
            " art.put('red', to=(0, 0, 4, 8)), root.update_layout(),"
            " root.tk.screen.refresh()))"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: t.display[3][0:4] == FULL * 4, message="the grown image")
    # 8 pixel rows is 4 rows of terminal.
    assert block(term, 0, 0, 4, 4) == [FULL * 4] * 4


def test_a_button_draws_an_image_and_still_reads_as_a_button(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tkcurses.Button(root, text='Go', image=art, compound='left')"
            ".place(x=2, y=1)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("Go")
    joined = "\n".join(term.display)
    assert FULL in joined
    assert "Go" in joined


def test_a_bitmap_draws_its_set_bits(terminal, tmp_path):
    """Set bits paint, clear bits are holes - on the same plane."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "bits = tkcurses.BitmapImage(master=root, data=['XX', 'XX'],"
            " foreground='cyan')\n"
            "tkcurses.Label(root, image=bits, anchor='nw').place(x=0, y=0)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text(FULL)
    term.wait_for_idle()
    assert block(term, 0, 0, 2, 1) == [FULL * 2]
    assert colour_at(term, 0, 0) == "cyan"


def test_art_stops_being_drawn_when_its_image_is_collected(terminal, tmp_path):
    """The trap, on the screen rather than in the geometry.

    Collection is silent - the registry just stops holding the image, and
    the list of widgets watching it dies with it - so nothing in the normal
    change notification can report this. Without a finalizer the widget goes
    on showing cells whose image no longer exists: not stale art, undrawable
    art, since the widget already agrees it has no image.

    Measured on Tk 9.0.2, the widget keeps the size it negotiated: deleting
    an image under a live Label left it at 22x12. Only the drawing stops.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "import gc\n"
            "held = [art]\n"
            "lab = tkcurses.Label(root, image=art, anchor='nw')\n"
            "lab.place(x=0, y=0)\n"
            "def drop():\n"
            "    held.clear()\n"
            "    globals().pop('art')\n"
            "    gc.collect()\n"
            "    buffer.write(6, 0, 'dropped %dx%d'"
            " % (lab.winfo_reqwidth(), lab.winfo_reqheight()))\n"
            "    root.tk.screen.refresh()\n"
            "root.after(200, drop)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text(FULL)
    term.wait_for_text("dropped")
    term.wait_for_idle()
    assert block(term, 0, 0, 2, 1) == ["  "]
    # The geometry it negotiated survives; only the image goes.
    assert "dropped 2x1" in "\n".join(term.display)


@pytest.mark.parametrize(
    ("show", "hide"),
    [("place(x=0, y=0)", "destroy()"),
     ("place(x=0, y=0)", "place_forget()"),
     ("pack(anchor='nw')", "pack_forget()")],
)  # fmt: skip
def test_a_picture_goes_with_its_widget(terminal, tmp_path, show, hide):
    """A picture's cells are written past curses, and re-emitted every
    frame; a widget destroyed or unmapped must take them with it, or they
    go on being painted over whatever curses draws there. They did: only
    drawing cleared them, and a gone widget does not draw."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            f"lab = tkcurses.Label(root, image=art, anchor='nw', borderwidth=0)\n"
            f"lab.{show}\n"
            "def drop():\n"
            f"    lab.{hide}\n"
            "    tkcurses.Label(root, text='ab', borderwidth=0).place(x=0, y=0)\n"
            # A picture drawn afterwards is what brought the old one back:
            # the painter wrote out everything it held whenever it changed.
            "    tkcurses.Label(root, image=art, borderwidth=0).place(x=9, y=0)\n"
            "root.after(200, drop)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text(FULL)
    # What is drawn where the picture was must show, not the picture.
    term.wait_for_cell(0, 9, lambda cell: cell.data == FULL, message="the new one")
    term.wait_for_text("ab", timeout=3)
    term.wait_for_idle()
    assert block(term, 0, 0, 2, 1) == ["ab"]


def test_a_picture_is_painted_again_when_curses_repaints_it(terminal, tmp_path):
    """Curses writes a picture's cells in the nearest colour it can name,
    and the exact colour has to be painted over them again that frame. It
    was not, because the frame was judged by the screen buffer alone, and
    widgets draw on panels."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "lab = tkcurses.Label(root, image=art, anchor='nw', borderwidth=0)\n"
            "lab.place(x=0, y=0)\n"
            # The same picture in the same place on a new widget: curses
            # writes the new cells in its own colours, and the painter holds
            # exactly what it wrote last, so only a frame known to have
            # repainted sends the exact colour again.
            "def redraw():\n"
            "    lab.destroy()\n"
            "    again = tkcurses.Label(root, image=art, anchor='nw', borderwidth=0)\n"
            "    again.place(x=0, y=0)\n"
            "    tkcurses.Label(root, text='redrawn').place(x=0, y=5)\n"
            "root.after(200, redraw)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_cell(0, 0, lambda cell: cell.data == FULL, message="the picture")
    term.wait_for_text("redrawn")
    term.wait_for_idle()
    # cd0000 is red written past curses; "red" is curses' own pair.
    assert term.attrs_at(0, 0)["fg"] == "cd0000"


def test_an_image_larger_than_its_window_fills_it_to_the_edges(terminal, tmp_path):
    """The clipped draw must reach the last visible row and column.

    A repaint composes only the pixels that can land in the widget, because
    composing a whole photograph and discarding 91% of it cost 47ms a frame.
    Every test before this one used an image that fitted inside its window,
    so a clip one cell too tight in either direction went unnoticed - it
    only shows where the image runs past the edge, which is the case that
    made clipping worth doing.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "big = tkcurses.PhotoImage(master=root, width=60, height=40)\n"
            "big.put('red', to=(0, 0, 60, 40))\n"
            "tkcurses.Label(root, image=big, anchor='nw', background='')"
            ".place(x=0, y=0, width=10, height=4)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text(FULL)
    term.wait_for_idle()
    # Every cell of the 10x4 window, corners included.
    assert block(term, 0, 0, 10, 4) == [FULL * 10] * 4
    # And nothing outside it.
    assert term.display[4][:10].strip() == ""
    assert term.display[0][10:].strip() == ""


def test_an_image_clipped_by_the_screen_edge_still_fills_what_shows(terminal, tmp_path):
    """Placed partly off-screen, the visible part must be complete."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "big = tkcurses.PhotoImage(master=root, width=60, height=40)\n"
            "big.put('red', to=(0, 0, 60, 40))\n"
            "tkcurses.Label(root, image=big, anchor='nw', background='')"
            ".place(x=34, y=9, width=20, height=8)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text(FULL)
    term.wait_for_idle()
    # Columns 34..39 and rows 9..11 are all that fit, and all must be drawn.
    assert block(term, 34, 9, 6, 3) == [FULL * 6] * 3
