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

"""``tkcurses-cfg`` alone at a terminal: the interactive screen, driven
through a real pseudo-terminal.

Every test waits for the cells it then reads (see CLAUDE.md, "Writing a tty
test"): the screen redraws whole frames, and a sample can land in the
middle of one.
"""

from __future__ import annotations

import os
import textwrap

import pytest

pytestmark = pytest.mark.tty

PROGRAM = """
from pathlib import Path
from tkcurses._cfg import cli
cli.config_paths = lambda: (Path({system!r}), Path({user!r}))
raise SystemExit(cli.main([]))
"""


@pytest.fixture
def screen(terminal, tmp_path):
    """Start the screen on scratch files: ``screen(user=..., system=...)``."""

    def start(cols=80, rows=24, *, user=None, system=None, env=None):
        system_path = tmp_path / "etc" / "tkcurses.ini"
        user_path = tmp_path / "home" / "tkcurses" / "tkcurses.ini"
        system_path.parent.mkdir(exist_ok=True)
        for path, text in ((system_path, system), (user_path, user)):
            if text is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
        term = terminal(cols, rows, env=env or {})
        term.run_source(PROGRAM.format(system=str(system_path), user=str(user_path)))
        term.wait_for_text("SETTING")
        term.system, term.user = system_path, user_path
        return term

    return start


def row_of(term, key: str) -> str:
    """The screen row showing setting ``key``."""
    for line in term.display:
        if line.startswith(f"   {key} "):
            return line
    raise AssertionError(f"no row for {key}:\n" + "\n".join(term.display))


def showing(key: str, *words: str):
    """A wait: ``key``'s row holds every one of ``words``."""

    def holds(term) -> bool:
        try:
            line = row_of(term, key)
        except AssertionError:
            return False
        return all(word in line.split() for word in words)

    return holds


def test_every_setting_its_value_unit_and_source(screen):
    term = screen(
        user="[mouse]\nclick_interval = 300\n",
        env={"TKCURSES_MOUSE_ENABLED": "0"},
    )
    term.wait_for(showing("enabled", "false", "environment"))
    assert row_of(term, "click_interval").split() == [
        "click_interval",
        "300",
        "ms",
        "300",
        "ms",
        "user",
    ]
    assert row_of(term, "escape_delay").split() == [
        "escape_delay",
        "-",
        "25",
        "ms",
        "default",
    ]
    assert row_of(term, "enabled").split() == ["enabled", "-", "false", "environment"]
    assert "editing your file" in term.row(0)


def test_the_details_follow_the_cursor(screen):
    term = screen()
    term.wait_for_text("mouse.click_interval = 200 ms, from the default")
    term.send_keys("<Down>")
    term.wait_for_text("mouse.enabled = true, from the default")
    assert term.contains("Takes true or false; default true.")


def test_a_number_is_typed_saved_and_written(screen):
    term = screen()
    term.send_keys("<Enter>")
    term.wait_for_text("Takes a whole number of milliseconds")
    term.send_keys(
        "<BackSpace>", "<BackSpace>", "<BackSpace>", "4", "5", "0", "<Enter>"
    )
    term.wait_for(showing("click_interval", "450", "*"))
    assert "1 unsaved" in term.row(0)
    term.send_keys("s")
    term.wait_for_text("Save these changes?")
    assert term.contains("mouse.click_interval  not set -> 450 ms")
    term.send_keys("y")
    term.wait_for_text("Saved 1 change to")
    assert term.user.read_text() == "[mouse]\nclick_interval = 450\n"
    term.wait_for(
        lambda t: "unsaved" not in t.row(0) and "*" not in row_of(t, "click_interval")
    )


@pytest.mark.parametrize(("cols", "rows"), [(80, 24), (60, 15), (100, 40)])
def test_the_details_never_cover_the_status_line(screen, cols, rows):
    """mouse.enabled's description is three lines at 80 columns, which
    once ran the details pane into the status line below it."""
    term = screen(cols, rows)
    term.send_keys("<Down>")  # no message: the status line stays empty

    def drawn(t) -> bool:
        return t.contains(
            "mouse.enabled = true, from the default"
        ) and "q quit" in t.row(rows - 1)

    term.wait_for(drawn)
    assert term.row(rows - 2).strip() == ""
    term.send_keys(" ")
    message = "mouse.enabled: false - not saved yet."
    term.wait_for(lambda t: t.row(rows - 2).strip() == message)


