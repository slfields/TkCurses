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
"""The example programs run, and do what the examples page says they do.

Each file in ``examples/`` is on ``docs/guide/examples.md``, where the docs
build runs it for its picture; these run each one again and use it the way
the page tells a reader to.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
PAGE = ROOT / "docs" / "guide" / "examples.md"
TIMES = "\N{MULTIPLICATION SIGN}"
DIRECTIVE = re.compile(r"^```\{tkcurses-example\} (\S+)$", re.M)


def source(name: str, *argv: str) -> str:
    """The program, with ``sys.argv`` set as if run with ``argv``."""
    text = (EXAMPLES / f"{name}.py").read_text()
    if not argv:
        return text
    return f"import sys\nsys.argv[1:] = {list(argv)!r}\n" + text


def start(terminal, tmp_path, name, *argv, cols=60, rows=16):
    term = terminal(cols=cols, rows=rows)
    term.run_source(source(name, *argv), workdir=tmp_path)
    term.wait_for(lambda t: any(line.strip() for line in t.display), message="a screen")
    return term


def test_every_example_is_on_the_page_and_nothing_else_is():
    shown = DIRECTIVE.findall(PAGE.read_text())
    files = sorted(f"examples/{path.name}" for path in EXAMPLES.glob("*.py"))
    assert sorted(shown) == files
    assert len(files) == 16


def test_every_example_carries_the_notice():
    for path in EXAMPLES.glob("*.py"):
        assert "SPDX-License-Identifier: GPL-3.0-only" in path.read_text()


@pytest.mark.tty
@pytest.mark.parametrize("name", sorted(p.stem for p in EXAMPLES.glob("*.py")))
def test_each_example_starts_and_ctrl_c_closes_it(terminal, tmp_path, name):
    term = start(terminal, tmp_path, name, rows=20)
    term.wait_for_idle()
    term.send(b"\x03")
    assert term.wait_for_exit() == 0
    assert term.stderr == ""


@pytest.mark.tty
def test_hello_quits_from_its_button(terminal, tmp_path):
    term = start(terminal, tmp_path, "hello")
    term.wait_for_text("Quit")
    term.send_keys("<Tab>", "<Return>")
    assert term.wait_for_exit() == 0


@pytest.mark.tty
def test_the_form_refuses_an_empty_name(terminal, tmp_path):
    term = start(terminal, tmp_path, "form", rows=20)
    term.wait_for_text("Country")
    term.send_keys(*["<Tab>"] * 7, "<Return>")
    term.wait_for_text("A name and an email address, please")


@pytest.mark.tty
def test_the_form_welcomes_a_new_account(terminal, tmp_path):
    term = start(terminal, tmp_path, "form", rows=20)
    term.wait_for_text("Country")
    # Tab to the Pro radio button, and space to choose it, as in Tk.
    term.send_keys("Ada", "<Tab>", "ada@example.org", "<Tab>", "<Tab>", "<Tab>", " ")
    term.send_keys(*["<Tab>"] * 3, "<Return>")
    # Busy for a second first, while the account is made.
    term.wait_for_text("Creating your account...")
    term.wait_for_text("Ada, your pro account is ready.")


@pytest.mark.tty
def test_the_list_adds_marks_and_removes(terminal, tmp_path):
    term = start(terminal, tmp_path, "todo", cols=40, rows=14)
    term.wait_for_text("2 tasks, 0 done")
    term.send_keys("Buy bread", "<Return>")
    term.wait_for_text("3 tasks, 0 done")
    term.send_keys("<Tab>", " ")
    term.wait_for_text("[x] Water the plants")
    term.wait_for_text("3 tasks, 1 done")
    term.send_keys("<Delete>")
    term.wait_for(
        lambda t: t.contains("2 tasks, 0 done") and not t.contains("Water the plants"),
        message="the task removed and counted",
    )


@pytest.mark.tty
def test_the_editor_opens_edits_and_saves_a_file(terminal, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("first line\n")
    term = start(terminal, tmp_path, "editor", str(notes))
    term.wait_for_text("notes.txt   line 1, column 1")
    term.send_keys("<End>", " added")
    term.wait_for_text("notes.txt (changed)   line 1, column 17")
    term.send(b"\x13")  # Ctrl-S
    term.wait_for_text("notes.txt   line 1, column 17")
    assert notes.read_text() == "first line added\n"


@pytest.mark.tty
def test_the_editor_asks_before_losing_changes(terminal, tmp_path):
    term = start(terminal, tmp_path, "editor")
    term.wait_for_text("untitled")
    term.send_keys("words")
    term.wait_for_text("untitled (changed)")
    term.send(b"\x11")  # Ctrl-Q
    term.wait_for_text("Quit without saving?")
    term.send_keys("<Escape>")
    term.wait_for(
        lambda t: not t.contains("Quit without saving?"), message="the question gone"
    )
    assert term.exit_status is None


@pytest.mark.tty
def test_the_editor_menu_opens_from_the_keyboard(terminal, tmp_path):
    term = start(terminal, tmp_path, "editor")
    term.wait_for_text("untitled")
    term.send_keys("<F10>")
    term.wait_for_text("Ctrl+O")
    assert term.contains("Save as...")


@pytest.mark.tty
def test_the_editor_view_menu_recolours_it(terminal, tmp_path):
    term = start(terminal, tmp_path, "editor")
    term.wait_for_text("untitled")
    row = next(r for r, line in enumerate(term.display) if "View" in line) + 2
    before = term.attrs_at(row, 5)["bg"]
    term.send_keys("<F10>", "<Right>", "<Right>")
    term.wait_for_text("Bisque")
    term.send_keys("d")
    term.wait_for(
        lambda t: t.attrs_at(row, 5)["bg"] not in (before, None),
        message="the text recoloured",
    )


@pytest.mark.tty
def test_the_editor_view_menu_shows_swatches_and_tears_off(terminal, tmp_path):
    term = start(terminal, tmp_path, "editor")
    term.wait_for_text("untitled")
    term.send_keys("<F10>", "<Right>", "<Right>")
    term.wait_for_text("Bisque")
    row = next(r for r, line in enumerate(term.display) if "Bisque" in line)
    swatch = term.display[row].index("Bisque") - 3
    term.wait_for_cell(row, swatch, lambda c: c.data == "█", message="a swatch")
    # Down lands on the dashed line first; Return tears the menu off.
    term.send_keys("<Down>", "<Return>")
    term.wait_for(
        lambda t: any("─View" in line for line in t.display),
        message="the torn-off View menu, titled",
    )
    term.send_keys("<Down>", "<Down>", "<Return>")
    term.wait_for(
        lambda t: (
            t.attrs_at(row + 4, 5)["bg"] not in (None, "black")
            and any("─View" in line for line in t.display)
        ),
        message="Bisque chosen, and the copy still up",
    )


@pytest.mark.tty
def test_the_table_shows_the_chosen_planet(terminal, tmp_path):
    term = start(terminal, tmp_path, "table", cols=52, rows=14)
    term.wait_for_text("Neptune")
    term.send_keys("<Down>", "<Down>", "<Return>")
    term.wait_for_text("Earth: 1.00 AU from the Sun, 1 moon")


@pytest.mark.tty
def test_a_number_sorts_the_table_and_again_reverses_it(terminal, tmp_path):
    term = start(terminal, tmp_path, "table", cols=52, rows=14)
    term.wait_for_text("Neptune")
    row = next(r for r, line in enumerate(term.display) if "Moons" in line)

    def first(t):
        return t.display[row + 1].lstrip("│").split()[0]

    term.send_keys("3")
    term.wait_for(
        lambda t: t.contains("Moons ^") and first(t) == "Mercury", message="fewest"
    )
    term.send_keys("3")
    term.wait_for(
        lambda t: t.contains("Moons v") and first(t) == "Saturn", message="most"
    )
    term.send_keys("1")
    term.wait_for(
        lambda t: t.contains("Planet ^") and first(t) == "Earth", message="by name"
    )


@pytest.mark.tty
def test_clicking_a_heading_sorts_the_table_and_again_reverses_it(terminal, tmp_path):
    """The heading's command, which a Treeview stored and never called."""
    term = start(terminal, tmp_path, "table", cols=52, rows=14)
    term.wait_for_text("Neptune")
    row, column = term.find_text("Moons")

    def first(t):
        return t.display[row + 1].lstrip("│").split()[0]

    term.click(column, row)
    term.wait_for(
        lambda t: t.contains("Moons ^") and first(t) == "Mercury", message="fewest"
    )
    term.click(column, row)
    term.wait_for(
        lambda t: t.contains("Moons v") and first(t) == "Saturn", message="most"
    )


