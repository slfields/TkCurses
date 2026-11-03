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

"""Smoke tests for the acceptance scenarios.

The scenarios exist to be run by a person; these tests only check that each
one still starts, renders, and leaves cleanly. Without them a scenario would
quietly rot the first time an API moved, and nobody would find out until they
sat down to accept a release.
"""

from __future__ import annotations

import collections
import contextlib
import io
import os
import re
import sys

import pytest
from uat.__main__ import scenarios, show

from tests.conftest import PROJECT_ROOT

pytestmark = pytest.mark.tty

ESCAPE = b"\x1b"


@pytest.fixture
def uat_terminal(terminal):
    """A harness whose child process can import the uat package.

    uat/ sits at the repository root and is deliberately outside the
    installed distribution - it is a development tool, not library code - so a
    child can import it only if the root is on its path. Inheriting that from
    whichever directory pytest happened to be started in would make these
    tests pass or fail depending on where the command was typed, so the path
    is passed explicitly.
    """

    def _make(**kwargs):
        env = dict(kwargs.pop("env", {}))
        inherited = os.environ.get("PYTHONPATH", "")
        env.setdefault(
            "PYTHONPATH",
            os.pathsep.join(part for part in (str(PROJECT_ROOT), inherited) if part),
        )
        return terminal(env=env, **kwargs)

    return _make


@pytest.mark.parametrize("scenario", scenarios())
def test_a_scenario_starts_renders_and_exits_cleanly(uat_terminal, scenario):
    term = uat_terminal(cols=60, rows=20)
    term.run([sys.executable, "-m", f"uat.{scenario}"])
    # Every scenario puts its title on the first line before waiting.
    term.wait_for(lambda t: t.row(0).strip() != "", message="the title line")
    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0
    assert "Traceback" not in term.stderr


def _listing_text() -> str:
    """The whole listing, produced in this process.

    The yardstick for both of the tests below: how many rows it needs, and
    how many bytes a child that finished writing it would have written.
    Both were formulas once and both drifted.
    """
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        show()
    return printed.getvalue()


def _listing_rows() -> int:
    """Rows the whole listing needs, counted by running it.

    Not a formula. It used to be ``2 * len(scenarios()) + 14``, which today
    gives exactly the right answer and no more: the footer has grown since
    that number was chosen, and one further line in it would have the top of
    the listing scroll off, failing as a missing scenario rather than as a
    terminal one row too short. Asking the listing how long it is cannot
    drift.
    """
    return _listing_text().count("\n") + 2


def test_the_runner_lists_every_scenario(uat_terminal):
    """Every scenario reachable from the runner's own listing.

    This failed on CI for days, on Python 3.13, with the listing truncated at
    a point that moved between runs, the footer absent and the child exiting
    0 - and never reproduced locally. It was TkCurses-9q7, and the fault was
    in the harness: _drain(0) checked its deadline before reading anything, so
    the drain that was supposed to collect what the child wrote between the
    last poll and its exit collected nothing. The tail was what got lost.

    The reporting below is kept because it is what finally made the failure
    legible, and it costs nothing when the test passes. The FOOTER is the
    sharper half: show() prints the scenarios and then the "What to look for"
    block, so the footer is the last thing written, and whether it arrived
    separates output lost in the MIDDLE from output lost off the END - which
    is what pointed at the reap.

    term.describe() rather than the raw display, because the display is long
    enough that pytest elides its middle, and I misread that elision as blank
    rows once already.
    """
    rows = _listing_rows()
    term = uat_terminal(cols=80, rows=rows)
    term.run([sys.executable, "-m", "uat"])
    assert term.wait_for_exit(timeout=10) == 0
    shown = "\n".join(term.display)
    missing = [scenario for scenario in scenarios() if scenario not in shown]
    footer = "docs/UAT_IMAGES.md"
    state = (
        "PRESENT - output was lost from the middle"
        if footer in shown
        else "ABSENT - the end of the output never arrived"
    )
    assert not missing, (
        f"{len(missing)} of {len(scenarios())} scenarios are not on the "
        f"listing, asked for {rows} rows.\n"
        f"FOOTER {state}\n"
        f"RECEIVED {len(bytes(term._received))} bytes, "
        f"of {len(_listing_text().encode())} the whole listing is\n"
        f"missing: {missing}\n{term.describe()}"
    )


def test_the_runner_refuses_a_scenario_that_does_not_exist(uat_terminal):
    term = uat_terminal(cols=80, rows=30)
    term.run([sys.executable, "-m", "uat", "99"])
    assert term.wait_for_exit(timeout=10) == 2


def test_a_scenario_reports_failure_through_its_exit_code(uat_terminal, tmp_path):
    """The contract that lets these be pointed at CI later."""
    term = uat_terminal(cols=60, rows=20)
    term.run_source(
        """
from uat import _support

def build(root, screen):
    raise RuntimeError("scenario is broken")

raise SystemExit(_support.run("broken", build))
""",
        workdir=tmp_path,
    )
    assert term.wait_for_exit(timeout=10) == 1
    assert "scenario is broken" in term.stderr


# The documented run-from-anywhere form. Given a path rather than -m, Python
# puts the uat directory itself on sys.path and never the repository root, so
# these would fail without the bootstrap in __main__.py - whatever the working
# directory. PYTHONSAFEPATH stops Python adding any path of its own, which
# rules out passing by luck.


def test_the_runner_works_when_given_its_path(terminal):
    term = terminal(cols=80, rows=_listing_rows(), env={"PYTHONSAFEPATH": "1"})
    term.run([sys.executable, str(PROJECT_ROOT / "uat")])
    assert term.wait_for_exit(timeout=10) == 0
    assert "Acceptance scenarios" in "\n".join(term.display)


def test_a_scenario_runs_when_the_runner_is_given_its_path(terminal):
    term = terminal(cols=60, rows=20, env={"PYTHONSAFEPATH": "1"})
    term.run([sys.executable, str(PROJECT_ROOT / "uat"), "2"])
    term.wait_for(lambda t: t.row(0).strip() != "", message="the title line")
    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0
    assert "Traceback" not in term.stderr


def test_scenario_38_actually_undoes_searches_and_reports_a_cell(uat_terminal):
    """The smoke test above only proves a scenario starts and stops.

    A scenario whose keys had quietly stopped working would still pass it,
    which is how a UAT rots: the checklist says press Ctrl-Z, the person
    presses it, nothing happens, and they report a bug in the widget. This
    drives the three things the checklist asks about, so that a break is a
    failed test rather than a wasted acceptance run.
    """
    term = uat_terminal(cols=100, rows=24)
    term.run([sys.executable, "-m", "uat.scenario_38_text_editing"])
    term.wait_for_text("insert 1.0")

    term.send(b"hello world")
    term.wait_for_text("insert 1.11")

    term.send(b"\x1a")  # Ctrl-Z
    term.wait_for_text("insert 1.0")  # the whole run, not one letter
    term.send(b"\x19")  # Ctrl-Y
    term.wait_for_text("insert 1.11")

    term.send(b"\x12")  # Ctrl-R loads the paragraph
    term.wait_for_text("noticed")

    term.send(b"\x06")  # Ctrl-F to the Find box
    term.send(b"dog\r")
    term.wait_for_text("in the text altogether")

    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0
    assert "Traceback" not in term.stderr


def test_scenario_38_shows_what_autoseparators_does(uat_terminal):
    """The option was set once and never exercised, which a person caught.

    A scenario that configures something and never lets you see it do
    anything is not acceptance for it. The group count is what makes
    grouping visible, so this drives the toggle and watches the count stop
    rising - the same thing the checklist asks a person to watch.
    """
    term = uat_terminal(cols=100, rows=24)
    term.run([sys.executable, "-m", "uat.scenario_38_text_editing"])
    term.wait_for_text("undo groups=0")

    term.send(b"ab")
    term.send_keys("<Left>")
    term.send(b"cd")
    term.wait_for_text("undo groups=2")

    term.send(b"\x14")  # Ctrl-T turns autoseparators off
    term.wait_for_text("autosep=OFF")
    term.send(b"ef")
    term.send_keys("<Left>")
    term.send(b"gh")
    # Nothing to wait for - the assertion is that the count does NOT move -
    # so give the same gestures the time the ones above took to land.
    term.send_keys("<Left>")
    term.wait_for_text("insert 1.3")
    assert any("undo groups=2" in row for row in term.display), (
        "with autoseparators off the count should have stopped rising"
    )

    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0