def test_a_number_out_of_range_is_not_accepted(screen):
    term = screen()
    term.send_keys(
        "<Enter>", "<BackSpace>", "<BackSpace>", "<BackSpace>", "5", "0", "0", "0"
    )
    term.wait_for_text("5000 is outside 1-1000")
    term.send_keys("<Enter>")  # refused: the field stays
    term.send_keys("<Up>")  # from past the end, to the end
    term.wait_for_text("[1000")
    term.send_keys("<Escape>")
    term.wait_for(lambda t: not t.contains("Esc cancel"))
    assert "*" not in row_of(term, "click_interval")


def test_space_switches_a_true_false_setting(screen):
    term = screen()
    term.send_keys("<Down>", " ")
    term.wait_for(showing("enabled", "false", "*"))
    term.send_keys(" ")
    term.wait_for(
        lambda t: "*" not in row_of(t, "enabled") and "true" in row_of(t, "enabled")
    )


def test_a_choice_is_picked_from_a_list(screen):
    term = screen()
    for _ in range(4):
        term.send_keys("<Down>")
    term.wait_for_text("display.color_mode = auto")
    term.send_keys("<Enter>")
    term.wait_for_text("auto   (now)")
    term.send_keys("<Down>", "<Down>", "<Down>", "<Enter>")
    term.wait_for(showing("color_mode", "256", "*"))


def test_quitting_with_changes_asks_and_discarding_leaves_the_file(screen):
    term = screen(user="[mouse]\nenabled = no\n")
    term.send_keys("<Down>", " ")
    term.wait_for(showing("enabled", "true", "*"))
    term.send_keys("q")
    term.wait_for_text("1 change not saved.")
    term.send_keys("<Escape>")  # keep editing
    term.wait_for(lambda t: not t.contains("1 change not saved."))
    term.send_keys("q")
    term.wait_for_text("1 change not saved.")
    term.send_keys("d")
    assert term.wait_for_exit() == 0
    assert term.user.read_text() == "[mouse]\nenabled = no\n"


def test_quitting_with_nothing_changed_does_not_ask(screen):
    term = screen()
    term.send_keys("q")
    assert term.wait_for_exit() == 0


def test_save_and_quit(screen):
    term = screen()
    term.send_keys("<Down>", " ", "q")
    term.wait_for_text("s save and quit")
    term.send_keys("s")
    term.wait_for_text("Save these changes?")
    term.send_keys("y")
    assert term.wait_for_exit() == 0
    assert term.user.read_text() == "[mouse]\nenabled = false\n"


def test_ctrl_c_restores_the_terminal_and_says_what_was_lost(screen):
    term = screen()
    term.send_keys("<Down>", " ")
    term.wait_for(showing("enabled", "false", "*"))
    term.send(b"\x03")
    assert term.wait_for_exit() == 130
    assert "interrupted; 1 unsaved change discarded" in term.stderr
    assert (
        term.received.endswith(b"\x1b[?1049l") or b"\x1b[?1049l" in term.received[-200:]
    )
    assert not term.user.exists()


def test_a_bad_value_blocks_saving_until_the_problems_list_fixes_it(screen):
    term = screen(user="[input]\nescape_delay = 5000\n")
    term.wait_for_text("1 problem in this file: p to see and fix.")
    term.send_keys("<Down>", " ")
    term.wait_for_text("cannot be saved while this file has a bad value")
    assert "!" in row_of(term, "enabled").split()
    term.send_keys("s")
    term.wait_for_text("Cannot save")
    term.send_keys("x")
    term.wait_for(lambda t: not t.contains("Cannot save"))
    term.send_keys("p")
    term.wait_for_text("5000 is outside 0-1000")
    term.send_keys("u")
    term.wait_for(showing("enabled", "false", "*"))
    term.wait_for_text("No problems in your file.")
    term.send_keys("s")
    term.wait_for_text("5000 -> not set")
    term.send_keys("y")
    term.wait_for_text("Saved 2 changes to")
    # The emptied [input] stays, as tkcurses-cfg unset leaves it.
    assert term.user.read_text() == "[input]\n\n[mouse]\nenabled = false\n"


def test_tab_edits_the_system_wide_file(screen):
    term = screen(system="[mouse]\nenabled = no\n")
    term.send_keys("<Tab>")
    term.wait_for_text("editing the system-wide file")
    term.wait_for(showing("enabled", "false", "false", "system"))
    term.send_keys("<Down>", " ", "s", "y")
    term.wait_for_text("Saved 1 change to")
    assert term.system.read_text() == "[mouse]\nenabled = true\n"


