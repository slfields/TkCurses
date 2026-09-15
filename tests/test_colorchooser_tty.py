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

"""The colour chooser against a real terminal.

A colour bar is a run of coloured blanks, so almost nothing here can be read
out of the characters on screen: the tests ask the emulator what colour each
cell was painted. The bars are found by looking for the coloured run on the
row a channel is named on, rather than by counting columns, so the assertions
survive the dialog being laid out a cell differently.
"""

from __future__ import annotations

import pytest

from tkcurses._core.colors import ColorDepth
from tkcurses.colorchooser import (
    BAR_LEVELS,
    BAR_WIDTH,
    CHANNEL_WIDTH,
    PANEL_HEIGHT,
    PANEL_WIDTH,
)

pytestmark = pytest.mark.tty

PROGRAM = """
import tkcurses
from tkcurses import colorchooser

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
buffer.write(0, 0, "ready")
root.tk.screen.refresh()


def ask(event):
    rgb, name = colorchooser.askcolor(parent=root, title=" Colour "{extra})
    buffer.write(1, 0, "picked=%s %s          " % (rgb, name))
    root.tk.screen.refresh()


root.bind("<Key-a>", ask)
root.after(8000, root.quit)
root.mainloop()
"""


def open_chooser(terminal, tmp_path, extra="", term_name="xterm-256color"):
    term = terminal(cols=60, rows=20, env={"TERM": term_name})
    term.run_source(PROGRAM.format(extra=extra), workdir=tmp_path)
    term.wait_for_text("ready")
    term.send(b"a")
    # "Red:" rather than "Selection:". Waiting on the longest label in the
    # dialog means a dialog that came up too narrow to show it fails as a
    # five-second timeout with no explanation, instead of as the assertion
    # that is actually interested in the width.
    term.wait_for_text("Red:")
    term.wait_for_idle()
    assert term.contains("Selection:"), (
        f"the dialog came up too narrow to show its own labels:\n{term.describe()}"
    )
    return term


def row_of(term, text):
    """The row a piece of text is on."""
    return next(i for i, line in enumerate(term.display) if text in line)


#: Which tier each of the terminals under test reports.
DEPTHS = {
    "xterm": ColorDepth.BASIC,
    "xterm-16color": ColorDepth.BRIGHT,
    "xterm-256color": ColorDepth.EXTENDED,
}