def test_scenario_38_types_a_tab_rather_than_leaving_the_editor(uat_terminal):
    """Tab belongs to the editor here, as it does in tkinter.

    TkCurses puts focus traversal on the ``all`` tag, so by default Tab
    moves the focus out of a Text - a sensible default for a terminal,
    where Control-Tab cannot be relied on, and the wrong one for something
    pretending to be an editor. The scenario takes Tab back; this makes
    sure it kept it, because the whole point is that the scenario should
    not disagree with tkinter about what Tab does.
    """
    term = uat_terminal(cols=100, rows=24)
    term.run([sys.executable, "-m", "uat.scenario_38_text_editing"])
    term.wait_for_text("insert 1.0")

    term.send(b"ab")
    term.wait_for_text("insert 1.2")
    term.send(b"\t")
    term.wait_for_text("insert 1.3")  # the tab went INTO the text
    term.send(b"cd")
    term.wait_for_text("insert 1.5")

    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0


def test_scenario_38_keeps_the_undo_count_on_screen_at_80_columns(uat_terminal):
    """The figure the checklist asks a person to watch must not fall off.

    On one line the status ran to 98 of 100 columns with the paragraph
    loaded and "undo groups" lost its number off the right edge - and 80
    columns is the common terminal, where far more went. Split across two
    lines now. Checked at 80 rather than 100 because that is the width that
    actually hurt.
    """
    term = uat_terminal(cols=80, rows=24)
    term.run([sys.executable, "-m", "uat.scenario_38_text_editing"])
    term.wait_for_text("insert 1.0")
    term.send(b"\x12")  # Ctrl-R: the paragraph, which is what made it long
    term.wait_for_text("noticed")
    term.send(b"\x06")
    term.send(b"dog\r")  # and move the cursor deep into a line
    term.wait_for_text("altogether")
    term.wait_for_idle()

    line = next(row for row in term.display if "undo groups=" in row)
    count = line.split("undo groups=")[1].split()
    assert count and count[0].isdigit(), (
        f"the undo count was cut off: {line.rstrip()!r}"
    )
    for row in term.display:
        assert len(row.rstrip()) <= 80, f"row ran past 80 columns: {row!r}"

    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0


def test_scenario_38_does_not_paint_over_the_find_box(uat_terminal):
    """It did, and a person spotted it before any test could.

    The status line was placed on the Entry's bottom border. An Entry is
    three rows tall - border, text, border - and the layout was written as
    though it were two. Asserted here because the fix is a row number, and
    a row number is exactly the sort of thing a later edit moves back.
    """
    term = uat_terminal(cols=100, rows=24)
    term.run([sys.executable, "-m", "uat.scenario_38_text_editing"])
    term.wait_for_text("Find:")
    term.wait_for_text("undo groups=0")

    rows = term.display
    # The Find box, not the scenario's own outer frame: both have a bottom
    # border, and taking the last one found the frame and passed whatever
    # the layout did. Anchoring on the "Find:" label is what makes this
    # test about the box it is named after - written that way after the
    # first version passed with the fault put back.
    label = next(n for n, row in enumerate(rows) if "Find:" in row)
    bottom = label + 1
    assert "\u2514" in rows[bottom], (
        f"expected the Find box's bottom border on row {bottom}, got {rows[bottom]!r}"
    )
    assert "insert" not in rows[bottom], (
        f"the status line is sitting on the Find box border, row {bottom}"
    )


def test_scenario_39_shows_tab_stops_lining_up(uat_terminal):
    """The columns must land where the ruler says, or the scenario teaches
    the wrong thing.

    Driven rather than eyeballed because the ruler is the scenario's whole
    affordance: if it and the text disagree, every reading a person takes
    off it is wrong, and the checklist would be worse than nothing.
    """
    term = uat_terminal(cols=100, rows=24)
    term.run([sys.executable, "-m", "uat.scenario_39_tabs_and_indentation"])
    term.wait_for_text("insert 1.0")
    term.send(b"\x12")  # Ctrl-R
    term.wait_for_text("Widget")
    term.wait_for_idle()

    row = next(line for line in term.display if "Qty" in line)
    body = row.strip("│ ")
    assert body.index("Qty") == 8, f"default stops put Qty at 8: {body!r}"
    assert body.index("Price") == 16, body

    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0
    assert "Traceback" not in term.stderr


def test_scenario_39_indent_keys_do_not_raise(uat_terminal):
    """All four of them, because one did.

    tag_configure(..., lmargin1=0, **options) is a duplicate keyword the
    moment options names lmargin1, and the block-indent key did exactly
    that: the screen went blank on Ctrl-G. A scenario whose keys raise is
    worse than a missing scenario, because it reads as a bug in the widget.
    """
    term = uat_terminal(cols=100, rows=24)
    term.run([sys.executable, "-m", "uat.scenario_39_tabs_and_indentation"])
    term.wait_for_text("insert 1.0")
    term.send(b"\x12")
    term.wait_for_text("Widget")

    for key, expected in (
        (b"\x02", "block indent"),
        (b"\x07", "hanging indent"),
        (b"\x05", "right margin"),
        (b"\x0e", "no margins"),
    ):
        term.send(key)
        term.wait_for_text(expected)

    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0
    assert "Traceback" not in term.stderr


def test_scenario_39_a_hanging_indent_reshapes_the_paragraph(uat_terminal):
    """The claim the whole cycle rests on, driven end to end.

    An indent NARROWS the rows it indents, so the paragraph breaks sooner.
    A version that only shifted the text would leave the wrapped rows
    ending where they did, and this is what notices.
    """
    term = uat_terminal(cols=100, rows=24)
    term.run([sys.executable, "-m", "uat.scenario_39_tabs_and_indentation"])
    term.wait_for_text("insert 1.0")
    term.send(b"\x12")
    term.wait_for_text("Widget")
    term.wait_for_idle()

    def paragraph_rows():
        """The rows inside the border, with their LEADING SPACES kept.

        Stripping spaces here would remove the indent this test is about -
        which it did on the first attempt, and the failure read as the
        widget not indenting at all.
        """
        wanted = ("paragraph is here", "only way", "merely moving", "sideways across")
        out = []
        for line in term.display:
            if any(key in line for key in wanted):
                out.append(line.split("│")[1] if "│" in line else line)
        return out

    plain = paragraph_rows()
    assert plain, "the paragraph should be on screen"
    first_plain = len(plain[0].rstrip())

    term.send(b"\x07")  # Ctrl-G, hanging indent
    term.wait_for_text("hanging indent")
    term.wait_for_idle()
    hung = paragraph_rows()
    assert hung, "the paragraph should still be on screen"

    assert len(hung[0].rstrip()) == first_plain, "the FIRST row keeps its full width"
    assert hung[1].startswith(" "), "and the wrapped rows are indented"
    assert len(hung[1].rstrip()) < first_plain, (
        f"the indented rows must be NARROWER, not merely moved: {hung[1].rstrip()!r}"
    )

    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0


def test_scenario_39_indenting_the_paragraph_leaves_the_table_alone(uat_terminal):
    """Tab stops are measured from the widget, not from where a line starts.

    So a tabbed table keeps its columns when something else on screen is
    indented. This is the rule that would have been got wrong by the natural
    implementation, and the checklist asks a person to confirm it.
    """
    term = uat_terminal(cols=100, rows=24)
    term.run([sys.executable, "-m", "uat.scenario_39_tabs_and_indentation"])
    term.wait_for_text("insert 1.0")
    term.send(b"\x12")
    term.wait_for_text("Widget")
    term.wait_for_idle()
    before = next(line for line in term.display if "Qty" in line)

    term.send(b"\x02")  # Ctrl-B, block indent on the paragraph
    term.wait_for_text("block indent")
    term.wait_for_idle()
    after = next(line for line in term.display if "Qty" in line)
    assert after == before, "indenting the paragraph moved the table"

    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0


def test_scenario_39_first_line_and_hanging_indents_are_opposites(uat_terminal):
    """The primary use, and the one it is most easily confused with.

    A first-line indent is lmargin1 alone: the paragraph's first line moves
    in and the rest stay flush, the way a paragraph is set in a book. A
    hanging indent is lmargin2 alone and does the opposite. They are the
    same two options with their values swapped, so a version that mixed
    them up would look plausible under either key on its own - which is why
    both are driven here and compared against each other.
    """
    term = uat_terminal(cols=100, rows=24)
    term.run([sys.executable, "-m", "uat.scenario_39_tabs_and_indentation"])
    term.wait_for_text("insert 1.0")
    term.send(b"\x12")
    term.wait_for_text("Widget")
    term.wait_for_idle()

    def rows():
        """Paragraph rows with leading spaces kept - they are the indent."""
        out = []
        for line in term.display:
            if "│" not in line:
                continue
            out.append(line.split("│")[1])
        # Past the table's four rows: the paragraph is what follows.
        return [row for row in out if row.strip()][4:]

    term.send(b"\x10")  # Ctrl-P, first-line
    term.wait_for_text("FIRST-LINE")
    term.wait_for_idle()
    first = rows()
    assert first[0].startswith("      "), f"first line should be indented: {first[0]!r}"
    assert not first[1].startswith(" "), f"the rest should be flush: {first[1]!r}"

    term.send(b"\x0e")  # Ctrl-N
    term.wait_for_text("no margins")
    term.send(b"\x07")  # Ctrl-G, hanging
    term.wait_for_text("hanging indent")
    term.wait_for_idle()
    hung = rows()
    assert not hung[0].startswith(" "), f"first line should be flush: {hung[0]!r}"
    assert hung[1].startswith("      "), f"the rest should be indented: {hung[1]!r}"

    assert first[0] != hung[0], "the two indents must not look the same"

    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0


