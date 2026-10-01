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

import contextlib
import io
import os
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
