"""Colour tests that need a real terminal.

The unit tests stub curses, so these confirm the manager works against the
real library: pairs are allocated, and the colours arrive at the terminal.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def test_colours_reach_the_terminal(terminal, tmp_path):
    term = terminal(cols=30, rows=6)
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

            buffer.write(0, 0, "red text", fg="red", bg="black")
            buffer.write(1, 0, "green text", fg="green", bg="black")
            buffer.write(2, 0, "blue on white", fg="blue", bg="white")
            screen.refresh()
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("blue on white")
    assert term.attrs_at(0, 0)["fg"] == "red"
    assert term.attrs_at(1, 0)["fg"] == "green"
    assert term.attrs_at(2, 0)["fg"] == "blue"
    assert term.attrs_at(2, 0)["bg"] == "white"
    term.send_keys("q")


def test_bright_colours_arrive_bold(terminal, tmp_path):
    """lime is bright green: green plus A_BOLD."""
    term = terminal(cols=30, rows=6)
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
            buffer.write(0, 0, "lime", fg="lime", bg="black")
            buffer.write(1, 0, "plain", fg="green", bg="black")
            screen.refresh()
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("plain")
    assert term.attrs_at(0, 0)["fg"] == "green"
    assert term.attrs_at(0, 0)["bold"] is True
    assert term.attrs_at(1, 0)["bold"] is False
    term.send_keys("q")


def test_hex_colours_render(terminal, tmp_path):
    term = terminal(cols=30, rows=6)
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
            buffer.write(0, 0, "orange hex", fg="#ff8000", bg="black")
            screen.refresh()
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("orange hex")
    # #ff8000 approximates to colour 3 rather than degrading to grey. pyte
    # reports colour 3 by its traditional ANSI name, "brown", not "yellow".
    assert term.attrs_at(0, 0)["fg"] == "brown"
    term.send_keys("q")


def test_pairs_are_allocated_against_real_curses(terminal, tmp_path):
    term = terminal(cols=40, rows=6)
    term.run_source(
        """
        from tkcurses._core.colors import ColorManager
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            colors = ColorManager()
            supported = colors.start()
            colors.attribute_for("red", "black")
            colors.attribute_for("red", "black")   # reused
            colors.attribute_for("blue", "black")  # new
            buffer.write(0, 0, "colour=%s pairs=%d" % (supported, colors.allocated))
            screen.refresh()
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("pairs=")
    assert term.row(0) == "colour=True pairs=2"
    term.send_keys("q")