# ------------------------------------------------- scenario 40, the themed core
#
# These drive GESTURES, which is the whole reason the scenario exists. A themed
# widget that draws correctly and answers nothing passes every other kind of
# test here: ttk.Panedwindow shipped from TkCurses-3h5.2 with its sash bindings
# registered under the classic widget's name, so the sash drew perfectly and
# could not be moved, and 4365 tests were green.


def _scenario_40(uat_terminal):
    """The scenario, up and settled, with the response line on screen."""
    term = uat_terminal(cols=100, rows=30)
    term.run([sys.executable, "-m", "uat.scenario_40_ttk_core_widgets"])
    term.wait_for_text("nothing yet")
    term.wait_for_idle()
    return term


def _responded(term):
    return next((row.strip() for row in term.display if "responded" in row), "")


def _click(term, x, y):
    """Press and release, with a drain between.

    The drain is not politeness. Sent back to back both escape sequences land
    in one read and ncurses holds the release until something else arrives -
    a property of this harness rather than of any real mouse, recorded in
    tests/test_button_tty.py. Omitting it made a working scenario look like
    one where nothing answered a click.
    """
    term.send_mouse(x, y, action="press")
    term._drain(0.08)
    term.send_mouse(x + 1, y, action="release")


def test_scenario_40_a_themed_button_answers_a_click(uat_terminal):
    """The gesture arrives, which no option-surface test can show."""
    term = _scenario_40(uat_terminal)
    _click(term, 8, 3)
    term.wait_for(
        lambda t: "ttk.Button" in _responded(t),
        message="the themed button to report a click",
    )

    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0
    assert "Traceback" not in term.stderr


def test_scenario_40_a_themed_button_answers_tab_and_space(uat_terminal):
    """Focus traversal reaches it too, not only the mouse."""
    term = _scenario_40(uat_terminal)
    term.send(b"\t")
    term._drain(0.08)
    term.send(b" ")
    term.wait_for(
        lambda t: "ttk.Button" in _responded(t),
        message="the themed button to report Tab then space",
    )

    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0


def test_scenario_40_the_paned_sash_can_be_dragged(uat_terminal):
    """The bug this scenario was written too late to prevent.

    ttk.Panedwindow bound sash press, motion, release and keys under
    "PanedWindow" while reporting TPanedwindow, so it received none of them.
    Asserted by where the sash ENDS UP rather than by the report line alone:
    a handler that fires and moves nothing would satisfy the report.
    """
    term = _scenario_40(uat_terminal)

    def sash_columns():
        return [
            x
            for y, row in enumerate(term.display)
            for x, cell in enumerate(row)
            if cell == "┃" and x > 45
        ]

    before = sash_columns()
    assert before, f"no sash on screen to drag\n{term.describe()}"
    column = before[0]
    row = next(
        y
        for y, line in enumerate(term.display)
        if len(line) > column and line[column] == "┃"
    )

    term.send_mouse(column, row, action="press")
    term._drain(0.08)
    term.send_mouse(column - 3, row, action="move", button=1)
    term._drain(0.08)
    term.send_mouse(column - 3, row, action="release")

    term.wait_for(
        lambda t: bool(sash_columns()) and sash_columns()[0] < column,
        message="the sash to move left",
    )

    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0
    assert "Traceback" not in term.stderr


#: Glyphs a border is drawn from, in any theme the library ships.
_BORDERS = set("─│┌┐└┘═║╔╗╚╝-|+╒╕╘╛┃.'`")


def _border_glyphs(term):
    return {cell for row in term.display[:20] for cell in row if cell in _BORDERS}


def test_scenario_40_the_theme_and_restyle_keys_are_live(uat_terminal):
    """The keys themselves work - what they reach is the test below."""
    term = _scenario_40(uat_terminal)
    term.send(b"\x14")  # Ctrl-T
    term.wait_for_text("theme ascii")
    term.send(b"\x12")  # Ctrl-R
    term.wait_for_text("restyled")

    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0
    assert "Traceback" not in term.stderr


def test_scenario_40_a_theme_change_redraws_the_themed_widgets(uat_terminal):
    """Changing the theme changes how the themed widgets LOOK.

    TkCurses-5vu, reported by the author running this scenario: Ctrl-T cycled
    the theme and nothing on screen moved. Nine widgets - Frame, Labelframe,
    Button, Checkbutton, Radiobutton, Menubutton, Entry, Spinbox and Scrollbar -
    inherited the classic widget's drawing entirely, so a theme reached none of
    them. They now take their box from the theme's glyph set.

    **The test this replaces asserted that the theme LABEL changed**, which is
    the scenario's own Label and says nothing about any themed widget. It passed
    throughout, which is how the gap reached a person instead of being caught
    here, and it is why this one reads the drawn characters.
    """
    term = _scenario_40(uat_terminal)
    before = _border_glyphs(term)
    term.send(b"\x14")  # Ctrl-T, to ascii
    term.wait_for_text("theme ascii")
    term.wait_for_idle()

    assert _border_glyphs(term) != before, (
        "the theme changed and not one border glyph did, so nothing on screen "
        f"is drawn from the theme: {sorted(before)}\n{term.describe()}"
    )


def _horizontal_runs(term, row, glyph):
    """A column from each run of ``glyph`` along ``row``, left to right.

    Used to find the themed box and the classic one beside it without naming
    their columns, which move whenever the scenario is rearranged.
    """
    line = term.display[row]
    columns, inside = [], False
    for column, cell in enumerate(line):
        if cell == glyph and not inside:
            columns.append(column)
            inside = True
        elif cell != glyph:
            inside = False
    return columns


def test_scenario_40_a_restyle_reaches_the_themed_column_only(uat_terminal):
    """``Style.configure`` recolours the themed widgets and not the classic ones.

    The second half of what UAT 40 asks, and the second thing a person found
    that no test had: Ctrl-R reported "restyled" and not one cell on screen
    changed colour. Every themed widget built on an ordinary one painted through
    the classic _background_attribute, which reads the widget's own options and
    never the style database.

    Both directions are asserted, because each failure means something
    different. The themed border not changing means the style database is not
    reaching the widget at all; the classic border changing too would mean the
    style is not scoped to the themed classes, and a program using both would
    find its plain widgets repainted under it.
    """
    term = _scenario_40(uat_terminal)

    def colours_at(row, column):
        cell = term.char_at(row, column)
        return (cell.fg, cell.bg)

    # Found rather than hardcoded. The first version named columns 3 and 31,
    # and then the scenario's classic column moved to make room for a list -
    # so the test compared a border against an empty cell and failed in the
    # gate. A test that knows the layout by heart breaks every time the layout
    # is improved.
    row = 2
    runs = _horizontal_runs(term, row, "─")
    assert len(runs) >= 2, (
        f"expected at least two bordered boxes on row {row}, found {len(runs)}"
        f"\n{term.describe()}"
    )
    themed, classic = (row, runs[0]), (row, runs[1])
    was_themed = colours_at(*themed)
    was_classic = colours_at(*classic)

    term.send(b"\x12")  # Ctrl-R
    term.wait_for_text("restyled")
    term.wait_for(
        lambda t: colours_at(*themed) != was_themed,
        message="the themed border to take the restyled colours",
    )
    assert colours_at(*classic) == was_classic, (
        "the classic widget was recoloured too, so the style is not scoped to "
        f"the themed classes: {colours_at(*classic)}\n{term.describe()}"
    )

    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0
    assert "Traceback" not in term.stderr


# --------------------------------------------------------------- scenario 41
#
# A smoke test checks that the title appears. It did so throughout, while this
# scenario had two visible faults: five bordered entries placed two rows apart
# so each one's bottom border was painted over, and a mode readout drawn from
# inside the validation callback - therefore showing the mode as it was a
# moment BEFORE the machinery changed it, which hid the one case the readout
# exists to show. Both were found by driving the scenario in a pty by hand.
# These tests are that hand-driving, kept. TkCurses-wkd.


def _scenario_41(uat_terminal):
    """The scenario, up and settled, with its mode readout on screen."""
    term = uat_terminal(cols=90, rows=28)
    term.run([sys.executable, "-m", "uat.scenario_41_entry_validation"])
    term.wait_for_text("forced (variable)")
    term.wait_for_text("modes")
    term.wait_for_idle()
    return term


