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

"""Tests for the pty/pyte harness itself.

Everything else asserts through this harness, so its own behaviour is verified
against plain curses programs before any TkCurses code depends on it.
"""

from __future__ import annotations

import time

import pytest

from tests.support import TerminalTimeout

pytestmark = pytest.mark.tty


BORDERED_APP = """
    import curses

    def main(stdscr):
        curses.curs_set(0)
        stdscr.clear()
        stdscr.refresh()
        win = curses.newwin(5, 20, 1, 2)
        win.border()
        win.addstr(2, 2, "OK")
        win.refresh()
        stdscr.getch()

    curses.wrapper(main)
"""


def test_renders_plain_text(terminal, tmp_path):
    term = terminal()
    term.run_source(
        """
        import curses

        def main(stdscr):
            stdscr.addstr(3, 5, "hello terminal")
            stdscr.refresh()
            stdscr.getch()

        curses.wrapper(main)
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("hello terminal")
    assert term.text_at(3, 5, 14) == "hello terminal"
    assert term.find_text("hello terminal") == (3, 5)


def test_child_sees_the_requested_terminal_size(terminal, tmp_path):
    """The pty must be sized before the fork, or curses reads the default 80x24."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        """
        import curses

        def main(stdscr):
            rows, cols = stdscr.getmaxyx()
            stdscr.addstr(0, 0, f"size={cols}x{rows}")
            stdscr.refresh()
            stdscr.getch()

        curses.wrapper(main)
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("size=")
    assert term.row(0) == "size=40x12"


def test_borders_render_as_utf8_box_glyphs(terminal, tmp_path):
    """NCURSES_NO_UTF8_ACS keeps ACS borders readable instead of 'lqqqk'."""
    term = terminal()
    term.run_source(BORDERED_APP, workdir=tmp_path)
    term.wait_for_text("OK")
    assert term.row(1) == "  ┌──────────────────┐"
    term.assert_box(top=1, left=2, height=5, width=20)


def test_assert_box_rejects_a_misplaced_border(terminal, tmp_path):
    term = terminal()
    term.run_source(BORDERED_APP, workdir=tmp_path)
    term.wait_for_text("OK")
    with pytest.raises(AssertionError, match="malformed"):
        term.assert_box(top=2, left=2, height=5, width=20)


def test_keystrokes_reach_the_application(terminal, tmp_path):
    term = terminal()
    term.run_source(
        """
        import curses

        def main(stdscr):
            stdscr.addstr(0, 0, "ready")
            stdscr.refresh()
            while True:
                ch = stdscr.getch()
                if ch in (ord("q"), 27):
                    return
                stdscr.addstr(1, 0, f"got={ch}   ")
                stdscr.refresh()

        curses.wrapper(main)
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send_keys("A")
    term.wait_for_text("got=65")
    # A terminal sends CR for Return; the pty line discipline (ICRNL)
    # translates it to NL before the application sees it, as on real hardware.
    term.send_keys("<Return>")
    term.wait_for_text("got=10")
    term.send_keys("q")


def test_named_keys_encode_to_escape_sequences(terminal, tmp_path):
    term = terminal()
    term.run_source(
        """
        import curses

        def main(stdscr):
            stdscr.keypad(True)
            stdscr.addstr(0, 0, "ready")
            stdscr.refresh()
            while True:
                ch = stdscr.getch()
                if ch == ord("q"):
                    return
                stdscr.addstr(1, 0, f"key={curses.keyname(ch).decode()}      ")
                stdscr.refresh()

        curses.wrapper(main)
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send_keys("<Up>")
    term.wait_for_text("key=KEY_UP")
    term.send_keys("<Left>")
    term.wait_for_text("key=KEY_LEFT")
    term.send_keys("q")


def test_resize_signals_the_application(terminal, tmp_path):
    """A resize must reach the child as KEY_RESIZE with the new dimensions.

    ncurses does not update stdscr's dimensions by itself: the application has
    to call update_lines_cols()/resize_term() on KEY_RESIZE. The harness's job
    is to deliver the event and the new pty size, which is what is asserted.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        """
        import curses
        import os

        def main(stdscr):
            stdscr.keypad(True)
            stdscr.addstr(0, 0, "size=%dx%d" % (curses.COLS, curses.LINES))
            stdscr.refresh()
            while True:
                ch = stdscr.getch()
                if ch == ord("q"):
                    return
                if ch == curses.KEY_RESIZE:
                    # update_lines_cols() alone leaves COLS/LINES stale; the
                    # true size has to come from the pty and be applied with
                    # resize_term().
                    size = os.get_terminal_size()
                    curses.resize_term(size.lines, size.columns)
                    stdscr.clear()
                    stdscr.addstr(0, 0, "size=%dx%d" % (curses.COLS, curses.LINES))
                    stdscr.addstr(1, 0, "event=KEY_RESIZE")
                    stdscr.refresh()

        curses.wrapper(main)
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("size=40x12")
    term.resize(60, 20)
    term.wait_for_text("event=KEY_RESIZE")
    assert term.row(0) == "size=60x20"
    term.send_keys("q")


def test_attributes_are_readable(terminal, tmp_path):
    term = terminal()
    term.run_source(
        """
        import curses

        def main(stdscr):
            stdscr.addstr(0, 0, "bold", curses.A_BOLD)
            stdscr.addstr(1, 0, "rev", curses.A_REVERSE)
            stdscr.addstr(2, 0, "plain")
            stdscr.refresh()
            stdscr.getch()

        curses.wrapper(main)
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("plain")
    assert term.attrs_at(0, 0)["bold"] is True
    assert term.attrs_at(1, 0)["reverse"] is True
    assert term.attrs_at(2, 0)["bold"] is False


def test_stderr_is_captured_and_kept_off_the_screen(terminal, tmp_path):
    """A crashing child must not corrupt the rendered screen under assertion."""
    term = terminal()
    term.run_source(
        """
        raise RuntimeError("boom in the child")
        """,
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "boom in the child" in t.stderr, message="child traceback")
    assert "boom in the child" in term.stderr
    assert not term.contains("boom in the child")
    assert not term.contains("RuntimeError")


def test_wait_for_text_times_out_with_the_screen_in_the_message(terminal, tmp_path):
    term = terminal()
    term.run_source(
        """
        import curses

        def main(stdscr):
            stdscr.addstr(0, 0, "present")
            stdscr.refresh()
            stdscr.getch()

        curses.wrapper(main)
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("present")
    with pytest.raises(TerminalTimeout) as excinfo:
        term.wait_for_text("never appears", timeout=0.4)
    message = str(excinfo.value)
    assert "never appears" in message
    assert "present" in message  # the rendered screen is included


def test_unknown_key_symbol_is_rejected(terminal):
    term = terminal()
    with pytest.raises(ValueError, match="unknown key symbol"):
        term.send_keys("<Nonexistent>")


def test_back_tab_moves_the_cursor_back_a_tab_stop(terminal):
    """ncurses emits CSI Z, and pyte has no handler of its own for it.

    Without this the emulator's column drifts from the real one and
    everything written afterwards lands a few cells off - seen as a status
    line reading "focus ontwo", a screen no terminal would have shown.
    """
    term = terminal(cols=40, rows=4)
    term._stream.feed(b"\x1b[H" + b"x" * 20 + b"\x1b[ZHERE")
    assert term.row(0).startswith("x" * 16 + "HERE")


def test_back_tab_takes_a_count(terminal):
    term = terminal(cols=40, rows=4)
    term._stream.feed(b"\x1b[H" + b"x" * 20 + b"\x1b[2ZHERE")
    assert term.row(0).startswith("x" * 8 + "HERE")


def test_back_tab_stops_at_the_left_margin(terminal):
    term = terminal(cols=40, rows=4)
    term._stream.feed(b"\x1b[H" + b"xxx" + b"\x1b[9ZHERE")
    assert term.row(0).startswith("HERE")


def test_assert_box_waits_for_a_box_that_is_still_arriving(terminal, tmp_path):
    """curses sends a refresh as a series of writes.

    The harness can read the screen between them, so a box still arriving
    looked exactly like a box drawn wrong. That failed CI roughly one run in
    ten, and only on the slowest machine in the matrix.
    """
    term = terminal(cols=30, rows=10)
    term.run_source(
        """
import curses, time

def main(stdscr):
    stdscr.addstr(0, 0, "\\u250c" + "\\u2500" * 8 + "\\u2510")
    stdscr.addstr(1, 0, "\\u2502" + " " * 8 + "\\u2502")
    stdscr.refresh()
    time.sleep(0.4)
    stdscr.addstr(2, 0, "\\u2514" + "\\u2500" * 8 + "\\u2518")
    stdscr.refresh()
    stdscr.getch()

curses.wrapper(main)
""",
        workdir=tmp_path,
    )
    term.assert_box(top=0, left=0, height=3, width=10)
    term.send_keys("q")


def test_assert_box_still_fails_on_a_box_that_never_appears(terminal, tmp_path):
    term = terminal(cols=30, rows=10)
    term.run_source(
        """
import curses

def main(stdscr):
    stdscr.addstr(0, 0, "not a box")
    stdscr.refresh()
    stdscr.getch()

curses.wrapper(main)
""",
        workdir=tmp_path,
    )
    term.wait_for_text("not a box")
    with pytest.raises(AssertionError, match="malformed"):
        term.assert_box(top=0, left=0, height=3, width=10, timeout=0.4)
    term.send_keys("q")


# ------------------------------------------------ clicking a slow program


SLOW_MOUSE_APP = """
    import curses
    import time

    def main(stdscr):
        curses.mousemask(curses.ALL_MOUSE_EVENTS)
        curses.mouseinterval(0)
        stdscr.keypad(True)
        stdscr.addstr(0, 0, "ready")
        stdscr.refresh()
        seen = []
        stdscr.timeout(200)
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            key = stdscr.getch()
            if key != curses.KEY_MOUSE:
                continue
            try:
                state = curses.getmouse()[4]
            except curses.error:
                continue
            if state & curses.BUTTON1_PRESSED:
                seen.append("p")
            elif state & curses.BUTTON1_RELEASED:
                seen.append("r")
            # As slow as click()'s own settle, which is the boundary of what
            # it can promise: measured, all four events arrive with a handler
            # up to 0.05s and are lost from 0.08s.
            time.sleep(0.05)
            stdscr.addstr(1, 0, ("saw: " + "".join(seen) + " " * 20)[:20])
            stdscr.refresh()

    curses.wrapper(main)
"""


def test_a_click_reaches_a_program_too_slow_to_keep_up(terminal, tmp_path):
    """The rule behind click()'s two pauses, pinned against plain curses.

    **ncurses drops mouse reports that arrive faster than the application
    drains them.** No TkCurses in this test at all: a curses program whose
    handler takes 120ms loses events from clicks sent back to back, and did
    so on an idle machine. That is what made CI red more often than green -
    a test would click a list and then a button, and the button's release
    never arrived, so it was drawn pressed and never invoked.

    click() pauses after the release as well as between press and release,
    which is what a real mouse does anyway: nobody clicks twice in fifty
    milliseconds.

    The promise is bounded by ``settle``: a handler slower than that still
    loses events, measured at 0.08s. A test driving something that slow
    should pass a larger settle rather than expect this to cover it.
    """
    term = terminal(cols=40, rows=6)
    term.run_source(SLOW_MOUSE_APP, workdir=tmp_path)
    term.wait_for_text("ready")
    term.wait_for_idle()
    term.click(5, 3)
    term.click(5, 4)
    term.wait_for(
        lambda t: "saw: prpr" in "\n".join(t.display),
        message="both clicks, press and release, to arrive",
    )


# ------------------------------------------------- direct colour and pyte


@pytest.mark.parametrize(
    ("emitted", "expected"),
    [
        (b"\x1b[38:2::51:102:204m", b"\x1b[38;2;51;102;204m"),
        (b"\x1b[48:2::17:34:51m", b"\x1b[48;2;17;34;51m"),
        (b"\x1b[38:5:62m", b"\x1b[38;5;62m"),
        (b"\x1b[1;38:2::1:2:3m", b"\x1b[1;38;2;1;2;3m"),
        # Already in pyte's form, and must be left exactly alone.
        (b"\x1b[38;5;62m", b"\x1b[38;5;62m"),
        (b"\x1b[m", b"\x1b[m"),
        (b"\x1b[0m", b"\x1b[0m"),
        # Not an SGR at all.
        (b"\x1b[2J", b"\x1b[2J"),
        (b"hello", b"hello"),
    ],
    ids=[
        "direct foreground",
        "direct background",
        "indexed with colons",
        "colons after another parameter",
        "already semicolons",
        "bare reset",
        "zero reset",
        "not an SGR",
        "not a sequence",
    ],
)
def test_colon_separated_sgr_is_rewritten_for_pyte(emitted, expected):
    """ncurses emits the colon form for a direct-colour terminfo.

    It is the ITU-T T.416 spelling and real terminals accept it; pyte does
    not, and printed it as literal text - so every tty test was meaningless
    under TERM=xterm-direct, and looked like a bug in the library.
    """
    from tests.support.terminal import _COLON_SGR, _semicolons

    assert _COLON_SGR.sub(_semicolons, emitted) == expected


def test_a_direct_colour_terminal_shows_the_exact_colour(terminal, tmp_path):
    """End to end, because the rewrite above could be perfect and unwired.

    At 256 colours #3366cc is approximated by the nearest cube entry. On a
    direct-colour terminal it arrives exactly, which is the whole point of
    the terminfo and could not be seen here at all before.
    """
    term = terminal(cols=20, rows=4, env={"TERM": "xterm-direct"})
    term.run_source(
        """
        from tkcurses._core.colors import ColorManager
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            colors = ColorManager()
            colors.start()
            screen.attribute_resolver = colors.attribute_for
            buffer.write(0, 0, "XX", fg="#3366cc", bg="#112233")
            screen.refresh()
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for(lambda screen: screen.display[0].startswith("XX"), message="XX")
    assert term.display[0].startswith("XX"), (
        "escape bytes reached the screen as text\n" + term.describe()
    )
    assert term.attrs_at(0, 0)["fg"] == "3366cc"
    assert term.attrs_at(0, 0)["bg"] == "112233"
    term.send_keys("q")


def test_wait_for_cell_waits_for_the_cell_not_the_screen(terminal, tmp_path):
    """The helper that makes waiting for the right thing the easy thing.

    A marker and the cell under assertion are written by different widgets
    and reach the terminal in different frames. This program makes that gap
    explicit: 'ready' appears at once, the cell it is about a beat later.
    Waiting on the text alone would read the cell too early.
    """
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
import tkcurses
root = tkcurses.Tk()
buffer = root.tk.screen.buffer
buffer.write(0, 0, 'ready')
root.tk.screen.refresh()

def later():
    buffer.write(2, 0, 'X')
    root.tk.screen.refresh()

root.after(400, later)
root.after(6000, root.quit)
root.mainloop()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.wait_for_cell(2, 0, lambda cell: cell.data == "X", message="the late cell")
    assert term.char_at(2, 0).data == "X"


def test_a_zero_budget_drain_collects_what_has_arrived(terminal, tmp_path):
    """``_drain(0)`` means "take what is already here", not "do nothing".

    TkCurses-9q7, and the reason it took a dozen experiments to find. _drain
    computed its remaining budget and returned when it was spent - before
    reading anything - so a budget of 0 read nothing at all. Six callers meant
    "collect whatever has arrived" and collected nothing: both post-reap
    drains, the mode check in send_keys, and the received, stderr and
    application_cursor_keys properties.

    What it cost was the tail of the scenario listing. The waiting loop drains
    for 0.05s and then checks for the child, so whatever was written between
    the last poll and the exit sat in the pty, and the drain that was supposed
    to pick it up afterwards did nothing. The cut moved with load, which is
    why it failed on one Python version on a loaded runner and never here.

    This is deliberately not an end-to-end test of that race: locally the
    0.05s polls win and collect everything, so a test through wait_for_exit
    passes with the fault present - measured, both ways round. It pins the
    contract instead, with nothing draining before the assertion.
    """
    term = terminal(cols=80, rows=24)
    term.run_source('print("arrived", flush=True)', workdir=tmp_path)
    # Long enough that the bytes are certainly sitting in the pty, and no
    # drain of any kind between the child writing them and the read below.
    time.sleep(0.5)
    assert "arrived" in term.received.decode(), (
        "a zero-budget drain read nothing, so bytes already waiting in the "
        "pty were invisible to every caller that asked for them"
    )


def test_stderr_written_on_the_way_out_is_collected(terminal, tmp_path):
    """The same fault on the other channel, where it hid a diagnostic.

    The stderr property drains with a budget of 0, so it read nothing ever. An
    instrument that reported a byte count from the child's atexit handler came
    back as "the instrument did not report", and that was nearly read as the
    child having died before running it. The child ran it; nothing collected
    it. A harness that cannot report what a child said about its own failure
    turns one bug into two.
    """
    term = terminal(cols=80, rows=24)
    term.run_source(
        """
        import atexit, os, sys
        atexit.register(lambda: os.write(2, b"LAST WORDS\\n"))
        print("done", flush=True)
        sys.exit(0)
        """,
        workdir=tmp_path,
    )
    time.sleep(0.5)
    assert "LAST WORDS" in term.stderr, (
        "the child's dying words were written to the stderr pipe and never read"
    )
