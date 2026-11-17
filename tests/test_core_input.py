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
import os

import pytest

from tkcurses._core.events import MOD_ALT, MOD_CTRL, MOD_SHIFT, KeyEvent, MouseEvent
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


def test_a_key_sent_after_escape_is_that_key_with_alt(curses_stub):
    """Alt-e from a terminal is Escape and e together; ncurses hands back
    both at once, and they are the one key Tk on X11 reports. TkCurses-r3og."""
    handler = make_handler(FakeScreen([27, ord("e"), 27, ord("E"), ord("a")]))
    events = handler.poll()
    assert [(e.keysym, e.char, e.modifiers) for e in events] == [
        ("e", "e", MOD_ALT),
        ("E", "E", MOD_ALT),
        ("a", "a", 0),
    ]


def test_an_escape_on_its_own_stays_escape(curses_stub):
    handler = make_handler(FakeScreen([ord("a"), 27]))
    events = handler.poll()
    assert [(e.keysym, e.modifiers) for e in events] == [("a", 0), ("Escape", 0)]


@pytest.mark.parametrize("follower", [curses.KEY_MOUSE, curses.KEY_RESIZE])
def test_a_mouse_report_or_resize_after_escape_is_not_alt(curses_stub, follower):
    """Neither is a key, so the Escape before it stays a key of its own."""
    curses_stub.setattr(
        curses, "getmouse", lambda: (0, 1, 1, 0, curses.BUTTON1_PRESSED)
    )
    curses_stub.setattr(curses, "resize_term", lambda rows, cols: None)
    curses_stub.setattr(os, "get_terminal_size", lambda: os.terminal_size((80, 24)))
    handler = make_handler(FakeScreen([27, follower, ord("x")]))
    events = handler.poll()
    assert (events[0].type, events[0].keysym, events[0].modifiers) == (
        "key",
        "Escape",
        0,
    )
    assert events[1].type != "key"
    assert (events[-1].keysym, events[-1].modifiers) == ("x", 0)


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


# ------------------------------------------- a flood of input, TkCurses-tcbj.21


def test_poll_stops_at_its_limit_and_says_more_is_waiting(curses_stub):
    handler = make_handler(FakeScreen([ord(c) for c in "abcde"]))
    assert [event.char for event in handler.poll(3)] == ["a", "b", "c"]
    assert handler.more_pending is True
    assert [event.char for event in handler.poll(3)] == ["d", "e"]
    assert handler.more_pending is False


def test_poll_without_a_limit_reads_everything_and_nothing_is_waiting(curses_stub):
    handler = make_handler(FakeScreen([ord("a")] * 1000))
    assert len(handler.poll()) == 1000
    assert handler.more_pending is False


def test_a_limit_does_not_split_an_alt_key(curses_stub):
    """Escape and the key after it are read together or not at all."""
    handler = make_handler(FakeScreen([ord("a"), 27, ord("e"), ord("b")]))
    first = handler.poll(1)
    second = handler.poll(1)
    assert [e.keysym for e in first] == ["a"]
    assert [(e.keysym, e.modifiers) for e in second] == [("e", MOD_ALT)]
    assert [e.keysym for e in handler.poll(1)] == ["b"]


def _collapse(events, widget_at=lambda x, y: "root"):
    """Tk._collapse_motion, with ``widget_at`` deciding the window."""
    import tkcurses

    class Stub:
        _widget_at = staticmethod(widget_at)

    return tkcurses.Tk._collapse_motion(Stub(), events)


def _moved(x, state="drag", button=1, modifiers=0):
    return MouseEvent(x=x, y=0, button=button, state=state, modifiers=modifiers)


def test_a_run_of_drag_reports_is_cut_to_its_last():
    events = [_moved(x) for x in range(100)]
    assert [e.x for e in _collapse(events)] == [99]


def test_motion_is_kept_apart_by_what_comes_between():
    press = MouseEvent(x=5, y=0, button=1, state="pressed")
    key = KeyEvent(keysym="a", char="a")
    events = [_moved(1), _moved(2), press, _moved(3), _moved(4), key, _moved(5)]
    kept = [events[1], press, events[4], key, events[6]]
    assert [id(e) for e in _collapse(events)] == [id(e) for e in kept]