def _modes(term):
    """The mode readout, both lines, as one string."""
    return " ".join(
        row.strip() for row in term.display if "digits=" in row or "broken=" in row
    )


def _last(term):
    return next((row.strip() for row in term.display if row.startswith(" last:")), "")


def test_scenario_41_a_refused_keystroke_does_not_reach_the_field(uat_terminal):
    """The edit condition, seen rather than asserted."""
    term = _scenario_41(uat_terminal)
    term.click(22, 5)
    term.send_keys("x")
    term.wait_for_text("REFUSED 'x'")
    # The field and the report are different cells, so wait for both.
    term.wait_for_cell(5, 22, lambda cell: cell.data.strip() == "")
    assert "REFUSED 'x'" in _last(term), term.describe()
    assert term.row(5)[22:38].strip() == "", (
        f"the refused keystroke reached the field\n{term.describe()}"
    )


def test_scenario_41_a_refused_insert_does_not_reach_the_field(uat_terminal):
    """The same gate, reached from code rather than the keyboard - TkCurses-tvj.

    This is the one a person could not previously have watched happen, because
    insert() did not validate at all.
    """
    term = _scenario_41(uat_terminal)
    term.click(49, 5)  # the "insert 'x'" button
    term.wait_for_text("insert('end', 'x')")
    term.wait_for_cell(5, 22, lambda cell: cell.data.strip() == "")
    assert "contents now ''" in _last(term), term.describe()


def test_scenario_41_a_readonly_entry_ignores_an_insert_from_code(uat_terminal):
    term = _scenario_41(uat_terminal)
    term.click(49, 8)  # the "insert '9'" button
    term.wait_for_text("insert('end', '9')")
    term.wait_for_cell(8, 22, lambda cell: cell.data.strip() == "")
    assert "contents now ''" in _last(term), term.describe()


def test_scenario_41_a_focus_refusal_complains_and_keeps_the_text(uat_terminal):
    """The focus condition is advisory: reverting the text would be the bug."""
    term = _scenario_41(uat_terminal)
    term.click(22, 11)
    term.send_keys("a", "b")
    term.wait_for_cell(11, 23, lambda cell: cell.data == "b")
    term.send_keys("<Tab>")
    term.wait_for_text("REFUSED 'ab'")
    term.wait_for_cell(11, 22, lambda cell: cell.data == "a")
    assert term.row(11)[22:24] == "ab", (
        f"a focus refusal must not change the text\n{term.describe()}"
    )
    assert "onfocus=focusout" in _modes(term), (
        f"a focus refusal must not switch validation off\n{term.describe()}"
    )


def test_scenario_41_the_mode_readout_shows_validation_switching_itself_off(
    uat_terminal,
):
    """The reason this scenario exists.

    A validator that raises leaves validate at "none" for good, and nothing on
    screen says so except this column. The readout used to be drawn from inside
    the callback, before the machinery had changed anything, so it showed
    broken=key forever - the failure made invisible by the very thing built to
    show it.
    """
    term = _scenario_41(uat_terminal)
    assert "broken=key" in _modes(term), term.describe()
    term.click(22, 14)
    term.send_keys("a")
    term.wait_for_text("broken=NONE!")
    assert "broken=NONE!" in _modes(term), (
        f"validation switched itself off and the readout did not say so"
        f"\n{term.describe()}"
    )


def test_scenario_41_a_forced_write_lands_and_switches_validation_off(uat_terminal):
    """TkCurses-3xb: the condition that cannot refuse anything."""
    term = _scenario_41(uat_terminal)
    term.click(49, 17)  # "set variable"
    term.wait_for_text("forced=NONE!")
    term.wait_for_cell(17, 22, lambda cell: cell.data == "x")
    assert term.row(17)[22:25] == "xyz", (
        f"a forced write must land whatever the validator said\n{term.describe()}"
    )
    assert "forced=NONE!" in _modes(term), term.describe()


def test_scenario_41_reset_puts_every_entry_back(uat_terminal):
    """Most of what this scenario shows is one-way, so it needs a way back."""
    term = _scenario_41(uat_terminal)
    term.click(22, 14)
    term.send_keys("a")
    term.wait_for_text("broken=NONE!")
    term.send(b"\x12")  # Ctrl-R
    term.wait_for_text("validating again")
    term.wait_for(
        lambda t: "broken=key" in _modes(t),
        message="the broken entry to be validating again",
    )
    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0
    assert "Traceback" not in term.stderr


def test_scenario_41_the_mode_readout_survives_a_resize(uat_terminal):
    """The third fault found by driving this scenario, and the subtlest.

    The readout was written at ``screen.height - 4``. The support screen replays
    each line at the row it was written at, so after a shrink those rows no
    longer existed and the whole column vanished for good - measured by resizing
    a pty from 28 rows to 24. It now lives at fixed rows under the title, where
    a resize cannot strand it.
    """
    term = _scenario_41(uat_terminal)
    assert "digits=key" in _modes(term), term.describe()
    term.resize(90, 24)
    term.wait_for(
        lambda t: "digits=key" in _modes(t),
        message="the mode readout to still be on screen after a resize",
    )
    term.resize(90, 30)
    term.wait_for(
        lambda t: "digits=key" in _modes(t),
        message="the mode readout to survive growing again",
    )
    # And exactly one copy of it, not a stale one left at the old rows.
    assert sum("digits=" in row for row in term.display) == 1, (
        f"the readout was left duplicated by the resize\n{term.describe()}"
    )
    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0


def test_scenario_41_no_box_has_its_bottom_border_painted_over(uat_terminal):
    """The overlap fault, caught as a class rather than one widget at a time.

    Every bordered widget here is three rows tall. Place two of them less than
    three rows apart and the upper one's bottom border is painted over by the
    lower one's top - which is invisible to a smoke test, was already a recorded
    finding from UAT 40, recurred in this scenario, and then recurred AGAIN in
    one button after a multi-edit aborted half way and the repair was not
    re-checked. Reported from UAT 41: "you have insert '9' box overlapping on
    the bottom of insert 'x' box".

    So this does not name coordinates. In any column, a box corner that opens
    must close: count the top-left corners and the bottom-left corners and they
    must agree, and likewise on the right. An overlap eats a bottom corner and
    the counts diverge.
    """
    term = _scenario_41(uat_terminal)

    def corners(glyph):
        return collections.Counter(
            x for row in term.display for x, cell in enumerate(row) if cell == glyph
        )

    tops_left, bottoms_left = corners("┌"), corners("└")
    tops_right, bottoms_right = corners("┐"), corners("┘")
    assert tops_left and tops_right, f"no boxes on screen at all\n{term.describe()}"
    assert tops_left == bottoms_left, (
        "a box opened and never closed on the left, so something is painted over"
        f": tops {dict(tops_left)} bottoms {dict(bottoms_left)}\n{term.describe()}"
    )
    assert tops_right == bottoms_right, (
        "a box opened and never closed on the right"
        f": tops {dict(tops_right)} bottoms {dict(bottoms_right)}\n{term.describe()}"
    )


def test_scenario_41_a_readonly_entry_shows_that_it_has_the_focus(uat_terminal):
    """Reported from UAT 41, and the library's gap rather than the scenario's.

    Tk draws no insertion cursor in a readonly entry - its manual says so - and
    shows the focus with the highlight ring instead. This library has no ring,
    so a focused readonly field looked identical to an unfocused one. The border
    carries it now.
    """
    term = _scenario_41(uat_terminal)
    readonly_top, digits_top = 7, 4
    term.wait_for_cell(readonly_top, 25, lambda cell: cell.data == "─")
    assert not term.attrs_at(readonly_top, 25)["bold"], (
        f"nothing is focused yet\n{term.describe()}"
    )

    term.click(25, 8)  # into the readonly field
    term.wait_for(
        lambda t: t.attrs_at(readonly_top, 25)["bold"],
        message="the readonly entry's border to show the focus",
    )
    assert not term.attrs_at(digits_top, 25)["bold"], (
        f"two entries claim the focus at once\n{term.describe()}"
    )


# --------------------------------------------------------------- scenario 42
#
# Views, selections and columns: acceptance for #121-#132, which had none.
# Driven, not just started, for the reason scenario 41's section gives - a
# smoke test that waits for the title passed throughout two visible faults
# there. TkCurses-w1h.


def _scenario_42(uat_terminal):
    """The scenario, up and settled, with its readout on screen."""
    term = uat_terminal(cols=90, rows=28)
    term.run([sys.executable, "-m", "uat.scenario_42_views_and_selections"])
    term.wait_for_text("last: reset")
    term.wait_for_idle()
    return term


def _readout(term):
    """The two readout rows, as one string."""
    return " ".join(row.strip() for row in term.display[1:3])


def _press(term, column, row, expect):
    """Click a button and wait for the readout line it should produce."""
    term.click(column, row)
    term.wait_for(lambda t: expect in _readout(t), message=repr(expect))