@pytest.mark.tty
def test_the_chart_draws_every_month_and_follows_a_resize(terminal, tmp_path):
    term = start(terminal, tmp_path, "chart", cols=50, rows=14)
    for month in ("Jan", "Feb", "Mar", "Apr", "May", "Jun"):
        term.wait_for_text(month)
    term.resize(60, 20)
    term.wait_for(
        lambda t: "Jun" in t.display[19] and t.display[19].index("Jun") > 45,
        message="the months along the new bottom row, spread wider",
    )


@pytest.mark.tty
def test_the_calculator_works_a_sum_typed(terminal, tmp_path):
    term = start(terminal, tmp_path, "calculator", cols=30, rows=14)
    term.wait_for_text("C")
    term.send_keys("12+30*2")
    term.wait_for(
        lambda t: (
            t.display[1].rstrip().endswith(f"42 {TIMES}")
            and t.display[2].strip() == "2"
        ),
        message="the sum so far above the number being typed",
    )
    term.send_keys("=")
    term.wait_for(
        lambda t: (
            t.display[1].strip() == f"42 {TIMES} 2 =" and t.display[2].strip() == "84"
        ),
        message="the answer, worked left to right",
    )


@pytest.mark.tty
def test_the_calculator_works_a_sum_clicked(terminal, tmp_path):
    term = start(terminal, tmp_path, "calculator", cols=30, rows=14)
    term.wait_for_text("C")
    for key in ("7", "+", "8", "="):
        row, column = term.find_text(key)
        term.click(column, row)
    term.wait_for(lambda t: t.display[2].strip() == "15", message="7 + 8 by mouse")