def test_a_change_of_modifier_ends_a_run():
    events = [_moved(1), _moved(2), _moved(3, modifiers=MOD_SHIFT), _moved(4)]
    assert [e.x for e in _collapse(events)] == [2, 3, 4]


def test_hover_motion_collapses_only_within_one_widget():
    """Tk_QueueWindowEvent replaces a held motion event only with one in the
    same window; crossing into another sends the first on."""
    events = [_moved(x, state="motion", button=0) for x in range(6)]
    collapsed = _collapse(events, lambda x, y: "left" if x < 3 else "right")
    assert [e.x for e in collapsed] == [2, 5]


class _Input:
    """An InputHandler that records whether the loop waited on it."""

    def __init__(self, more_pending):
        self.more_pending = more_pending
        self.waited = False

    def wait_for_input(self, timeout_ms):
        self.waited = True

    def poll(self, limit=None):
        return []


@pytest.mark.parametrize("more_pending", [True, False])
def test_the_loop_reads_again_at_once_after_a_read_stopped_short(more_pending):
    """What is left may be inside curses, where select() cannot see it, and
    a wait there would stall the rest of a paste for its whole timeout."""
    import types

    import tkcurses

    loop = types.SimpleNamespace(
        _input=_Input(more_pending),
        _motion_asserted=True,
        tk=types.SimpleNamespace(timers=types.SimpleNamespace(next_delay=lambda: None)),
        _collapse_motion=lambda events: events,
        _guard=lambda *call: None,
    )
    tkcurses.Tk._read_input(loop)
    assert loop._input.waited is not more_pending


# --------------------------------- a late answer to a query, TkCurses-tcbj.24

#: What a terminal with OSC 52 answers, then the DA1 fence.
_LATE = b"\x1bP1+r4d73=1b5d\x1b\\" + b"\x1b[?62;22c"


def test_a_late_reply_is_dropped_and_typing_around_it_is_not(curses_stub):
    handler = make_handler(FakeScreen([ord("a"), *_LATE, ord("b")]))
    handler.expect_late_reply()
    assert [e.keysym for e in handler.poll()] == ["a", "b"]
    # The fence came, so nothing more is looked for.
    assert handler._late_reply_until is None


def test_a_late_reply_is_typing_when_none_was_expected(curses_stub):
    """As before the fix: the reason it is only dropped after a query that
    went unanswered."""
    handler = make_handler(FakeScreen(list(_LATE)))
    assert "".join(e.char for e in handler.poll()).endswith("?62;22c")


def test_a_late_reply_is_typing_once_the_window_has_passed(curses_stub):
    handler = make_handler(FakeScreen(list(_LATE)))
    handler.expect_late_reply(window=-1)
    assert len(handler.poll()) > 2


@pytest.mark.parametrize(
    ("sent", "keys"),
    [
        (b"\x1b[x", [("[", MOD_ALT), ("x", 0)]),
        (b"\x1bPq", [("P", MOD_ALT), ("q", 0)]),
        (b"\x1bP1+z", [("P", MOD_ALT), ("1", 0), ("+", 0), ("z", 0)]),
    ],
)
def test_what_stops_looking_like_a_reply_is_read_as_typed(curses_stub, sent, keys):
    handler = make_handler(FakeScreen(list(sent)))
    handler.expect_late_reply()
    assert [(e.keysym, e.modifiers) for e in handler.poll()] == keys


# ------------------------------------- typing beyond ASCII, TkCurses-w9kd


def typed(text: str) -> list[int]:
    """What getch() returns for ``text``: a code per UTF-8 byte."""
    return list(text.encode())


def test_a_character_beyond_ascii_is_one_key(curses_stub):
    handler = make_handler(FakeScreen(typed("aé界😀b")))
    events = handler.poll()
    assert [(e.keysym, e.char) for e in events] == [
        ("a", "a"),
        ("é", "é"),
        ("界", "界"),
        ("😀", "😀"),
        ("b", "b"),
    ]
    assert [e.keycode for e in events[1:4]] == [0xE9, 0x754C, 0x1F600]
    assert not any(e.modifiers for e in events)


def test_a_character_beyond_ascii_can_be_typed_with_alt(curses_stub):
    handler = make_handler(FakeScreen([27, *typed("é")]))
    assert [(e.keysym, e.char, e.modifiers) for e in handler.poll()] == [
        ("é", "é", MOD_ALT)
    ]