def test_scenario_42_the_entry_view_and_selection_follow_tk(uat_terminal):
    """Each button's effect, read back from the readout - TkCurses-i8s/61v/bfy.

    Every assertion is on the readout line the step waited for, so a step
    cannot be judged on a half-drawn screen.
    """
    term = _scenario_42(uat_terminal)
    _press(term, 40, 5, "first shown 0  cursor 36  selection none")
    assert term.row(5)[3:7] == "0123", (
        f"a program's insert shows the START\n{term.describe()}"
    )
    _press(term, 40, 8, "selection 2-8")
    _press(term, 40, 11, "cursor 38  selection 4-10")  # insert XY at 0
    # And on screen, not only in the readout: the highlight is still on
    # "234567", now two cells to the right, and not on its neighbours. The
    # entry's text starts at column 3.
    # Waited for, not read straight after the readout: the readout and the
    # entry are different cells and need not arrive in one chunk (CLAUDE.md,
    # "A test must wait for every cell it asserts on").
    term.wait_for(
        lambda t: (
            t.row(5)[7:13] == "234567"
            and [c for c in range(3, 31) if t.attrs_at(5, c)["reverse"]]
            == list(range(7, 13))
        ),
        message="the highlight on '234567', two cells right",
    )
    _press(term, 40, 14, "cursor 36  selection 2-8")  # delete 0-2
    _press(term, 40, 17, "cursor 36  selection 2-12")  # adjust 12
    _press(term, 40, 20, "first shown 5  cursor 36  selection 2-12")  # xview 5
    term.send(ESCAPE)
    assert term.wait_for_exit(timeout=10) == 0


def test_scenario_42_the_tree_columns_fill_it_but_one(uat_terminal):
    """TkCurses-a01: name and kind take the width; size, stretch=False, keeps 5."""
    term = _scenario_42(uat_terminal)
    term.wait_for(lambda t: "tree columns 14/5/11 of 34" in _readout(t), message="tree")
    _press(term, 68, 15, "of 30")  # narrower
    assert "/5/" in _readout(term), term.describe()
    term.send(ESCAPE)


def test_scenario_42_validate_turns_the_check_field_red_and_back(uat_terminal):
    """TkCurses-52q, as a person sees it: the FIELD turns red, not just the
    readout. The first version of this test waited for the readout's
    "check: invalid" - the state - and passed while the field stayed its old
    colour until the next keystroke, because state() never repainted. The
    checklist promises a colour, so the colour is what is asserted.
    """
    term = _scenario_42(uat_terminal)
    term.click(5, 20)
    term.send_keys("a")
    term.wait_for_cell(20, 3, lambda cell: cell.data == "a")
    _press(term, 26, 20, "check: invalid")
    term.wait_for_cell(20, 3, lambda cell: cell.fg == "red")
    # Clear it, type a digit, and validate again: the red goes at once.
    term.click(5, 20)
    term.send_keys("<BackSpace>", "7")
    term.wait_for_cell(20, 3, lambda cell: cell.data == "7")
    _press(term, 26, 20, "check: valid")
    term.wait_for_cell(20, 3, lambda cell: cell.fg != "red")
    term.send(ESCAPE)


def test_scenario_42_the_list_scrolls_sideways(uat_terminal):
    """TkCurses-019: its scrollbar's right arrow moves the first column."""
    term = _scenario_42(uat_terminal)
    # The list's text starts at column 4: its border, then a cell of margin.
    assert term.row(11)[4:6] == "01", term.describe()
    term.click(30, 17)
    term.wait_for(lambda t: "first column 1" in _readout(t), message="list scrolled")
    # The rows moved, as well as the readout: every one shifted left by one.
    term.wait_for_cell(11, 4, lambda cell: cell.data == "1")
    term.wait_for_cell(12, 4, lambda cell: cell.data == "2")
    term.send(ESCAPE)


def test_scenario_42_tags_colour_the_tree_rows(uat_terminal):
    """TkCurses-67u: 'build' is tagged cyan, 'big.iso' red - the checklist says so."""
    term = _scenario_42(uat_terminal)
    build_row = next(i for i, row in enumerate(term.display) if " build " in row)
    big_row = next(i for i, row in enumerate(term.display) if "big.iso" in row)
    column = term.row(build_row).index("build")
    term.wait_for_cell(build_row, column, lambda cell: cell.fg == "cyan")
    term.wait_for_cell(
        big_row, term.row(big_row).index("big.iso"), lambda c: c.fg == "red"
    )
    term.send(ESCAPE)


def test_scenario_42_left_at_the_start_of_the_entry_stays(uat_terminal):
    """TkCurses-11m, as the checklist asks a person to try it."""
    term = _scenario_42(uat_terminal)
    _press(term, 40, 5, "cursor 36")  # fill
    term.click(10, 5)
    term.send_keys("<Home>", "<Left>")
    term.wait_for(lambda t: "cursor 0 " in _readout(t), message="cursor at 0")
    term.send(ESCAPE)


# --------------------------------------------------------------- scenario 43
#
# Copy, cut and paste, driven with the real keys - including the real Ctrl-C
# byte, which copies with a selection and closes without one. TkCurses-lw2.


def _scenario_43(uat_terminal):
    term = uat_terminal(cols=90, rows=24)
    term.run([sys.executable, "-m", "uat.scenario_43_copy_cut_paste"])
    term.wait_for_text("last: reset")
    term.wait_for_text("clipboard: (empty)")
    return term


def _clip(term):
    return term.display[1]


def _select_first_five(term):
    """Home, then Shift-Right five times: 'hello' selected in the source."""
    term.send_keys("<Home>")
    for _ in range(5):
        term.send(b"\x1b[1;2C")  # Shift-Right
    # The whole selection highlighted, waited for: the source's text starts
    # at column 21, and a key handled late would be judged half-done.
    term.wait_for(
        lambda t: all(t.attrs_at(5, c)["reverse"] for c in range(21, 26)),
        message="'hello' highlighted",
    )


def test_scenario_43_cut_here_and_paste_there(uat_terminal):
    term = _scenario_43(uat_terminal)
    term.wait_for_text("read-only")
    _select_first_five(term)
    term.send(b"\x18")  # Ctrl-X
    term.wait_for(
        lambda t: "clipboard: 'hello'" in t.display[1] and t.row(5)[21:27] == " world",
        message="cut",
    )
    term.click(25, 8)  # the target field
    term.wait_for_text("focus: target")
    term.send(b"\x16")  # Ctrl-V
    term.wait_for(lambda t: t.row(8)[21:26] == "hello", message="pasted")
    term.send(ESCAPE)


def test_scenario_43_ctrl_c_copies_a_selection_then_closes_without_one(uat_terminal):
    """The author's rule, with the real byte: copies, keeps running; then,
    the selection gone, closes."""
    term = _scenario_43(uat_terminal)
    term.wait_for_text("read-only")
    _select_first_five(term)
    term.send(b"\x03")
    term.wait_for_text("clipboard: 'hello'")
    assert term.row(5)[21:32] == "hello world", "a copy must not change the field"
    term.send_keys("<End>")
    term.wait_for_cell(5, 21, lambda cell: not cell.reverse)
    term.send(b"\x03")
    assert term.wait_for_exit(timeout=10) == 0


def test_scenario_43_a_masked_field_copies_its_stars(uat_terminal):
    term = _scenario_43(uat_terminal)
    term.wait_for_text("read-only")
    term.click(25, 11)
    term.wait_for_text("focus: masked")
    term.send(b"\x1f")  # Ctrl-/ : select all (it arrives as Ctrl-_)
    term.wait_for_cell(11, 21, lambda cell: cell.reverse)
    term.send(b"\x03")
    term.wait_for_text("clipboard: '******'")
    term.send(ESCAPE)


def test_scenario_43_a_read_only_field_cuts_as_a_copy(uat_terminal):
    term = _scenario_43(uat_terminal)
    term.wait_for_text("read-only")
    term.click(25, 14)
    term.wait_for_text("focus: locked")
    term.send(b"\x1f")
    term.wait_for_cell(14, 21, lambda cell: cell.reverse)
    term.send(b"\x18")
    term.wait_for(
        lambda t: (
            "clipboard: 'copy me, not cut'" in t.display[1]
            and t.row(14)[21:37] == "copy me, not cut"
        ),
        message="copied, not cut",
    )
    term.send(ESCAPE)


def test_scenario_43_the_text_copies_too(uat_terminal):
    term = _scenario_43(uat_terminal)
    term.wait_for_text("read-only")
    term.click(25, 17)
    term.wait_for_text("focus: text")
    term.send(b"\x1f")
    term.wait_for_cell(17, 21, lambda cell: cell.reverse)
    term.send(b"\x03")
    term.wait_for_text("clipboard: 'line one\\nline two")
    term.send(ESCAPE)