@pytest.mark.tty
def test_the_calculator_refuses_to_divide_by_zero(terminal, tmp_path):
    term = start(terminal, tmp_path, "calculator", cols=30, rows=14)
    term.wait_for_text("C")
    term.send_keys("7/0=")
    term.wait_for_text("Division by zero")
    term.send_keys("2+2=")
    term.wait_for(lambda t: t.display[2].strip() == "4", message="a fresh start")


@pytest.mark.tty
def test_the_calculator_keeps_a_long_answer_inside_the_window(terminal, tmp_path):
    """A display Label as wide as its text pushed the keys a cell right and
    cut the last figure off, until the grid followed Tk's arithmetic
    (TkCurses-xcy3); the four columns are one uniform group, as they would
    be in Tk, and the display asks for all it likes."""
    term = start(terminal, tmp_path, "calculator", cols=30, rows=14)
    term.wait_for_text("C")
    term.send_keys("999999999999*999999=", "*999999=")
    term.wait_for(
        lambda t: (
            t.display[2].strip() == "9.99998e+23"
            and t.display[1].rstrip().endswith(f"e+17 {TIMES} 999999 =")
        ),
        message="the whole answer, and the end of the sum - too wide for the window",
    )
    # The keys stay where they were; the sum is the Label's to cut, and,
    # anchored e, it loses its start, as in Tk (TkCurses-tyd9).
    assert term.display[4].index("C") == 3


def legend_colour(term, name):
    row, column = term.find_text(name)
    return term.attrs_at(row, column)["fg"]