@pytest.mark.parametrize(
    "sent",
    [
        b"\xa9",  # a continuation byte with nothing before it
        b"\xe7\x95",  # a character cut short
        b"\xe0\x80\x80",  # an overlong form
        b"\xed\xa0\x80",  # a surrogate
        b"\xc0\xaf",  # a lead no character uses
        b"\xff",
    ],
)
def test_bytes_that_make_no_character_are_not_text(curses_stub, sent):
    handler = make_handler(FakeScreen([*sent, ord("b")]))
    events = handler.poll()
    assert [e.keycode for e in events] == [*sent, ord("b")]
    assert [e.char for e in events] == [""] * len(sent) + ["b"]


def test_a_character_cut_short_by_another_key_keeps_the_key(curses_stub):
    handler = make_handler(FakeScreen([0xC3, 27, ord("x")]))
    events = handler.poll()
    assert [(e.keysym, e.char, e.modifiers) for e in events] == [
        ("keycode-195", "", 0),
        ("x", "x", MOD_ALT),
    ]


def test_the_rest_of_a_character_is_waited_for(curses_stub, monkeypatch):
    """A character split across two reads: getch() runs dry after its first
    byte, and the rest arrives during the wait."""
    first, *rest = typed("界")
    handler = make_handler(FakeScreen([first, curses.ERR, *rest]))
    waits = []
    monkeypatch.setattr(
        handler, "wait_for_input", lambda ms: bool(waits.append(ms)) or True
    )
    assert [e.char for e in handler.poll()] == ["界"]
    assert waits == [50]


def test_a_character_that_never_finishes_is_not_text(curses_stub, monkeypatch):
    handler = make_handler(FakeScreen([0xE7, 0x95]))
    monkeypatch.setattr(handler, "wait_for_input", lambda ms: False)
    assert [e.char for e in handler.poll()] == ["", ""]


def test_a_limit_does_not_split_a_character(curses_stub):
    handler = make_handler(FakeScreen(typed("a界b")))
    assert [e.char for e in handler.poll(limit=2)] == ["a", "界"]
    assert handler.more_pending
    assert [e.char for e in handler.poll()] == ["b"]


# ------------------------------------------ bracketed paste, TkCurses-tcbj.22

from tkcurses._core import input as input_module  # noqa: E402
from tkcurses._core.events import PasteEvent  # noqa: E402


def pasted(text: bytes) -> list[int]:
    """What getch() returns for ``text`` pasted with the mode on."""
    return list(b"\x1b[200~" + text + b"\x1b[201~")


def paste_handler(codes, **kwargs):
    return make_handler(FakeScreen(codes), bracketed_paste=True, **kwargs)


def summary(events):
    return [
        ("paste", e.text, e.complete) if isinstance(e, PasteEvent) else e.keysym
        for e in events
    ]


def test_a_paste_is_one_event_and_typing_around_it_is_keys(curses_stub):
    handler = paste_handler([ord("a"), *pasted(b"x\ry\tz"), ord("b")])
    assert summary(handler.poll()) == ["a", ("paste", "x\ry\tz", True), "b"]


def test_without_the_mode_a_paste_is_the_keys_it_always_was(curses_stub):
    handler = make_handler(FakeScreen(pasted(b"x")))
    keys = handler.poll()
    assert not any(isinstance(e, PasteEvent) for e in keys)
    assert [(e.keysym, e.modifiers) for e in keys][:2] == [("[", MOD_ALT), ("2", 0)]


@pytest.mark.parametrize(
    ("sent", "text"),
    [
        ("aé界😀".encode(), "aé界😀"),
        (b"a\xffb", "a�b"),
        (b"a\x1bb", "a\x1bb"),  # an Escape that starts no end marker
        (b"a\x1b[20x", "a\x1b[20x"),  # one that starts it and stops
        (b"a\x1b[201", "a\x1b[201"),  # the marker all but its last byte
        (b"\x1b", "\x1b"),  # an Escape just before the real marker
        (b"", ""),
    ],
)
def test_what_a_paste_holds_is_kept_as_it_came(curses_stub, sent, text):
    handler = paste_handler([*pasted(sent), ord("k")])
    assert summary(handler.poll()) == [("paste", text, True), "k"]