def test_scenario_43_the_middle_button_pastes_primary(uat_terminal):
    term = _scenario_43(uat_terminal)
    term.wait_for_text("read-only")
    _select_first_five(term)
    term.wait_for_text("PRIMARY: 'hello'")
    term.click(23, 8, button=2)  # the target, two cells in
    term.wait_for(lambda t: t.row(8)[21:26] == "hello", message="pasted PRIMARY")
    term.send(ESCAPE)


def test_scenario_43_dragging_selects_and_ctrl_c_copies_it(uat_terminal):
    """What a person tried first, and found did nothing: drag across a field
    to select, then copy. With real mouse reports, press, moves and release.
    TkCurses-lw2."""
    term = _scenario_43(uat_terminal)
    term.wait_for_text("read-only")
    # Paced by what is on screen, one report at a time: ncurses DROPS mouse
    # reports that arrive faster than the program reads them (TkCurses-txk),
    # and fired back to back the moves were lost on every CI runner while
    # passing here. A hand is never that fast; the test should not be either.
    term.send_mouse(21, 5, action="press")
    # Nothing on screen changes on the press - the cursor is already at the
    # start - so it gets the settle every drag test here uses, scaled for a
    # slow runner. A lost press is a lost drag: that was CI's whole failure.
    term._drain(term._budget(0.08))
    for column in range(22, 27):
        term.send_mouse(column, 5, action="move")
        term.wait_for(
            lambda t, column=column: all(
                t.attrs_at(5, c)["reverse"] for c in range(21, column)
            ),
            message=f"the highlight reaching column {column}",
        )
    term._drain(term._budget(0.08))
    term.send_mouse(26, 5, action="release")
    term.wait_for(
        lambda t: (
            all(t.attrs_at(5, c)["reverse"] for c in range(21, 26))
            and "PRIMARY: 'hello'" in t.display[1]
        ),
        message="'hello' dragged over, highlighted and on PRIMARY",
    )
    term.send(b"\x03")
    term.wait_for_text("clipboard: 'hello'")
    term.send(ESCAPE)


def test_scenario_43_selecting_elsewhere_clears_the_first_selection(uat_terminal):
    """What a person reported: select in source, copy, select in read-only,
    and source stayed highlighted. Tk clears the first - measured - and so
    does this now, Entry and Text alike. TkCurses-lw2."""
    term = _scenario_43(uat_terminal)
    term.wait_for_text("read-only")
    _select_first_five(term)
    term.send(b"\x03")
    term.wait_for_text("clipboard: 'hello'")
    term.click(25, 14)  # the read-only field
    term.wait_for_text("focus: locked")
    term.send(b"\x1f")  # select all there
    term.wait_for(
        lambda t: (
            t.attrs_at(14, 21)["reverse"]
            and not any(t.attrs_at(5, c)["reverse"] for c in range(21, 32))
        ),
        message="read-only selected, source no longer",
    )
    term.click(25, 17)  # the text
    term.wait_for_text("focus: text")
    term.send(b"\x1f")
    term.wait_for(
        lambda t: (
            t.attrs_at(17, 21)["reverse"]
            and not any(t.attrs_at(14, c)["reverse"] for c in range(21, 37))
        ),
        message="text selected, read-only no longer",
    )
    term.send(ESCAPE)


def test_scenario_43_pasting_over_a_selection_replaces_it(uat_terminal):
    """What a person expected and did not get: paste with text selected, and
    the selection is replaced. A deliberate departure from classic Tk on
    Linux, which keeps it; ttk replaces everywhere. TkCurses-lw2."""
    term = _scenario_43(uat_terminal)
    term.wait_for_text("read-only")
    _select_first_five(term)
    term.send(b"\x03")  # copy 'hello'
    term.wait_for_text("clipboard: 'hello'")
    term.send_keys("<End>")
    for _ in range(5):
        term.send(b"\x1b[1;2D")  # Shift-Left, five times: 'world'
    term.wait_for(
        lambda t: all(t.attrs_at(5, c)["reverse"] for c in range(27, 32)),
        message="'world' highlighted",
    )
    term.send(b"\x16")  # Ctrl-V
    term.wait_for(
        lambda t: (
            t.row(5)[21:32] == "hello hello"
            and not any(t.attrs_at(5, c)["reverse"] for c in range(21, 32))
        ),
        message="'world' replaced by 'hello', nothing left selected",
    )
    term.send(ESCAPE)


# ---------------------------------------------------------------------------
# Selecting with the mouse - double, triple and shift-clicks, and autoscroll
#
# The first tests anywhere to send a real double-click through a terminal: the
# decoder's click counting was only ever unit-tested. Run with the click window
# at its 1000ms maximum (TKCURSES_MOUSE_CLICK_INTERVAL) so that the harness can
# pace each report by the screen, as every mouse test here must - ncurses drops
# reports that arrive faster than the program reads them (TkCurses-txk) - and
# still land the second press inside the window on a slow runner. TkCurses-svtr.

#: Screen columns where each widget's text starts, and its row, at 90x24.
ENTRY_44, TENTRY_44, NARROW_44 = (18, 5), (18, 8), (18, 17)
TEXT_44 = (53, 5)


def _scenario_44(uat_terminal):
    term = uat_terminal(cols=90, rows=24, env={"TKCURSES_MOUSE_CLICK_INTERVAL": "1000"})
    term.run([sys.executable, "-m", "uat.scenario_44_mouse_selection"])
    term.wait_for_text("focus: entry")
    term.wait_for_text("line 07")
    return term


def _settle(term):
    term._drain(term._budget(0.05))


def _clicks(term, x, y, count):
    """``count`` presses and releases on one cell, each report settled."""
    for _ in range(count):
        term.send_mouse(x, y, action="press")
        _settle(term)
        term.send_mouse(x, y, action="release")
        _settle(term)


def _reversed(term, row, columns):
    return all(term.attrs_at(row, c)["reverse"] for c in columns)


def test_scenario_44_a_double_click_selects_a_word(uat_terminal):
    term = _scenario_44(uat_terminal)
    x, y = ENTRY_44
    _clicks(term, x + 8, y, 2)  # the 'o' of 'world'
    term.wait_for(
        lambda t: (
            "last: double-click on entry" in t.display[1]
            and "selected: 7-12 'world'" in t.display[3]
            and "cursor: 12" in t.display[2]
            and _reversed(t, y, range(x + 7, x + 12))
            and not t.attrs_at(y, x + 6)["reverse"]
        ),
        message="'world' selected by a double-click, the cursor after it",
    )
    term.send(ESCAPE)


def test_scenario_44_a_triple_click_in_the_text_selects_its_line(uat_terminal):
    term = _scenario_44(uat_terminal)
    x, y = TEXT_44
    _clicks(term, x + 3, y + 2, 3)  # in '  bar', line 3
    term.wait_for(
        lambda t: (
            "last: triple-click on text" in t.display[1]
            and "selected: 3.0-4.0 '  bar\\n'" in t.display[3]
            and "cursor: 3.0" in t.display[2]
        ),
        message="line 3 and its newline selected, the cursor at its start",
    )
    term.send(ESCAPE)


def test_scenario_44_a_drag_after_a_double_click_extends_by_words(uat_terminal):
    term = _scenario_44(uat_terminal)
    x, y = TEXT_44
    _clicks(term, x + 5, y, 1)
    term.send_mouse(x + 5, y, action="press")  # the second press: a double
    _settle(term)
    term.wait_for_text("selected: 1.4-1.7 'two'")
    term.send_mouse(x + 10, y, action="move", button=1)
    term.wait_for(
        lambda t: (
            "selected: 1.4-1.13 'two three'" in t.display[3]
            and _reversed(t, y, range(x + 4, x + 13))
        ),
        message="extended to the whole of 'three'",
    )
    term.send_mouse(x + 10, y, action="release")
    term.send(ESCAPE)


def test_scenario_44_a_ttk_shift_click_extends_and_moves_the_cursor(uat_terminal):
    term = _scenario_44(uat_terminal)
    x, y = TENTRY_44
    _clicks(term, x + 7, y, 1)
    term.wait_for_text("focus: tentry")
    term.send(b"\x1b[<4;31;9M")  # a shift-press at column 31, row 9 (1-based)
    _settle(term)
    term.send(b"\x1b[<4;31;9m")
    term.wait_for(
        lambda t: (
            "last: shift-click on tentry" in t.display[1]
            and "selected: 7-12 'world'" in t.display[3]
            and "cursor: 12" in t.display[2]
        ),
        message="extended from the click to the shift-click, the cursor there",
    )
    term.send(ESCAPE)