def cells_coloured(term, colour):
    return sum(
        term.attrs_at(row, column)["fg"] == colour
        for row in range(1, len(term.display) - 1)
        for column in range(len(term.display[row]))
        if term.display[row][column] in "▀▄█"
    )


@pytest.mark.tty
def test_the_plot_hides_and_shows_a_curve(terminal, tmp_path):
    term = start(terminal, tmp_path, "plot", cols=60, rows=16)
    term.wait_for_text("2 cos x")
    term.wait_for_idle()
    blue = legend_colour(term, "2 cos x")
    assert cells_coloured(term, blue) > 30
    term.send_keys("2")
    term.wait_for(
        lambda t: legend_colour(t, "2 cos x") != blue and cells_coloured(t, blue) == 0,
        message="the cosine gone and its legend greyed",
    )
    term.send_keys("2")
    term.wait_for(lambda t: cells_coloured(t, blue) > 30, message="the cosine back")


@pytest.mark.tty
def test_the_plot_follows_a_resize(terminal, tmp_path):
    term = start(terminal, tmp_path, "plot", cols=60, rows=16)
    term.wait_for_text("4π")
    term.resize(80, 20)
    term.wait_for(
        lambda t: (
            t.display[19].rstrip().endswith("4π") and len(t.display[19].rstrip()) == 79
        ),
        message="the axis labels along the new bottom row, to the right edge",
    )


@pytest.mark.tty
def test_the_shapes_move_with_the_arrows(terminal, tmp_path):
    term = start(terminal, tmp_path, "shapes", cols=40, rows=14)
    term.wait_for_text("Moving the sun")
    row, column = term.find_text("~~")
    term.send_keys("<Tab>", "<Tab>", "<Tab>")
    term.wait_for_text("Moving the bird")
    term.send_keys("<Right>", "<Right>", "<Right>", "<Down>", "<Down>")
    term.wait_for(
        lambda t: t.find_text("~~") == (row + 1, column + 3),
        message="the bird three cells right and a row down",
    )


@pytest.mark.tty
def test_the_reset_button_on_the_canvas_puts_the_shapes_back(terminal, tmp_path):
    """The button is a window item: the canvas lays it out, and a click on it
    reaches it. moveto then puts each moved shape where it began."""
    term = start(terminal, tmp_path, "shapes", cols=40, rows=14)
    term.wait_for_text("Reset")
    row, column = term.find_text("~~")
    term.send_keys("<Tab>", "<Tab>", "<Tab>")
    term.wait_for_text("Moving the bird")
    term.send_keys("<Right>", "<Right>", "<Down>", "<Down>")
    term.wait_for(lambda t: t.find_text("~~") == (row + 1, column + 2))
    reset_row, reset_column = term.find_text("Reset")
    term.click(reset_column + 1, reset_row)
    term.wait_for(
        lambda t: t.find_text("~~") == (row, column), message="the bird back home"
    )


@pytest.mark.tty
def test_a_shape_is_dragged_with_the_mouse(terminal, tmp_path):
    term = start(terminal, tmp_path, "shapes", cols=40, rows=14)
    term.wait_for_text("Moving the sun")
    row, column = term.find_text("~~")
    term.send_mouse(column, row, action="press")
    term.wait_for_text("Moving the bird")
    # Two movements, so a drag measured from where it began is caught.
    term.send_mouse(column + 2, row, action="move")
    term.wait_for(
        lambda t: t.find_text("~~") == (row, column + 2), message="the drag under way"
    )
    term.send_mouse(column + 5, row, action="move")
    term.send_mouse(column + 5, row, action="release")
    term.wait_for(
        lambda t: t.find_text("~~") == (row, column + 5), message="the bird dragged"
    )


@pytest.mark.tty
def test_the_picture_zooms_and_moves(terminal, tmp_path):
    term = start(terminal, tmp_path, "picture", cols=60, rows=16)
    term.wait_for_text("-0.6000 +0.0000i, 1x")
    term.send_keys("+")
    term.wait_for_text("-0.6000 +0.0000i, 2x")
    term.send_keys("<Right>")
    term.wait_for_text("-0.2000 +0.0000i, 2x")
    term.send_keys("-", "-")
    term.wait_for_text("-0.2000 +0.0000i, 0.5x")