@pytest.mark.skipif(os.geteuid() == 0, reason="root may write anywhere")
def test_a_file_that_cannot_be_written_is_read_only_and_says_why(screen, tmp_path):
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc").chmod(0o555)
    try:
        term = screen()
        term.send_keys("<Tab>")
        term.wait_for_text("editing the system-wide file (read-only)")
        term.wait_for_text(
            "The system-wide file: read-only. It needs root: sudo tkcurses-cfg."
        )
        term.send_keys("<Down>", " ")
        term.wait_for_text("cannot be changed. It needs root: sudo tkcurses-cfg.")
        assert "*" not in row_of(term, "enabled")
    finally:
        (tmp_path / "etc").chmod(0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="root may write anywhere")
def test_a_failed_save_keeps_the_changes(screen):
    term = screen(user="[mouse]\nenabled = no\n")
    term.send_keys("<Down>", " ")
    term.wait_for(showing("enabled", "true", "*"))
    term.user.parent.chmod(0o555)
    try:
        term.send_keys("s", "y")
        term.wait_for_text("Not saved")
        assert term.contains("permission denied")
        term.send_keys("x")
        term.wait_for(lambda t: not t.contains("Not saved"))
        assert "*" in row_of(term, "enabled").split()
    finally:
        term.user.parent.chmod(0o755)
    term.send_keys("s", "y")
    term.wait_for_text("Saved 1 change to")
    assert term.user.read_text() == "[mouse]\nenabled = true\n"


def test_a_change_on_disk_is_read_again(screen):
    term = screen(user="[mouse]\nenabled = no\n")
    term.wait_for(showing("enabled", "false"))
    term.user.write_text("[mouse]\nenabled = no\nclick_interval = 333\n")
    term.wait_for_text("Your file changed on disk and was read again.")
    term.wait_for(showing("click_interval", "333"))


def test_the_smallest_layout_and_too_small(screen):
    term = screen(60, 15)
    term.wait_for(lambda t: "q quit" in t.row(14) and "click_interval" in t.row(3))
    term.resize(50, 12)
    term.wait_for_text("tkcurses-cfg needs 60x15;")
    assert term.contains("this terminal is 50x12.")
    term.resize(80, 24)
    term.wait_for(showing("primary", "true", "default"))
    term.send_keys("q")
    assert term.wait_for_exit() == 0


def test_help_lists_the_keys(screen):
    term = screen()
    term.send_keys("?")
    term.wait_for_text("take the setting out of this file")
    for _ in range(10):
        term.send_keys("<Down>")  # longer than 24 rows: scroll to its end
    term.wait_for_text("Values are typed without their unit")
    term.send_keys("x")
    term.wait_for(lambda t: not t.contains("take the setting out of this file"))


def test_more_shows_the_whole_description_and_where_the_value_comes_from(screen):
    term = screen(
        system="[input]\nescape_delay = 40\n", user="[input]\nescape_delay = 60\n"
    )
    for _ in range(7):
        term.send_keys("<Down>")
    term.wait_for_text("input.escape_delay = 60 ms, from your file")
    term.send_keys("i")
    term.wait_for_text("Where it comes from, lowest first:")
    assert term.contains("> user 60 ms")
    assert term.contains("system 40 ms")


def test_a_bug_in_the_screen_restores_the_terminal_and_is_reported(terminal, tmp_path):
    term = terminal(80, 24)
    term.run_source(
        PROGRAM.replace(
            "raise SystemExit",
            "from tkcurses._cfg import ui\n"
            "ui.Screen.handle = lambda self, key: 1 / 0\n"
            "raise SystemExit",
        ).format(system=str(tmp_path / "s.ini"), user=str(tmp_path / "u.ini"))
    )
    term.wait_for_text("SETTING")
    term.send_keys("j")
    assert term.wait_for_exit() == 1
    assert "unexpected error: ZeroDivisionError" in term.stderr
    assert b"\x1b[?1049l" in term.received[-200:]  # back from the alternate screen


def test_without_colour_a_change_is_marked_in_bold(screen):
    term = screen()  # the harness sets NO_COLOR
    term.send_keys("<Down>", " ")
    term.wait_for(showing("enabled", "false", "*"))
    line = row_of(term, "enabled")
    row = term.display.index(line)
    attrs = term.attrs_at(row, line.index("*"))
    plain = term.attrs_at(row, line.index("enabled"))
    assert attrs["bold"] and not plain["bold"]
    assert (attrs["fg"], attrs["bg"]) == (plain["fg"], plain["bg"])  # no colour


def test_without_a_terminal_it_prints_the_help(capsys):
    from tkcurses._cfg import cli

    assert cli.main([]) == 2
    assert "usage: tkcurses-cfg" in capsys.readouterr().err


def test_the_program_text_is_a_complete_program():
    """The template every test runs; a mistake in it fails every test the
    same way, which reads as a broken screen."""
    compile(textwrap.dedent(PROGRAM.format(system="/s", user="/u")), "p", "exec")