def test_scenario_44_a_double_clicks_drag_stays_with_its_widget(uat_terminal):
    """The double press takes the grab, as a single one does: dragged down
    over the ttk entry, it is still the first entry extending by words."""
    term = _scenario_44(uat_terminal)
    x, y = ENTRY_44
    _clicks(term, x + 8, y, 1)
    term.send_mouse(x + 8, y, action="press")
    _settle(term)
    term.wait_for_text("selected: 7-12 'world'")
    term.send_mouse(x + 15, TENTRY_44[1], action="move", button=1)
    term.wait_for(
        lambda t: (
            "focus: entry" in t.display[2]
            and "selected: 7-21 'world  foo_bar'" in t.display[3]
            and not _reversed(t, TENTRY_44[1], range(TENTRY_44[0], TENTRY_44[0] + 5))
        ),
        message="the first entry extended; the one under the pointer untouched",
    )
    term.send_mouse(x + 15, TENTRY_44[1], action="release")
    term.send(ESCAPE)


def test_scenario_44_dragging_past_the_narrow_field_keeps_scrolling(uat_terminal):
    term = _scenario_44(uat_terminal)
    x, y = NARROW_44
    term.send_mouse(x + 1, y, action="press")
    _settle(term)
    term.send_mouse(x + 27, y, action="move", button=1)  # past its right edge
    # Held still out there, it goes on scrolling: no further reports arrive,
    # so only the repeating timer can be doing it.
    term.wait_for(
        lambda t: (
            t.row(y)[x : x + 9] != "the quick"
            and "selected: 1-" in t.display[3]
            and int(t.display[3].split("selected: 1-")[1].split()[0]) > 30
        ),
        message="the field scrolled on its own and the selection grew past 30",
    )
    term.send_mouse(x + 27, y, action="release")
    _settle(term)
    term.wait_for_idle()
    stopped = term.row(y)
    term._drain(term._budget(0.3))
    assert term.row(y) == stopped, "the release stopped it"
    term.send(ESCAPE)


def test_scenario_44_dragging_below_the_text_scrolls_it(uat_terminal):
    term = _scenario_44(uat_terminal)
    x, y = TEXT_44
    term.send_mouse(x, y, action="press")
    _settle(term)
    term.send_mouse(x, y + 15, action="move", button=1)  # rows below its bottom
    term.wait_for(
        lambda t: t.row(y)[x : x + 7] != "one two" and "selected: 1.0-" in t.display[3],
        message="the text scrolled down, selecting from the press",
    )
    term.send_mouse(x, y + 15, action="release")
    term.send(ESCAPE)


def test_scenario_44_an_alt_click_extends_where_shift_cannot_reach(uat_terminal):
    """The bytes the author's VTE terminal sent for an Alt-click, recorded by a
    raw probe that also showed it never sends a Shift-click: ESC [<8;x;yM. In
    the text, from a drag over 'two' to an Alt-click in 'four'."""
    term = _scenario_44(uat_terminal)
    x, y = TEXT_44
    term.send_mouse(x + 4, y, action="press")
    _settle(term)
    term.send_mouse(x + 7, y, action="move", button=1)
    _settle(term)
    term.send_mouse(x + 7, y, action="release")
    term.wait_for_text("selected: 1.4-1.7 'two'")
    term.send(f"\x1b[<8;{x + 16};{y + 1}M".encode())  # Alt, button 1, 1-based
    _settle(term)
    term.send(f"\x1b[<8;{x + 16};{y + 1}m".encode())
    term.wait_for(
        lambda t: (
            "last: alt-click on text" in t.display[1]
            and "selected: 1.4-1.15 'two three f'" in t.display[3]
            and "cursor: 1.15" in t.display[2]
        ),
        message="extended from 'two' to the alt-click",
    )
    term.send(ESCAPE)


def test_scenario_44_a_ctrl_click_moves_the_cursor_and_keeps_the_selection(
    uat_terminal,
):
    """With the bytes the author's terminal sends for a Ctrl-click, recorded
    by the raw mouse probe: ESC [<16;x;yM. TkCurses-mndh."""
    term = _scenario_44(uat_terminal)
    x, y = ENTRY_44
    term.send_mouse(x + 7, y, action="press")
    _settle(term)
    term.send_mouse(x + 12, y, action="move", button=1)
    _settle(term)
    term.send_mouse(x + 12, y, action="release")
    term.wait_for_text("selected: 7-12 'world'")
    term.send(f"\x1b[<16;{x + 3};{y + 1}M".encode())  # Ctrl, button 1, 1-based
    _settle(term)
    term.send(f"\x1b[<16;{x + 3};{y + 1}m".encode())
    term.wait_for(
        lambda t: (
            "last: ctrl-click on entry" in t.display[1]
            and "selected: 7-12 'world'" in t.display[3]
            and "cursor: 2" in t.display[2]
            and _reversed(t, y, range(x + 7, x + 12))
        ),
        message="the cursor moved to 2 and 'world' stayed selected",
    )
    term.send(ESCAPE)


# ---------------------------------------------------------------------------
# Key sequences - chords, with the real bytes a terminal sends: Ctrl-X is 0x18,
# Ctrl-S 0x13. Each waits for the help Label before pressing anything: the
# readout is written straight to the screen and appears BEFORE the widgets
# are laid out, and the layout's <Configure> on another widget cancels a chord
# - as it does in Tk, measured. TkCurses-jfm.


def _scenario_45(uat_terminal):
    term = uat_terminal(cols=80, rows=16)
    term.run([sys.executable, "-m", "uat.scenario_45_key_sequences"])
    term.wait_for_text("Ctrl-X then Ctrl-S")
    term.wait_for_text("focus: pad")
    return term


def test_scenario_45_a_chord_fires(uat_terminal):
    term = _scenario_45(uat_terminal)
    term.send(b"\x18")
    term.wait_for_text("last key: x")
    term.send(b"\x13")
    term.wait_for_text("chords: save")
    term.send(ESCAPE)


def test_scenario_45_a_key_in_between_cancels_it(uat_terminal):
    term = _scenario_45(uat_terminal)
    term.send(b"\x18")
    term.wait_for_text("last key: x")
    term.send(b"a")
    term.wait_for_text("last key: a")
    term.send(b"\x13")
    term.wait_for_text("last key: s")
    term.wait_for_idle()
    assert "chords: (none yet)" in term.row(2), term.describe()
    term.send(ESCAPE)


def test_scenario_45_the_quirk_holds_with_real_keys(uat_terminal):
    """Ctrl-X twice then Ctrl-S does nothing, as in both Tks; a third
    Ctrl-X and it does."""
    term = _scenario_45(uat_terminal)
    for _ in range(2):
        term.send(b"\x18")
        term.wait_for_idle()
    term.send(b"\x13")
    term.wait_for_text("last key: s")
    term.wait_for_idle()
    assert "chords: (none yet)" in term.row(2), term.describe()
    for _ in range(3):
        term.send(b"\x18")
        term.wait_for_idle()
    term.send(b"\x13")
    term.wait_for_text("chords: save")
    term.send(ESCAPE)


# ---------------------------------------------------------------------------
# Menu columns and shortcuts. The menubar's "Colours" is drawn by a widget, so
# waiting for it is waiting for the layout. TkCurses-aj1.13.1.


def _scenario_46(uat_terminal):
    term = uat_terminal(cols=80, rows=20)
    term.run([sys.executable, "-m", "uat.scenario_46_menu_columns_accelerators"])
    term.wait_for_text("Colours")
    term.wait_for_text("last chosen: -")
    term.wait_for_idle()
    return term


def test_scenario_46_a_click_in_the_second_column_chooses_there(uat_terminal):
    term = _scenario_46(uat_terminal)
    term.send(b"\x1bOR")  # F3: Colours
    term.wait_for_text("Purple")
    row = next(i for i, line in enumerate(term.display) if "Teal" in line)
    term.click(term.display[row].index("Teal") + 1, row)
    term.wait_for_text("last chosen: colour Teal")
    term.send(ESCAPE)


def test_scenario_46_down_goes_from_a_columns_foot_to_the_next_top(uat_terminal):
    term = _scenario_46(uat_terminal)
    term.send(b"\x1bOR")
    term.wait_for_text("Purple")
    for _ in range(6):  # Black, Maroon, Green, Olive, Navy, then Purple
        term.send_keys("<Down>")
        term.wait_for_idle()
    term.send(b"\r")
    term.wait_for_text("last chosen: colour Purple")
    term.send(ESCAPE)


def test_scenario_46_the_shortcuts_work_with_the_menu_closed(uat_terminal):
    term = _scenario_46(uat_terminal)
    term.send(b"\x0f")  # Ctrl+O
    term.wait_for_text("last chosen: Open")
    term.send(b"\x18")  # Ctrl+X ...
    term.wait_for_idle()
    term.send(b"\x13")  # ... Ctrl+S
    term.wait_for_text("last chosen: Save")
    term.send(b"\x10")  # Ctrl+P: Print is disabled
    term.wait_for_idle()
    assert "last chosen: Save" in term.row(1), term.describe()
    term.send(b"\x1b[15~")  # F5, from the Recent submenu
    term.wait_for_text("last chosen: Last file")
    term.send(ESCAPE)


