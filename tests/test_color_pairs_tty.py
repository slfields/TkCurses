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

"""Colour pairs are recycled, so the second colourful thing is still itself.

A pair is the scarcest thing a terminal has: 255, because that is all eight
bits of ``A_COLOR`` can name. They were never given back once handed out, so
the table was append-only for the life of the screen - and one photograph
very nearly fills it. Measured on xterm-256color before this was fixed, with
the two perl-Tk demo images:

    mickey.gif  allocated=238  exhausted=False
    earth.gif   allocated=255  exhausted=True
    mickey.gif  allocated=255  exhausted=True
    earth.gif   allocated=255  exhausted=True

From the second image onwards every new colour fell back to the nearest pair
the FIRST image happened to leave behind, so an image viewer showed its first
picture correctly and every later one in the wrong palette.

**This has to be tested through the whole path, not against the allocator.**
The allocator in isolation looked completely healthy - it degrades exactly as
designed when it runs out - and that is precisely what kept this invisible.
What was wrong was that nothing ever gave a pair back, which is only visible
when something draws, stops drawing, and something else draws in its place.

The images here are generated rather than read from disk: the demo images
are not installed on a CI runner, and a picture whose every pixel is a
different colour is a harsher test of the table than a photograph anyway.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

#: One picture is WIDE * TALL / 2 = 192 cells, and every cell is built to be
#: a *different* (fg, bg) pair - see ``picture``. Two pictures therefore ask
#: for 384 pairs between them, which cannot fit in 255 unless the first
#: one's are given back. This is the whole mechanism of the test, and it has
#: to be arranged rather than assumed: a first attempt used 128-cell images
#: whose colours wrapped the cube, all four shared their pairs, the table
#: peaked at 217 and the test passed with the bug still in.
WIDE, TALL = 24, 16

#: Images are written past curses on any terminal with 256 colours or more,
#: so they no longer touch the pair table there. These tests are ABOUT the
#: pair table, so they ask for the setting that sends drawing back through
#: it - which is also the escape hatch for a terminal that mis-renders the
#: sequences.
PAIRS_ONLY = {
    "TERM": "xterm-256color",
    "COLORTERM": "",
    "TKCURSES_DISPLAY_DIRECT_IMAGES": "0",
}


def program(shades: str) -> str:
    """An app that shows several all-unique-colour images in turn.

    ``shades`` picks which corner of the colour cube each image lives in, so
    the second image cannot be drawn with the first one's pairs by accident.
    """
    return f"""
import tkcurses

root = tkcurses.Tk()
manager = root.tk.colors
label = tkcurses.Label(root)
label.place(x=0, y=3)
report = tkcurses.Label(root, text="", anchor="w")
report.place(x=0, y=0, width=78)
state = {{"i": 0, "held": [], "worst": 0, "ever_exhausted": False}}

ORDER = {shades!r}


# The 6x6x6 cube xterm actually has. Colours are taken FROM it rather than
# near it, because anything finer is quantised onto these levels before the
# pair table ever sees it - a first attempt stepped each channel by 3 and
# every pixel in a row collapsed onto the same cube entry, so the picture
# asked for a handful of pairs instead of a hundred and the test passed
# with the bug still in place.
LEVELS = (0, 95, 135, 175, 215, 255)


