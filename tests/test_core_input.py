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

"""Tests for tkcurses._core.input.

Mouse decoding is pure, so it is driven directly with curses button masks.
The handler itself needs a terminal and is covered by the tty tests.
"""

from __future__ import annotations

import curses

import pytest

from tkcurses._core.events import MOD_ALT, MOD_CTRL, MOD_SHIFT
from tkcurses._core.input import (
    DEFAULT_CLICK_INTERVAL,
    MouseDecoder,
    decode_modifiers,
)


@pytest.fixture
def decoder():
    return MouseDecoder()


# --------------------------------------------------------------- modifiers


def test_no_modifiers():
    assert decode_modifiers(curses.BUTTON1_PRESSED) == 0


@pytest.mark.parametrize(
    ("name", "flag"),
    [("BUTTON_SHIFT", MOD_SHIFT), ("BUTTON_CTRL", MOD_CTRL), ("BUTTON_ALT", MOD_ALT)],
)
def test_each_modifier_is_decoded(name, flag):
    mask = getattr(curses, name, 0)
    if not mask:
        pytest.skip(f"{name} is not defined on this platform")
    assert decode_modifiers(mask) & flag


def test_modifiers_combine():
    mask = curses.BUTTON_SHIFT | curses.BUTTON_CTRL
    decoded = decode_modifiers(mask)
    assert decoded & MOD_SHIFT
    assert decoded & MOD_CTRL


# ------------------------------------------------------------------ buttons


def test_press_is_decoded(decoder):
    events = decoder.decode(5, 3, curses.BUTTON1_PRESSED)
    assert len(events) == 1
    event = events[0]
    assert (event.x, event.y) == (5, 3)
    assert event.button == 1
    assert event.state == "pressed"


@pytest.mark.parametrize("button", [1, 2, 3])
def test_each_button_is_distinguished(decoder, button):
    mask = getattr(curses, f"BUTTON{button}_PRESSED")
    events = decoder.decode(0, 0, mask)
    assert events[0].button == button


def test_click_is_decoded(decoder):
    events = decoder.decode(1, 1, curses.BUTTON1_CLICKED)
    assert events[0].state == "clicked"


def test_double_click_is_decoded(decoder):
    events = decoder.decode(1, 1, curses.BUTTON1_DOUBLE_CLICKED)
    assert events[0].state == "double"


def test_triple_click_is_decoded(decoder):
    events = decoder.decode(1, 1, curses.BUTTON1_TRIPLE_CLICKED)
    assert events[0].state == "triple"


def test_a_triple_click_is_not_reported_as_a_click(decoder):
    """Curses sets both bits; the more specific state must win."""
    mask = curses.BUTTON1_TRIPLE_CLICKED | curses.BUTTON1_CLICKED
    assert decoder.decode(1, 1, mask)[0].state == "triple"


def test_wheel_events_use_buttons_four_and_five(decoder):
    up = decoder.decode(2, 2, curses.BUTTON4_PRESSED)
    assert up[0].button == 4
    assert up[0].is_scroll


def test_an_empty_mask_yields_nothing(decoder):
    assert decoder.decode(0, 0, 0) == []


def test_several_buttons_in_one_report(decoder):
    mask = curses.BUTTON1_PRESSED | curses.BUTTON3_PRESSED
    events = decoder.decode(0, 0, mask)
    assert {event.button for event in events} == {1, 3}


# -------------------------------------------------------------------- drags


def test_a_press_starts_a_drag(decoder):
    events = decoder.decode(4, 2, curses.BUTTON1_PRESSED)
    assert decoder.dragging
    assert decoder.drag_button == 1
    assert events[0].drag_start == (4, 2)


def test_motion_while_held_becomes_a_drag(decoder):
    """Curses does not report drags; they are inferred from held motion."""
    decoder.decode(4, 2, curses.BUTTON1_PRESSED)
    events = decoder.decode(9, 5, curses.REPORT_MOUSE_POSITION)
    assert len(events) == 1
    event = events[0]
    assert event.state == "drag"
    assert event.button == 1
    assert (event.x, event.y) == (9, 5)
    assert event.drag_start == (4, 2)


def test_release_ends_the_drag_and_reports_both_ends(decoder):
    decoder.decode(4, 2, curses.BUTTON1_PRESSED)
    decoder.decode(9, 5, curses.REPORT_MOUSE_POSITION)
    events = decoder.decode(12, 7, curses.BUTTON1_RELEASED)
    event = events[0]
    assert event.state == "released"
    assert event.drag_start == (4, 2)
    assert event.drag_end == (12, 7)
    assert not decoder.dragging


def test_the_full_drag_sequence(decoder):
    """The sequence ARCHITECTURE.md specifies under 'Drag Event Sequence'."""
    states = []
    states += [e.state for e in decoder.decode(10, 5, curses.BUTTON1_PRESSED)]
    states += [e.state for e in decoder.decode(15, 5, curses.REPORT_MOUSE_POSITION)]
    states += [e.state for e in decoder.decode(20, 8, curses.REPORT_MOUSE_POSITION)]
    states += [e.state for e in decoder.decode(25, 10, curses.BUTTON1_RELEASED)]
    assert states == ["pressed", "drag", "drag", "released"]


