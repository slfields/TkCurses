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

"""What the terminal sends, read by InputHandler, over byte streams
Hypothesis invents.

Everything a terminal sends is read here: keys, a character in UTF-8 a byte
at a time, escape sequences, a late answer to a question asked at start-up,
a paste between its markers. The hand-made cases in test_core_input and
test_input_hostile are the ones someone thought of; these hold for every
stream, including the ones nobody did.
"""

from __future__ import annotations

import codecs
import contextlib
import curses
import os
import threading

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses._core.events import KeyEvent, PasteEvent
from tkcurses._core.input import InputHandler

ESCAPE = 0x1B
PASTE_START = b"\x1b[200~"
PASTE_END = b"\x1b[201~"
#: Codes curses decodes on its own, mixed in with the bytes.
KEYS = [curses.KEY_UP, curses.KEY_F1, curses.KEY_BACKSPACE, curses.KEY_DC]

#: 300 each in an ordinary run; ``TKCURSES_FUZZ_EXAMPLES=20000`` for a long
#: one, worth doing after changing a parser.
FUZZ = settings(
    max_examples=int(os.environ.get("TKCURSES_FUZZ_EXAMPLES", "300")),
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


class Terminal:
    """A curses window whose getch replays ``codes``, then has nothing."""

    def __init__(self, codes):
        self.codes = list(codes)

    def keypad(self, value):
        pass

    def nodelay(self, value):
        pass

    def getch(self):
        return self.codes.pop(0) if self.codes else curses.ERR


@contextlib.contextmanager
def reading(codes, *, paste=False, late_reply=False):
    """An InputHandler reading ``codes``, with nothing reaching the real
    terminal and nothing more ever arriving."""
    with pytest.MonkeyPatch.context() as patch:
        for name in ("noecho", "cbreak", "doupdate"):
            patch.setattr(curses, name, lambda: None)
        patch.setattr(curses, "mousemask", lambda mask: (mask, 0))
        patch.setattr(curses, "mouseinterval", lambda ms: None)

        def no_mouse():
            raise curses.error("no mouse event")

        patch.setattr(curses, "getmouse", no_mouse)
        patch.setattr(
            InputHandler, "_write_to_terminal", staticmethod(lambda data: True)
        )
        terminal = Terminal(codes)
        handler = InputHandler(
            terminal,
            dispatcher=CursesDispatcher(owner_thread_id=threading.get_ident()),
            bracketed_paste=paste,
        )
        patch.setattr(handler, "wait_for_input", lambda timeout_ms=50: False)
        if late_reply:
            handler.expect_late_reply()
        yield handler, terminal


def read_all(codes, **kwargs):
    """Every event ``codes`` make, and whether any were left unread."""
    with reading(codes, **kwargs) as (handler, terminal):
        events = handler.poll()
        return events, terminal.codes + handler._pushback


def typed(events):
    """The text the key events carry."""
    return "".join(e.char for e in events if isinstance(e, KeyEvent))


#: Anything a terminal could send: bytes, and now and then a key curses
#: decoded itself.
streams = st.lists(st.one_of(st.integers(0, 255), st.sampled_from(KEYS)), max_size=60)
#: Text with no control characters, so no byte of it is an Escape.
plain_text = st.text(
    st.characters(blacklist_categories=("Cc", "Cs")),
    max_size=40,
)


@FUZZ
@given(codes=streams, paste=st.booleans(), late_reply=st.booleans())
def test_any_stream_is_read_to_the_end_without_an_exception(codes, paste, late_reply):
    """Whatever arrives, poll returns, raises nothing, and reads it all:
    nothing is left behind to be read as something else later."""
    events, left = read_all(codes, paste=paste, late_reply=late_reply)
    assert left == []
    assert all(isinstance(e, (KeyEvent, PasteEvent)) for e in events)


@FUZZ
@given(text=plain_text)
def test_typed_text_arrives_as_exactly_that_text(text):
    """No character lost, none invented, none split into two keys."""
    events, left = read_all(list(text.encode()))
    assert left == []
    assert typed(events) == text
    assert len(events) == len(text)


@FUZZ
@given(data=st.binary(max_size=60).filter(lambda data: b"\x1b" not in data))
def test_bytes_that_are_not_utf8_never_become_text(data):
    """A lone continuation byte, a sequence cut short, an overlong form or
    a surrogate is read as keys with no character - never as a character
    the bytes do not spell. What is text is exactly what UTF-8 makes of
    them, leaving out what it cannot."""
    events, _ = read_all(list(data))
    wide = "".join(c for c in typed(events) if ord(c) > 0x7F)
    assert wide == "".join(
        c for c in data.decode("utf-8", errors="ignore") if ord(c) > 0x7F
    )


@FUZZ
@given(
    before=plain_text,
    pasted=st.binary(max_size=80).filter(lambda data: PASTE_END not in data),
    after=plain_text,
)
def test_a_paste_is_one_event_holding_what_was_pasted(before, pasted, after):
    """Whatever bytes are pasted, and whatever is typed either side."""
    sent = before.encode() + PASTE_START + pasted + PASTE_END + after.encode()
    events, left = read_all(list(sent), paste=True)
    assert left == []
    pastes = [e for e in events if isinstance(e, PasteEvent)]
    assert len(pastes) == 1
    assert pastes[0].complete
    assert pastes[0].text == pasted.decode("utf-8", errors="replace")
    at = events.index(pastes[0])
    assert typed(events[:at]) == before
    assert typed(events[at + 1 :]) == after


@FUZZ
@given(pasted=st.binary(max_size=80).filter(lambda data: PASTE_END not in data))
def test_a_paste_whose_end_never_comes_is_kept_and_marked(pasted):
    events, left = read_all(list(PASTE_START + pasted), paste=True)
    assert left == []
    assert len(events) == 1
    assert isinstance(events[0], PasteEvent)
    assert not events[0].complete
    # A character the cut left incomplete is dropped, not shown as U+FFFD.
    unfinished = codecs.getincrementaldecoder("utf-8")("replace")
    assert events[0].text == unfinished.decode(pasted, final=False)


@FUZZ
@given(text=plain_text)
def test_without_paste_mode_the_markers_are_only_typing(text):
    """A program that did not ask for marked pastes gets keys, Escape among
    them, and the pasted text as typed."""
    sent = PASTE_START + text.encode() + PASTE_END
    events, left = read_all(list(sent))
    assert left == []
    assert not any(isinstance(e, PasteEvent) for e in events)
    assert text in typed(events)


@FUZZ
@given(hex_digits=st.text("0123456789abcdefABCDEF", max_size=20), text=plain_text)
def test_a_late_reply_is_dropped_and_typing_after_it_kept(hex_digits, text):
    """The answer to the start-up clipboard question, arriving after curses
    started, is never typed into the program."""
    reply = b"\x1bP1+r" + hex_digits.encode() + b"\x1b\\" + b"\x1b[?62;22c"
    events, left = read_all(list(reply + text.encode()), late_reply=True)
    assert left == []
    assert typed(events) == text
