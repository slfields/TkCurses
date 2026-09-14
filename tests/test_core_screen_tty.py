"""CursesScreen tests that need a real terminal.

These run the screen inside a pty and read back what the terminal displays,
which is the only way to verify that the buffer actually reaches curses.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def test_buffer_contents_reach_the_terminal(terminal, tmp_path):
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            buffer.write(1, 2, "painted from the buffer")
            screen.refresh()
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("painted")
    assert term.text_at(1, 2, 23) == "painted from the buffer"
    term.send_keys("q")


def test_buffer_is_sized_to_the_terminal(terminal, tmp_path):
    term = terminal(cols=34, rows=9)
    term.run_source(
        """
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            buffer.write(0, 0, "size=%dx%d" % (buffer.width, buffer.height))
            screen.refresh()
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("size=")
    assert term.row(0) == "size=34x9"
    term.send_keys("q")


def test_only_changed_cells_are_repainted(terminal, tmp_path):
    """An unchanged frame must cost nothing to redraw."""
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            buffer.write(0, 0, "hello")
            first = screen.refresh()
            second = screen.refresh()          # nothing changed
            buffer.write(0, 0, "hellX")        # one cell differs
            third = screen.refresh()
            buffer.write(2, 0, "counts=%d,%d,%d" % (first, second, third))
            screen.refresh()
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("counts=")
    assert term.row(2) == "counts=5,0,1"
    term.send_keys("q")


def test_attributes_are_applied(terminal, tmp_path):
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
        import curses
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            buffer.write(0, 0, "bold", attr=curses.A_BOLD)
            buffer.write(1, 0, "reverse", attr=curses.A_REVERSE)
            buffer.write(2, 0, "plain")
            screen.refresh()
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("plain")
    assert term.attrs_at(0, 0)["bold"] is True
    assert term.attrs_at(1, 0)["reverse"] is True
    assert term.attrs_at(2, 0)["bold"] is False
    term.send_keys("q")


def test_the_bottom_right_cell_can_be_written(terminal, tmp_path):
    """Writing the last cell raises in curses; the screen works around it."""
    term = terminal(cols=20, rows=5)
    term.run_source(
        """
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            buffer.fill(buffer.bounds, ".")
            buffer.write(buffer.height - 1, buffer.width - 1, "X")
            screen.refresh()
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("X")
    assert term.display[4][19] == "X"
    assert term.display[0] == "." * 20
    term.send_keys("q")


def test_the_terminal_is_restored_after_a_crash(terminal, tmp_path):
    """A failure must not leave the shell in raw mode."""
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
        import sys
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        try:
            screen.start()
            raise RuntimeError("application failure")
        except RuntimeError:
            screen.stop()
            print("terminal restored", file=sys.stderr, flush=True)
        """,
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "terminal restored" in t.stderr, message="clean teardown")
    assert "application failure" not in term.stderr


def test_context_manager_starts_and_stops(terminal, tmp_path):
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        with screen as buffer:
            buffer.write(0, 0, "inside context")
            screen.refresh()
            screen.stdscr.getch()
        assert not screen.started
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("inside context")
    term.send_keys("q")