def test_releasing_a_different_button_does_not_end_the_drag(decoder):
    decoder.decode(1, 1, curses.BUTTON1_PRESSED)
    events = decoder.decode(2, 2, curses.BUTTON3_RELEASED)
    assert events[0].drag_end is None
    assert decoder.dragging, "button 1 is still held"


def test_motion_without_a_button_is_plain_motion(decoder):
    events = decoder.decode(3, 4, curses.REPORT_MOUSE_POSITION)
    assert len(events) == 1
    assert events[0].state == "motion"
    assert events[0].button == 0


def test_reset_forgets_a_drag(decoder):
    decoder.decode(1, 1, curses.BUTTON1_PRESSED)
    decoder.reset()
    assert not decoder.dragging
    assert decoder.decode(5, 5, curses.REPORT_MOUSE_POSITION)[0].state == "motion"


def test_default_click_interval_is_balanced():
    """ARCHITECTURE.md recommends 200ms as the balanced default."""
    assert DEFAULT_CLICK_INTERVAL == 200


# ---------------------------------------------------------------- handler

# These cover paths a real terminal will not produce on demand: a terminal
# refusing mouse reporting, a descriptor closed mid-shutdown, a mouse report
# that curses cannot deliver.

import threading  # noqa: E402

from tkcurses._core.dispatcher import CursesDispatcher  # noqa: E402
from tkcurses._core.input import InputHandler  # noqa: E402


class FakeScreen:
    """A curses window that records configuration and replays key codes."""

    def __init__(self, codes=()):
        self.codes = list(codes)
        self.keypad_set = None
        self.nodelay_set = None

    def keypad(self, value):
        self.keypad_set = value

    def nodelay(self, value):
        self.nodelay_set = value

    def getch(self):
        return self.codes.pop(0) if self.codes else curses.ERR


#: What the handler asked the terminal for, filled in by the stub below.
PUT: list[bytes] = []


@pytest.fixture
def curses_stub(monkeypatch):
    """Neutralise the curses calls the handler makes during setup.

    The terminal write included: it goes straight to the file descriptor, so
    without a stub these tests set the developer's own terminal reporting the
    mouse and leave it that way.
    """
    PUT.clear()
    monkeypatch.setattr(curses, "noecho", lambda: None)
    monkeypatch.setattr(curses, "cbreak", lambda: None)
    monkeypatch.setattr(curses, "mousemask", lambda mask: (mask, 0))
    monkeypatch.setattr(curses, "mouseinterval", lambda ms: None)
    monkeypatch.setattr(curses, "doupdate", lambda: None)
    monkeypatch.setattr(
        InputHandler,
        "_write_to_terminal",
        staticmethod(lambda data: bool(PUT.append(data)) or True),
    )
    return monkeypatch


def make_handler(screen, **kwargs):
    return InputHandler(
        screen,
        dispatcher=CursesDispatcher(owner_thread_id=threading.get_ident()),
        **kwargs,
    )


def test_setup_configures_curses(curses_stub):
    screen = FakeScreen()
    handler = make_handler(screen)
    assert screen.keypad_set is True
    assert screen.nodelay_set is True, "select does the waiting, not getch"
    assert handler.mouse_available


def test_decoder_is_exposed(curses_stub):
    handler = make_handler(FakeScreen())
    assert isinstance(handler.decoder, MouseDecoder)


def test_a_terminal_refusing_mouse_reporting_is_survived(curses_stub):
    def refuse(mask):
        raise curses.error("no mouse here")

    curses_stub.setattr(curses, "mousemask", refuse)
    handler = make_handler(FakeScreen())
    assert not handler.mouse_available


def test_a_terminal_reporting_no_mouse_support(curses_stub):
    curses_stub.setattr(curses, "mousemask", lambda mask: (0, 0))
    handler = make_handler(FakeScreen())
    assert not handler.mouse_available
    # Setting the interval must not be attempted when there is no mouse.
    handler.click_interval = 300
    assert handler.click_interval == 300


def test_poll_drains_every_pending_code(curses_stub):
    handler = make_handler(FakeScreen([ord("a"), ord("b"), ord("c")]))
    events = handler.poll()
    assert [event.char for event in events] == ["a", "b", "c"]


def test_poll_on_an_idle_terminal_returns_nothing(curses_stub):
    assert make_handler(FakeScreen()).poll() == []


def test_an_undeliverable_mouse_report_is_skipped(curses_stub):
    """curses raises if the report was already consumed or is malformed."""

    def refuse():
        raise curses.error("no mouse event")

    curses_stub.setattr(curses, "getmouse", refuse)
    handler = make_handler(FakeScreen([curses.KEY_MOUSE, ord("x")]))
    events = handler.poll()
    assert [event.type for event in events] == ["key"]


