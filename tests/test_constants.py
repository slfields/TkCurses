"""Tests for tkcurses.constants.

The important guarantee is compatibility: application code that does
``from tkinter.constants import *`` must get identical names and values from
``tkcurses.constants``. That is checked against the real tkinter where it is
importable, rather than against a hand-copied list.
"""

from __future__ import annotations

import curses

import pytest

from tkcurses import constants

tkinter_constants = pytest.importorskip(
    "tkinter.constants", reason="tkinter is not available for cross-checking"
)


def _public_names(module) -> set[str]:
    return {name for name in dir(module) if not name.startswith("_")}


def test_defines_every_tkinter_constant():
    missing = _public_names(tkinter_constants) - _public_names(constants)
    assert not missing, f"constants missing from tkcurses: {sorted(missing)}"


@pytest.mark.parametrize("name", sorted(_public_names(tkinter_constants)))
def test_value_matches_tkinter(name):
    assert getattr(constants, name) == getattr(tkinter_constants, name)


def test_booleans_are_real_booleans():
    assert constants.TRUE is True
    assert constants.FALSE is False
    assert constants.YES is True and constants.NO is False
    assert constants.ON is True and constants.OFF is False


def test_curses_attributes_match_curses():
    for name in (
        "A_NORMAL",
        "A_STANDOUT",
        "A_UNDERLINE",
        "A_REVERSE",
        "A_BLINK",
        "A_DIM",
        "A_BOLD",
        "A_PROTECT",
        "A_INVIS",
        "A_ALTCHARSET",
        "A_ITALIC",
    ):
        assert getattr(constants, name) == getattr(curses, name)


def test_curses_colors_match_curses():
    for name in (
        "COLOR_BLACK",
        "COLOR_RED",
        "COLOR_GREEN",
        "COLOR_YELLOW",
        "COLOR_BLUE",
        "COLOR_MAGENTA",
        "COLOR_CYAN",
        "COLOR_WHITE",
    ):
        assert getattr(constants, name) == getattr(curses, name)


def test_curses_keys_match_curses():
    for name in (
        "KEY_UP",
        "KEY_DOWN",
        "KEY_LEFT",
        "KEY_RIGHT",
        "KEY_HOME",
        "KEY_END",
        "KEY_PPAGE",
        "KEY_NPAGE",
        "KEY_DC",
        "KEY_IC",
        "KEY_BACKSPACE",
        "KEY_MOUSE",
        "KEY_RESIZE",
    ):
        assert getattr(constants, name) == getattr(curses, name)


@pytest.mark.parametrize("number", [0, 1, 5, 12, 63])
def test_function_keys_are_derived(number):
    assert getattr(constants, f"KEY_F{number}") == curses.KEY_F0 + number


def test_function_key_out_of_range_is_rejected():
    with pytest.raises(ValueError, match="out of range"):
        constants._function_key(64)


def test_unknown_attribute_raises():
    unknown = "NOT_A_CONSTANT"
    with pytest.raises(AttributeError, match="has no attribute"):
        getattr(constants, unknown)


def test_acs_before_screen_initialisation_explains_itself():
    """Importing must not need a screen, so ACS access fails informatively."""
    acs = "ACS_HLINE"
    with pytest.raises(AttributeError, match="until the screen is initialised"):
        getattr(constants, acs)


@pytest.mark.tty
def test_acs_resolves_once_a_screen_exists(terminal, tmp_path):
    """Inside a curses session the ACS names resolve to real curses values."""
    term = terminal()
    term.run_source(
        """
        import curses

        def main(stdscr):
            from tkcurses import constants
            ok = (
                constants.ACS_HLINE == curses.ACS_HLINE
                and constants.ACS_ULCORNER == curses.ACS_ULCORNER
                and constants.ACS_VLINE == curses.ACS_VLINE
            )
            stdscr.addstr(0, 0, "acs-ok" if ok else "acs-MISMATCH")
            stdscr.refresh()
            stdscr.getch()

        curses.wrapper(main)
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("acs-")
    assert term.row(0) == "acs-ok"
    term.send_keys("q")