@pytest.mark.tty
def test_the_picture_opens_a_file_and_fills_the_window(terminal, tmp_path):
    width, height = 40, 20
    pixels = bytes(
        channel
        for y in range(height)
        for x in range(width)
        for channel in (x * 6, y * 12, 160)
    )
    (tmp_path / "ramp.ppm").write_bytes(b"P6 40 20 255\n" + pixels)
    term = start(terminal, tmp_path, "picture", str(tmp_path / "ramp.ppm"))
    term.wait_for_text("ramp.ppm, 40x20")
    # 40x20 pixels fit 60 columns by 15 rows at one and a half times.
    term.wait_for(
        lambda t: all(line == "▀" * 60 for line in t.display[:15]),
        message="the picture across the whole window",
    )
    assert term.attrs_at(0, 0) != term.attrs_at(14, 59)


def pane_sizes(term):
    found = re.search(r"pack (\d+)x(\d+).*grid (\d+)x(\d+)", term.display[1])
    return tuple(map(int, found.groups())) if found else None


@pytest.mark.tty
def test_the_layout_follows_a_resize(terminal, tmp_path):
    term = start(terminal, tmp_path, "layout", cols=60, rows=16)
    term.wait_for_text("60x16")
    left, high, right, _ = pane_sizes(term)
    assert (left, high, right) == (20, 14, 39)
    term.resize(80, 20)
    term.wait_for(
        lambda t: (
            t.display[19].startswith(" 80x20")
            and t.display[19].rstrip().endswith("relx=1")
            and len(t.display[19].rstrip()) == 79
            and pane_sizes(t) == (20, 18, 59, 18)
        ),
        message="the status bar's ends at the new edges, both panes taller, "
        "and the growth all to the last pane",
    )
    # The fields' column and the Text's row have weight, so the fields reach
    # one cell short of the window's edge and the Text down to the status bar.
    row, _ = term.find_text("To")
    assert len(term.display[row].rstrip()) == 79
    assert term.display[18].count("┘") == 2


@pytest.mark.tty
def test_the_layout_sash_moves_from_the_keyboard(terminal, tmp_path):
    term = start(terminal, tmp_path, "layout", cols=60, rows=16)
    term.wait_for_text("60x16")
    left, _, right, _ = pane_sizes(term)
    term.send_keys("<Tab>", "<Right>", "<Right>", "<Right>")
    term.wait_for(
        lambda t: (
            (sizes := pane_sizes(t)) is not None
            and (sizes[0], sizes[2]) == (left + 3, right - 3)
        ),
        message="the left pane three wider and the right three narrower",
    )


@pytest.mark.tty
def test_notes_are_written_and_saved_beside_the_program(terminal, tmp_path):
    term = start(terminal, tmp_path, "notes")
    term.wait_for_text("1 of 1 notes")
    term.send_keys("Shopping", "<Tab>", "milk and eggs", "<Control-n>")
    term.wait_for_text("2 of 2 notes")
    # The text first and the title last, so that the title is kept by its
    # own edit and not only because editing the text copies it too.
    term.send_keys("<Tab>", "a tutorial")
    term.send(b"\x1b[Z")  # Shift-Tab, back to the title
    term.send_keys("Ideas")
    term.wait_for(
        lambda t: t.contains("a tutorial") and t.contains("Ideas"),
        message="the second note in the editor and the list",
    )
    term.send_keys("<Control-q>")
    assert term.wait_for_exit() == 0
    saved = json.loads((tmp_path / "notes.json").read_text())
    assert saved == [
        {"title": "Shopping", "text": "milk and eggs"},
        {"title": "Ideas", "text": "a tutorial"},
    ]


