"""Tests for the pty/pyte harness itself.

Everything else asserts through this harness, so its own behaviour is verified
against plain curses programs before any TkCurses code depends on it.
"""

from __future__ import annotations

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