def test_a_paste_start_that_goes_wrong_is_read_as_typed(curses_stub):
    handler = paste_handler(list(b"\x1b[20x"))
    assert [(e.keysym, e.modifiers) for e in handler.poll()] == [
        ("[", MOD_ALT),
        ("2", 0),
        ("0", 0),
        ("x", 0),
    ]


def test_a_paste_past_the_limit_is_cut_and_the_rest_not_typed(curses_stub, monkeypatch):
    monkeypatch.setattr(input_module, "PASTE_LIMIT", 4)
    handler = paste_handler([*pasted(b"abcdefgh"), ord("k")])
    assert summary(handler.poll()) == [("paste", "abcd", False), "k"]


def test_a_paste_cut_mid_character_loses_the_character(curses_stub, monkeypatch):
    monkeypatch.setattr(input_module, "PASTE_LIMIT", 2)
    handler = paste_handler(pasted("a界".encode()))
    assert summary(handler.poll()) == [("paste", "a", False)]


def test_a_paste_whose_end_never_comes_ends(curses_stub, monkeypatch):
    handler = paste_handler(list(b"\x1b[200~abc\x1b[20"))
    waits = []
    monkeypatch.setattr(
        handler, "wait_for_input", lambda ms: bool(waits.append(ms)) and False
    )
    assert summary(handler.poll()) == [("paste", "abc\x1b[20", False)]
    assert waits == [500]


def test_a_paste_waits_out_a_pause(curses_stub, monkeypatch):
    handler = paste_handler([*b"\x1b[200~ab", curses.ERR, *b"cd\x1b[201~"])
    monkeypatch.setattr(handler, "wait_for_input", lambda ms: True)
    assert summary(handler.poll()) == [("paste", "abcd", True)]


def test_a_key_curses_decoded_inside_a_paste_is_dropped(curses_stub):
    handler = paste_handler([*b"\x1b[200~a", curses.KEY_UP, *b"b\x1b[201~", ord("k")])
    assert summary(handler.poll()) == [("paste", "ab", True), "k"]


def test_a_mouse_report_inside_a_paste_comes_after_it(curses_stub, monkeypatch):
    monkeypatch.setattr(
        curses, "getmouse", lambda: (0, 3, 4, 0, curses.BUTTON1_PRESSED)
    )
    handler = paste_handler([*b"\x1b[200~a", curses.KEY_MOUSE, *b"b\x1b[201~"])
    events = handler.poll()
    assert summary(events[:1]) == [("paste", "ab", True)]
    assert isinstance(events[1], MouseEvent)


def test_a_paste_counts_once_against_a_limit(curses_stub):
    handler = paste_handler([*pasted(b"long text"), ord("k")])
    assert summary(handler.poll(limit=1)) == [("paste", "long text", True)]
    assert [e.keysym for e in handler.poll()] == ["k"]


def test_the_terminal_is_asked_to_mark_pastes_only_when_wanted(curses_stub):
    make_handler(FakeScreen())
    assert input_module.PASTE_MODE_ON not in PUT
    handler = paste_handler([])
    assert PUT[-1] == input_module.PASTE_MODE_ON
    assert handler.paste_mode
    handler.restore()
    assert input_module.PASTE_MODE_OFF in PUT
    assert not handler.paste_mode
    assert not handler.enable_paste()


def test_a_pause_turns_the_modes_off_and_a_resume_back_on(curses_stub):
    handler = paste_handler([])
    PUT.clear()
    handler.pause()
    assert PUT == [b"\x1b[?1003l\x1b[?1002l" + input_module.PASTE_MODE_OFF]
    PUT.clear()
    handler.resume()
    assert PUT == [b"\x1b[?1002h", input_module.PASTE_MODE_ON]
    assert handler.paste_mode


def test_keys_for_text_are_the_keys_typing_it_sends(curses_stub):
    handler = make_handler(FakeScreen())
    keys = handler.keys_for("a\rb\té\x03")
    assert [(k.keysym, k.char, k.modifiers) for k in keys] == [
        ("a", "a", 0),
        ("Return", "", 0),
        ("b", "b", 0),
        ("Tab", "", 0),
        ("é", "é", 0),
        ("c", "", MOD_CTRL),
    ]