def test_next_event_returns_the_first_event(curses_stub, monkeypatch):
    handler = make_handler(FakeScreen([ord("q")]))
    # next_event gates on select() over the real stdin, which the fake screen
    # bypasses; report input as ready so the queued code is read.
    monkeypatch.setattr(handler, "wait_for_input", lambda timeout_ms=50: True)
    event = handler.next_event(timeout_ms=0)
    assert event is not None
    assert event.char == "q"


def test_next_event_returns_none_when_idle(curses_stub, monkeypatch):
    handler = make_handler(FakeScreen())
    monkeypatch.setattr(handler, "wait_for_input", lambda timeout_ms=50: False)
    assert handler.next_event() is None


def test_next_event_returns_none_when_input_yields_no_events(curses_stub, monkeypatch):
    """select can report readable input that produces no event at all."""
    handler = make_handler(FakeScreen())
    monkeypatch.setattr(handler, "wait_for_input", lambda timeout_ms=50: True)
    assert handler.next_event() is None


def test_waiting_on_a_closed_descriptor_reports_no_input(curses_stub):
    """During shutdown the descriptor can go away underneath the loop."""

    class ClosedStream:
        def fileno(self):
            raise ValueError("I/O operation on closed file")

    handler = make_handler(FakeScreen(), stream=ClosedStream())
    assert handler.wait_for_input(0) is False


def test_negative_click_interval_is_rejected(curses_stub):
    handler = make_handler(FakeScreen())
    with pytest.raises(ValueError, match="must not be negative"):
        handler.click_interval = -1


def test_button_masks_skips_what_a_platform_does_not_define():
    """Button 5 and some wheel masks are missing on certain builds."""
    from types import SimpleNamespace

    from tkcurses._core.input import button_masks

    partial = SimpleNamespace(
        BUTTON1_PRESSED=1,
        BUTTON1_RELEASED=2,
        BUTTON2_PRESSED=0,  # defined but unusable
    )
    masks = button_masks(partial)
    assert set(masks) == {1}, "a button with no usable masks is left out"
    assert set(masks[1]) == {"pressed", "released"}


def test_button_masks_of_this_platform_cover_the_main_buttons():
    from tkcurses._core.input import button_masks

    masks = button_masks()
    assert {1, 2, 3} <= set(masks)
    assert "pressed" in masks[1]


# --------------------------------------------------------- motion reporting


def test_the_handler_asks_the_terminal_for_drags(curses_stub):
    """ncurses asks only for press and release, whatever mousemask grants."""
    make_handler(FakeScreen())
    assert b"\x1b[?1002h" in PUT


def test_hover_reporting_is_not_asked_for_by_default(curses_stub):
    make_handler(FakeScreen())
    assert b"\x1b[?1003h" not in PUT


def test_hover_reporting_is_asked_for_when_wanted(curses_stub):
    make_handler(FakeScreen(), report_hover=True)
    assert b"\x1b[?1003h" in PUT
    assert b"\x1b[?1002h" not in PUT


def test_nothing_is_asked_for_when_motion_is_off(curses_stub):
    make_handler(FakeScreen(), report_motion=False)
    assert PUT == []


def test_the_terminal_is_put_back(curses_stub):
    handler = make_handler(FakeScreen())
    handler.disable_mouse()
    assert b"\x1b[?1003l\x1b[?1002l" in PUT


def test_putting_it_back_twice_is_harmless(curses_stub):
    handler = make_handler(FakeScreen())
    handler.disable_mouse()
    before = len(PUT)
    handler.disable_mouse()
    assert len(PUT) == before


def test_a_drag_reported_with_the_button_bit_is_still_a_drag(curses_stub):
    """Some ncurses builds set both, and reading it as a press is fatal.

    Every motion of the drag would look like a fresh press, re-anchoring the
    selection where the pointer is - so a drag would select nothing while
    press and release went on working perfectly.
    """
    handler = make_handler(FakeScreen())
    decoder = handler.decoder
    pressed = decoder.decode(4, 4, curses.BUTTON1_PRESSED)
    assert [event.state for event in pressed] == ["pressed"]
    dragged = decoder.decode(
        9, 4, curses.BUTTON1_PRESSED | curses.REPORT_MOUSE_POSITION
    )
    assert [event.state for event in dragged] == ["drag"]
    assert dragged[0].button == 1


def test_motion_with_no_button_held_is_not_a_drag(curses_stub):
    handler = make_handler(FakeScreen())
    events = handler.decoder.decode(3, 3, curses.REPORT_MOUSE_POSITION)
    assert [event.state for event in events] == ["motion"]


def test_a_press_after_a_release_is_a_press_again(curses_stub):
    handler = make_handler(FakeScreen())
    decoder = handler.decoder
    decoder.decode(1, 1, curses.BUTTON1_PRESSED)
    decoder.decode(1, 1, curses.BUTTON1_RELEASED)
    events = decoder.decode(2, 2, curses.BUTTON1_PRESSED | curses.REPORT_MOUSE_POSITION)
    assert [event.state for event in events] == ["pressed"]
