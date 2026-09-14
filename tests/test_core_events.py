"""Tests for tkcurses._core.events."""

from __future__ import annotations

import curses

import pytest

from tkcurses._core.events import (
    MOD_ALT,
    MOD_CTRL,
    MOD_META,
    MOD_SHIFT,
    Event,
    KeyEvent,
    MouseEvent,
    ResizeEvent,
    keysym_for,
    modifier_names,
    shift_held,
)

# ------------------------------------------------------------------ events


def test_events_carry_a_type_and_timestamp():
    assert Event().type == "event"
    assert KeyEvent().type == "key"
    assert MouseEvent().type == "mouse"
    assert ResizeEvent().type == "resize"
    assert KeyEvent().time > 0


def test_key_event_printability():
    assert KeyEvent(keysym="a", char="a").is_printable
    assert not KeyEvent(keysym="Up").is_printable


def test_mouse_event_position_and_scroll():
    event = MouseEvent(x=4, y=7, button=1)
    assert event.position == (4, 7)
    assert not event.is_scroll
    assert MouseEvent(button=4).is_scroll
    assert MouseEvent(button=5).is_scroll


def test_resize_event_size():
    assert ResizeEvent(width=80, height=24).size == (80, 24)


def test_mouse_drag_fields_default_to_absent():
    event = MouseEvent(x=1, y=1, button=1, state="pressed")
    assert event.drag_start is None
    assert event.drag_end is None


# --------------------------------------------------------------- modifiers


def test_modifier_flags_are_distinct_bits():
    flags = [MOD_SHIFT, MOD_CTRL, MOD_ALT, MOD_META]
    assert len(set(flags)) == len(flags)
    for flag in flags:
        assert flag & (flag - 1) == 0, "each modifier must be a single bit"


def test_modifier_names_are_ordered_for_bindings():
    assert modifier_names(0) == ()
    assert modifier_names(MOD_CTRL) == ("Control",)
    # Order is fixed so binding strings read <Control-Alt-x>, not <Alt-Control-x>.
    assert modifier_names(MOD_ALT | MOD_CTRL) == ("Control", "Alt")
    assert modifier_names(MOD_SHIFT | MOD_CTRL | MOD_ALT | MOD_META) == (
        "Shift",
        "Control",
        "Alt",
        "Meta",
    )


# ------------------------------------------------------------------ keysym


@pytest.mark.parametrize(
    ("keycode", "expected"),
    [
        (ord("a"), "a"),
        (ord("A"), "A"),
        (ord("0"), "0"),
        (ord("~"), "~"),
        (32, "space"),
        (9, "Tab"),
        (10, "Return"),
        (13, "Return"),
        (27, "Escape"),
        (127, "BackSpace"),
    ],
)
def test_ascii_and_control_keysyms(keycode, expected):
    assert keysym_for(keycode) == expected


@pytest.mark.parametrize(
    ("keycode", "expected"),
    [
        (curses.KEY_UP, "Up"),
        (curses.KEY_DOWN, "Down"),
        (curses.KEY_LEFT, "Left"),
        (curses.KEY_RIGHT, "Right"),
        (curses.KEY_HOME, "Home"),
        (curses.KEY_END, "End"),
        (curses.KEY_PPAGE, "Prior"),
        (curses.KEY_NPAGE, "Next"),
        (curses.KEY_IC, "Insert"),
        (curses.KEY_DC, "Delete"),
        (curses.KEY_BACKSPACE, "BackSpace"),
        (curses.KEY_ENTER, "Return"),
        (curses.KEY_BTAB, "ISO_Left_Tab"),
        (curses.KEY_MOUSE, "Mouse"),
        (curses.KEY_RESIZE, "Configure"),
    ],
)
def test_special_keysyms_use_tkinter_names(keycode, expected):
    assert keysym_for(keycode) == expected


@pytest.mark.parametrize("number", [0, 1, 5, 12, 40, 63])
def test_all_function_keys_resolve(number):
    """All 64 function keys work, not only the twelve on a typical keyboard."""
    assert keysym_for(curses.KEY_F0 + number) == f"F{number}"


@pytest.mark.parametrize(("keycode", "expected"), [(1, "a"), (2, "b"), (26, "z")])
def test_control_letters_report_the_base_letter(keycode, expected):
    """Control-A arrives as 1; the keysym is the letter, the modifier is separate."""
    assert keysym_for(keycode) == expected


def test_unknown_keycode_stays_visible():
    assert keysym_for(9999) == "keycode-9999"
    assert keysym_for(-1) == "keycode--1"


def test_page_keys_use_tkinter_not_curses_names():
    """tkinter calls them Prior/Next; curses calls them PPAGE/NPAGE."""
    assert keysym_for(curses.KEY_PPAGE) == "Prior"
    assert keysym_for(curses.KEY_NPAGE) == "Next"


def test_every_printable_ascii_has_a_keysym():
    for code in range(32, 127):
        assert keysym_for(code), f"no keysym for {code}"


# ------------------------------------------------------------ shifted keys


@pytest.mark.parametrize(
    ("keycode", "expected"),
    [
        (curses.KEY_SLEFT, "Left"),
        (curses.KEY_SRIGHT, "Right"),
        (curses.KEY_SF, "Down"),
        (curses.KEY_SR, "Up"),
        (curses.KEY_SHOME, "Home"),
        (curses.KEY_SEND, "End"),
    ],
)
def test_a_shifted_arrow_is_the_plain_keysym(keycode, expected):
    """ncurses reports Shift-Down as KEY_SF, not as Down with a modifier.

    Without this, selecting with the keyboard could not work at all:
    Shift-Right was indistinguishable from Right, so nothing extended a
    selection.
    """
    assert keysym_for(keycode) == expected
    assert shift_held(keycode)


def test_a_plain_arrow_is_not_shifted():
    assert not shift_held(curses.KEY_DOWN)
    assert keysym_for(curses.KEY_DOWN) == "Down"