def test_resize_updates_curses_and_the_buffer(terminal, tmp_path):
    """handle_resize must use resize_term, since update_lines_cols is stale."""
    term = terminal(cols=30, rows=8)
    term.run_source(
        """
        import curses
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            screen.stdscr.keypad(True)
            buffer.write(0, 0, "start=%dx%d" % (buffer.width, buffer.height))
            screen.refresh()
            while True:
                ch = screen.stdscr.getch()
                if ch == ord("q"):
                    break
                if ch == curses.KEY_RESIZE:
                    size = screen.handle_resize()
                    buffer.write(0, 0, "now=%dx%d" % (size.width, size.height))
                    buffer.write(1, 0, "buffer=%dx%d" % (buffer.width, buffer.height))
                    screen.refresh()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("start=30x8")
    term.resize(48, 14)
    term.wait_for_text("now=48x14")
    assert term.row(1) == "buffer=48x14"
    term.send_keys("q")


def test_shrinking_leaves_no_fragment_of_the_old_screen(terminal, tmp_path):
    """A shrinking terminal scrolls its own content and curses is not told.

    Nothing the application paints changes between the two frames, which is
    the whole difficulty: curses believes every cell already holds what is
    about to be written and so writes nothing, while the terminal has moved
    that content up the screen. Unless curses' record of the physical screen
    is discarded, the display keeps the scrolled fragment - here the bottom
    half of the old screen, showing rows that no longer exist.
    """
    term = terminal(cols=24, rows=12)
    term.run_source(
        """
        import curses
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()

        def paint():
            for row in range(buffer.height):
                buffer.write(row, 0, ("row %02d" % row)[: buffer.width])
            screen.refresh()

        try:
            screen.stdscr.keypad(True)
            paint()
            while True:
                ch = screen.stdscr.getch()
                if ch == ord("q"):
                    break
                if ch == curses.KEY_RESIZE:
                    screen.handle_resize()
                    paint()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("row 11")
    term.resize(24, 6)
    term.wait_for(lambda t: t.row(0) == "row 00", message="the repainted first row")
    assert term.display[:6] == [f"row {row:02d}".ljust(24) for row in range(6)]
    term.send_keys("q")


def test_starting_twice_is_rejected(terminal, tmp_path):
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
        import sys
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        screen.start()
        try:
            screen.start()
        except RuntimeError as exc:
            print(f"rejected: {exc}", file=sys.stderr, flush=True)
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "rejected:" in t.stderr, message="the second start")
    assert "already started" in term.stderr


def test_stop_is_idempotent(terminal, tmp_path):
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
        import sys
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        screen.start()
        screen.stop()
        screen.stop()
        print("stopped twice cleanly", file=sys.stderr, flush=True)
        """,
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "stopped twice cleanly" in t.stderr, message="teardown")


def test_using_a_stopped_screen_is_rejected(terminal, tmp_path):
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
        import sys
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        for attempt in ("buffer", "stdscr"):
            try:
                getattr(screen, attempt)
            except RuntimeError as exc:
                print(f"{attempt}: {exc}", file=sys.stderr, flush=True)
        """,
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "stdscr:" in t.stderr, message="both rejections")
    assert "buffer: screen is not started" in term.stderr
    assert "stdscr: screen is not started" in term.stderr


def test_size_reports_the_terminal_dimensions(terminal, tmp_path):
    term = terminal(cols=26, rows=7)
    term.run_source(
        """
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            buffer.write(0, 0, "size=%dx%d" % (screen.size.width, screen.size.height))
            screen.refresh()
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("size=")
    assert term.row(0) == "size=26x7"
    term.send_keys("q")


def test_failed_setup_restores_the_terminal(terminal, tmp_path):
    """If start() fails part way, the terminal must not be left in raw mode."""
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
        import curses
        import sys
        from tkcurses._core.screen import CursesScreen

        # Make setup fail after initscr has already taken over the terminal.
        curses.cbreak = lambda *a, **k: (_ for _ in ()).throw(
            curses.error("cbreak refused")
        )

        screen = CursesScreen()
        try:
            screen.start()
        except curses.error as exc:
            print(f"setup failed: {exc}", file=sys.stderr, flush=True)
        print(f"started={screen.started}", file=sys.stderr, flush=True)
        """,
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "started=" in t.stderr, message="teardown after failure")
    assert "setup failed: cbreak refused" in term.stderr
    assert "started=False" in term.stderr, "a failed start must not stay started"


def test_resize_on_a_stopped_screen_is_rejected(terminal, tmp_path):
    term = terminal(cols=30, rows=6)
    term.run_source(
        """
        import sys
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        try:
            screen.handle_resize()
        except RuntimeError as exc:
            print(f"rejected: {exc}", file=sys.stderr, flush=True)
        """,
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "rejected:" in t.stderr, message="the rejection")
    assert "not started" in term.stderr