def geometry(term):
    """How many steps this terminal's bars have, and how wide each one is."""
    levels = BAR_LEVELS[DEPTHS[term._extra_env["TERM"]]]
    return len(levels), max(1, BAR_WIDTH // len(levels))


def bar(term, channel):
    """One channel's bar, as ``[(column, colour)]`` left to right.

    Found by position rather than by looking for colour. A step can be the
    same colour as the dialog behind it - black is the top of every bar -
    and is a step all the same, so a helper that hunted for coloured cells
    would quietly lose it and the count would look right when it was not.
    """
    row = row_of(term, f"{channel}:")
    label = f"{channel}:"
    start = term.display[row].index(label) + len(label) + CHANNEL_WIDTH
    count, cells = geometry(term)
    return [
        (column, term.attrs_at(row, column)["bg"])
        for column in range(start, start + count * cells)
    ]


def steps(term, channel):
    """The distinct colours one bar shows, in order, without repeats."""
    seen: list[str] = []
    for _, color in bar(term, channel):
        if not seen or seen[-1] != color:
            seen.append(color)
    return seen


def marker_column(term, channel):
    """Where the marker beneath one channel's bar is pointing."""
    return term.display[row_of(term, f"{channel}:") + 1].index("▲")


def selection_entry(term):
    """Where the Selection entry's text starts, as ``(row, column)``.

    Under its label, which is the column Tk puts it in.
    """
    row = row_of(term, "Selection:") + 1
    return row, term.display[row].index("#")


def panel_bands(term):
    """Every row of the result panel, as the colours of its cells.

    Found from the panel's own top-left corner rather than by counting rows
    down the dialog, so the assertions survive the layout moving.
    """
    top = row_of(term, "Selection:") + 2
    left = term.display[top].index("┌") + 1
    return [
        [
            term.attrs_at(top + 1 + band, left + cell)["bg"]
            for cell in range(PANEL_WIDTH)
        ]
        for band in range(PANEL_HEIGHT)
    ]


def retype_selection(term, text):
    """Clear the Selection entry and type something else into it."""
    row, column = selection_entry(term)
    term.click(column, row)
    term.wait_for_idle()
    term.send_keys("<End>")
    term.send(b"\x7f" * 12)
    term.send(text.encode())


# ---------------------------------------------------------------- the shape


def test_there_is_a_bar_for_each_channel(terminal, tmp_path):
    """Tk's shape: three colour bars, one per channel, each labelled."""
    term = open_chooser(terminal, tmp_path)
    for channel in ("Red", "Green", "Blue"):
        assert term.contains(f"{channel}:"), term.describe()
        assert len(bar(term, channel)) > 1, f"no bar for {channel}\n{term.describe()}"


def test_there_is_a_selection_entry_and_a_result_panel(terminal, tmp_path):
    """Tk's shape: the entry above a panel painted in the colour itself.

    A block rather than a line, because the point of it is to be big enough
    to judge a colour by - three numbers do not answer "what have I actually
    chosen" and a person can only settle that by looking at it.
    """
    term = open_chooser(terminal, tmp_path, extra=', color="#ff8000"')
    assert term.contains("Selection:")
    assert term.contains("#ff8000"), term.describe()
    bands = panel_bands(term)
    assert len(bands) == PANEL_HEIGHT
    for band in bands:
        assert band == ["ff8700"] * PANEL_WIDTH, term.describe()


def test_the_result_panel_follows_the_colour(terminal, tmp_path):
    term = open_chooser(terminal, tmp_path)
    assert panel_bands(term)[0] == ["black"] * PANEL_WIDTH, term.describe()
    retype_selection(term, "#ff8000\r")
    term.wait_for(
        lambda t: panel_bands(t)[0] == ["ff8700"] * PANEL_WIDTH,
        message="the panel to follow the colour",
    )


def test_there_is_no_colour_name_lookup(terminal, tmp_path):
    """Tk has none, and a list of names is not how anybody picks a colour out
    of a picker. The Selection entry still takes a name, as Tk's does."""
    term = open_chooser(terminal, tmp_path)
    screen = "\n".join(term.display).lower()
    assert "type a colour" not in screen
    assert "name" not in screen


def test_there_is_an_ok_and_a_cancel(terminal, tmp_path):
    term = open_chooser(terminal, tmp_path)
    assert term.contains("OK")
    assert term.contains("Cancel")


# ------------------------------------------------------------- the adapting


#: How many different colours each channel's bar really shows, measured on
#: each terminal. Two of these are not the step count: at sixteen colours the
#: blue bar shows two appearances for its three steps, because the palette's
#: blue is #0000ee and its bright blue is #5c5cff - so pure blue at any
#: intensity lands on the first and never reaches the second. Red and green
#: have no such gap. It is the palette's shape, not an error, and the entries
#: still reach every value.
SHOWN = {
    "xterm": {"Red": 2, "Green": 2, "Blue": 2},
    "xterm-16color": {"Red": 3, "Green": 3, "Blue": 2},
    "xterm-256color": {"Red": 6, "Green": 6, "Blue": 6},
}


@pytest.mark.parametrize("term_name", sorted(SHOWN))
def test_a_bar_has_as_many_steps_as_the_terminal_has_intensities(
    terminal, tmp_path, term_name
):
    """The reason the chooser had to wait for the colour tiers.

    Sixteen steps of red on an eight-colour terminal are two appearances and
    fourteen repeats. Each step here is an intensity the terminal has, so the
    count changes with the terminal: two at eight colours, three at sixteen,
    six at 256.
    """
    term = open_chooser(terminal, tmp_path, term_name=term_name)
    count, cells = geometry(term)
    for channel, expected in SHOWN[term_name].items():
        assert len(bar(term, channel)) == count * cells, term.describe()
        assert len(steps(term, channel)) == expected, (
            f"{channel} on {term_name}\n{term.describe()}"
        )


def test_every_step_of_a_bar_looks_different_from_its_neighbours(terminal, tmp_path):
    """Which is the point of choosing the count from the depth. A bar with a
    repeat in it offers a choice that is not a choice."""
    term = open_chooser(terminal, tmp_path)
    count, _ = geometry(term)
    for channel in ("Red", "Green", "Blue"):
        colors = steps(term, channel)
        assert len(set(colors)) == count, (
            f"{channel} repeats a colour\n{term.describe()}"
        )


def test_each_bar_is_its_own_channel_from_nothing_to_full(terminal, tmp_path):
    """Whatever the other two are doing."""
    term = open_chooser(terminal, tmp_path, extra=', color="#ff8000"')
    assert steps(term, "Blue")[0] == "black"
    assert steps(term, "Blue")[-1] == "0000ff"
    assert steps(term, "Red")[-1] == "brightred"
    assert steps(term, "Green")[-1] == "brightgreen"


def test_a_bar_does_not_change_when_another_channel_moves(terminal, tmp_path):
    """A deliberate departure from Tk, and the reason is the terminal.

    Tk repaints the other two strips with the channel you moved - measured
    against Tk 9.0.2. On an X display that is a live preview of millions of
    colours. Here a bar has between two and six steps, and with the other
    channels at mid intensity the whole of it collapses to one colour at
    eight and sixteen, so the scale stops being a scale. The panel shows the
    colour being built instead.
    """
    term = open_chooser(terminal, tmp_path)
    before = {channel: steps(term, channel) for channel in ("Red", "Green", "Blue")}
    retype_selection(term, "#808080\r")
    term.wait_for(
        lambda t: panel_bands(t)[0] == ["808080"] * PANEL_WIDTH,
        message="the colour to move to mid grey",
    )
    after = {channel: steps(term, channel) for channel in ("Red", "Green", "Blue")}
    assert after == before, term.describe()


# ------------------------------------------------------------- the bars


def test_clicking_a_bar_sets_that_channel(terminal, tmp_path):
    term = open_chooser(terminal, tmp_path)
    column, _ = bar(term, "Red")[-1]
    term.click(column, row_of(term, "Red:"))
    term.wait_for_text("#ff0000")


def test_clicking_moves_the_marker_to_that_step(terminal, tmp_path):
    term = open_chooser(terminal, tmp_path)
    cells = bar(term, "Red")
    before = marker_column(term, "Red")
    term.click(cells[-1][0], row_of(term, "Red:"))
    term.wait_for(
        lambda t: marker_column(t, "Red") != before, message="the marker to move"
    )
    assert marker_column(term, "Red") > before


def test_dragging_along_a_bar_follows_the_pointer(terminal, tmp_path):
    """Tk's bars are draggable, and so are these - the press holds the
    implicit grab, so a drag arrives at the step it started on with
    coordinates that say where the pointer really is."""
    term = open_chooser(terminal, tmp_path)
    row = row_of(term, "Red:")
    cells = bar(term, "Red")
    term.send_mouse(cells[0][0], row, action="press")
    term._drain(0.05)
    seen = []
    for column, _ in cells[1:]:
        term.send_mouse(column, row, action="move")
        term._drain(0.04)
        seen.append(marker_column(term, "Red"))
    term.send_mouse(cells[-1][0], row, action="release")
    assert seen == sorted(seen), f"the marker went backwards: {seen}"
    assert seen[-1] > seen[0], term.describe()
    term.wait_for_text("#ff0000")


# ----------------------------------------------------------- the entries


def retype(term, row, column, text):
    """Clear an entry by clicking into it and type something else."""
    term.click(column, row)
    term.wait_for_idle()
    term.send_keys("<End>")
    term.send(b"\x7f" * 5)
    term.send(text.encode())
    term.send(b"\r")


def test_typing_a_channel_value_moves_its_bar(terminal, tmp_path):
    term = open_chooser(terminal, tmp_path)
    row = row_of(term, "Red:")
    column = term.display[row].index("Red:") + len("Red:")
    before = marker_column(term, "Red")
    retype(term, row, column, "255")
    term.wait_for_text("#ff0000")
    assert marker_column(term, "Red") > before, term.describe()


def test_a_channel_value_out_of_range_is_clamped(terminal, tmp_path):
    """Tk clamps rather than refusing, so a typo cannot wedge the dialog."""
    term = open_chooser(terminal, tmp_path)
    row = row_of(term, "Red:")
    column = term.display[row].index("Red:") + len("Red:")
    retype(term, row, column, "999")
    term.wait_for_text("#ff0000")


def test_a_channel_value_that_is_not_a_number_becomes_zero(terminal, tmp_path):
    """Tk's own rule, from HandleRGBEntry."""
    term = open_chooser(terminal, tmp_path, extra=', color="#ff8000"')
    row = row_of(term, "Red:")
    column = term.display[row].index("Red:") + len("Red:")
    retype(term, row, column, "nonsense")
    term.wait_for_text("#008000")


def test_typing_a_colour_into_the_selection_entry_sets_all_three(terminal, tmp_path):
    term = open_chooser(terminal, tmp_path)
    retype_selection(term, "#ff8000\r")
    term.wait_for(
        lambda t: panel_bands(t)[0] == ["ff8700"] * PANEL_WIDTH,
        message="the colour to be taken",
    )
    # All three markers moved, which is what "sets all three" means.
    assert marker_column(term, "Red") > marker_column(term, "Blue"), term.describe()
    assert marker_column(term, "Green") > marker_column(term, "Blue"), term.describe()


def test_the_selection_entry_takes_a_name_as_tk_does(terminal, tmp_path):
    """Tk hands whatever is typed to winfo_rgb, and so does this. What
    neither has is a list of names to choose from."""
    term = open_chooser(terminal, tmp_path)
    retype_selection(term, "red\r")
    term.wait_for_text("#cd0000")


def test_a_selection_that_is_not_a_colour_is_put_back(terminal, tmp_path):
    """And must not take the application down: winfo_rgb raises ValueError
    for an unknown name, which a dialog has to catch rather than let out."""
    term = open_chooser(terminal, tmp_path, extra=', color="#ff8000"')
    retype_selection(term, "nosuchcolour\r")
    term.wait_for_idle()
    assert term.contains("#ff8000"), term.describe()
    assert "Traceback" not in term.stderr


# ------------------------------------------------------------- the answer


def test_ok_answers_with_the_colour_shown(terminal, tmp_path):
    term = open_chooser(terminal, tmp_path, extra=', color="#ff8000"')
    row = row_of(term, "OK")
    term.click(term.display[row].index("OK"), row)
    term.wait_for_text("picked=(255, 128, 0) #ff8000")


def test_ok_takes_what_was_typed_and_not_yet_applied(terminal, tmp_path):
    """Tk answers with the last colour committed, so typing a colour and
    pressing OK gets the one before it - which reads as the dialog ignoring
    what was typed. This applies it first."""
    term = open_chooser(terminal, tmp_path)
    retype_selection(term, "#ff8000")
    button = row_of(term, "OK")
    term.click(term.display[button].index("OK"), button)
    term.wait_for_text("picked=(255, 128, 0) #ff8000")


def test_cancelling_answers_with_a_pair_of_nones(terminal, tmp_path):
    term = open_chooser(terminal, tmp_path)
    term.send_keys("<Escape>")
    term.wait_for_text("picked=None None")


def test_the_cancel_button_answers_with_a_pair_of_nones(terminal, tmp_path):
    term = open_chooser(terminal, tmp_path)
    row = row_of(term, "Cancel")
    term.click(term.display[row].index("Cancel"), row)
    term.wait_for_text("picked=None None")


def test_an_initial_colour_is_there_to_start_with(terminal, tmp_path):
    term = open_chooser(terminal, tmp_path, extra=', color="green"')
    assert term.contains("#00cd00"), term.describe()
    row = row_of(term, "OK")
    term.click(term.display[row].index("OK"), row)
    term.wait_for_text("picked=(0, 205, 0) #00cd00")


def test_an_initial_colour_is_reported_as_the_terminal_will_draw_it(terminal, tmp_path):
    """`green` is #00ff00 in X11 and #00cd00 here, and here is what the
    swatch beside it is about to be."""
    term = open_chooser(terminal, tmp_path, extra=', color="green"')
    assert term.contains("#00cd00")
    assert not term.contains("#00ff00")