def cube(index):
    index %= 216
    return "#%02x%02x%02x" % (
        LEVELS[index // 36],
        LEVELS[(index // 6) % 6],
        LEVELS[index % 6],
    )


# A picture whose every CELL is a distinct (fg, bg) pair. Built cell by cell
# rather than pixel by pixel, because the pair is what is scarce: the top
# pixel of a cell walks the cube in order and the bottom one walks it seven
# at a time, so no two cells ask for the same combination. The base shifts
# only the bottom pixel, which makes a second picture whose pairs are
# disjoint from those of the first.
def picture(base):
    art = tkcurses.PhotoImage(master=root, width={WIDE}, height={TALL})
    for cell_row in range({TALL} // 2):
        for x in range({WIDE}):
            k = cell_row * {WIDE} + x
            art.put(cube(k), to=(x, cell_row * 2, x + 1, cell_row * 2 + 1))
            art.put(
                cube(k * 7 + base),
                to=(x, cell_row * 2 + 1, x + 1, cell_row * 2 + 2),
            )
    return art


def step():
    i = state["i"]
    if i >= len(ORDER):
        report.configure(
            text=f"DONE worst={{state['worst']}} ever={{state['ever_exhausted']}}"
        )
        return
    art = picture(ORDER[i])
    state["held"] = [art]
    label.configure(image=art)
    state["i"] = i + 1
    root.after(200, settle)


def settle():
    # Read after a frame has been through _update_display, so any renewal
    # has already happened and been repainted.
    state["worst"] = max(state["worst"], manager.allocated)
    state["ever_exhausted"] = state["ever_exhausted"] or manager.exhausted
    report.configure(
        text=f"SHOWN {{state['i']}} allocated={{manager.allocated}}"
        f" exhausted={{manager.exhausted}} remaining={{manager.remaining}}"
    )
    root.after(200, step)


root.after(200, step)
root.after(20000, root.quit)
root.mainloop()
"""


def test_four_colourful_images_in_turn_never_strand_the_pair_table(terminal):
    """The regression, end to end: the fourth image is still drawn as itself.

    Before pairs were recycled this reported ``ever=True`` from the second
    image onwards and never recovered.
    """
    term = terminal(cols=80, rows=24, env=PAIRS_ONLY)
    term.run_source(program([1, 2, 3, 4]))
    term.wait_for(lambda t: any("DONE" in row for row in t.display), timeout=40)

    line = next(row for row in term.display if "DONE" in row)
    assert "ever=False" in line, (
        f"the pair table ran dry and stayed dry: {line.strip()!r}. "
        "Pairs belonging to an image that is no longer shown must be "
        "reclaimed, or every later picture is drawn in the first one's palette."
    )


def test_a_later_image_is_drawn_in_its_own_colours(terminal):
    """Not merely 'not exhausted' - the colours on screen are the new ones.

    The two images sit in opposite corners of the colour cube, so drawing
    the second one out of the first one's table would show blues where
    yellows belong. This asserts on the terminal, which is the only place
    that can tell the difference.
    """
    term = terminal(cols=80, rows=24, env=PAIRS_ONLY)
    term.run_source(program([1, 2]))
    term.wait_for(lambda t: any("DONE" in row for row in t.display), timeout=40)

    # The picture occupies rows 3 onwards; read the band it fills.
    seen = set()
    for row in range(3, 3 + TALL // 2):
        for col in range(WIDE):
            cell = term.char_at(row, col)
            seen.add((cell.fg, cell.bg))
    # Every cell of the picture is built to be a different pair, so a screen
    # showing it faithfully has exactly that many. This is exact rather than
    # a threshold because the number comes from how the picture is made, not
    # from what a run happened to produce. Measured at 192 when pairs are
    # recycled and 171 when they are not: the missing 21 are cells that had
    # to share somebody else's nearest colour.
    assert len(seen) == WIDE * TALL // 2, (
        f"{len(seen)} distinct pairs on screen, {WIDE * TALL // 2} expected. "
        "Cells have collapsed onto each other's colours, which is what a "
        "table still full of the previous picture's pairs forces."
    )


def test_the_budget_is_reported_and_shrinks_with_use(terminal):
    """`capacity` and `remaining` are what an image sizing itself will ask."""
    term = terminal(cols=80, rows=24, env=PAIRS_ONLY)
    term.run_source(program([1]))
    term.wait_for(lambda t: any("SHOWN 1" in row for row in t.display), timeout=40)

    line = next(row for row in term.display if "SHOWN 1" in row)
    allocated = int(line.split("allocated=")[1].split()[0])
    remaining = int(line.split("remaining=")[1].split()[0])
    assert allocated > 0, f"a colourful picture allocated nothing: {line.strip()!r}"
    assert allocated + remaining == 255, (
        "allocated and remaining must account for the whole table, and the "
        f"table is 255 pairs: {line.strip()!r}"
    )


# --------------------------- past curses, for pictures it cannot hold


def picture_program(cells_wide: int, cells_tall: int) -> str:
    """An app showing a picture with a different colour in every cell."""
    return f"""
import tkcurses

root = tkcurses.Tk()
art = tkcurses.PhotoImage(
    master=root, width={cells_wide}, height={cells_tall * 2}
)
for y in range({cells_tall * 2}):
    for x in range({cells_wide}):
        art.put(f"#{{x * 7 % 256:02x}}{{y * 11 % 256:02x}}{{(x * y) % 256:02x}}",
                to=(x, y, x + 1, y + 1))
held = [art]
label = tkcurses.Label(root, image=art, anchor="nw")
label.place(x=0, y=1, width={cells_wide}, height={cells_tall})
ready = tkcurses.Label(root, text="", anchor="w")
ready.place(x=0, y=0, width=8)
root.update_layout()
root.tk.screen.refresh()

def settled():
    # Said only once the mainloop has pumped a frame. The picture is
    # written past curses in _update_display, so reading on the refresh
    # above reads the frame BEFORE it is finished.
    ready.configure(text="DONE")
    root.update_layout()
    root.tk.screen.refresh()

root.after(500, settled)
root.after(15000, root.quit)
root.mainloop()
"""


def distinct_pairs(term, wide, tall):
    return len(
        {
            (term.char_at(y + 1, x).fg, term.char_at(y + 1, x).bg)
            for y in range(tall)
            for x in range(wide)
        }
    )


def test_a_picture_is_not_held_to_the_255_pairs_curses_can_name(terminal):
    """The ceiling broken, which is the whole point of painting past curses.

    Python's curses cannot name more than 255 pairs - color_pair(300) wraps
    to 44 - and a photograph wants thousands. With COLORTERM saying the
    terminal takes direct colour, the cells are written as SGR instead and
    the limit stops applying.
    """
    wide, tall = 60, 20
    term = terminal(
        cols=wide + 4,
        rows=tall + 4,
        env={"TERM": "xterm-256color", "COLORTERM": "truecolor"},
    )
    term.run_source(picture_program(wide, tall))
    term.wait_for(lambda t: any("DONE" in row for row in t.display), timeout=40)

    seen = distinct_pairs(term, wide, tall)
    assert seen > 255, (
        f"only {seen} distinct colour pairs on a {wide}x{tall} picture; the "
        "255-pair ceiling is still being applied"
    )


def test_without_colorterm_the_palette_form_is_used(terminal):
    """A 256-colour terminal is still written to directly - in ITS form.

    The ceiling is worth escaping on any terminal with a palette, not only
    on one with direct colour: measured on mickey.gif, 14 colours through
    the pair table against 88 written by hand. So the cells are still
    written here, as ESC[38;5;N against the palette - and never as
    ESC[38;2;r;g;b, which this terminal has not said it understands.
    """
    wide, tall = 60, 20
    term = terminal(
        cols=wide + 4, rows=tall + 4, env={"TERM": "xterm-256color", "COLORTERM": ""}
    )
    term.run_source(picture_program(wide, tall))
    term.wait_for(lambda t: any("DONE" in row for row in t.display), timeout=40)

    raw = bytes(term._received)
    assert b"\x1b[38;5;" in raw, "the palette form was never written"
    assert b"\x1b[38;2;" not in raw, (
        "direct colour was written to a terminal that never said it could take it"
    )
    assert distinct_pairs(term, wide, tall) > 255, (
        "the 255-pair ceiling is still being applied on a palette terminal"
    )


def test_eight_colours_is_left_to_curses(terminal):
    """Nothing to escape there: 8 colours makes 64 combinations, not 255."""
    wide, tall = 60, 20
    term = terminal(
        cols=wide + 4, rows=tall + 4, env={"TERM": "xterm", "COLORTERM": ""}
    )
    term.run_source(picture_program(wide, tall))
    term.wait_for(lambda t: any("DONE" in row for row in t.display), timeout=40)

    raw = bytes(term._received)
    assert b"\x1b[38;5;" not in raw and b"\x1b[38;2;" not in raw, (
        "an eight-colour terminal was sent extended colour sequences"
    )


def test_the_escape_hatch_sends_drawing_back_through_curses(terminal):
    """A terminal that mis-renders the sequences needs a way out.

    TKCURSES_DISPLAY_DIRECT_IMAGES=0. The picture then costs what it used to
    - held to the pairs curses can name - which is the point: correct
    everywhere rather than better only where it works.
    """
    wide, tall = 60, 20
    term = terminal(cols=wide + 4, rows=tall + 4, env=PAIRS_ONLY)
    term.run_source(picture_program(wide, tall))
    term.wait_for(lambda t: any("DONE" in row for row in t.display), timeout=40)

    raw = bytes(term._received)
    assert b"\x1b[38;2;" not in raw, "direct colour written with the hatch shut"
    assert distinct_pairs(term, wide, tall) <= 255


def test_the_text_beside_a_picture_keeps_its_own_colours(terminal):
    """The overlay must not bleed. SGR is reset when the picture ends."""
    wide, tall = 60, 20
    term = terminal(
        cols=wide + 4,
        rows=tall + 4,
        env={"TERM": "xterm-256color", "COLORTERM": "truecolor"},
    )
    term.run_source(picture_program(wide, tall))
    term.wait_for(lambda t: any("DONE" in row for row in t.display), timeout=40)

    row, column = term.find_text("DONE")
    cell = term.char_at(row, column)
    assert cell.fg in ("default", "white"), (
        f"the label beside the picture came out {cell.fg!r}; the picture's "
        "colours leaked past its own cells"
    )