@pytest.mark.tty
def test_notes_scrollbar_lights_the_part_under_the_mouse(terminal, tmp_path):
    """With hover reported, the scrollbar arrow under the pointer is drawn in
    the example's activebackground, and goes back when the pointer leaves."""
    term = terminal(cols=60, rows=16)
    hover = "import os\nos.environ['TKCURSES_MOUSE_REPORT_HOVER'] = '1'\n"
    term.run_source(hover + source("notes"), workdir=tmp_path)
    term.wait_for_text("1 of 1 notes")
    row, column = next(
        (r, line.index("\u25b2"))
        for r, line in enumerate(term.display)
        if "\u25b2" in line
    )
    # SGR code 35: motion with no button held, which send_mouse cannot spell.
    term.send(f"\x1b[<35;{column + 1};{row + 1}M".encode())
    term.wait_for_cell(row, column, lambda c: c.bg == "cyan", message="the lit arrow")
    term.send(f"\x1b[<35;{column - 10};{row + 1}M".encode())
    term.wait_for_cell(row, column, lambda c: c.bg != "cyan", message="the arrow unlit")
    term.send_keys("<Control-q>")
    assert term.wait_for_exit() == 0


@pytest.mark.tty
def test_table_scrollbar_arrow_held_down_keeps_scrolling(terminal, tmp_path):
    """The ttk Scrollbar repeats as ttk::Repeatedly does: one press, held,
    scrolls the table past more than the one row a click would."""
    term = start(terminal, tmp_path, "table", rows=8)
    term.wait_for_text("Mercury")
    row, column = next(
        (r, line.rindex("\u25bc"))
        for r, line in enumerate(term.display)
        if "\u25bc" in line
    )
    term.send_mouse(column, row, action="press")
    term.wait_for(
        lambda t: not t.contains("Venus") and not t.contains("Earth"),
        message="three rows scrolled away while the arrow is held",
    )
    term.send_mouse(column, row, action="release")


@pytest.mark.tty
def test_notes_search_narrows_the_list(terminal, tmp_path):
    store = tmp_path / "mine.json"
    store.write_text(
        json.dumps(
            [{"title": "Shopping", "text": "milk"}, {"title": "Ideas", "text": "eggs"}]
        )
    )
    term = start(terminal, tmp_path, "notes", str(store))
    term.wait_for_text("2 of 2 notes")
    term.send(b"\x1b[Z")  # Shift-Tab, from the list back to the search field
    term.send_keys("egg")
    term.wait_for(
        lambda t: (
            t.contains("1 of 2 notes")
            and t.contains("Ideas")
            and t.find_text("Shopping")[0] == 2
        ),
        message="only Ideas listed; Shopping is still the title being edited",
    )


@pytest.mark.tty
def test_notes_asks_before_deleting(terminal, tmp_path):
    store = tmp_path / "mine.json"
    store.write_text(
        json.dumps(
            [{"title": "Shopping", "text": "milk"}, {"title": "Ideas", "text": "eggs"}]
        )
    )
    term = start(terminal, tmp_path, "notes", str(store))
    term.wait_for_text("2 of 2 notes")
    row, column = term.find_text("Delete")
    term.click(column + 1, row)
    term.wait_for_text("Delete Shopping?")
    term.send_keys("<Return>")
    term.wait_for_text("Saved 1 notes")
    assert json.loads(store.read_text()) == [{"title": "Ideas", "text": "eggs"}]


@pytest.mark.tty
def test_the_recipe_scales_ticks_and_clears(terminal, tmp_path):
    """The Spinbox in the text rescales the quantities; a Checkbutton in the
    text ticks its line, and the button at the end clears it."""
    term = start(terminal, tmp_path, "recipe", cols=60, rows=24)
    term.wait_for(
        lambda t: t.contains("[ ] 300 g plain flour") and t.contains("Clear the ticks"),
        message="the card",
    )
    term.send_keys("<Up>")
    term.wait_for(
        lambda t: t.contains("Serves 5") and t.contains("[ ] 375 g plain flour"),
        message="five people's flour",
    )
    row, column = term.find_text("[ ] 375 g plain flour")
    term.click(column + 1, row)
    term.wait_for_text("[x] 375 g plain flour")
    row, column = term.find_text("Clear the ticks")
    term.click(column + 1, row)
    term.wait_for_text("[ ] 375 g plain flour")