def test_scenario_46_left_in_a_dropdown_opens_the_menu_to_its_left(uat_terminal):
    """Found writing this checklist: Left closed the dropdown instead."""
    term = _scenario_46(uat_terminal)
    term.send(b"\x1bOR")  # F3: Colours
    term.wait_for_text("Purple")
    term.send_keys("<Left>")
    term.wait_for(
        lambda t: (
            any("Open..." in row for row in t.display)
            and not any("Purple" in row for row in t.display)
        ),
        message="File's menu open in place of Colours",
    )
    term.send(ESCAPE)


def test_scenario_46_a_shortcut_does_nothing_while_a_menu_is_open(uat_terminal):
    """The author's report: F3, then F5, and "last file" was written over
    the menu's top border. F5 should not have fired at all - Tk's open menu
    keeps every key - and the readout writing over the menu was the visible
    half of that."""
    term = _scenario_46(uat_terminal)
    term.send(b"\x1bOR")  # F3: Colours
    term.wait_for_text("Purple")
    top = next(i for i, row in enumerate(term.display) if "┌" in row)
    term.send(b"\x1b[15~")  # F5
    term.wait_for_idle()
    term._drain(term._budget(0.3))
    assert "Last file" not in "\n".join(term.display), term.describe()
    assert "┌" in term.display[top], "the menu's top border is intact"
    term.send(ESCAPE)


def test_scenario_46_escape_leaves_nothing_highlighted_on_the_bar(uat_terminal):
    """The author's report: F3, Escape, and Colours stayed highlighted while
    the arrows did nothing to it. Tk clears the bar's highlight."""
    term = _scenario_46(uat_terminal)
    column = term.display[0].index("Colours")
    term.send(b"\x1bOR")  # F3
    term.wait_for(
        lambda t: "Purple" in "\n".join(t.display) and t.attrs_at(0, column)["reverse"],
        message="Colours open and highlighted",
    )
    term.send(ESCAPE)
    term.wait_for(
        lambda t: (
            "Purple" not in "\n".join(t.display)
            and not t.attrs_at(0, column)["reverse"]
        ),
        message="Colours closed, and not highlighted",
    )
    term.send_keys("<Right>")
    term.wait_for_idle()
    assert "Open..." not in "\n".join(term.display), "no menu opened"
    assert not term.attrs_at(0, column)["reverse"]


# ---------------------------------------------------------------------------
# Treeview frozen rows and columns. "Region" is the tree's own heading, so
# waiting for it is waiting for the tree to draw. TkCurses-xe9.6.


def _scenario_47(uat_terminal):
    term = uat_terminal(cols=80, rows=24)
    term.run([sys.executable, "-m", "uat.scenario_47_treeview_frozen_titles"])
    term.wait_for(
        lambda t: (
            "titlecolumns=0" in t.row(1) and any("Region" in r for r in t.display)
        ),
        message="the readout and the tree's heading",
    )
    term.wait_for_idle()
    return term


def _heading_row(term):
    return next(row for row in term.display if "Region" in row or "North" in row)


def test_scenario_47_a_frozen_tree_column_stays_as_the_rest_scroll(uat_terminal):
    term = _scenario_47(uat_terminal)
    term.send_keys("c")
    term.wait_for_text("titlecolumns=1")
    term.send_keys(">")
    term.wait_for(
        lambda t: "Region" in _heading_row(t) and "North" not in _heading_row(t),
        message="Region frozen, North scrolled away under it",
    )
    term.send(ESCAPE)


def test_scenario_47_unfrozen_the_tree_column_scrolls_away(uat_terminal):
    term = _scenario_47(uat_terminal)
    term.send_keys(">")
    term.wait_for(
        lambda t: not any("Region" in r for r in t.display),
        message="the tree column scrolled off the left",
    )
    term.send(ESCAPE)


def test_scenario_47_frozen_rows_stay_on_top(uat_terminal):
    term = _scenario_47(uat_terminal)
    term.send_keys("i", "i")
    term.wait_for_text("titleitems=2")
    # Two titles leave ten rows that scroll, so the sixteenth row is past
    # them: the twelfth, tried first, was still in view and moved nothing.
    for _ in range(16):
        term.send_keys("<Down>")
    term.wait_for(
        lambda t: (
            any("Group 0" in r for r in t.display)
            and any("Item 0.0" in r for r in t.display)
            and not any("Item 0.1 " in r for r in t.display)
            and "yview (0.00" not in t.row(2)
        ),
        message="Group 0 and Item 0.0 frozen while the rows under them scrolled",
    )
    term.send(ESCAPE)


def test_scenario_47_a_click_names_the_cell_under_it(uat_terminal):
    term = _scenario_47(uat_terminal)
    term.send_keys("c", ">")
    term.wait_for(
        lambda t: "titlecolumns=1" in t.row(1) and "North" not in _heading_row(t),
        message="scrolled with the tree column frozen",
    )
    row = next(i for i, line in enumerate(term.display) if "Item 0.0" in line)
    term.click(term.display[row].index("Item 0.0") + 1, row)
    term.wait_for_text("last clicked: Item 0.0 #0")
    term.send(ESCAPE)


# ---------------------------------------------------------------------------
# How classic widgets look. The readout's "focus: plain" is written after the
# widgets are built, and the plain field's text is drawn by the field itself,
# so waiting for both is waiting for the scene. Colours are read on an
# eight-colour terminal, where a colour name comes back as itself.
# TkCurses-gm66.11.

#: DECSCUSR, ``ESC [ n SP q``: a request for the cursor's shape.
_CURSOR_SHAPE = re.compile(rb"\x1b\[(\d) q")


def _scenario_48(uat_terminal):
    term = uat_terminal(cols=80, rows=24, env={"TERM": "xterm", "COLORTERM": ""})
    term.run([sys.executable, "-m", "uat.scenario_48_classic_looks"])
    term.wait_for(
        lambda t: (
            "focus: plain" in t.row(2) and any("plain field" in r for r in t.display)
        ),
        message="the readout and the plain field",
    )
    term.wait_for_idle()
    return term


def _at(term, text):
    row = next(i for i, line in enumerate(term.display) if text in line)
    return row, term.display[row].index(text)


def test_scenario_48_moving_the_focus_reshapes_the_cursor(uat_terminal):
    term = _scenario_48(uat_terminal)
    assert not _CURSOR_SHAPE.search(term.received), "the plain field asked for a shape"
    term.send_keys("<F8>")
    term.wait_for_text("focus: bar")
    term.wait_for(
        lambda t: b"\x1b[5 q" in t.received, message="a blinking bar for insertwidth=1"
    )
    term.send_keys("<F8>")
    term.wait_for_text("focus: steady")
    term.wait_for(lambda t: b"\x1b[6 q" in t.received, message="a steady bar")
    term.send(ESCAPE)


def test_scenario_48_a_disabled_field_takes_its_colours(uat_terminal):
    term = _scenario_48(uat_terminal)
    row, column = _at(term, "a thin bar")
    column += 7  # the "b" of "bar", past the selection's five cells
    term.send_keys("<F5>")
    term.wait_for_text("fields: disabled")
    term.wait_for_cell(
        row,
        column,
        lambda cell: cell.data == "b" and (cell.fg, cell.bg) == ("brown", "blue"),
        message="yellow on blue",
    )
    term.send_keys("<F5>")
    term.wait_for_text("fields: readonly")
    term.wait_for_cell(
        row, column, lambda cell: cell.bg == "magenta", message="readonly magenta"
    )
    term.send(ESCAPE)


def test_scenario_48_an_active_button_takes_its_colours(uat_terminal):
    term = _scenario_48(uat_terminal)
    row, column = _at(term, "Press me")
    term.send_keys("<F6>")
    term.wait_for_text("buttons: active")
    term.wait_for_cell(
        row,
        column,
        lambda cell: cell.data == "P" and (cell.fg, cell.bg) == ("brown", "red"),
        message="yellow on red",
    )
    term.send(ESCAPE)


def test_scenario_48_f7_hides_the_texts_unfocused_selection(uat_terminal):
    term = _scenario_48(uat_terminal)
    row, column = _at(term, "a block cursor")
    selected = column + 2  # "block", 1.2 to 1.7
    term.wait_for_cell(
        row, selected, lambda cell: cell.bg == "green", message="green, unfocused"
    )
    term.send_keys("<F7>")
    term.wait_for_text("selection: hidden")
    term.wait_for_cell(
        row,
        selected,
        lambda cell: cell.data == "b" and cell.bg != "green" and not cell.reverse,
        message="the selection hidden",
    )
    term.send(ESCAPE)