def tk_photo_rows(path):
    """A PNG's rows of colours, read by this library as tkinter would."""
    import tkcurses

    root = tkcurses.Tk(useTk=False)
    try:
        return tkcurses.PhotoImage(master=root, file=str(path)).data()
    finally:
        root.destroy()


def test_the_wallpaper_tiles_centres_and_recolours(terminal, tmp_path):
    """Tiled, the pattern covers the desktop; untiled, one copy sits in the
    middle; Colours repaints it through the image, a pattern changes, and
    Save writes it as a PNG."""
    term = start(terminal, tmp_path, "wallpaper", str(tmp_path), cols=64, rows=18)
    term.wait_for_text("tiled")
    # Inside the desktop's border, at its top left: the first brick.
    row, column = 1, term.display[0].index("┌") + 1
    term.wait_for_cell(row, column, lambda cell: cell.data == "█", message="a brick")
    before = term.char_at(row, column).fg
    tile_row, tile_column = term.find_text("Tile")
    term.click(tile_column, tile_row)
    term.wait_for_text("centred")
    term.wait_for(
        lambda t: t.char_at(row, column).data == " " and "████████" in t.display[9],
        message="no tiles, and one copy in the middle",
    )
    row, column = term.find_text("Colours")
    term.click(column, row)
    term.wait_for(
        lambda t: any(
            t.char_at(9, c).data == "█" and t.char_at(9, c).fg != before
            for c in range(64)
        ),
        message="the copy in the next colours",
    )
    row, column = term.find_text("Checks")
    term.click(column, row)
    term.wait_for_text("Checks, 8x4")
    row, column = term.find_text("Save")
    term.click(column, row)
    term.wait_for_text("Saved checks.png")
    saved = tk_photo_rows(tmp_path / "checks.png")
    assert len(saved) == 4
    assert len(set(saved[0].split())) == 2


def test_the_mark_book_adds_up_the_cells_selected(terminal, tmp_path):
    """The arrows reach the last column, a click takes one mark, Shift-click
    the rectangle to another, and Row the whole row; the student's name is
    never counted."""
    term = start(terminal, tmp_path, "marks", cols=60, rows=16)
    term.wait_for_text("1 marks, total 72")
    # Right goes as far as Exam, the last column: Ada's 78. Tk 9.0.2 stops at
    # Lab, one short, which TkCurses does not copy.
    for mark in ("85", "90", "78", "78"):
        term.send_keys("<Right>")
        term.wait_for_text(f"1 marks, total {mark},")
    row, column = term.find_text("91")
    term.click(column, row)
    term.wait_for_text("1 marks, total 91,")
    corner = term.find_text("87")
    term.click(corner[1], corner[0], shift=True)
    # Grace's Exam to Edsger's Exam: 91, 84 and 87.
    term.wait_for_text("3 marks, total 262, mean 87.3")
    term.wait_for_cell(row, column, lambda cell: cell.reverse, message="91 reversed")
    row, column = term.find_text("Row")
    term.click(column, row)
    # The keyboard stayed on Grace: 88, 79, 95 and 91.
    term.wait_for_text("4 marks, total 353, mean 88.2")


@pytest.mark.tty
def test_the_scroller_moves_its_pad_with_the_keys(terminal, tmp_path):
    term = start(terminal, tmp_path, "scroller", cols=44, rows=12)
    term.wait_for(lambda t: t.row(1).startswith("line 001"), message="line 001")
    term.send_keys("<Down>", "<Down>")
    term.wait_for(lambda t: t.row(1).startswith("line 003"), message="line 003")
    term.send_keys("<End>")
    term.wait_for(
        lambda t: t.row(1).startswith("line 191") and t.row(10).startswith("line 200"),
        message="the last screenful",
    )
    term.send_keys("q")
    assert term.wait_for_exit(timeout=10) == 0
